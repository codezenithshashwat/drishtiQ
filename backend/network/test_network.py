"""DrishtiQ Network tests. They build a small FastAPI app containing only the Network router and a throwaway database,
so no models are loaded and no real data is touched.   Run:  .venv/Scripts/python -m pytest -q backend/network"""
import re
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.network import db, security, seed, services  # noqa: E402
from backend.network.router import router  # noqa: E402
from backend.network.saathi import gemini, guardrails, nlu  # noqa: E402

H = {"X-Requested-With": "dqn"}


@pytest.fixture(scope="module")
def tmp_db(tmp_path_factory):
    db.connect(tmp_path_factory.mktemp("net") / "network.sqlite")
    seed.seed_demo()
    yield
    db.close()


@pytest.fixture()
def client(tmp_db):
    security.reset_rate_limits()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def code(r):
    return r.json()["detail"]["code"]


def reg(c, camp_id=1, **kw):
    body = {"camp_id": camp_id, "name": "Ram", "pin": "453331", "consent": True, **kw}
    return c.post("/api/network/registrations", json=body, headers=H)


def open_camp_ids(c):
    return [x["id"] for x in c.get("/api/network/camps?pin=453331").json()["items"] if x["state"] == "open"]


# ---- camps -------------------------------------------------------------------------------------------------------
def test_search_exact_pin_and_labels(client):
    items = client.get("/api/network/camps?pin=453331").json()["items"]
    assert items and all(i["place"]["pin"] == "453331" for i in items if i["match"] == "exact")
    assert all(i["verification"] == "simulated" and i["is_demo"] for i in items)           # never presented as real
    assert all(i["price"] is None and i["contact"] is None for i in items)                  # only verified camps show these


def test_search_hides_expired_unless_asked(client):
    default = client.get("/api/network/camps?pin=453331").json()["items"]
    assert all(i["state"] != "expired" for i in default)
    past = client.get("/api/network/camps?pin=453331&include_expired=true").json()["items"]
    assert any(i["state"] == "expired" for i in past)


def test_search_invalid_and_empty(client):
    r = client.get("/api/network/camps?pin=12")
    assert r.status_code == 422 and code(r) == "invalid_pin"
    assert client.get("/api/network/camps?pin=999999").json()["items"] == []                # nothing invented
    assert client.get("/api/network/camps?q=nowhere-xyz").json()["items"] == []


def test_nearby_region_is_labelled(client):
    d = client.get("/api/network/camps?pin=453999").json()
    assert d["exact"] == 0 and d["nearby"] > 0 and all(i["match"] == "nearby" for i in d["items"])


def test_unknown_camp(client):
    assert code(client.get("/api/network/camps/99999")) == "camp_not_found"


# ---- registrations -----------------------------------------------------------------------------------------------
def test_guest_registration_and_lookup(client):
    cid = open_camp_ids(client)[0]
    r = reg(client, cid, phone="9811111111", contact_consent=True, idempotency_key="a1")
    assert r.status_code == 200
    j = r.json()
    assert j["registration"]["status"] == "interest_received" and j["receipt_code"] and j["duplicate"] is False
    ref, rc = j["registration"]["ref"], j["receipt_code"]
    ok = client.post("/api/network/registrations/lookup", json={"ref": ref, "code": rc}, headers=H)
    assert ok.status_code == 200 and ok.json()["status"] == "interest_received"
    bad = client.post("/api/network/registrations/lookup", json={"ref": ref, "code": "AAAA-AAAA"}, headers=H)
    assert bad.status_code == 404                                                           # wrong code reveals nothing


def test_idempotent_replay_and_duplicate(client):
    cid = open_camp_ids(client)[1]
    a = reg(client, cid, idempotency_key="k-same").json()
    b = reg(client, cid, idempotency_key="k-same").json()
    assert a["registration"]["ref"] == b["registration"]["ref"] and b["replayed"] and b["receipt_code"] == a["receipt_code"]
    first = reg(client, cid, phone="9822222222").json()
    again = reg(client, cid, phone="9822222222").json()
    assert again["duplicate"] is True and again["receipt_code"] is None                     # a stranger gets no receipt back
    assert again["registration"]["ref"] == first["registration"]["ref"]


