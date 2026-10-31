"""Grounding tests for template explanations: every number in a sentence must be a measured value from the findings
record (or a declared guideline/threshold constant), and every declared value must equal the record at its path.
Run: .venv\\Scripts\\python -m pytest tests -q
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from inference import explanations, findings  # noqa: E402
from inference.pipeline import LESION_NAMES, LESIONS, quality_flags  # noqa: E402

NUMBER = re.compile(r"(?<![\w-])\d+(?:\.\d+)?(?![\w-])")


def disk(mask, x, y, r):
    yy, xx = np.ogrid[:mask.shape[0], :mask.shape[1]]
    mask[(xx - x) ** 2 + (yy - y) ** 2 <= r * r] = True


def synthetic(grade, he_quadrants=2, ex_near_fovea=False, low_conf=False, blur=False, regression=False):
    h, w = 680, 1024
    od, fovea = (760.0, 340.0, 40.0), (520.0, 350.0)  # disc to the right of the fovea; DD = 80 px
    masks = {k: np.zeros((h, w), bool) for k in LESIONS}
    if grade >= 1:
        for x, y in [(400, 300), (450, 420), (600, 250)]:
            disk(masks["MA"], x, y, 2)
    if grade >= 2:
        spots = [(420, 250), (650, 260), (420, 460), (650, 450)][:he_quadrants]  # ST, SN, IT, IN around the fovea
        for x, y in spots:
            disk(masks["HE"], x, y, 6)
        disk(masks["EX"], 540 if ex_near_fovea else 300, 360 if ex_near_fovea else 560, 5)  # a single exudate: exercises "1 ..."
    probs = [0.05] * 5
    probs[grade] = 0.8
    grading = dict(grade=grade, label=explanations.GRADES[grade], probabilities=probs, referable_probability=sum(probs[2:]),
                   head_agreement=0.5 if low_conf else 1.0, low_confidence=low_conf, calibrated=False,
                   score=grade + 0.3 if regression else None, thresholds=[0.5, 1.5, 2.625, 3.5] if regression else None)
    if regression:
        i = min(range(4), key=lambda k: abs(grading["thresholds"][k] - grading["score"]))
        grading["between"] = dict(lower=i, upper=i + 1, closer_to=grade, nearest_boundary=i)
    quality = dict(usable=not blur, fov_fraction=0.7, brightness=60.0, sharpness=0.3 if blur else 3.0, red_dominant=True)
    flags = quality_flags(quality)
    if low_conf:
        flags.append(dict(id="low-confidence", trigger=dict(top_score=0.45, agreeing=3, heads=6, needed=5),
                          simple="Low confidence: needs a doctor's look.",
                          template="Model confidence is low: the top grade score is {top_score}, below 0.50 and only {agreeing} "
                                   "of {heads} ensemble heads agree ({needed} needed). Clinician review recommended."))
    return findings.build(grading, masks, LESION_NAMES, quality, od, fovea, False, (512.0, 340.0),
                          dict(app="test", checkpoints={}), flags)


CASES = [dict(grade=g) for g in range(5)] + [dict(grade=2, he_quadrants=4, ex_near_fovea=True), dict(grade=1, low_conf=True, blur=True),
                                               dict(grade=3, he_quadrants=4), dict(grade=2, regression=True)]


@pytest.mark.parametrize("case", CASES, ids=lambda c: "-".join(f"{k}{v}" for k, v in c.items()))
def test_every_number_is_grounded(case):
    record = synthetic(**case)
    sentences = explanations.explain(record)
    assert sentences, "no explanation generated"
    json.dumps(record)
    for s in sentences:
        allowed = {explanations.fmt(v["value"]) for v in s["values"].values()} | explanations.CONSTANTS
        for mode in ("simple", "clinical"):
            for number in NUMBER.findall(s[mode]):
                assert number in allowed, f"{s['id']} ({mode}): '{number}' is not a measured value or declared constant: {s[mode]}"
        for name, v in s["values"].items():
            assert explanations.get(record, v["path"]) == v["value"], f"{s['id']}.{name} does not match the record"
            assert explanations.fmt(v["value"]) in s["clinical"], f"{s['id']}: value {name} not shown in clinical text"


@pytest.mark.parametrize("case", CASES, ids=lambda c: "-".join(f"{k}{v}" for k, v in c.items()))
def test_simple_mode_is_plain(case):
    terms = explanations.clinical_only_terms()
    for s in explanations.explain(synthetic(**case)):
        text = s["simple"].lower()
        for key, (clin, pl) in terms.items():
            if re.search(rf"\b{re.escape(clin)}\b", text):
                assert pl in text, f"{s['id']}: clinical term '{clin}' used without its plain label '{pl}': {s['simple']}"
        for jargon in ("npdr", "haemorrhage", "exudate", "microaneurysm", "fovea", "quadrant", "ensemble", "threshold"):
            assert not re.search(rf"\b{jargon}", text), f"{s['id']}: jargon '{jargon}' in Simple text: {s['simple']}"
        assert len(s["simple"].split()) <= 30, f"{s['id']}: Simple text too long: {s['simple']}"


PLURALS = ("bulges", "spots", "deposits", "patches", "regions", "areas", "widths")


@pytest.mark.parametrize("case", CASES + [dict(grade=2, he_quadrants=1)], ids=lambda c: "-".join(f"{k}{v}" for k, v in c.items()))
def test_counts_agree_with_nouns(case):
    record = synthetic(**case)
    for s in explanations.explain(record):
        for mode in ("simple", "clinical"):
            for word in PLURALS:
                assert not re.search(rf"(?<![\d.])1 (?:[a-z-]+ ){{0,3}}{word}\b", s[mode]), f"{s['id']} ({mode}): '1 ... {word}': {s[mode]}"
        assert not re.search(r"\b(an|a) [A-Z][a-z]", s["simple"]), f"{s['id']}: capitalised word mid-sentence: {s['simple']}"


def test_quadrants_and_dme():
    r = synthetic(grade=2, he_quadrants=4, ex_near_fovea=True)
    assert r["haemorrhage_quadrants"]["count"] == 4
    assert sorted(r["haemorrhage_quadrants"]["quadrants"]) == sorted(findings.QUADRANTS)
    assert r["macular_edema_risk"]["level"] == "high"
    assert synthetic(grade=2, ex_near_fovea=False)["macular_edema_risk"]["level"] == "possible"
    assert synthetic(grade=0)["macular_edema_risk"]["level"] == "low"


def test_higher_grade_reasoning_mentions_limits():
    texts = {s["id"]: s["text"] for s in explanations.explain(synthetic(grade=3, he_quadrants=4))}
    assert "cannot be ruled out" in texts["why-not-higher"]
    texts = {s["id"]: s["text"] for s in explanations.explain(synthetic(grade=0))}
    assert "pdr-limit" in texts


def test_pipeline_output_is_grounded():
    import csv
    from inference import Pipeline
    with open(ROOT / "configs/splits/idrid_grading_devtrain.csv", newline="") as f:
        row = next(r for r in csv.DictReader(f) if r["DR_grade"] == "2")
    result = Pipeline().analyze((ROOT / row["filepath"]).read_bytes())
    json.dumps(result["findings"])
    for s in result["explanations"]:
        allowed = {explanations.fmt(v["value"]) for v in s["values"].values()} | explanations.CONSTANTS
        for mode in ("simple", "clinical"):
            assert all(n in allowed for n in NUMBER.findall(s[mode])), s[mode]
        assert all(explanations.get(result["findings"], v["path"]) == v["value"] for v in s["values"].values())


def test_patient_summary_strings_complete():
    """review/hindi_review.csv is the single source of patient-summary wording; every key needs English and Hindi."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend.report_text import PATIENT, REQUIRED
    assert set(PATIENT) == {"en", "hi"} and len(REQUIRED) == 36
    assert all(any("ऀ" <= ch <= "ॿ" for ch in PATIENT["hi"]["stage"][s][0]) for s in range(5))  # Devanagari
