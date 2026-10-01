"""Supabase access over httpx (PostgREST + Storage).

New-style keys (sb_secret_...) are not JWTs, so they go in the `apikey` header only.
"""
import os
from urllib.parse import quote

import httpx

from constants import BUCKET, SIGNED_URL_TTL_S
from errors import ApiError, DuplicateError

TIMEOUT = httpx.Timeout(20.0, connect=10.0)


def _base() -> str:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not url:
        raise ApiError(500, "not_configured", "Database is not configured.")
    return url


def _headers(extra: dict | None = None) -> dict:
    key = os.environ.get("SUPABASE_SECRET_KEY", "")
    h = {"apikey": key}
    if key.startswith("eyJ"):  # legacy JWT-style keys also work as Bearer
        h["Authorization"] = f"Bearer {key}"
    if extra:
        h.update(extra)
    return h


def _req(method: str, path: str, **kw) -> httpx.Response:
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            return c.request(method, _base() + path, headers=_headers(kw.pop("headers", None)), **kw)
    except httpx.HTTPError:
        raise ApiError(502, "database_unreachable", "The database could not be reached. Please retry.")


def _check(r: httpx.Response, what: str):
    if r.status_code == 409 or (r.status_code == 400 and "23505" in r.text):
        raise DuplicateError()
    if r.status_code >= 400:
        raise ApiError(500, "database_error", f"Database error while {what}.")
    return r


# ---------- candidates ----------

def find_by_hash(role: str, file_hash: str):
    r = _check(_req("GET", f"/rest/v1/candidates?select=id&role=eq.{role}&file_hash=eq.{file_hash}&limit=1"), "checking duplicates")
    rows = r.json()
    return rows[0]["id"] if rows else None


def find_by_email(role: str, email: str):
    r = _check(_req("GET", "/rest/v1/candidates?select=id&limit=1&role=eq." + role +
                    "&email=ilike." + quote(email.replace("*", ""), safe="")), "checking duplicates")
    rows = r.json()
    return rows[0]["id"] if rows else None


def insert_candidate(row: dict) -> dict:
    r = _check(_req("POST", "/rest/v1/candidates", json=row, headers={"Prefer": "return=representation"}), "saving candidate")
    return r.json()[0]


def insert_scores(rows: list):
    _check(_req("POST", "/rest/v1/scores", json=rows, headers={"Prefer": "return=minimal"}), "saving scores")


def upsert_result(row: dict):
    _check(_req("POST", "/rest/v1/results", json=row,
                headers={"Prefer": "resolution=merge-duplicates,return=minimal"}), "saving result")


def delete_candidate(candidate_id: str):
    try:
        _req("DELETE", f"/rest/v1/candidates?id=eq.{candidate_id}")
    except ApiError:
        pass


def list_candidates(role: str | None = None) -> list:
    q = "/rest/v1/candidates?select=*,scores(requirement_id,score,evidence,reason),results(*)&order=created_at.asc&limit=5000"
    if role:
        q += f"&role=eq.{role}"
    return _check(_req("GET", q), "loading candidates").json()


def get_candidate(candidate_id: str):
    r = _check(_req("GET", f"/rest/v1/candidates?select=*&id=eq.{quote(candidate_id, safe='')}&limit=1"), "loading candidate")
    rows = r.json()
    return rows[0] if rows else None


# ---------- storage ----------

def upload_file(path: str, data: bytes, content_type: str):
    r = _req("POST", f"/storage/v1/object/{BUCKET}/{quote(path, safe='/')}", content=data,
             headers={"Content-Type": content_type, "x-upsert": "false"})
    if r.status_code >= 400:
        raise ApiError(500, "storage_error", "The resume file could not be stored.")


def remove_files(paths: list):
    if paths:
        _req("DELETE", f"/storage/v1/object/{BUCKET}", json={"prefixes": paths})


def signed_url(path: str) -> str:
    r = _req("POST", f"/storage/v1/object/sign/{BUCKET}/{quote(path, safe='/')}", json={"expiresIn": SIGNED_URL_TTL_S})
    if r.status_code >= 400:
        raise ApiError(404, "file_not_found", "The resume file was not found.")
    rel = r.json().get("signedURL", "")
    return _base() + "/storage/v1" + (rel if rel.startswith("/") else "/" + rel)


