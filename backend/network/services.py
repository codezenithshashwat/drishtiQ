"""Business rules: camp search/state, registrations, accounts, worker and organiser scoping. Routes stay thin."""
import hashlib
import re
import secrets
from datetime import datetime, timedelta

from . import config, db, security
from .security import err, iso, now

CONSENT_VERSION = "2026-11-01"
PIN_RE = re.compile(r"^\d{6}$")
STATUS_FLOW = {
    "interest_received": {"contacted", "confirmed_by_organiser", "cancelled"},
    "contacted": {"confirmed_by_organiser", "no_show", "cancelled"},
    "confirmed_by_organiser": {"attended", "no_show", "cancelled"},
    "attended": set(), "no_show": set(), "cancelled": set(),
}


# ---- camps -------------------------------------------------------------------------------------------------------
_CAMP_SQL = """SELECT c.*, l.label AS loc_label, l.village, l.district, l.state AS loc_state, l.pin,
               o.name AS org_name, o.verification AS org_verification, o.kind AS org_kind
               FROM camps c JOIN locations l ON l.id=c.location_id JOIN organisations o ON o.id=c.org_id"""


def interest_count(camp_id: int) -> int:
    return db.one("SELECT COUNT(*) n FROM registrations WHERE camp_id=? AND status!='cancelled'", (camp_id,))["n"]


def camp_state(r, count: int | None = None) -> str:
    """open | full | closed | expired | cancelled. Derived, never stored, so it cannot drift."""
    if r["publish_state"] == "cancelled":
        return "cancelled"
    if datetime.fromisoformat(r["ends_at"]) < now():
        return "expired"
    if r["publish_state"] == "closed":
        return "closed"
    if r["capacity"] is not None and (count if count is not None else interest_count(r["id"])) >= r["capacity"]:
        return "full"
    return "open"


def camp_dto(r) -> dict:
    verified = r["verification"] == "verified"
    return {
        "id": r["id"], "title": {"hi": r["title_hi"], "en": r["title_en"]},
        "starts_at": r["starts_at"], "ends_at": r["ends_at"],
        "place": {"label": r["loc_label"], "village": r["village"], "district": r["district"], "state": r["loc_state"], "pin": r["pin"]},
        "organiser": {"name": r["org_name"], "kind": r["org_kind"], "verification": r["org_verification"]},
        "verification": r["verification"], "is_demo": r["source"] == "demo_seed",
        "state": camp_state(r),
        "planned_capacity": r["capacity"],  # a planning figure for the interest list, not a count of booked seats
        "price": r["price_info"] if verified else None,
        "contact": r["contact_public"] if verified else None,
        "publish_state": r["publish_state"],
    }


def search_camps(pin: str | None, q: str | None, include_expired: bool, limit: int = 30) -> dict:
    if pin is not None and not PIN_RE.match(pin):
        raise err(422, "invalid_pin", "A PIN code has 6 digits.")
    rows = db.all_(_CAMP_SQL + " WHERE c.publish_state IN ('published','closed') ORDER BY c.starts_at")
    ql = (q or "").strip().lower()
    out = []
    for r in rows:
        state = camp_state(r)
        if state in ("expired", "cancelled") and not include_expired:
            continue
        match = None
        if pin:
            if r["pin"] == pin:
                match = "exact"
            elif r["pin"][:3] == pin[:3]:
                match = "nearby"  # same PIN-code region (first three digits), a coarse proximity only
            else:
                continue
        if ql:
            hay = " ".join(str(x or "") for x in (r["village"], r["district"], r["loc_state"], r["loc_label"], r["title_en"], r["title_hi"], r["pin"])).lower()
            if ql not in hay:
                continue
            match = match or "text"
        d = camp_dto(r)
        d["match"] = match
        out.append(d)
    out.sort(key=lambda d: ({"exact": 0, "text": 1, "nearby": 2, None: 3}[d["match"]], d["state"] in ("expired", "cancelled"), d["starts_at"]))
    return {"items": out[:limit], "exact": sum(d["match"] == "exact" for d in out), "nearby": sum(d["match"] == "nearby" for d in out), "query": {"pin": pin, "q": q}}


