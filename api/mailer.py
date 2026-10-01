"""Shortlist email drafts and sending via Resend.

Drafts are plain templates (no AI). Nothing is ever sent without an explicit confirmed
request from the Emails tab; see POST /api/emails/{id}/send.
"""
import html
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import httpx

from errors import ApiError

PLACEHOLDER = "[interview date and time - to be added]"
VENUE = "2nd floor, WeWork, Salarpuria Symbiosis, Arekere Village, Bannerghatta Rd, Begur Hobli, Bengaluru, Karnataka 560076"
PHONE = "1122334455"
ROLE_TITLES = {"PM": "Product Manager", "SPM": "Senior Product Manager"}


def provider() -> str:
    """'gmail' when GMAIL_USER and GMAIL_APP_PASSWORD are set (sends to anyone, no domain needed), else 'resend'."""
    return "gmail" if os.environ.get("GMAIL_USER") and os.environ.get("GMAIL_APP_PASSWORD") else "resend"


def configured() -> bool:
    return provider() == "gmail" or bool(os.environ.get("RESEND_API_KEY"))


def from_display() -> str:
    if provider() == "gmail":
        return formataddr((os.environ.get("GMAIL_FROM_NAME") or "Arjun Mehta", os.environ["GMAIL_USER"]))
    return os.environ.get("RESEND_FROM") or "Arjun Mehta <onboarding@resend.dev>"


def test_recipient():
    """Resend sandbox only: when set (RESEND_TEST_RECIPIENT), every send goes to this address only, as a labelled test.
    Never active with Gmail, which can deliver to any address."""
    if provider() == "gmail":
        return None
    return (os.environ.get("RESEND_TEST_RECIPIENT") or "").strip() or None


def subject_for(role: str) -> str:
    return f"Shortlisted for the {ROLE_TITLES[role]} role at Kargo - Invitation to In-Person Interview"


def body_for(name, role: str, interview_at) -> str:
    title = ROLE_TITLES[role]
    when = (interview_at or "").strip() or PLACEHOLDER
    greet = f"Dear {name}," if name else "Dear Candidate,"
    return (
        f"{greet}\n\n"
        f"I am Arjun Mehta, Founder of Kargo, a Series A logistics software company based in Mumbai. "
        f"Thank you for applying for the position of {title} at Kargo.\n\n"
        f"I am pleased to inform you that, after reviewing your application, you have been shortlisted for this role. "
        f"We would like to invite you to attend an in-person interview.\n\n"
        f"Interview details\n"
        f"Role: {title}\n"
        f"Date and time: {when}\n"
        f"Venue: {VENUE}\n\n"
        f"If you are interested in taking this forward, please call us on {PHONE} to book your interview slot. "
        f"Kindly carry a copy of your resume and a valid photo ID.\n\n"
        f"Should you have any questions, please feel free to call the same number.\n\n"
        f"We look forward to meeting you.\n\n"
        f"Yours sincerely,\n"
        f"Arjun Mehta\n"
        f"Founder, Kargo\n"
        f"Mumbai, India"
    )


def apply_date(row: dict, new_date: str) -> dict:
    """Patch for an unsent draft when the interview date changes. Edited bodies only get the date text swapped."""
    new_date = (new_date or "").strip()
    old = (row.get("interview_at") or "").strip() or PLACEHOLDER
    new_text = new_date or PLACEHOLDER
    if row.get("edited"):
        body = row["body"].replace(old, new_text) if old in row["body"] else row["body"]
    else:
        body = None  # caller regenerates from the template
    return {"interview_at": new_date or None, "body": body}


def blockers(row: dict, shortlisted: bool) -> list:
    out = []
    if not shortlisted:
        out.append("Candidate is no longer on the shortlist.")
    if not row.get("to_email"):
        out.append("No email address was found on this resume.")
    if PLACEHOLDER in row.get("body", "") or PLACEHOLDER in row.get("subject", ""):
        out.append("Add the interview date and time before sending.")
    if not row.get("subject", "").strip() or not row.get("body", "").strip():
        out.append("Subject and body cannot be empty.")
    return out


def _to_html(text: str) -> str:
    paras = [p for p in text.split("\n\n")]
    return "<div style=\"font-family:Arial,sans-serif;font-size:14px;line-height:1.6;color:#0f172a\">" + "".join(
        f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in paras) + "</div>"


def send_email(to: str, subject: str, text: str, idempotency_key: str) -> str:
    """Sends through the active provider and returns a message id. Tests monkeypatch this."""
    if provider() == "gmail":
        return _send_gmail(to, subject, text)
    return _send_resend(to, subject, text, idempotency_key)


def _send_gmail(to: str, subject: str, text: str) -> str:
    user = os.environ["GMAIL_USER"]
    msg = EmailMessage()
    msg["From"] = from_display()
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=user.split("@")[-1])
    msg.set_content(text)
    msg.add_alternative(_to_html(text), subtype="html")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30, context=ssl.create_default_context()) as smtp:
            smtp.login(user, os.environ["GMAIL_APP_PASSWORD"].replace(" ", ""))
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise ApiError(502, "email_auth", "Gmail rejected the login. Check GMAIL_USER and the app password (2-Step Verification must be on).")
    except smtplib.SMTPRecipientsRefused:
        raise ApiError(502, "email_rejected", "Gmail refused this recipient address. Check the candidate's email.")
    except (smtplib.SMTPException, OSError):
        raise ApiError(502, "email_unreachable", "Gmail could not be reached or refused the message. Nothing was confirmed as sent; please retry.")
    return msg["Message-ID"]


def _send_resend(to: str, subject: str, text: str, idempotency_key: str) -> str:
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        raise ApiError(500, "email_not_configured", "Email sending is not configured.")
    sender = os.environ.get("RESEND_FROM") or "Arjun Mehta <onboarding@resend.dev>"
    try:
        r = httpx.post("https://api.resend.com/emails", timeout=30,
                       headers={"Authorization": f"Bearer {key}", "Idempotency-Key": idempotency_key},
                       json={"from": sender, "to": [to], "subject": subject, "text": text, "html": _to_html(text)})
    except httpx.HTTPError:
        raise ApiError(502, "email_unreachable", "The email service could not be reached. Nothing was sent; please retry.")
    if r.status_code >= 400:
        try:
            detail = r.json().get("message", "")
        except Exception:
            detail = ""
        if "verify a domain" in detail.lower():
            detail += " (Fix: verify a domain at resend.com/domains and set RESEND_FROM, or set RESEND_TEST_RECIPIENT for test mode.)"
        raise ApiError(502, "email_rejected", f"The email service rejected the message: {detail[:450] or r.status_code}")
    return r.json().get("id", "")
