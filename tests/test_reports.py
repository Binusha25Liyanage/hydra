"""Report engine tests: rebuild the 3 Nov 2026 situation and compare with the sample reports.

Needs HYDRA_SAMPLES with: target_report.db (Famulus), the SFA exports (OutletWiseSKU…, Callage…, Sales_Order…)
and the five sample outputs (Day_Report…, Target_vs_Achievement…, Sales_Comparison…, Daily_Winners…, Pending_Order_Value…).
"""
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("HYDRA_DATA_DIR", tempfile.mkdtemp(prefix="hydra_test_"))
sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402
from app.data import famulus, store, targets_import  # noqa: E402
from app.reports import engine  # noqa: E402

db.init()
SAMPLES = Path(os.environ["HYDRA_SAMPLES"]) if os.environ.get("HYDRA_SAMPLES") else None
D = date(2026, 11, 3)


def one(pattern):
    found = sorted(SAMPLES.glob(pattern)) if SAMPLES else []
    if not found:
        pytest.skip(f"sample {pattern} not available")
    return found[0]


@pytest.fixture(scope="module")
def nov3():
    import openpyxl
    famulus.import_all(one("target_report.db"), overwrite=True)
    tva_file = one("*Target_vs_Achievement*.xlsx")
    targets_import.save(targets_import.parse(tva_file), "2026-11", overwrite=True)
    targets_import.set_nowd("2026-11", 24)
    for pat in ("*OutletWiseSKU*.xlsx", "*Callage*.xlsx", "*Sales_Order*.xlsx"):
        f = one(pat)
        if not store.inspect(f).get("duplicate"):
            store.import_file(f, replace=True)
    # 2 Nov is not in the samples: rebuild it from the sample reports (cumulative − today)
    day = {r[0]: r for r in openpyxl.load_workbook(one("*Day_Report*.xlsx")).active.iter_rows(min_row=5, values_only=True) if r[0]}
    tva = {r[0]: r for r in openpyxl.load_workbook(tva_file).active.iter_rows(min_row=5, values_only=True) if r[0]}
    modes = {r["name"].lower(): r["selling_mode"] for r in db.conn().execute("SELECT name, selling_mode FROM territories")}
    with db.tx() as c:
        c.execute("DELETE FROM imports WHERE sha256 IN ('fx2','fx2c')")
        a = c.execute("INSERT INTO imports(kind,file_name,sha256,rows,imported_at) VALUES ('sku','fixture','fx2',0,'x')").lastrowid
        b = c.execute("INSERT INTO imports(kind,file_name,sha256,rows,imported_at) VALUES ('callage','fixture','fx2c',0,'x')").lastrowid
        for name, r in day.items():
            if "Total" in name or name == "NATIONAL TOTAL":
                continue
            v = round((tva[name][2] or 0) - (r[3] or 0), 2)
            if v:
                c.execute("INSERT INTO sku_lines(import_id,date,territory,outlet_classification,sales_value) VALUES (?,?,?,?,?)",
                          (a, "2026-11-02", name, "Groceries - Large(GR - L)", v))
            calls, pc = (r[8] or 0, r[9] or 0) if modes.get(name.lower()) == "pre" else (0, (r[20] or 0) - (r[9] or 0))
            if calls or pc:
                c.execute("INSERT INTO callage_lines(import_id,date,territory,calls_made,productive_calls,unplanned_visits) "
                          "VALUES (?,?,?,?,?,0)", (b, "2026-11-02", name, calls, pc))
    c = db.conn()
    c.execute("DELETE FROM callage_prepared WHERE source='hydra' AND date BETWEEN '2026-11-01' AND '2026-11-30'")
    return day


def _sample_rows(pattern, key_col=0):
    import openpyxl
    ws = openpyxl.load_workbook(one(pattern)).active
    return {ws.cell(r, key_col + 1).value: [ws.cell(r, c).value for c in range(1, ws.max_column + 1)]
            for r in range(5, ws.max_row + 1)}


