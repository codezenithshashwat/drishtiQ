"""One conversation turn: understand (rules first, optional Gemini only for sentences the rules cannot parse), run an
allowlisted tool, and compose the answer from templates. Stateless: the client sends back the small `state` we return."""
from fastapi import HTTPException

from . import gemini, guardrails, nlu, tools
from .nlu import Intent
from .templates import STATE_WORD, STATUS, SUGGEST, camp_line, fmt_when, t, trust_note

STATE_KEYS = ("lang", "awaiting", "pin", "camp_id", "want")


def clean_state(s: dict | None) -> dict:
    s = s or {}
    out = {k: s[k] for k in STATE_KEYS if isinstance(s.get(k), (str, int)) and s.get(k) != ""}
    ids = [i for i in (s.get("camp_ids") or []) if isinstance(i, int)][:5]
    if ids:
        out["camp_ids"] = ids
    if out.get("pin") and not (str(out["pin"]).isdigit() and len(str(out["pin"])) == 6):
        out.pop("pin")
    return out


def capabilities() -> dict:
    return {"providers": ["rules"] + (["gemini"] if gemini.available() else []), "languages": ["hi", "en"],
            "note": "Gemini (optional, free tier) only helps understand sentences; answers always come from the database and approved content."}


def handle_turn(text: str, lang: str, state: dict | None, ui: dict | None, user) -> dict:
    text = (text or "").strip()[:500]
    lang = lang if lang in ("hi", "en") else "hi"
    state = clean_state(state)
    ui = ui or {}
    intent = nlu.route(text, state, ui, lang)
    provider, degraded = "rules", False
    if intent.name == "unknown" and text:
        g = gemini.route(text, state, lang)
        if g is not None:
            intent, provider = g, "gemini"
        elif gemini.available() is False and gemini.config.gemini_key():
            degraded = True  # key present but paused (quota/outage): say so, stay useful in rules mode
    rl = intent.lang or lang
    if rl not in ("hi", "en"):
        rl = lang
    out = _compose(intent, rl, state, ui, user)
    if not guardrails.reply_ok(out["text"]):
        out = {"text": guardrails.SAFE_FALLBACK[rl], "cards": [], "links": [], "actions": [], "suggestions": [], "state": state}
    # A question Saathi asked ("awaiting") is answered or abandoned by the next understood turn; only a turn Saathi could
    # not understand keeps it open, so a stale "waiting for a PIN" never captures an unrelated later sentence.
    carried = state if intent.name == "unknown" else {k: v for k, v in state.items() if k != "awaiting"}
    new_state = {**carried, **out.pop("state", {})}
    new_state["lang"] = rl
    new_state = {k: v for k, v in new_state.items() if v not in (None, "")}
    return {"reply": {"text": out["text"], "lang": rl}, "cards": out.get("cards", []), "links": out.get("links", []), "actions": out.get("actions", []),
            "suggestions": out.get("suggestions", SUGGEST["start"][rl]), "state": new_state, "meta": {"provider": provider, "degraded": degraded, "intent": intent.name}}


def _r(text, **kw):
    return {"text": text, "cards": [], "links": [], "actions": [], **kw}


def _camps_card(items, lang):
    return [{"type": "camps", "items": [tools.lite(c, lang) for c in items]}]


def _open_form(camp, lang, state, user):
    prefill = {"pin": state.get("pin") or (user["pin"] if user is not None else None) or None, "language": lang}
    if user is not None:
        prefill.update(name=user["display_name"], village=user["village"], pin=prefill["pin"] or user["pin"])
    return _r(t("form_open", lang), cards=_camps_card([camp], lang), actions=[{"type": "open_registration", "camp_id": camp["id"], "prefill": {k: v for k, v in prefill.items() if v}}],
              state={"camp_id": camp["id"], "want": None, "awaiting": None}, suggestions=[])


