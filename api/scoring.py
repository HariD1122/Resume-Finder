"""Deterministic scoring. Arithmetic never comes from the model."""
from constants import (HOLD_MIN, MIN_EVIDENCED_REQUIREMENTS, MUMBAI_REGION, SHORTLIST_MIN)
from requirements import ROLES

GATE_LABELS = {5: "OK", 3: "Confirm", 0: "Not relocating"}


def experience_score(role: str, years):
    """PM: 2-4 =5; [1.5,2) or (4,6] =3; else 1. SPM: 5-8 =5; [4,5) or (8,10] =3; else 1."""
    if years is None:
        return 1
    y = float(years)
    if role == "PM":
        if 2 <= y <= 4:
            return 5
        if 1.5 <= y < 2 or 4 < y <= 6:
            return 3
        return 1
    if 5 <= y <= 8:
        return 5
    if 4 <= y < 5 or 8 < y <= 10:
        return 3
    return 1


def in_mumbai_region(location) -> bool:
    if not location:
        return False
    loc = str(location).lower()
    return any(name in loc for name in MUMBAI_REGION)


def location_score(location, relocation) -> int:
    # Mumbai-based people need no relocation, so Mumbai wins even if relocation is "unwilling"
    if in_mumbai_region(location):
        return 5
    if relocation == "unwilling":
        return 0
    if relocation == "willing":
        return 5
    return 3


def location_gate(score: int) -> str:
    return GATE_LABELS.get(score, "Confirm")


def weighted_score(role: str, scores: dict) -> float:
    total = 0.0
    for req in ROLES[role]["requirements"]:
        total += req.weight * int(scores.get(req.id, 0)) / 5
    return round(total, 1)


def core_sum(role: str, scores: dict) -> int:
    return sum(int(scores.get(r.id, 0)) for r in ROLES[role]["requirements"] if r.core)


def evidenced_count(role: str, scores: dict) -> int:
    return sum(1 for r in ROLES[role]["requirements"] if r.kind == "model" and int(scores.get(r.id, 0)) > 0)


def recommend(role: str, scores: dict, weighted: float, loc_score: int):
    """Returns (recommendation, note). note is None unless the thin-resume rule fires."""
    if loc_score == 0:
        return "Pass (location)", None
    if evidenced_count(role, scores) < MIN_EVIDENCED_REQUIREMENTS:
        return "Hold", "Insufficient information"
    if weighted >= SHORTLIST_MIN:
        return "Shortlist", None
    if weighted >= HOLD_MIN:
        return "Hold", None
    return "Pass", None


def compute_result(role: str, model_scores: dict, pm_years, location, relocation) -> dict:
    """Adds computed requirements to model scores and derives the totals."""
    spec = ROLES[role]
    scores = dict(model_scores)
    scores[spec["experience_id"]] = experience_score(role, pm_years)
    loc = location_score(location, relocation)
    scores[spec["location_id"]] = loc
    weighted = weighted_score(role, scores)
    rec, note = recommend(role, scores, weighted, loc)
    return {"scores": scores, "weighted_score": weighted, "recommendation": rec,
            "location_gate": location_gate(loc), "note": note, "location_score": loc}


def rank_rows(role: str, rows: list) -> list:
    """rows: dicts with 'weighted_score', 'score_map', 'created_at'. Adds 'rank'; returns sorted."""
    def key(r):
        return (-float(r["weighted_score"]), -core_sum(role, r["score_map"]), r["created_at"] or "")
    ordered = sorted(rows, key=key)
    for i, r in enumerate(ordered, 1):
        r["rank"] = i
    return ordered