def get_camp(camp_id: int):
    r = db.one(_CAMP_SQL + " WHERE c.id=?", (camp_id,))
    if r is None or r["publish_state"] == "draft":
        raise err(404, "camp_not_found", "This camp was not found.")
    return r


# ---- registrations -----------------------------------------------------------------------------------------------
_REF_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def _new_ref() -> str:
    return "DQN-" + "".join(secrets.choice(_REF_ALPHABET) for _ in range(6))


def clean_phone(raw: str | None) -> str | None:
    if not raw or not raw.strip():
        return None
    n = security.normalise_identifier(raw)
    if not n or n[0] != "mobile":
        raise err(422, "invalid_phone", "Enter a 10-digit mobile number or leave it empty.")
    return n[1]


def clean_email(raw: str | None) -> str | None:
    if not raw or not raw.strip():
        return None
    n = security.normalise_identifier(raw)
    if not n or n[0] != "email":
        raise err(422, "invalid_email", "Enter a valid email or leave it empty.")
    return n[1]


def reg_dto(r, with_contact: bool = False) -> dict:
    camp = db.one(_CAMP_SQL + " WHERE c.id=?", (r["camp_id"],))
    d = {"ref": r["public_ref"], "status": r["status"], "created_at": r["created_at"], "updated_at": r["updated_at"], "channel": r["channel"],
         "name": r["display_name"], "pin": r["pin"], "village": r["village"], "language": r["language"], "camp": camp_dto(camp)}
    if with_contact:
        d["phone"] = r["phone"]
        d["email"] = r["email"]
    else:
        d["phone_masked"] = security.mask(r["phone"]) if r["phone"] else None
    return d


