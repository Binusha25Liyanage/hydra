"""Generate reports for a date: build → write Excel → record in the reports table."""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from .. import db, paths, settings
from .. import services
from . import excel


class ReportError(Exception):
    """A report could not be built (message is shown to the user)."""


def _is_report_error(e: Exception) -> bool:
    return isinstance(e, ReportError) or type(e).__name__ == "ReportError"


def report_types() -> dict[str, str]:
    return {rid: r.name for rid, (_, r) in services.all_reports().items()}

log = logging.getLogger("hydra.reports")


def output_dir(d: date) -> Path:
    root = Path(settings.get("output.root") or (paths.data_root() / "Reports"))
    return root / d.strftime("%Y-%m") / d.isoformat() / "outputs"


def build(d: date, report_type: str):
    return services.report(report_type)[1].build(d)


def readiness(d: date) -> list[dict]:
    """Data check of every installed service, for the Run Center."""
    items = []
    for svc in services.all_services().values():
        if svc.readiness:
            items += svc.readiness(d)
    return items


def generate(d: date, types: list[str] | None = None, user: str | None = None, run_id: int | None = None,
             formats: tuple[str, ...] = ("pdf", "png"), stop=None, progress=None) -> list[dict]:
    """Build every selected report: Excel always, PDF/PNG when a browser is available.
    `stop()` -> True ends the run between reports; `progress(text)` reports what is happening."""
    names = report_types()
    types = [t for t in (types or list(names)) if t in names]
    results = []
    from .render import Renderer
    with Renderer() if formats else _NoRender() as rnd:
        for t in types:
            name = names[t]
            if stop and stop():
                results.append(_record(run_id, t, d, name, None, None, [], "skipped", [], {}, "Stopped by user", user))
                continue
            if progress:
                progress(f"Building {name}")
            pdf, pngs, path = None, [], None
            try:
                table = build(d, t)
                path = excel.write(table, output_dir(d) / f"{table.file_stem}.xlsx")
                status, title, warnings, summary, err = "generated", table.title, list(table.warnings), table.summary, ""
                if formats:
                    if rnd.ok:
                        if progress:
                            progress(f"Rendering {name} (PDF / images)")
                        try:
                            pdf, pngs = rnd.render(table, path, pdf="pdf" in formats, png="png" in formats)
                        except Exception as e:
                            log.exception("Render %s failed", t)
                            warnings.append(f"PDF/PNG not created: {e}")
                    else:
                        warnings.append(f"PDF/PNG not created: {rnd.error}")
            except Exception as e:   # never let one report stop the others
                if not _is_report_error(e):
                    log.exception("Report %s failed", t)
                    status, title, warnings, summary, err = "failed", name, [], {}, f"{type(e).__name__}: {e}"
                else:
                    status, title, warnings, summary, err = ("skipped" if "skipped" in str(e) else "failed"), name, [], {}, str(e)
            results.append(_record(run_id, t, d, title, path, pdf, pngs, status, warnings, summary, err, user, name))
    done = ", ".join(r["type"] + "=" + r["status"] for r in results)
    db.audit(user, "reports.generate", f"{d} {done}")
    return results


class _NoRender:
    ok, error = False, "PDF/PNG turned off"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


def _record(run_id, t, d, title, path, pdf, pngs, status, warnings, summary, err, user, name=None) -> dict:
    cur = db.conn().execute(
        "INSERT INTO reports(run_id, report_type, report_date, title, xlsx_path, pdf_path, png_paths, status, "
        "summary_json, warnings_json, created_at, created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (run_id, t, d.isoformat(), title, str(path) if path else None, str(pdf) if pdf else None,
         json.dumps([str(p) for p in pngs]), status, json.dumps(summary, default=str),
         json.dumps(warnings + ([err] if err else [])), db.now_iso(), user))
    log.info("Report %s for %s: %s%s", name or title, d, status, f" ({err})" if err else "")
    return {"id": cur.lastrowid, "type": t, "name": name or title, "title": title, "status": status,
            "path": str(path) if path else "", "pdf": str(pdf) if pdf else "", "pngs": [str(p) for p in pngs],
            "warnings": warnings, "error": err, "summary": summary}


def get(report_id: int) -> dict | None:
    r = db.conn().execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
    return _row(r, report_types()) if r else None


def set_status(ids: list[int], status: str, user: str | None = None) -> int:
    if status not in ("generated", "approved", "sent", "saved", "skipped"):
        raise ValueError(f"Bad status {status}")
    ids = [int(i) for i in ids]
    if not ids:
        return 0
    with db.tx() as c:
        n = c.execute(f"UPDATE reports SET status=? WHERE id IN ({','.join('?' * len(ids))}) AND status!='failed'",
                      [status, *ids]).rowcount
    db.audit(user, f"reports.{status}", ",".join(map(str, ids)))
    return n


def image(report_id: int, page: int = 0) -> dict:
    """A report's PNG page as a data URL for the preview (falls back to nothing if not rendered)."""
    import base64
    r = get(report_id)
    if not r:
        raise ValueError("Report not found")
    pngs = [p for p in r["png_paths"] if Path(p).exists()]
    if not pngs:
        return {"src": "", "page": 0, "pages": 0}
    page = max(0, min(page, len(pngs) - 1))
    data = base64.b64encode(Path(pngs[page]).read_bytes()).decode()
    return {"src": "data:image/png;base64," + data, "page": page, "pages": len(pngs)}


def _row(r, names) -> dict:
    x = dict(r)
    x["summary"] = json.loads(x.pop("summary_json") or "{}")
    x["warnings"] = json.loads(x.pop("warnings_json") or "[]")
    try:
        x["png_paths"] = json.loads(x.get("png_paths") or "[]")
    except ValueError:
        x["png_paths"] = []
    x["name"] = names.get(x["report_type"], x["report_type"])
    x["exists"] = bool(x["xlsx_path"]) and Path(x["xlsx_path"]).exists()
    x["has_pdf"] = bool(x.get("pdf_path")) and Path(x["pdf_path"]).exists()
    x["pages"] = sum(1 for p in x["png_paths"] if Path(p).exists())
    return x


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
    names = report_types()
    return [_row(r, names) for r in db.conn().execute(q, args)]