def test_registration_guards(client):
    cid = open_camp_ids(client)[0]
    assert code(reg(client, cid, consent=False)) == "consent_required"
    assert reg(client, cid, pin="12").status_code == 422
    assert code(reg(client, cid, phone="123")) == "invalid_phone"
    assert code(reg(client, 99999)) == "camp_not_found"
    by_key = {c["seed_key"]: c["id"] for c in map(dict, db.all_("SELECT id, seed_key FROM camps"))}
    assert code(reg(client, by_key["d7"])) == "camp_expired"                               # past camp
    assert code(reg(client, by_key["d8"])) == "camp_closed"                                # closed interest list


def test_csrf_guard(client):
    r = client.post("/api/network/registrations", json={"camp_id": 1, "name": "x", "pin": "453331", "consent": True})
    assert r.status_code == 403 and code(r) == "csrf"
    r = client.post("/api/network/registrations", json={"camp_id": 1, "name": "x", "pin": "453331", "consent": True}, headers={**H, "Origin": "https://evil.example"})
    assert r.status_code == 403


def test_capacity_marks_camp_full(tmp_db, client):
    r = services.upsert_camp(dict(db.one("SELECT * FROM users WHERE identifier_norm='9000000002'")),
                             {"title_en": "Tiny", "title_hi": "", "place_label": "Hall", "village": None, "district": "Indore", "state": "MP", "pin": "460001",
                              "starts_at": (security.now().replace(microsecond=0) + __import__("datetime").timedelta(days=3)).isoformat(),
                              "ends_at": (security.now().replace(microsecond=0) + __import__("datetime").timedelta(days=3, hours=4)).isoformat(),
                              "capacity": 1, "price_info": None, "contact_public": None, "publish_state": "published"})
    assert r["verification"] == "unverified"                                                # organisers cannot self-verify
    assert reg(client, r["id"], idempotency_key="cap1").status_code == 200
    assert code(reg(client, r["id"], name="Sita", idempotency_key="cap2")) == "camp_full"


# ---- accounts ----------------------------------------------------------------------------------------------------
def signup(c, ident="9876543210", pw="Sita@12345", name="Sita"):
    return c.post("/api/network/auth/signup", json={"name": name, "identifier": ident, "password": pw, "pin": "453331", "consent": True}, headers=H)


def test_signup_login_session_profile(client):
    r = signup(client)
    assert r.status_code == 200 and "dqn_session" in client.cookies
    u = r.json()["user"]
    assert u["identifier_verified"] is False and u["identifier_masked"].endswith("3210") and "9876543210" not in str(r.json())
    assert client.get("/api/network/me").json()["user"]["name"] == "Sita"
    p = client.patch("/api/network/me", json={"language": "en", "village": "Demo"}, headers=H).json()["user"]
    assert p["language"] == "en" and p["village"] == "Demo"
    client.post("/api/network/auth/logout", headers=H)
    assert client.get("/api/network/me").json()["user"] is None
    assert client.post("/api/network/auth/login", json={"identifier": "98765 43210", "password": "Sita@12345"}, headers=H).status_code == 200


def test_signup_validation_and_hashing(client):
    assert code(signup(client, ident="12345", pw="Strong@123")) == "invalid_identifier"
    assert signup(client, ident="9812345678", pw="password").status_code in (409, 422)
    row = db.one("SELECT password_hash FROM users WHERE identifier_norm='9876543210'")
    assert row["password_hash"].startswith("$argon2id$")
    assert code(signup(TestClient(client.app), ident="9876543210", pw="Another@123")) == "signup_failed"     # no enumeration detail


