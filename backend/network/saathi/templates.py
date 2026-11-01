"""Hindi/English response templates. Facts (camps, dates, statuses, profile) are always rendered here from database
results; a language model never writes them. Hindi is in Devanagari so device voices read it correctly.
Persona wording is feminine in Hindi, matching the brief's example ('main madad karti hoon')."""
from datetime import datetime

MONTHS_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
STATUS = {
    "interest_received": {"hi": "रुचि दर्ज हुई (पुष्टि बाकी)", "en": "Interest received (not yet confirmed)"},
    "contacted": {"hi": "आयोजक ने संपर्क किया", "en": "Organiser has contacted you"},
    "confirmed_by_organiser": {"hi": "आयोजक द्वारा पुष्टि", "en": "Confirmed by organiser"},
    "attended": {"hi": "शामिल हुए", "en": "Attended"},
    "no_show": {"hi": "शामिल नहीं हुए", "en": "Did not attend"},
    "cancelled": {"hi": "रद्द", "en": "Cancelled"},
}
STATE_WORD = {"open": {"hi": "रुचि दर्ज हो सकती है", "en": "taking interest"}, "full": {"hi": "सूची भर चुकी है", "en": "interest list full"},
              "closed": {"hi": "पंजीकरण बंद", "en": "closed"}, "expired": {"hi": "समाप्त", "en": "ended"}, "cancelled": {"hi": "रद्द", "en": "cancelled"}}
LANG_NAME = {"hi": {"hi": "हिंदी", "en": "Hindi"}, "en": {"hi": "अंग्रेज़ी", "en": "English"}}


def fmt_when(iso: str, lang: str) -> str:
    d = datetime.fromisoformat(iso)
    if lang == "hi":
        h = d.hour
        period = "सुबह" if h < 12 else "दोपहर" if h < 16 else "शाम" if h < 19 else "रात"
        h12 = h % 12 or 12
        return f"{d.day} {MONTHS_HI[d.month - 1]}, {period} {h12} बजे"
    return f"{d.day} {MONTHS_EN[d.month - 1]}, {d.strftime('%I:%M %p').lstrip('0')}"


def camp_line(c: dict, lang: str) -> str:
    p = c["place"]
    where = p["village"] or p["label"]
    return f"{c['title'][lang]}, {fmt_when(c['starts_at'], lang)}, {where}, {p['district']}"


def trust_note(items: list[dict], lang: str) -> str:
    if all(i["verification"] == "simulated" for i in items):
        return ("ये प्रदर्शन के लिए बनाए गए नमूना शिविर हैं, असली सेवाएँ नहीं।" if lang == "hi"
                else "These are demonstration camps made for this prototype, not real services.")
    if any(i["verification"] == "simulated" for i in items):
        return ("इनमें कुछ नमूना शिविर हैं, असली नहीं।" if lang == "hi" else "Some of these are demonstration camps, not real services.")
    if any(i["verification"] == "unverified" for i in items):
        return ("इन शिविरों की अभी पुष्टि नहीं हुई है, इसलिए आयोजक से जाँच कर लें।" if lang == "hi"
                else "These camps are not verified yet, so please check with the organiser.")
    return ""


