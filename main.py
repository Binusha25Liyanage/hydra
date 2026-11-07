"""Hydra — Management Report Automation.

Run from source:   python main.py
Debug (DevTools):  set HYDRA_DEBUG=1 && python main.py
"""
from __future__ import annotations

import logging
import os
import sys

from app import db, logging_setup, paths, version
from app.api import Api

log = logging.getLogger("hydra.main")
_lock_handle = None


def single_instance() -> bool:
    """Only one Hydra window per Windows user."""
    global _lock_handle
    _lock_handle = open(paths.lock_path(), "a+")
    try:
        if sys.platform.startswith("win"):
            import msvcrt
            msvcrt.locking(_lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(_lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def main() -> int:
    if not single_instance():
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, "Hydra is already running.", "Hydra", 0x40)
        except Exception:
            print("Hydra is already running.")
        return 0

    db.init()
    logging_setup.setup(logging.DEBUG if os.environ.get("HYDRA_DEBUG") == "1" else logging.INFO)
    log.info("Hydra %s starting (%s) — data folder %s", version.VERSION, version.PHASE, paths.data_root())

    import webview

    api = Api()
    window = webview.create_window(
        title="Hydra — Management Report Automation",
        url=str(paths.ui_dir() / "splash.html"),
        js_api=api,
        width=1440, height=900, min_size=(1280, 720),
        background_color="#0B0C0E",
        text_select=False,
    )
    api._attach(window)
    webview.start(debug=os.environ.get("HYDRA_DEBUG") == "1", http_server=True,
                  icon=str(paths.ui_dir() / "assets" / "img" / "hydra_icon.png"))
    log.info("Hydra closed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
