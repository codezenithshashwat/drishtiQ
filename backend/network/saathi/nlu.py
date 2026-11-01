"""Deterministic understanding of Hindi (Devanagari), Hinglish (Roman Hindi) and English requests. Always available;
needs no model and no network. Also used to sanity-check anything a provider suggests."""
import re
from dataclasses import dataclass, field

_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

DIGIT_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "shunya": "0", "ek": "1", "teen": "3", "char": "4", "chaar": "4", "paanch": "5", "panch": "5", "chhe": "6", "chhah": "6", "cheh": "6",
    "saat": "7", "aath": "8", "nau": "9", "sifar": "0", "sifr": "0", "chaar": "4", "chah": "6", "chha": "6",
    "शून्य": "0", "एक": "1", "तीन": "3", "चार": "4", "पांच": "5", "पाँच": "5", "छह": "6", "छः": "6", "छे": "6", "सात": "7", "आठ": "8", "नौ": "9",
    "सिफ़र": "0", "सिफर": "0", "शुन्य": "0", "ज़ीरो": "0", "जीरो": "0", "वन": "1", "टू": "2", "थ्री": "3", "फ़ोर": "4", "फोर": "4", "फ़ाइव": "5",
    "फाइव": "5", "सिक्स": "6", "सेवन": "7", "एट": "8", "नाइन": "9",
}
# Words that are also ordinary words ('kar do', 'go to'): they count only next to other digits, and are dropped again
# from either end of a run when that is what makes it six digits.
AMBIGUOUS_DIGITS = {"do": "2", "दो": "2", "to": "2", "too": "2", "for": "4", "ate": "8", "o": "0", "oh": "0"}
REPEAT = {"double": 2, "triple": 3, "डबल": 2, "ट्रिपल": 3}  # Indian English: "four five two double zero one"

HINGLISH = {
    "mujhe", "mera", "meri", "mere", "hai", "hain", "hoon", "karna", "karni", "karwani", "karwana", "karo", "kijiye", "kijiyega", "aankhon", "aankh",
    "jaanch", "janch", "jach", "gaon", "gav", "gaanv", "batao", "bataiye", "bataye", "kya", "kaise", "kahan", "kahaan", "nahi", "nahin", "haan",
    "chahiye", "chahta", "chahti", "dikhao", "dikhaiye", "madad", "shivir", "paas", "mein", "main", "aap", "apna", "apne", "kitna", "kab", "kaun",
    "kyon", "kyun", "zaruri", "zaroori", "jaruri", "kripya", "dhanyavad", "shukriya", "namaste", "namaskar", "bhasha", "bolo", "boliye", "samajh",
    "sugar", "madhumeh", "panjikaran", "tarikh", "pehla", "pehle", "doosra", "teesra", "iske", "uske", "wala", "wali", "maine", "humare", "hamare",
    "shaher", "shahar", "ilaj", "dawai", "dawa", "badal", "angrezi", "sakte", "sakti", "sakta", "puchna", "poochna", "jankari", "jaankari",
}
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


@dataclass
class Intent:
    name: str
    args: dict = field(default_factory=dict)
    lang: str | None = None      # language of the user's words, when it can be told
    source: str = "rules"


