"""Phase 9: WhatsApp link + sending, against tools/mock_whatsapp.py (no phone needed)."""
import json
import os
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

os.environ.setdefault("HYDRA_DATA_DIR", tempfile.mkdtemp(prefix="hydra_test_"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import pytest  # noqa: E402

from app import db, paths, settings  # noqa: E402
from app.whatsapp import service as W  # noqa: E402
from app.whatsapp import status as wa_status  # noqa: E402

PORT = 8791
BASE = f"http://127.0.0.1:{PORT}"


def _post(path):
    urllib.request.urlopen(urllib.request.Request(BASE + path, data=b"", method="POST"), timeout=5).read()


def _sent():
    return json.loads(urllib.request.urlopen(BASE + "/sent", timeout=5).read())


def _wait(cond, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.3)
    return False


@pytest.fixture(scope="module")
def mock():
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        pytest.skip("playwright not installed")
    import mock_whatsapp
    srv = mock_whatsapp.serve(PORT, background=True)
    db.init()
    settings.set("whatsapp.url", BASE)
    settings.set("whatsapp.headless", True)
    settings.set("whatsapp.gap_s", 0)
    yield srv
    W.WORKER.shutdown()
    srv.shutdown()


def test_recipients_and_routes(mock):
    with pytest.raises(W.WAServiceError):
        W.save_recipient({"name": ""})
    gid = W.save_recipient({"name": "Lakmee Management", "kind": "group"})
    cid = W.save_recipient({"name": "NSM", "kind": "contact", "phone": "077 123 4567"})
    with pytest.raises(W.WAServiceError):
        W.save_recipient({"name": "lakmee management"})
    assert db.conn().execute("SELECT phone FROM wa_recipients WHERE id=?", (cid,)).fetchone()[0] == "94771234567"
    W.save_routes({"day_report": [gid, cid], "daily_winners": [gid]})
    assert sorted(W.routes()["day_report"]) == sorted([gid, cid])
    assert sorted({r["name"]: r["reports"] for r in W.recipients()}["Lakmee Management"]) == ["daily_winners", "day_report"]


def test_link_by_qr(mock):
    _post("/reset")
    W.WORKER.link()
    assert _wait(lambda: W.WORKER.snapshot()["phase"] == "qr" and W.WORKER.snapshot()["qr"].startswith("data:image/png")), W.WORKER.snapshot()
    _post("/scan")
    assert _wait(lambda: W.WORKER.snapshot()["phase"] == "linked"), W.WORKER.snapshot()
    st = wa_status.status()
    assert st["linked"] and st["number"] == "+94771234567"


def _fake_report(tmp: Path, rtype="day_report"):
    Image = pytest.importorskip("PIL.Image")
    pngs = []
    for i in (1, 2):
        p = tmp / f"Day_Report_{i}.png"
        Image.new("RGB", (40, 20), "white").save(p)
        pngs.append(str(p))
    pdf = tmp / "Day_Report.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%fake\n")
    return db.conn().execute(
        "INSERT INTO reports(report_type, report_date, title, xlsx_path, pdf_path, png_paths, status, created_at) "
        "VALUES (?, '2026-11-03', 'Day Report — 2026-11-03', NULL, ?, ?, 'generated', 'x')",
        (rtype, str(pdf), json.dumps(pngs))).lastrowid


def test_send_reports_and_test_message(mock, tmp_path):
    assert W.WORKER.snapshot()["phase"] in ("linked", "idle")
    rid = _fake_report(tmp_path)
    q = W.queue_reports([rid], fmt="both", caption="{title} ({date})")
    assert q["queued"] == 2 and not q["skipped"]
    assert _wait(lambda: W.batch_status(q["batch"])["done"], 120), W.batch_status(q["batch"])
    st = W.batch_status(q["batch"])
    assert st["counts"]["sent"] == 2, st
    sent = _sent()
    group = [m for m in sent if m["chat"] == "Lakmee Management"]
    assert group[0]["files"] == ["Day_Report_1.png", "Day_Report_2.png"] and group[0]["text"] == "Day Report — 2026-11-03 (03 Nov 2026)"
    assert group[1]["files"] == ["Day_Report.pdf"]
    assert any(m["chat"] == "+94771234567" for m in sent)            # contact opened by phone number
    assert db.conn().execute("SELECT status FROM reports WHERE id=?", (rid,)).fetchone()[0] == "sent"
    # a report type with no recipients is skipped, not lost
    other = _fake_report(tmp_path, "pending_orders")
    assert W.queue_reports([other])["skipped"] == ["Pending Order Value"]
    t = W.queue_test(W.recipients()[0]["id"])
    assert _wait(lambda: W.batch_status(t["batch"])["done"], 60)
    assert W.batch_status(t["batch"])["counts"]["sent"] == 1
    assert "Hydra test message" in _sent()[-1]["text"]


def test_unknown_group_fails_cleanly(mock, tmp_path):
    bad = W.save_recipient({"name": "No Such Group"})
    rid = _fake_report(tmp_path, "sales_comparison")
    W.save_routes({"sales_comparison": [bad]})
    q = W.queue_reports([rid], fmt="png")
    assert _wait(lambda: W.batch_status(q["batch"])["done"], 90)
    item = W.batch_status(q["batch"])["items"][0]
    assert item["status"] == "failed" and "No chat called" in item["error"]
    assert db.conn().execute("SELECT status FROM reports WHERE id=?", (rid,)).fetchone()[0] == "approved"


def test_unlink(mock):
    W.WORKER.unlink()
    assert _wait(lambda: not wa_status.status()["linked"], 30)
    assert not (paths.whatsapp_profile_dir() / "browser").exists()