def _compare(table, pattern, key_col=0, skip_labels=()):
    sample = _sample_rows(pattern, key_col)
    bad = []
    for row in table.rows:
        vals = [row.label if i == 0 and key_col == 0 else row.values.get(c.key) for i, c in enumerate(table.columns)]
        s = sample.get(vals[key_col])
        assert s is not None, f"row {vals[key_col]} missing from sample"
        if vals[key_col] in skip_labels:
            continue
        for h, a, b in zip(table.columns, vals, s):
            if isinstance(b, (int, float)) and abs((a or 0) - b) > 0.011:
                bad.append((vals[key_col], h.header, a, b))
            elif not isinstance(b, (int, float)) and (a or None) != (b or None):
                bad.append((vals[key_col], h.header, a, b))
    assert len(table.rows) == len(sample)
    assert not bad, bad[:5]


def test_day_report_matches_sample(nov3):
    t = engine.build(D, "day_report")
    _compare(t, "*Day_Report*.xlsx")
    assert t.subtitle.startswith("Working Days (NOWD): 24   |   Day 3 of the month   |   GT Day Target: 5,303,872")
    kad = next(r for r in t.rows if r.label == "Kaduwela").values
    assert round(kad["day_target"], 2) == 85110.30 and round(kad["cum_target"], 2) == 168443.64


def test_target_vs_achievement_matches_sample(nov3):
    _compare(engine.build(D, "target_vs_achievement"), "*Target_vs_Achievement*.xlsx")


def test_sales_comparison_matches_sample(nov3):
    _compare(engine.build(D, "sales_comparison"), "*Sales_Comparison*.xlsx")


def test_daily_winners_matches_sample(nov3):
    t = engine.build(D, "daily_winners")
    _compare(t, "*Daily_Winners*.xlsx", key_col=5)
    assert t.summary["Winners"] == 8


def test_pending_orders(nov3):
    # the SFA snapshot in the samples was taken later in the day, so only check territories not invoiced in between
    t = engine.build(D, "pending_orders")
    v = {r.label: r.values for r in t.rows}
    assert round(v["Puttlam"]["value"], 2) == 194584.50 and v["Puttlam"]["count"] == 30
    assert round(v["Chilaw"]["value"], 2) == 175241.66 and v["Chilaw"]["count"] == 33


def test_generate_writes_excel_with_formulas(nov3, tmp_path):
    import openpyxl
    from app import settings
    settings.set("output.root", str(tmp_path))
    res = engine.generate(D, user="test")
    assert all(r["status"] == "generated" for r in res), res
    ws = openpyxl.load_workbook(next(r["path"] for r in res if r["type"] == "day_report")).active
    assert ws["E5"].value == "=IF(C5=0,0,D5/C5)" and ws["A100"].value == "NATIONAL TOTAL"
    assert ws["B100"].value.startswith("=SUM(")


def test_generate_renders_pdf_and_whatsapp_images(nov3, tmp_path):
    from app import settings
    from app.reports import render
    settings.set("output.root", str(tmp_path))
    res = engine.generate(D, ["day_report", "daily_winners"], user="test")
    for r in res:
        assert r["status"] == "generated", r
        if any("PDF/PNG not created" in w for w in r["warnings"]):
            pytest.skip("no browser in this environment")
        assert r["pdf"].endswith(".pdf") and Path(r["pdf"]).stat().st_size > 5000
        assert r["pngs"] and all(Path(p).exists() for p in r["pngs"])
    day = next(r for r in res if r["type"] == "day_report")
    assert len(day["pngs"]) >= 2                       # ~100 rows -> several WhatsApp images
    img = engine.image(day["id"], 1)
    assert img["src"].startswith("data:image/png;base64,") and img["pages"] == len(day["pngs"])
    assert engine.set_status([day["id"]], "approved", "test") == 1
    assert engine.get(day["id"])["status"] == "approved"
    # chunks never leave a tiny last image and cover every row once
    rows = engine.build(D, "day_report").rows
    parts = render.chunks(rows)
    assert sum(len(p) for p in parts) == len(rows) and min(len(p) for p in parts) > 6


def test_service_registry():
    from app import services
    svc = services.all_services()["sales_reports"]
    assert [r.id for r in svc.reports] == ["day_report", "target_vs_achievement", "sales_comparison",
                                          "daily_winners", "pending_orders"]
    assert services.report("day_report")[0].id == "sales_reports"
