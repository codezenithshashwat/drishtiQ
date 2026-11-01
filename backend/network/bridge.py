"""The ONLY place where DrishtiQ Network reads anything clinical (tests enforce this).

It answers one question for a registration: what may the patient be told about their screening? The answer is a process
state, an approved next-action KEY (rendered as fixed Hindi/English text by the page) and which eye is missing. It never
contains a DR stage, an image, a probability, a reviewer, a case ID or a note. Without an active, clinician-made link the
answer is 'not_linked'.
"""
from . import db


def active_link(registration_id: int):
    return db.one("SELECT * FROM screening_links WHERE registration_id=? AND revoked_at IS NULL", (registration_id,))


def screening_status(registration_id: int) -> dict:
    link = active_link(registration_id)
    if link is None:
        return {"state": "not_linked"}
    from .. import clinical_state  # in-process call; no HTTP, no SQL across databases
    s = clinical_state.public_status(link["encounter_id"])
    allowed = {"state", "next_action", "missing_eyes", "quality_provisional", "eyes_awaiting_review", "decided_at"}
    return {k: v for k, v in s.items() if k in allowed}
