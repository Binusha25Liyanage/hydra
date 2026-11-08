"""Generate reports for a date: build → write Excel → record in the reports table."""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from .. import db, paths, settings
from . import excel
from .builders import BUILDERS, REPORT_TYPES
from .context import Context, ReportError

log = logging.getLogger("hydra.reports")


def output_dir(d: date) -> Path:
    root = Path(settings.get("output.root") or (paths.data_root() / "Reports"))
    return root / d.strftime("%Y-%m") / d.isoformat() / "outputs"


def build(d: date, report_type: str):
    ctx = Context(d, fallback_hierarchy=(report_type == "sales_comparison"))
    return BUILDERS[report_type](ctx)


def generate(d: date, types: list[str] | None = None, user: str | None = None, run_id: int | None = None) -> list[dict]:
    types = [t for t in (types or list(BUILDERS)) if t in BUILDERS]
    results = []
    for t in types:
        name = REPORT_TYPES[t]
        try:
            table = build(d, t)
            path = excel.write(table, output_dir(d) / f"{table.file_stem}.xlsx")
            status, title, warnings, summary, err = "generated", table.title, table.warnings, table.summary, ""
        except ReportError as e:
            path, status, title, warnings, summary, err = None, "skipped" if "skipped" in str(e) else "failed", name, [], {}, str(e)
        except Exception as e:   # never let one report stop the others
            log.exception("Report %s failed", t)
            path, status, title, warnings, summary, err = None, "failed", name, [], {}, f"{type(e).__name__}: {e}"
        cur = db.conn().execute(
            "INSERT INTO reports(run_id, report_type, report_date, title, xlsx_path, status, summary_json, warnings_json, "
            "created_at, created_by) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (run_id, t, d.isoformat(), title, str(path) if path else None, status, json.dumps(summary, default=str),
             json.dumps(warnings + ([err] if err else [])), db.now_iso(), user))
        log.info("Report %s for %s: %s%s", name, d, status, f" ({err})" if err else "")
        results.append({"id": cur.lastrowid, "type": t, "name": name, "title": title, "status": status,
                        "path": str(path) if path else "", "warnings": warnings, "error": err, "summary": summary})
    done = ", ".join(r["type"] + "=" + r["status"] for r in results)
    db.audit(user, "reports.generate", f"{d} {done}")
    return results


def readiness(d: date) -> list[dict]:
    """What data exists for a report date — shown in the Run Center before generating."""
    from .context import _prev_working
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


def history(limit: int = 300, report_type: str = "", status: str = "") -> list[dict]:
    q, args = "SELECT * FROM reports WHERE 1=1", []
    if report_type:
        q += " AND report_type=?"
        args.append(report_type)
    if status:
        q += " AND status=?"
        args.append(status)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    out = []
    for r in db.conn().execute(q, args):
        x = dict(r)
        x["summary"] = json.loads(x.pop("summary_json"))
        x["warnings"] = json.loads(x.pop("warnings_json"))
        x["name"] = REPORT_TYPES.get(x["report_type"], x["report_type"])
        x["exists"] = bool(x["xlsx_path"]) and Path(x["xlsx_path"]).exists()
        out.append(x)
    return out
