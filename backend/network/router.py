"""HTTP surface of DrishtiQ Network: /api/network/*. Thin; rules live in services.py and saathi/."""
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from . import config, content, db, security, services
from .saathi import engine
from .security import csrf_guard, err, need_role, need_user

router = APIRouter(prefix="/api/network", dependencies=[Depends(csrf_guard)], tags=["network"])
Lang = Literal["hi", "en"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---- public ------------------------------------------------------------------------------------------------------
@router.get("/health")
def health():
    return {"ok": True, "demo_mode": config.DEMO_MODE}


@router.get("/public/config")
def public_config():
    return {"demo_mode": config.DEMO_MODE, "saathi": engine.capabilities(), "languages": ["hi", "en"], "content_version": content.VERSION,
            "consent_version": services.CONSENT_VERSION, "retention_days": config.RETENTION_DAYS}


@router.get("/public/summary")
def public_summary():
    items = services.search_camps(None, None, include_expired=False, limit=100)["items"]
    return {"open_camps": sum(c["state"] == "open" for c in items), "all_demo": all(c["is_demo"] for c in items) if items else False}


@router.get("/camps")
def camps(pin: str | None = Query(None, max_length=6), q: str | None = Query(None, max_length=40), include_expired: bool = False):
    return services.search_camps(pin.strip() if pin else None, q, include_expired)


@router.get("/camps/{camp_id}")
def camp(camp_id: int):
    return services.camp_dto(services.get_camp(camp_id))


@router.get("/content")
def content_list(lang: Lang = "hi"):
    return {"version": content.VERSION, "items": content.listing(lang)}


@router.get("/content/{slug}")
def content_item(slug: str, lang: Lang = "hi"):
    t = content.topic(slug, lang)
    if t is None:
        raise err(404, "topic_not_found", "Unknown topic.")
    return t


# ---- registrations -----------------------------------------------------------------------------------------------
class RegIn(Strict):
    camp_id: int
    name: str = Field(min_length=1, max_length=80)
    pin: str = Field(pattern=r"^\d{6}$")
    village: str | None = Field(None, max_length=60)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=120)
    language: Lang = "hi"
    consent: bool
    contact_consent: bool = False
    idempotency_key: str | None = Field(None, max_length=64)
    via_saathi: bool = False


@router.post("/registrations")
def register(body: RegIn, request: Request):
    security.rate_limit(f"reg:{security.client_ip(request)}", 20, 600)
    user = security.current_user(request)
    res = services.create_registration(body.model_dump(), user, channel="saathi_guided" if body.via_saathi else "self")
    return res


class LookupIn(Strict):
    ref: str = Field(max_length=20)
    code: str = Field(max_length=20)


@router.post("/registrations/lookup")
def lookup(body: LookupIn, request: Request):
    security.rate_limit(f"lookup:{security.client_ip(request)}", 15, 300)
    return services.lookup_registration(body.ref, body.code)


# ---- accounts ----------------------------------------------------------------------------------------------------
class SignupIn(Strict):
    name: str = Field(min_length=1, max_length=80)
    identifier: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    village: str | None = Field(None, max_length=60)
    pin: str | None = Field(None, pattern=r"^\d{6}$")
    language: Lang = "hi"
    reminders_opt_in: bool = False
    comm_pref: Literal["none", "sms", "call", "email"] = "none"
    consent: bool


class LoginIn(Strict):
    identifier: str = Field(max_length=120)
    password: str = Field(max_length=128)


def _session(resp: Response, request: Request, u) -> None:
    security.revoke(request.cookies.get(security.COOKIE))  # rotate on login
    security.set_cookie(resp, request, security.create_session(u["id"]))


@router.post("/auth/signup")
def signup(body: SignupIn, request: Request, response: Response):
    security.rate_limit(f"signup:{security.client_ip(request)}", 10, 3600)
    u = services.signup(body.model_dump())
    _session(response, request, u)
    return {"user": services.user_dto(u)}


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response):
    # Per IP AND account (strict) plus a looser per-IP ceiling: one shared camp/PHC connection must not lock out every
    # user, while repeated guessing at one account is still stopped here and by the account lockout in services.login.
    ip = security.client_ip(request)
    security.rate_limit(f"login:{ip}:{(body.identifier or '').strip().lower()[:120]}", 10, 300)
    security.rate_limit(f"login-ip:{ip}", 100, 300)
    u = services.login(body.identifier, body.password)
    _session(response, request, u)
    return {"user": services.user_dto(u)}


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    security.revoke(request.cookies.get(security.COOKIE))
    security.clear_cookie(response)
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    u = security.current_user(request)
    return {"user": services.user_dto(u) if u is not None else None}  # 200 with null: the page can ask "am I signed in?" quietly


class ProfileIn(Strict):
    name: str | None = Field(None, min_length=1, max_length=80)
    village: str | None = Field(None, max_length=60)
    pin: str | None = Field(None, pattern=r"^(\d{6})?$")
    language: Lang | None = None
    reminders_opt_in: bool | None = None
    comm_pref: Literal["none", "sms", "call", "email"] | None = None


@router.patch("/me")
def update_me(body: ProfileIn, u=Depends(need_user)):
    return {"user": services.update_profile(u, body.model_dump(exclude_unset=True))}