def create_registration(data: dict, user, channel: str = "self", created_by=None) -> dict:
    """Records an INTEREST. It never produces an appointment: status starts at interest_received and only an
    organiser/worker action can move it. Returns {registration, receipt_code?, duplicate}."""
    if not data.get("consent"):
        raise err(422, "consent_required", "Consent is needed to record your interest.")
    if not PIN_RE.match(data.get("pin") or ""):
        raise err(422, "invalid_pin", "A PIN code has 6 digits.")
    phone, email = clean_phone(data.get("phone")), clean_email(data.get("email"))
    contact_consent = bool(data.get("contact_consent")) and bool(phone or email)
    idem = (data.get("idempotency_key") or "")[:64] or None
    camp_id = data["camp_id"]
    if user is not None and user["role"] != "user" and channel != "assisted":
        user = None  # staff accounts do not register themselves through the public form
    with db.tx() as c:
        if idem:
            prev = c.execute("SELECT * FROM registrations WHERE idempotency_key=?", (idem,)).fetchone()
            if prev is not None:
                return {"registration": reg_dto(prev), "receipt_code": security.receipt_code(prev["public_ref"]), "duplicate": False, "replayed": True}
        camp = c.execute(_CAMP_SQL + " WHERE c.id=?", (camp_id,)).fetchone()
        if camp is None or camp["publish_state"] in ("draft",):
            raise err(404, "camp_not_found", "This camp was not found.")
        n = c.execute("SELECT COUNT(*) n FROM registrations WHERE camp_id=? AND status!='cancelled'", (camp_id,)).fetchone()["n"]
        state = camp_state(camp, n)
        if state != "open":
            code = {"expired": "camp_expired", "closed": "camp_closed", "full": "camp_full", "cancelled": "camp_closed"}[state]
            raise err(409, code, "This camp is not taking interest now.")
        owner = user["id"] if (user is not None and channel != "assisted") else None
        if owner:
            dkey = hashlib.sha256(f"u:{owner}:{camp_id}".encode()).hexdigest()
        elif phone or email:
            dkey = hashlib.sha256(f"c:{phone or email}:{camp_id}".encode()).hexdigest()
        else:
            dkey = None
        if owner:  # one active interest per account and camp, even if the record was claimed from an earlier guest receipt
            prev = c.execute("SELECT * FROM registrations WHERE user_id=? AND camp_id=? AND status!='cancelled' ORDER BY id LIMIT 1", (owner, camp_id)).fetchone()
            if prev is not None:
                return {"registration": reg_dto(prev), "receipt_code": security.receipt_code(prev["public_ref"]), "duplicate": True, "replayed": False}
        if dkey:
            prev = c.execute("SELECT * FROM registrations WHERE dedupe_key=?", (dkey,)).fetchone()
            if prev is not None and prev["status"] != "cancelled":
                mine = owner is not None  # the receipt is only re-shown to the signed-in owner
                return {"registration": reg_dto(prev), "receipt_code": security.receipt_code(prev["public_ref"]) if mine else None,
                        "duplicate": True, "replayed": False}
            if prev is not None:  # cancelled earlier: free the key so the person can register again
                c.execute("UPDATE registrations SET dedupe_key=NULL WHERE id=?", (prev["id"],))
        t = now()
        ref = _new_ref()
        while c.execute("SELECT 1 FROM registrations WHERE public_ref=?", (ref,)).fetchone():
            ref = _new_ref()
        cur = c.execute("""INSERT INTO registrations(public_ref,camp_id,user_id,created_by_user_id,display_name,village,pin,phone,email,language,
                           dedupe_key,idempotency_key,status,consent_version,consent_at,contact_consent,channel,created_at,updated_at,purge_after)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'interest_received',?,?,?,?,?,?,?)""",
                        (ref, camp_id, owner, created_by["id"] if created_by else None, data["name"].strip()[:80], (data.get("village") or "").strip()[:60] or None,
                         data["pin"], phone, email, data.get("language") or "hi", dkey, idem, CONSENT_VERSION, iso(t), int(contact_consent), channel,
                         iso(t), iso(t), iso(t + timedelta(days=config.RETENTION_DAYS))))
        rid = cur.lastrowid
        worker = c.execute("SELECT user_id FROM worker_assignments WHERE camp_id=? ORDER BY id LIMIT 1", (camp_id,)).fetchone()
        c.execute("INSERT INTO followups(registration_id,assigned_to,kind,status,due_at,updated_at) VALUES(?,?,'contact','open',?,?)",
                  (rid, worker["user_id"] if worker else None, iso(t + timedelta(days=2)), iso(t)))
        row = c.execute("SELECT * FROM registrations WHERE id=?", (rid,)).fetchone()
    security.audit(created_by or user, "registration.create", "registration", rid, f"channel={channel}")
    return {"registration": reg_dto(row), "receipt_code": security.receipt_code(ref), "duplicate": False, "replayed": False}


def verify_receipt(ref: str, code: str):
    """The registration a patient-presented receipt (reference + code) proves, or a generic 404. Every wrong code counts
    towards a per-reference lockout (on top of the per-IP limits), so a known reference cannot be brute-forced; once locked,
    even the right code is refused for a while."""
    norm = (ref or "").strip().upper()
    security.receipt_lock_check(norm)
    r = db.one("SELECT * FROM registrations WHERE public_ref=?", (norm,))
    if r is None or not security.receipt_ok(r["public_ref"], code):
        security.receipt_failed(norm)
        raise err(404, "receipt_not_found", "No registration matches this reference and code.")
    return r


def lookup_registration(ref: str, code: str) -> dict:
    """Receipt holder's view: the interest record plus the minimal screening status (process state and an approved
    next-action key only; never a stage, image, prediction or clinical record)."""
    from .bridge import screening_status
    r = verify_receipt(ref, code)
    return {**reg_dto(r), "screening": screening_status(r["id"])}


def my_registrations(user) -> list[dict]:
    from .bridge import screening_status
    return [{**reg_dto(r), "screening": screening_status(r["id"])}
            for r in db.all_("SELECT * FROM registrations WHERE user_id=? ORDER BY created_at DESC", (user["id"],))]


