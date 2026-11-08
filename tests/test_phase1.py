"""Phase 1 tests — run with:  python -m pytest -q tests"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("HYDRA_DATA_DIR", tempfile.mkdtemp(prefix="hydra_test_"))
sys.path.insert(0, str(ROOT))

from app import auth, db, settings  # noqa: E402
from app.api import Api  # noqa: E402

db.init()


@pytest.fixture(scope="module")
def mock_sfa():
    proc = subprocess.Popen([sys.executable, str(ROOT / "tools" / "mock_sfa_server.py")],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    yield "http://127.0.0.1:8765"
    proc.terminate()


def test_migrations_and_health():
    assert db.schema_version() >= 1
    assert db.quick_check() == "ok"


def test_first_admin_and_login():
    api = Api()
    assert api.auth_create_first_admin("tester", "Tester", "short", "short")["ok"] is False
    assert api.auth_create_first_admin("tester", "Tester", "Hydra2026!", "Hydra2026!")["ok"]
    assert api.auth_create_first_admin("other", "Other", "Hydra2026!", "Hydra2026!")["ok"] is False
    assert api.auth_login("tester", "wrong")["ok"] is False
    r = api.auth_login("tester", "Hydra2026!", True)
    assert r["ok"] and r["next"] == "wizard"
    auth._current = None
    assert auth.auto_login()["username"] == "tester"


def test_lockout_after_failed_attempts():
    auth.create_user("locky", "Locky2026x", "user", by="tester")
    for _ in range(auth.MAX_FAILED):
        with pytest.raises(auth.AuthError):
            auth.verify("locky", "nope")
    with pytest.raises(auth.AuthError, match="Too many"):
        auth.verify("locky", "Locky2026x")


def test_settings_roundtrip_and_secret():
    settings.set("reports.title_prefix", "Hydra")
    assert settings.get("reports.title_prefix") == "Hydra"
    settings.set_secret("sfa.password", "Secret123")
    assert settings.get_secret("sfa.password") == "Secret123"


def test_sfa_login_and_pages(mock_sfa):
    api = Api()
    api.auth_login("tester", "Hydra2026!")
    assert api.sfa_save({"base_url": mock_sfa, "username": "binusha", "password": "Secret123",
                         "browser": "chromium", "headless": True, "timeout_s": 20})["ok"]
    ok = api.sfa_test_login({})["result"]
    assert ok["ok"] and ok["display_name"] == "Binusha Liyanage"
    bad = api.sfa_test_login({"password": "wrong"})["result"]
    assert not bad["ok"] and bad["kind"] == "credentials"
    api.sfa_test_login({})
    res = {r["key"]: r for r in api.pages_test()["results"]}
    assert res["sku"]["ok"] and "OUTLET WISE SKU" in res["sku"]["heading"]
    assert not res["rep_performance"]["ok"]


def test_daily_startup_sequence(mock_sfa, tmp_path):
    from app.startup import StartupSequence
    api = Api()
    api.auth_login("tester", "Hydra2026!")
    api.output_save(str(tmp_path / "out"))
    api.pages_save([{"key": "sku", "url": "/it/reports/outlet_wise_sku_sales"}])
    assert api.wizard_complete()["ok"]
    s = StartupSequence()
    assert s.mode == "daily"
    s.start()
    while not s.snapshot()["finished"]:
        time.sleep(0.1)
    snap = s.snapshot()
    steps = {x["id"]: x for x in snap["steps"]}
    assert not snap["fatal"] and snap["progress"] == 100
    assert steps["database"]["state"] == "ok"
    assert steps["sfa_login"]["state"] == "ok"
    assert steps["whatsapp"]["state"] == "warning"     # not linked yet
