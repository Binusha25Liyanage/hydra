"""Settings stored as JSON values in the settings table.

Secrets (the SFA password) never go into the database: they are stored in
Windows Credential Manager through `keyring`.
"""
from __future__ import annotations

import copy
import json
import logging

from . import db

log = logging.getLogger("hydra.settings")

KEYRING_SERVICE = "Hydra"

# Default SFA page paths, taken from the SalesPro URLs (user can change all of them).
DEFAULT_PAGES = {
    "sku":             {"name": "Outlet Wise SKU Sales Report", "path": "/it/reports/outlet_wise_sku_sales"},
    "callage":         {"name": "Callage Summary",               "path": "/it/reports/callage_summary"},
    "preselling":      {"name": "View Pre-Selling (Sales Order)", "path": "/it/pre_selling"},
    "territory":       {"name": "View Territory",                "path": "/it/level-six"},
    "rep_performance": {"name": "Rep Performance Report",        "path": ""},
}

DEFAULTS: dict = {
    # SFA connection
    "sfa.base_url": "https://lakmee.salespro.lk",
    "sfa.login_path": "/",
    "sfa.username": "",
    "sfa.browser": "chromium",          # chromium | msedge | chrome
    "sfa.headless": True,
    # Login form selectors: tried in order. Editable in Settings → SFA Connection → Advanced.
    "sfa.selectors": {
        "username": ['input[name="username"]', 'input[name="email"]', "input#username",
                     "input#email", 'input[type="email"]', 'input[type="text"]'],
        "password": ['input[type="password"]'],
        "submit": ['button[type="submit"]', 'input[type="submit"]',
                   'button:has-text("Login")', 'button:has-text("Log in")',
                   'button:has-text("Sign in")'],
        # Any of these visible after login means "logged in"
        "logged_in": ["text=/Welcome,/i", "text=REPORTS", "text=DASHBOARD"],
    },
    # Output
    "output.root": "",
    # Startup
    "startup.check_sfa_login": True,
    "startup.sfa_timeout_s": 45,
    "startup.check_whatsapp": True,
    # Setup wizard
    "setup.completed": False,
    "setup.completed_steps": [],
    # Reports
    "reports.title_prefix": "",
    # Notifications
    "notifications.windows_toasts": True,
    "notifications.sound": False,
    # UI
    "ui.theme": "dark",
    "ui.titlebar": "black",             # black (red title) | red (white title)
    "ui.sidebar_collapsed": False,
    # Data meter
    "datameter.monthly_cap_mb": 2048,
}


def get(key: str, default=None):
    row = db.conn().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if row is None:
        if default is not None:
            return default
        return copy.deepcopy(DEFAULTS.get(key))
    return json.loads(row["value"])


def set(key: str, value) -> None:  # noqa: A001 - mirrors get()
    db.conn().execute(
        "INSERT INTO settings(key, value, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, json.dumps(value), db.now_iso()),
    )


def set_many(values: dict) -> None:
    with db.tx():
        for k, v in values.items():
            set(k, v)


def get_prefix(prefix: str) -> dict:
    """All settings under a prefix, defaults filled in."""
    out = {k: copy.deepcopy(v) for k, v in DEFAULTS.items() if k.startswith(prefix)}
    for row in db.conn().execute("SELECT key, value FROM settings WHERE key LIKE ?", (prefix + "%",)):
        out[row["key"]] = json.loads(row["value"])
    return out


def sfa_url(path: str) -> str:
    base = (get("sfa.base_url") or "").rstrip("/")
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return base + "/" + path.lstrip("/")


# ---------------------------------------------------------------- page profiles
def ensure_page_profiles() -> None:
    c = db.conn()
    for key, p in DEFAULT_PAGES.items():
        c.execute(
            "INSERT OR IGNORE INTO page_profiles(key, name, url, updated_at) VALUES (?,?,?,?)",
            (key, p["name"], p["path"], db.now_iso()),
        )


def page_profiles() -> list[dict]:
    ensure_page_profiles()
    order = list(DEFAULT_PAGES)
    rows = [dict(r) for r in db.conn().execute("SELECT * FROM page_profiles")]
    rows.sort(key=lambda r: order.index(r["key"]) if r["key"] in order else 99)
    for r in rows:
        r["full_url"] = sfa_url(r["url"])
        r["filters"] = json.loads(r.pop("filters_json"))
        r["date_rules"] = json.loads(r.pop("date_rules_json"))
    return rows


def save_page_url(key: str, url: str) -> None:
    ensure_page_profiles()
    db.conn().execute(
        "UPDATE page_profiles SET url=?, updated_at=? WHERE key=?", (url.strip(), db.now_iso(), key)
    )


# ---------------------------------------------------------------- secrets
_fallback_warned = False


def set_secret(name: str, value: str) -> None:
    try:
        import keyring
        keyring.set_password(KEYRING_SERVICE, name, value)
        db.conn().execute("DELETE FROM settings WHERE key=?", (f"secret.fallback.{name}",))
    except Exception as e:  # no keyring backend (non-Windows dev box)
        global _fallback_warned
        if not _fallback_warned:
            log.warning("Credential Manager unavailable (%s); storing secret locally (dev only).", e)
            _fallback_warned = True
        import base64
        set(f"secret.fallback.{name}", base64.b64encode(value.encode()).decode())


def get_secret(name: str) -> str:
    try:
        import keyring
        v = keyring.get_password(KEYRING_SERVICE, name)
        if v is not None:
            return v
    except Exception:
        pass
    fb = get(f"secret.fallback.{name}", "")
    if fb:
        import base64
        return base64.b64decode(fb).decode()
    return ""


def has_secret(name: str) -> bool:
    return bool(get_secret(name))