def claim_registration(user, ref: str, code: str) -> dict:
    r = verify_receipt(ref, code)
    if r["user_id"] is not None and r["user_id"] != user["id"]:
        raise err(409, "already_owned", "This registration already belongs to another account.")
    db.run("UPDATE registrations SET user_id=?, updated_at=? WHERE id=?", (user["id"], iso(), r["id"]))
    security.audit(user, "registration.claim", "registration", r["id"])
    return reg_dto(db.one("SELECT * FROM registrations WHERE id=?", (r["id"],)))


def set_status(actor, reg_id: int, new_status: str) -> dict:
    r = db.one("SELECT * FROM registrations WHERE id=?", (reg_id,))
    if r is None:
        raise err(404, "not_found", "Not found.")
    allowed_camps = camp_scope(actor) if actor["role"] != "user" else None
    if allowed_camps is not None and r["camp_id"] not in allowed_camps:
        raise err(403, "forbidden", "This registration is outside your camps.")
    if actor["role"] == "user":
        if r["user_id"] != actor["id"] or new_status != "cancelled":
            raise err(403, "forbidden", "You can only cancel your own interest.")
    if new_status not in STATUS_FLOW.get(r["status"], set()):
        raise err(409, "bad_transition", "That status change is not allowed.")
    db.run("UPDATE registrations SET status=?, updated_at=? WHERE id=?", (new_status, iso(), reg_id))
    if new_status in ("contacted", "confirmed_by_organiser", "attended", "no_show", "cancelled"):
        db.run("UPDATE followups SET status='done', updated_at=? WHERE registration_id=? AND kind='contact' AND status='open'", (iso(), reg_id)) if new_status != "cancelled" else \
            db.run("UPDATE followups SET status='cancelled', updated_at=? WHERE registration_id=? AND status='open'", (iso(), reg_id))
    if new_status == "confirmed_by_organiser":
        db.run("INSERT INTO followups(registration_id,assigned_to,kind,status,updated_at) SELECT ?,assigned_to,'confirm_attendance','open',? FROM followups WHERE registration_id=? LIMIT 1", (reg_id, iso(), reg_id))
    security.audit(actor, "registration.status", "registration", reg_id, new_status)
    return reg_dto(db.one("SELECT * FROM registrations WHERE id=?", (reg_id,)), with_contact=actor["role"] != "user")


# ---- scoping -----------------------------------------------------------------------------------------------------
def camp_scope(actor) -> set[int] | None:
    """Camp ids this actor may act on; None = all (admin)."""
    role = actor["role"]
    if role == "admin":
        return None
    if role == "health_worker":
        return {r["camp_id"] for r in db.all_("SELECT camp_id FROM worker_assignments WHERE user_id=?", (actor["id"],))}
    if role == "organiser":
        return {r["id"] for r in db.all_("SELECT id FROM camps WHERE org_id=?", (actor["org_id"],))}
    return set()


def staff_requests(actor, camp_id: int | None = None, status: str | None = None) -> list[dict]:
    scope = camp_scope(actor)
    rows = db.all_("SELECT * FROM registrations ORDER BY created_at DESC")
    out = []
    for r in rows:
        if scope is not None and r["camp_id"] not in scope:
            continue
        if camp_id and r["camp_id"] != camp_id:
            continue
        if status and r["status"] != status:
            continue
        d = reg_dto(r, with_contact=True)
        d["id"] = r["id"]
        d["contact_consent"] = bool(r["contact_consent"])
        if not r["contact_consent"]:  # contact details are shown to staff only when the person agreed to be contacted
            d["phone"], d["email"] = None, None
            d["phone_masked"] = None
        out.append(d)
    return out


