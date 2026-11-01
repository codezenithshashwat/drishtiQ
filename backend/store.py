"""Local case store (SQLite) for the worklist, screening encounters, clinician reviews and reports.

Everything lives under data/app/ (git-ignored): cases.sqlite plus the original image of each case in images/, kept so a
case can be re-analysed when the app's models change. One case is one photograph of one eye. A screening encounter groups
the right- and left-eye photographs of ONE visit; cases from before encounters existed keep encounter_id NULL and are never
paired with anything. Reviews are append-only (enforced by triggers): a correction is a new row, never an edit.
Access control lives in backend/clinical_auth.py. No encryption at rest: not suitable for real patient data.
"""
import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from .dbmigrate import add_columns, migrate

ROOT = Path(__file__).resolve().parents[1]
DIR = Path(os.environ.get("RS_DATA_DIR") or ROOT / "data/app")  # override for tests
IMAGES = DIR / "images"
_lock = threading.Lock()
SCHEMA_VERSION = 3

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

# V3, additive only. Older reviews keep reviewer_user_id NULL: they stay visible as historical records but are never an
# authenticated clinical decision (backend/clinical_state.py).
V3 = """
CREATE TABLE IF NOT EXISTS encounters (
  id TEXT PRIMARY KEY, patient_ref TEXT NOT NULL, created TEXT NOT NULL, created_by_user_id INTEGER, created_by_name TEXT,
  client_key TEXT UNIQUE);
CREATE INDEX IF NOT EXISTS idx_cases_encounter ON cases(encounter_id);
CREATE INDEX IF NOT EXISTS idx_reviews_case ON reviews(case_id);
CREATE TRIGGER IF NOT EXISTS reviews_append_only_update BEFORE UPDATE ON reviews BEGIN SELECT RAISE(ABORT, 'reviews are append-only'); END;
CREATE TRIGGER IF NOT EXISTS reviews_append_only_delete BEFORE DELETE ON reviews BEGIN SELECT RAISE(ABORT, 'reviews are append-only'); END;
"""


def _v3(db):
    add_columns(db, "cases", {"encounter_id": "TEXT"})
    add_columns(db, "reviews", {"reviewer_user_id": "INTEGER", "next_action": "TEXT", "ai_dme": "TEXT", "ai_model_version": "TEXT",
                                "ai_route_state": "TEXT", "analysed_with": "TEXT"})
    db.executescript(V3)


