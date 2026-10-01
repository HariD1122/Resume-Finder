"""Shortlist email flow. Resend is faked: these tests can never send a real email."""
import json
import os

import pytest
from fastapi.testclient import TestClient

import db
import gemini
import index
import mailer
from errors import ApiError
from requirements import model_requirements
from test_api import FIX, FakeDB

REAL_SEND = mailer.send_email  # captured before fixtures replace it


@pytest.fixture()
def env(monkeypatch):
    fake = FakeDB()
    for name in ("find_by_hash", "find_by_email", "upload_file", "remove_files", "insert_candidate", "insert_scores",
                 "upsert_result", "delete_candidate", "list_candidates", "email_list", "email_insert", "email_update"):
        monkeypatch.setattr(db, name, getattr(fake, name))
    state = {"score": 5, "email": "a@example.com", "name": "Anika Rao"}
    sent = []

    def gen(role, text, pdf):
        return json.dumps({"is_resume": True, "full_name": state["name"], "email": state["email"], "location": "Mumbai",
                           "relocation": "unknown", "pm_years": 3, "applied_role_hint": role,
                           "requirements": [{"id": r.id, "score": state["score"], "evidence": "none", "reason": "r"}
                                            for r in model_requirements(role)], "probe_questions": []})

    monkeypatch.setattr(gemini, "_generate", gen)

    def fake_send(to, subject, text, key):
        sent.append({"to": to, "subject": subject, "text": text, "key": key})
        return "re_123"

    monkeypatch.setattr(mailer, "send_email", fake_send)
    client = TestClient(index.app, raise_server_exceptions=False)

    def upload(fname, role="PM", **over):
        state.update(over)
        data = open(os.path.join(FIX, fname), "rb").read()
        return client.post("/api/upload", files={"file": (fname, data, "application/pdf")}, data={"role": role})

    return client, fake, state, sent, upload


def first(client):
    return client.get("/api/emails").json()["emails"][0]


def test_drafts_only_for_shortlisted(env):
    client, _, state, sent, upload = env
    assert upload("strong_pm.pdf", score=5).json()["result"]["recommendation"] == "Shortlist"
    assert upload("weak_pm.pdf", score=1, email="b@example.com", name="Weak").json()["result"]["recommendation"] == "Pass"
    r = client.get("/api/emails").json()
    assert r["count"] == 1 and r["emails"][0]["full_name"] == "Anika Rao"
    assert not sent  # drafting never sends


def test_template_content(env):
    client, _, _, _, upload = env
    upload("strong_pm.pdf")
    e = first(client)
    for must in ("Dear Anika Rao,", "Arjun Mehta, Founder of Kargo", "Series A", "Mumbai", "shortlisted",
                 "2nd floor, WeWork, Salarpuria Symbiosis, Arekere Village, Bannerghatta Rd, Begur Hobli, Bengaluru, Karnataka 560076",
                 "1122334455", "book your interview slot", "Product Manager"):
        assert must in e["body"], must
    assert "Product Manager" in e["subject"] and e["to_email"] == "a@example.com"
    assert e["status"] == "draft" and not e["can_send"]  # the date placeholder blocks sending


def test_spm_role_title(env):
    client, _, _, _, upload = env
    upload("strong_spm.pdf", role="SPM")
    assert "Senior Product Manager" in first(client)["subject"]


def test_cannot_send_without_date_or_confirm(env):
    client, _, _, sent, upload = env
    upload("strong_pm.pdf")
    e = first(client)
    cid = e["candidate_id"]
    assert client.post(f"/api/emails/{cid}/send", json={"confirm": False, "version": e["version"]}).status_code == 400
    r = client.post(f"/api/emails/{cid}/send", json={"confirm": True, "version": e["version"]})
    assert r.status_code == 422 and "interview date" in r.json()["error"]["message"]
    assert not sent


def test_set_date_edit_and_send_once(env):
    client, _, _, sent, upload = env
    upload("strong_pm.pdf")
    cid = first(client)["candidate_id"]
    assert client.post("/api/emails/interview-date", json={"interview_at": "Monday, 12 October 2026, 10:30 AM"}).json()["updated"] == 1
    e = first(client)
    assert "Monday, 12 October 2026, 10:30 AM" in e["body"] and e["can_send"]
    # edit the body, then change the date: the edit survives and only the date text is swapped
    body = e["body"].replace("We look forward to meeting you.", "We look forward to meeting you in person.")
    assert client.put(f"/api/emails/{cid}", json={"subject": e["subject"], "body": body}).status_code == 200
    client.post("/api/emails/interview-date", json={"interview_at": "Tuesday, 13 October 2026, 11:00 AM"})
    e2 = first(client)
    assert "in person." in e2["body"] and "Tuesday, 13 October 2026, 11:00 AM" in e2["body"] and "Monday" not in e2["body"]
    # a stale version is refused
    assert client.post(f"/api/emails/{cid}/send", json={"confirm": True, "version": e["version"]}).status_code == 409
    assert not sent
    r = client.post(f"/api/emails/{cid}/send", json={"confirm": True, "version": e2["version"]})
    assert r.status_code == 200 and len(sent) == 1 and sent[0]["to"] == "a@example.com" and "in person." in sent[0]["text"]
    # a second send and editing after send are refused
    assert client.post(f"/api/emails/{cid}/send", json={"confirm": True, "version": e2["version"]}).status_code == 409
    assert client.put(f"/api/emails/{cid}", json={"subject": "x", "body": "y"}).status_code == 409
    assert len(sent) == 1
    after = first(client)
    assert after["status"] == "sent" and not after["editable"]