@router.delete("/me")
def delete_me(response: Response, u=Depends(need_user)):
    services.delete_account(u)
    security.clear_cookie(response)
    return {"ok": True}


@router.get("/me/registrations")
def my_regs(u=Depends(need_user)):
    return {"items": services.my_registrations(u)}


@router.get("/me/export")
def my_export(u=Depends(need_user)):
    return services.export_data(u)


@router.post("/me/registrations/claim")
def claim(body: LookupIn, u=Depends(need_role("user"))):
    return services.claim_registration(u, body.ref, body.code)


@router.post("/me/registrations/{reg_id}/cancel")
def cancel(reg_id: int, u=Depends(need_role("user"))):
    return services.set_status(u, reg_id, "cancelled")


# ---- staff: health worker ----------------------------------------------------------------------------------------
class StatusIn(Strict):
    status: Literal["contacted", "confirmed_by_organiser", "attended", "no_show", "cancelled"]


class AssistedIn(RegIn):
    consent_spoken_confirmed: bool = False


STAFF = ("health_worker", "organiser", "admin")


@router.get("/worker/camps")
def worker_camps(u=Depends(need_role("health_worker", "admin"))):
    return {"items": services.organiser_camps(u)}


@router.get("/worker/requests")
def worker_requests(camp_id: int | None = None, status: str | None = None, u=Depends(need_role(*STAFF))):
    return {"items": services.staff_requests(u, camp_id, status)}


@router.get("/worker/followups")
def worker_followups(u=Depends(need_role("health_worker", "admin"))):
    return {"items": services.staff_followups(u)}


class FollowupIn(Strict):
    note: str | None = Field(None, max_length=200)


@router.patch("/worker/followups/{fid}")
def worker_followup_done(fid: int, body: FollowupIn, u=Depends(need_role("health_worker", "admin"))):
    return services.complete_followup(u, fid, body.note)


@router.patch("/worker/registrations/{reg_id}/status")
def worker_status(reg_id: int, body: StatusIn, u=Depends(need_role(*STAFF))):
    return services.set_status(u, reg_id, body.status)


@router.post("/worker/registrations")
def worker_assisted(body: AssistedIn, u=Depends(need_role("health_worker", "admin"))):
    """Assisted registration: the worker records it on behalf of a person who has agreed in front of them. Without the
    explicit confirmation it is refused; the record states it was created by staff (channel=assisted, created_by)."""
    if not body.consent_spoken_confirmed:
        raise err(422, "consent_required", "Confirm that the person agreed.")
    scope = services.camp_scope(u)
    if scope is not None and body.camp_id not in scope:
        raise err(403, "forbidden", "This camp is not assigned to you.")
    return services.create_registration(body.model_dump(exclude={"consent_spoken_confirmed", "via_saathi"}), u, channel="assisted", created_by=u)


# ---- organiser ---------------------------------------------------------------------------------------------------
class CampIn(Strict):
    title_en: str = Field(min_length=1, max_length=120)
    title_hi: str = Field("", max_length=120)
    place_label: str = Field(min_length=1, max_length=120)
    village: str | None = Field(None, max_length=60)
    district: str = Field(min_length=1, max_length=60)
    state: str = Field(min_length=1, max_length=60)
    pin: str = Field(pattern=r"^\d{6}$")
    starts_at: str
    ends_at: str
    capacity: int | None = Field(None, ge=0, le=100000)
    price_info: str | None = Field(None, max_length=120)
    contact_public: str | None = Field(None, max_length=120)
    publish_state: Literal["draft", "published", "closed", "cancelled"] = "draft"


ORG = ("organiser", "admin")


@router.get("/organiser/camps")
def org_camps(u=Depends(need_role(*ORG))):
    return {"items": services.organiser_camps(u)}


@router.post("/organiser/camps")
def org_create(body: CampIn, u=Depends(need_role(*ORG))):
    return services.upsert_camp(u, body.model_dump())


@router.patch("/organiser/camps/{camp_id}")
def org_update(camp_id: int, body: CampIn, u=Depends(need_role(*ORG))):
    return services.upsert_camp(u, body.model_dump(), camp_id)


class VerifyIn(Strict):
    verification: Literal["verified", "unverified"]


@router.patch("/admin/camps/{camp_id}/verification")
def admin_verify(camp_id: int, body: VerifyIn, u=Depends(need_role("admin"))):
    return services.set_verification(u, camp_id, body.verification)


@router.get("/organiser/summary")
def org_summary(u=Depends(need_role(*ORG))):
    return services.organiser_summary(u)


# ---- Saathi ------------------------------------------------------------------------------------------------------
class TurnIn(Strict):
    text: str = Field(max_length=500)
    lang: Lang = "hi"
    state: dict | None = None
    ui: dict | None = None


@router.get("/saathi/capabilities")
def saathi_caps():
    return engine.capabilities()


@router.post("/saathi/turn")
def saathi_turn(body: TurnIn, request: Request):
    ip = security.client_ip(request)
    security.rate_limit(f"saathi:{ip}", 40, 60)
    ui = {k: v for k, v in (body.ui or {}).items() if k in ("screen", "camp_id") and isinstance(v, (str, int))}
    return engine.handle_turn(body.text, body.lang, body.state, ui, security.current_user(request))