def staff_followups(actor) -> list[dict]:
    scope = camp_scope(actor)
    rows = db.all_("""SELECT f.*, r.public_ref, r.display_name, r.camp_id, r.phone, r.contact_consent FROM followups f
                      JOIN registrations r ON r.id=f.registration_id WHERE f.status='open' ORDER BY f.due_at""")
    out = []
    for f in rows:
        if scope is not None and f["camp_id"] not in scope:
            continue
        if actor["role"] == "health_worker" and f["assigned_to"] not in (None, actor["id"]):
            continue
        camp = db.one(_CAMP_SQL + " WHERE c.id=?", (f["camp_id"],))
        out.append({"id": f["id"], "kind": f["kind"], "status": f["status"], "due_at": f["due_at"], "note": f["note_short"], "ref": f["public_ref"],
                    "name": f["display_name"], "phone": f["phone"] if f["contact_consent"] else None, "camp": camp_dto(camp)})
    return out


def complete_followup(actor, fid: int, note: str | None) -> dict:
    f = db.one("SELECT f.*, r.camp_id FROM followups f JOIN registrations r ON r.id=f.registration_id WHERE f.id=?", (fid,))
    scope = camp_scope(actor)
    if f is None or (scope is not None and f["camp_id"] not in scope):
        raise err(404, "not_found", "Not found.")
    db.run("UPDATE followups SET status='done', note_short=?, updated_at=? WHERE id=?", ((note or "").strip()[:200] or None, iso(), fid))
    security.audit(actor, "followup.done", "followup", fid)
    return {"id": fid, "status": "done"}


# ---- organiser ---------------------------------------------------------------------------------------------------
def organiser_camps(actor) -> list[dict]:
    scope = camp_scope(actor)
    out = []
    for r in db.all_(_CAMP_SQL + " ORDER BY c.starts_at DESC"):
        if scope is not None and r["id"] not in scope:
            continue
        d = camp_dto(r)
        d["price_info"], d["contact_public"] = r["price_info"], r["contact_public"]  # staff see what they entered even before verification
        counts = {x["status"]: x["n"] for x in db.all_("SELECT status, COUNT(*) n FROM registrations WHERE camp_id=? GROUP BY status", (r["id"],))}
        d["counts"] = counts
        d["interest_total"] = sum(v for k, v in counts.items() if k != "cancelled")
        out.append(d)
    return out


def _parse_dt(s: str) -> datetime:
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        raise err(422, "invalid_date", "Enter a valid date and time.") from None
    return d if d.tzinfo else d.replace(tzinfo=security.IST)


def upsert_camp(actor, data: dict, camp_id: int | None = None) -> dict:
    start, end = _parse_dt(data["starts_at"]), _parse_dt(data["ends_at"])
    if end <= start:
        raise err(422, "invalid_date", "The end must be after the start.")
    if camp_id is None and end < now():
        raise err(422, "invalid_date", "Choose a future date.")
    if not PIN_RE.match(data["pin"]):
        raise err(422, "invalid_pin", "A PIN code has 6 digits.")
    pub = data["publish_state"]
    with db.tx() as c:
        if camp_id is None:
            org_id = actor["org_id"]
            if org_id is None:
                raise err(403, "forbidden", "Your account is not linked to an organisation.")
            loc = c.execute("INSERT INTO locations(label,village,district,state,pin) VALUES(?,?,?,?,?)",
                            (data["place_label"], data.get("village"), data["district"], data["state"], data["pin"]))
            cur = c.execute("""INSERT INTO camps(org_id,location_id,title_hi,title_en,starts_at,ends_at,capacity,price_info,contact_public,verification,
                               publish_state,source,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,'unverified',?,?,?,?,?)""",
                            (org_id, loc.lastrowid, data["title_hi"] or data["title_en"], data["title_en"] or data["title_hi"], iso(start), iso(end), data.get("capacity"),
                             data.get("price_info"), data.get("contact_public"), pub, "admin" if actor["role"] == "admin" else "organiser", actor["id"], iso(), iso()))
            camp_id = cur.lastrowid
            if actor["role"] == "organiser":  # organisers manage their own camps without a separate assignment
                pass
        else:
            scope = camp_scope(actor)
            row = c.execute("SELECT * FROM camps WHERE id=?", (camp_id,)).fetchone()
            if row is None or (scope is not None and camp_id not in scope):
                raise err(404, "camp_not_found", "This camp was not found.")
            c.execute("""UPDATE locations SET label=?, village=?, district=?, state=?, pin=? WHERE id=?""",
                      (data["place_label"], data.get("village"), data["district"], data["state"], data["pin"], row["location_id"]))
            c.execute("""UPDATE camps SET title_hi=?, title_en=?, starts_at=?, ends_at=?, capacity=?, price_info=?, contact_public=?, publish_state=?, updated_at=? WHERE id=?""",
                      (data["title_hi"] or data["title_en"], data["title_en"] or data["title_hi"], iso(start), iso(end), data.get("capacity"), data.get("price_info"),
                       data.get("contact_public"), pub, iso(), camp_id))
    security.audit(actor, "camp.upsert", "camp", camp_id)
    return camp_dto(db.one(_CAMP_SQL + " WHERE c.id=?", (camp_id,)))


