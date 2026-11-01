"""DrishtiQ V3 P0 safety tests: clinical access control, clinician-authoritative decisions, encounters (OD/OS), the
registration-to-screening link, the patient-facing status, reports and migrations.

Synthetic data only: analyses are hand-built records (no images, no model inference), both databases live in a temp
directory, and the app's lifespan (which would load the models) is not run.  Run:
    .venv\\Scripts\\python -m pytest backend/test_clinical_p0.py -q
"""
import json
import sqlite3
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend import app as appmod, clinical_auth, clinical_state, store
from backend.network import db as ndb, security, seed

H = {"X-Requested-With": "dqn"}
CLINICIAN = ("9000000004", "Demo@Eye-Doctor1")
SIG = "sig-v1"


def fake(grade=1, usable=True, dme="low", status="ok"):
    """A minimal analysis record with the fields routing, assist, the worklist and the reports read."""
    a = dict(status=status, model_version="test-model", quality=dict(usable=usable, issues=[] if usable else ["The photo is too blurred."],
                                                                      fov_fraction=0.9, brightness=0.5, sharpness=0.5),
             lesions=[], consistency_flags=[], explanations=[])
    if status == "ok":
        a["grading"] = dict(grade=grade, label=f"stage {grade}", low_confidence=False, score=float(grade))
        a["findings"] = dict(macular_edema_risk=dict(level=dme, reason="", nearest_exudate_dd=None, exudates_within_1dd=0, landmarks_uncertain=False),
                             lesions={k: dict(name=k, count=0, area_px=0, per_quadrant={}, regions=[]) for k in ("MA", "HE", "EX", "SE")},
                             landmarks=dict(optic_disc=None, fovea=None, disc_diameter_px=0))
    return a


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("p0")
    old = store.DIR, store.IMAGES
    store.DIR, store.IMAGES = tmp, tmp / "images"
    ndb.connect(tmp / "network.sqlite")
    seed.seed_demo()
    st = appmod.state
    saved = dict(st)
    st.clear()
    st.update(db=store.connect(), signature=SIG, calibration=None, routing_valid=False,
              pipeline=SimpleNamespace(grader_spec="finetune:test.pt", model_version="test-model", checkpoints={}, system=None, device="cpu"))
    yield SimpleNamespace(tmp=tmp, db=st["db"])
    st.clear()
    st.update(saved)
    ndb.close()
    store.DIR, store.IMAGES = old


def client():
    security.reset_rate_limits()
    return TestClient(appmod.app)  # no `with`: the lifespan (model loading) is not run


def login(c, ident=CLINICIAN[0], pw=CLINICIAN[1]):
    r = c.post("/api/network/auth/login", json={"identifier": ident, "password": pw}, headers=H)
    assert r.status_code == 200, r.text
    return r.json()["user"]


@pytest.fixture()
def doc(env):
    c = client()
    login(c)
    return c


def enc(env, ref, *eyes, grades=None, usable=None):
    """An encounter with one photo per given eye. Returns (encounter_id, {eye: case_id})."""
    e = store.create_encounter(env.db, ref)
    ids = {}
    for i, eye in enumerate(eyes):
        a = fake(grade=(grades or {}).get(eye, 1), usable=(usable or {}).get(eye, True))
        ids[eye] = store.add_case(env.db, ref, eye, "upload", b"img", "jpg", a, SIG, encounter_id=e["id"])
    return e["id"], ids


def sign(c, cid, decision="agree", next_action="routine_rescreen", stage=None, note="", dme=None):
    return c.post(f"/api/cases/{cid}/review", json={"decision": decision, "corrected_stage": stage, "corrected_dme": dme, "next_action": next_action,
                                                   "note": note, "reviewer": "Somebody Else"}, headers=H)


# ---- access control ---------------------------------------------------------------------------------------------
def test_every_clinical_route_requires_a_clinician():
    for r in appmod.app.routes:
        if not isinstance(r, APIRoute) or not r.path.startswith("/api") or r.path.startswith("/api/network") or r.path in appmod.PUBLIC_API \
                or r.path == "/api/{path:path}":
            continue
        assert clinical_auth.need_clinician in [d.call for d in r.dependant.dependencies], f"{r.path} is reachable without a clinician"


