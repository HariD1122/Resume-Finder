# Resume Finder

Upload CVs, let Gemini extract the facts and score each candidate against weighted role requirements, and review a ranked, evidence-backed shortlist. Built for the (fictional) Kargo hiring case: a founder with two open roles, 60 CVs and no record of why anyone was shortlisted.

**The app recommends. A person decides.** It never says "rejected", and it sends an email only after a person reviews it and clicks confirm.

## Architecture

```
Browser (React + Vite, plain CSS)
   |  relative /api calls (no secrets in the browser)
   v
Vercel  --  static site (dist) + Python serverless function api/index.py (FastAPI)
   |                         |
   v                         v
Supabase (Postgres + private    Gemini API (google-genai)
Storage bucket "resumes")

GitHub (main) --push--> Vercel auto-deploy
```

## Setup

1. Copy `.env.example` to `.env` and fill in **new** keys (never paste secrets into chat or code).
2. Create the database: paste `supabase/schema.sql` into Supabase Dashboard -> SQL Editor -> Run. (The secret key cannot run DDL.) Then `python scripts/setup_supabase.py` checks the tables and creates the private `resumes` bucket.
3. Local development:
   ```bash
   python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
   npm install
   .venv/Scripts/python -m uvicorn index:app --app-dir api --port 8000   # backend (reads .env via your shell)
   npm run dev                                                           # UI on :5173, proxies /api to :8000
   ```
   No keys yet? `python scripts/dev_mock.py` runs the API with an in-memory database and a **fake** Gemini (UI exploration only).
4. Tests: `python scripts/make_fixtures.py && python -m pytest` (no network needed). Fixtures are fictional CVs.

## Shortlist emails (Emails tab)

- A draft invitation is written for **shortlisted candidates only** (official structure, from Arjun Mehta, with the interview venue and phone number).
- Set the interview date once; it fills every unsent draft. Sending is blocked until a date is set, and for candidates without an email address or who are no longer shortlisted.
- Every draft is editable until sent. "Review and send" opens a confirmation; the server also requires `confirm=true` and the exact draft version you reviewed, and refuses to send twice.
- Sending provider: **Gmail** when `GMAIL_USER` and `GMAIL_APP_PASSWORD` are set (an app password from myaccount.google.com/apppasswords; sends to any address, about 500 a day, no domain needed). Otherwise **Resend** (`RESEND_API_KEY`, `RESEND_FROM`); Resend's sandbox sender only delivers to your own Resend account email, so verify a domain at resend.com/domains and set `RESEND_FROM` to email candidates. `RESEND_TEST_RECIPIENT` turns on a Resend-only test mode that redirects every send to one address.
- Venue and phone live in `api/mailer.py`.

## How scoring works

- Requirements, weights and rubric anchors live in `api/requirements.py`; thresholds and limits in `api/constants.py`. Each role's weights total exactly 100 (unit-tested).
- Gemini scores the "model" requirements 0-5 and must quote the resume. Python then **verifies each quote appears in the resume** (otherwise the quote becomes "No verifiable quote" and the score drops by 1), clamps scores, and does all arithmetic.
- Computed in Python: PM experience (PM9 / SP11) from `pm_years`, and location (PM10 / SP12): Mumbai region = 5, willing to relocate = 5, unknown = 3, unwilling = 0.
- Weighted score = sum(weight x score / 5). Shortlist >= 70, Hold >= 55, otherwise Pass; location score 0 -> "Pass (location)"; a resume with fewer than 2 evidenced requirements is held ("Insufficient information"), never silently rejected.
- Rank: weighted score, then sum of core requirement scores, then earliest upload.
- Changed weights or thresholds? `POST /api/recompute` re-scores everything from stored per-requirement scores without calling Gemini.
- To add a role: add its requirements and context in `api/requirements.py`, extend the `role` check in the schema, and add it to `ROLES`.

### Limitation: JD-fit is not success prediction
The score ranks fit to the **job description**. The case's own finding is that the spec does not predict who succeeds; the eight past hires shared something the spec never named. This app does not claim to predict success. Calibration would be added later as a new requirement with its own weight plus a "similar to thriving hires" evidence line, built from the past-hire profiles.

## API

`POST /api/upload` (file + role PM|SPM), `GET /api/candidates?role=`, `GET /api/contacts`, `GET /api/resume-url?candidate_id=` (signed URL, 10 min), `GET /api/health`, `GET /api/config`, `GET /api/emails`, `PUT /api/emails/{id}`, `POST /api/emails/interview-date`, `POST /api/emails/{id}/send`, `POST /api/reset`, `POST /api/recompute`. Errors: `{"error":{"code","message"}}`.

## Privacy and security

- Resumes hold personal data. The bucket is private, row-level security is on with no policies (only the backend's secret key can read or write), downloads use 10-minute signed URLs, and no resume text or PII is logged.
- **Set `APP_ACCESS_CODE` before sharing the URL**, otherwise anyone with the link can see candidate data.
- Prompt-injection defence: resume text is delimited and declared as data, output is schema-validated, quotes verified, arithmetic done in Python. Instruction-like text in a CV is flagged in the notes.
- Fairness: the prompt forbids protected attributes and the schema has no field for them.
- Reset permanently deletes all rows and stored files.

## Known limits

4 MB file cap (Vercel request limit); legacy `.doc` is best effort; Gemini rate limits mean uploads run one at a time; scanned PDFs are read by Gemini directly; emails go out only after confirmation in the Emails tab.

## Decisions and assumptions

- App name is **Resume Finder** (the build prompts called it "Kargo Resume Screener").
- Supabase is called over `httpx` (PostgREST + Storage) with the key in the `apikey` header, avoiding supabase-py key-format issues and keeping the function small.
- Gemini is called before the file is stored, so the email-duplicate check and the "not a resume" check leave nothing behind to clean up.
- If any database step fails after the file is stored, the file and partial rows are deleted.
- The browser polls `/api/health` every 60 s; Refresh compares counts and latest `updated_at` per role with the health report.
- `.doc` text is pulled heuristically from the binary; if too little is found the file fails with a convert-to-PDF/DOCX message.

## Roadmap (out of scope now)

Calibration against the 8 past hires; a decision column (move forward / hold / pass) for the founder; respectful replies for candidates who are not advanced, and follow-up with the two August candidates (invitation emails for shortlisted candidates already exist).
