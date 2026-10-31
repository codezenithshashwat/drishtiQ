"""Decision layer (Approach V2, ADR-039/040): eye states and patient routing from proven signals only.

Signals: quality gate, calibrated P(referable) and stage confidence (policy c, thresholds frozen from the internal
hold-out in configs/routing/routing_v1.json), the AI stage and the macular-oedema risk (escalate only), the two optional
intake answers, a laterality check and previous signed clinician results. The AI never declares an eye free of disease.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/routing/routing_v1.json"

URGENT, REVIEW, REFERABLE, RETAKE, ROUTINE, INCOMPLETE = (
    "URGENT_REVIEW", "CLINICIAN_REVIEW", "REFERABLE", "RETAKE", "ROUTINE_RESCREEN_ELIGIBLE", "INCOMPLETE_SCREENING")
# Worklist / severity order (ADR-040): lower = first.
ORDER = {URGENT: 0, REVIEW: 1, REFERABLE: 2, RETAKE: 3, INCOMPLETE: 3, ROUTINE: 4}
# Patient aggregation: the worse eye decides.
SEVERITY = {URGENT: 5, REFERABLE: 4, REVIEW: 3, RETAKE: 2, INCOMPLETE: 1, ROUTINE: 0}

LABEL = {URGENT: "Expedited specialist review recommended", REVIEW: "Clinician review", REFERABLE: "Referable: specialist review",
         RETAKE: "Retake photograph", ROUTINE: "Routine rescreening eligible", INCOMPLETE: "Incomplete screening"}
CLINICIAN_ROUTINE_TEXT = "No referable diabetic retinopathy detected by AI in gradable images of both eyes."


def load_config():
    return json.loads(CONFIG.read_text())


def routing_valid(grader_spec, checkpoints, has_system=False, has_fusion=False):
    """The frozen thresholds hold only for the pinned grader alone (ADR-040): same checkpoint file and hash, no system
    parts (thresholds, specialists, TTA) and no fusion. Otherwise nothing is routed to routine."""
    cfg = load_config()
    return (grader_spec.endswith(cfg["pinned_checkpoint"]) and checkpoints.get(cfg["pinned_checkpoint"]) == cfg["pinned_sha256"]
            and not has_system and not has_fusion)


def wording(target):
    cfg = load_config()
    v = cfg["verified"][f"{target}"]["APTOS-val"]
    return (f"target referable miss rate {target * 100:g}%; verified upper bound {v['upper95'] * 100:.1f}% on APTOS-val (development data); "
            "not yet validated on external data")


def p_referable(score, cfg):
    return 1 / (1 + math.exp(-(cfg["platt"]["coef"] * score + cfg["platt"]["intercept"])))


def laterality(analysis):
    """'right' if the optic disc lies right of the fovea (or of the image centre), else 'left'. A heuristic; not validated."""
    f = analysis.get("findings") or {}
    lm = f.get("landmarks") or {}
    disc, fovea = lm.get("optic_disc"), lm.get("fovea")
    if not disc:
        return None
    ref = fovea["x"] if fovea and not fovea.get("uncertain") else None
    if ref is None:
        return None
    return "right" if disc["x"] > ref else "left"


def eye_state(analysis, *, eye, target, valid, stage_confidence=None, intake=None, prior_referral=None, retakes=0):
    """State of one image/eye with plain-language reasons (first match wins, ADR-040)."""
    cfg = load_config()
    reasons = []
    if analysis.get("status") != "ok" or not analysis["quality"]["usable"]:
        if retakes >= 1:
            return dict(state=REVIEW, reasons=["The photograph could not be graded after a retake: a person should grade this eye."])
        issues = " ".join(analysis.get("quality", {}).get("issues", [])) or "The image could not be assessed."
        return dict(state=RETAKE, reasons=[f"Retake the photograph now. {issues}"])
    g = analysis["grading"]
    stage, score = g["grade"], g.get("score")
    dme = (analysis.get("findings") or {}).get("macular_edema_risk", {}).get("level")
    if stage >= 3:
        reasons.append("Signs of severe diabetic retinopathy suspected by the AI (not confirmed).")
    if dme == "high":
        reasons.append("Yellow deposits close to the centre of vision (central-vision concern).")
    if reasons:
        return dict(state=URGENT, reasons=reasons)
    if stage == 2:
        return dict(state=REFERABLE, reasons=["Moderate diabetic retinopathy suggested by the AI: specialist review."])
    # Stage 0-1: routine only if every available safety signal agrees (policy c).
    if intake and intake.get("vision_problems"):
        reasons.append("The patient reports vision problems.")
    if intake and intake.get("prior_treatment"):
        reasons.append("The patient has had eye treatment or laser before.")
    if prior_referral:
        reasons.append(f"A clinician referred this eye at a previous visit ({prior_referral}); the AI does not downgrade that.")
    seen = laterality(analysis)
    if eye in ("right", "left") and seen and seen != eye:
        reasons.append(f"The optic disc position suggests a {seen} eye, but the photo is recorded as {eye}: please check the eye label.")
    if not valid:
        reasons.append("Routine routing is not validated for the model currently in use.")
    elif score is None or stage_confidence is None:
        reasons.append("Confidence could not be estimated for this image.")
    else:
        p = p_referable(score, cfg)
        if stage_confidence < cfg["tau"]:
            reasons.append("The AI is not confident enough about the stage.")
        if p >= cfg["thresholds"][f"{target}"]:
            reasons.append("The chance of referable disease is above the routine-rescreening threshold.")
    if reasons:
        return dict(state=REVIEW, reasons=reasons)
    return dict(state=ROUTINE, reasons=["Eligible for routine rescreening at the configured operating point (" + wording(target) + ")."])


def patient_state(eyes):
    """eyes: list of dict(eye, state, reasons, stage) for the latest case per recorded eye. Worse eye decides (ADR-040)."""
    by_eye = {e["eye"]: e for e in eyes if e["eye"] in ("right", "left")}
    notes = []
    worst = max((e["state"] for e in eyes), key=lambda s: SEVERITY[s], default=INCOMPLETE)
    missing = [side for side in ("right", "left") if side not in by_eye]
    if worst == ROUTINE and missing:
        state = INCOMPLETE
        notes.append(f"No {' or '.join(missing)}-eye photograph: screening is incomplete, so routine rescreening cannot be suggested.")
    else:
        state = worst
        if missing and state != INCOMPLETE:
            notes.append(f"No {' or '.join(missing)}-eye photograph in this screening.")
    stages = [e.get("stage") for e in by_eye.values() if e.get("stage") is not None]
    if len(stages) == 2 and abs(stages[0] - stages[1]) >= 2:
        notes.append("The two eyes differ by two or more stages; the worse eye decides.")
    if state == ROUTINE:
        notes.insert(0, CLINICIAN_ROUTINE_TEXT)
    return dict(state=state, label=LABEL[state], notes=notes)
