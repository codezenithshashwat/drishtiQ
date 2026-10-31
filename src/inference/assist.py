"""Assistant layer on top of an analysis record.

B5 (ADR-019): calibrated P(referable), calibrated stage confidence and abstention, from
configs/calibration/app_grader.json. Used only when that file was fitted for the current app grader; otherwise the case
says calibration is unavailable (the GPU queue refits it after every grader change).
B6 (ADR-020): worklist priority. Deferred or low-quality images first, then P(referable) descending.
B7: patient-level summary across eyes and a suggested follow-up category. The categories follow the structure of the
International Council of Ophthalmology DR guidelines (2017); the timing wording defers to local protocol, and the
clinician decides.
"""
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CALIBRATION = ROOT / "configs/calibration/app_grader.json"


def load_calibration(grader_spec):
    if not CALIBRATION.exists():
        return None
    cal = json.loads(CALIBRATION.read_text())
    return cal if cal.get("grader") == grader_spec else None


def annotate(result, cal):
    """Returns the assist record for one analysis (does not modify the analysis)."""
    if result.get("status") != "ok":
        return dict(available=False, defer=True, reason="rejected")
    g = result["grading"]
    usable = result["quality"]["usable"]
    if cal is None or g.get("score") is None:
        return dict(available=False, defer=bool(g["low_confidence"] or not usable),
                    reason="no calibration for this grader yet" if cal is None else "grader has no continuous score")
    s, t = float(g["score"]), np.asarray(cal["thresholds"])
    margin = float(np.min(np.abs(s - t)))
    conf = float(np.interp(margin, cal["isotonic"]["x"], cal["isotonic"]["y"]))
    p_ref = 1 / (1 + math.exp(-(cal["platt"]["coef"] * s + cal["platt"]["intercept"])))
    low_conf = conf < cal["tau"]
    reason = "low confidence" if low_conf else "image quality" if not usable else None
    return dict(available=True, p_referable=round(p_ref, 3), stage_confidence=round(conf, 3), tau=cal["tau"],
                defer=bool(low_conf or not usable), reason=reason,
                confidence_level="high" if conf >= 0.85 else "moderate" if conf >= cal["tau"] else "low")


def priority(assist):
    """Sort key for the worklist (ascending = first)."""
    return (0 if assist.get("defer") else 1, -(assist.get("p_referable") or 0.0))


FOLLOW_UP = {
    "human": dict(level="human", urgency=3, title="Human grading needed",
                  text="The AI was not confident enough, or the image quality was too low. A trained grader or doctor should grade the photographs before a referral decision."),
    "urgent": dict(level="urgent", urgency=2, title="Urgent referral to an eye specialist",
                   text="Severe or proliferative changes, or exudates near the centre of vision, were found."),
    "refer": dict(level="refer", urgency=1, title="Refer to an eye specialist",
                  text="Moderate changes, or exudates away from the centre of vision, were found."),
    "routine": dict(level="routine", urgency=0, title="Routine re-screening",
                    text="No referable changes were found. Re-screen as per the local programme."),
}


def patient_summary(cases):
    """cases: list of dicts with eye, analysis, assist (latest case per eye). Worst eye decides."""
    eyes, worst_stage, dme, any_defer = [], -1, "low", False
    for c in cases:
        a, s = c["analysis"], c["assist"]
        if a.get("status") != "ok":
            any_defer = True
            eyes.append(dict(eye=c["eye"], case_id=c["id"], stage=None, dme=None, defer=True))
            continue
        stage = a["grading"]["grade"]
        risk = a["findings"]["macular_edema_risk"]["level"]
        any_defer |= bool(s.get("defer"))
        worst_stage = max(worst_stage, stage)
        dme = max(dme, risk, key=["low", "possible", "high"].index)
        eyes.append(dict(eye=c["eye"], case_id=c["id"], stage=stage, label=a["grading"]["label"], dme=risk, defer=bool(s.get("defer")),
                         p_referable=s.get("p_referable")))
    if any_defer:
        key = "human"
    elif worst_stage >= 3 or dme == "high":
        key = "urgent"
    elif worst_stage == 2 or dme == "possible":
        key = "refer"
    else:
        key = "routine"
    return dict(eyes=eyes, worst_stage=worst_stage if worst_stage >= 0 else None, worst_dme=dme, follow_up=FOLLOW_UP[key],
                note="Suggested by the prototype from the AI output. The doctor decides.")
