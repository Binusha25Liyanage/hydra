"""Where Hydra keeps its code resources and its runtime data.

Runtime data (database, logs, browser profiles) lives in the user's
LocalAppData folder so it survives re-installs and never sits inside
Program Files:  %LOCALAPPDATA%\\Hydra\\
Set HYDRA_DATA_DIR to override (useful for testing).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_FOLDER = "Hydra"


def resource_root() -> Path:
    """Folder that contains ui/ (works from source and from a PyInstaller build)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def ui_dir() -> Path:
    return resource_root() / "ui"


def data_root() -> Path:
    override = os.environ.get("HYDRA_DATA_DIR")
    if override:
        root = Path(override)
    else:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
        root = Path(base) / APP_FOLDER
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sub(name: str) -> Path:
    p = data_root() / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return _sub("data") / "hydra.db"


def logs_dir() -> Path:
    return _sub("logs")


def profiles_dir() -> Path:
    return _sub("profiles")


def sfa_state_path() -> Path:
    """Saved SFA browser session (cookies) so runs can skip the login form."""
    return _sub("data") / "sfa_session.json"


def whatsapp_profile_dir() -> Path:
    p = profiles_dir() / "whatsapp"
    p.mkdir(parents=True, exist_ok=True)
    return p


def remember_token_path() -> Path:
    return _sub("data") / "remember.token"


def lock_path() -> Path:
    return data_root() / "hydra.lock"
