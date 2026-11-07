"""The bridge between the HTML interface and Python (pywebview js_api).

Every public method is callable from JavaScript as
    await window.pywebview.api.<method>(...)
and always returns a JSON-friendly dict:  {"ok": True, ...}  or
{"ok": False, "error": "message for the user"}.
"""
from __future__ import annotations

import functools
import logging
import os
import platform
import subprocess
import sys
from pathlib import Path

from . import auth, db, logging_setup, notify, paths, settings, version
from .startup import StartupSequence
from .whatsapp import status as wa_status

log = logging.getLogger("hydra.api")

# Setup wizard: step number, id, title, subtitle, phase where it becomes available.
WIZARD_STEPS = [
    (1, "welcome", "Welcome", "Introduction", 1),
    (2, "sfa", "SFA Connection", "URL, username, password, browser", 1),
    (3, "pages", "Page URLs", "The 5 SFA pages Hydra uses", 1),
    (4, "filters", "Filter Setup", "Filters + date rules per page", 2),
    (5, "territories", "Territory Sync", "Active territories from SFA", 3),
    (6, "selling_mode", "Selling Mode", "Van / Pre per territory", 3),
    (7, "targets", "Targets", "NSM workbook / Famulus import", 5),
    (8, "calendar", "Calendar & Competition", "NOWD, holidays, rounds", 5),
    (9, "rules", "Report Rules", "Winner limits, outlet categories", 6),
    (10, "output", "Save Location", "Where reports are saved", 1),
    (11, "whatsapp", "WhatsApp Link", "Scan QR, choose recipients", 9),
    (12, "schedule", "Schedule", "Run times, Today / Yesterday", 10),
    (13, "finish", "Finish", "Review and start", 1),
]
CURRENT_PHASE = 1


