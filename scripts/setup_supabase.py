"""Check the Supabase project is ready: tables exist and the private 'resumes' bucket exists.

The secret key cannot run DDL. If tables are missing, paste supabase/schema.sql into
Supabase Dashboard -> SQL Editor -> New query -> Run, then run this script again.
Reads SUPABASE_URL and SUPABASE_SECRET_KEY from .env (never printed).
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "api"))


def load_env():
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    load_env()
    import db
    missing = []
    for t in ("candidates", "scores", "results"):
        r = db._req("GET", f"/rest/v1/{t}?select=*&limit=1")
        if r.status_code >= 400:
            missing.append(t)
    print("tables missing:", missing or "none")
    print("bucket ready:", db.ensure_bucket())
    if missing:
        print("\nPaste supabase/schema.sql into the Supabase SQL editor and run it, then re-run this script.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
