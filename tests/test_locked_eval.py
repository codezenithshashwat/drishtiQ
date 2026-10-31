"""tools/locked_eval.py logic on synthetic records (no models, no locked data): the locked evaluation runs once, so its
aggregation and metrics are checked before it does."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
import locked_eval as le  # noqa: E402
from inference import routing  # noqa: E402


def rec(state, stage, score, usable=True, conf=0.9):
    return dict(path="x", status="ok", usable=usable, stage=stage, score=score, stage_confidence=conf, dme="low", state=state, reasons=[])


def img(pid, side, view, grade, quality_ok=True):
    return dict(image_id=f"{pid}_{side[0]}{view}", patient_id=pid, grade=grade, quality_ok=quality_ok)


def grade(i):
    return 5 if i["grade"] is None else int(i["grade"])


def test_patient_level_worse_eye_retake_view_and_missed_referable():
    R, Q, F = routing.ROUTINE, routing.REVIEW, routing.RETAKE
    rows = [  # patient 1: both eyes routine, labels 0 -> routine, not referable
        (img("1", "right", 1, 0), rec(R, 0, 0.1)), (img("1", "right", 2, 0), rec(R, 0, 0.2)),
        (img("1", "left", 1, 0), rec(R, 0, 0.1)), (img("1", "left", 2, 0), rec(R, 0, 0.1)),
        # patient 2: left eye one view retake, other routine -> eye routine; label 2 on left -> a missed referable patient
        (img("2", "right", 1, 0), rec(R, 0, 0.1)), (img("2", "right", 2, 0), rec(R, 0, 0.1)),
        (img("2", "left", 1, 2), rec(F, None, None, usable=False)), (img("2", "left", 2, 2), rec(R, 1, 0.7)),
        # patient 3: right eye both views retake -> patient RETAKE (never routine)
        (img("3", "right", 1, 0), rec(F, None, None, usable=False)), (img("3", "right", 2, 0), rec(F, None, None, usable=False)),
        (img("3", "left", 1, 0), rec(R, 0, 0.1)), (img("3", "left", 2, 0), rec(R, 0, 0.1)),
        # patient 4: one view clinician review -> eye review; label 3 -> referable, not missed
        (img("4", "right", 1, 3), rec(Q, 1, 1.2, conf=0.4)), (img("4", "right", 2, 3), rec(R, 1, 0.8)),
        (img("4", "left", 1, 0), rec(R, 0, 0.1)), (img("4", "left", 2, 0), rec(R, 0, 0.1)),
        # patient 5: only a left eye, grade 5 (None) -> incomplete, label unknown
        (img("5", "left", 1, None), rec(R, 0, 0.1)),
    ]
    imgs, recs = [r[0] for r in rows], [r[1] for r in rows]
    items = [dict(path="x", eye="left" if "_l" in i["image_id"] else "right") for i in imgs]
    eye_g, pat = le.eye_and_patient(imgs, recs, items, grade, np.random.default_rng(0))
    assert pat["n"] == 5 and pat["routed_routine"] == 2 and pat["coverage"] == pytest.approx(0.4)
    assert pat["referable"] == 2 and pat["missed"] == 1 and pat["label_unknown"] == 1
    assert pat["states"][routing.RETAKE] == 1 and pat["states"][routing.REVIEW] == 1 and pat["states"][routing.INCOMPLETE] == 1
    assert pat["miss_rate_upper95"] == pytest.approx(le.cp_upper(1, 2))
    assert eye_g["deferred_or_ungradable_eyes"] == 1 and eye_g["n"] == 7  # 9 eyes - 1 ungradable - 1 grade 5


def test_image_level_routing_counts_and_grade5_excluded_from_grading():
    R, U = routing.ROUTINE, routing.URGENT
    recs = [rec(R, 0, 0.1), rec(R, 0, 0.2), rec(U, 3, 3.1), rec(R, 0, 0.1), rec(routing.RETAKE, None, None, usable=False)]
    y = np.array([0, 2, 3, 5, 0])
    g, rt = le.image_level(recs, y, np.random.default_rng(0))
    assert g["n"] == 3  # grade 5 and the rejected image are not graded
    assert rt["n"] == 5 and rt["routed_routine"] == 3 and rt["referable"] == 2 and rt["missed"] == 1
    assert rt["quality_flag_rate"] == pytest.approx(0.2)
    assert g["decision_changing_errors"] == dict(referable_called_non_referable=1, non_referable_called_referable=0)


def test_guard_refuses_without_rc1_tag(monkeypatch):
    monkeypatch.setattr(le, "git", lambda *a: "")
    with pytest.raises(SystemExit, match="rc-1"):
        le.guard("idrid_test")
