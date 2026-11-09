"""Schedule: runs reports at set times while Hydra is open (or in the tray).

Each schedule has a time, the days it runs, which report date to use (today / yesterday /
last working day), which reports, and what to do with them (preview / send / save).

* One run per schedule per day ("slot"). Two Hydra starts never run the same slot twice.
* Data not in yet  -> the run waits and tries again every `retry_min` minutes, `retry_max` times.
* Hydra was closed at the time -> it still runs if Hydra opens within `catch_up_min` minutes,
  otherwise the slot is recorded as missed (so nobody wonders why reports didn't come).
"""
from __future__ import annotations

import json
import logging
import re
import threading
from datetime import date, datetime, timedelta

from . import db, notify, runner, settings

log = logging.getLogger("hydra.scheduler")
TICK_S = 20
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ScheduleError(Exception):
    pass


# =============================================================================== schedules
def _row(r) -> dict:
    x = dict(r)
    x["report_types"] = json.loads(x["report_types"] or "[]")
    x["formats"] = json.loads(x["formats"] or "[]")
    return x


def listing() -> list[dict]:
    out = []
    now = datetime.now()
    for r in db.conn().execute("SELECT * FROM schedules ORDER BY time, id"):
        x = _row(r)
        nxt = next_slot(x, now)
        x["next_run"] = nxt.isoformat(timespec="minutes") if nxt else None
        x["next_report_date"] = report_date(x["date_mode"], nxt.date()).isoformat() if nxt else None
        last = db.conn().execute("SELECT status, started_at, report_date, message, generated, failed FROM runs WHERE schedule_id=? "
                                 "ORDER BY id DESC LIMIT 1", (x["id"],)).fetchone()
        x["last_run"] = dict(last) if last else None
        out.append(x)
    return out


