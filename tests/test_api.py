"""Upload flow with the database and Gemini replaced by fakes (no network)."""
import json
import os

import pytest
from fastapi.testclient import TestClient

import db
import gemini
import index
from errors import DuplicateError
from requirements import model_requirements

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


class FakeDB:
    def __init__(self):
        self.cands, self.scores, self.results, self.files = {}, {}, {}, {}
        self.emails, self.tick = {}, 0

    def find_by_hash(self, role, h):
        return next((c["id"] for c in self.cands.values() if c["role"] == role and c["file_hash"] == h), None)

    def find_by_email(self, role, e):
        return next((c["id"] for c in self.cands.values() if c["role"] == role and (c["email"] or "").lower() == e.lower()), None)

    def upload_file(self, path, data, ct):
        self.files[path] = data

    def remove_files(self, paths):
        for p in paths:
            self.files.pop(p, None)

    def insert_candidate(self, row):
        self.cands[row["id"]] = dict(row, created_at="2025-01-01T00:00:00Z", updated_at="2025-01-01T00:00:00Z")
        return row

    def insert_scores(self, rows):
        self.scores[rows[0]["candidate_id"]] = rows

    def upsert_result(self, row):
        self.results[row["candidate_id"]] = row

    def delete_candidate(self, cid):
        self.cands.pop(cid, None)

    def email_list(self):
        return [dict(e) for e in self.emails.values()]

    def email_insert(self, row):
        if row["candidate_id"] not in self.emails:
            self.tick += 1
            self.emails[row["candidate_id"]] = dict(row, edited=False, status=row.get("status", "draft"), error=None,
                                                    updated_at=f"v{self.tick}", sent_at=None)

    def email_update(self, cid, patch, only=None):
        e = self.emails.get(cid)
        if not e or (only and e["status"] not in only):
            return None
        self.tick += 1
        e.update(patch, updated_at=f"v{self.tick}")
        return dict(e)

    def list_candidates(self, role=None):
        return [dict(c, scores=self.scores.get(c["id"], []), results=self.results.get(c["id"]))
                for c in self.cands.values() if role in (None, c["role"])]


def raw_for(role="PM", score=4, email="anika.rao@example.com", is_resume=True):
    if not is_resume:
        return {"is_resume": False, "requirements": [], "probe_questions": []}
    return {"is_resume": True, "full_name": "Anika Rao", "email": email, "phone": "+91 98200 11111",
            "location": "Mumbai", "relocation": "unknown", "pm_years": 3, "applied_role_hint": role,
            "requirements": [{"id": r.id, "score": score, "evidence": "none", "reason": "r"} for r in model_requirements(role)],
            "probe_questions": ["a", "b"]}


@pytest.fixture()
def env(monkeypatch):
    fake = FakeDB()
    for name in ("find_by_hash", "find_by_email", "upload_file", "remove_files", "insert_candidate", "insert_scores",
                 "upsert_result", "delete_candidate", "list_candidates"):
        monkeypatch.setattr(db, name, getattr(fake, name))
    holder = {"raw": raw_for()}
    monkeypatch.setattr(gemini, "_generate", lambda role, text, pdf: json.dumps(holder["raw"]))
    return TestClient(index.app, raise_server_exceptions=False), fake, holder


def post(client, name, role="PM"):
    data = open(os.path.join(FIX, name), "rb").read()
    return client.post("/api/upload", files={"file": (name, data, "application/pdf")}, data={"role": role})


def test_upload_saves_and_scores(env):
    client, fake, _ = env
    r = post(client, "strong_pm.pdf")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "saved"
    # 8 model reqs at 4: (100-3-2)*0.8 = 76.0, plus PM9=5 (3) and PM10=5 (2) -> 81.0
    assert body["result"]["weighted_score"] == 81.0 and body["result"]["recommendation"] == "Shortlist"
    assert len(fake.files) == 1 and len(body["scores"]) == 10
    listed = client.get("/api/candidates?role=PM").json()
    assert listed["count"] == 1 and listed["candidates"][0]["rank"] == 1
    assert client.get("/api/contacts").json()["contacts"][0]["email"] == "anika.rao@example.com"


def test_duplicate_hash_and_email(env):
    client, fake, holder = env
    assert post(client, "strong_pm.pdf").status_code == 200
    assert post(client, "duplicate_of_strong_pm.pdf").json()["status"] == "duplicate"
    assert post(client, "weak_pm.pdf").status_code == 409  # same email in the model output
    assert len(fake.cands) == 1
    holder["raw"] = raw_for("SPM", email="anika.rao@example.com")
    assert post(client, "strong_pm.pdf", role="SPM").status_code == 200  # same person, other role is allowed


def test_not_a_resume_saves_nothing(env):
    client, fake, holder = env
    holder["raw"] = raw_for(is_resume=False)
    r = post(client, "invoice.pdf")
    assert r.status_code == 422 and r.json()["error"]["code"] == "not_a_resume"
    assert not fake.cands and not fake.files


def test_encrypted_and_bad_inputs(env):
    client, fake, _ = env
    r = post(client, "encrypted.pdf")
    assert r.status_code == 422 and "password" in r.json()["error"]["message"]
    assert client.post("/api/upload", files={"file": ("x.txt", b"hi", "text/plain")}, data={"role": "PM"}).status_code == 415
    assert post(client, "strong_pm.pdf", role="XX").status_code == 422
    assert not fake.cands


def test_failed_db_step_cleans_up(env, monkeypatch):
    client, fake, _ = env

    def boom(rows):
        raise RuntimeError("db down")

    monkeypatch.setattr(db, "insert_scores", boom)
    r = post(client, "strong_pm.pdf")
    assert r.status_code == 500 and not fake.cands and not fake.files


def test_injection_note_and_no_inflation(env, monkeypatch):
    client, fake, holder = env
    holder["raw"] = raw_for(score=1, email="dev@example.com")
    r = post(client, "injection_pm.pdf")
    assert r.status_code == 200
    assert "instruction-like" in r.json()["candidate"]["extraction_notes"]
    assert r.json()["result"]["weighted_score"] < 50


def test_access_code(env, monkeypatch):
    client, _, _ = env
    monkeypatch.setenv("APP_ACCESS_CODE", "s3cret")
    assert client.get("/api/candidates?role=PM").status_code == 401
    assert client.get("/api/candidates?role=PM", headers={"X-Access-Code": "s3cret"}).status_code == 200
    assert client.get("/api/health").json()["access_required"] is True
