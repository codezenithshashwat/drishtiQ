"""Optional understanding layer using the Gemini free tier (REST, key from the backend environment only).

Gemini is used ONLY as an intent router: it must answer with one function call from the allowlist; it never writes text that
reaches the user, and it never sees profile or registration data. Only PII-scrubbed utterances are sent. It is called only
when the deterministic rules could not understand the sentence, so most turns use no quota. Free-tier traffic may be used by
Google to improve its products, which is another reason nothing personal is sent. On any failure Saathi stays in rules mode.
There is no paid fallback: if the free quota is exhausted the provider simply pauses."""
import time
from datetime import date

import httpx

from .. import config, content
from . import guardrails
from .nlu import Intent

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_cool_until = 0.0
_count = {"day": None, "n": 0}
TOPICS = sorted(content.BY_SLUG)
NAV = ["home", "camps", "learn", "me", "login", "signup", "about"]

SYSTEM = ("You are the intent router for DrishtiQ Saathi, an eye-screening camp helper for rural India. The user writes Hindi, Hinglish "
          "or English. Choose exactly ONE function that matches the request. Never answer in text. Use urgent_symptom for sudden vision "
          "loss, eye injury, chemicals in the eye or severe eye pain. Use screening_question when the person asks whether they should get "
          "their eyes checked. Use affirm or decline for a plain yes or no. Use medical_advice for any question "
          "about diagnosis, medicines or treatment. Use unknown if nothing fits.")

FUNCS = [
    {"name": "find_camps", "description": "Find eye screening camps by PIN code (6 digits) or place name",
     "parameters": {"type": "object", "properties": {"pin": {"type": "string"}, "place": {"type": "string"}}}},
    {"name": "explain_topic", "description": "Explain an eye-health topic from approved content",
     "parameters": {"type": "object", "properties": {"topic": {"type": "string", "enum": TOPICS}}, "required": ["topic"]}},
    {"name": "start_registration", "description": "User wants to register interest in a camp", "parameters": {"type": "object", "properties": {}}},
    {"name": "choose_camp", "description": "User picks one of the camps just listed (1-based position)",
     "parameters": {"type": "object", "properties": {"position": {"type": "integer"}}, "required": ["position"]}},
    {"name": "camp_details", "description": "Details of the camp in context", "parameters": {"type": "object", "properties": {}}},
    {"name": "camp_price", "description": "Fee of the camp in context", "parameters": {"type": "object", "properties": {}}},
    {"name": "show_profile", "description": "Show the user's own profile", "parameters": {"type": "object", "properties": {}}},
    {"name": "list_my_registrations", "description": "Show the user's own registrations", "parameters": {"type": "object", "properties": {}}},
    {"name": "set_language", "description": "Switch language",
     "parameters": {"type": "object", "properties": {"lang": {"type": "string", "enum": ["hi", "en"]}}, "required": ["lang"]}},
    {"name": "navigate", "description": "Open a section of the website",
     "parameters": {"type": "object", "properties": {"target": {"type": "string", "enum": NAV}}, "required": ["target"]}},
    {"name": "medical_advice", "description": "Diagnosis, medicine or treatment question", "parameters": {"type": "object", "properties": {}}},
    {"name": "urgent_symptom", "description": "Sudden vision loss, eye injury, chemical in the eye or severe eye pain", "parameters": {"type": "object", "properties": {}}},
    {"name": "screening_question", "description": "Asks whether they should get an eye check (e.g. because of diabetes)",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "affirm", "description": "Plain yes / agreement to Saathi's last question", "parameters": {"type": "object", "properties": {}}},
    {"name": "decline", "description": "Plain no / not now", "parameters": {"type": "object", "properties": {}}},
    {"name": "greet", "description": "Greeting", "parameters": {"type": "object", "properties": {}}},
    {"name": "help", "description": "What can you do", "parameters": {"type": "object", "properties": {}}},
    {"name": "about", "description": "What is DrishtiQ", "parameters": {"type": "object", "properties": {}}},
    {"name": "unknown", "description": "Nothing matches", "parameters": {"type": "object", "properties": {}}},
]