def save(data: dict, user=None) -> int:
    name = (data.get("name") or "").strip() or f"Reports at {data.get('time')}"
    t = (data.get("time") or "").strip()
    if not _TIME.match(t):
        raise ScheduleError("Enter the time as HH:MM (24-hour), e.g. 08:30")
    days = "".join("1" if c in ("1", 1, True) else "0" for c in (data.get("days") or "1111110"))
    if len(days) != 7 or "1" not in days:
        raise ScheduleError("Choose at least one day")
    mode = data.get("date_mode") or "yesterday"
    if mode not in ("today", "yesterday", "last_working"):
        raise ScheduleError("Choose which report date to use")
    delivery = data.get("delivery") or "preview"
    if delivery not in ("preview", "send", "save"):
        raise ScheduleError("Choose what happens to the reports")
    from . import services
    known = {r for r in services.all_reports()}
    types = [t2 for t2 in data.get("report_types") or [] if t2 in known]
    formats = [f for f in data.get("formats") or [] if f in ("pdf", "png")]
    if delivery == "send" and "png" not in formats and "pdf" not in formats:
        raise ScheduleError("Sending on WhatsApp needs images or PDF — tick at least one")
    nums = {}
    for k, lo, hi, dflt in (("retry_min", 5, 240, 15), ("retry_max", 0, 24, 4), ("catch_up_min", 0, 720, 120)):
        try:
            nums[k] = max(lo, min(hi, int(data.get(k, dflt))))
        except (TypeError, ValueError):
            raise ScheduleError(f"{k.replace('_', ' ')} must be a whole number")
    now = db.now_iso()
    with db.tx() as c:
        dup = c.execute("SELECT name FROM schedules WHERE time=? AND id!=? AND active=1", (t, int(data.get("id") or 0))).fetchone()
        if dup and data.get("active", True):
            raise ScheduleError(f"“{dup['name']}” already runs at {t} — pick another time")
        vals = (name, t, days, mode, json.dumps(types), json.dumps(formats), delivery, nums["retry_min"], nums["retry_max"],
                nums["catch_up_min"], 1 if data.get("active", True) else 0)
        if data.get("id"):
            c.execute("UPDATE schedules SET name=?, time=?, days=?, date_mode=?, report_types=?, formats=?, delivery=?, retry_min=?, "
                      "retry_max=?, catch_up_min=?, active=?, updated_at=? WHERE id=?", (*vals, now, int(data["id"])))
            sid = int(data["id"])
        else:
            sid = c.execute("INSERT INTO schedules(name, time, days, date_mode, report_types, formats, delivery, retry_min, retry_max, "
                            "catch_up_min, active, created_at, updated_at, created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (*vals, now, now, user)).lastrowid
    db.audit(user, "schedule.save", f"{name} {t} {days} {mode} {delivery}")
    SCHEDULER.wake()
    return sid


def set_active(sid: int, active: bool, user=None):
    db.conn().execute("UPDATE schedules SET active=?, updated_at=? WHERE id=?", (1 if active else 0, db.now_iso(), int(sid)))
    db.audit(user, "schedule.active" if active else "schedule.pause", str(sid))
    SCHEDULER.wake()


def delete(sid: int, user=None):
    with db.tx() as c:
        r = c.execute("SELECT name FROM schedules WHERE id=?", (int(sid),)).fetchone()
        c.execute("DELETE FROM schedules WHERE id=?", (int(sid),))
    db.audit(user, "schedule.delete", r["name"] if r else str(sid))


# =============================================================================== dates
def report_date(mode: str, run_day: date) -> date:
    if mode == "today":
        return run_day
    d = run_day - timedelta(days=1)
    if mode == "last_working":
        while d.weekday() == 6:            # skip Sundays
            d -= timedelta(days=1)
    return d


def _slot_dt(s: dict, day: date) -> datetime:
    h, m = map(int, s["time"].split(":"))
    return datetime(day.year, day.month, day.day, h, m)


def next_slot(s: dict, now: datetime) -> datetime | None:
    if not s["active"]:
        return None
    for i in range(0, 8):
        day = (now + timedelta(days=i)).date()
        if s["days"][day.weekday()] != "1":
            continue
        dt = _slot_dt(s, day)
        if dt > now:
            return dt
    return None


def next_run(now: datetime | None = None) -> dict | None:
    if not settings.get("scheduler.enabled", True):
        return None
    now = now or datetime.now()
    best = None
    for r in db.conn().execute("SELECT * FROM schedules WHERE active=1"):
        s = _row(r)
        n = next_slot(s, now)
        if n and (best is None or n < best[0]):
            best = (n, s)
    return {"at": best[0].isoformat(timespec="minutes"), "name": best[1]["name"]} if best else None


# =============================================================================== the loop
class Scheduler:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._wake = threading.Event()
        self._quit = threading.Event()
        self.started_at: datetime | None = None
        self.last_tick: datetime | None = None
        self.note = ""

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._quit.clear()
        self.started_at = datetime.now()
        self._thread = threading.Thread(target=self._loop, name="hydra-scheduler", daemon=True)
        self._thread.start()
        log.info("Scheduler started")

    def stop(self):
        self._quit.set()
        self._wake.set()

    def wake(self):
        self._wake.set()

    @property
    def alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _loop(self):
        while not self._quit.is_set():
            try:
                self.tick(datetime.now())
            except Exception:
                log.exception("Scheduler tick failed")
            self._wake.wait(TICK_S)
            self._wake.clear()

    # ---------------------------------------------------------------- one pass (tests call this directly)
    def tick(self, now: datetime) -> list[int]:
        """Start whatever is due at `now`. Returns run ids it acted on."""
        self.last_tick = now
        if not settings.get("scheduler.enabled", True):
            self.note = "Paused"
            return []
        acted = []
        c = db.conn()
        # 1) waiting runs whose retry time has come
        for r in c.execute("SELECT r.*, s.name sname FROM runs r JOIN schedules s ON s.id=r.schedule_id "
                           "WHERE r.status='waiting' AND r.next_try_at<=? ORDER BY r.id", (now.isoformat(timespec="seconds"),)).fetchall():
            s = _row(c.execute("SELECT * FROM schedules WHERE id=?", (r["schedule_id"],)).fetchone())
            if self._attempt(s, r["id"], date.fromisoformat(r["report_date"]), now):
                acted.append(r["id"])
        # 2) new slots
        for row in c.execute("SELECT * FROM schedules WHERE active=1 ORDER BY time, id").fetchall():
            s = _row(row)
            for day in (now.date() - timedelta(days=1), now.date()):      # yesterday covers late-night slots after midnight
                if s["days"][day.weekday()] != "1":
                    continue
                slot = _slot_dt(s, day)
                if slot > now:
                    continue
                key = slot.isoformat(timespec="minutes")
                if c.execute("SELECT 1 FROM runs WHERE schedule_id=? AND slot=?", (s["id"], key)).fetchone():
                    continue
                if key < s["updated_at"][:16]:          # db.now_iso() is local time, like slots
                    continue                                   # created or edited after this slot's time: starts next time
                late = (now - slot).total_seconds() / 60
                rd = report_date(s["date_mode"], day)
                if late > max(s["catch_up_min"], 2):
                    rid = runner.start_run_row("schedule", rd, s["delivery"], "scheduler", s["id"], key, status="missed",
                                               message=f"Hydra was not running at {s['time']} (opened {int(late)} min late)")
                    c.execute("UPDATE runs SET finished_at=? WHERE id=?", (db.now_iso(), rid))
                    notify.add("schedule", "warning", f"Missed: {s['name']} ({s['time']})",
                               f"Hydra was not running. Generate the reports for {rd} from the Run Center.", "schedule")
                    acted.append(rid)
                    continue
                if runner.STATE["running"]:
                    self.note = "Waiting for the current run to finish"
                    continue                                   # next tick
                trigger = "schedule" if late <= 2 else "catch_up"
                rid = runner.start_run_row(trigger, rd, s["delivery"], "scheduler", s["id"], key, status="waiting")
                self._attempt(s, rid, rd, now)
                acted.append(rid)
        self.note = ""
        return acted

    def _attempt(self, s: dict, run_id: int, rd: date, now: datetime) -> bool:
        c = db.conn()
        ready, why = self._data_ready(s, rd)
        if not ready:
            att = c.execute("SELECT attempts FROM runs WHERE id=?", (run_id,)).fetchone()[0] + 1
            if att > s["retry_max"]:
                c.execute("UPDATE runs SET status='failed', attempts=?, finished_at=?, message=? WHERE id=?",
                          (att, db.now_iso(), f"Gave up after {att} tries: {why}", run_id))
                notify.add("schedule", "error", f"{s['name']}: no reports for {rd}", why + " — import the data and use the Run Center.", "schedule")
            else:
                nxt = now + timedelta(minutes=s["retry_min"])
                c.execute("UPDATE runs SET status='waiting', attempts=?, next_try_at=?, message=? WHERE id=?",
                          (att, nxt.isoformat(timespec="seconds"), f"{why} — trying again at {nxt:%H:%M}", run_id))
                if att == 1:
                    notify.add("schedule", "warning", f"{s['name']}: waiting for data", f"{why}. Hydra tries again every {s['retry_min']} min.", "schedule")
            return True
        if runner.STATE["running"]:
            c.execute("UPDATE runs SET next_try_at=? WHERE id=?", ((now + timedelta(minutes=1)).isoformat(timespec="seconds"), run_id))
            return False
        try:
            runner.run(rd, s["report_types"] or None, tuple(s["formats"]), "scheduler", trigger="schedule",
                       delivery=s["delivery"], schedule_id=s["id"], run_id=run_id, label=s["name"])
        except runner.Busy:
            c.execute("UPDATE runs SET status='waiting', next_try_at=? WHERE id=?",
                      ((now + timedelta(minutes=1)).isoformat(timespec="seconds"), run_id))
            return False
        except Exception:
            log.exception("Scheduled run %s failed", run_id)
        return True

    @staticmethod
    def _data_ready(s: dict, rd: date) -> tuple[bool, str]:
        from . import services
        wanted = set(s["report_types"] or services.all_reports().keys())
        for svc in services.all_services().values():
            if svc.data_ready and any(r.id in wanted for r in svc.reports):
                ok, why = svc.data_ready(rd)
                if not ok:
                    return False, why
        return True, ""

    def status(self) -> dict:
        enabled = bool(settings.get("scheduler.enabled", True))
        n = db.conn().execute("SELECT COUNT(*) FROM schedules WHERE active=1").fetchone()[0]
        waiting = db.conn().execute("SELECT COUNT(*) FROM runs WHERE status='waiting'").fetchone()[0]
        if not self.alive:
            label, state = "Stopped", "stopped"
        elif not enabled:
            label, state = "Paused", "paused"
        elif runner.STATE["running"]:
            label, state = "Running — " + (runner.STATE["text"] or ""), "running"
        elif waiting:
            label, state = f"Waiting for data ({waiting})", "waiting"
        elif n:
            label, state = f"On · {n} schedule{'s' if n > 1 else ''}", "on"
        else:
            label, state = "No schedules", "idle"
        return {"state": state, "label": label, "enabled": enabled, "active": n, "waiting": waiting,
                "next": next_run(), "note": self.note}


SCHEDULER = Scheduler()
