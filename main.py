"""Hydra — Work Automation Suite for Lakmee Exports Lanka.

Run from source:   python main.py
Debug (DevTools):  set HYDRA_DEBUG=1 && python main.py
"""
from __future__ import annotations

import logging
import os
import sys

from app import db, logging_setup, paths, settings, version, winicon
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
    start_hidden = "--tray" in sys.argv
    if not single_instance():
        from app import tray as _tray
        if _tray.ask_running_to_show():          # bring the running Hydra to the front instead
            return 0
        if start_hidden:
            return 0
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, "Hydra is already running.", "Hydra", 0x40)
        except Exception:
            print("Hydra is already running.")
        return 0

    db.init()
    logging_setup.setup(logging.DEBUG if os.environ.get("HYDRA_DEBUG") == "1" else logging.INFO)
    log.info("Hydra %s starting (%s) — data folder %s", version.VERSION, version.PHASE, paths.data_root())
    from app.whatsapp import service as wa_service
    from app import autostart, runner, tray
    from app.scheduler import SCHEDULER
    wa_service.recover()                         # messages interrupted by the last close -> failed
    runner.recover()                             # runs cut off by the last close -> failed
    try:
        autostart.refresh()                      # keep "start with Windows" pointing at this copy
    except Exception:
        log.exception("Autostart refresh failed")

    import webview

    ico = paths.ui_dir() / "assets" / "img" / "hydra.ico"
    winicon.set_app_id(version.APP_ID)          # own taskbar group, not python.exe

    api = Api()
    window = webview.create_window(
        title="HYDRA",
        url=str(paths.ui_dir() / "splash.html"),
        js_api=api,
        width=1440, height=900, min_size=(1280, 720),
        background_color="#0B0C0E",
        text_select=False,
        hidden=start_hidden,
    )
    api._attach(window)
    window.events.shown += lambda: winicon.apply_when_ready(ico, settings.get("ui.titlebar"))
    window.events.loaded += lambda: winicon.apply_when_ready(ico, settings.get("ui.titlebar"), attempts=3)
    # ---------------------------------------------------------------- tray + schedule
    state = {"quitting": False}

    def show():
        try:
            window.show()
            window.restore()
            if t:
                t.window_hidden = False
        except Exception:
            log.exception("Show window")

    def generate_now():
        show()
        try:
            window.evaluate_js("window.App && App.go('run', {autorun: true})")
        except Exception:
            pass

    def quit_():
        state["quitting"] = True
        try:
            window.destroy()
        except Exception:
            pass

    t = tray.Tray(show, generate_now, quit_)

    def on_closing():
        if state["quitting"] or not settings.get("ui.close_to_tray", True) or not t.icon:
            return True                          # really close
        window.hide()
        t.window_hidden = True
        if tray.first_hide_notice():
            t.balloon("Hydra is still running", "Scheduled reports keep running. Right-click the Hydra icon to open or quit.")
        return False                             # cancel the close

    def on_started():
        if t.start():
            t.window_hidden = start_hidden
        elif start_hidden:
            show()                               # no tray on this PC: never leave Hydra invisible
        tray.listen_for_show(show)
        SCHEDULER.start()

    window.events.closing += on_closing
    webview.start(on_started, debug=os.environ.get("HYDRA_DEBUG") == "1", http_server=True,
                  icon=str(paths.ui_dir() / "assets" / "img" / "hydra_icon.png"))
    SCHEDULER.stop()
    t.stop()
    wa_service.WORKER.shutdown()                 # close the WhatsApp browser cleanly
    if wa_service.WORKER._thread:
        wa_service.WORKER._thread.join(timeout=5)
    log.info("Hydra closed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
