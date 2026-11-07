"""Windows taskbar / title-bar icon for Hydra when it runs from source (python main.py).

Two things are needed so Windows shows the Hydra logo instead of the Python logo:
1. Our own AppUserModelID, so the taskbar does not group Hydra under python.exe.
2. The window's big/small icons set from hydra.ico (WM_SETICON).

The packaged Hydra.exe (Phase 12) gets its icon from the build as well.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path

log = logging.getLogger("hydra.winicon")

IS_WINDOWS = sys.platform.startswith("win")


def set_app_id(app_id: str) -> None:
    """Call before the first window is created."""
    if not IS_WINDOWS:
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception as e:
        log.debug("AppUserModelID not set: %s", e)


def _apply(ico: Path) -> int:
    """Set the icon on every visible top-level window of this process. Returns windows changed."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    IMAGE_ICON, LR_LOADFROMFILE, WM_SETICON = 1, 0x10, 0x80
    ICON_SMALL, ICON_BIG = 0, 1
    big_px = max(32, user32.GetSystemMetrics(11))     # SM_CXICON
    small_px = max(16, user32.GetSystemMetrics(49))   # SM_CXSMICON
    big = user32.LoadImageW(None, str(ico), IMAGE_ICON, big_px * 2, big_px * 2, LR_LOADFROMFILE)
    small = user32.LoadImageW(None, str(ico), IMAGE_ICON, small_px, small_px, LR_LOADFROMFILE)
    if not big:
        return 0

    pid = os.getpid()
    found: list[int] = []
    EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    for hwnd in found:
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big)
        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small or big)
    return len(found)


def apply_icon_when_ready(ico: Path, attempts: int = 20) -> None:
    """Keep trying for a few seconds until the pywebview window exists, then set its icon."""
    if not IS_WINDOWS or not ico.exists():
        return

    def worker():
        for _ in range(attempts):
            try:
                if _apply(ico):
                    log.debug("Window icon set from %s", ico.name)
                    return
            except Exception as e:
                log.debug("Window icon not set yet: %s", e)
            time.sleep(0.3)

    threading.Thread(target=worker, name="win-icon", daemon=True).start()
