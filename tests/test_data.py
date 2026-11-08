"""Data-layer tests. Unit tests always run; the real-file tests run when HYDRA_SAMPLES
points to a folder with the SFA sample exports (they hold company data, so they are not in git):
    set HYDRA_SAMPLES=D:\\projects\\hydra-samples && python -m pytest -q tests
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("HYDRA_DATA_DIR", tempfile.mkdtemp(prefix="hydra_test_"))
sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402
from app.data import store  # noqa: E402
from app.data.sfa_excel import ExportError, read_export, to_iso_date, to_number  # noqa: E402

SAMPLES = Path(os.environ.get("HYDRA_SAMPLES", "")) if os.environ.get("HYDRA_SAMPLES") else None
db.init()


def sample(pattern):
    if not SAMPLES or not SAMPLES.exists():
        pytest.skip("HYDRA_SAMPLES not set")
    found = sorted(SAMPLES.glob(pattern))
    if not found:
        pytest.skip(f"no sample matching {pattern}")
    return found[0]


@pytest.mark.parametrize("raw,expected", [
    ("2,325.00", 2325.0), ("1,560", 1560), ("(150.00)", -150.0), ("38.5%", 38.5), (" 12 ", 12),
    (648.0, 648.0), (18, 18), ("", None), ("-", None), (None, None),
])
def test_to_number(raw, expected):
    assert to_number(raw) == expected


def test_to_number_rejects_text():
    with pytest.raises(ValueError):
        to_number("0.0.30")


def test_dates():
    assert to_iso_date("November 3, 2026") == "2026-11-03"
    assert to_iso_date("2026-11-03") == "2026-11-03"


def test_sku_export_matches_sfa_total():
    p = read_export(sample("*OutletWiseSKU*.xlsx"))
    assert p.kind == "sku" and p.period_from == "2026-11-03"
    assert p.verification()["ok"] is True
    assert round(p.total("sales_value"), 2) == 2318859.42          # Day Report GT achievement
    kad = [r for r in p.rows if r["territory"] == "Kaduwela"]
    assert round(sum(r["sales_value"] for r in kad), 2) == 100214.08


def test_callage_and_sales_order():
    c = read_export(sample("*Callage*.xlsx"))
    assert c.kind == "callage" and c.verification()["ok"] is True
    kad = next(r for r in c.rows if r["territory"] == "Kaduwela")
    assert (kad["calls_made"], kad["productive_calls"]) == (67, 31)
    so = read_export(sample("*Sales_Order*.xlsx"))
    put = [r for r in so.rows if r["territory"] == "Puttlam"]
    assert round(sum(r["net_amount"] for r in put), 2) == 194584.50
    assert len({r["customer"] for r in put}) == 30


def test_finished_reports_are_rejected():
    with pytest.raises(ExportError):
        read_export(sample("*Day_Report*.xlsx"))


def test_import_duplicate_and_replace():
    f = sample("*OutletWiseSKU*.xlsx")
    for imp in store.list_imports("sku"):
        store.delete_import(imp["id"])
    r = store.import_file(f)
    assert r["rows"] == 1520
    with pytest.raises(ExportError, match="already imported"):
        store.import_file(f)
    assert store.inspect(f)["conflicts"][0]["dates"] == ["2026-11-03"]
    modes = {t["name"]: t["selling_mode"] for t in store.territories()}
    assert modes["Puttlam"] == "pre" and modes["Kaduwela"] == "van"