def test_unauthenticated_patient_and_staff_are_refused(env):
    eid, ids = enc(env, "ACL-1", "right")
    anon = client()
    for method, path in [("get", "/api/cases"), ("get", f"/api/cases/{ids['right']}"), ("get", f"/api/encounters/{eid}"), ("get", "/api/feedback.csv"),
                         ("get", "/api/patients/ACL-1/report.html"), ("get", "/api/patients/ACL-1/report.pdf"), ("get", "/api/settings"),
                         ("get", "/api/disagreements"), ("get", "/api/clinician/me")]:
        assert getattr(anon, method)(path).status_code == 401, path
    assert anon.post(f"/api/cases/{ids['right']}/review", json={"decision": "agree", "next_action": "routine_rescreen"}, headers=H).status_code == 401
    assert anon.post("/api/settings", json={"target": 0.05}, headers=H).status_code == 401
    patient = client()
    r = patient.post("/api/network/auth/signup", json={"name": "Asha", "identifier": "9811111111", "password": "Secret@12345", "consent": True}, headers=H)
    assert r.status_code == 200
    assert patient.get("/api/cases").status_code == 403 and patient.get(f"/api/cases/{ids['right']}").status_code == 403
    for ident, pw in [("9000000001", "Demo@Worker1"), ("9000000002", "Demo@Organiser1"), ("9000000003", "Demo@Admin1")]:
        staff = client()
        login(staff, ident, pw)
        assert staff.get("/api/cases").status_code == 403, ident                     # Network staff roles are not clinicians
    for public in ("/api/health", "/api/glossary"):
        assert anon.get(public).status_code != 401


def test_csrf_and_reviewer_identity_come_from_the_session(env, doc):
    _, ids = enc(env, "ID-1", "right")
    no_header = doc.post(f"/api/cases/{ids['right']}/review", json={"decision": "agree", "next_action": "routine_rescreen"})
    assert no_header.status_code == 403
    r = sign(doc, ids["right"])
    assert r.status_code == 200, r.text
    rv = r.json()["reviews"][0]
    assert rv["reviewer"] == "Dr. Demo Ophthalmologist (prototype)" and rv["reviewer_user_id"] and rv["authenticated"]  # not "Somebody Else"


def test_revoking_access_takes_effect_immediately(env):
    c = client()
    me = login(c)
    assert c.get("/api/cases").status_code == 200
    assert clinical_auth.revoke(me["id"], "test")
    assert c.get("/api/cases").status_code == 403
    assert clinical_auth.grant(me["id"], "test")
    assert c.get("/api/cases").status_code == 200
    assert ndb.one("SELECT COUNT(*) n FROM clinician_roles WHERE user_id=?", (me["id"],))["n"] == 2   # history kept


def test_clinician_sessions_expire_when_idle(env):
    c = client()
    login(c)
    assert c.get("/api/cases").status_code == 200
    old = security.iso(security.now() - timedelta(minutes=31))
    ndb.run("UPDATE sessions SET last_seen=? WHERE user_id=(SELECT id FROM users WHERE identifier_norm=?)", (old, CLINICIAN[0]))
    r = c.get("/api/cases")
    assert r.status_code == 401 and r.json()["detail"]["code"] == "session_expired"