def test_login_lockout_and_generic_errors(client):
    signup(client, ident="9700000001", pw="Right@12345")
    c2 = TestClient(client.app)
    for _ in range(5):
        r = c2.post("/api/network/auth/login", json={"identifier": "9700000001", "password": "wrong-password"}, headers=H)
        assert code(r) == "login_failed"
    locked = c2.post("/api/network/auth/login", json={"identifier": "9700000001", "password": "Right@12345"}, headers=H)
    assert locked.status_code == 429 and code(locked) == "account_locked"
    assert code(c2.post("/api/network/auth/login", json={"identifier": "9111111111", "password": "x" * 9}, headers=H)) == "login_failed"


def test_users_cannot_see_each_others_data(client):
    cid = open_camp_ids(client)[0]
    a, b = TestClient(client.app), TestClient(client.app)
    signup(a, ident="9600000001", pw="Alice@12345", name="Alice")
    signup(b, ident="9600000002", pw="Bobby@12345", name="Bob")
    ra = a.post("/api/network/registrations", json={"camp_id": cid, "name": "Alice", "pin": "453331", "consent": True}, headers=H).json()
    assert len(a.get("/api/network/me/registrations").json()["items"]) == 1
    assert b.get("/api/network/me/registrations").json()["items"] == []
    rid = db.one("SELECT id FROM registrations WHERE public_ref=?", (ra["registration"]["ref"],))["id"]
    assert b.post(f"/api/network/me/registrations/{rid}/cancel", headers=H).status_code == 403   # IDOR blocked
    assert a.post(f"/api/network/me/registrations/{rid}/cancel", headers=H).json()["status"] == "cancelled"
    assert b.get("/api/network/me/export").json()["registrations"] == []
    assert client.get("/api/network/worker/requests").status_code == 401                          # guests have no staff access
    assert a.get("/api/network/worker/requests").status_code == 403                               # nor do ordinary users
    assert a.get("/api/network/organiser/summary").status_code == 403


def test_claimed_guest_registration_counts_as_the_users_interest(client):
    cid = open_camp_ids(client)[0]
    c = TestClient(client.app)
    signup(c, ident="9300000001", pw="Claim@12345", name="Claimer")
    guest = TestClient(client.app)
    g = reg(guest, cid, name="Claimer").json()                                             # guest, no contact details, so no contact-based key
    ok = c.post("/api/network/me/registrations/claim", json={"ref": g["registration"]["ref"], "code": g["receipt_code"]}, headers=H)
    assert ok.status_code == 200 and len(c.get("/api/network/me/registrations").json()["items"]) == 1
    again = c.post("/api/network/registrations", json={"camp_id": cid, "name": "Claimer", "pin": "453331", "consent": True}, headers=H).json()
    assert again["duplicate"] is True and again["registration"]["ref"] == g["registration"]["ref"]
    assert len(c.get("/api/network/me/registrations").json()["items"]) == 1                  # still exactly one


def test_delete_account_anonymises(client):
    cid = open_camp_ids(client)[2 if len(open_camp_ids(client)) > 2 else 0]
    c = TestClient(client.app)
    signup(c, ident="9500000001", pw="Delete@12345", name="Gone Person")
    c.post("/api/network/registrations", json={"camp_id": cid, "name": "Gone Person", "pin": "453331", "phone": "9833333333", "consent": True}, headers=H)
    assert c.delete("/api/network/me", headers=H).status_code == 200
    assert db.one("SELECT 1 FROM users WHERE identifier_norm='9500000001'") is None
    row = db.one("SELECT display_name, phone FROM registrations WHERE display_name='Deleted' ORDER BY id DESC LIMIT 1")
    assert row and row["phone"] is None


# ---- staff -------------------------------------------------------------------------------------------------------
def login(c, ident, pw):
    return c.post("/api/network/auth/login", json={"identifier": ident, "password": pw}, headers=H)


