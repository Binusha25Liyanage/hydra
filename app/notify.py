"""In-app notifications (bell + Notifications page). Windows toasts come in Phase 11."""
from __future__ import annotations

from . import db

LEVELS = ("info", "success", "warning", "error")


def add(kind: str, level: str, title: str, body: str = "", action: str = "") -> int:
    if level not in LEVELS:
        level = "info"
    cur = db.conn().execute(
        "INSERT INTO notifications(ts, kind, level, title, body, action) VALUES (?,?,?,?,?,?)",
        (db.now_iso(), kind, level, title, body, action),
    )
    return cur.lastrowid


def listing(limit: int = 200, only_unread: bool = False, kind: str = "") -> list[dict]:
    q = "SELECT * FROM notifications WHERE 1=1"
    args: list = []
    if only_unread:
        q += " AND read=0"
    if kind:
        q += " AND kind=?"
        args.append(kind)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in db.conn().execute(q, args)]


def unread_count() -> int:
    return db.conn().execute("SELECT COUNT(*) FROM notifications WHERE read=0").fetchone()[0]


def mark_read(ids: list[int] | None = None) -> None:
    if ids:
        db.conn().executemany("UPDATE notifications SET read=1 WHERE id=?", [(i,) for i in ids])
    else:
        db.conn().execute("UPDATE notifications SET read=1 WHERE read=0")
