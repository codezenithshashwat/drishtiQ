"""The only actions Saathi can perform. Each tool validates its own arguments, takes identity from the session (never from
parameters), reads through the same services as the website, and returns plain data. There is no free-form query access and
no tool writes registrations: submitting interest is a button the person presses in the form, validated by the server."""
from .. import content, db, security, services
from ..security import err

NAV_TARGETS = {"home": "/network", "camps": "/network/camps", "learn": "/network/learn", "saathi": "/network/saathi", "me": "/network/me",
               "login": "/network/login", "signup": "/network/signup", "about": "/network/about"}


def find_camps(pin: str | None = None, q: str | None = None) -> dict:
    return services.search_camps(pin, (q or "")[:40] or None, include_expired=False, limit=5)


def get_camp_details(camp_id) -> dict:
    if not isinstance(camp_id, int):
        raise err(422, "invalid_camp", "Unknown camp.")
    return services.camp_dto(services.get_camp(camp_id))


def get_awareness_content(topic: str, lang: str) -> dict:
    t = content.topic(topic, lang)
    if t is None:
        raise err(404, "topic_not_found", "Unknown topic.")
    return t


def navigate_to_section(target: str) -> str:
    if target not in NAV_TARGETS:
        raise err(422, "invalid_target", "Unknown section.")
    return NAV_TARGETS[target]


def get_registration_requirements() -> dict:
    return {"required": ["name", "pin", "consent"], "optional": ["village", "phone", "email"]}


def get_supported_languages() -> list[str]:
    return ["hi", "en"]


def set_language(lang: str, user) -> str:
    if lang not in ("hi", "en"):
        raise err(422, "invalid_language", "Unsupported language.")
    if user is not None:
        db.run("UPDATE users SET language=? WHERE id=?", (lang, user["id"]))
    return lang


def show_my_profile(user) -> dict:
    if user is None:
        raise err(401, "login_required", "Please log in first.")
    return services.user_dto(user)


def list_my_registrations(user) -> list[dict]:
    if user is None:
        raise err(401, "login_required", "Please log in first.")
    return services.my_registrations(user)


def lite(c: dict, lang: str) -> dict:
    """Small camp shape for chat cards."""
    p = c["place"]
    return {"id": c["id"], "title": c["title"][lang], "starts_at": c["starts_at"], "ends_at": c["ends_at"], "village": p["village"] or p["label"],
            "district": p["district"], "pin": p["pin"], "verification": c["verification"], "state": c["state"], "is_demo": c["is_demo"],
            "match": c.get("match")}


# Names exposed to a provider's function-calling schema. Anything else is refused.
ALLOWED = {"find_camps", "get_camp_details", "get_awareness_content", "navigate_to_section", "get_registration_requirements",
           "get_supported_languages", "set_language", "show_my_profile", "list_my_registrations"}
