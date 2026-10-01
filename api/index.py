"""Resume Finder API (FastAPI on Vercel). Entry point: `app`."""
import hashlib
import os
import sys
import time
import uuid
from collections import defaultdict, deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, File, Form, Request, UploadFile  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

import db  # noqa: E402
import extract  # noqa: E402
import gemini  # noqa: E402
import scoring  # noqa: E402
from constants import MAX_FILE_BYTES, RUBRIC_VERSION, UPLOAD_RATE_LIMIT_PER_MIN  # noqa: E402
from errors import ApiError, DuplicateError  # noqa: E402
from requirements import ROLES  # noqa: E402

app = FastAPI(title="Resume Finder", docs_url=None, redoc_url=None, openapi_url=None)

origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
if os.environ.get("ALLOWED_ORIGIN"):
    origins.append(os.environ["ALLOWED_ORIGIN"].rstrip("/"))
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type", "X-Access-Code"], expose_headers=["X-Request-Id", "Retry-After"])


def err(status: int, code: str, message: str, headers: dict | None = None, extra: dict | None = None):
    body = {"error": {"code": code, "message": message}}
    body.update(extra or {})
    return JSONResponse(body, status_code=status, headers=headers or {})


@app.exception_handler(ApiError)
async def _api_error(_: Request, e: ApiError):
    return err(e.status, e.code, e.message, e.headers, e.extra)


@app.exception_handler(StarletteHTTPException)
async def _http_error(_: Request, e: StarletteHTTPException):
    return err(e.status_code, "http_error", str(e.detail))


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, e: RequestValidationError):
    return err(422, "invalid_request", "The request was not valid.")


@app.exception_handler(Exception)
async def _unhandled(_: Request, e: Exception):  # no PII: log only the exception type
    print(f"unhandled {type(e).__name__}")
    return err(500, "server_error", "Something went wrong on the server.")


def _access_ok(request: Request) -> bool:
    code = os.environ.get("APP_ACCESS_CODE")
    return not code or request.headers.get("x-access-code") == code


@app.middleware("http")
async def guard(request: Request, call_next):
    rid = uuid.uuid4().hex[:12]
    path = request.url.path
    if request.method != "OPTIONS" and path != "/api/health" and not _access_ok(request):
        resp = err(401, "unauthorized", "A valid access code is required.")
    else:
        resp = await call_next(request)
    resp.headers["X-Request-Id"] = rid
    return resp


# ---------- helpers ----------
_hits = defaultdict(deque)


def rate_limit(request: Request):
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= UPLOAD_RATE_LIMIT_PER_MIN:
        raise ApiError(429, "rate_limited", "Too many uploads. Please wait a moment.", {"Retry-After": "30"})
    q.append(now)


def role_or_400(role: str | None) -> str:
    if role not in ROLES:
        raise ApiError(422, "invalid_role", "Role must be PM or SPM.")
    return role


def _result_of(row: dict) -> dict:
    res = row.get("results")
    if isinstance(res, list):
        res = res[0] if res else None
    return res or {}


def candidate_view(row: dict) -> dict:
    res = _result_of(row)
    smap = {s["requirement_id"]: s for s in row.get("scores", [])}
    return {
        "id": row["id"], "role": row["role"], "full_name": row.get("full_name"),
        "current_title": row.get("current_title"), "current_company": row.get("current_company"),
        "pm_years": row.get("pm_years"), "location": row.get("location"), "email": row.get("email"),
        "phone": row.get("phone"), "address": row.get("address"), "summary": row.get("summary"),
        "extraction_notes": row.get("extraction_notes"), "file_name": row.get("file_name"),
        "created_at": row.get("created_at"), "updated_at": row.get("updated_at"),
        "scores": {k: {"score": v["score"], "evidence": v.get("evidence"), "reason": v.get("reason")} for k, v in smap.items()},
        "weighted_score": float(res.get("weighted_score", 0) or 0),
        "recommendation": res.get("recommendation", "Hold"),
        "location_gate": res.get("location_gate"),
        "probe_questions": res.get("probe_questions") or [],
    }


# ---------- routes ----------

