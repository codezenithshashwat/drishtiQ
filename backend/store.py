"""Local case store (SQLite) for the worklist, reviews (B7 feedback store) and reports.

Everything lives under data/app/ (git-ignored): cases.sqlite plus the original image of each case in images/, kept so a
case can be re-analysed when the app's models change. This is a single-user local prototype: no authentication and no
encryption at rest, so it is not suitable for real patient data.
"""
import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = Path(os.environ.get("RS_DATA_DIR") or ROOT / "data/app")  # override for tests
IMAGES = DIR / "images"
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
  id TEXT PRIMARY KEY, created TEXT NOT NULL, patient_ref TEXT NOT NULL, eye TEXT NOT NULL,
  source TEXT NOT NULL, image_ext TEXT NOT NULL, analysis TEXT NOT NULL, analysed_with TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new');
CREATE TABLE IF NOT EXISTS reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL REFERENCES cases(id), created TEXT NOT NULL,
  reviewer TEXT NOT NULL, decision TEXT NOT NULL, corrected_stage INTEGER, corrected_dme TEXT, note TEXT NOT NULL DEFAULT '',
  ai_stage INTEGER, ai_grader TEXT);
"""


def connect():
    DIR.mkdir(parents=True, exist_ok=True)
    IMAGES.mkdir(exist_ok=True)
    db = sqlite3.connect(DIR / "cases.sqlite", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    cols = {r[1] for r in db.execute("PRAGMA table_info(cases)")}
    for col in ("vision_problems", "prior_treatment"):  # optional intake answers (ADR-040), added to older stores
        if col not in cols:
            db.execute(f"ALTER TABLE cases ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
    db.commit()
    return db


def settings():
    p = DIR / "settings.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save_settings(values):
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / "settings.json").write_text(json.dumps({**settings(), **values}, indent=2))


def earlier_cases(db, row):
    """Cases of the same patient and eye created before this one, newest first (repeat visits, retakes)."""
    # Ties within one second fall back to the id (RS-1001 < RS-1002): a later case is never an "earlier" one.
    return db.execute("SELECT * FROM cases WHERE patient_ref=? AND eye=? AND (created<? OR (created=? AND id<?)) ORDER BY created DESC, id DESC",
                      (row["patient_ref"], row["eye"], row["created"], row["created"], row["id"])).fetchall()


def now():
    return datetime.now().isoformat(timespec="seconds")


def next_id(db):
    n = db.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    return f"RS-{1001 + n}"


def add_case(db, patient_ref, eye, source, image_bytes, image_ext, analysis, analysed_with, intake=None):
    with _lock:
        cid = next_id(db)
        (IMAGES / f"{cid}.{image_ext}").write_bytes(image_bytes)
        intake = intake or {}
        db.execute("INSERT INTO cases (id, created, patient_ref, eye, source, image_ext, analysis, analysed_with, status, vision_problems, "
                   "prior_treatment) VALUES (?,?,?,?,?,?,?,?, 'new', ?, ?)",
                   (cid, now(), patient_ref, eye, source, image_ext, json.dumps(analysis), analysed_with,
                    int(bool(intake.get("vision_problems"))), int(bool(intake.get("prior_treatment")))))
        db.commit()
    return cid


def update_analysis(db, cid, analysis, analysed_with):
    with _lock:
        db.execute("UPDATE cases SET analysis=?, analysed_with=? WHERE id=?", (json.dumps(analysis), analysed_with, cid))
        db.commit()


def image_bytes(row):
    return (IMAGES / f"{row['id']}.{row['image_ext']}").read_bytes()


def cases(db):
    return db.execute("SELECT * FROM cases ORDER BY created DESC").fetchall()


def case(db, cid):
    return db.execute("SELECT * FROM cases WHERE id=?", (cid,)).fetchone()


def patient_cases(db, patient_ref):
    """Latest case per eye for one patient."""
    rows = db.execute("SELECT * FROM cases WHERE patient_ref=? ORDER BY created DESC, id DESC", (patient_ref,)).fetchall()
    latest = {}
    for r in rows:
        latest.setdefault(r["eye"], r)
    return [latest[e] for e in sorted(latest, key=lambda e: ["right", "left", "unknown"].index(e))]


def add_review(db, cid, reviewer, decision, corrected_stage, corrected_dme, note, ai_stage, ai_grader):
    with _lock:
        db.execute("INSERT INTO reviews (case_id, created, reviewer, decision, corrected_stage, corrected_dme, note, ai_stage, ai_grader) "
                   "VALUES (?,?,?,?,?,?,?,?,?)", (cid, now(), reviewer, decision, corrected_stage, corrected_dme, note, ai_stage, ai_grader))
        db.execute("UPDATE cases SET status='reviewed' WHERE id=?", (cid,))
        db.commit()


def reviews(db, cid=None):
    q, args = ("SELECT * FROM reviews WHERE case_id=? ORDER BY id DESC", (cid,)) if cid else ("SELECT * FROM reviews ORDER BY id", ())
    return [dict(r) for r in db.execute(q, args).fetchall()]
