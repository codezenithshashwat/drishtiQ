"""Safe, additive SQLite migrations shared by the clinical store (cases.sqlite) and DrishtiQ Network (network.sqlite).

Rules (DrishtiQ V3):
- Migrations only ADD tables, columns, indexes and triggers. They never rebuild, rewrite or delete existing rows.
- Before an existing database with data is migrated, an online backup is written next to it and validated
  (integrity_check plus identical row counts for every table). If validation fails, the migration is not run.
- The schema version lives in PRAGMA user_version, so a migration runs once.
"""
import sqlite3
from datetime import datetime
from pathlib import Path


def tables(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables(conn)}


def has_data(conn: sqlite3.Connection) -> bool:
    return any(n > 0 for n in row_counts(conn).values())


def backup_validated(conn: sqlite3.Connection, path: Path, label: str) -> Path:
    """Copy the live database to <name>.<label>-<time>.bak and prove the copy is complete. Returns the backup path."""
    dest = path.with_name(f"{path.name}.{label}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak")
    n = 1
    while dest.exists():
        dest = dest.with_name(f"{dest.stem}-{n}.bak")
        n += 1
    b = sqlite3.connect(str(dest))
    try:
        conn.backup(b)
        if b.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError(f"backup {dest.name} failed its integrity check")
        if row_counts(b) != row_counts(conn):
            raise RuntimeError(f"backup {dest.name} does not contain the same rows as {path.name}")
    finally:
        b.close()
    return dest


def column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}


def add_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> list[str]:
    """ALTER TABLE ... ADD COLUMN for each missing column (nullable or with a constant default). Returns the added names."""
    have = column_names(conn, table)
    added = []
    for name, decl in columns.items():
        if name not in have:
            conn.execute(f'ALTER TABLE "{table}" ADD COLUMN {name} {decl}')
            added.append(name)
    return added


def migrate(conn: sqlite3.Connection, path: Path, version: int, steps, label: str = "pre-v3") -> dict:
    """Run `steps(conn)` once, if user_version < version. Backs up first when the database already holds data.
    Returns a small report (also logged by the callers)."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current >= version:
        return {"migrated": False, "version": current}
    backup = backup_validated(conn, path, label) if path.exists() and has_data(conn) else None
    before = row_counts(conn)
    steps(conn)
    after = row_counts(conn)
    lost = {t: (before[t], after.get(t)) for t in before if after.get(t) != before[t]}
    if lost:  # additive steps must never change existing row counts
        raise RuntimeError(f"migration changed existing row counts: {lost}; restore from {backup}")
    conn.execute(f"PRAGMA user_version={int(version)}")
    conn.commit()
    return {"migrated": True, "from": current, "to": version, "backup": str(backup) if backup else None}
