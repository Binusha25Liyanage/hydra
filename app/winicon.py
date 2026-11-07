"""Windows window chrome for Hydra: taskbar identity, window icon and title-bar colours.

- Own AppUserModelID, so the taskbar does not group Hydra under python.exe.
- hydra.ico set as the window's big/small icon (WM_SETICON).
- Title bar coloured through DWM (Windows 11): black with a red title, or red
  with a white title. Minimise / maximise / close stay native Windows buttons,
  and snapping / resizing keep working.
The packaged Hydra.exe (Phase 12) also gets the icon from the build.
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

# Title-bar styles. Colours are written as #RRGGBB and converted to COLORREF (0x00BBGGRR).
TITLEBAR_STYLES = {
    "black": {"caption": "#0B0C0E", "text": "#D42A45", "border": "#B3172F"},
    "red":   {"caption": "#9A1428", "text": "#FFFFFF", "border": "#5A0C18"},
}


def set_app_id(app_id: str) -> None:
    """Call before the first window is created."""
    if not IS_WINDOWS:
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception as e:
        log.debug("AppUserModelID not set: %s", e)


def _colorref(hex_color: str) -> int:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


def _own_windows() -> list[int]:
    """Visible top-level windows that belong to this process."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
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
    return found


def set_icon(ico: Path) -> int:
    """Set hydra.ico on every Hydra window. Returns the number of windows changed."""
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
    windows = _own_windows()
    for hwnd in windows:
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big)
        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small or big)
    return len(windows)


def style_titlebar(mode: str = "black") -> int:
    """Colour the native title bar. On Windows 10 only dark mode applies (colours need Windows 11)."""
    if not IS_WINDOWS:
        return 0
    import ctypes
    from ctypes import wintypes
    style = TITLEBAR_STYLES.get(mode, TITLEBAR_STYLES["black"])
    dwm = ctypes.windll.dwmapi
    DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_BORDER_COLOR, DWMWA_CAPTION_COLOR, DWMWA_TEXT_COLOR = 20, 34, 35, 36
    windows = _own_windows()
    for hwnd in windows:
        h = wintypes.HWND(hwnd)
        dark = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(h, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark), ctypes.sizeof(dark))
        for attr, key in ((DWMWA_CAPTION_COLOR, "caption"), (DWMWA_TEXT_COLOR, "text"), (DWMWA_BORDER_COLOR, "border")):
            val = wintypes.DWORD(_colorref(style[key]))
            dwm.DwmSetWindowAttribute(h, attr, ctypes.byref(val), ctypes.sizeof(val))
        # SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED: repaint the frame now
        ctypes.windll.user32.SetWindowPos(h, None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
    return len(windows)


def apply_when_ready(ico: Path, titlebar: str = "black", attempts: int = 20) -> None:
    """Retry for a few seconds until the pywebview window exists, then set icon + title bar."""
    if not IS_WINDOWS:
        return

    def worker():
        for _ in range(attempts):
            try:
                if (set_icon(ico) if ico.exists() else len(_own_windows())):
                    style_titlebar(titlebar)
                    log.debug("Window icon and %s title bar applied", titlebar)
                    return
            except Exception as e:
                log.debug("Window chrome not applied yet: %s", e)
            time.sleep(0.3)

    threading.Thread(target=worker, name="win-chrome", daemon=True).start()
