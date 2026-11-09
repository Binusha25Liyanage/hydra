"""Phase 10: schedules, report dates, waiting for data, catch-up / missed, delivery — with a fake clock."""
import os
import tempfile
from datetime import date, datetime

os.environ.setdefault("HYDRA_DATA_DIR", tempfile.mkdtemp(prefix="hydra_test_"))

import pytest  # noqa: E402

from app import db, runner, settings  # noqa: E402
from app import scheduler as S  # noqa: E402

MON = date(2031, 6, 2)          # a Monday
CALLS = []


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    db.init()
    with db.tx() as c:
        c.execute("DELETE FROM runs")
        c.execute("DELETE FROM schedules")
        c.execute("DELETE FROM sku_lines WHERE date LIKE '2031-%'")
    settings.set("scheduler.enabled", True)
    CALLS.clear()

    def fake_generate(d, types, user, run_id, formats, stop, progress):
        CALLS.append((d, tuple(types), formats))
        rid = db.conn().execute("INSERT INTO reports(run_id, report_type, report_date, title, status, created_at) "
                                "VALUES (?, 'day_report', ?, 'Day Report', 'generated', 'x')", (run_id, d.isoformat())).lastrowid
        return [{"id": rid, "type": "day_report", "name": "Day Report", "title": "Day Report", "status": "generated",
                 "error": "", "warnings": []}]
    monkeypatch.setattr(runner, "_generate", fake_generate)
    yield


def _sched(**kw):
    d = {"name": "Morning", "time": "08:30", "days": "1111110", "date_mode": "yesterday", "delivery": "save",
         "formats": ["pdf", "png"], "report_types": ["day_report"]}
    d.update(kw)
    sid = S.save(d, "t")
    db.conn().execute("UPDATE schedules SET updated_at='2031-01-01T00:00:00' WHERE id=?", (sid,))   # existed long before
    return sid


def _data(d):
    imp = db.conn().execute("INSERT INTO imports(kind,file_name,sha256,rows,imported_at) VALUES ('sku','t',?,1,'x')",
                            (f"sch-{d}-{datetime.now().timestamp()}",)).lastrowid
    db.conn().execute("INSERT INTO sku_lines(import_id,date,territory,sales_value) VALUES (?,?,'Alpha',1)", (imp, d.isoformat()))


def _runs():
    return [dict(r) for r in db.conn().execute("SELECT * FROM runs ORDER BY id")]


def test_validation_and_report_dates():
    with pytest.raises(S.ScheduleError):
        S.save({"time": "8.30"})
    with pytest.raises(S.ScheduleError):
        S.save({"time": "08:30", "days": "0000000"})
    _sched()
    with pytest.raises(S.ScheduleError):
        S.save({"name": "Clash", "time": "08:30"})                 # two active schedules at the same minute
    assert S.report_date("today", MON) == MON
    assert S.report_date("yesterday", MON) == date(2031, 6, 1)                 # Sunday
    assert S.report_date("last_working", MON) == date(2031, 5, 31)             # skips Sunday -> Saturday


def test_runs_once_at_time_with_yesterdays_date():
    _sched()
    _data(date(2031, 6, 1))
    assert S.SCHEDULER.tick(datetime(2031, 6, 2, 8, 29)) == []
    S.SCHEDULER.tick(datetime(2031, 6, 2, 8, 30, 10))
    assert CALLS == [(date(2031, 6, 1), ("day_report",), ("pdf", "png"))]
    S.SCHEDULER.tick(datetime(2031, 6, 2, 8, 31))                 # same slot never runs twice
    assert len(CALLS) == 1
    r = _runs()[0]
    assert r["status"] == "done" and r["trigger"] == "schedule" and r["slot"] == "2031-06-02T08:30"
    assert db.conn().execute("SELECT status FROM reports WHERE run_id=?", (r["id"],)).fetchone()[0] == "saved"


