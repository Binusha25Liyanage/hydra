"""The splash-screen startup sequence.

Two modes:
  first_run — Hydra is not set up yet. Only local preparation is real
              (database, folders); the bar runs smoothly for the look and
              hands over to account creation + the setup wizard.
  daily     — every real check is run and the bar moves with them:
              configuration, database health, save folder, internet,
              SFA server, SFA sign-in (live Playwright login), WhatsApp,
              schedule, and this month's data readiness.

Warnings never block Hydra from opening; only a damaged database does.
The UI polls `snapshot()` every ~150 ms.
"""
from __future__ import annotations

import json
import logging
import shutil
import threading
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

from . import auth, db, net, notify, paths, settings
from .whatsapp import status as wa_status

log = logging.getLogger("hydra.startup")

OK, WARN, FAIL, SKIP, RUN, WAIT = "ok", "warning", "error", "skipped", "running", "pending"


@dataclass
class Step:
    id: str
    label: str
    weight: int
    fn: Callable[["Step"], None]
    fatal: bool = False
    skippable: bool = False
    state: str = WAIT
    detail: str = ""
    sub: int = 0          # 0..100 progress inside the step
    ms: int = 0

    def public(self) -> dict:
        return {"id": self.id, "label": self.label, "state": self.state, "detail": self.detail,
                "skippable": self.skippable, "ms": self.ms}


@dataclass
class StartupResult:
    mode: str
    finished: bool = False
    fatal: bool = False
    warnings: int = 0
    next: str = ""          # create_admin | login | wizard | app
    sfa: dict = field(default_factory=dict)
    whatsapp: dict = field(default_factory=dict)


