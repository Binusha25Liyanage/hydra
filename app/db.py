"""SQLite database: one file, versioned migrations, one connection per thread.

Later phases add their tables as new entries in MIGRATIONS — never edit an
existing migration once it has shipped.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime

from . import paths

_local = threading.local()
_init_lock = threading.Lock()
_initialised = False

MIGRATIONS: list[tuple[int, str]] = [
    (1, """
    CREATE TABLE settings (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE users (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        username     TEXT NOT NULL UNIQUE COLLATE NOCASE,
        display_name TEXT NOT NULL DEFAULT '',
        role         TEXT NOT NULL CHECK (role IN ('superadmin','admin','user')),
        pw_hash      TEXT NOT NULL,
        salt         TEXT NOT NULL,
        iterations   INTEGER NOT NULL,
        active       INTEGER NOT NULL DEFAULT 1,
        failed_count INTEGER NOT NULL DEFAULT 0,
        locked_until TEXT,
        created_at   TEXT NOT NULL,
        last_login   TEXT
    );

    CREATE TABLE remember_tokens (
        token_hash TEXT PRIMARY KEY,
        user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at TEXT NOT NULL
    );

    CREATE TABLE audit (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        ts       TEXT NOT NULL,
        username TEXT,
        action   TEXT NOT NULL,
        details  TEXT
    );
    CREATE INDEX ix_audit_ts ON audit(ts);

    CREATE TABLE logs (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        ts      TEXT NOT NULL,
        level   TEXT NOT NULL,
        source  TEXT NOT NULL,
        run_id  INTEGER,
        message TEXT NOT NULL
    );
    CREATE INDEX ix_logs_ts ON logs(ts);
    CREATE INDEX ix_logs_run ON logs(run_id);

    CREATE TABLE notifications (
        id     INTEGER PRIMARY KEY AUTOINCREMENT,
        ts     TEXT NOT NULL,
        kind   TEXT NOT NULL,
        level  TEXT NOT NULL CHECK (level IN ('info','success','warning','error')),
        title  TEXT NOT NULL,
        body   TEXT,
        action TEXT,
        read   INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX ix_notif_ts ON notifications(ts);

    CREATE TABLE page_profiles (
        key             TEXT PRIMARY KEY,
        name            TEXT NOT NULL,
        url             TEXT NOT NULL,
        filters_json    TEXT NOT NULL DEFAULT '{}',
        date_rules_json TEXT NOT NULL DEFAULT '{}',
        updated_at      TEXT NOT NULL
    );

    CREATE TABLE startup_history (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ts          TEXT NOT NULL,
        mode        TEXT NOT NULL,
        duration_ms INTEGER NOT NULL,
        result      TEXT NOT NULL,
        steps_json  TEXT NOT NULL
    );
    """),
]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(paths.db_path(), timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=30000")
    return con


def conn() -> sqlite3.Connection:
    """Connection for the current thread (opened on first use)."""
    init()
    c = getattr(_local, "con", None)
    if c is None:
        c = _local.con = _connect()
    return c


@contextmanager
def tx():
    """Transaction block: commits on success, rolls back on error."""
    c = conn()
    c.execute("BEGIN IMMEDIATE")
    try:
        yield c
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise


def schema_version(c: sqlite3.Connection | None = None) -> int:
    c = c or conn()
    c.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = c.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    return row["v"] or 0


def init() -> int:
    """Create the database file and apply pending migrations. Safe to call often."""
    global _initialised
    if _initialised:
        return 0
    with _init_lock:
        if _initialised:
            return 0
        c = _connect()
        try:
            applied = 0
            current = schema_version(c)
            for version, sql in MIGRATIONS:
                if version > current:
                    # executescript runs the whole migration; the version row is
                    # written in the same script so a half-applied migration is
                    # never recorded as done.
                    c.executescript(
                        "BEGIN;\n" + sql
                        + f"\nINSERT INTO schema_version(version) VALUES ({int(version)});\nCOMMIT;"
                    )
                    applied += 1
        finally:
            c.close()
        _initialised = True
        return applied


def quick_check() -> str:
    """'ok' when the database file is healthy."""
    row = conn().execute("PRAGMA quick_check").fetchone()
    return row[0]


def table_exists(name: str) -> bool:
    row = conn().execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def audit(username: str | None, action: str, details: str = "") -> None:
    conn().execute(
        "INSERT INTO audit(ts, username, action, details) VALUES (?,?,?,?)",
        (now_iso(), username, action, details),
    )
