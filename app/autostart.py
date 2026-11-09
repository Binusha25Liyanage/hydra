"""Start Hydra when Windows starts (per user, no admin rights): HKCU\\...\\Run\\Hydra.

Hydra then opens straight into the tray (--tray), so the schedule runs without a window popping up.
"""
from __future__ import annotations

import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "Hydra"


def supported() -> bool:
    return sys.platform.startswith("win")


def command() -> str:
    if getattr(sys, "frozen", False):                    # Hydra.exe (Phase 12 build)
        return f'"{sys.executable}" --tray'
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")                   # no console window
    main = Path(__file__).resolve().parents[1] / "main.py"
    return f'"{pyw if pyw.exists() else exe}" "{main}" --tray'


def enabled() -> bool:
    if not supported():
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, NAME)
            return True
    except OSError:
        return False


def set_enabled(on: bool) -> None:
    if not supported():
        raise RuntimeError("Only available on Windows")
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(k, NAME)
            except FileNotFoundError:
                pass


def refresh() -> None:
    """If start-up is on, make sure it still points at this copy of Hydra (after moving the folder or updating)."""
    if supported() and enabled():
        set_enabled(True)
