"""Who may use the clinical workspace: an authenticated account with an ACTIVE ophthalmologist grant (network
clinician_roles). One sign-in system for the whole platform (backend/network/security.py sessions); clinical access is an
extra, revocable grant checked on every request, so revoking it takes effect immediately.

Clinician sessions are shorter than patient sessions: 30 minutes idle, 12 hours absolute. Patient sessions are unchanged.
State-changing clinical requests carry the same CSRF guard as the Network API.
"""
from datetime import datetime, timedelta

from fastapi import HTTPException, Request

from .network import db as ndb, security

IDLE = timedelta(minutes=30)
ABSOLUTE = timedelta(hours=12)


def active_grant(user_id: int):
    return ndb.one("SELECT * FROM clinician_roles WHERE user_id=? AND revoked_at IS NULL", (user_id,))


def grant(user_id: int, granted_by: str) -> bool:
    """Idempotent. Returns True if a new grant was created."""
    if active_grant(user_id) is not None:
        return False
    ndb.run("INSERT INTO clinician_roles(user_id, role, granted_by, granted_at) VALUES(?,?,?,?)", (user_id, "ophthalmologist", granted_by, security.iso()))
    security.audit(None, "clinician.grant", "user", user_id, f"by {granted_by}"[:200])
    return True


def revoke(user_id: int, revoked_by: str) -> bool:
    cur = ndb.run("UPDATE clinician_roles SET revoked_at=?, revoked_by=? WHERE user_id=? AND revoked_at IS NULL", (security.iso(), revoked_by, user_id))
    if cur.rowcount:
        security.audit(None, "clinician.revoke", "user", user_id, f"by {revoked_by}"[:200])
    return bool(cur.rowcount)


def _fail(status: int, code: str, message: str):
    raise HTTPException(status, {"code": code, "message": message})


def clinician(request: Request) -> dict:
    """The signed-in clinician, or 401/403. Never reads identity from request parameters."""
    token = request.cookies.get(security.COOKIE)
    if not token:
        _fail(401, "login_required", "Sign in with a specialist account.")
    row = ndb.one("SELECT created_at, last_seen FROM sessions WHERE id_hash=?", (security._h(token),))
    user = security.current_user(request)  # also refreshes the sliding patient expiry
    if row is None or user is None:
        _fail(401, "login_required", "Sign in with a specialist account.")
    if active_grant(user["id"]) is None:
        _fail(403, "not_clinician", "This account does not have specialist access.")
    now = security.now()
    if now - datetime.fromisoformat(row["last_seen"]) > IDLE or now - datetime.fromisoformat(row["created_at"]) > ABSOLUTE:
        security.revoke(token)
        _fail(401, "session_expired", "Your specialist session has expired. Please sign in again.")
    return dict(id=user["id"], name=user["display_name"], role="ophthalmologist")


def need_clinician(request: Request) -> dict:
    """FastAPI dependency for every clinical endpoint except the public allowlist in backend/app.py."""
    security.csrf_guard(request)
    return clinician(request)
