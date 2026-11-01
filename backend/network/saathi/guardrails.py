"""Output and input safeguards for Saathi."""
import re

# Phrases Saathi must never produce: false booking confirmations and personal diagnoses.
BANNED = re.compile(
    r"(appointment\s+(is|has been|was)\s+(booked|confirmed)|you are (now )?(booked|confirmed)|your (seat|slot) is (booked|reserved)|"
    r"बुक हो गया|बुक कर दिया|आपका (अपॉइंटमेंट|स्लॉट) (पक्का|बुक)|you (definitely )?have diabetic retinopathy|आपको डायबिटिक रेटिनोपैथी है)",
    re.I)

SAFE_FALLBACK = {"hi": "माफ़ कीजिए, मैं यह बात ठीक से नहीं बता सकती। कृपया किसी डॉक्टर या शिविर आयोजक से पूछें।",
                 "en": "Sorry, I can't say that reliably. Please ask a doctor or the camp organiser."}


def reply_ok(text: str) -> bool:
    return BANNED.search(text) is None


def scrub_for_provider(text: str) -> str:
    """Remove personal identifiers before text is sent to any outside AI provider. A 6-digit PIN is kept (needed to search,
    not identifying on its own). Phone numbers, emails and long digit runs (Aadhaar-like) are removed."""
    t = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]", text)
    t = re.sub(r"(?<!\d)(?:\+?91[\s-]?)?[6-9](?:[\s-]?\d){9}(?!\d)", "[number]", t)
    t = re.sub(r"(?<!\d)\d{7,}(?!\d)", "[number]", t)
    t = re.sub(r"(?<!\d)\d{4}[\s-]\d{4}[\s-]\d{4}(?!\d)", "[number]", t)
    return t[:300]