# ---- clinician-authoritative decisions -------------------------------------------------------------------------
def test_signed_decision_governs_worklist_case_summary_and_reports(env, doc):
    eid, ids = enc(env, "AUTH-1", "right", "left", grades={"right": 1, "left": 1})
    r = sign(doc, ids["right"], decision="disagree", stage=3, next_action="urgent_referral", note="IRMA seen")
    assert r.status_code == 200, r.text
    case = r.json()
    eff = case["effective"]
    assert eff["source"] == "clinician" and eff["stage"] == 3 and eff["next_action"] == "urgent_referral"
    assert eff["ai_at_signing"]["stage"] == 1 and case["analysis"]["grading"]["grade"] == 1      # the AI prediction is preserved
    rows = {x["id"]: x for x in doc.get("/api/cases").json()["cases"]}
    assert rows[ids["right"]]["queue"] == "signed" and rows[ids["left"]]["queue"] != "signed"
    s = doc.get(f"/api/cases/{ids['left']}").json()["patient"]
    assert s["effective"]["state"] == "decision_recorded" and s["effective"]["next_action"] == "urgent_referral"   # left unsigned: not held back
    assert s["effective"]["pending_eyes"] == ["left"] and s["follow_up"]["level"] == "urgent"
    doctor = doc.get(f"/api/patients/AUTH-1/report.html?kind=doctor&lang=en&case={ids['right']}").text
    assert "Urgent referral to an eye specialist" in doctor and "Not yet signed" in doctor
    patient = doc.get(f"/api/patients/AUTH-1/report.html?kind=patient&lang=en&case={ids['right']}").text
    from backend.report_text import PATIENT
    assert PATIENT["en"]["follow_up"]["urgent"] in patient and PATIENT["en"]["eye_pending"] in patient
    assert PATIENT["en"]["stage"][1][0] not in patient                                     # the unsigned AI stage is not shown to the patient


def test_reanalysis_after_signing_never_changes_the_decision(env, doc):
    _, ids = enc(env, "REAN-1", "right", "left")
    assert sign(doc, ids["right"], decision="agree", next_action="referral").status_code == 200
    store.update_analysis(env.db, ids["right"], fake(grade=0), "sig-v2")                # newer model, lower AI stage
    eff = doc.get(f"/api/cases/{ids['right']}").json()["effective"]
    assert eff["next_action"] == "referral" and eff["stage"] == 1 and eff["reanalysed_since_signing"] is True


def test_decision_rules(env, doc):
    _, ids = enc(env, "RULES-1", "right", grades={"right": 3})
    assert sign(doc, ids["right"], decision="disagree", next_action="referral").status_code == 422             # no corrected stage
    assert sign(doc, ids["right"], next_action=None).status_code == 422                                          # no next action
    assert sign(doc, ids["right"], next_action="discharge").status_code == 422                                   # not an allowed action
    assert sign(doc, ids["right"], decision="ungradable", next_action="routine_rescreen").status_code == 422    # unassessable != healthy
    assert sign(doc, ids["right"], decision="agree", next_action="routine_rescreen").status_code == 422         # stage 3 routine needs a note
    assert sign(doc, ids["right"], decision="agree", next_action="routine_rescreen", note="Old laser scars, stable for 5 years").status_code == 200
    assert sign(doc, ids["right"], decision="disagree", stage=0, next_action="urgent_referral").status_code == 200  # more cautious: no note needed
    _, rej = enc(env, "RULES-2", "left")
    store.update_analysis(env.db, rej["left"], fake(status="rejected", usable=False), SIG)
    assert sign(doc, rej["left"], decision="agree", next_action="recapture").status_code == 422                 # nothing to confirm


