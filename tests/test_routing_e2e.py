"""Approach V2 Step 3 (ADR-040) end to end: every patient-level routing case through the HTTP API and the reports.

One real analysis (a dev-train image) is made through POST /api/cases; the other cases are stored variants of it
(stage, score, quality, landmarks, macular finding), so the routing rules are exercised without more inference.
Run on CPU while the GPU queue trains: set RS_DEVICE=cpu, then .venv\\Scripts\\python -m pytest tests/test_routing_e2e.py -q
(not CUDA_VISIBLE_DEVICES=-1, which crashes with this NVIDIA driver; ADR-044)
"""
import copy
import csv
import json
import math
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from inference import routing  # noqa: E402

FORBIDDEN = ("normal", "healthy", "cleared")


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    from backend import store
    from backend.app import app, state
    old = store.DIR, store.IMAGES
    tmp = tmp_path_factory.mktemp("store")
    store.DIR, store.IMAGES = tmp, tmp / "images"
    with open(ROOT / "data/interim/manifests/idrid_grading_train_clean.csv", newline="") as f:
        image = (ROOT / next(csv.DictReader(f))["filepath"]).read_bytes()
    with TestClient(app) as c:
        r = c.post("/api/cases", files={"file": ("f.jpg", image, "image/jpeg")},
                   data={"patient_ref": "INTAKE-1", "eye": "left", "prior_treatment": "true"})
        assert r.status_code == 200
        template = r.json()
        assert template["analysis"]["status"] == "ok" and state["calibration"] is not None
        yield dict(client=c, state=state, store=store, image=image, template=template)
    store.DIR, store.IMAGES = old


def variant(t, *, grade=0, score=None, usable=True, dme="low", side="left"):
    """A stored analysis with the given stage, score, quality and macular finding; landmarks placed for `side`."""
    a = copy.deepcopy(t["analysis"])
    cfg = routing.load_config()
    if score is None:  # far from the routine threshold and from the stage boundaries: confident routine candidate
        score = {0: 0.0, 1: 0.0, 2: 2.0, 3: 3.0, 4: 4.0}[grade]
    a["grading"].update(grade=grade, score=score)
    a["quality"]["usable"] = usable
    if not usable:
        a["quality"]["issues"] = ["The photo is too blurred."]
    f = a["findings"]
    f["macular_edema_risk"]["level"] = dme
    lm = f["landmarks"]
    lm["fovea"].update(x=500.0, uncertain=False)
    lm["optic_disc"]["x"] = 800.0 if side == "right" else 200.0
    return a


def add(env, ref, eye, analysis, intake=None):
    return env["store"].add_case(env["state"]["db"], ref, eye, "upload", env["image"], "jpg", analysis, env["state"]["signature"], intake=intake)


def patient(env, cid):
    return env["client"].get(f"/api/cases/{cid}").json()


def reports(env, ref):
    out = {}
    for kind, lang in (("doctor", "en"), ("patient", "en"), ("patient", "hi")):
        h = env["client"].get(f"/api/patients/{ref}/report.html?kind={kind}&lang={lang}")
        assert h.status_code == 200
        out[(kind, lang)] = h.text
    return out


@pytest.fixture
def valid(env, monkeypatch):
    """Routine routing on: the rules are tested independently of which grader this checkout runs."""
    monkeypatch.setitem(env["state"], "routing_valid", True)


def test_intake_checkbox_from_the_form_routes_to_clinician_review(env):
    c = env["template"]
    # The form answer is stored with the case; its effect on a stage 0-1 eye is tested below (stored variants).
    assert c["routing"]["intake"] == {"vision_problems": False, "prior_treatment": True} and c["routing"]["state"] != routing.ROUTINE


def test_both_eyes_routine(env, valid):
    add(env, "P-ROUTINE", "right", variant(env["template"], side="right"))
    cid = add(env, "P-ROUTINE", "left", variant(env["template"], side="left"))
    p = patient(env, cid)["patient"]
    assert [e["state"] for e in p["eyes"]] == [routing.ROUTINE, routing.ROUTINE]
    assert p["state"] == routing.ROUTINE and p["follow_up"]["level"] == "routine"
    assert p["notes"][0] == routing.CLINICIAN_ROUTINE_TEXT
    assert "not yet validated on external data" in p["operating_point"]["wording"]
    from backend.report_text import PATIENT
    html = reports(env, "P-ROUTINE")
    assert PATIENT["en"]["follow_up"]["routine"] in html[("patient", "en")]
    assert PATIENT["hi"]["follow_up"]["routine"] in html[("patient", "hi")]
    assert routing.CLINICIAN_ROUTINE_TEXT in html[("doctor", "en")] or "Routine rescreening eligible" in html[("doctor", "en")]
    for text in html.values():
        assert not any(w in text.lower().split() for w in FORBIDDEN)


def test_missing_eye_is_incomplete_screening(env, valid):
    cid = add(env, "P-ONE-EYE", "left", variant(env["template"]))
    p = patient(env, cid)["patient"]
    assert p["state"] == routing.INCOMPLETE and p["follow_up"]["level"] == "incomplete"
    assert any("No right-eye photograph" in n for n in p["notes"])
    reports(env, "P-ONE-EYE")


def test_ungradable_retake_then_clinician_after_failed_retake(env, valid):
    first = add(env, "P-RETAKE", "left", variant(env["template"], usable=False))
    add(env, "P-RETAKE", "right", variant(env["template"], side="right"))
    p = patient(env, first)["patient"]
    assert patient(env, first)["routing"]["state"] == routing.RETAKE and p["state"] == routing.RETAKE and p["follow_up"]["level"] == "retake"
    html = reports(env, "P-RETAKE")
    assert "Retake" in html[("doctor", "en")]
    second = add(env, "P-RETAKE", "left", variant(env["template"], usable=False))
    c = patient(env, second)
    assert c["routing"]["state"] == routing.REVIEW and "after a retake" in c["routing"]["reasons"][0]
    assert c["patient"]["state"] == routing.REVIEW


