"""Authentication helpers: argon2id passwords, opaque hashed sessions in an HttpOnly cookie, CSRF guard, rate limits."""
import hashlib
import hmac
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException, Request, Response

from . import config, db

COOKIE = "dqn_session"
_ph = PasswordHasher()
IST = timezone(timedelta(hours=5, minutes=30))


def now() -> datetime:
    return datetime.now(IST)


def iso(dt: datetime | None = None) -> str:
    return (dt or now()).isoformat(timespec="seconds")


def err(status: int, code: str, message: str) -> HTTPException:
    """Machine-readable code + plain-language message; the frontend maps the code to Hindi/English text."""
    return HTTPException(status, {"code": code, "message": message})


# ---- identifiers -------------------------------------------------------------------------------------------------
def normalise_identifier(raw: str) -> tuple[str, str] | None:
    """-> (type, normalised) or None. A mobile/email is a login handle only; it is never proof of identity."""
    s = (raw or "").strip()
    if "@" in s:
        e = s.lower()
        return ("email", e) if re.fullmatch(r"[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}", e) and len(e) <= 120 else None
    digits = re.sub(r"[\s\-()]", "", s)
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return ("mobile", digits) if re.fullmatch(r"[6-9]\d{9}", digits) else None


def mask(identifier: str | None) -> str:
    if not identifier:
        return ""
    if "@" in identifier:
        name, _, dom = identifier.partition("@")
        return name[:1] + "•••@" + dom
    return "•••••" + identifier[-4:]


# ---- passwords ---------------------------------------------------------------------------------------------------
COMMON = {"password", "password1", "12345678", "123456789", "qwerty123", "iloveyou", "11111111", "abcd1234", "admin123"}


def check_password_strength(pw: str) -> str | None:
    if len(pw) < 8:
        return "short"
    if pw.lower() in COMMON or len(set(pw)) < 3:
        return "common"
    return None


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(h: str, pw: str) -> bool:
    try:
        return _ph.verify(h, pw)
    except (VerificationError, InvalidHashError):
        return False


# ---- sessions ----------------------------------------------------------------------------------------------------
def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    t = now()
    db.run("INSERT INTO sessions(id_hash,user_id,created_at,expires_at,last_seen) VALUES(?,?,?,?,?)",
           (_h(token), user_id, iso(t), iso(t + timedelta(days=config.SESSION_DAYS)), iso(t)))
    db.run("DELETE FROM sessions WHERE expires_at < ?", (iso(t),))
    return token


def set_cookie(resp: Response, request: Request, token: str) -> None:
    resp.set_cookie(COOKIE, token, max_age=config.SESSION_DAYS * 86400, httponly=True, samesite="lax", path="/",
                    secure=request.url.scheme == "https")


def clear_cookie(resp: Response) -> None:
    resp.delete_cookie(COOKIE, path="/")


def revoke(token: str | None) -> None:
    if token:
        db.run("DELETE FROM sessions WHERE id_hash=?", (_h(token),))


def revoke_all(user_id: int) -> None:
    db.run("DELETE FROM sessions WHERE user_id=?", (user_id,))


def current_user(request: Request):
    """The signed-in user row, or None. Identity always comes from the session, never from request parameters."""
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    row = db.one("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.id_hash=? AND s.expires_at>? AND u.deleted_at IS NULL",
                 (_h(token), iso()))
    if row is not None:  # sliding expiry
        db.run("UPDATE sessions SET last_seen=?, expires_at=? WHERE id_hash=?",
               (iso(), iso(now() + timedelta(days=config.SESSION_DAYS)), _h(token)))
    return row


def need_user(request: Request):
    u = current_user(request)
    if u is None:
        raise err(401, "login_required", "Please log in first.")
    return u


def need_role(*roles: str):
    def dep(request: Request):
        u = need_user(request)
        if u["role"] not in roles:
            raise err(403, "forbidden", "This account cannot do that.")
        return u
    return dep


def csrf_guard(request: Request) -> None:
    """State-changing requests must carry a custom header (a cross-site form or image cannot add one without a CORS
    preflight, and this API sends no CORS headers) and, when the browser sends an Origin, it must match the host."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if request.headers.get("x-requested-with") != "dqn":
        raise err(403, "csrf", "Request rejected.")
    origin = request.headers.get("origin")
    if origin and origin.split("://", 1)[-1] != request.headers.get("host"):
        raise err(403, "csrf", "Request rejected.")


# ---- rate limits (in memory; single-process prototype) ------------------------------------------------------------
_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(key: str, limit: int, window: int) -> None:
    t = time.monotonic()
    q = _hits[key]
    while q and q[0] < t - window:
        q.popleft()
    if len(q) >= limit:
        raise err(429, "rate_limited", "Too many attempts. Please wait a minute and try again.")
    q.append(t)


def reset_rate_limits() -> None:
    _hits.clear()
    _receipt_fails.clear()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


# ---- receipts: derived from a server secret so a replayed request returns the same code ------------------------------
def _secret() -> bytes:
    row = db.one("SELECT value FROM kv WHERE key='receipt_secret'")
    if row:
        return bytes.fromhex(row["value"])
    s = secrets.token_bytes(32)
    db.run("INSERT OR IGNORE INTO kv(key,value) VALUES('receipt_secret',?)", (s.hex(),))
    return bytes.fromhex(db.one("SELECT value FROM kv WHERE key='receipt_secret'")["value"])


def receipt_code(public_ref: str) -> str:
    d = hmac.new(_secret(), public_ref.encode(), hashlib.sha256).digest()
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    code = "".join(alphabet[b % 32] for b in d[:8])
    return f"{code[:4]}-{code[4:]}"


def receipt_ok(public_ref: str, code: str) -> bool:
    return hmac.compare_digest(receipt_code(public_ref), (code or "").strip().upper())


# Receipt strength (V3 review): the reference is 6 random characters from a 32-letter alphabet (30 bits) and the code is
# 8 characters of HMAC-SHA256 under a 32-byte server secret (40 bits, unbiased because 256 % 32 == 0), compared in
# constant time. Both are needed. With the per-IP limits and this per-reference lockout, guessing is impractical, so
# receipt generation is unchanged and every existing receipt stays valid.
RECEIPT_MAX_FAILS = 8
RECEIPT_WINDOW = 3600
_receipt_fails: dict[str, deque] = defaultdict(deque)


def _recent_fails(ref: str) -> deque:
    q, t = _receipt_fails[ref], time.monotonic()
    while q and q[0] < t - RECEIPT_WINDOW:
        q.popleft()
    return q


def receipt_lock_check(ref: str) -> None:
    if len(_recent_fails(ref)) >= RECEIPT_MAX_FAILS:
        raise err(429, "rate_limited", "Too many attempts. Please wait a minute and try again.")


def receipt_failed(ref: str) -> None:
    _recent_fails(ref).append(time.monotonic())


def reset_receipt_locks() -> None:
    _receipt_fails.clear()


def audit(actor, action: str, entity: str, entity_id, detail: str = "") -> None:
    """Append-only; never put personal data in `detail`."""
    db.run("INSERT INTO audit_log(at,actor_user_id,actor_role,action,entity,entity_id,detail) VALUES(?,?,?,?,?,?,?)",
           (iso(), actor["id"] if actor else None, actor["role"] if actor else "guest", action, entity, str(entity_id), detail[:200]))
