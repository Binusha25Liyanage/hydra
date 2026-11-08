"""Turn a report Table into a PDF (A4 landscape) and WhatsApp-ready PNG images.

One headless browser is opened per generate run (Renderer is a context manager)
and every report is printed through it. Fonts and the logo are embedded, so the
output looks the same on every PC and needs no internet.
"""
from __future__ import annotations

import base64
import html
import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from .. import paths, settings
from .table import Table

log = logging.getLogger("hydra.render")

ROWS_PER_IMAGE = 40          # WhatsApp shows ~40 rows legibly on a phone
A4_LANDSCAPE_PX = 1060       # printable width at 96 dpi with 8 mm margins


# ------------------------------------------------------------------ assets
@lru_cache(maxsize=None)
def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def _font_css() -> str:
    fonts = paths.ui_dir() / "assets" / "fonts"
    out = []
    for w in (400, 500, 600, 700):
        f = fonts / f"inter-latin-{w}-normal.woff2"
        if f.exists():
            out.append(f'@font-face{{font-family:"Inter";font-weight:{w};src:url(data:font/woff2;base64,{_b64(f)}) format("woff2")}}')
    f = fonts / "eb-garamond-latin-600-normal.woff2"
    if f.exists():
        out.append(f'@font-face{{font-family:"EB Garamond";font-weight:600;src:url(data:font/woff2;base64,{_b64(f)}) format("woff2")}}')
    return "\n".join(out)