def available() -> bool:
    if not config.gemini_key() or time.monotonic() < _cool_until:
        return False
    today = date.today().isoformat()
    if _count["day"] != today:
        _count.update(day=today, n=0)
    return _count["n"] < config.GEMINI_DAILY_CAP


def _post(payload: dict) -> dict:  # isolated so tests can replace it; never called without a key
    r = httpx.post(ENDPOINT.format(model=config.GEMINI_MODEL), json=payload, timeout=6.0,
                   headers={"x-goog-api-key": config.gemini_key(), "content-type": "application/json"})
    r.raise_for_status()
    return r.json()


def parse_call(data: dict, state: dict) -> Intent | None:
    """Turn a Gemini response into a validated Intent (or None). Arguments are re-checked here, never trusted."""
    try:
        parts = data["candidates"][0]["content"]["parts"]
        call = next(p["functionCall"] for p in parts if "functionCall" in p)
    except (KeyError, IndexError, StopIteration, TypeError):
        return None
    name, args = call.get("name"), call.get("args") or {}
    ids = state.get("camp_ids") or []
    if name == "find_camps":
        pin = str(args.get("pin") or "")
        return Intent("find_camps", {"pin": pin if len(pin) == 6 and pin.isdigit() else None, "q": (str(args.get("place") or "")[:40] or None) if not (len(pin) == 6 and pin.isdigit()) else None}, source="gemini")
    if name == "explain_topic" and args.get("topic") in content.BY_SLUG:
        return Intent("explain", {"topic": args["topic"]}, source="gemini")
    if name == "choose_camp":
        try:
            pos = int(args.get("position"))
        except (TypeError, ValueError):
            return None
        return Intent("choose_camp", {"camp_id": ids[pos - 1]}, source="gemini") if 1 <= pos <= len(ids) else None
    if name == "set_language" and args.get("lang") in ("hi", "en"):
        return Intent("set_language", {"lang": args["lang"]}, lang=args["lang"], source="gemini")
    if name == "navigate" and args.get("target") in NAV:
        return Intent("navigate", {"target": args["target"]}, source="gemini")
    if name == "affirm" and state.get("awaiting") in ("confirm_find", "pin"):  # same dialogue rule as nlu.route
        return Intent("find_camps", {"q": None}, source="gemini")
    simple = {"start_registration", "camp_details", "camp_price", "show_profile", "list_my_registrations", "medical_advice", "greet", "help", "about",
              "urgent_symptom", "screening_question", "affirm", "decline"}
    if name in simple:
        a = {}
        if name in ("camp_details", "camp_price"):
            a = {"camp_id": state.get("camp_id") or (ids[0] if len(ids) == 1 else None)}
        return Intent(name, a, source="gemini")
    return None


def route(text: str, state: dict, lang: str) -> Intent | None:
    """None when unavailable, failing, or unsure; the caller then stays with the rules."""
    global _cool_until
    if not available():
        return None
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        # Conversation context without personal data: only what Saathi is waiting for and how many camps are on screen.
        "contents": [{"role": "user", "parts": [{"text": f"[context: waiting_for={state.get('awaiting') or 'nothing'}; "
                                                         f"camps_listed={len(state.get('camp_ids') or [])}]\n{guardrails.scrub_for_provider(text)}"}]}],
        "tools": [{"functionDeclarations": FUNCS}],
        "toolConfig": {"functionCallingConfig": {"mode": "ANY"}},
        "generationConfig": {"temperature": 0, "maxOutputTokens": 128},
    }
    try:
        _count["n"] += 1
        data = _post(payload)
    except httpx.HTTPStatusError as e:
        _cool_until = time.monotonic() + (600 if e.response.status_code == 429 else 60)  # quota or outage: pause, never upgrade
        return None
    except Exception:  # noqa: BLE001  network, timeout, bad JSON
        _cool_until = time.monotonic() + 30
        return None
    intent = parse_call(data, state)
    return None if intent is None or intent.name == "unknown" else intent