def test_days_and_pause():
    _sched(days="1111100")                                        # Mon–Fri
    _data(date(2031, 6, 6))
    S.SCHEDULER.tick(datetime(2031, 6, 7, 9, 0))                  # Saturday: not a run day
    assert not CALLS
    settings.set("scheduler.enabled", False)
    S.SCHEDULER.tick(datetime(2031, 6, 9, 8, 31))                 # Monday but paused
    assert not CALLS and S.SCHEDULER.status()["state"] in ("paused", "stopped")


def test_waits_for_data_then_runs():
    _sched(retry_min=15, retry_max=3)
    S.SCHEDULER.tick(datetime(2031, 6, 2, 8, 30))
    r = _runs()[0]
    assert r["status"] == "waiting" and r["attempts"] == 1 and r["next_try_at"] == "2031-06-02T08:45:00"
    S.SCHEDULER.tick(datetime(2031, 6, 2, 8, 40))                 # too early to retry
    assert _runs()[0]["attempts"] == 1 and not CALLS
    _data(date(2031, 6, 1))
    S.SCHEDULER.tick(datetime(2031, 6, 2, 8, 45))
    assert _runs()[0]["status"] == "done" and len(CALLS) == 1


def test_gives_up_after_retries():
    _sched(retry_min=5, retry_max=2)
    for m in (30, 35, 40):
        S.SCHEDULER.tick(datetime(2031, 6, 2, 8, m))
    r = _runs()[0]
    assert r["status"] == "failed" and "Gave up after 3 tries" in r["message"] and not CALLS


def test_catch_up_and_missed():
    _sched(catch_up_min=60)
    _data(date(2031, 6, 1))
    S.SCHEDULER.tick(datetime(2031, 6, 2, 9, 15))                 # opened 45 min late -> still runs
    assert _runs()[0]["trigger"] == "catch_up" and _runs()[0]["status"] == "done"
    _data(date(2031, 6, 2))
    S.SCHEDULER.tick(datetime(2031, 6, 3, 11, 0))                 # 2.5 h late -> missed, nothing generated
    r = _runs()[-1]
    assert r["status"] == "missed" and len(CALLS) == 1


def test_new_schedule_starts_next_time():
    sid = S.save({"name": "Late add", "time": "07:00", "days": "1111111", "delivery": "save", "formats": ["png"]}, "t")
    db.conn().execute("UPDATE schedules SET updated_at='2031-06-02T10:00:00' WHERE id=?", (sid,))
    _data(date(2031, 6, 1))
    S.SCHEDULER.tick(datetime(2031, 6, 2, 10, 5))                 # 07:00 already passed when it was created
    assert not _runs()
    assert S.next_run(datetime(2031, 6, 2, 10, 5))["at"] == "2031-06-03T07:00"


def test_send_falls_back_to_preview_when_whatsapp_not_linked():
    _sched(delivery="send")
    _data(date(2031, 6, 1))
    S.SCHEDULER.tick(datetime(2031, 6, 2, 8, 30))
    r = _runs()[0]
    assert r["status"] == "done" and "WhatsApp not linked" in r["message"]


def test_busy_runner_is_not_lost():
    _sched()
    _data(date(2031, 6, 1))
    runner.STATE["running"] = True
    try:
        S.SCHEDULER.tick(datetime(2031, 6, 2, 8, 30))
        assert not _runs() and not CALLS                          # nothing recorded while busy...
    finally:
        runner.STATE["running"] = False
    S.SCHEDULER.tick(datetime(2031, 6, 2, 8, 31))                 # ...and it runs on the next tick
    assert len(CALLS) == 1


def test_listing_shows_next_and_last():
    _sched()
    _data(date(2031, 6, 1))
    S.SCHEDULER.tick(datetime(2031, 6, 2, 8, 30))
    x = S.listing()[0]
    assert x["last_run"]["status"] == "done" and x["next_run"]