def test_worker_scope_and_assisted_registration(client):
    cid = open_camp_ids(client)[0]
    w = TestClient(client.app)
    assert login(w, "9000000001", "Demo@Worker1").status_code == 200
    camps = {c["id"] for c in w.get("/api/network/worker/camps").json()["items"]}
    unassigned = db.one("SELECT id FROM camps WHERE seed_key='d5'")["id"]
    assert unassigned not in camps
    body = {"camp_id": unassigned, "name": "P", "pin": "454001", "consent": True, "consent_spoken_confirmed": True}
    assert w.post("/api/network/worker/registrations", json=body, headers=H).status_code == 403   # outside assignment
    body = {"camp_id": cid, "name": "Assisted Person", "pin": "453331", "consent": True, "consent_spoken_confirmed": False}
    assert code(w.post("/api/network/worker/registrations", json=body, headers=H)) == "consent_required"
    body["consent_spoken_confirmed"] = True
    r = w.post("/api/network/worker/registrations", json=body, headers=H).json()
    assert r["registration"]["channel"] == "assisted"
    rid = db.one("SELECT id FROM registrations WHERE public_ref=?", (r["registration"]["ref"],))["id"]
    s = w.patch(f"/api/network/worker/registrations/{rid}/status", json={"status": "contacted"}, headers=H)
    assert s.status_code == 200 and s.json()["status"] == "contacted"
    assert w.patch(f"/api/network/worker/registrations/{rid}/status", json={"status": "attended"}, headers=H).status_code == 409   # skipping steps refused
    assert w.get("/api/network/organiser/camps").status_code == 403


def test_contact_details_only_with_consent(client):
    cid = open_camp_ids(client)[0]
    reg(client, cid, name="NoConsent", phone="9844444444", contact_consent=False)
    w = TestClient(client.app)
    login(w, "9000000001", "Demo@Worker1")
    rows = {r["name"]: r for r in w.get("/api/network/worker/requests").json()["items"]}
    assert rows["NoConsent"]["phone"] is None


def test_organiser_and_admin_rules(client):
    o = TestClient(client.app)
    assert login(o, "9000000002", "Demo@Organiser1").status_code == 200
    assert o.get("/api/network/organiser/summary").json()["is_demo_data"] is True
    demo = db.one("SELECT id FROM camps WHERE seed_key='d1'")["id"]
    assert o.patch(f"/api/network/admin/camps/{demo}/verification", json={"verification": "verified"}, headers=H).status_code == 403
    a = TestClient(client.app)
    login(a, "9000000003", "Demo@Admin1")
    assert code(a.patch(f"/api/network/admin/camps/{demo}/verification", json={"verification": "verified"}, headers=H)) == "demo_cannot_verify"
    bad = dict(title_en="x", place_label="y", district="d", state="s", pin="453331", starts_at="2020-01-01T10:00", ends_at="2020-01-01T12:00", publish_state="draft")
    assert code(o.post("/api/network/organiser/camps", json=bad, headers=H)) == "invalid_date"


