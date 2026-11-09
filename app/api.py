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
import threading as _threading

from . import auth, db, logging_setup, notify, paths, runner, settings, version
from .scheduler import SCHEDULER
from . import autostart, tray
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

    # =========================================================== SFA data (imports)
    @api_method
    def data_choose_files(self):
        import webview
        auth.require()
        if not self._window:
            return {"ok": False, "error": "No window"}
        res = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True,
                                              file_types=("Excel files (*.xlsx)", "All files (*.*)"))
        return {"paths": list(res or [])}

    @api_method
    def data_inspect(self, paths):
        auth.require()
        from .data import store
        return {"files": [store.inspect(p) for p in paths]}

    @api_method
    def data_import(self, items):
        user = auth.require()
        from .data import store
        from .data.sfa_excel import ExportError
        results = []
        for it in items:
            try:
                r = store.import_file(it["path"], replace=bool(it.get("replace")), source="manual",
                                      user=user["username"])
                results.append({"ok": True, "file_name": r["file_name"], "import_id": r["import_id"],
                                "kind": r["kind"], "rows": r["rows"], "replaced": bool(r["replaced"])})
            except ExportError as e:
                results.append({"ok": False, "file_name": Path(it["path"]).name, "error": str(e)})
        done = [r for r in results if r["ok"]]
        if done:
            notify.add("data", "success", f"Imported {len(done)} SFA file(s)",
                       ", ".join(f"{r['file_name']} ({r['rows']} rows)" for r in done)[:400])
        return {"results": results}

    @api_method
    def data_imports(self, kind=""):
        auth.require()
        from .data import store
        return {"imports": store.list_imports(kind or ""), "coverage": store.coverage(21)}

    @api_method
    def data_delete(self, import_id):
        user = auth.require("superadmin", "admin")
        from .data import store
        store.delete_import(int(import_id), user["username"])

    @api_method
    def famulus_choose(self):
        import webview
        auth.require("superadmin", "admin")
        if not self._window:
            return {"ok": False, "error": "No window"}
        res = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False,
                                              file_types=("Famulus database (*.db)", "All files (*.*)"))
        return {"path": (res[0] if res else "")}

    @api_method
    def famulus_inspect(self, path):
        auth.require("superadmin", "admin")
        from .data import famulus
        from .data.sfa_excel import ExportError
        try:
            return famulus.inspect(path)
        except ExportError as e:
            return {"ok": False, "error": str(e)}

    @api_method
    def famulus_import(self, path, parts, overwrite=False):
        user = auth.require("superadmin", "admin")
        from .data import famulus
        from .data.sfa_excel import ExportError
        try:
            rep = famulus.import_all(path, parts, bool(overwrite), user["username"])
        except ExportError as e:
            return {"ok": False, "error": str(e)}
        notify.add("data", "success", "Imported from Famulus", "; ".join(f"{k}: {v}" for k, v in rep.items())[:500])
        return {"report": rep}

    @api_method
    def targets_month(self, month=""):
        auth.require()
        from .data import famulus
        if not month:
            row = db.conn().execute("SELECT month FROM target_months ORDER BY month DESC LIMIT 1").fetchone()
            month = row[0] if row else ""
        return famulus.month_tree(month) if month else {"month": None, "tree": [], "months": []}

    # =========================================================== reports
    @api_method
    def reports_types(self):
        auth.require()
        from . import services
        return {"types": [{"id": r.id, "name": r.name, "service": s.id, "service_name": s.name, "default_on": r.default_on}
                          for s in services.all_services().values() for r in s.reports]}

    @api_method
    def reports_readiness(self, day):
        auth.require()
        from datetime import date as _d
        from .reports import engine
        return {"items": engine.readiness(_d.fromisoformat(day))}

    @api_method
    def reports_generate(self, day, types, formats=None):
        user = auth.require()
        from datetime import date as _d
        from . import runner
        try:
            return runner.run(_d.fromisoformat(day), list(types or []), tuple(formats) if formats is not None else None,
                              user["username"], trigger="manual", delivery="preview")
        except runner.Busy as e:
            return {"ok": False, "error": str(e)}

    @api_method
    def reports_progress(self):
        auth.require()
        from . import runner
        return runner.snapshot()

    @api_method
    def reports_stop(self):
        user = auth.require()
        from . import runner
        if runner.stop():
            db.audit(user["username"], "reports.stop", runner.STATE.get("day") or "")
            return {"stopping": True}
        return {"stopping": False}

    @api_method
    def reports_get(self, ids):
        auth.require()
        from .reports import engine
        return {"reports": [r for r in (engine.get(int(i)) for i in ids or []) if r]}

    @api_method
    def report_image(self, report_id, page=0):
        auth.require()
        from .reports import engine
        return engine.image(int(report_id), int(page or 0))

    @api_method
    def reports_set_status(self, ids, status):
        user = auth.require()
        from .reports import engine
        n = engine.set_status(list(ids or []), status, user["username"])
        return {"updated": n}

    @api_method
    def reports_history(self, report_type="", status=""):
        auth.require()
        from .reports import engine
        return {"reports": engine.history(400, report_type or "", status or "")}

    @api_method
    def open_path(self, path):
        """Open a generated file or its folder (only inside Hydra's output / data folders)."""
        auth.require()
        p = Path(path).resolve()
        roots = [Path(settings.get("output.root") or paths.data_root()).resolve(), paths.data_root().resolve()]
        if not any(str(p).startswith(str(r)) for r in roots):
            return {"ok": False, "error": "This file is outside Hydra's folders"}
        if not p.exists():
            return {"ok": False, "error": "The file no longer exists"}
        if sys.platform.startswith("win"):
            os.startfile(str(p))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(p)])
        return {}

    # =========================================================== targets
    @api_method
    def targets_choose_file(self):
        import webview
        auth.require("superadmin", "admin")
        if not self._window:
            return {"ok": False, "error": "No window"}
        res = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Excel files (*.xlsx)",))
        return {"path": res[0] if res else ""}

    @api_method
    def targets_inspect(self, path):
        auth.require("superadmin", "admin")
        from .data import targets_import
        from .data.sfa_excel import ExportError
        try:
            p = targets_import.parse(path)
        except ExportError as e:
            return {"ok": False, "error": str(e)}
        p.pop("root")
        p["exists"] = bool(p["month"]) and db.conn().execute(
            "SELECT 1 FROM hierarchy_nodes WHERE month=? LIMIT 1", (p["month"],)).fetchone() is not None
        return p

    @api_method
    def targets_import(self, path, month, overwrite=False):
        user = auth.require("superadmin", "admin")
        from .data import targets_import
        from .data.sfa_excel import ExportError
        try:
            r = targets_import.save(targets_import.parse(path), month, bool(overwrite), user["username"])
        except ExportError as e:
            return {"ok": False, "error": str(e)}
        notify.add("data", "success", f"Targets imported for {month}", f"{r['territories']} territories · {r['total']:,.0f}")
        return r

    @api_method
    def targets_set_nowd(self, month, nowd):
        user = auth.require("superadmin", "admin")
        from .data import targets_import
        from .data.sfa_excel import ExportError
        try:
            targets_import.set_nowd(month, int(nowd), user["username"])
        except (ExportError, ValueError) as e:
            return {"ok": False, "error": str(e)}

    # =========================================================== Phase 5: planning (targets editor, competition, aliases)
    @staticmethod
    def _plan(name, *args, edit=True):
        user = auth.require("superadmin", "admin") if edit else auth.require()
        from .services.sales_reports import planning
        try:
            fn = getattr(planning, name)
            out = fn(*args, user=user["username"]) if edit else fn(*args)
        except planning.PlanningError as e:
            return {"ok": False, "error": str(e)}
        return out if isinstance(out, dict) else {"ok": True, "result": out}

    @api_method
    def targets_update(self, changes):
        return self._plan("update_nodes", changes)

    @api_method
    def targets_add(self, parent_id, label, target=0, is_smmt=False):
        return self._plan("add_node", parent_id, label, target, is_smmt)

    @api_method
    def targets_move(self, node_id, parent_id):
        return self._plan("move_node", node_id, parent_id)

    @api_method
    def targets_delete(self, node_id):
        return self._plan("delete_node", node_id)

    @api_method
    def targets_parents(self, month, level):
        return {"parents": self._plan("parents_for", month, int(level), edit=False)["result"]}

    @api_method
    def targets_copy_month(self, src, dst, keep_targets=True):
        return self._plan("copy_month", src, dst, bool(keep_targets))

    @api_method
    def targets_delete_month(self, month):
        return self._plan("delete_month", month)

    @api_method
    def targets_lock(self, month, locked):
        return self._plan("set_locked", month, bool(locked))

    @api_method
    def competition_month(self, month):
        return self._plan("rounds", month, edit=False)

    @api_method
    def competition_save_round(self, month, data):
        return self._plan("save_round", month, data)

    @api_method
    def competition_delete_round(self, round_id):
        return self._plan("delete_round", round_id)

    @api_method
    def competition_save_days(self, month, assignment):
        return self._plan("save_days", month, assignment)

    @api_method
    def competition_copy(self, src, dst):
        return self._plan("copy_rounds", src, dst)

    @api_method
    def aliases_month(self, month):
        return self._plan("aliases", month, edit=False)

    @api_method
    def aliases_set(self, node_id, sfa_name):
        return self._plan("set_alias", node_id, sfa_name)

    @api_method
    def outlets_list(self, month=""):
        return {"outlets": self._plan("outlets", month or None, edit=False)["result"]}

    @api_method
    def outlets_set(self, category_key, label, include):
        return self._plan("set_outlet", category_key, label, bool(include))

    # =========================================================== Phase 9: WhatsApp
    @staticmethod
    def _wa(name, *args, edit=True):
        user = auth.require("superadmin", "admin") if edit else auth.require()
        from .whatsapp import service as W
        try:
            fn = getattr(W, name)
            out = fn(*args, user=user["username"]) if edit else fn(*args)
        except W.WAServiceError as e:
            return {"ok": False, "error": str(e)}
        return out if isinstance(out, dict) else {"ok": True, "result": out}

    @api_method
    def wa_state(self):
        auth.require()
        from .whatsapp import service as W
        q = db.conn().execute("SELECT COUNT(*) FROM wa_sends WHERE status IN ('queued','sending')").fetchone()[0]
        return {"status": wa_status.status(), "worker": W.WORKER.snapshot(), "pending": q,
                "settings": {k: settings.get("whatsapp." + k) for k in ("url", "headless", "gap_s", "send_timeout_s")}}

    @api_method
    def wa_link(self):
        auth.require("superadmin", "admin")
        from .whatsapp import service as W
        W.WORKER.link()

    @api_method
    def wa_unlink(self):
        user = auth.require("superadmin", "admin")
        from .whatsapp import service as W
        W.WORKER.unlink()
        db.audit(user["username"], "whatsapp.unlink", "")

    @api_method
    def wa_recipients(self):
        from .whatsapp import service as W
        auth.require()
        return {"recipients": W.recipients(), "routes": W.routes()}

    @api_method
    def wa_recipient_save(self, data):
        return self._wa("save_recipient", data)

    @api_method
    def wa_recipient_delete(self, rid):
        return self._wa("delete_recipient", rid)

    @api_method
    def wa_routes_save(self, mapping):
        return self._wa("save_routes", mapping)

    @api_method
    def wa_test(self, rid):
        return self._wa("queue_test", rid)

    @api_method
    def reports_send(self, ids, fmt="png", caption="{title}"):
        user = auth.require()
        from .whatsapp import service as W
        settings.set("reports.send_format", fmt)
        settings.set("reports.caption", caption)
        return W.queue_reports(list(ids or []), fmt, caption, user=user["username"])

    @api_method
    def wa_batch(self, batch):
        auth.require()
        from .whatsapp import service as W
        return W.batch_status(batch)

    @api_method
    def wa_cancel(self):
        user = auth.require()
        from .whatsapp import service as W
        return {"cancelled": W.cancel_queued(user["username"])}

    @api_method
    def wa_history(self, limit=200):
        auth.require()
        from .whatsapp import service as W
        return {"items": W.history(int(limit))}

    @api_method
    def wa_settings_save(self, data):
        user = auth.require("superadmin", "admin")
        url = (data.get("url") or "").strip() or "https://web.whatsapp.com"
        if not url.startswith(("http://", "https://")):
            return {"ok": False, "error": "WhatsApp URL must start with https://"}
        settings.set("whatsapp.url", url)
        settings.set("whatsapp.headless", bool(data.get("headless", True)))
        settings.set("whatsapp.gap_s", max(0, min(60, int(data.get("gap_s") or 0))))
        settings.set("whatsapp.send_timeout_s", max(20, min(600, int(data.get("send_timeout_s") or 90))))
        db.audit(user["username"], "whatsapp.settings", url)

    # =========================================================== Phase 10: schedule & background
    @api_method
    def schedule_list(self):
        auth.require()
        from . import scheduler as S
        return {"schedules": S.listing(), "status": SCHEDULER.status(), "runs": runner.history(60),
                "background": {"close_to_tray": bool(settings.get("ui.close_to_tray", True)),
                               "autostart": autostart.enabled(), "autostart_supported": autostart.supported(),
                               "tray_supported": tray.supported()}}

    @api_method
    def schedule_save(self, data):
        user = auth.require("superadmin", "admin")
        from . import scheduler as S
        try:
            return {"id": S.save(data, user["username"])}
        except S.ScheduleError as e:
            return {"ok": False, "error": str(e)}

    @api_method
    def schedule_active(self, sid, active):
        user = auth.require("superadmin", "admin")
        from . import scheduler as S
        S.set_active(sid, bool(active), user["username"])

    @api_method
    def schedule_delete(self, sid):
        user = auth.require("superadmin", "admin")
        from . import scheduler as S
        S.delete(sid, user["username"])

    @api_method
    def schedule_pause(self, paused):
        user = auth.require("superadmin", "admin")
        settings.set("scheduler.enabled", not paused)
        db.audit(user["username"], "schedule.pause_all" if paused else "schedule.resume_all", "")
        SCHEDULER.wake()
        return SCHEDULER.status()

    @api_method
    def schedule_run_now(self, sid):
        """Run a schedule now (its own reports, date rule and delivery) — in the background."""
        user = auth.require()
        from datetime import date as _d
        from . import scheduler as S
        s = next((x for x in S.listing() if x["id"] == int(sid)), None)
        if not s:
            return {"ok": False, "error": "Schedule not found"}
        if runner.STATE["running"]:
            return {"ok": False, "error": "A run is already in progress"}
        rd = S.report_date(s["date_mode"], _d.today())

        def go():
            try:
                runner.run(rd, s["report_types"] or None, tuple(s["formats"]), user["username"], trigger="manual",
                           delivery=s["delivery"], schedule_id=s["id"], label=s["name"])
            except runner.Busy:
                pass
            except Exception:
                logging.getLogger("hydra.api").exception("Run now failed")
        _threading.Thread(target=go, daemon=True, name="hydra-run-now").start()
        return {"started": True, "report_date": rd.isoformat()}

    @api_method
    def runs_history(self, limit=100):
        auth.require()
        return {"runs": runner.history(int(limit))}

    @api_method
    def run_reports(self, run_id):
        auth.require()
        return {"ids": runner.report_ids(int(run_id))}

    @api_method
    def background_save(self, close_to_tray=None, autostart_on=None):
        user = auth.require()
        if close_to_tray is not None:
            settings.set("ui.close_to_tray", bool(close_to_tray))
        if autostart_on is not None:
            try:
                autostart.set_enabled(bool(autostart_on))
            except Exception as e:
                return {"ok": False, "error": f"Could not change Windows start-up: {e}"}
        db.audit(user["username"], "background.save", f"tray={close_to_tray} autostart={autostart_on}")
        return {"close_to_tray": bool(settings.get("ui.close_to_tray", True)), "autostart": autostart.enabled()}

    @api_method
    def territories_list(self):
        auth.require()
        from .data import store
        return {"territories": store.territories()}

    @api_method
    def territory_set_mode(self, name, mode):
        user = auth.require("superadmin", "admin")
        from .data import store
        store.set_selling_mode(name, mode or None, user["username"])

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
            "worker": (sch := SCHEDULER.status()),
            "run": runner.snapshot(),
            "next_run": (sch.get("next") or {}).get("at"),
            "next_run_name": (sch.get("next") or {}).get("name"),
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