def _list_prefix(prefix: str) -> list:
    """All object paths under prefix, traversing folders and paging by 100."""
    found, offset = [], 0
    while True:
        r = _req("POST", f"/storage/v1/object/list/{BUCKET}",
                 json={"prefix": prefix, "limit": 100, "offset": offset, "sortBy": {"column": "name", "order": "asc"}})
        if r.status_code >= 400:
            raise ApiError(500, "storage_error", "Could not list stored resumes.")
        items = r.json()
        for it in items:
            full = f"{prefix}/{it['name']}" if prefix else it["name"]
            if it.get("id") is None:  # folder
                found.extend(_list_prefix(full))
            else:
                found.append(full)
        if len(items) < 100:
            return found
        offset += 100


def purge_bucket() -> int:
    removed = 0
    for _ in range(50):
        paths = _list_prefix("")
        if not paths:
            break
        for i in range(0, len(paths), 100):
            remove_files(paths[i:i + 100])
        removed += len(paths)
    return removed


def count_bucket() -> int:
    return len(_list_prefix(""))


def ensure_bucket():
    r = _req("POST", "/storage/v1/bucket", json={"id": BUCKET, "name": BUCKET, "public": False})
    return r.status_code in (200, 201) or "already exists" in r.text.lower() or r.status_code == 409


# ---------- reset / health ----------

def _delete_all(table: str, col: str) -> int:
    r = _check(_req("DELETE", f"/rest/v1/{table}?{col}=not.is.null",
                    headers={"Prefer": "count=exact,return=minimal"}), f"clearing {table}")
    cr = r.headers.get("content-range", "*/0")
    try:
        return int(cr.split("/")[-1])
    except ValueError:
        return 0


def reset_all() -> dict:
    results = _delete_all("results", "candidate_id")
    scores = _delete_all("scores", "id")
    candidates = _delete_all("candidates", "id")
    files = purge_bucket()
    return {"candidates": candidates, "scores": scores, "results": results, "files": files}


def health_counts() -> dict:
    """Counts and latest updated_at per role. Raises ApiError if the database is unreachable."""
    out = {"candidates": 0, "PM": 0, "SPM": 0, "latest_updated_at": None, "latest_by_role": {"PM": None, "SPM": None}}
    for role in ("PM", "SPM"):
        r = _check(_req("GET", f"/rest/v1/candidates?select=updated_at&role=eq.{role}&order=updated_at.desc&limit=1",
                        headers={"Prefer": "count=exact"}), "checking health")
        try:
            out[role] = int(r.headers.get("content-range", "*/0").split("/")[-1])
        except ValueError:
            out[role] = 0
        rows = r.json()
        out["latest_by_role"][role] = rows[0]["updated_at"] if rows else None
    out["candidates"] = out["PM"] + out["SPM"]
    stamps = [v for v in out["latest_by_role"].values() if v]
    out["latest_updated_at"] = max(stamps) if stamps else None
    return out


# ---------- emails ----------

def email_list() -> list:
    return _check(_req("GET", "/rest/v1/emails?select=*&limit=5000"), "loading emails").json()


def email_insert(row: dict):
    """Insert a draft; an existing row for the candidate is left untouched."""
    _check(_req("POST", "/rest/v1/emails?on_conflict=candidate_id", json=row,
                headers={"Prefer": "resolution=ignore-duplicates,return=minimal"}), "saving email draft")


def email_update(candidate_id: str, patch: dict, only_statuses: tuple | None = None):
    """Conditional update; returns the updated row or None if the status condition did not match."""
    q = f"/rest/v1/emails?candidate_id=eq.{quote(candidate_id, safe='')}"
    if only_statuses:
        q += "&status=in.(" + ",".join(only_statuses) + ")"
    rows = _check(_req("PATCH", q, json=patch, headers={"Prefer": "return=representation"}), "updating email").json()
    return rows[0] if rows else None
