"""The effective (authoritative) clinical state. One resolver, used by every consumer: Specialist Attention, the case view,
the patient summary, both reports, and the Network next-action bridge.

Authority, in order:
1. The latest SIGNED review of an eye: written by an authenticated ophthalmologist (reviewer_user_id set) with an explicit
   next action. It governs that eye. What the AI showed at signing is kept in the review row; a later re-analysis rewrites
   only cases.analysis and is reported as such, never as a change of decision.
2. Otherwise the AI output, always labelled provisional. It orders the worklist; it never produces a patient-facing result.
Historical reviews without an authenticated identity (made before V3) stay visible but are never authoritative.

The AI stage does not decide referral urgency. The clinician's explicit next action does.
"""
import json

# Explicit next actions a clinician can sign, most urgent first. `rank` orders them across eyes.
NEXT_ACTIONS = {
    "urgent_referral": dict(rank=6, label="Urgent referral to an eye specialist"),
    "referral": dict(rank=5, label="Referral to an eye specialist"),
    "examination": dict(rank=5, label="Cannot assess from the photograph: in-person eye examination"),
    "recapture": dict(rank=3, label="Retake the photograph"),
    "follow_up": dict(rank=2, label="Follow-up with the eye-care team"),
    "routine_rescreen": dict(rank=0, label="Routine rescreening"),
}
DECISIONS = ("agree", "disagree", "ungradable")
REQUIRED_EYES = ("right", "left")

# Public screening states (Network status page). Objective capture facts may be shown before sign-off; clinical outcomes
# only after it. Order is the patient's progression.
PUBLIC_STATES = ("not_linked", "in_progress", "incomplete", "quality_check", "awaiting_review", "decision_recorded")


class DecisionError(ValueError):
    pass


def is_signed(review: dict) -> bool:
    return review.get("reviewer_user_id") is not None and review.get("next_action") in NEXT_ACTIONS


def signed_review(reviews: list[dict]) -> dict | None:
    """Latest signed review; `reviews` are newest first (store.reviews)."""
    return next((r for r in reviews if is_signed(r)), None)


def quality_concern(analysis: dict) -> bool:
    return analysis.get("status") != "ok" or not (analysis.get("quality") or {}).get("usable", False)


def decided_stage(review: dict) -> int | None:
    if review["decision"] == "disagree":
        return review["corrected_stage"]
    if review["decision"] == "agree":
        return review["ai_stage"]
    return None


def validate_decision(decision: str, stage: int | None, dme: str | None, next_action: str | None, note: str) -> None:
    """Server-side rules for a new signed review. They check the clinician's OWN decision for internal consistency; the AI
    output is never used to overrule the clinician."""
    if decision not in DECISIONS:
        raise DecisionError("Unknown decision.")
    if next_action not in NEXT_ACTIONS:
        raise DecisionError("Choose the next action for this eye.")
    if decision == "ungradable" and next_action == "routine_rescreen":
        raise DecisionError("An image that cannot be assessed must not be signed as routine rescreening: choose a retake or an in-person examination.")
    if decision != "ungradable" and next_action == "routine_rescreen" and ((stage is not None and stage >= 2) or dme == "high"):
        if len((note or "").strip()) < 5:
            raise DecisionError("Routine rescreening with the stage or macular finding you recorded needs a short justification note.")


def eye_decision(case_row, analysis: dict, reviews: list[dict]) -> dict:
    """Effective state of one eye (one case)."""
    legacy = [r for r in reviews if r.get("reviewer_user_id") is None]
    s = signed_review(reviews)
    base = dict(case_id=case_row["id"], eye=case_row["eye"], quality_concern=quality_concern(analysis), legacy_reviews=len(legacy))
    if s is None:
        return dict(base, source="ai_provisional", signed=False, next_action=None, stage=None, dme=None)
    stage = decided_stage(s)
    dme = s.get("corrected_dme") or (s.get("ai_dme") if s["decision"] == "agree" else None)
    reanalysed = bool(s.get("analysed_with")) and case_row["analysed_with"] != s["analysed_with"]
    return dict(base, source="clinician", signed=True, decision=s["decision"], stage=stage, dme=dme, next_action=s["next_action"],
                next_action_label=NEXT_ACTIONS[s["next_action"]]["label"], reviewer=s["reviewer"], reviewer_user_id=s["reviewer_user_id"],
                signed_at=s["created"], review_id=s["id"], note=s.get("note") or "", reanalysed_since_signing=reanalysed,
                ai_at_signing=dict(stage=s.get("ai_stage"), dme=s.get("ai_dme"), route_state=s.get("ai_route_state"),
                                   model_version=s.get("ai_model_version"), grader=s.get("ai_grader")))


