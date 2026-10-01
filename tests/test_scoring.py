import pytest

import scoring
from requirements import ROLES


@pytest.mark.parametrize("role", ["PM", "SPM"])
def test_weights_total_100(role):
    assert sum(r.weight for r in ROLES[role]["requirements"]) == 100


@pytest.mark.parametrize("years,exp", [(1.4, 1), (1.5, 3), (1.99, 3), (2, 5), (4, 5), (4.01, 3), (6, 3), (6.01, 1), (None, 1)])
def test_pm_experience(years, exp):
    assert scoring.experience_score("PM", years) == exp


@pytest.mark.parametrize("years,exp", [(3.9, 1), (4, 3), (4.99, 3), (5, 5), (8, 5), (8.01, 3), (10, 3), (10.01, 1), (None, 1)])
def test_spm_experience(years, exp):
    assert scoring.experience_score("SPM", years) == exp


@pytest.mark.parametrize("loc,rel,exp", [
    ("Mumbai, India", "unknown", 5), ("Thane", "unknown", 5), ("Navi Mumbai", "unwilling", 5),
    ("Bengaluru", "willing", 5), ("Bengaluru", "unknown", 3), ("Pune", "unwilling", 0),
    (None, "unknown", 3), (None, "willing", 5)])
def test_location(loc, rel, exp):
    assert scoring.location_score(loc, rel) == exp


def test_gate_labels():
    assert [scoring.location_gate(s) for s in (5, 3, 0)] == ["OK", "Confirm", "Not relocating"]


def _all(role, value, **over):
    s = {r.id: value for r in ROLES[role]["requirements"]}
    s.update(over)
    return s


def test_weighted_hand_calculated_pm():
    # all 5s -> 100; all 0s except PM1=5 (18) and PM6=5 (14) -> 32.0
    assert scoring.weighted_score("PM", _all("PM", 5)) == 100.0
    s = _all("PM", 0, PM1=5, PM6=5)
    assert scoring.weighted_score("PM", s) == 32.0
    # PM1=4 (14.4) + PM2=3 (9.6) + PM9=5 (3) + PM10=3 (1.2) = 28.2
    s = _all("PM", 0, PM1=4, PM2=3, PM9=5, PM10=3)
    assert scoring.weighted_score("PM", s) == 28.2


def test_weighted_hand_calculated_spm():
    s = _all("SPM", 0, SP1=5, SP2=4, SP11=5, SP12=5)  # 15 + 12.8 + 2 + 2 = 31.8
    assert scoring.weighted_score("SPM", s) == 31.8


@pytest.mark.parametrize("w,exp", [(54.9, "Pass"), (55, "Hold"), (69.9, "Hold"), (70, "Shortlist")])
def test_thresholds(w, exp):
    s = _all("PM", 3)
    assert scoring.recommend("PM", s, w, 5)[0] == exp


def test_location_override_and_thin_resume():
    s = _all("PM", 5)
    assert scoring.recommend("PM", s, 100, 0)[0] == "Pass (location)"
    thin = _all("PM", 0, PM1=4)
    assert scoring.recommend("PM", thin, 80, 5) == ("Hold", "Insufficient information")


def test_compute_result_end_to_end():
    ms = {r.id: 4 for r in ROLES["PM"]["requirements"] if r.kind == "model"}
    out = scoring.compute_result("PM", ms, 3, "Mumbai", "unknown")
    assert out["scores"]["PM9"] == 5 and out["scores"]["PM10"] == 5
    assert out["weighted_score"] == round(95 * 4 / 5 + 3 + 2, 1)
    assert out["location_gate"] == "OK"


def test_tie_break_order():
    a = {"weighted_score": 60, "score_map": _all("PM", 0, PM1=5), "created_at": "2025-02"}
    b = {"weighted_score": 60, "score_map": _all("PM", 0, PM1=5, PM2=5), "created_at": "2025-03"}
    c = {"weighted_score": 60, "score_map": _all("PM", 0, PM1=5), "created_at": "2025-01"}
    d = {"weighted_score": 70, "score_map": _all("PM", 0), "created_at": "2025-04"}
    ordered = scoring.rank_rows("PM", [a, b, c, d])
    assert ordered == [d, b, c, a]
    assert [r["rank"] for r in ordered] == [1, 2, 3, 4]
