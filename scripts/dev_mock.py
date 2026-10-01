"""UI-only dev server: in-memory database and a FAKE Gemini, so the app can be explored with no keys.

    python scripts/dev_mock.py     # API on :8000, then `npm run dev` for the UI

Scores here are pseudo-random but deterministic per file. Never use for real screening.
"""
import hashlib
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "api"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import uvicorn  # noqa: E402

import db  # noqa: E402
import gemini  # noqa: E402
import index  # noqa: E402
from requirements import model_requirements  # noqa: E402
from test_api import FakeDB  # noqa: E402

fake = FakeDB()
fake.signed = lambda path: "http://127.0.0.1:8000/api/config"
for name in ("find_by_hash", "find_by_email", "upload_file", "remove_files", "insert_candidate", "insert_scores",
             "upsert_result", "delete_candidate", "list_candidates", "email_list", "email_insert", "email_update"):
    setattr(db, name, getattr(fake, name))
db.health_counts = lambda: {
    "candidates": len(fake.cands), "PM": sum(c["role"] == "PM" for c in fake.cands.values()),
    "SPM": sum(c["role"] == "SPM" for c in fake.cands.values()),
    "latest_updated_at": "2025-01-01T00:00:00Z" if fake.cands else None,
    "latest_by_role": {r: ("2025-01-01T00:00:00Z" if any(c["role"] == r for c in fake.cands.values()) else None) for r in ("PM", "SPM")}}


def reset_all():
    n = {"candidates": len(fake.cands), "scores": len(fake.scores), "results": len(fake.results), "files": len(fake.files)}
    fake.cands.clear(); fake.scores.clear(); fake.results.clear(); fake.files.clear()
    return n


db.reset_all = reset_all
db.count_bucket = lambda: len(fake.files)
db.get_candidate = lambda cid: fake.cands.get(cid)
db.signed_url = fake.signed
gemini.gemini_ok = lambda: True


def fake_generate(role, text, pdf):
    seed = int(hashlib.sha256((text or "x").encode()).hexdigest(), 16)
    words = (text or "Candidate Name").split()
    first = (text or "Mock Candidate").strip().splitlines()[0][:40]
    reqs = []
    for i, r in enumerate(model_requirements(role)):
        sc = 5 if "FreightLoop" in (text or "") else (seed >> (i * 3)) % 6  # strong sample CV -> shortlist
        quote = " ".join(words[i * 3:i * 3 + 5]) if sc else "none"
        reqs.append({"id": r.id, "score": sc, "evidence": quote, "reason": f"Mock reason for {r.short}."})
    return json.dumps({
        "is_resume": "INVOICE" not in (text or ""), "full_name": first, "email": f"cand{seed % 10000}@example.com",
        "phone": "+91 98200 1" + str(seed % 10000).zfill(4), "address": None, "current_company": "Mock Co",
        "current_title": "Product Manager", "pm_years": 2 + seed % 6, "location": ["Mumbai", "Pune", "Bengaluru"][seed % 3],
        "relocation": "unknown" if "FreightLoop" in (text or "") else ["unknown", "willing", "unwilling"][seed % 3], "summary": "Mock summary generated offline.",
        "applied_role_hint": role, "requirements": reqs, "probe_questions": ["Mock question one?", "Mock question two?"]})


gemini._generate = fake_generate
import mailer  # noqa: E402
mailer.send_email = lambda to, subject, text, key: 'mock-' + key[:8]  # never really sends

if __name__ == "__main__":
    uvicorn.run(index.app, host="127.0.0.1", port=8000)