# ---- Saathi ------------------------------------------------------------------------------------------------------
def turn(c, text, state=None, lang="hi"):
    r = c.post("/api/network/saathi/turn", json={"text": text, "lang": lang, "state": state or {}}, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def test_saathi_hindi_dialogue_uses_real_camps(client):
    t1 = turn(client, "Mujhe apne gaon mein aankhon ki jaanch karwani hai.")
    assert t1["meta"]["intent"] == "find_camps" and t1["state"].get("awaiting") == "pin" and "PIN" in t1["reply"]["text"]
    t2 = turn(client, "453331", t1["state"])
    ids = t2["state"]["camp_ids"]
    assert ids and t2["cards"][0]["type"] == "camps" and {i["id"] for i in t2["cards"][0]["items"]} == set(ids)
    assert "नमूना" in t2["reply"]["text"]                                                  # says they are demonstration camps
    t3 = turn(client, "pehla wala", t2["state"])
    assert t3["meta"]["intent"] == "choose_camp" and str(t3["cards"][0]["items"][0]["id"]) == str(ids[0])
    t4 = turn(client, "mujhe registration karna hai", t3["state"])
    assert [a["type"] for a in t4["actions"]] == ["open_registration"] and t4["actions"][0]["camp_id"] == ids[0]
    assert db.one("SELECT COUNT(*) n FROM registrations WHERE display_name='Saathi'")["n"] == 0   # chat never submits anything


def test_saathi_scripted_demo_dialogue_without_gemini(monkeypatch, client):
    """The hackathon demo, turn by turn, with no AI provider configured."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    q = turn(client, "मुझे diabetes है लेकिन मुझे ठीक दिखाई देता है। क्या मुझे आँखों की जाँच करवानी चाहिए?")
    assert q["meta"] == {"provider": "rules", "degraded": False, "intent": "screening_question"}
    assert "रेटिना" in q["reply"]["text"] and q["reply"]["text"].endswith("क्या मैं आपके पास आँखों की जाँच ढूँढूँ?")
    assert q["state"]["awaiting"] == "confirm_find" and q["cards"][0]["slug"] == "why-screening"
    yes = turn(client, "हाँ", q["state"])
    assert yes["meta"]["intent"] == "find_camps" and yes["state"]["awaiting"] == "pin" and "6 अंकों का PIN" in yes["reply"]["text"]
    res = turn(client, "452001", yes["state"])
    items = res["cards"][0]["items"]
    assert items and all(i["pin"] == "452001" and i["is_demo"] for i in items) and "नमूना" in res["reply"]["text"]
    assert res["state"]["camp_ids"] == [i["id"] for i in items] and "awaiting" not in res["state"]
    db_ids = {r["id"] for r in db.all_("SELECT c.id FROM camps c JOIN locations l ON l.id=c.location_id WHERE l.pin='452001'")}
    assert {i["id"] for i in items} <= db_ids                                               # only real database rows
    det = turn(client, "पहले वाले के बारे में बताइए", res["state"])
    assert det["meta"]["intent"] == "choose_camp" and det["cards"][0]["items"][0]["id"] == items[0]["id"]
    reg = turn(client, "रुचि दर्ज करनी है", det["state"])
    assert [a["type"] for a in reg["actions"]] == ["open_registration"] and "अपॉइंटमेंट नहीं" in reg["reply"]["text"]


def test_saathi_yes_no_and_context(client):
    no = turn(client, "नहीं, अभी नहीं", {"awaiting": "confirm_find"})
    assert no["meta"]["intent"] == "decline" and "awaiting" not in no["state"]
    assert turn(client, "Yes, find a camp", {"awaiting": "confirm_find"}, lang="en")["state"]["awaiting"] == "pin"
    assert turn(client, "haan", {"awaiting": "pin"})["meta"]["intent"] == "find_camps"         # not a place called "haan"
    assert turn(client, "haan")["meta"]["intent"] == "affirm"                                 # a yes with no question: offer help
    assert turn(client, "mujhe theek se nahi dikhta")["meta"]["intent"] == "medical_advice"  # a sentence, not a "no"
    ids = turn(client, "453331")["state"]["camp_ids"]
    assert turn(client, "doosri wali", {"camp_ids": ids})["cards"][0]["items"][0]["id"] == ids[1]
    assert turn(client, "2 wala", {"camp_ids": ids})["cards"][0]["items"][0]["id"] == ids[1]
    stale = turn(client, "namaste", {"awaiting": "pin"})                                    # an answered turn closes the question
    assert "awaiting" not in stale["state"]
    assert turn(client, "Indore", stale["state"])["meta"]["intent"] == "unknown"             # ...so a later word is not a place search


def test_saathi_urgent_symptoms_escalate_without_camps(client):
    for text, lang in [("मेरी आँखों से अचानक दिखना बंद हो गया", "hi"), ("aankh mein chot lag gayi", "hi"), ("sudden vision loss in my left eye", "en"),
                       ("I suddenly can't see from one eye", "en"), ("chemical went into my eye", "en")]:
        r = turn(client, text, {"awaiting": "pin", "camp_ids": [1]}, lang=lang)
        assert r["meta"]["intent"] == "urgent_symptom", text
        assert r["cards"] == [] and r["actions"] == [] and "112" in r["reply"]["text"] and "awaiting" not in r["state"]
    assert turn(client, "mujhe dhundhla dikhta hai")["meta"]["intent"] == "medical_advice"   # not every symptom is an emergency


def test_saathi_spoken_digits_and_no_camps(client):
    t = turn(client, "four five three three three one", lang="en")
    assert t["meta"]["intent"] == "find_camps" and t["reply"]["lang"] == "en" and t["state"]["camp_ids"]
    none = turn(client, "999999")
    assert none["cards"] == [] and "सत्यापित शिविर नहीं" in none["reply"]["text"]            # honest empty result
    bad = turn(client, "mujhe camp chahiye", {"awaiting": "pin"})
    assert bad["meta"]["intent"] == "find_camps"


def test_saathi_safety_and_awareness(client):
    m = turn(client, "kya mujhe retinopathy hai? kaun si dawai lun?")
    assert m["meta"]["intent"] == "medical_advice" and "डॉक्टर" in m["reply"]["text"] and m["cards"] == []
    e = turn(client, "Why is screening important?", lang="en")
    assert e["meta"]["intent"] == "explain" and e["cards"][0]["slug"] == "why-screening"
    assert turn(client, "diabetes aur aankhon ke baare mein batao")["cards"][0]["slug"] == "diabetes-and-eyes"
    assert turn(client, "xyzzy plugh")["meta"]["intent"] == "unknown"


def test_saathi_personal_data_requires_login(client):
    g = turn(client, "meri profile dikhao")
    assert g["meta"]["intent"] == "show_profile" and g["cards"] == [] and "लॉग इन" in g["reply"]["text"]
    assert "लॉग इन" in turn(client, "Maine kis camp mein registration kiya hai?")["reply"]["text"]
    c = TestClient(client.app)
    signup(c, ident="9400000001", pw="Secret@12345", name="Meena")
    p = turn(c, "meri profile dikhao")
    assert "Meena" in p["reply"]["text"] and p["cards"][0]["type"] == "profile" and "9400000001" not in p["reply"]["text"]
    other = TestClient(client.app)
    assert "Meena" not in turn(other, "meri profile dikhao")["reply"]["text"]
    sl = turn(c, "Meri bhasha English kar do")
    assert sl["actions"] == [{"type": "set_language", "lang": "en"}]
    assert db.one("SELECT language FROM users WHERE identifier_norm='9400000001'")["language"] == "en"


def test_saathi_input_limits(client):
    assert client.post("/api/network/saathi/turn", json={"text": "x" * 501, "lang": "hi"}, headers=H).status_code == 422
    assert client.post("/api/network/saathi/turn", json={"text": "hi", "lang": "fr"}, headers=H).status_code == 422
    r = turn(client, "namaste", {"awaiting": "x" * 5, "camp_ids": ["; DROP TABLE camps", 3], "pin": "not-a-pin"})
    assert r["reply"]["text"]


def test_nlu_units():
    assert nlu.extract_pin("mera pin 453331 hai") == "453331" and nlu.extract_pin("४५३३३१") == "453331"
    assert nlu.extract_pin("चार पाँच तीन तीन तीन एक") == "453331" and nlu.extract_pin("kar do") is None and nlu.extract_pin("12345") is None
    assert nlu.extract_pin("four five two double zero one") == "452001" and nlu.extract_pin("mera pin to 452001 hai") == "452001"
    assert nlu.extract_pin("do paanch do shunya shunya ek") == "252001" and nlu.extract_pin("45 20 01") == "452001"
    assert nlu.extract_pin("सिफ़र") is None and nlu.extract_pin("go to camp") is None
    assert nlu.detect_language("Mujhe aankhon ki jaanch karwani hai") == "hi" and nlu.detect_language("I need an eye check") == "en"
    assert nlu.detect_language("मुझे शिविर चाहिए") == "hi" and nlu.detect_language("453331", "en") == "en"


def test_guardrails():
    assert not guardrails.reply_ok("Your appointment is confirmed for Monday.")
    assert not guardrails.reply_ok("आपका अपॉइंटमेंट पक्का हो गया")
    assert not guardrails.reply_ok("You definitely have diabetic retinopathy")
    assert guardrails.reply_ok("This only records your interest; it is not a confirmed appointment.")
    s = guardrails.scrub_for_provider("call me on 9876543210 or a@b.com, aadhaar 1234 5678 9012, pin 453331")
    assert "9876543210" not in s and "a@b.com" not in s and "1234 5678" not in s and "453331" in s


def test_gemini_provider_is_optional_and_validated(monkeypatch, client):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert gemini.available() is False and gemini.route("kuch bhi", {}, "hi") is None
    resp = {"candidates": [{"content": {"parts": [{"functionCall": {"name": "find_camps", "args": {"pin": "453331"}}}]}}]}
    assert gemini.parse_call(resp, {}).args["pin"] == "453331"
    evil = {"candidates": [{"content": {"parts": [{"functionCall": {"name": "run_sql", "args": {"q": "DROP TABLE users"}}}]}}]}
    assert gemini.parse_call(evil, {}) is None                                              # unknown tools are refused
    assert gemini.parse_call({"candidates": [{"content": {"parts": [{"functionCall": {"name": "choose_camp", "args": {"position": 9}}}]}}]}, {"camp_ids": [1]}) is None
    sent = {}
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(gemini, "_post", lambda p: sent.update(p) or resp)
    r = turn(client, "xyzzy mera number 9876543210 hai gaon ke liye")                          # unknown to rules -> router; no network call (mocked)
    assert r["meta"]["provider"] in ("gemini", "rules")
    if sent:
        assert "9876543210" not in str(sent) and "tools" in sent


def test_gemini_quota_pause_falls_back_to_rules(monkeypatch, client):
    import httpx
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(gemini, "_cool_until", 0.0)
    def boom(_):
        raise httpx.HTTPStatusError("429", request=httpx.Request("POST", "http://x"), response=httpx.Response(429))
    monkeypatch.setattr(gemini, "_post", boom)
    r = turn(client, "xyzzy plugh")
    assert r["meta"]["provider"] == "rules" and r["reply"]["text"]                                # still answers, no paid fallback
    assert gemini.available() is False                                                           # paused after quota error


# ---- content & isolation -----------------------------------------------------------------------------------------
def test_content_is_labelled_and_bilingual(client):
    items = client.get("/api/network/content?lang=hi").json()["items"]
    assert len(items) == 6 and all(i["review_status"] == "illustrative" for i in items)
    t = client.get("/api/network/content/myths-facts?lang=en").json()
    assert t["blocks"] and client.get("/api/network/content/nope").status_code == 404


def test_network_never_touches_clinical_code():
    banned = re.compile(r"backend\.store|from \.+ import .*\bstore\b|^\s*import store\b|from inference|import inference|state\[.db.\]", re.M)
    for f in (ROOT / "backend" / "network").rglob("*.py"):
        if f.name == "test_network.py":
            continue
        assert not banned.search(f.read_text(encoding="utf-8")), f
    # V3: exactly one controlled read path into clinical state (bridge.py); the CLI may grant/revoke clinician access.
    clinical = re.compile(r"clinical_state|clinical_auth|backend\.app\b")
    users = {f.name for f in (ROOT / "backend" / "network").rglob("*.py") if f.name != "test_network.py" and clinical.search(f.read_text(encoding="utf-8"))}
    assert users <= {"bridge.py", "cli.py"}, users
    assert "clinical_auth" not in (ROOT / "backend/network/bridge.py").read_text(encoding="utf-8")


def test_bridge_status_is_minimal_without_a_link(client):
    c = TestClient(client.app)
    r = reg(c, name="Bridge Test").json()
    look = c.post("/api/network/registrations/lookup", json={"ref": r["registration"]["ref"], "code": r["receipt_code"]}, headers=H).json()
    assert look["screening"] == {"state": "not_linked"}
