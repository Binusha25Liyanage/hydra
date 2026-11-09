"""One report run at a time — shared by the Generate button, the top-bar button and the scheduler.

A run = generate the chosen reports for a date, then deliver them:
  preview  -> leave them for Preview & Send (a notification says they're ready)
  send     -> queue them on WhatsApp to each report's recipients
  save     -> mark them saved (files stay in the output folder)
Every run is recorded in the `runs` table (Activity Monitor reads it in Phase 11).
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import date

from . import db, notify, settings

log = logging.getLogger("hydra.runner")

LOCK = threading.Lock()
STATE: dict = {"running": False, "text": "", "stop": threading.Event(), "day": None, "run_id": None, "source": None}


class Busy(Exception):
    pass


def _generate(d, types, user, run_id, formats, stop, progress):      # replaced in tests
    from .reports import engine
    return engine.generate(d, types, user, run_id=run_id, formats=formats, stop=stop, progress=progress)


def snapshot() -> dict:
    return {k: STATE[k] for k in ("running", "text", "day", "run_id", "source")}


def stop() -> bool:
    if STATE["running"]:
        STATE["stop"].set()
        return True
    return False


def start_run_row(trigger: str, d: date | None, delivery: str, user: str | None, schedule_id=None, slot=None,
                  status="running", message=None) -> int:
    return db.conn().execute(
        "INSERT INTO runs(schedule_id, slot, trigger, report_date, delivery, status, started_at, user, message) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (schedule_id, slot, trigger, d.isoformat() if d else None, delivery, status, db.now_iso(), user, message)).lastrowid


def run(d: date, types: list[str] | None = None, formats: tuple[str, ...] | None = None, user: str | None = None,
        trigger: str = "manual", delivery: str = "preview", schedule_id: int | None = None,
        run_id: int | None = None, label: str = "") -> dict:
    """Generate + deliver. Raises Busy if another run is in progress."""
    from .reports import engine
    with LOCK:
        if STATE["running"]:
            raise Busy(f"A run is already in progress ({STATE['text'] or 'working'})")
        STATE.update(running=True, text="Starting…", stop=threading.Event(), day=d.isoformat(), source=trigger)
    try:
        if run_id is None:
            run_id = start_run_row(trigger, d, delivery, user, schedule_id)
        else:
            db.conn().execute("UPDATE runs SET status='running', attempts=attempts+1, next_try_at=NULL WHERE id=?", (run_id,))
        STATE["run_id"] = run_id
        fm = tuple(formats) if formats is not None else tuple(settings.get("reports.formats") or ("pdf", "png"))
        try:
            res = _generate(d, list(types or []), user, run_id, fm, STATE["stop"].is_set, lambda t: STATE.update(text=t))
        except Exception as e:                       # should not happen (generate catches per report), but never hang a run
            log.exception("Run %s crashed", run_id)
            _finish(run_id, "failed", 0, 0, None, f"{type(e).__name__}: {e}")
            notify.add("reports", "error", f"Run failed for {d}", str(e)[:300], "run")
            raise
        stopped = STATE["stop"].is_set()
    finally:
        STATE.update(running=False, text="", run_id=None, source=None)

    ok = [r for r in res if r["status"] == "generated"]
    bad = [r for r in res if r["status"] == "failed"]
    batch, msg = None, ""
    if ok and not stopped:
        if delivery == "send":
            from .whatsapp import service as W, status as wa_status
            if wa_status.status().get("linked"):
                q = W.queue_reports([r["id"] for r in ok], settings.get("reports.send_format") or "png",
                                    settings.get("reports.caption") or "{title}", user=user or "scheduler")
                batch = q["batch"]
                msg = f"{q['queued']} WhatsApp message(s) queued" + (f"; no recipients for {', '.join(q['skipped'])}" if q["skipped"] else "")
            else:
                msg = "WhatsApp not linked — reports left in Preview & Send"
                delivery = "preview"
        elif delivery == "save":
            engine.set_status([r["id"] for r in ok], "saved", user or "scheduler")
            msg = "Saved to the output folder"
    status = "stopped" if stopped else ("failed" if not ok and bad else ("partial" if bad else ("done" if ok else "failed")))
    if not ok and not bad and not stopped:
        msg = msg or "Nothing was generated (" + "; ".join(r["error"] for r in res if r["error"])[:200] + ")"
    _finish(run_id, status, len(ok), len(bad), batch, msg)

    who = label or ("Scheduled run" if trigger != "manual" else "")
    title = (f"{who}: " if who else "") + f"{len(ok)} report(s) for {d}" + (f", {len(bad)} failed" if bad else "") + (" — stopped" if stopped else "")
    detail = msg or ("Open Preview & Send to check and send them" if delivery == "preview" and ok else "")
    errs = "; ".join(f"{r['name']}: {r['error']}" for r in res if r["error"])
    notify.add("reports", "error" if bad or not ok else ("warning" if stopped else "success"), title,
               (detail + (" | " if detail and errs else "") + errs)[:400], "reports")
    return {"run_id": run_id, "results": res, "folder": str(engine.output_dir(d)), "stopped": stopped,
            "batch": batch, "status": status, "message": msg, "delivery": delivery}


def _finish(run_id, status, gen, failed, batch, msg):
    db.conn().execute("UPDATE runs SET status=?, finished_at=?, generated=?, failed=?, wa_batch=?, message=? WHERE id=?",
                      (status, db.now_iso(), gen, failed, batch, msg or None, run_id))


def history(limit: int = 100) -> list[dict]:
    rows = db.conn().execute(
        "SELECT r.*, s.name schedule_name FROM runs r LEFT JOIN schedules s ON s.id=r.schedule_id "
        "ORDER BY r.id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        x = dict(r)
        if x.get("wa_batch"):
            c = db.conn().execute("SELECT status, COUNT(*) FROM wa_sends WHERE batch=? GROUP BY status", (x["wa_batch"],)).fetchall()
            x["wa"] = {k: v for k, v in c}
        out.append(x)
    return out


def report_ids(run_id: int) -> list[int]:
    return [r[0] for r in db.conn().execute("SELECT id FROM reports WHERE run_id=? AND status NOT IN ('failed','skipped')", (run_id,))]


def recover():
    """At start-up: a run left 'running' was cut off by Hydra closing."""
    db.conn().execute("UPDATE runs SET status='failed', finished_at=?, message='Hydra closed during the run' WHERE status='running'",
                      (db.now_iso(),))


def to_json(x) -> str:
    return json.dumps(x)