def test_missing_recipient_blocked(env):
    client, _, _, sent, upload = env
    upload("strong_pm.pdf", email=None)
    client.post("/api/emails/interview-date", json={"interview_at": "Monday 10 AM"})
    e = first(client)
    assert not e["can_send"] and any("No email" in b for b in e["blockers"])
    assert client.post(f"/api/emails/{e['candidate_id']}/send", json={"confirm": True, "version": e["version"]}).status_code == 422
    assert not sent


def test_resend_failure_marks_failed_and_allows_retry(env, monkeypatch):
    client, _, _, sent, upload = env
    upload("strong_pm.pdf")
    client.post("/api/emails/interview-date", json={"interview_at": "Monday 10 AM"})
    e = first(client)

    def boom(*a):
        raise ApiError(502, "email_rejected", "The email service rejected the message: testing")

    monkeypatch.setattr(mailer, "send_email", boom)
    r = client.post(f"/api/emails/{e['candidate_id']}/send", json={"confirm": True, "version": e["version"]})
    assert r.status_code == 502, r.text
    f = first(client)
    assert f["status"] == "failed" and "rejected" in f["error"] and f["editable"]
    monkeypatch.setattr(mailer, "send_email", lambda to, s, t, k: "re_ok")
    assert client.post(f"/api/emails/{f['candidate_id']}/send", json={"confirm": True, "version": f["version"]}).status_code == 200


def test_no_longer_shortlisted_is_blocked(env):
    client, fake, _, sent, upload = env
    upload("strong_pm.pdf")
    client.post("/api/emails/interview-date", json={"interview_at": "Monday 10 AM"})
    e = first(client)
    fake.results[e["candidate_id"]]["recommendation"] = "Hold"  # e.g. weights changed and recompute ran
    assert client.get("/api/emails").json()["count"] == 0
    assert client.post(f"/api/emails/{e['candidate_id']}/send", json={"confirm": True, "version": e["version"]}).status_code == 422
    assert not sent


def test_html_is_escaped():
    out = mailer._to_html("Hi <script>alert(1)</script>\n\nBye")
    assert "<script>" not in out and "&lt;script&gt;" in out


def test_test_mode_redirects_and_keeps_draft_unsent(env, monkeypatch):
    client, _, _, sent, upload = env
    monkeypatch.setenv("RESEND_TEST_RECIPIENT", "owner@example.com")
    upload("strong_pm.pdf")
    client.post("/api/emails/interview-date", json={"interview_at": "Monday 10 AM"})
    e = first(client)
    assert client.get("/api/emails").json()["test_recipient"] == "owner@example.com"
    r = client.post(f"/api/emails/{e['candidate_id']}/send", json={"confirm": True, "version": e["version"]})
    assert r.status_code == 200 and r.json()["status"] == "test_sent"
    assert sent[0]["to"] == "owner@example.com" and sent[0]["subject"].startswith("[TEST - intended for a@example.com]")
    assert first(client)["status"] == "draft"  # the real draft is untouched
    assert client.post(f"/api/emails/{e['candidate_id']}/send", json={"confirm": False, "version": e["version"]}).status_code == 400


# ---- Gmail provider (SMTP is faked; nothing is sent)
class FakeSMTP:
    log = []
    fail_login = False

    def __init__(self, host, port, timeout=None, context=None):
        FakeSMTP.log.append(("connect", host, port))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, user, pw):
        if FakeSMTP.fail_login:
            import smtplib
            raise smtplib.SMTPAuthenticationError(535, b"bad")
        FakeSMTP.log.append(("login", user, pw))

    def send_message(self, msg):
        FakeSMTP.log.append(("send", msg["To"], msg["From"], msg["Subject"], msg.get_body(("plain",)).get_content()))


@pytest.fixture()
def gmail(monkeypatch):
    import smtplib
    FakeSMTP.log, FakeSMTP.fail_login = [], False
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setenv("GMAIL_USER", "owner@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setenv("RESEND_TEST_RECIPIENT", "owner@gmail.com")  # must be ignored with Gmail
    return FakeSMTP


def test_gmail_provider_sends_to_any_address(gmail):
    assert mailer.provider() == "gmail" and mailer.test_recipient() is None
    mid = mailer._send_gmail("someone@anydomain.com", "Subj", "Hello\n\nBody")
    kinds = [x[0] for x in gmail.log]
    assert kinds == ["connect", "login", "send"] and mid.startswith("<")
    assert gmail.log[1][2] == "abcdefghijklmnop"  # spaces stripped from the app password
    sent = gmail.log[2]
    assert sent[1] == "someone@anydomain.com" and "Arjun Mehta" in sent[2] and "owner@gmail.com" in sent[2]


def test_gmail_auth_failure_is_clear(gmail):
    gmail.fail_login = True
    with pytest.raises(ApiError) as e:
        mailer._send_gmail("x@y.com", "s", "t")
    assert e.value.code == "email_auth" and "app password" in e.value.message


def test_full_send_flow_with_gmail_is_real_not_test_mode(env, gmail, monkeypatch):
    client, _, _, _, upload = env
    monkeypatch.setattr(mailer, "send_email", REAL_SEND)  # run the real dispatcher against the fake SMTP
    FakeSMTP.log = []
    upload("strong_pm.pdf")
    client.post("/api/emails/interview-date", json={"interview_at": "Monday 10 AM"})
    e = first(client)
    assert client.get("/api/emails").json()["provider"] == "gmail"
    r = client.post(f"/api/emails/{e['candidate_id']}/send", json={"confirm": True, "version": e["version"]})
    assert r.status_code == 200 and r.json()["status"] == "sent"
    sends = [x for x in FakeSMTP.log if x[0] == "send"]
    assert len(sends) == 1 and sends[0][1] == "a@example.com" and not sends[0][3].startswith("[TEST")
    assert first(client)["status"] == "sent"
