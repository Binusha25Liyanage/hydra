"""Famulus import tests — need the Famulus database (company data, not in git):
    set HYDRA_SAMPLES=D:\\projects\\hydra-samples   (folder containing target_report.db)
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
from app.data import famulus  # noqa: E402

db.init()


@pytest.fixture(scope="module")
def fam_db():
    s = os.environ.get("HYDRA_SAMPLES")
    p = Path(s) / "target_report.db" if s else None
    if not p or not p.exists():
        pytest.skip("Famulus target_report.db not in HYDRA_SAMPLES")
    famulus.import_all(p, overwrite=True)
    return p


def test_october_targets(fam_db):
    tree = famulus.month_tree("2026-10")
    nat = tree["tree"][0]
    assert tree["month"]["nowd"] == 27
    assert nat["gt"] + nat["smmt"] == 140_600_000
    assert nat["smmt"] == 16_000_000


def test_october_history_matches_reports(fam_db):
    c = db.conn()
    total = c.execute("SELECT ROUND(SUM(sales_value),2) FROM sku_lines "
                      "WHERE date BETWEEN '2026-10-01' AND '2026-10-03'").fetchone()[0]
    smmt = c.execute("SELECT ROUND(SUM(sales_value),2) FROM sku_lines WHERE date BETWEEN '2026-10-01' AND '2026-10-03' "
                     "AND LOWER(territory) LIKE '%smmt%'").fetchone()[0]
    assert total == 5_085_384.48            # Sales Comparison: cumulative 1-3 Oct
    assert round(total - smmt) == 4_527_764  # Day Report: Prev. Month GT 1-3 Oct


def test_reimport_skips_existing(fam_db):
    rep = famulus.import_all(fam_db)
    assert "skipped" in rep["sales"] and "skipped existing" in rep["targets"]