def _compose(i: Intent, lang: str, state: dict, ui: dict, user) -> dict:
    n = i.name
    if n == "greet":
        return _r(t("greet", lang), suggestions=SUGGEST["start"][lang])
    if n == "help":
        return _r(t("help", lang), suggestions=SUGGEST["start"][lang])
    if n == "about":
        return _r(t("about", lang), links=[{"label": {"hi": "नेटवर्क के बारे में", "en": "About Network"}[lang], "to": "/network/about"}], suggestions=SUGGEST["start"][lang])
    if n == "thanks":
        return _r(t("thanks", lang))
    if n == "bye":
        return _r(t("bye", lang))
    if n == "urgent_symptom":
        # Possible emergency: clear advice to get care today. No camp search, no diagnosis, nothing else on screen.
        return _r(t("urgent", lang), suggestions=[], state={"awaiting": None, "want": None})
    if n == "screening_question":
        # General awareness (approved wording), then an offer that a plain "yes" can accept.
        topic = tools.get_awareness_content("why-screening", lang)
        return _r(t("screening_answer", lang), cards=[{"type": "topic", "slug": topic["slug"], "title": topic["title"], "summary": topic["summary"],
                                                        "review_status": topic["review_status"]}],
                  links=[{"label": {"hi": "पूरा पढ़ें", "en": "Read more"}[lang], "to": f"/network/learn/{topic['slug']}"}],
                  suggestions=SUGGEST["confirm"][lang], state={"awaiting": "confirm_find"})
    if n == "decline":
        return _r(t("declined", lang), suggestions=SUGGEST["after_topic"][lang], state={"awaiting": None, "want": None})
    if n == "affirm":  # a "yes" with no open question: say what Saathi can do instead of guessing
        return _r(t("help", lang), suggestions=SUGGEST["start"][lang])
    if n == "medical_advice":
        return _r(t("medical", lang), suggestions=SUGGEST["confirm"][lang], state={"awaiting": "confirm_find"})
    if n == "unknown":
        return _r(t("unknown", lang), suggestions=SUGGEST["start"][lang])
    if n == "requirements":
        tools.get_registration_requirements()
        return _r(t("requirements", lang), suggestions=SUGGEST["after_camps"][lang])

    if n == "set_language":
        target = tools.set_language(i.args["lang"], user)
        return _r(t("lang_set", target), actions=[{"type": "set_language", "lang": target}], suggestions=SUGGEST["start"][target])

    if n == "navigate":
        to = tools.navigate_to_section(i.args["target"])
        return _r(t("navigating", lang), actions=[{"type": "navigate", "to": to}], suggestions=[])

    if n == "explain":
        topic = tools.get_awareness_content(i.args["topic"], lang)
        note = "यह सामान्य जानकारी है, डॉक्टर की सलाह का विकल्प नहीं।" if lang == "hi" else "This is general information, not a substitute for a doctor's advice."
        return _r(f"{topic['summary']} {note}", cards=[{"type": "topic", "slug": topic["slug"], "title": topic["title"], "summary": topic["summary"], "review_status": topic["review_status"]}],
                  links=[{"label": {"hi": "पूरा पढ़ें", "en": "Read more"}[lang], "to": f"/network/learn/{topic['slug']}"}], suggestions=SUGGEST["after_topic"][lang])

    if n == "show_profile":
        if user is None:
            return _r(t("login_needed", lang), links=[{"label": {"hi": "लॉग इन", "en": "Log in"}[lang], "to": "/network/login"}], suggestions=SUGGEST["login"][lang])
        p = tools.show_my_profile(user)
        na = "दर्ज नहीं" if lang == "hi" else "not set"
        if lang == "hi":
            txt = f"आपका नाम {p['name']} है। गाँव या शहर: {p['village'] or na}। PIN कोड: {p['pin'] or na}। भाषा: {'हिंदी' if p['language'] == 'hi' else 'अंग्रेज़ी'}। आपका संपर्क {p['identifier_masked']} है, जिसकी पुष्टि नहीं हुई है।"
        else:
            txt = f"Your name is {p['name']}. Village or city: {p['village'] or na}. PIN code: {p['pin'] or na}. Language: {'Hindi' if p['language'] == 'hi' else 'English'}. Your contact is {p['identifier_masked']} (not verified)."
        return _r(txt, cards=[{"type": "profile", "profile": p}], links=[{"label": "My DrishtiQ", "to": "/network/me"}], suggestions=[])

    if n == "list_my_registrations":
        if user is None:
            return _r(t("login_needed", lang), links=[{"label": {"hi": "लॉग इन", "en": "Log in"}[lang], "to": "/network/login"}], suggestions=SUGGEST["login"][lang])
        regs = tools.list_my_registrations(user)
        if not regs:
            return _r(t("no_regs", lang), suggestions=SUGGEST["start"][lang])
        lines = [f"{k + 1}. {r['camp']['title'][lang]}, {fmt_when(r['camp']['starts_at'], lang)}: {STATUS[r['status']][lang]}" for k, r in enumerate(regs[:4])]
        head = f"आपने {len(regs)} शिविर में रुचि दर्ज की है। " if lang == "hi" else f"You have registered interest in {len(regs)} camp(s). "
        return _r(head + " ".join(lines), cards=[{"type": "registrations", "items": [{"ref": r["ref"], "title": r["camp"]["title"][lang], "starts_at": r["camp"]["starts_at"],
                                                                                    "status": r["status"], "status_label": STATUS[r["status"]][lang]} for r in regs[:4]]}],
                  links=[{"label": "My DrishtiQ", "to": "/network/me"}], suggestions=[])

    if n == "find_camps":
        pin, q = i.args.get("pin"), i.args.get("q")
        if not pin and not q:
            return _r(t("ask_pin", lang), state={"awaiting": "pin"})
        try:
            res = tools.find_camps(pin, q)
        except HTTPException:
            return _r(t("bad_pin", lang), state={"awaiting": "pin"})
        items = res["items"]
        if not items:
            return _r(t("no_camps", lang), state={"awaiting": "pin", "camp_ids": None}, suggestions=SUGGEST["after_topic"][lang],
                      links=[{"label": {"hi": "आँखों की जानकारी", "en": "Eye-health info"}[lang], "to": "/network/learn"}])
        exact = res["exact"] if pin else len(items)
        if pin and exact:
            head = (f"मुझे PIN {pin} के लिए {exact} शिविर मिले।" if lang == "hi" else f"I found {exact} camp(s) for PIN {pin}.")
        elif pin:
            head = (f"इस PIN पर सीधे कोई शिविर नहीं मिला, पर आस-पास के क्षेत्र में {len(items)} मिले।" if lang == "hi"
                    else f"No camp is listed exactly at PIN {pin}, but I found {len(items)} in the nearby PIN region.")
        else:
            head = (f"'{q}' के लिए {len(items)} शिविर मिले।" if lang == "hi" else f"I found {len(items)} camp(s) for '{q}'.")
        shown = [c for c in items if c.get("match") == "exact"][:3] if (pin and exact) else items[:3]  # exact-PIN camps first; nearby ones only when there is no exact match
        lines = []
        for k, c in enumerate(shown):
            extra = f" ({STATE_WORD[c['state']][lang]})" if c["state"] != "open" else ""
            lines.append(f"{k + 1}. {camp_line(c, lang)}{extra}।" if lang == "hi" else f"{k + 1}. {camp_line(c, lang)}{extra}.")
        tail = "किसी के बारे में जानना हो या रुचि दर्ज करनी हो तो बताइए।" if lang == "hi" else "Tell me if you want details or to register interest in one."
        txt = " ".join([head, *lines, trust_note(shown, lang), tail]).replace("  ", " ")
        ids = [c["id"] for c in shown]
        new = {"pin": pin or state.get("pin"), "camp_ids": ids, "awaiting": None, "camp_id": None}
        links = [{"label": {"hi": "सभी शिविर देखें", "en": "See all camps"}[lang], "to": f"/network/camps?pin={pin}" if pin else f"/network/camps?q={q}"}]
        if state.get("want") == "register":
            opens = [c for c in shown if c["state"] == "open"]
            if len(opens) == 1:
                return _open_form(opens[0], lang, {**state, "pin": pin}, user)
            new.update(awaiting="camp_choice")
            txt += " " + t("pick_camp", lang)
        return _r(txt, cards=_camps_card(shown, lang), links=links, state=new, suggestions=SUGGEST["after_camps"][lang])

    if n in ("choose_camp", "camp_details", "camp_price", "start_registration"):
        cid = i.args.get("camp_id") or state.get("camp_id") or ui.get("camp_id")
        ids = state.get("camp_ids") or []
        if cid is None and len(ids) == 1:
            cid = ids[0]
        if cid is None:
            if n == "start_registration":
                if ids:
                    camps = [tools.get_camp_details(x) for x in ids]
                    return _r(t("pick_camp", lang), cards=_camps_card(camps, lang), state={"want": "register", "awaiting": "camp_choice"}, suggestions=[])
                return _r(t("no_camp_context", lang), state={"want": "register", "awaiting": "pin"})
            return _r(t("no_camp_context", lang), state={"awaiting": "pin"})
        camp = tools.get_camp_details(int(cid))
        if n == "start_registration" or (n == "choose_camp" and state.get("want") == "register"):
            if camp["state"] != "open":
                return _r(t("camp_closed", lang), cards=_camps_card([camp], lang), suggestions=SUGGEST["after_topic"][lang])
            return _open_form(camp, lang, state, user)
        if n == "camp_price":
            txt = (f"फ़ीस: {camp['price']}।" if lang == "hi" else f"Fee: {camp['price']}.") if camp["price"] else t("price_none", lang)
            return _r(txt, cards=_camps_card([camp], lang), state={"camp_id": camp["id"]}, suggestions=SUGGEST["after_camps"][lang])
        p = camp["place"]
        txt = (f"{camp['title'][lang]}। तारीख और समय: {fmt_when(camp['starts_at'], lang)}। जगह: {p['village'] or p['label']}, {p['district']}, PIN {p['pin']}। आयोजक: {camp['organiser']['name']}। "
               if lang == "hi" else
               f"{camp['title'][lang]}. When: {fmt_when(camp['starts_at'], lang)}. Where: {p['village'] or p['label']}, {p['district']}, PIN {p['pin']}. Organiser: {camp['organiser']['name']}. ")
        txt += trust_note([camp], lang)
        links = [{"label": {"hi": "पूरी जानकारी", "en": "Full details"}[lang], "to": f"/network/camps/{camp['id']}"}]
        return _r(txt.strip(), cards=_camps_card([camp], lang), links=links, state={"camp_id": camp["id"], "awaiting": None}, suggestions=SUGGEST["after_camps"][lang])

    return _r(t("unknown", lang))
