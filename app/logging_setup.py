"""Logging to a rotating file, the database (for the Logs screen) and memory."""
from __future__ import annotations

import logging
import logging.handlers
import threading
from collections import deque

from . import db, paths

_FORMAT = "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s"
_recent: deque = deque(maxlen=2000)
_current_run = threading.local()


def set_run_id(run_id: int | None) -> None:
    _current_run.value = run_id


class _DbHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith("hydra.db"):
            return
        try:
            db.conn().execute(
                "INSERT INTO logs(ts, level, source, run_id, message) VALUES (?,?,?,?,?)",
                (db.now_iso(), record.levelname, record.name.removeprefix("hydra."),
                 getattr(_current_run, "value", None), self.format(record)),
            )
        except Exception:
            pass  # logging must never crash the app


class _MemoryHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _recent.append(self.format(record))


def setup(level: int = logging.INFO) -> None:
    root = logging.getLogger("hydra")
    if root.handlers:
        return
    root.setLevel(level)
    file_h = logging.handlers.RotatingFileHandler(
        paths.logs_dir() / "hydra.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_h.setFormatter(logging.Formatter(_FORMAT))
    db_h = _DbHandler()
    db_h.setFormatter(logging.Formatter("%(message)s"))
    mem_h = _MemoryHandler()
    mem_h.setFormatter(logging.Formatter(_FORMAT))
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(_FORMAT))
    for h in (file_h, db_h, mem_h, console):
        root.addHandler(h)


def recent_lines() -> list[str]:
    return list(_recent)