@app.get("/api/health")
def health(request: Request):
    authed = _access_ok(request)
    required = bool(os.environ.get("APP_ACCESS_CODE"))
    if not authed:
        return {"status": "ok", "access_required": True}
    sb, counts = True, {}
    try:
        counts = db.health_counts()
    except Exception:
        sb = False
    gm = gemini.gemini_ok()
    return {"status": "ok" if sb and gm else "degraded", "supabase": sb, "gemini": gm,
            "access_required": required,
            "counts": {k: counts.get(k, 0) for k in ("candidates", "PM", "SPM")},
            "latest_updated_at": counts.get("latest_updated_at"),
            "latest_by_role": counts.get("latest_by_role", {}),
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


@app.get("/api/auth-check")
def auth_check():
    return {"ok": True}


@app.get("/api/config")
def config():
    return {"rubric_version": RUBRIC_VERSION, "max_file_bytes": MAX_FILE_BYTES, "roles": {
        code: {"code": code, "name": s["name"], "short": s["short"], "requirements": [
            {"id": r.id, "label": r.label, "short": r.short, "weight": r.weight, "kind": r.kind,
             "focus": r.anchors[3] or ("Computed from stated experience" if r.id == s["experience_id"]
                                       else "Computed from location and relocation")}
            for r in s["requirements"]]} for code, s in ROLES.items()}}


@app.post("/api/upload")
async def upload(request: Request, file: UploadFile = File(...), role: str = Form(...)):
    rate_limit(request)
    role = role_or_400(role)
    data = await file.read(MAX_FILE_BYTES + 1)
    filename = file.filename or "resume"
    kind = extract.detect_kind(filename, data)
    file_hash = hashlib.sha256(data).hexdigest()

    existing = db.find_by_hash(role, file_hash)
    if existing:
        return JSONResponse({"status": "duplicate", "existing_candidate_id": existing,
                             "message": "Already added for this role."}, status_code=409)

    text, method = extract.extract_text(kind, data)
    raw = gemini.call_gemini(role, text if method == "text" else None, data if method == "gemini_vision" else None)
    out = gemini.validate_output(raw, role, text, method)
    if not out["is_resume"]:
        raise ApiError(422, "not_a_resume", "This file does not look like a resume.")

    if out["email"]:
        existing = db.find_by_email(role, out["email"])
        if existing:
            return JSONResponse({"status": "duplicate", "existing_candidate_id": existing,
                                 "message": "Already added for this role (same email)."}, status_code=409)

    model_scores = {s["requirement_id"]: s["score"] for s in out["requirements"]}
    comp = scoring.compute_result(role, model_scores, out["pm_years"], out["location"], out["relocation"])

    cid = str(uuid.uuid4())
    safe = extract.sanitize_filename(filename)
    path = f"{role}/{cid}/{safe}"
    ctype = {"pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "doc": "application/msword"}[kind]
    notes = out["extraction_notes"]
    if comp["note"]:
        notes = f"{notes}; {comp['note']}" if notes else comp["note"]

    db.upload_file(path, data, ctype)
    try:
        db.insert_candidate({
            "id": cid, "role": role, "full_name": out["full_name"], "email": out["email"], "phone": out["phone"],
            "address": out["address"], "current_company": out["current_company"], "current_title": out["current_title"],
            "pm_years": out["pm_years"], "total_experience_years": out["total_experience_years"],
            "location": out["location"], "relocation": out["relocation"], "summary": out["summary"],
            "applied_role_hint": out["applied_role_hint"], "extraction_notes": notes, "extraction_method": method,
            "file_name": safe, "file_path": path, "file_hash": file_hash, "file_size": len(data),
            "gemini_model": gemini.get_model()})
        by_id = {s["requirement_id"]: s for s in out["requirements"]}
        score_rows = []
        for req in ROLES[role]["requirements"]:
            if req.kind == "model":
                s = by_id[req.id]
                score_rows.append({"candidate_id": cid, "requirement_id": req.id, "score": s["score"],
                                   "evidence": s["evidence"], "reason": s["reason"]})
            else:
                score_rows.append({"candidate_id": cid, "requirement_id": req.id, "score": comp["scores"][req.id],
                                   "evidence": "Computed", "reason": "Computed from extracted experience/location."})
        db.insert_scores(score_rows)
        db.upsert_result({"candidate_id": cid, "weighted_score": comp["weighted_score"],
                          "recommendation": comp["recommendation"], "location_gate": comp["location_gate"],
                          "probe_questions": out["probe_questions"], "rubric_version": RUBRIC_VERSION})
    except DuplicateError:
        db.delete_candidate(cid)
        db.remove_files([path])
        return JSONResponse({"status": "duplicate", "existing_candidate_id": None,
                             "message": "Already added for this role."}, status_code=409)
    except Exception:  # leave nothing half-saved
        db.delete_candidate(cid)
        db.remove_files([path])
        raise

    return {"status": "saved",
            "candidate": {"id": cid, "role": role, "full_name": out["full_name"], "email": out["email"],
                          "phone": out["phone"], "address": out["address"], "current_company": out["current_company"],
                          "current_title": out["current_title"], "pm_years": out["pm_years"],
                          "summary": out["summary"], "extraction_notes": notes},
            "scores": score_rows,
            "result": {"weighted_score": comp["weighted_score"], "recommendation": comp["recommendation"],
                       "location_gate": comp["location_gate"], "rubric_version": RUBRIC_VERSION},
            "probe_questions": out["probe_questions"], "applied_role_hint": out["applied_role_hint"]}


@app.get("/api/candidates")
def candidates(role: str):
    role = role_or_400(role)
    rows = []
    for r in db.list_candidates(role):
        v = candidate_view(r)
        v["score_map"] = {k: s["score"] for k, s in v["scores"].items()}
        rows.append(v)
    ordered = scoring.rank_rows(role, rows)
    for v in ordered:
        v.pop("score_map", None)
    latest = max((v["updated_at"] for v in ordered if v["updated_at"]), default=None)
    return {"role": role, "count": len(ordered), "latest_updated_at": latest, "candidates": ordered}


@app.get("/api/contacts")
def contacts(role: str | None = None):
    if role:
        role_or_400(role)
    rows = db.list_candidates(role or None)
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return {"count": len(rows), "contacts": [
        {"id": r["id"], "full_name": r.get("full_name"), "role": r["role"], "phone": r.get("phone"),
         "email": r.get("email"), "address": r.get("address") or r.get("location"),
         "created_at": r.get("created_at"), "has_resume": bool(r.get("file_path"))} for r in rows]}


@app.get("/api/resume-url")
def resume_url(candidate_id: str):
    row = db.get_candidate(candidate_id)
    if not row or not row.get("file_path"):
        raise ApiError(404, "not_found", "Resume not found.")
    return {"url": db.signed_url(row["file_path"]), "expires_in": 600}


@app.post("/api/reset")
def reset():
    deleted = db.reset_all()
    left = db.health_counts()["candidates"] + db.count_bucket()
    if left:
        raise ApiError(500, "reset_incomplete", "Some data could not be deleted. Please try again.")
    return {"deleted": deleted}


@app.post("/api/recompute")
def recompute():
    """Re-score every stored candidate from stored per-requirement scores. No Gemini calls."""
    n = 0
    for r in db.list_candidates(None):
        role = r["role"]
        smap = {s["requirement_id"]: s["score"] for s in r.get("scores", [])}
        model_scores = {k: v for k, v in smap.items() if k not in (ROLES[role]["experience_id"], ROLES[role]["location_id"])}
        comp = scoring.compute_result(role, model_scores, r.get("pm_years"), r.get("location"), r.get("relocation"))
        rows = [{"candidate_id": r["id"], "requirement_id": k, "score": comp["scores"][k],
                 "evidence": "Computed", "reason": "Computed from extracted experience/location."}
                for k in (ROLES[role]["experience_id"], ROLES[role]["location_id"])]
        db._check(db._req("POST", "/rest/v1/scores?on_conflict=candidate_id,requirement_id", json=rows,
                          headers={"Prefer": "resolution=merge-duplicates,return=minimal"}), "recomputing")
        old = _result_of(r)
        db.upsert_result({"candidate_id": r["id"], "weighted_score": comp["weighted_score"],
                          "recommendation": comp["recommendation"], "location_gate": comp["location_gate"],
                          "probe_questions": old.get("probe_questions") or [], "rubric_version": RUBRIC_VERSION})
        n += 1
    return {"recomputed": n, "rubric_version": RUBRIC_VERSION}
