"""Frozen output semantics (ADR-039/040): the AI never "clears" an eye or calls it "normal" / "healthy".

Scans every user-facing source: frontend code, the report template, patient-summary strings (English column of
review/hindi_review.csv), glossary, explanations, routing texts, the pipeline's messages and the public docs.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = re.compile(r"\b(normal|healthy|cleared|clears)\b", re.I)
SOURCES = (list((ROOT / "frontend/src").rglob("*.ts")) + list((ROOT / "frontend/src").rglob("*.tsx"))
           + [ROOT / p for p in ("backend/templates/report.html", "backend/report_text.py", "review/hindi_review.csv", "src/inference/glossary.py",
                                 "src/inference/explanations.py", "src/inference/routing.py", "src/inference/pipeline.py", "src/inference/assist.py",
                                 "docs/MODEL_CARD.md", "docs/DATA_CARD.md", "README.md")])


def test_no_clearing_language():
    hits = []
    for p in SOURCES:
        for n, line in enumerate(p.read_text(encoding="utf-8-sig").splitlines(), 1):
            text = re.sub(r"inter-latin-\d+-normal", "", line)  # font file names
            if FORBIDDEN.search(text):
                hits.append(f"{p.relative_to(ROOT)}:{n}: {line.strip()[:100]}")
    assert not hits, "forbidden wording:\n" + "\n".join(hits)


def test_routine_texts_are_the_frozen_wording():
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    from backend.report_text import PATIENT
    from inference import routing
    assert routing.CLINICIAN_ROUTINE_TEXT == "No referable diabetic retinopathy detected by AI in gradable images of both eyes."
    assert PATIENT["en"]["follow_up"]["routine"] == ("This photo check did not find diabetic eye damage that needs a specialist now. "
                                                     "It is not a full eye examination. Come back for your next check, or sooner if your vision changes.")


def test_landing_page_makes_no_clinical_overclaims():
    """UI v3 landing page: no "replaces doctors", "diagnoses", "fairer" or "clinically proven" (owner's rule)."""
    text = (ROOT / "frontend/src/app/screens/Landing.tsx").read_text(encoding="utf-8")
    banned = re.compile(r"\b(replaces?|replacing)\s+(doctors?|clinicians?|specialists?|ophthalmologists?)\b|\bdiagnoses\b|\bfairer\b|\bclinically\s+proven\b", re.I)
    hits = [m.group(0) for m in banned.finditer(text)]
    assert not hits, f"landing page overclaims: {hits}"