def set_verification(actor, camp_id: int, verification: str) -> dict:
    if actor["role"] != "admin":
        raise err(403, "forbidden", "Only an admin can verify a camp.")
    r = db.one("SELECT * FROM camps WHERE id=?", (camp_id,))
    if r is None:
        raise err(404, "camp_not_found", "This camp was not found.")
    if r["source"] == "demo_seed" and verification == "verified":
        raise err(409, "demo_cannot_verify", "Demonstration camps cannot be marked verified.")
    db.run("UPDATE camps SET verification=?, updated_at=? WHERE id=?", (verification, iso(), camp_id))
    security.audit(actor, "camp.verify", "camp", camp_id, verification)
    return camp_dto(db.one(_CAMP_SQL + " WHERE c.id=?", (camp_id,)))


def organiser_summary(actor) -> dict:
    camps = organiser_camps(actor)
    ids = [c["id"] for c in camps]
    by_pin: dict[str, int] = {}
    totals = {"interest_received": 0, "contacted": 0, "confirmed_by_organiser": 0, "attended": 0, "no_show": 0, "cancelled": 0}
    for r in db.all_("SELECT camp_id, pin, status FROM registrations"):
        if r["camp_id"] in ids:
            totals[r["status"]] += 1
            if r["status"] != "cancelled":
                by_pin[r["pin"]] = by_pin.get(r["pin"], 0) + 1
    cap = sum(c["planned_capacity"] or 0 for c in camps if c["state"] in ("open", "full"))
    return {"camps": len(camps), "open_camps": sum(c["state"] == "open" for c in camps), "interest_total": sum(c["interest_total"] for c in camps),
            "planned_capacity_open": cap, "status_totals": totals,
            "interest_by_pin": sorted(({"pin": k, "n": v} for k, v in by_pin.items()), key=lambda x: -x["n"])[:8],
            "is_demo_data": any(c["is_demo"] for c in camps)}


# ---- accounts ----------------------------------------------------------------------------------------------------
def user_dto(u) -> dict:
    return {"id": u["id"], "role": u["role"], "name": u["display_name"], "identifier_type": u["identifier_type"],
            "identifier_masked": security.mask(u["identifier_norm"]), "identifier_verified": bool(u["identifier_verified"]),
            "village": u["village"], "pin": u["pin"], "language": u["language"], "reminders_opt_in": bool(u["reminders_opt_in"]),
            "comm_pref": u["comm_pref"], "is_prototype": bool(u["is_prototype"]), "created_at": u["created_at"]}


