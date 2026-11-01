"""network.sqlite: separate from the clinical cases.sqlite. Path is resolved at connect time (tests pass their own)."""
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from ..dbmigrate import migrate
from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS organisations(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN('ngo','hospital','programme_proposed','other')),
  verification TEXT NOT NULL CHECK(verification IN('verified','unverified','simulated')),
  source TEXT NOT NULL DEFAULT 'organiser', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY,
  role TEXT NOT NULL CHECK(role IN('user','health_worker','organiser','admin')),
  display_name TEXT NOT NULL,
  identifier_type TEXT NOT NULL CHECK(identifier_type IN('mobile','email')),
  identifier_norm TEXT NOT NULL UNIQUE,
  identifier_verified INTEGER NOT NULL DEFAULT 0,
  password_hash TEXT NOT NULL,
  village TEXT, pin TEXT,
  language TEXT NOT NULL DEFAULT 'hi' CHECK(language IN('hi','en')),
  consent_version TEXT, consent_at TEXT,
  reminders_opt_in INTEGER NOT NULL DEFAULT 0,
  comm_pref TEXT NOT NULL DEFAULT 'none' CHECK(comm_pref IN('none','sms','call','email')),
  org_id INTEGER REFERENCES organisations(id),
  is_prototype INTEGER NOT NULL DEFAULT 0,
  failed_logins INTEGER NOT NULL DEFAULT 0, locked_until TEXT,
  created_at TEXT NOT NULL, deleted_at TEXT);
CREATE TABLE IF NOT EXISTS locations(
  id INTEGER PRIMARY KEY, label TEXT NOT NULL, village TEXT, district TEXT NOT NULL, state TEXT NOT NULL,
  pin TEXT NOT NULL CHECK(length(pin)=6 AND pin NOT GLOB '*[^0-9]*'));
CREATE TABLE IF NOT EXISTS camps(
  id INTEGER PRIMARY KEY, seed_key TEXT UNIQUE,
  org_id INTEGER NOT NULL REFERENCES organisations(id), location_id INTEGER NOT NULL REFERENCES locations(id),
  title_hi TEXT NOT NULL, title_en TEXT NOT NULL, starts_at TEXT NOT NULL, ends_at TEXT NOT NULL,
  capacity INTEGER CHECK(capacity IS NULL OR capacity>=0),
  price_info TEXT, contact_public TEXT,
  verification TEXT NOT NULL CHECK(verification IN('verified','unverified','simulated')),
  publish_state TEXT NOT NULL CHECK(publish_state IN('draft','published','closed','cancelled')),
  source TEXT NOT NULL CHECK(source IN('demo_seed','organiser','admin')),
  created_by INTEGER REFERENCES users(id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(
  id_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL, expires_at TEXT NOT NULL, last_seen TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS registrations(
  id INTEGER PRIMARY KEY, public_ref TEXT NOT NULL UNIQUE,
  camp_id INTEGER NOT NULL REFERENCES camps(id),
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL, created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  display_name TEXT NOT NULL, village TEXT, pin TEXT NOT NULL, phone TEXT, email TEXT,
  language TEXT NOT NULL CHECK(language IN('hi','en')),
  dedupe_key TEXT UNIQUE, idempotency_key TEXT UNIQUE,
  status TEXT NOT NULL CHECK(status IN('interest_received','contacted','confirmed_by_organiser','attended','no_show','cancelled')),
  consent_version TEXT NOT NULL, consent_at TEXT NOT NULL, contact_consent INTEGER NOT NULL DEFAULT 0,
  channel TEXT NOT NULL CHECK(channel IN('self','assisted','saathi_guided')),
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, purge_after TEXT);
CREATE INDEX IF NOT EXISTS idx_reg_camp ON registrations(camp_id, status);
CREATE INDEX IF NOT EXISTS idx_reg_user ON registrations(user_id);
CREATE TABLE IF NOT EXISTS worker_assignments(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  camp_id INTEGER NOT NULL REFERENCES camps(id) ON DELETE CASCADE, UNIQUE(user_id, camp_id));
CREATE TABLE IF NOT EXISTS followups(
  id INTEGER PRIMARY KEY, registration_id INTEGER NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL,
  kind TEXT NOT NULL CHECK(kind IN('contact','confirm_attendance','post_screening')),
  status TEXT NOT NULL DEFAULT 'open' CHECK(status IN('open','done','cancelled')),
  note_short TEXT CHECK(note_short IS NULL OR length(note_short)<=200), due_at TEXT, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor_user_id INTEGER, actor_role TEXT NOT NULL,
  action TEXT NOT NULL, entity TEXT NOT NULL, entity_id TEXT, detail TEXT);
"""

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    """Open (or reopen) network.sqlite and create the schema. Idempotent."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        p = Path(path) if path else config.data_dir() / "network.sqlite"
        p.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(p), check_same_thread=False, isolation_level=None)  # autocommit; transactions are explicit
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=3000")
        try:
            c.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            pass
        c.executescript(SCHEMA)
        report = migrate(c, p, SCHEMA_VERSION, _v3)
        if report["migrated"]:
            print(f"network.sqlite migrated to v{SCHEMA_VERSION} (backup: {report['backup'] or 'not needed, empty database'})", flush=True)
        _conn = c
        return c


# ---- V3 (additive): clinician grants and registration-to-screening links ----------------------------------------------
SCHEMA_VERSION = 3
V3 = """
-- Ophthalmologist access is a separate, revocable grant. users.role is untouched, so no existing permission changes and
-- public signup (which always creates role 'user') can never produce clinical access. History is kept: a revoked grant
-- stays as a row; at most one grant per user is active.
CREATE TABLE IF NOT EXISTS clinician_roles(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN('ophthalmologist')),
  granted_by TEXT NOT NULL, granted_at TEXT NOT NULL, revoked_by TEXT, revoked_at TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_clinician_active ON clinician_roles(user_id) WHERE revoked_at IS NULL;
-- An explicit, consented link made by a signed-in clinician from a patient-presented receipt. One active link per
-- registration and per encounter. encounter_id refers to cases.sqlite (a separate database), so it is a plain value.
CREATE TABLE IF NOT EXISTS screening_links(
  id INTEGER PRIMARY KEY, registration_id INTEGER NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  encounter_id TEXT NOT NULL, linked_by INTEGER REFERENCES users(id) ON DELETE SET NULL, linked_by_name TEXT NOT NULL,
  consent_confirmed_at TEXT NOT NULL, created_at TEXT NOT NULL,
  revoked_at TEXT, revoked_by INTEGER REFERENCES users(id) ON DELETE SET NULL, revoke_reason TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_link_reg_active ON screening_links(registration_id) WHERE revoked_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_link_enc_active ON screening_links(encounter_id) WHERE revoked_at IS NULL;
"""


def _v3(c: sqlite3.Connection) -> None:
    c.executescript(V3)


def close() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


def db() -> sqlite3.Connection:
    if _conn is None:
        connect()
    return _conn  # type: ignore[return-value]


def one(sql: str, args: tuple = ()):
    with _lock:
        return db().execute(sql, args).fetchone()


def all_(sql: str, args: tuple = ()):
    with _lock:
        return db().execute(sql, args).fetchall()


def run(sql: str, args: tuple = ()):
    with _lock:
        return db().execute(sql, args)


@contextmanager
def tx():
    """Serialised write transaction (BEGIN IMMEDIATE) so duplicate/capacity checks cannot race."""
    with _lock:
        c = db()
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
            c.execute("COMMIT")
        except BaseException:
            c.execute("ROLLBACK")
            raise