T = {
    "greet": {"hi": "नमस्ते! मैं दृष्टि साथी हूँ। मैं आँखों की जाँच शिविर खोजने, जानकारी समझाने और रुचि दर्ज कराने में मदद कर सकती हूँ। आप क्या जानना चाहेंगे?",
              "en": "Hello! I'm Saathi. I can help you find eye screening camps, explain eye-health basics, and register your interest. What would you like to do?"},
    "help": {"hi": "मैं पास के जाँच शिविर खोज सकती हूँ, डायबिटीज़ और आँखों की जानकारी समझा सकती हूँ, रुचि दर्ज करा सकती हूँ, और भाषा बदल सकती हूँ। आप PIN कोड बता सकते हैं।",
             "en": "I can find nearby screening camps, explain diabetes and eye health, help you register your interest, and switch language. You can just tell me your PIN code."},
    "about": {"hi": "दृष्टि क्यू एक शोध प्रोटोटाइप है। इसका AI भाग आँख की तस्वीर देखकर डॉक्टर की मदद करता है, और यह नेटवर्क लोगों को जाँच शिविरों और जानकारी से जोड़ता है। मैं साथी हूँ, एक AI सहायक। यह कोई सरकारी योजना या चालू अस्पताल सेवा नहीं है।",
              "en": "DrishtiQ is a research prototype. Its AI part helps doctors review eye pictures, and this Network connects people with screening camps and information. I'm Saathi, an AI helper. This is not a government programme or a running hospital service."},
    "thanks": {"hi": "आपका स्वागत है! कुछ और पूछना हो तो बताइए।", "en": "You're welcome! Ask me anything else you need."},
    "bye": {"hi": "ठीक है, ध्यान रखिए। जब चाहें मुझसे फिर बात करें।", "en": "Take care. Talk to me whenever you like."},
    "ask_pin": {"hi": "बिल्कुल, मैं मदद करती हूँ। अपना 6 अंकों का PIN कोड बताइए, या अपने गाँव या शहर का नाम।",
                "en": "Of course. Please tell me your 6-digit PIN code, or the name of your village or town."},
    "screening_answer": {
        "hi": "हाँ, यह एक अच्छा सवाल है। डायबिटीज़ होने पर आँख के अंदर के पर्दे (रेटिना) में बदलाव तब भी शुरू हो सकते हैं, जब दिखाई बिल्कुल ठीक देता हो। "
              "इसलिए डायबिटीज़ वाले लोगों को सलाह दी जाती है कि कोई परेशानी न होने पर भी डॉक्टर के बताए अनुसार नियमित आँखों की जाँच कराएँ। "
              "यह सामान्य जानकारी है, आपकी जाँच का नतीजा नहीं। क्या मैं आपके पास आँखों की जाँच ढूँढूँ?",
        "en": "That's a good question. With diabetes, changes inside the eye (in the retina) can begin even while your vision feels completely normal. "
              "That is why people with diabetes are advised to have regular eye checks, as their doctor recommends, even without any problems. "
              "This is general information, not a result about your eyes. Shall I look for an eye check near you?"},
    "urgent": {
        "hi": "यह ज़रूरी हो सकता है। अचानक दिखना कम या बंद होना, आँख में चोट, कोई रसायन जाना, तेज़ दर्द, या आँख के आगे पर्दा-सा आना — ऐसे में जाँच शिविर का "
              "इंतज़ार न करें। कृपया आज ही, जितनी जल्दी हो सके, किसी नेत्र अस्पताल या नज़दीकी अस्पताल की आपातकालीन सेवा में जाएँ। आपात स्थिति में 112 पर कॉल करें। "
              "मैं बीमारी की पहचान नहीं कर सकती, यह डॉक्टर ही बता सकते हैं।",
        "en": "This could be urgent. Sudden loss or dimming of vision, an eye injury, a chemical in the eye, severe pain, or a curtain or shadow over your "
              "sight should not wait for a screening camp. Please go to an eye hospital or the emergency department of the nearest hospital today, as soon "
              "as you can. In an emergency, call 112. I can't tell what is causing it; only a doctor can."},
    "declined": {"hi": "ठीक है। जब भी चाहें, मुझसे पास का जाँच शिविर खोजने को कहिए। तब तक आप डायबिटीज़ और आँखों के बारे में पढ़ सकते हैं।",
                 "en": "Okay. Whenever you like, just ask me to find a nearby screening camp. Meanwhile you can read about diabetes and your eyes."},
    "searching": {"hi": "मैं इस PIN कोड के आस-पास के शिविर देखती हूँ।", "en": "Let me check camps around this PIN code."},
    "bad_pin": {"hi": "PIN कोड में 6 अंक होते हैं। कृपया फिर से बताइए।", "en": "A PIN code has 6 digits. Please say it again."},
    "no_camps": {"hi": "माफ़ कीजिए, इस जगह के आस-पास मुझे कोई सत्यापित शिविर नहीं मिला। मैं अपने मन से कोई शिविर नहीं बता सकती। आप दूसरा PIN या ज़िले का नाम बताएँ, या आँखों की जानकारी पढ़ सकते हैं।",
                 "en": "Sorry, I couldn't find any camps listed near that place. I can't make up a camp. You can try another PIN code or district, or read the eye-health information."},
    "medical": {"hi": "मैं बीमारी की पहचान या दवा-इलाज की सलाह नहीं दे सकती। इसके लिए कृपया नेत्र चिकित्सक या अपने डॉक्टर से मिलें। अगर अचानक दिखना कम हुआ है या आँख में तेज़ दर्द है, तो तुरंत डॉक्टर के पास जाएँ। चाहें तो मैं पास का जाँच शिविर खोज दूँ।",
                "en": "I can't diagnose conditions or advise on medicines or treatment. Please see an eye doctor or your own doctor. If your vision suddenly drops or you have strong eye pain, see a doctor right away. I can look for a nearby screening camp if you like."},
    "unknown": {"hi": "माफ़ कीजिए, मैं ठीक से समझ नहीं पाई। आप कह सकते हैं: \"मुझे अपने गाँव में आँखों की जाँच करानी है\", या \"डायबिटीज़ और आँखों के बारे में बताइए\"।",
                "en": "Sorry, I didn't quite get that. You can say: \"I want an eye check in my village\" or \"tell me about diabetes and eyes\"."},
    "login_needed": {"hi": "यह जानकारी देखने के लिए पहले लॉग इन करना होगा। बिना लॉग इन के भी आप शिविर खोज सकते हैं और रुचि दर्ज कर सकते हैं।",
                     "en": "You need to log in to see this. You can still find camps and register interest without logging in."},
    "no_regs": {"hi": "आपने अभी कोई शिविर में रुचि दर्ज नहीं की है।", "en": "You haven't registered interest in any camp yet."},
    "pick_camp": {"hi": "आप किस शिविर के लिए रुचि दर्ज करना चाहते हैं? पहला, दूसरा या तीसरा बताइए।", "en": "Which camp would you like to register interest in? Say first, second or third."},
    "no_camp_context": {"hi": "पहले मैं आपके पास का शिविर खोजती हूँ। अपना गाँव या PIN कोड बताइए।", "en": "Let me find a camp near you first. Please tell me your village or PIN code."},
    "form_open": {"hi": "ठीक है, मैंने रुचि दर्ज करने का फ़ॉर्म खोल दिया है। जानकारी जाँचकर 'पुष्टि करें' दबाइए। ध्यान रहे, यह सिर्फ़ रुचि दर्ज करना है, पक्का अपॉइंटमेंट नहीं।",
                  "en": "Okay, I've opened the interest form. Check the details and press Confirm. Remember, this only records your interest; it is not a confirmed appointment."},
    "camp_closed": {"hi": "माफ़ कीजिए, इस शिविर में अभी रुचि दर्ज नहीं हो सकती।", "en": "Sorry, this camp is not taking interest right now."},
    "price_none": {"hi": "इस शिविर की फ़ीस की पुष्टि हुई जानकारी मेरे पास नहीं है, इसलिए मैं कुछ नहीं बता सकती। कृपया आयोजक से पूछें।",
                   "en": "I don't have verified fee information for this camp, so I can't say. Please ask the organiser."},
    "lang_set": {"hi": "ठीक है, अब मैं हिंदी में बात करूँगी।", "en": "Okay, I'll speak English now."},
    "navigating": {"hi": "ठीक है, मैं आपको वहाँ ले चलती हूँ।", "en": "Sure, taking you there."},
    "requirements": {"hi": "रुचि दर्ज करने के लिए नाम, PIN कोड और सहमति चाहिए। फ़ोन नंबर या ईमेल देना आपकी मर्ज़ी है।", "en": "To register interest I need a name, PIN code and your consent. A phone number or email is optional."},
}

SUGGEST = {
    "start": {"hi": ["मुझे अपने गाँव में आँखों की जाँच करानी है", "डायबिटीज़ और आँखें", "जाँच क्यों ज़रूरी है?"], "en": ["Find an eye camp near me", "Diabetes and eyes", "Why is screening important?"]},
    "after_camps": {"hi": ["पहले शिविर के बारे में बताइए", "रुचि दर्ज करनी है", "फ़ीस कितनी है?"], "en": ["Tell me about the first camp", "I want to register interest", "What is the fee?"]},
    "after_topic": {"hi": ["मेरे पास का शिविर खोजिए", "भ्रम और सच", "जाँच में क्या होता है?"], "en": ["Find a camp near me", "Myths and facts", "What happens at a screening?"]},
    "login": {"hi": ["लॉग इन खोलिए", "शिविर खोजिए"], "en": ["Open log in", "Find a camp"]},
    "confirm": {"hi": ["हाँ, जाँच खोजिए", "नहीं, अभी नहीं"], "en": ["Yes, find a camp", "No, not now"]},
}


def t(key: str, lang: str, **kw) -> str:
    s = T[key][lang if lang in ("hi", "en") else "hi"]
    return s.format(**kw) if kw else s