def test_contradictory_eyes_worse_eye_decides_with_asymmetry_note(env, valid):
    add(env, "P-ASYM", "right", variant(env["template"], side="right"))
    cid = add(env, "P-ASYM", "left", variant(env["template"], grade=3))
    p = patient(env, cid)["patient"]
    assert p["state"] == routing.URGENT and p["follow_up"]["level"] == "urgent"
    assert any("differ by two or more stages" in n for n in p["notes"])
    reports(env, "P-ASYM")


def test_central_vision_concern_is_urgent(env, valid):
    add(env, "P-DME", "right", variant(env["template"], side="right"))
    cid = add(env, "P-DME", "left", variant(env["template"], grade=1, dme="high"))
    c = patient(env, cid)
    assert c["routing"]["state"] == routing.URGENT and c["patient"]["state"] == routing.URGENT


def test_stage_2_is_referable(env, valid):
    add(env, "P-REF", "right", variant(env["template"], side="right"))
    cid = add(env, "P-REF", "left", variant(env["template"], grade=2))
    p = patient(env, cid)["patient"]
    assert p["state"] == routing.REFERABLE and p["follow_up"]["level"] == "refer"


def test_laterality_mismatch_goes_to_clinician_review(env, valid):
    add(env, "P-LAT", "right", variant(env["template"], side="left"))  # disc position says left; recorded as right
    cid = add(env, "P-LAT", "left", variant(env["template"]))
    c = patient(env, cid)
    right = next(e for e in c["patient"]["eyes"] if e["eye"] == "right")
    assert right["state"] == routing.REVIEW and any("check the eye label" in r for r in right["reasons"])
    assert c["patient"]["state"] == routing.REVIEW


def test_repeat_visit_never_downgrades_a_signed_referral(env, valid):
    add(env, "P-REPEAT", "right", variant(env["template"], side="right"))
    old = add(env, "P-REPEAT", "left", variant(env["template"]))
    r = env["client"].post(f"/api/cases/{old}/review", json={"reviewer": "Dr T", "decision": "disagree", "corrected_stage": 2, "note": "IRMA"})
    assert r.status_code == 200
    new = add(env, "P-REPEAT", "left", variant(env["template"]))
    c = patient(env, new)
    assert c["routing"]["state"] == routing.REVIEW and any("previous visit" in x for x in c["routing"]["reasons"])
    assert c["routing"]["previous"]["case_id"] == old and c["routing"]["previous"]["corrected_stage"] == 2
    assert c["patient"]["state"] == routing.REVIEW


def test_intake_vision_problems_routes_to_clinician_review(env, valid):
    add(env, "P-INTAKE", "right", variant(env["template"], side="right"))
    cid = add(env, "P-INTAKE", "left", variant(env["template"]), intake=dict(vision_problems=True))
    c = patient(env, cid)
    assert c["routing"]["state"] == routing.REVIEW and "The patient reports vision problems." in c["routing"]["reasons"]
    cid = add(env, "P-INTAKE-2", "left", variant(env["template"]), intake=dict(prior_treatment=True))
    assert any("eye treatment or laser" in r for r in patient(env, cid)["routing"]["reasons"])


def test_routing_invalid_for_another_grader_means_no_routine(env, monkeypatch):
    monkeypatch.setitem(env["state"], "routing_valid", False)
    add(env, "P-INVALID", "right", variant(env["template"], side="right"))
    cid = add(env, "P-INVALID", "left", variant(env["template"]))
    c = patient(env, cid)
    assert c["routing"]["state"] == routing.REVIEW and any("not validated" in r for r in c["routing"]["reasons"])
    assert c["patient"]["state"] == routing.REVIEW and c["patient"]["operating_point"]["valid"] is False


def test_worklist_order_follows_adr040(env, valid):
    rows = [c for c in env["client"].get("/api/cases").json()["cases"] if c["status"] == "new"]
    order = [routing.ORDER[c["routing"]["state"]] for c in rows]
    assert order == sorted(order) and order[0] == 0 and order[-1] == routing.ORDER[routing.ROUTINE]


def test_settings_endpoint_and_operating_point(env, valid):
    c = env["client"]
    s = c.get("/api/settings").json()
    assert s["target"] == 0.025 and sorted(s["choices"]) == [0.025, 0.05]
    assert s["wording"].startswith("target referable miss rate 2.5%; verified upper bound 2.7% on APTOS-val (development data)")
    assert c.post("/api/settings", json={"target": 0.1}).status_code == 422
    cfg = routing.load_config()
    # A score whose P(referable) lies between the two thresholds: review at 2.5%, routine at 5%.
    p = (cfg["thresholds"]["0.025"] + cfg["thresholds"]["0.05"]) / 2
    score = (math.log(p / (1 - p)) - cfg["platt"]["intercept"]) / cfg["platt"]["coef"]
    a = variant(env["template"], grade=1, score=score)
    at = {t: routing.eye_state(a, eye="left", target=t, valid=True, stage_confidence=0.9)["state"] for t in (0.025, 0.05)}
    assert at == {0.025: routing.REVIEW, 0.05: routing.ROUTINE}
    s = c.post("/api/settings", json={"target": 0.05}).json()
    assert s["target"] == 0.05 and "verified upper bound 4.3%" in s["wording"]
    assert c.post("/api/settings", json={"target": 0.025}).json()["target"] == 0.025