def connect():
    DIR.mkdir(parents=True, exist_ok=True)
    IMAGES.mkdir(exist_ok=True)
    path = DIR / "cases.sqlite"
    db = sqlite3.connect(path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    cols = {r[1] for r in db.execute("PRAGMA table_info(cases)")}
    for col in ("vision_problems", "prior_treatment"):  # optional intake answers (ADR-040), added to older stores
        if col not in cols:
            db.execute(f"ALTER TABLE cases ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
    db.commit()
    report = migrate(db, path, SCHEMA_VERSION, _v3)
    if report["migrated"]:
        print(f"cases.sqlite migrated to v{SCHEMA_VERSION} (backup: {report['backup'] or 'not needed, empty database'})", flush=True)
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


def add_case(db, patient_ref, eye, source, image_bytes, image_ext, analysis, analysed_with, intake=None, encounter_id=None):
    with _lock:
        cid = next_id(db)
        (IMAGES / f"{cid}.{image_ext}").write_bytes(image_bytes)
        intake = intake or {}
        db.execute("INSERT INTO cases (id, created, patient_ref, eye, source, image_ext, analysis, analysed_with, status, vision_problems, "
                   "prior_treatment, encounter_id) VALUES (?,?,?,?,?,?,?,?, 'new', ?, ?, ?)",
                   (cid, now(), patient_ref, eye, source, image_ext, json.dumps(analysis), analysed_with,
                    int(bool(intake.get("vision_problems"))), int(bool(intake.get("prior_treatment"))), encounter_id))
        db.commit()
    return cid


def update_analysis(db, cid, analysis, analysed_with):
    """Re-analysis rewrites only the AI output. Reviews keep their own snapshot of what the clinician saw."""
    with _lock:
        db.execute("UPDATE cases SET analysis=?, analysed_with=? WHERE id=?", (json.dumps(analysis), analysed_with, cid))
        db.commit()


def image_bytes(row):
    return (IMAGES / f"{row['id']}.{row['image_ext']}").read_bytes()


def cases(db):
    return db.execute("SELECT * FROM cases ORDER BY created DESC").fetchall()


def case(db, cid):
    return db.execute("SELECT * FROM cases WHERE id=?", (cid,)).fetchone()


EYE_ORDER = ["right", "left", "unknown"]


def latest_per_eye(rows):
    latest = {}
    for r in rows:  # rows are newest first
        latest.setdefault(r["eye"], r)
    return [latest[e] for e in sorted(latest, key=EYE_ORDER.index)]


def patient_cases(db, patient_ref):
    """Latest case per eye for one patient ACROSS VISITS. Kept for history views only; reports and patient outcomes use
    encounter_cases (one visit) so unrelated visits are never combined."""
    return latest_per_eye(db.execute("SELECT * FROM cases WHERE patient_ref=? ORDER BY created DESC, id DESC", (patient_ref,)).fetchall())


# ---- screening encounters ------------------------------------------------------------------------------------------
_ENC_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def create_encounter(db, patient_ref, user_id=None, user_name=None, client_key=None):
    """One visit. Idempotent on client_key (a double-clicked 'Analyse' never creates two encounters)."""
    with _lock:
        if client_key:
            row = db.execute("SELECT * FROM encounters WHERE client_key=?", (client_key,)).fetchone()
            if row is not None:
                return dict(row)
        eid = "ENC-" + "".join(secrets.choice(_ENC_ALPHABET) for _ in range(10))
        db.execute("INSERT INTO encounters (id, patient_ref, created, created_by_user_id, created_by_name, client_key) VALUES (?,?,?,?,?,?)",
                   (eid, patient_ref, now(), user_id, user_name, client_key))
        db.commit()
    return dict(encounter(db, eid))


def encounter(db, eid):
    return db.execute("SELECT * FROM encounters WHERE id=?", (eid,)).fetchone()


def encounter_all_cases(db, eid):
    return db.execute("SELECT * FROM cases WHERE encounter_id=? ORDER BY created DESC, rowid DESC", (eid,)).fetchall()


def encounter_cases(db, eid):
    """Latest photograph per eye within one encounter (a retake replaces the earlier photo of that eye)."""
    return latest_per_eye(encounter_all_cases(db, eid))


def latest_encounter_for_patient(db, patient_ref):
    """Ties within one second fall back to insertion order (ids are random)."""
    return db.execute("SELECT * FROM encounters WHERE patient_ref=? ORDER BY created DESC, rowid DESC LIMIT 1", (patient_ref,)).fetchone()


# ---- reviews (append-only) -----------------------------------------------------------------------------------------
def add_review(db, cid, reviewer, decision, corrected_stage, corrected_dme, note, ai_stage, ai_grader, *, reviewer_user_id=None,
               next_action=None, ai_dme=None, ai_model_version=None, ai_route_state=None, analysed_with=None):
    with _lock:
        cur = db.execute("INSERT INTO reviews (case_id, created, reviewer, decision, corrected_stage, corrected_dme, note, ai_stage, ai_grader, "
                         "reviewer_user_id, next_action, ai_dme, ai_model_version, ai_route_state, analysed_with) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (cid, now(), reviewer, decision, corrected_stage, corrected_dme, note, ai_stage, ai_grader,
                          reviewer_user_id, next_action, ai_dme, ai_model_version, ai_route_state, analysed_with))
        db.execute("UPDATE cases SET status='reviewed' WHERE id=?", (cid,))
        db.commit()
    return cur.lastrowid


def reviews(db, cid=None):
    q, args = ("SELECT * FROM reviews WHERE case_id=? ORDER BY id DESC", (cid,)) if cid else ("SELECT * FROM reviews ORDER BY id", ())
    return [dict(r) for r in db.execute(q, args).fetchall()]