def api_method(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            out = fn(*args, **kwargs)
            if out is None:
                out = {}
            if isinstance(out, dict):
                out.setdefault("ok", True)
            return out
        except auth.AuthError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            log.exception("API %s failed", fn.__name__)
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return wrapper


class Api:
    def __init__(self):
        self._window = None
        self._startup: StartupSequence | None = None

    def _attach(self, window) -> None:
        self._window = window

    # =========================================================== app / startup
    @api_method
    def app_info(self):
        return {"name": version.APP_NAME, "version": version.VERSION, "phase": version.PHASE,
                "build_date": version.BUILD_DATE, "platform": platform.platform(terse=True)}

    @api_method
    def startup_begin(self, mode: str | None = None):
        if self._startup is None or self._startup.result.finished:
            self._startup = StartupSequence(mode)
            self._startup.start()
        return {"mode": self._startup.mode}

    @api_method
    def startup_poll(self):
        if self._startup is None:
            return {"started": False}
        return self._startup.snapshot()

    @api_method
    def startup_skip(self):
        if self._startup:
            self._startup.skip_current()

    # =========================================================== auth
    @api_method
    def auth_state(self):
        return {"has_users": auth.has_users(), "user": auth.current(),
                "setup_completed": bool(settings.get("setup.completed"))}

    @api_method
    def auth_create_first_admin(self, username, display_name, password, confirm):
        if password != confirm:
            return {"ok": False, "error": "The two passwords do not match."}
        user = auth.create_first_admin(username, password, display_name)
        auth.login(username, password, remember=False)
        notify.add("system", "success", "Administrator account created", f"Signed in as {user['display_name']}")
        return {"user": user, "next": "wizard"}

    @api_method
    def auth_login(self, username, password, remember=False):
        user = auth.login(username, password, bool(remember))
        nxt = "app" if settings.get("setup.completed") else "wizard"
        return {"user": user, "next": nxt}

    @api_method
    def auth_logout(self):
        auth.logout()

    @api_method
    def auth_change_password(self, old, new, confirm):
        if new != confirm:
            return {"ok": False, "error": "The two new passwords do not match."}
        auth.change_password(old, new)

    @api_method
    def users_list(self):
        auth.require("superadmin")
        return {"users": auth.list_users(), "roles": list(auth.ROLES)}

    @api_method
    def users_create(self, data):
        admin = auth.require("superadmin")
        u = auth.create_user(data.get("username", ""), data.get("password", ""), data.get("role", "user"),
                             data.get("display_name", ""), by=admin["username"])
        return {"user": u}

    @api_method
    def users_update(self, data):
        auth.update_user(int(data["id"]), data["role"], bool(data["active"]), data.get("display_name", ""))

    @api_method
    def users_reset_password(self, user_id, new):
        auth.reset_password(int(user_id), new)

    # =========================================================== setup wizard
    @api_method
    def wizard_state(self):
        auth.require("superadmin", "admin")
        done = set(settings.get("setup.completed_steps") or [])
        steps = [{"n": n, "id": sid, "title": t, "subtitle": sub, "phase": ph,
                  "available": ph <= CURRENT_PHASE, "done": sid in done}
                 for n, sid, t, sub, ph in WIZARD_STEPS]
        return {"steps": steps, "sfa": self._sfa_form(), "pages": settings.page_profiles(),
                "output": {"root": settings.get("output.root") or self._default_output()},
                "completed": bool(settings.get("setup.completed"))}

    def _sfa_form(self) -> dict:
        return {"base_url": settings.get("sfa.base_url"), "login_path": settings.get("sfa.login_path"),
                "username": settings.get("sfa.username"), "has_password": settings.has_secret("sfa.password"),
                "browser": settings.get("sfa.browser"), "headless": settings.get("sfa.headless"),
                "timeout_s": settings.get("startup.sfa_timeout_s"),
                "last_test": settings.get("status.sfa_last_test", {})}

    @staticmethod
    def _default_output() -> str:
        docs = Path(os.environ.get("USERPROFILE", Path.home())) / "Documents"
        return str(docs / "Hydra Reports")

    def _mark_step(self, step_id: str, done: bool = True) -> None:
        cur = list(settings.get("setup.completed_steps") or [])
        if done and step_id not in cur:
            cur.append(step_id)
        if not done and step_id in cur:
            cur.remove(step_id)
        settings.set("setup.completed_steps", cur)

    @api_method
    def wizard_mark(self, step_id, done=True):
        auth.require("superadmin", "admin")
        self._mark_step(step_id, bool(done))

    @api_method
    def sfa_save(self, data):
        user = auth.require("superadmin", "admin")
        base = (data.get("base_url") or "").strip().rstrip("/")
        if not base.startswith(("http://", "https://")):
            return {"ok": False, "error": "SFA URL must start with https://"}
        if not (data.get("username") or "").strip():
            return {"ok": False, "error": "Enter the SFA username."}
        if data.get("browser") not in ("chromium", "msedge", "chrome"):
            return {"ok": False, "error": "Choose a browser."}
        old_user = settings.get("sfa.username")
        settings.set_many({
            "sfa.base_url": base,
            "sfa.login_path": (data.get("login_path") or "/").strip() or "/",
            "sfa.username": data["username"].strip(),
            "sfa.browser": data["browser"],
            "sfa.headless": bool(data.get("headless", True)),
            "startup.sfa_timeout_s": max(15, min(180, int(data.get("timeout_s") or 45))),
        })
        if data.get("password"):
            settings.set_secret("sfa.password", data["password"])
        if not settings.has_secret("sfa.password"):
            return {"ok": False, "error": "Enter the SFA password."}
        if old_user != data["username"].strip() or data.get("password"):
            paths.sfa_state_path().unlink(missing_ok=True)   # credentials changed: forget old session
        db.audit(user["username"], "settings.sfa", f"{base} as {data['username'].strip()}")
        self._mark_step("sfa")
        return {"sfa": self._sfa_form()}

    @api_method
    def sfa_test_login(self, data=None):
        """Live Playwright sign-in with the form values (password from the form or Credential Manager)."""
        auth.require("superadmin", "admin")
        from .sfa.login import check_login, config_from_settings
        data = data or {}
        overrides = {k: data[k] for k in ("base_url", "login_path", "username", "browser", "headless", "timeout_s")
                     if data.get(k) not in (None, "")}
        cfg = config_from_settings(password=data.get("password") or None, overrides=overrides)
        paths.sfa_state_path().unlink(missing_ok=True)       # always test a fresh login
        r = check_login(cfg)
        res = r.as_dict()
        res["ts"] = db.now_iso()
        settings.set("status.sfa_last_test", res)
        return {"result": res}

    @api_method
    def pages_save(self, pages):
        user = auth.require("superadmin", "admin")
        for pg in pages:
            settings.save_page_url(pg["key"], pg.get("url", ""))
        db.audit(user["username"], "settings.pages", ", ".join(p["key"] for p in pages))
        self._mark_step("pages")
        return {"pages": settings.page_profiles()}

    @api_method
    def pages_test(self, keys=None):
        auth.require("superadmin", "admin")
        from .sfa.login import check_pages, config_from_settings
        pages = [p for p in settings.page_profiles() if not keys or p["key"] in keys]
        res = check_pages(config_from_settings(),
                          [{"key": p["key"], "name": p["name"], "url": p["full_url"]} for p in pages])
        return {"results": res}

    @api_method
    def output_save(self, root):
        user = auth.require("superadmin", "admin")
        root = (root or "").strip()
        if not root:
            return {"ok": False, "error": "Choose a folder."}
        p = Path(root)
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".hydra_write_test"
            probe.write_text("ok")
            probe.unlink()
        except OSError as e:
            return {"ok": False, "error": f"Hydra cannot write to this folder: {e.strerror or e}"}
        settings.set("output.root", str(p))
        db.audit(user["username"], "settings.output", str(p))
        self._mark_step("output")
        return {"root": str(p)}

    @api_method
    def choose_folder(self, start=""):
        import webview
        if not self._window:
            return {"ok": False, "error": "No window"}
        res = self._window.create_file_dialog(webview.FOLDER_DIALOG, directory=start or "")
        return {"path": res[0] if res else ""}

    @api_method
    def wizard_complete(self):
        user = auth.require("superadmin", "admin")
        missing = [s for s in ("sfa", "pages", "output") if s not in (settings.get("setup.completed_steps") or [])]
        if missing:
            names = {"sfa": "SFA Connection", "pages": "Page URLs", "output": "Save Location"}
            return {"ok": False, "error": "Please complete: " + ", ".join(names[m] for m in missing)}
        settings.set("setup.completed", True)
        db.audit(user["username"], "setup.complete", "")
        notify.add("system", "success", "Setup complete",
                   "Hydra will now run the full startup check every time it opens.")
        return {"next": "splash"}

    # =========================================================== settings
    @api_method
    def settings_get(self):
        auth.require()
        return {
            "sfa": self._sfa_form(),
            "pages": settings.page_profiles(),
            "output": {"root": settings.get("output.root")},
            "startup": {"check_sfa_login": settings.get("startup.check_sfa_login"),
                        "check_whatsapp": settings.get("startup.check_whatsapp"),
                        "sfa_timeout_s": settings.get("startup.sfa_timeout_s")},
            "reports": {"title_prefix": settings.get("reports.title_prefix")},
            "notifications": {"windows_toasts": settings.get("notifications.windows_toasts"),
                              "sound": settings.get("notifications.sound")},
            "general": {"theme": settings.get("ui.theme"), "titlebar": settings.get("ui.titlebar")},
            "datameter": {"monthly_cap_mb": settings.get("datameter.monthly_cap_mb")},
            "user": auth.current(),
        }

    @api_method
    def settings_save(self, section, data):
        user = auth.require("superadmin", "admin")
        allowed = {
            "startup": {"check_sfa_login": bool, "check_whatsapp": bool, "sfa_timeout_s": int},
            "reports": {"title_prefix": str},
            "notifications": {"windows_toasts": bool, "sound": bool},
            "general": {"theme": str, "titlebar": str},
            "datameter": {"monthly_cap_mb": int},
        }
        prefix = {"general": "ui", "startup": "startup", "reports": "reports",
                  "notifications": "notifications", "datameter": "datameter"}
        if section not in allowed:
            return {"ok": False, "error": f"Unknown settings section {section}"}
        vals = {}
        for k, typ in allowed[section].items():
            if k in data:
                vals[f"{prefix[section]}.{k}"] = typ(data[k]).strip() if typ is str else typ(data[k])
        if "ui.titlebar" in vals and vals["ui.titlebar"] not in ("black", "red"):
            return {"ok": False, "error": "Title bar must be black or red."}
        settings.set_many(vals)
        db.audit(user["username"], f"settings.{section}", ", ".join(vals))
        if "ui.titlebar" in vals:
            from . import winicon
            winicon.style_titlebar(vals["ui.titlebar"])     # apply immediately
        return {}

    # =========================================================== status / dashboard
    @api_method
    def status_bar(self):
        last = settings.get("status.last_startup", {}) or {}
        sfa = last.get("sfa", {}) or {}
        return {
            "sfa": {"logged_in": bool(sfa.get("logged_in")), "reachable": sfa.get("reachable"),
                    "latency_ms": sfa.get("latency_ms", 0), "message": sfa.get("message", ""),
                    "display_name": sfa.get("display_name", ""), "ts": sfa.get("ts", "")},
            "whatsapp": wa_status.status(),
            "worker": {"state": "not_installed", "label": "Scheduler arrives in Phase 10"},
            "next_run": None,
            "data_today_mb": 0.0,
            "unread": notify.unread_count(),
            "version": version.VERSION,
            "user": auth.current(),
        }

    @api_method
    def dashboard_summary(self):
        auth.require()
        row = db.conn().execute("SELECT * FROM startup_history ORDER BY id DESC LIMIT 1").fetchone()
        import json
        startup = None
        if row:
            startup = {"ts": row["ts"], "mode": row["mode"], "duration_ms": row["duration_ms"],
                       "result": row["result"], "steps": json.loads(row["steps_json"])}
        done = set(settings.get("setup.completed_steps") or [])
        checklist = [{"id": sid, "title": t, "phase": ph, "done": sid in done or sid in ("welcome", "finish")}
                     for _, sid, t, _, ph in WIZARD_STEPS if sid not in ("welcome", "finish")]
        return {"startup": startup, "checklist": checklist, "phase": CURRENT_PHASE}

    # =========================================================== notifications
    @api_method
    def notifications_list(self, only_unread=False, kind=""):
        auth.require()
        return {"items": notify.listing(300, bool(only_unread), kind or ""), "unread": notify.unread_count()}

    @api_method
    def notifications_mark_read(self, ids=None):
        auth.require()
        notify.mark_read([int(i) for i in ids] if ids else None)
        return {"unread": notify.unread_count()}

    # =========================================================== logs
    @api_method
    def logs_query(self, level="", search="", limit=500, before_id=None):
        auth.require()
        q, args = "SELECT * FROM logs WHERE 1=1", []
        levels = {"ERROR": ("ERROR", "CRITICAL"), "WARNING": ("WARNING", "ERROR", "CRITICAL"),
                  "INFO": ("INFO", "WARNING", "ERROR", "CRITICAL")}
        if level in levels:
            q += f" AND level IN ({','.join('?' * len(levels[level]))})"
            args += list(levels[level])
        if search:
            q += " AND (message LIKE ? OR source LIKE ?)"
            args += [f"%{search}%", f"%{search}%"]
        if before_id:
            q += " AND id < ?"
            args.append(int(before_id))
        q += " ORDER BY id DESC LIMIT ?"
        args.append(max(1, min(5000, int(limit))))
        rows = [dict(r) for r in db.conn().execute(q, args)]
        rows.reverse()
        return {"rows": rows}

    @api_method
    def copy_text(self, text):
        import pyperclip
        pyperclip.copy(text or "")
        return {"chars": len(text or "")}

    @api_method
    def logs_export(self, text):
        import webview
        if not self._window:
            return {"ok": False, "error": "No window"}
        res = self._window.create_file_dialog(webview.SAVE_DIALOG, save_filename="hydra_log.txt",
                                              file_types=("Text files (*.txt)",))
        if not res:
            return {"saved": ""}
        target = res if isinstance(res, str) else res[0]
        Path(target).write_text(text or "", encoding="utf-8")
        return {"saved": target}

    # =========================================================== about / system
    @api_method
    def about(self):
        auth.require()
        try:
            import importlib.metadata as md
            pw = md.version("playwright")
        except Exception:
            pw = "not installed"
        dbp = paths.db_path()
        return {"name": version.APP_NAME, "version": version.VERSION, "phase": version.PHASE,
                "build_date": version.BUILD_DATE, "data_folder": str(paths.data_root()),
                "db_path": str(dbp), "db_size_mb": round(dbp.stat().st_size / 1024 / 1024, 2) if dbp.exists() else 0,
                "schema": db.schema_version(), "python": sys.version.split()[0], "playwright": pw,
                "platform": platform.platform(terse=True)}

    @api_method
    def open_folder(self, which="data"):
        auth.require()
        target = {"data": paths.data_root(), "logs": paths.logs_dir(),
                  "output": Path(settings.get("output.root") or paths.data_root())}.get(which, paths.data_root())
        target.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return {"path": str(target)}

    @api_method
    def recent_log_text(self, lines=400):
        return {"text": "\n".join(logging_setup.recent_lines()[-int(lines):])}