class StartupSequence:
    def __init__(self, mode: str | None = None):
        self.mode = mode or ("daily" if settings_ready() else "first_run")
        self.result = StartupResult(self.mode)
        self.current = ""
        self.message = "Starting Hydra…"
        self._skip = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.steps = self._first_run_steps() if self.mode == "first_run" else self._daily_steps()

    # --------------------------------------------------------------- public
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="startup", daemon=True)
        self._thread.start()

    def skip_current(self) -> None:
        self._skip.set()

    def snapshot(self) -> dict:
        with self._lock:
            total = sum(s.weight for s in self.steps)
            done = 0.0
            for s in self.steps:
                if s.state in (OK, WARN, FAIL, SKIP):
                    done += s.weight
                elif s.state == RUN:
                    done += s.weight * s.sub / 100
            return {
                "mode": self.mode,
                "progress": round(100 * done / total) if total else 100,
                "message": self.message,
                "current": self.current,
                "steps": [s.public() for s in self.steps],
                "finished": self.result.finished,
                "fatal": self.result.fatal,
                "warnings": self.result.warnings,
                "next": self.result.next,
                "skippable": any(s.state == RUN and s.skippable for s in self.steps),
            }

    # --------------------------------------------------------------- engine
    def _run(self) -> None:
        t0 = time.perf_counter()
        for step in self.steps:
            with self._lock:
                step.state, step.sub, self.current = RUN, 0, step.id
                self.message = step.label + "…"
            self._skip.clear()
            s0 = time.perf_counter()
            try:
                step.fn(step)
                if step.state == RUN:
                    step.state = OK
            except Exception as e:  # a check failing must not crash the splash
                log.exception("Startup step %s failed", step.id)
                step.state, step.detail = FAIL, str(e)
            step.ms = int((time.perf_counter() - s0) * 1000)
            if step.state == FAIL and step.fatal:
                self.result.fatal = True
                self.message = f"{step.label} failed — {step.detail}"
                break
        self.result.warnings = sum(1 for s in self.steps if s.state in (WARN, FAIL))
        if not self.result.fatal:
            self.result.next = self._route()
            self.message = ("Ready" if not self.result.warnings
                            else f"Ready — {self.result.warnings} item(s) need attention")
        self.result.finished = True
        self._record(int((time.perf_counter() - t0) * 1000))

    def _route(self) -> str:
        if not auth.has_users():
            return "create_admin"
        if not settings.get("setup.completed"):
            return "login"          # login, then the wizard continues
        return "app" if auth.auto_login() else "login"

    def _record(self, ms: int) -> None:
        try:
            result = "fatal" if self.result.fatal else ("warnings" if self.result.warnings else "ok")
            db.conn().execute(
                "INSERT INTO startup_history(ts, mode, duration_ms, result, steps_json) VALUES (?,?,?,?,?)",
                (db.now_iso(), self.mode, ms, result, json.dumps([s.public() for s in self.steps])),
            )
            settings.set("status.last_startup", {
                "ts": db.now_iso(), "result": result, "sfa": self.result.sfa, "whatsapp": self.result.whatsapp,
            })
            log.info("Startup (%s) finished in %s ms: %s", self.mode, ms, result)
        except Exception:
            log.exception("Could not record startup history")

    def _set(self, step: Step, sub: int, msg: str | None = None) -> None:
        with self._lock:
            step.sub = max(0, min(100, sub))
            if msg:
                self.message = msg

    # --------------------------------------------------------------- first run
    def _first_run_steps(self) -> list[Step]:
        def prepare_db(step: Step):
            self._glide(step, 0, 60, 0.6, "Preparing database…")
            db.init()
            settings.ensure_page_profiles()
            step.detail = "Database created"
            self._glide(step, 60, 100, 0.3)

        def prepare_folders(step: Step):
            self._glide(step, 0, 100, 0.7, "Preparing folders…")
            paths.logs_dir(); paths.profiles_dir()
            step.detail = str(paths.data_root())

        def load_ui(step: Step):
            self._glide(step, 0, 100, 0.8, "Loading interface…")

        def welcome(step: Step):
            self._glide(step, 0, 100, 0.6, "Welcome to Hydra — let's set things up")

        return [
            Step("db", "Preparing database", 30, prepare_db, fatal=True),
            Step("folders", "Preparing folders", 20, prepare_folders),
            Step("ui", "Loading interface", 30, load_ui),
            Step("welcome", "Starting first-time setup", 20, welcome),
        ]

    def _glide(self, step: Step, a: int, b: int, seconds: float, msg: str | None = None) -> None:
        """Animate a step's sub-progress (first-run cosmetic mode only)."""
        n = max(1, int(seconds / 0.05))
        for i in range(n + 1):
            self._set(step, a + (b - a) * i // n, msg if i == 0 else None)
            time.sleep(seconds / n)

    # --------------------------------------------------------------- daily
    def _daily_steps(self) -> list[Step]:
        def config(step: Step):
            missing = [k for k in ("sfa.base_url", "sfa.username") if not settings.get(k)]
            if not settings.has_secret("sfa.password"):
                missing.append("SFA password")
            if missing:
                step.state, step.detail = WARN, "Missing: " + ", ".join(missing)
            else:
                step.detail = "Settings loaded"

        def database(step: Step):
            db.init()
            self._set(step, 50, "Checking database health…")
            res = db.quick_check()
            if res != "ok":
                step.state, step.detail = FAIL, f"Database check failed: {res}"
                return
            size = paths.db_path().stat().st_size / 1024 / 1024
            step.detail = f"Healthy · {size:.1f} MB · schema v{db.schema_version()}"

        def storage(step: Step):
            root = settings.get("output.root")
            if not root:
                step.state, step.detail = WARN, "Save location not set (Settings → Save Location)"
                return
            p = Path(root)
            try:
                p.mkdir(parents=True, exist_ok=True)
                probe = p / ".hydra_write_test"
                probe.write_text("ok"); probe.unlink()
            except OSError as e:
                step.state, step.detail = WARN, f"Cannot write to {root} ({e.strerror})"
                return
            free_gb = shutil.disk_usage(p).free / 1024 ** 3
            if free_gb < 1:
                step.state, step.detail = WARN, f"Low disk space: {free_gb:.1f} GB free"
            else:
                step.detail = f"{root} · {free_gb:.0f} GB free"

        def internet(step: Step):
            ok, msg = net.internet_ok(settings.get("sfa.base_url"))
            step.detail = msg
            if not ok:
                step.state = WARN

        def sfa_server(step: Step):
            ok, msg, ms = net.reach(settings.get("sfa.base_url"))
            step.detail = msg
            self.result.sfa = {"reachable": ok, "latency_ms": ms}
            if not ok:
                step.state = WARN

        def sfa_login(step: Step):
            if not settings.get("startup.check_sfa_login"):
                step.state, step.detail = SKIP, "Turned off in Settings → Startup"
                return
            if self.result.sfa.get("reachable") is False:
                step.state, step.detail = SKIP, "Skipped — SFA server not reachable"
                self.result.sfa["logged_in"] = False
                return
            from .sfa.login import check_login, config_from_settings
            cfg = config_from_settings()

            def prog(pct: int, msg: str):
                self._set(step, pct, f"SFA sign-in: {msg}")

            # Sign in on a helper thread so "Skip" works instantly, even while the
            # browser is still waiting for SFA to answer.
            box: dict = {}
            worker = threading.Thread(target=lambda: box.update(r=check_login(cfg, prog, self._skip)),
                                      name="sfa-login", daemon=True)
            worker.start()
            while worker.is_alive() and not self._skip.is_set():
                worker.join(0.1)
            if "r" not in box:
                step.state, step.detail = SKIP, "Skipped by user — Hydra will sign in before the first run"
                self.result.sfa.update({"logged_in": False, "message": "SFA check skipped", "kind": "cancelled",
                                        "ts": db.now_iso()})
                return
            r = box["r"]
            self.result.sfa.update({"logged_in": r.ok, "display_name": r.display_name,
                                    "message": r.message, "kind": r.kind, "ts": db.now_iso()})
            step.detail = r.message + (f" as {r.display_name}" if r.display_name else "")
            if r.kind == "cancelled":
                step.state = SKIP
            elif not r.ok:
                step.state = WARN
                notify.add("sfa", "warning", "SFA sign-in failed at startup", r.message, "settings:sfa")

        def whatsapp(step: Step):
            if not settings.get("startup.check_whatsapp"):
                step.state, step.detail = SKIP, "Turned off in Settings → Startup"
                return
            st = wa_status.status()
            self.result.whatsapp = st
            step.detail = st["message"]
            if not st["linked"]:
                step.state = WARN

        def schedule(step: Step):
            # The scheduler/worker arrives in Phase 10; until then report what is configured.
            slots = settings.get("schedule.slots", []) or []
            step.detail = (f"{len(slots)} scheduled time(s)" if slots
                           else "No schedule yet (set up in Schedule)")

        def data_ready(step: Step):
            month = date.today().strftime("%Y-%m")
            notes = []
            if db.table_exists("target_months"):
                row = db.conn().execute("SELECT 1 FROM target_months WHERE month=?", (month,)).fetchone()
                if row is None:
                    notes.append(f"Targets for {date.today():%B %Y} not set")
            else:
                notes.append("Targets editor arrives in Phase 5")
            step.detail = "; ".join(notes) or f"Targets and calendar ready for {date.today():%B %Y}"
            if notes and db.table_exists("target_months"):
                step.state = WARN

        def ready(step: Step):
            self._set(step, 100, "Opening Hydra…")
            step.detail = "All checks complete"
            time.sleep(0.2)

        return [
            Step("config", "Loading configuration", 4, config),
            Step("database", "Checking database", 8, database, fatal=True),
            Step("storage", "Checking save location", 4, storage),
            Step("internet", "Checking internet connection", 6, internet),
            Step("sfa_server", "Contacting SFA server", 8, sfa_server),
            Step("sfa_login", "Signing in to SFA", 50, sfa_login, skippable=True),
            Step("whatsapp", "Checking WhatsApp link", 6, whatsapp),
            Step("schedule", "Loading schedule", 4, schedule),
            Step("data", "Checking this month's targets", 5, data_ready),
            Step("ready", "Ready", 5, ready),
        ]


def settings_ready() -> bool:
    """Daily mode once an admin exists and the setup wizard has been completed."""
    try:
        db.init()
        return auth.has_users() and bool(settings.get("setup.completed"))
    except Exception:
        return False