def signup(data: dict) -> dict:
    ident = security.normalise_identifier(data["identifier"])
    if ident is None:
        raise err(422, "invalid_identifier", "Enter a 10-digit mobile number or an email address.")
    if not data.get("consent"):
        raise err(422, "consent_required", "Consent is needed to create an account.")
    weak = security.check_password_strength(data["password"])
    if weak:
        raise err(422, "weak_password", "Choose a password with at least 8 characters that is not too common.")
    if data.get("pin") and not PIN_RE.match(data["pin"]):
        raise err(422, "invalid_pin", "A PIN code has 6 digits.")
    if db.one("SELECT 1 FROM users WHERE identifier_norm=?", (ident[1],)):
        raise err(409, "signup_failed", "We could not create an account with these details. If you already have one, please log in.")
    t = iso()
    cur = db.run("""INSERT INTO users(role,display_name,identifier_type,identifier_norm,password_hash,village,pin,language,consent_version,consent_at,
                    reminders_opt_in,comm_pref,created_at) VALUES('user',?,?,?,?,?,?,?,?,?,?,?,?)""",
                 (data["name"].strip()[:80], ident[0], ident[1], security.hash_password(data["password"]), (data.get("village") or "").strip()[:60] or None,
                  data.get("pin") or None, data.get("language") or "hi", CONSENT_VERSION, t, int(bool(data.get("reminders_opt_in"))),
                  data.get("comm_pref") or "none", t))
    u = db.one("SELECT * FROM users WHERE id=?", (cur.lastrowid,))
    security.audit(u, "account.signup", "user", u["id"])
    return u


def login(identifier: str, password: str):
    ident = security.normalise_identifier(identifier)
    generic = err(401, "login_failed", "That contact or password is not right.")
    if ident is None:
        raise generic
    u = db.one("SELECT * FROM users WHERE identifier_norm=? AND deleted_at IS NULL", (ident[1],))
    if u is None:
        security.verify_password(security.hash_password("x"), password)  # similar timing
        raise generic
    if u["locked_until"] and datetime.fromisoformat(u["locked_until"]) > now():
        raise err(429, "account_locked", "Too many wrong attempts. Please try again in 15 minutes.")
    if not security.verify_password(u["password_hash"], password):
        fails = u["failed_logins"] + 1
        locked = iso(now() + timedelta(minutes=15)) if fails >= 5 else None
        db.run("UPDATE users SET failed_logins=?, locked_until=? WHERE id=?", (0 if locked else fails, locked, u["id"]))
        raise generic
    db.run("UPDATE users SET failed_logins=0, locked_until=NULL WHERE id=?", (u["id"],))
    security.audit(u, "account.login", "user", u["id"])
    return u


def update_profile(u, data: dict) -> dict:
    fields = {}
    if data.get("name") is not None:
        fields["display_name"] = data["name"].strip()[:80] or u["display_name"]
    if "village" in data and data["village"] is not None:
        fields["village"] = data["village"].strip()[:60] or None
    if "pin" in data and data["pin"] is not None:
        if data["pin"] and not PIN_RE.match(data["pin"]):
            raise err(422, "invalid_pin", "A PIN code has 6 digits.")
        fields["pin"] = data["pin"] or None
    if data.get("language"):
        fields["language"] = data["language"]
    if data.get("reminders_opt_in") is not None:
        fields["reminders_opt_in"] = int(data["reminders_opt_in"])
    if data.get("comm_pref"):
        fields["comm_pref"] = data["comm_pref"]
    if fields:
        db.run(f"UPDATE users SET {', '.join(k + '=?' for k in fields)} WHERE id=?", (*fields.values(), u["id"]))
    return user_dto(db.one("SELECT * FROM users WHERE id=?", (u["id"],)))


def export_data(u) -> dict:
    return {"profile": user_dto(u), "registrations": [reg_dto(r, with_contact=True) for r in db.all_("SELECT * FROM registrations WHERE user_id=?", (u["id"],))],
            "consent": {"version": u["consent_version"], "at": u["consent_at"]}}