def eye_state(photos: list[tuple]) -> dict:
    """Effective state of one eye in one encounter. `photos` = [(case_row, analysis, reviews)], newest photo first.

    The latest signed decision across the eye's photos governs. If it was signed on an EARLIER photo:
    - a requested recapture is fulfilled by the newer photo, so the eye is pending review again;
    - any other decision (e.g. an urgent referral) stands, and the newer photo is flagged as awaiting review.
    """
    latest_row, latest_a, latest_reviews = photos[0]
    best = None
    for row, a, revs in photos:
        s = signed_review(revs)
        if s and (best is None or s["id"] > best[2]["id"]):
            best = (row, a, s, revs)
    current = eye_decision(latest_row, latest_a, latest_reviews)
    current["photos"] = len(photos)
    if best is None or best[0]["id"] == latest_row["id"]:
        current["pending"] = not current["signed"]
        return current
    if best[2]["next_action"] == "recapture":
        return dict(current, pending=True, recapture_fulfilled=True)
    earlier = eye_decision(best[0], best[1], best[3])
    return dict(earlier, photos=len(photos), pending=True, newer_photo_case_id=latest_row["id"],
                quality_concern=quality_concern(latest_a))


def aggregate(eyes: list[dict]) -> dict:
    """Encounter-level outcome from per-eye effective states (eye_decision outputs for the latest photo of each eye).

    - A non-routine signed action for ANY eye is shown at once, even if the other eye is missing or unsigned (an urgent
      referral is never held back). Completeness stays visible alongside it.
    - Routine rescreening is only the outcome when BOTH eyes are photographed and BOTH are signed routine.
    - Before sign-off only objective process states are given: in progress, incomplete (missing eye), image quality to be
      checked (automated, provisional), awaiting clinician review.
    """
    present = {e["eye"] for e in eyes}
    missing = [e for e in REQUIRED_EYES if e not in present]
    signed = [e for e in eyes if e["signed"]]
    pending = [e["eye"] for e in eyes if e.get("pending", not e["signed"])]
    quality_provisional = any(e["quality_concern"] for e in eyes if e.get("pending", not e["signed"]))
    out = dict(missing_eyes=missing, pending_eyes=pending, quality_provisional=quality_provisional, complete=not missing,
               signed_eyes=[e["eye"] for e in signed], next_action=None, decided_at=None)
    top = max(signed, key=lambda e: NEXT_ACTIONS[e["next_action"]]["rank"], default=None)
    if top and (top["next_action"] != "routine_rescreen" or (not missing and not pending)):
        return dict(out, state="decision_recorded", next_action=top["next_action"], next_action_label=NEXT_ACTIONS[top["next_action"]]["label"],
                    decided_at=max(e["signed_at"] for e in signed), partial=bool(missing or pending))
    if not eyes:
        state = "in_progress"
    elif missing:
        state = "incomplete"
    elif quality_provisional:
        state = "quality_check"
    else:
        state = "awaiting_review"
    return dict(out, state=state, partial=bool(signed))


def encounter_eyes(db, encounter_id: str) -> list[dict]:
    """eye_state for every photographed eye of an encounter, right eye first."""
    from . import store
    by_eye: dict[str, list] = {}
    for r in store.encounter_all_cases(db, encounter_id):  # newest first
        by_eye.setdefault(r["eye"], []).append((r, json.loads(r["analysis"]), store.reviews(db, r["id"])))
    return [eye_state(by_eye[e]) for e in sorted(by_eye, key=store.EYE_ORDER.index)]


# ---- read-only view for the Network bridge ------------------------------------------------------------------------
_provider = None


def set_db_provider(fn) -> None:
    """The app registers a callable returning its open cases.sqlite connection (or None while starting)."""
    global _provider
    _provider = fn


def public_status(encounter_id: str) -> dict:
    """Minimal, patient-safe status of one encounter: process state, approved next-action KEY, eye completeness. Never a
    stage, an image, a probability, a reviewer or a case ID."""
    from . import store  # local import: this module stays importable without the clinical store being open
    db = _provider() if _provider else None
    if db is None or store.encounter(db, encounter_id) is None:
        return dict(state="unavailable")
    a = aggregate(encounter_eyes(db, encounter_id))
    return dict(state=a["state"], next_action=a["next_action"], missing_eyes=a["missing_eyes"], quality_provisional=a["quality_provisional"],
                eyes_awaiting_review=len(a["pending_eyes"]), decided_at=a["decided_at"])
