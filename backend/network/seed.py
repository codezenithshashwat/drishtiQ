"""Demonstration data. Everything seeded here is flagged source=demo_seed / verification=simulated and the UI shows a
permanent DEMONSTRATION label. No real organisations, hospitals or phone numbers are used, and the dates are shifted
forward on every start so the demo never goes stale. Switched off with NETWORK_DEMO_MODE=0."""
from datetime import timedelta

from . import db, security

DEMO_ORG = "Demo Netra Seva Trust (simulated)"

# seed_key, title_hi, title_en, village, district, state, pin, offset_days, capacity, publish_state
CAMPS = [
    ("d1", "ग्राम नेत्र जाँच शिविर (नमूना)", "Village Eye Screening Camp (demo)", "Demo Gram Panchayat", "Indore", "Madhya Pradesh", "453331", 6, 80, "published"),
    ("d2", "मधुमेह एवं नेत्र जाँच दिवस (नमूना)", "Diabetes & Eye Check Day (demo)", "Demo Community Hall", "Indore", "Madhya Pradesh", "453331", 13, 60, "published"),
    ("d3", "नेत्र जाँच शिविर, डेमो ब्लॉक (नमूना)", "Eye Screening Camp, Demo Block (demo)", "Demo Block Centre", "Indore", "Madhya Pradesh", "453441", 9, 70, "published"),
    ("d4", "शहरी नेत्र जाँच शिविर (नमूना)", "City Eye Screening Camp (demo)", "Demo Ward Office", "Indore", "Madhya Pradesh", "452001", 4, 120, "published"),
    ("d5", "नेत्र जाँच शिविर, धार (नमूना)", "Eye Screening Camp, Dhar (demo)", "Demo Health Centre", "Dhar", "Madhya Pradesh", "454001", 16, 90, "published"),
    ("d6", "नेत्र जाँच शिविर, उज्जैन (नमूना)", "Eye Screening Camp, Ujjain (demo)", "Demo Temple Trust Hall", "Ujjain", "Madhya Pradesh", "456001", 24, None, "published"),
    ("d7", "पिछला नेत्र जाँच शिविर (नमूना)", "Past Eye Screening Camp (demo)", "Demo Gram Panchayat", "Indore", "Madhya Pradesh", "453331", -12, 80, "published"),
    ("d8", "बंद पंजीकरण शिविर (नमूना)", "Camp with closed interest list (demo)", "Demo Ward Office", "Indore", "Madhya Pradesh", "452001", 20, 40, "closed"),
]

DEMO_STAFF = [  # (role, name, identifier, password). Prototype accounts only; shown with a PROTOTYPE banner.
    ("health_worker", "Demo Health Worker", "9000000001", "Demo@Worker1"),
    ("organiser", "Demo Organiser", "9000000002", "Demo@Organiser1"),
    ("admin", "Demo Admin", "9000000003", "Demo@Admin1"),
]
DEMO_CLINICIAN = ("9000000004", "Dr. Demo Ophthalmologist (prototype)", "Demo@Eye-Doctor1")


def seed_demo() -> None:
    """Idempotent. Creates the demo organisation, camps and staff; refreshes demo camp dates relative to today."""
    now = security.now()
    org = db.one("SELECT id FROM organisations WHERE name=?", (DEMO_ORG,))
    if org is None:
        cur = db.run("INSERT INTO organisations(name,kind,verification,source,created_at) VALUES(?,?,?,?,?)",
                     (DEMO_ORG, "ngo", "simulated", "demo_seed", security.iso(now)))
        org_id = cur.lastrowid
    else:
        org_id = org["id"]
    for key, thi, ten, village, district, state, pin, off, cap, pub in CAMPS:
        start = (now + timedelta(days=off)).replace(hour=10, minute=0, second=0, microsecond=0)
        end = start.replace(hour=16)
        row = db.one("SELECT id, location_id FROM camps WHERE seed_key=?", (key,))
        if row is None:
            loc = db.run("INSERT INTO locations(label,village,district,state,pin) VALUES(?,?,?,?,?)", (village, village, district, state, pin))
            db.run("""INSERT INTO camps(seed_key,org_id,location_id,title_hi,title_en,starts_at,ends_at,capacity,price_info,contact_public,
                      verification,publish_state,source,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,NULL,NULL,'simulated',?, 'demo_seed',NULL,?,?)""",
                   (key, org_id, loc.lastrowid, thi, ten, security.iso(start), security.iso(end), cap, pub, security.iso(now), security.iso(now)))
        else:  # keep the demo current without touching its registrations
            db.run("UPDATE camps SET starts_at=?, ends_at=?, updated_at=? WHERE id=?", (security.iso(start), security.iso(end), security.iso(now), row["id"]))
    for role, name, ident, pw in DEMO_STAFF:
        if db.one("SELECT id FROM users WHERE identifier_norm=?", (ident,)) is None:
            db.run("""INSERT INTO users(role,display_name,identifier_type,identifier_norm,password_hash,language,org_id,is_prototype,created_at)
                      VALUES(?,?,?,?,?,'en',?,1,?)""",
                   (role, name, "mobile", ident, security.hash_password(pw), org_id if role in ("organiser", "admin", "health_worker") else None,
                    security.iso(now)))
    # Demo ophthalmologist: an ordinary account plus a clinician grant marked as demo-seeded (prototype only).
    ident, name, pw = DEMO_CLINICIAN
    if db.one("SELECT id FROM users WHERE identifier_norm=?", (ident,)) is None:
        db.run("""INSERT INTO users(role,display_name,identifier_type,identifier_norm,password_hash,language,is_prototype,created_at)
                  VALUES('user',?,'mobile',?,?,'en',1,?)""", (name, ident, security.hash_password(pw), security.iso(now)))
    uid = db.one("SELECT id FROM users WHERE identifier_norm=?", (ident,))["id"]
    if db.one("SELECT id FROM clinician_roles WHERE user_id=?", (uid,)) is None:  # never re-grant a revoked demo grant
        db.run("INSERT INTO clinician_roles(user_id,role,granted_by,granted_at) VALUES(?,'ophthalmologist','demo_seed',?)", (uid, security.iso(now)))
    worker = db.one("SELECT id FROM users WHERE identifier_norm='9000000001'")
    for c in db.all_("SELECT id FROM camps WHERE seed_key IN ('d1','d2','d3','d4')"):
        db.run("INSERT OR IGNORE INTO worker_assignments(user_id,camp_id) VALUES(?,?)", (worker["id"], c["id"]))