def delete_account(u) -> None:
    """Hard-deletes the profile and sessions; the person's registrations are anonymised (name, contact and village removed) so
    organiser counts stay correct but nothing identifies them any more."""
    with db.tx() as c:
        c.execute("""UPDATE registrations SET display_name='Deleted', phone=NULL, email=NULL, village=NULL, dedupe_key=NULL, user_id=NULL, updated_at=?
                     WHERE user_id=?""", (iso(), u["id"]))
        c.execute("DELETE FROM sessions WHERE user_id=?", (u["id"],))
        c.execute("DELETE FROM users WHERE id=?", (u["id"],))
    security.audit(None, "account.delete", "user", u["id"])


def purge_expired() -> int:
    """Removes contact details from registrations past their retention date (aggregate rows stay)."""
    cur = db.run("""UPDATE registrations SET phone=NULL, email=NULL, village=NULL, display_name='Expired', dedupe_key=NULL
                    WHERE purge_after IS NOT NULL AND purge_after < ? AND display_name!='Expired'""", (iso(),))
    return cur.rowcount


# ---- registration <-> screening encounter links (made only by a signed-in clinician; see backend/app.py) ----------------
def _link_dto(link) -> dict:
    r = db.one("SELECT * FROM registrations WHERE id=?", (link["registration_id"],))
    camp = db.one(_CAMP_SQL + " WHERE c.id=?", (r["camp_id"],))
    return {"ref": r["public_ref"], "name": r["display_name"], "camp": {"en": camp["title_en"], "hi": camp["title_hi"]},
            "camp_is_demo": camp["source"] == "demo_seed", "linked_at": link["created_at"], "linked_by": link["linked_by_name"],
            "consent_confirmed_at": link["consent_confirmed_at"]}


def link_for_encounter(encounter_id: str) -> dict | None:
    link = db.one("SELECT * FROM screening_links WHERE encounter_id=? AND revoked_at IS NULL", (encounter_id,))
    return _link_dto(link) if link else None


def link_screening(clinician: dict, encounter_id: str, ref: str, code: str, consent_confirmed: bool) -> dict:
    """Explicit link from a receipt the patient presents. Never by name, phone or PIN."""
    actor = {"id": clinician["id"], "role": "ophthalmologist"}
    security.rate_limit(f"link:{clinician['id']}", 10, 600)
    if not consent_confirmed:
        raise err(422, "consent_required", "Confirm that the person agreed to link this screening to their registration.")
    r = verify_receipt(ref, code)
    if r["status"] in ("cancelled", "no_show"):
        raise err(409, "registration_closed", "This registration was cancelled or marked as not attended.")
    with db.tx() as c:
        if c.execute("SELECT 1 FROM screening_links WHERE registration_id=? AND revoked_at IS NULL", (r["id"],)).fetchone():
            raise err(409, "registration_already_linked", "This registration is already linked to a screening. Unlink it there first.")
        if c.execute("SELECT 1 FROM screening_links WHERE encounter_id=? AND revoked_at IS NULL", (encounter_id,)).fetchone():
            raise err(409, "encounter_already_linked", "This screening is already linked to a registration. Unlink it first.")
        c.execute("""INSERT INTO screening_links(registration_id,encounter_id,linked_by,linked_by_name,consent_confirmed_at,created_at)
                     VALUES(?,?,?,?,?,?)""", (r["id"], encounter_id, clinician["id"], clinician["name"], iso(), iso()))
    security.audit(actor, "screening.link", "registration", r["id"], f"encounter {encounter_id}")
    return link_for_encounter(encounter_id)


def unlink_screening(clinician: dict, encounter_id: str, reason: str) -> None:
    link = db.one("SELECT * FROM screening_links WHERE encounter_id=? AND revoked_at IS NULL", (encounter_id,))
    if link is None:
        raise err(404, "not_linked", "This screening is not linked to a registration.")
    db.run("UPDATE screening_links SET revoked_at=?, revoked_by=?, revoke_reason=? WHERE id=?", (iso(), clinician["id"], reason.strip()[:200], link["id"]))
    security.audit({"id": clinician["id"], "role": "ophthalmologist"}, "screening.unlink", "registration", link["registration_id"],
                   f"encounter {encounter_id}")
