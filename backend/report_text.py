"""Patient-summary wording in English and Hindi (B7), read from review/hindi_review.csv (key, english, hindi, context).

The CSV is the single source: edit it (Excel keeps Devanagari intact; the file is UTF-8 with a byte-order mark) and
restart the app. Only these strings and model outputs appear in a patient summary; nothing is machine-translated at
run time. The Hindi text awaits review (the Report screen says so).
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRINGS = ROOT / "review/hindi_review.csv"
REQUIRED = (["title", "patient", "date", "intro", "result", "next_step", "right", "left", "unknown", "not_assessed", "swelling",
             "care_title", "questions", "disclaimer", "care.0", "care.1", "care.2"]
            + [f"risk.{k}" for k in ("low", "possible", "high")] + [f"follow_up.{k}" for k in ("routine", "refer", "urgent", "human", "retake", "incomplete")]
            + [f"stage.{s}.{p}" for s in range(5) for p in ("name", "explain")])


def load(path=STRINGS):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = {r["key"].strip(): r for r in csv.DictReader(f)}
    missing = [k for k in REQUIRED if k not in rows or not rows[k]["english"].strip() or not rows[k]["hindi"].strip()]
    if missing:
        raise ValueError(f"{path.name}: missing or empty strings for {missing}")
    out = {}
    for lang, col in (("en", "english"), ("hi", "hindi")):
        t = {k: rows[k][col].strip() for k in REQUIRED if "." not in k}
        t["risk"] = {k: rows[f"risk.{k}"][col].strip() for k in ("low", "possible", "high")}
        t["care"] = [rows[f"care.{i}"][col].strip() for i in range(3)]
        t["stage"] = {s: (rows[f"stage.{s}.name"][col].strip(), rows[f"stage.{s}.explain"][col].strip()) for s in range(5)}
        t["follow_up"] = {k: rows[f"follow_up.{k}"][col].strip() for k in ("routine", "refer", "urgent", "human", "retake", "incomplete")}
        out[lang] = t
    return out


PATIENT = load()
