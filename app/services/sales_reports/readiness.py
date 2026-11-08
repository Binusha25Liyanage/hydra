"""Data check for the sales reports (shown in the Run Center before generating)."""
from __future__ import annotations

from datetime import date

from ... import db
from .context import _prev_working


def readiness(d: date) -> list[dict]:
    """What data exists for a report date — shown in the Run Center before generating."""
    c = db.conn()
    ds = d.isoformat()
    prev = _prev_working(d).isoformat()
    month = d.strftime("%Y-%m")
    tm = c.execute("SELECT nowd FROM target_months WHERE month=?", (month,)).fetchone()
    has_h = c.execute("SELECT 1 FROM hierarchy_nodes WHERE month=? LIMIT 1", (month,)).fetchone() is not None
    sku = c.execute("SELECT COUNT(*), ROUND(SUM(sales_value),2) FROM sku_lines WHERE date=?", (ds,)).fetchone()
    cal = c.execute("SELECT COUNT(*) FROM callage_lines WHERE date=?", (ds,)).fetchone()[0] or \
        c.execute("SELECT COUNT(*) FROM callage_prepared WHERE date=?", (ds,)).fetchone()[0]
    calp = c.execute("SELECT COUNT(*) FROM callage_lines WHERE date=?", (prev,)).fetchone()[0] or \
        c.execute("SELECT COUNT(*) FROM callage_prepared WHERE date=? AND source='famulus'", (ds,)).fetchone()[0]
    so = c.execute("SELECT COUNT(DISTINCT import_id), COUNT(*) FROM sales_orders WHERE date=?", (ds,)).fetchone()
    unset = c.execute("SELECT COUNT(*) FROM territories WHERE selling_mode IS NULL AND is_smmt=0").fetchone()[0]
    return [
        {"item": f"Targets for {d:%B %Y}", "ok": has_h, "detail": "Set" if has_h else "Import on Hierarchy & Targets",
         "needed_by": "All except Sales Comparison"},
        {"item": "Working days (NOWD)", "ok": bool(tm and tm["nowd"]), "detail": str(tm["nowd"]) if tm and tm["nowd"] else "Not set",
         "needed_by": "Day Report"},
        {"item": f"SKU sales {ds}", "ok": sku[0] > 0, "detail": f"{sku[0]:,} rows · {sku[1] or 0:,.2f}" if sku[0] else "Not imported",
         "needed_by": "All"},
        {"item": f"Callage {ds} (Van)", "ok": cal > 0, "detail": f"{cal} rows" if cal else "Not imported",
         "needed_by": "Day Report, Daily Winners"},
        {"item": f"Callage {prev} (Pre)", "ok": calp > 0, "detail": f"{calp} rows" if calp else "Not imported",
         "needed_by": "Day Report, Daily Winners"},
        {"item": f"Pre-Selling orders {ds}", "ok": so[0] > 0, "detail": f"{so[0]} snapshot(s)" if so[0] else "Not imported",
         "needed_by": "Pending Order Value"},
        {"item": "Van / Pre for every territory", "ok": unset == 0, "detail": "All set" if not unset else f"{unset} not set",
         "needed_by": "Callage, Pending Orders"},
    ]
