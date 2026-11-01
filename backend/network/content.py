"""Awareness content (Hindi/English). Every item carries a review_status.

IMPORTANT: nothing here has been clinically reviewed yet, so every topic is marked "illustrative". Before real use an
ophthalmologist / diabetologist must review and sign off (see docs in drishtiQ_network.md, risk table). The wording is
deliberately general and gives no individual medical advice.
"""

VERSION = "2026-11-01"

TOPICS = [
    {
        "slug": "what-is-dr", "icon": "eye",
        "title": {"hi": "डायबिटिक रेटिनोपैथी क्या है?", "en": "What is diabetic retinopathy?"},
        "summary": {
            "hi": "डायबिटीज़ यानी मधुमेह में आँख के पीछे की पतली नसें खराब हो सकती हैं। इसे डायबिटिक रेटिनोपैथी कहते हैं। शुरू में अक्सर कोई तकलीफ़ नहीं होती।",
            "en": "With diabetes, the tiny blood vessels at the back of the eye can get damaged. This is called diabetic retinopathy. Early on, there are often no symptoms.",
        },
        "blocks": {
            "hi": [
                {"h": "आँख का पर्दा", "p": "आँख के पीछे एक पतला पर्दा होता है जिसे रेटिना कहते हैं। यह रोशनी को पहचान कर दिमाग तक पहुँचाता है।"},
                {"h": "शुगर का असर", "p": "लंबे समय तक शुगर ज़्यादा रहने से रेटिना की छोटी नसें कमज़ोर हो सकती हैं और उनसे रिसाव हो सकता है।"},
                {"h": "चुपचाप बढ़ने वाली बीमारी", "p": "शुरुआत में दिखाई ठीक रहता है, इसलिए कई लोगों को पता ही नहीं चलता। जाँच से इसे जल्दी पकड़ा जा सकता है।"},
            ],
            "en": [
                {"h": "The back of the eye", "p": "At the back of the eye is a thin layer called the retina. It senses light and sends signals to the brain."},
                {"h": "How sugar affects it", "p": "When blood sugar stays high for a long time, the retina's small blood vessels can weaken and leak."},
                {"h": "A silent condition", "p": "Early on, vision can seem normal, so many people do not know. A screening can find it early."},
            ],
        },
        "review_status": "illustrative",
    },
    {
        "slug": "why-screening", "icon": "shield",
        "title": {"hi": "जाँच क्यों ज़रूरी है?", "en": "Why does screening matter?"},
        "summary": {
            "hi": "शुरुआत में पकड़ में आने पर इलाज से आँखों की रोशनी बचाने में मदद मिल सकती है। जिन्हें डायबिटीज़ है, उन्हें डॉक्टर की सलाह के अनुसार नियमित आँख जाँच करानी चाहिए।",
            "en": "When it is found early, treatment can help protect eyesight. People with diabetes should have regular eye checks, as advised by their doctor.",
        },
        "blocks": {
            "hi": [
                {"h": "जल्दी पता चले तो बेहतर", "p": "नुकसान बढ़ने से पहले पता चलने पर डॉक्टर के पास कई विकल्प होते हैं।"},
                {"h": "दिखाई ठीक है, फिर भी जाँच", "p": "आँखें ठीक दिखें तब भी रेटिना में बदलाव हो सकते हैं। इसलिए सिर्फ़ लक्षणों का इंतज़ार न करें।"},
                {"h": "कितनी बार?", "p": "कितने समय पर जाँच करानी है, यह आपका डॉक्टर बताएगा। आमतौर पर डायबिटीज़ वालों को नियमित जाँच की सलाह दी जाती है।"},
            ],
            "en": [
                {"h": "Earlier is better", "p": "If it is found before much damage is done, doctors have more options."},
                {"h": "Seeing well is not enough", "p": "Changes can begin in the retina even when vision feels fine, so do not wait for symptoms."},
                {"h": "How often?", "p": "Your doctor will tell you how often to be checked. People with diabetes are usually advised to have regular checks."},
            ],
        },
        "review_status": "illustrative",
    },
    {
        "slug": "what-happens", "icon": "camera",
        "title": {"hi": "जाँच में क्या होता है?", "en": "What happens at a screening?"},
        "summary": {
            "hi": "एक विशेष कैमरे से आँख के पीछे की तस्वीर ली जाती है। यह दर्द रहित है और कुछ मिनट लगते हैं। तस्वीर को डॉक्टर देखते हैं; कंप्यूटर सिर्फ़ मदद करता है।",
            "en": "A special camera takes a picture of the back of your eye. It is painless and takes a few minutes. A doctor reviews the picture; the computer only assists.",
        },
        "blocks": {
            "hi": [
                {"h": "तस्वीर लेना", "p": "आपको कैमरे के सामने बैठकर सीधे देखना होता है। कभी-कभी पुतली बड़ी करने की बूँदें डाली जाती हैं।"},
                {"h": "दर्द नहीं", "p": "यह जाँच दर्द रहित है। बूँदों के बाद कुछ घंटे धुंधला दिख सकता है।"},
                {"h": "नतीजा कौन बताता है", "p": "तस्वीर डॉक्टर या प्रशिक्षित विशेषज्ञ देखते हैं। आगे क्या करना है, यह वही तय करते हैं।"},
            ],
            "en": [
                {"h": "Taking the picture", "p": "You sit in front of the camera and look straight ahead. Sometimes eye drops are used to widen the pupil."},
                {"h": "No pain", "p": "The check is painless. After the drops, vision may be blurry for a few hours."},
                {"h": "Who gives the result", "p": "A doctor or trained specialist reviews the picture and decides what to do next."},
            ],
        },
        "review_status": "illustrative",
    },
    {
        "slug": "myths-facts", "icon": "help",
        "title": {"hi": "भ्रम और सच", "en": "Myths and facts"},
        "summary": {
            "hi": "कई लोग मानते हैं कि दिखाई ठीक है तो आँखें ठीक हैं। यह हमेशा सच नहीं है। नीचे कुछ आम भ्रम और सच दिए हैं।",
            "en": "Many people believe that if they see well, their eyes are healthy. That is not always true. Below are some common myths and facts.",
        },
        "blocks": {
            "hi": [
                {"h": "भ्रम: दिखाई ठीक है तो चिंता की बात नहीं", "p": "सच: शुरुआती बदलाव अक्सर महसूस नहीं होते। जाँच ही उन्हें पकड़ पाती है।"},
                {"h": "भ्रम: चश्मे से यह ठीक हो जाएगा", "p": "सच: चश्मा नंबर ठीक करता है, रेटिना की नसों को हुए नुकसान को नहीं।"},
                {"h": "भ्रम: जाँच में तकलीफ़ होती है", "p": "सच: इसमें सिर्फ़ तस्वीर ली जाती है, कोई चीरा या दर्द नहीं।"},
                {"h": "भ्रम: यह सिर्फ़ बुज़ुर्गों को होता है", "p": "सच: डायबिटीज़ वाले किसी भी उम्र के व्यक्ति को हो सकता है।"},
            ],
            "en": [
                {"h": "Myth: if I see well, I need not worry", "p": "Fact: early changes are often not felt. Only a check can find them."},
                {"h": "Myth: glasses will fix it", "p": "Fact: glasses correct focus, not damage to the retina's blood vessels."},
                {"h": "Myth: the check hurts", "p": "Fact: it only takes a picture. There is no cut and no pain."},
                {"h": "Myth: only older people get it", "p": "Fact: a person with diabetes of any age can be affected."},
            ],
        },
        "review_status": "illustrative",
    },
    {
        "slug": "diabetes-and-eyes", "icon": "heart",
        "title": {"hi": "डायबिटीज़ और आँखों की देखभाल", "en": "Diabetes and caring for your eyes"},
        "summary": {
            "hi": "डॉक्टर की सलाह पर दवा, खानपान और नियमित जाँच से आँखों के जोखिम को कम करने में मदद मिलती है। अपनी दवा खुद बंद या बदलें नहीं।",
            "en": "Following your doctor's advice on medicines, food and regular checks can help lower the risk to your eyes. Do not stop or change medicines on your own.",
        },
        "blocks": {
            "hi": [
                {"h": "डॉक्टर की सलाह", "p": "शुगर और ब्लड प्रेशर की जाँच व दवा डॉक्टर के बताए अनुसार लें।"},
                {"h": "नियमित जाँच", "p": "आँख की नियमित जाँच भी इस देखभाल का हिस्सा है।"},
                {"h": "इन संकेतों पर तुरंत डॉक्टर को दिखाएँ", "p": "अचानक धुंधला दिखना, आँख के सामने काले धब्बे या दिखाई कम होना हो तो इंतज़ार न करें, किसी डॉक्टर से मिलें।"},
            ],
            "en": [
                {"h": "Your doctor's advice", "p": "Get your sugar and blood pressure checked and take medicines as your doctor says."},
                {"h": "Regular checks", "p": "A regular eye check is part of that care."},
                {"h": "See a doctor promptly if", "p": "you notice sudden blurring, dark spots in front of your eyes or loss of vision. Do not wait; see a doctor."},
            ],
        },
        "review_status": "illustrative",
    },
    {
        "slug": "next-steps", "icon": "route",
        "title": {"hi": "अगला कदम क्या है?", "en": "What to do next"},
        "summary": {
            "hi": "अपने पास का जाँच शिविर खोजें, अपनी रुचि दर्ज करें, और अपनी पुरानी रिपोर्ट व दवाओं की सूची साथ रखें। शिविर के आयोजक आपसे संपर्क कर सकते हैं।",
            "en": "Find a screening camp near you, register your interest, and keep your old reports and medicine list ready. The camp organiser may contact you.",
        },
        "blocks": {
            "hi": [
                {"h": "शिविर खोजें", "p": "अपना PIN कोड डालकर पास के शिविर देखें।"},
                {"h": "रुचि दर्ज करें", "p": "यह सिर्फ़ रुचि दर्ज करना है, अपॉइंटमेंट की पक्की पुष्टि नहीं। पुष्टि आयोजक करते हैं।"},
                {"h": "साथ ले जाएँ", "p": "पुरानी रिपोर्ट, चश्मा और दवाओं की सूची साथ रखें।"},
            ],
            "en": [
                {"h": "Find a camp", "p": "Enter your PIN code to see camps nearby."},
                {"h": "Register interest", "p": "This only records your interest. It is not a confirmed appointment; the organiser confirms."},
                {"h": "Bring with you", "p": "Old reports, glasses and a list of your medicines."},
            ],
        },
        "review_status": "illustrative",
    },
]

BY_SLUG = {t["slug"]: t for t in TOPICS}

# Topic keys the assistant may explain; mapping from intent to slug.
INTENT_TOPIC = {"explain_dr": "what-is-dr", "why_screening": "why-screening", "what_happens": "what-happens",
                "myths": "myths-facts", "diabetes_care": "diabetes-and-eyes", "next_steps": "next-steps"}


def topic(slug: str, lang: str) -> dict | None:
    t = BY_SLUG.get(slug)
    if not t:
        return None
    lang = lang if lang in ("hi", "en") else "hi"
    return {"slug": t["slug"], "icon": t["icon"], "title": t["title"][lang], "summary": t["summary"][lang],
            "blocks": t["blocks"][lang], "review_status": t["review_status"], "lang": lang}


def listing(lang: str) -> list[dict]:
    lang = lang if lang in ("hi", "en") else "hi"
    return [{"slug": t["slug"], "icon": t["icon"], "title": t["title"][lang], "summary": t["summary"][lang],
             "review_status": t["review_status"]} for t in TOPICS]