def _logo() -> str:
    p = paths.ui_dir() / "assets" / "img" / "hydra_logo_cherry.png"
    return f"data:image/png;base64,{_b64(p)}" if p.exists() else ""


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Inter",Arial,sans-serif;color:#1A1B1E;background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.sheet{display:inline-block;padding:18px 20px 14px;background:#fff;min-width:640px}
.head{display:flex;align-items:center;gap:14px;border-bottom:3px solid #9A1428;padding-bottom:10px;margin-bottom:10px}
.head img{height:44px}
.head .t{flex:1}
.head h1{font-family:"EB Garamond",Georgia,serif;font-weight:600;font-size:22px;color:#9A1428;letter-spacing:.2px}
.head .sub{font-size:11px;color:#55575E;margin-top:3px;max-width:1100px;line-height:1.35}
.head .meta{text-align:right;font-size:10px;color:#6B6E76;line-height:1.5;white-space:nowrap}
.head .meta b{color:#1A1B1E;font-weight:600}
table{border-collapse:collapse;font-size:11.5px}
thead th{background:#9A1428;color:#fff;font-weight:600;padding:6px 7px;border:1px solid #7A0F20;text-align:center;line-height:1.2}
td{padding:4px 7px;border:1px solid #D5D6DA;white-space:nowrap;font-variant-numeric:tabular-nums}
td.n{text-align:right}
td.c{text-align:center}
tr.sub td{background:#F6E6E9;font-weight:600}
tr.reg td{background:#EDCDD3;font-weight:700}
tr.tot td{background:#D9A3AD;font-weight:700;border-top:2px solid #9A1428}
tr.win td{background:#E3F4EC}
td.red{color:#C00000}
td.neg{color:#B3172F}
td.yes{color:#13603F;font-weight:700}
tbody tr:nth-child(even):not(.sub):not(.reg):not(.tot):not(.win) td{background:#FAFAFB}
.foot{display:flex;justify-content:space-between;font-size:9.5px;color:#8A8C93;margin-top:8px}
.warn{margin-top:8px;font-size:10px;color:#8A5A00}
@page{size:A4 landscape;margin:8mm}
@media print{.sheet{display:block;padding:0;min-width:0}thead{display:table-header-group}tr{break-inside:avoid}}
"""


# ------------------------------------------------------------------ formatting
def fmt(v, kind: str) -> str:
    if v is None or v == "":
        return ""
    if kind == "text" or isinstance(v, str):
        return html.escape(str(v))
    try:
        x = float(v)
    except (TypeError, ValueError):
        return html.escape(str(v))
    if kind == "pct":
        return f"{x * 100:,.1f}%"
    if kind == "int":
        return f"{x:,.0f}"
    if kind == "number":
        return f"{x:,.2f}"
    return f"{x:,.0f}"          # money: whole rupees on images/PDF (Excel keeps the cents)


def _cell(table: Table, row, i: int, c) -> tuple[str, str]:
    first = table.columns[0].key
    if i == 0 and c.kind == "text" and first in ("label", "territory") and row.kind != "plain":
        v = row.label
    elif c.key == first and row.kind == "total":
        v = row.label
    else:
        v = row.values.get(c.key)
    cls = []
    if c.kind != "text":
        cls.append("n")
        try:
            if float(v) < 0:
                cls.append("neg")
        except (TypeError, ValueError):
            pass
    if c.key == "winner":
        cls = ["c"] + (["yes"] if v == "Yes" else [])
    if i == 0 and row.style == "red":
        cls.append("red")
    return fmt(v, c.kind), " ".join(cls)


def _row_class(row) -> str:
    if row.kind == "total":
        return "tot"
    if row.kind == "subtotal":
        return "reg" if row.level <= 2 else "sub"
    return "win" if row.style == "winner" else ""


def html_for(table: Table, rows: list | None = None, part: tuple[int, int] | None = None, for_print=False) -> str:
    rows = table.rows if rows is None else rows
    head = "".join(f"<th>{html.escape(c.header)}</th>" for c in table.columns)
    body = []
    for r in rows:
        tds = "".join(f'<td class="{cls}">{txt}</td>' for txt, cls in
                      (_cell(table, r, i, c) for i, c in enumerate(table.columns)))
        body.append(f'<tr class="{_row_class(r)}">{tds}</tr>')
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")
    part_txt = f"Image {part[0]} of {part[1]}" if part and part[1] > 1 else ""
    logo = _logo()
    warn = ""
    if for_print and table.warnings:
        warn = '<div class="warn">' + "<br>".join("⚠ " + html.escape(w) for w in table.warnings[:6]) + "</div>"
    org = html.escape(settings.get("reports.org_name") or "Lakmee Exports Lanka")
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_font_css()}{CSS}</style></head>
<body><div class="sheet">
<div class="head">{f'<img src="{logo}">' if logo else ''}<div class="t"><h1>{html.escape(table.title)}</h1>
<div class="sub">{html.escape(table.subtitle or '')}</div></div>
<div class="meta"><b>{org}</b><br>Generated {now}<br>{part_txt}</div></div>
<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>
{warn}<div class="foot"><span>Hydra · Work Automation Suite</span><span>{part_txt}</span></div>
</div></body></html>"""


def chunks(rows: list, size: int = ROWS_PER_IMAGE) -> list[list]:
    """Split rows into image pages. Prefer to cut just after a subtotal so a group isn't split."""
    if len(rows) <= size + 6:          # a few extra rows are better than a 2-row second image
        return [rows]
    out, i = [], 0
    while i < len(rows):
        end = min(i + size, len(rows))
        if end < len(rows):
            for j in range(end, max(i + size - 12, i + 1), -1):
                if rows[j - 1].kind in ("subtotal", "total"):
                    end = j
                    break
            if len(rows) - end <= 6:   # don't leave a tiny last image
                end = len(rows)
        out.append(rows[i:end])
        i = end
    return out


# ------------------------------------------------------------------ browser
class Renderer:
    """with Renderer() as r: r.render(table, xlsx_path) -> (pdf_path, [png paths])"""

    def __init__(self):
        self._pw = self._browser = self._page = None
        self.error = ""

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            channel = settings.get("sfa.browser") or "chromium"
            try:
                args = {"headless": True}
                if channel in ("msedge", "chrome"):
                    args["channel"] = channel
                self._browser = self._pw.chromium.launch(**args)
            except Exception:
                # fall back to whichever browser exists on this PC
                for ch in ("msedge", "chrome", None):
                    try:
                        self._browser = self._pw.chromium.launch(headless=True, **({"channel": ch} if ch else {}))
                        break
                    except Exception:
                        continue
            if not self._browser:
                raise RuntimeError("No browser available for PDF/PNG (install Edge/Chrome or run 'playwright install chromium')")
            self._page = self._browser.new_page(viewport={"width": 1400, "height": 900}, device_scale_factor=2)
        except Exception as e:
            self.error = str(e)
            log.warning("PDF/PNG rendering unavailable: %s", e)
            self.close()
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        for obj, fn in ((self._browser, "close"), (self._pw, "stop")):
            try:
                if obj:
                    getattr(obj, fn)()
            except Exception:
                pass
        self._pw = self._browser = self._page = None

    @property
    def ok(self) -> bool:
        return self._page is not None

    def render(self, table: Table, xlsx_path: Path, pdf=True, png=True) -> tuple[Path | None, list[Path]]:
        if not self.ok:
            raise RuntimeError(self.error or "Renderer not started")
        base = Path(xlsx_path).with_suffix("")
        pdf_path, pngs = None, []
        page = self._page
        if pdf:
            page.set_content(html_for(table, for_print=True), wait_until="load")
            width = page.evaluate("document.querySelector('table').getBoundingClientRect().width")
            scale = max(0.35, min(1.0, A4_LANDSCAPE_PX / max(width, 1)))
            pdf_path = base.with_suffix(".pdf")
            page.pdf(path=str(pdf_path), format="A4", landscape=True, print_background=True, scale=scale,
                     margin={"top": "8mm", "bottom": "8mm", "left": "8mm", "right": "8mm"})
        if png:
            parts = chunks(table.rows)
            for i, rows in enumerate(parts, start=1):
                page.set_content(html_for(table, rows, (i, len(parts))), wait_until="load")
                out = Path(f"{base}{'' if len(parts) == 1 else f'_{i}'}.png")
                page.locator(".sheet").screenshot(path=str(out))
                pngs.append(out)
        return pdf_path, pngs