def normalise(text: str) -> str:
    t = text.translate(_DEV_DIGITS).lower()
    t = re.sub(r"[^\w\sऀ-ॿ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def detect_language(text: str, default: str = "hi") -> str:
    t = normalise(text)
    if not t or not re.search(r"[a-zऀ-ॿ]", t):
        return default  # digits only: keep the current language
    if DEVANAGARI.search(t):
        return "hi"
    words = set(t.split())
    return "hi" if words & HINGLISH else "en"


def _digit(tk: str) -> str | None:
    return tk if tk.isdigit() else DIGIT_WORDS.get(tk)


def extract_pin(text: str) -> str | None:
    """6-digit PIN written as digits ('453331', '453 331', '45 20 01', '४५३३३१') or spoken ('four five three three three
    one', 'char paanch do shunya shunya ek', 'four five two double zero one')."""
    toks = normalise(text).split()
    runs: list[list[tuple[str, bool]]] = []  # (digits, came from an ambiguous word)
    run: list[tuple[str, bool]] = []
    repeat = 0
    for k, tk in enumerate(toks):
        if tk in REPEAT:
            repeat = REPEAT[tk]
            continue
        d, amb = _digit(tk), False
        if d is None and tk in AMBIGUOUS_DIGITS:
            nxt = toks[k + 1] if k + 1 < len(toks) else ""
            if run or _digit(nxt) is not None or nxt in REPEAT:  # ambiguous words count only next to real digits
                d, amb = AMBIGUOUS_DIGITS[tk], True
        if d is not None:
            run.extend([(d, amb)] * (repeat if repeat and len(d) == 1 else 1))
        else:
            if run:
                runs.append(run)
            run = []
        repeat = 0
    if run:
        runs.append(run)
    for r in runs:
        for lo, hi in ((0, len(r)), (1, len(r)), (0, len(r) - 1), (1, len(r) - 1)):  # whole run, then without an ambiguous end
            if (lo == 1 and not r[0][1]) or (hi == len(r) - 1 and not r[-1][1]):
                continue
            s = "".join(d for d, _ in r[lo:hi])
            if len(s) == 6:
                return s
    return None


def _has(t: str, *needles: str) -> bool:
    return any(n in t for n in needles)


def _words(t: str) -> set[str]:
    return set(t.split())


ORDINALS = {"pehla": 0, "pehle": 0, "pahla": 0, "pehli": 0, "pahli": 0, "first": 0, "1st": 0, "पहला": 0, "पहले": 0, "पहली": 0,
            "doosra": 1, "dusra": 1, "doosre": 1, "dusre": 1, "doosri": 1, "dusri": 1, "second": 1, "2nd": 1, "दूसरा": 1, "दूसरे": 1, "दूसरी": 1,
            "teesra": 2, "tisra": 2, "teesre": 2, "teesri": 2, "tisri": 2, "third": 2, "3rd": 2, "तीसरा": 2, "तीसरे": 2, "तीसरी": 2}
YES = {"haan", "han", "haa", "ha", "haanji", "ji", "jee", "yes", "yeah", "yep", "yup", "ok", "okay", "sure", "bilkul", "zaroor", "zarur", "jarur",
       "theek", "thik", "please", "हाँ", "हां", "हा", "जी", "ठीक", "बिल्कुल", "बिलकुल", "ज़रूर", "जरूर", "ओके"}
NO = {"nahi", "nahin", "nhi", "na", "no", "nope", "नहीं", "नही", "ना"}
# Words that may accompany a yes/no without changing it. A sentence with any other word ('nahi dikhta') is not a yes/no.
FILLER = {"ji", "abhi", "bhi", "please", "kripya", "khojiye", "khojo", "dhundho", "dhoondho", "dhundhiye", "search", "find", "look", "karo", "kijiye",
          "dijiye", "hai", "a", "an", "the", "me", "for", "it", "now", "not", "later", "baad", "mein", "camp", "camps", "shivir", "jaanch", "thanks",
          "thank", "you", "do", "that", "sir", "madam", "अभी", "भी", "खोजिए", "खोजें", "ढूँढिए", "ढूंढिए", "कीजिए", "करो", "है", "बाद", "में", "शिविर", "जाँच",
          "जांच", "कृपया", "धन्यवाद"}

# Symptoms that need care now, not a future camp. Checked before anything else; Saathi never diagnoses them.
_SUDDEN = ("अचानक", "एकदम से", "achanak", "achaanak", "ekdam se", "sudden", "all of a sudden")
_SIGHT = ("दिख", "नज़र", "नजर", "रोशनी", "धुंध", "धुँध", "अंधेर", "अँधेर", "dikh", "nazar", "najar", "roshni", "dhundh", "andher",
          "vision", "sight", "see", "blind", "blur", "dark")
_URGENT = ("दिखना बंद", "दिखाई देना बंद", "दिखाई नहीं दे रहा", "दिखाई नहीं दे रही", "कुछ नहीं दिख", "कुछ भी नहीं दिख", "रोशनी चली", "पर्दा सा", "पर्दा जैसा",
           "dikhna band", "dikhai dena band", "dikhai nahi de", "kuch nahi dikh", "kuchh nahi dikh", "kuch bhi nahi dikh", "roshni chali", "parda sa",
           "parda jaisa", "can t see anything", "cant see anything", "cannot see anything", "can t see at all", "cannot see at all", "lost my vision", "lost my sight", "loss of vision", "vision loss",
           "lost vision", "went blind", "gone blind", "curtain", "flashes of light", "flashing lights", "shower of floaters",
           "आँख में चोट", "आंख में चोट", "आँख पर चोट", "आंख पर चोट", "aankh mein chot", "aankh me chot", "aankh par chot", "eye injury", "injured my eye",
           "hit in the eye", "hit my eye", "chemical", "केमिकल", "तेज़ाब", "तेजाब", "tezab", "acid", "चूना", "chuna",
           "तेज़ दर्द", "तेज दर्द", "बहुत दर्द", "असहनीय दर्द", "tez dard", "bahut dard", "severe pain", "severe eye pain", "terrible eye pain")
_NON_URGENT = ("धुंधला", "धुँधला", "कम दिख", "नहीं दिख", "ठीक से नहीं", "dhundhla", "dhundla", "kam dikh", "nahi dikh", "nahin dikh", "theek se nahi",
               "blurry", "blurred", "blurring", "weak eyesight", "poor eyesight", "can t see well", "cannot see well")


def is_urgent(t: str) -> bool:
    return _has(t, *_URGENT) or (_has(t, *_SUDDEN) and _has(t, *_SIGHT))


def is_screening_question(t: str) -> bool:
    """'Should I get my eyes checked?' -- but not 'where is a camp?' and not 'why does screening matter?'."""
    eye_or_dm = _has(t, "आँख", "आंख", "नेत्र", "रेटिना", "aankh", "ankh", "netra", "retina", "eye", "डायबिटीज", "डायबिटीज़", "मधुमेह", "शुगर",
                     "diabetes", "diabetic", "madhumeh", "sugar")
    check = _has(t, "जाँच", "जांच", "चेक", "टेस्ट", "jaanch", "janch", "jach", "check", "test", "screening", "examin")
    ask = _has(t, "चाहिए", "ज़रूरी", "जरूरी", "करवा लूँ", "करवा लूं", "करा लूँ", "करा लूं", "chahiye", "zaruri", "zaroori", "jaruri", "karwa lun",
               "karwa loon", "kara lun", "should", "do i need", "need to", "necessary", "is it needed", "required")
    why = _has(t, "क्यों", "kyon", "kyun", "kyu ", "why")
    where = _has(t, "camp", "shivir", "शिविर", "कैंप", "kahan", "kahaan", "कहाँ", "कहां", "where", "near", "paas", "पास", "gaon", "गाँव", "गांव", "village")
    return eye_or_dm and check and ask and not why and not where


def route(text: str, state: dict, ui: dict, default_lang: str = "hi") -> Intent:
    """Map one utterance to an allowlisted intent. `state` is what the previous turn returned (awaiting, camp_ids, ...)."""
    t = normalise(text)
    lang = detect_language(text, state.get("lang") or default_lang)
    w = _words(t)
    pin = extract_pin(text)
    awaiting = state.get("awaiting")
    ids = state.get("camp_ids") or []

    if not t:
        return Intent("unknown", lang=lang)

    # safety first: a possible emergency is never redirected to a future camp
    if is_urgent(t):
        return Intent("urgent_symptom", lang=lang)

    # choosing one of the camps just shown ("pehla wala", "doosri", "number 2", "2 wala")
    if ids and (w & set(ORDINALS) or re.search(r"(?:^|\s)(?:number|no|नंबर|नम्बर)\s*[1-5](?:\s|$)", t)
                or re.search(r"(?:^|\s)[1-5]\s*(?:wala|wali|wale|वाला|वाली|वाले)(?:\s|$)", t) or (awaiting == "camp_choice" and re.fullmatch(r"[1-5]", t))):
        idx = next((ORDINALS[x] for x in t.split() if x in ORDINALS), None)
        if idx is None:
            m = re.search(r"([1-5])", t)
            idx = int(m.group(1)) - 1 if m else 0
        if idx < len(ids):
            return Intent("choose_camp", {"camp_id": ids[idx]}, lang)

    # a short yes / no that answers Saathi's last question ("हाँ", "haan ji", "नहीं, अभी नहीं", "Yes, find a camp")
    if not pin and w <= YES | NO | FILLER and w & (YES | NO):
        if w & NO:
            return Intent("decline", lang=lang)
        if awaiting in ("confirm_find", "pin"):
            return Intent("find_camps", {"q": None}, lang)
        if awaiting == "camp_choice" and len(ids) == 1:
            return Intent("choose_camp", {"camp_id": ids[0]}, lang)
        return Intent("affirm", lang=lang)

    if pin and not _has(t, "phone", "mobile", "number dena"):
        return Intent("find_camps", {"pin": pin}, lang)

    # "I have diabetes but see fine; should I get my eyes checked?" -> general awareness plus an offer to find a camp
    if is_screening_question(t):
        return Intent("screening_question", lang=lang)

    # individual medical questions and non-urgent symptoms are never answered; Saathi points to a doctor
    if _has(t, *_NON_URGENT) or (_has(t, "diagnos", "medicine", "dawai", "dawa", "दवा", "दवाई", "इलाज", "ilaj", "treatment", "insulin", "surgery", "operation", "ऑपरेशन", "आपरेशन", "dose")
            or re.search(r"(mujhe|mere|mera|मुझे|मेरी|मेरे).*(retinopathy|रेटिनोपैथी|andhapan|अंधापन|bimari|बीमारी).*(hai|है|ho)", t)
            or re.search(r"\bdo i have\b|\bam i going blind\b|क्या मुझे", t)):
        return Intent("medical_advice", lang=lang)

    # language
    if _has(t, "hindi", "हिंदी", "हिन्दी", "english", "अंग्रेज", "angrezi", "इंग्लिश") and (
            _has(t, "badal", "बदल", "kar do", "karo", "kijiye", "switch", "change", "speak", "bolo", "mein baat", "में बात", "me baat", "language", "bhasha", "भाषा", "बोलो") or len(w) <= 2):
        target = "en" if _has(t, "english", "अंग्रेज", "angrezi", "इंग्लिश") else "hi"
        return Intent("set_language", {"lang": target}, target)

    # signed-in features
    if _has(t, "meri profile", "mera profile", "my profile", "profile dikhao", "profile", "प्रोफ़ाइल", "प्रोफाइल", "my details", "meri jaankari", "meri jankari"):
        return Intent("show_profile", lang=lang)
    if _has(t, "maine kis camp", "maine kis", "kaun se camp", "kis camp", "my registration", "my registrations", "mere registration", "meri registration",
            "registration status", "मैंने किस", "मेरा पंजीकरण", "मेरे पंजीकरण", "my interest", "kya registration kiya"):
        return Intent("list_my_registrations", lang=lang)

    if _has(t, "requirement", "kya kya chahiye", "kya chahiye", "documents", "what do i need", "क्या चाहिए", "कौन से दस्तावेज़", "दस्तावेज"):
        return Intent("requirements", lang=lang)

    if _has(t, "register", "registration", "panjikaran", "पंजीकरण", "रजिस्टर", "naam likh", "नाम लिख", "sign me up", "interest darj", "darj karna", "रुचि दर्ज") \
            and not _has(t, "my registration", "mere registration", "meri registration"):
        return Intent("start_registration", lang=lang)

    # awareness
    if _has(t, "myth", "bhram", "भ्रम", "galat dharna", "गलतफहमी"):
        return Intent("explain", {"topic": "myths-facts"}, lang)
    if _has(t, "diabetic retinopathy", "retinopathy", "रेटिनोपैथी", "dr kya"):
        return Intent("explain", {"topic": "what-is-dr"}, lang)
    if _has(t, "kyon zaruri", "kyun zaruri", "kyon zaroori", "kyun zaroori", "kyu zaruri", "why screening", "why is screening", "why important", "why do i need",
            "kyon karwani", "kyun karwani", "क्यों ज़रूरी", "क्यों जरूरी", "जाँच क्यों", "जांच क्यों", "importance", "zaruri kyu", "zaroori kyon"):
        return Intent("explain", {"topic": "why-screening"}, lang)
    if _has(t, "what happens", "kya hota hai", "kaise hoti", "process", "प्रक्रिया", "क्या होता", "कैसे होती", "painless", "dard") and _has(t, "jaanch", "janch", "screening", "check", "जाँच", "जांच", "test", "hota", "happens", "होता", "process", "प्रक्रिया"):
        return Intent("explain", {"topic": "what-happens"}, lang)
    if _has(t, "next step", "aage kya", "आगे क्या", "अगला कदम", "what should i do", "kya karun", "क्या करूं", "क्या करूँ"):
        return Intent("explain", {"topic": "next-steps"}, lang)
    if _has(t, "diabetes", "madhumeh", "मधुमेह", "डायबिटीज", "sugar", "शुगर", "देखभाल", "eye care" ):
        return Intent("explain", {"topic": "diabetes-and-eyes"}, lang)
    if _has(t, "drishtiq", "drishti q", "दृष्टि", "what is this", "kya hai ye", "ye kya hai", "yeh kya hai", "about this", "tell me about", "what do you do", "kya karta", "iske baare"):
        return Intent("about", lang=lang)

    # camps
    eye = _has(t, "aankh", "aankhon", "आँख", "आंख", "eye", "netra", "नेत्र", "nazar")
    test = _has(t, "jaanch", "janch", "jach", "जाँच", "जांच", "test", "check", "screening", "camp", "shivir", "शिविर", "कैंप", "शिबिर")
    if (eye and test) or _has(t, "camp", "shivir", "शिविर", "कैंप", "screening", "near me", "nearby", "paas mein", "पास में", "gaon mein", "गाँव में", "गांव में", "my village", "mere gaon"):
        return Intent("find_camps", {"q": None}, lang)

    # price / details about the camp in context
    if _has(t, "kitna paisa", "kitne paise", "fees", "fee", "cost", "price", "kharcha", "free", "मुफ्त", "मुफ़्त", "कीमत", "शुल्क", "kitna lagega", "कितना"):
        return Intent("camp_price", {"camp_id": state.get("camp_id") or ui.get("camp_id") or (ids[0] if len(ids) == 1 else None)}, lang)
    if _has(t, "details", "detail", "iske baare", "kab hai", "kahan hai", "kahaan", "tarikh", "date", "when", "where", "समय", "कब", "कहाँ", "कहां", "तारीख", "jankari do") and (ids or state.get("camp_id") or ui.get("camp_id")):
        return Intent("camp_details", {"camp_id": state.get("camp_id") or ui.get("camp_id") or (ids[0] if ids else None)}, lang)

    # navigation
    nav = [("login", ("login", "log in", "sign in", "लॉगिन", "लॉग इन")), ("signup", ("signup", "sign up", "account banao", "account banana", "खाता", "साइन अप")),
           ("learn", ("learn", "awareness", "seekhna", "सीखना", "जानकारी पढ़")), ("home", ("home", "ghar", "घर", "main page", "homepage")),
           ("me", ("my drishtiq", "mera dashboard", "dashboard", "मेरा खाता")), ("camps", ("camps list", "all camps", "camp list", "सभी शिविर"))]
    for target, keys in nav:
        if _has(t, *keys):
            return Intent("navigate", {"target": target}, lang)

    if _has(t, "thank", "dhanyavad", "shukriya", "धन्यवाद", "शुक्रिया", "bahut accha", "bahut achha"):
        return Intent("thanks", lang=lang)
    if _has(t, "bye", "alvida", "अलविदा", "phir milte", "tata"):
        return Intent("bye", lang=lang)
    if w & {"hello", "hi", "hey", "namaste", "namaskar", "नमस्ते", "नमस्कार", "pranam", "प्रणाम", "hii", "helo"}:
        return Intent("greet", lang=lang)
    if _has(t, "help", "madad", "मदद", "kya kar sakti", "kya kar sakte", "what can you do", "kya kya", "क्या कर सकती"):
        return Intent("help", lang=lang)
    # a bare place name while we are waiting for one
    if awaiting == "pin" and 1 <= len(w) <= 4:
        return Intent("find_camps", {"q": text.strip()[:40]}, lang)
    return Intent("unknown", lang=lang)