def test_reviews_are_append_only(env, doc):
    _, ids = enc(env, "APPEND-1", "right")
    sign(doc, ids["right"], next_action="follow_up")
    sign(doc, ids["right"], decision="disagree", stage=2, next_action="referral")
    revs = store.reviews(env.db, ids["right"])
    assert [r["next_action"] for r in revs] == ["referral", "follow_up"]                   # amendment = new row; both kept
    for sql in ("UPDATE reviews SET next_action='routine_rescreen'", "DELETE FROM reviews"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            env.db.execute(sql)
    env.db.rollback()


def test_historical_reviews_stay_visible_but_are_not_authoritative(env, doc):
    _, ids = enc(env, "LEGACY-1", "right", "left")
    store.add_review(env.db, ids["right"], "Dr Typed Name", "agree", None, None, "", 1, "old-grader")   # pre-V3 style: no identity
    c = doc.get(f"/api/cases/{ids['right']}").json()
    assert c["reviews"][0]["authenticated"] is False and c["effective"]["source"] == "ai_provisional" and c["effective"]["legacy_reviews"] == 1
    row = next(x for x in doc.get("/api/cases").json()["cases"] if x["id"] == ids["right"])
    assert row["queue"] == "awaiting" and "historical" in row["queue_reason"]
    assert c["patient"]["effective"]["state"] == "awaiting_review" and c["patient"]["follow_up"]["level"] == "pending"


# ---- encounters and the visit outcome ---------------------------------------------------------------------------
def test_visit_outcome_states(env, doc):
    eid, ids = enc(env, "VISIT-1", "right")
    assert clinical_state.aggregate(clinical_state.encounter_eyes(env.db, eid))["state"] == "incomplete"     # left missing
    eid2, ids2 = enc(env, "VISIT-2", "right", "left", usable={"left": False})
    assert clinical_state.aggregate(clinical_state.encounter_eyes(env.db, eid2))["state"] == "quality_check"
    eid3, ids3 = enc(env, "VISIT-3", "right", "left")
    sign(doc, ids3["right"], next_action="routine_rescreen")
    out = clinical_state.aggregate(clinical_state.encounter_eyes(env.db, eid3))
    assert out["state"] == "awaiting_review" and out["partial"]                            # one eye routine is not a routine visit
    sign(doc, ids3["left"], next_action="routine_rescreen")
    out = clinical_state.aggregate(clinical_state.encounter_eyes(env.db, eid3))
    assert out["state"] == "decision_recorded" and out["next_action"] == "routine_rescreen"
    sign(doc, ids[ "right"], decision="disagree", stage=4, next_action="urgent_referral")
    out = clinical_state.aggregate(clinical_state.encounter_eyes(env.db, eid))
    assert out["next_action"] == "urgent_referral" and out["missing_eyes"] == ["left"]        # urgent shown, incompleteness still visible
    assert clinical_state.aggregate([])["state"] == "in_progress"


def test_retakes_within_an_encounter(env, doc):
    eid, ids = enc(env, "RETAKE-1", "right", "left")
    sign(doc, ids["right"], decision="disagree", stage=3, next_action="urgent_referral")
    newer = store.add_case(env.db, "RETAKE-1", "right", "upload", b"img", "jpg", fake(), SIG, encounter_id=eid)
    right = next(e for e in clinical_state.encounter_eyes(env.db, eid) if e["eye"] == "right")
    assert right["next_action"] == "urgent_referral" and right["pending"] and right["newer_photo_case_id"] == newer   # urgent stands
    eid2, ids2 = enc(env, "RETAKE-2", "right", "left")
    sign(doc, ids2["left"], decision="ungradable", next_action="recapture")
    assert clinical_state.aggregate(clinical_state.encounter_eyes(env.db, eid2))["next_action"] == "recapture"
    store.add_case(env.db, "RETAKE-2", "left", "upload", b"img", "jpg", fake(), SIG, encounter_id=eid2)
    out = clinical_state.aggregate(clinical_state.encounter_eyes(env.db, eid2))
    assert out["state"] == "awaiting_review" and out["next_action"] is None                 # the requested retake was taken


def test_encounter_identity_rules(env, doc):
    e = doc.post("/api/encounters", json={"patient_ref": "ENC-1", "client_key": "k-123"}, headers=H).json()
    again = doc.post("/api/encounters", json={"patient_ref": "ENC-1", "client_key": "k-123"}, headers=H).json()
    assert e["id"] == again["id"] and e["id"].startswith("ENC-")                            # no duplicate on a double submit
    assert doc.post("/api/encounters", json={"patient_ref": "OTHER", "client_key": "k-123"}, headers=H).status_code == 409
    up = lambda **d: doc.post("/api/cases", files={"file": ("f.jpg", b"not checked", "image/jpeg")}, data=d, headers=H)
    assert up(patient_ref="SOMEONE-ELSE", eye="right", encounter_id=e["id"]).status_code == 422
    assert up(patient_ref="ENC-1", eye="unknown", encounter_id=e["id"]).status_code == 422
    assert up(patient_ref="ENC-1", eye="right", encounter_id="ENC-NOPE").status_code == 422
    single = store.add_case(env.db, "ENC-1", "left", "upload", b"img", "jpg", fake(), SIG)            # old-style photo, no encounter
    p = doc.get(f"/api/cases/{single}").json()
    assert p["encounter"] is None and p["patient"]["single_photo"] and [x["case_id"] for x in p["patient"]["eyes"]] == [single]


def test_reports_never_mix_visits(env, doc):
    _, first = enc(env, "MIX-1", "right")
    _, second = enc(env, "MIX-1", "left")
    html = doc.get("/api/patients/MIX-1/report.html?kind=doctor").text                     # latest visit only
    assert second["left"] in html and first["right"] not in html
    assert doc.get(f"/api/patients/MIX-1/report.html?kind=doctor&case={first['right']}").text.count(first["right"]) >= 1
    _, other = enc(env, "MIX-2", "right")
    assert doc.get(f"/api/patients/MIX-1/report.html?case={other['right']}").status_code == 404


# ---- registration <-> screening link and the public status -------------------------------------------------------
def registration(c, name="Kamla"):
    r = c.post("/api/network/registrations", json={"camp_id": 1, "name": name, "pin": "453331", "consent": True}, headers=H).json()
    return r["registration"]["ref"], r["receipt_code"]


def test_linking_and_public_status(env, doc):
    guest = client()
    ref, code = registration(guest)
    look = lambda: guest.post("/api/network/registrations/lookup", json={"ref": ref, "code": code}, headers=H).json()
    assert look()["screening"] == {"state": "not_linked"}
    eid, ids = enc(env, "LINK-1", "right")
    link = lambda **kw: doc.post(f"/api/encounters/{eid}/link", json={"ref": ref, "code": code, "consent_confirmed": True, **kw}, headers=H)
    assert link(consent_confirmed=False).status_code == 422
    assert link(code="AAAA-AAAA").status_code == 404
    r = link()
    assert r.status_code == 200 and r.json()["link"]["ref"] == ref
    s = look()["screening"]
    assert s["state"] == "incomplete" and s["missing_eyes"] == ["left"] and s["next_action"] is None
    sign(doc, ids["right"], decision="disagree", stage=2, next_action="referral")
    s = look()["screening"]
    assert s["state"] == "decision_recorded" and s["next_action"] == "referral"
    assert set(s) <= {"state", "next_action", "missing_eyes", "quality_provisional", "eyes_awaiting_review", "decided_at"}
    blob = json.dumps(look())
    for secret in (ids["right"], eid, "stage", "Dr. Demo", "grade", "p_referable", "analysis"):
        assert secret not in blob, secret                                                   # nothing clinical leaks
    eid2, _ = enc(env, "LINK-2", "right")
    assert doc.post(f"/api/encounters/{eid2}/link", json={"ref": ref, "code": code, "consent_confirmed": True}, headers=H).status_code == 409
    ref2, code2 = registration(guest, "Ramesh")
    assert doc.post(f"/api/encounters/{eid}/link", json={"ref": ref2, "code": code2, "consent_confirmed": True}, headers=H).status_code == 409
    patient = client()
    patient.post("/api/network/auth/signup", json={"name": "Nisha", "identifier": "9822222222", "password": "Secret@12345", "consent": True}, headers=H)
    assert patient.post(f"/api/encounters/{eid}/link", json={"ref": ref2, "code": code2, "consent_confirmed": True}, headers=H).status_code == 403
    assert doc.post(f"/api/encounters/{eid}/unlink", json={"reason": "wrong person"}, headers=H).status_code == 200
    assert look()["screening"] == {"state": "not_linked"}
    actions = [r["action"] for r in ndb.all_("SELECT action FROM audit_log WHERE action LIKE 'screening.%'")]
    assert actions[-2:] == ["screening.link", "screening.unlink"]


def test_receipt_lookup_resists_enumeration(env):
    guest = client()
    ref, code = registration(guest, "Enum Test")
    for _ in range(security.RECEIPT_MAX_FAILS):
        assert guest.post("/api/network/registrations/lookup", json={"ref": ref, "code": "ZZZZ-ZZZZ"}, headers=H).status_code == 404
    locked = guest.post("/api/network/registrations/lookup", json={"ref": ref, "code": code}, headers=H)
    assert locked.status_code == 429                                                        # even the right code, for a while
    security.reset_receipt_locks()
    assert guest.post("/api/network/registrations/lookup", json={"ref": ref, "code": code}, headers=H).status_code == 200


# ---- migrations ------------------------------------------------------------------------------------------------
OLD_CASES = """
CREATE TABLE cases (id TEXT PRIMARY KEY, created TEXT NOT NULL, patient_ref TEXT NOT NULL, eye TEXT NOT NULL, source TEXT NOT NULL,
  image_ext TEXT NOT NULL, analysis TEXT NOT NULL, analysed_with TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new',
  vision_problems INTEGER NOT NULL DEFAULT 0, prior_treatment INTEGER NOT NULL DEFAULT 0);
CREATE TABLE reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL REFERENCES cases(id), created TEXT NOT NULL,
  reviewer TEXT NOT NULL, decision TEXT NOT NULL, corrected_stage INTEGER, corrected_dme TEXT, note TEXT NOT NULL DEFAULT '', ai_stage INTEGER, ai_grader TEXT);
"""


def test_clinical_store_migration_is_additive_and_backed_up(tmp_path, monkeypatch):
    path = tmp_path / "cases.sqlite"
    old = sqlite3.connect(path)
    old.executescript(OLD_CASES)
    old.execute("INSERT INTO cases VALUES('RS-1001','2026-10-01T10:00:00','P1','left','upload','jpg','{}','x','reviewed',0,0)")
    old.execute("INSERT INTO reviews(case_id,created,reviewer,decision,ai_stage) VALUES('RS-1001','2026-10-01T11:00:00','Dr Old','agree',1)")
    old.commit()
    old.close()
    monkeypatch.setattr(store, "DIR", tmp_path)
    monkeypatch.setattr(store, "IMAGES", tmp_path / "images")
    db = store.connect()
    backups = list(tmp_path.glob("cases.sqlite.pre-v3-*.bak"))
    assert len(backups) == 1
    b = sqlite3.connect(backups[0])
    assert b.execute("SELECT reviewer FROM reviews").fetchone()[0] == "Dr Old" and b.execute("PRAGMA user_version").fetchone()[0] == 0
    assert db.execute("PRAGMA user_version").fetchone()[0] == store.SCHEMA_VERSION
    rv = dict(db.execute("SELECT * FROM reviews").fetchone())
    assert rv["reviewer"] == "Dr Old" and rv["reviewer_user_id"] is None and "next_action" in rv     # preserved, not re-attributed
    assert db.execute("SELECT encounter_id FROM cases").fetchone()[0] is None
    db.close()
    store.connect().close()                                                                 # second start: no new backup
    assert len(list(tmp_path.glob("cases.sqlite.pre-v3-*.bak"))) == 1


def test_network_migration_preserves_accounts_and_registrations(tmp_path):
    path = tmp_path / "network.sqlite"
    old = sqlite3.connect(path)
    old.executescript(ndb.SCHEMA)                                                           # the pre-V3 schema
    old.execute("INSERT INTO users(role,display_name,identifier_type,identifier_norm,password_hash,created_at) VALUES('organiser','O','mobile','9333333333','h','t')")
    old.execute("INSERT INTO sessions(id_hash,user_id,created_at,expires_at,last_seen) VALUES('s',1,'t','2999-01-01','t')")
    old.commit()
    old.close()
    try:
        c = ndb.connect(path)
        assert len(list(tmp_path.glob("network.sqlite.pre-v3-*.bak"))) == 1
        assert c.execute("SELECT role FROM users").fetchone()[0] == "organiser"            # users.role untouched
        assert c.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM clinician_roles").fetchone()[0] == 0         # nobody gains clinical access
        assert "role IN('user','health_worker','organiser','admin')" in c.execute("SELECT sql FROM sqlite_master WHERE name='users'").fetchone()[0]
    finally:
        ndb.close()
