"""Hydra in the Windows notification area (tray), so the schedule keeps running when the window is closed.

Also: a second Hydra start shows the running window instead of opening another one
(the running Hydra listens on a local-only port written to data/show.port).
"""
from __future__ import annotations

import logging
import socket
import sys
import threading
import time

from . import db, notify, paths, settings

log = logging.getLogger("hydra.tray")


def supported() -> bool:
    if not sys.platform.startswith("win"):
        return False
    try:
        import pystray  # noqa: F401
        from PIL import Image  # noqa: F401
        return True
    except Exception:
        return False


class Tray:
    """callbacks: show(), generate(), quit(); pause state comes from settings."""

    def __init__(self, show, generate, quit_):
        self._show, self._generate, self._quit = show, generate, quit_
        self.icon = None
        self.window_hidden = False
        self._seen = 0

    def start(self) -> bool:
        if not supported():
            return False
        try:
            import pystray
            from PIL import Image
            img = Image.open(paths.ui_dir() / "assets" / "img" / "hydra_icon.png")
            paused = lambda _i: not settings.get("scheduler.enabled", True)   # noqa: E731

            def toggle_pause(_i, _it):
                from .scheduler import SCHEDULER
                settings.set("scheduler.enabled", not settings.get("scheduler.enabled", True))
                SCHEDULER.wake()
                self.icon.update_menu()

            menu = pystray.Menu(
                pystray.MenuItem("Open Hydra", lambda _i, _it: self._show(), default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Generate Reports Now", lambda _i, _it: self._generate()),
                pystray.MenuItem("Pause schedule", toggle_pause, checked=paused),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit Hydra", lambda _i, _it: self._quit()),
            )
            self.icon = pystray.Icon("Hydra", img, "Hydra — Work Automation Suite", menu)
            self.icon.run_detached()
            self._seen = db.conn().execute("SELECT COALESCE(MAX(id),0) FROM notifications").fetchone()[0]
            threading.Thread(target=self._balloons, daemon=True, name="hydra-tray-balloons").start()
            return True
        except Exception:
            log.exception("Tray icon not available")
            self.icon = None
            return False

    def stop(self):
        try:
            if self.icon:
                self.icon.stop()
        except Exception:
            pass

    def balloon(self, title: str, text: str = ""):
        try:
            if self.icon and settings.get("notifications.windows_toasts", True):
                self.icon.notify(text or " ", title)
        except Exception:
            pass

    def _balloons(self):
        """While the window is hidden, show Windows pop-ups for new run/WhatsApp/schedule notifications."""
        while self.icon:
            time.sleep(15)
            try:
                rows = db.conn().execute("SELECT id, title, body, level, kind FROM notifications WHERE id>? ORDER BY id",
                                         (self._seen,)).fetchall()
            except Exception:
                continue
            for r in rows:
                self._seen = r["id"]
                if self.window_hidden and r["kind"] in ("reports", "schedule", "whatsapp") and r["level"] in ("success", "error", "warning"):
                    self.balloon(r["title"], r["body"] or "")


# ---------------------------------------------------------------- "show the running Hydra"
def listen_for_show(on_show) -> None:
    def serve():
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.bind(("127.0.0.1", 0))
            srv.listen(2)
            (paths.data_root() / "show.port").write_text(str(srv.getsockname()[1]), encoding="utf-8")
            while True:
                conn, _ = srv.accept()
                with conn:
                    if conn.recv(16).startswith(b"show"):
                        on_show()
        except Exception:
            log.exception("Show listener stopped")
    threading.Thread(target=serve, daemon=True, name="hydra-show").start()


def ask_running_to_show() -> bool:
    try:
        port = int((paths.data_root() / "show.port").read_text(encoding="utf-8").strip())
        with socket.create_connection(("127.0.0.1", port), timeout=2) as s:
            s.sendall(b"show")
        return True
    except Exception:
        return False


def first_hide_notice():
    if not settings.get("tray.notice_shown"):
        settings.set("tray.notice_shown", True)
        notify.add("system", "info", "Hydra is still running in the tray",
                   "Scheduled reports keep running. Right-click the Hydra icon near the clock to open or quit.", "settings")
        return True
    return False
