"""Write a report Table to a styled .xlsx with real formulas."""
from __future__ import annotations

import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .table import Table

CHERRY = "9A1428"
HEADER_FILL = PatternFill("solid", fgColor=CHERRY)
SUB_FILL = PatternFill("solid", fgColor="F6E6E9")
REGION_FILL = PatternFill("solid", fgColor="EDCDD3")
TOTAL_FILL = PatternFill("solid", fgColor="D9A3AD")
WIN_FILL = PatternFill("solid", fgColor="E3F4EC")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
FORMATS = {"money": "#,##0.00", "int": "#,##0", "pct": "0.0%", "number": "#,##0.00", "text": "General"}
FIRST_DATA_ROW = 5


def _sheet_name(name: str) -> str:
    return re.sub(r"[\[\]\:\*\?\/\\]", "", name)[:31]


def write(table: Table, path: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = _sheet_name(table.name)
    ncol = len(table.columns)
    letters = {c.key: get_column_letter(i + 1) for i, c in enumerate(table.columns)}
    last = get_column_letter(ncol)

    # Title + summary
    ws["A1"] = table.title
    ws["A1"].font = Font(bold=True, size=14, color=CHERRY)
    ws.merge_cells(f"A1:{last}1")
    ws["A2"] = table.subtitle
    ws["A2"].font = Font(italic=True, size=10)
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(f"A2:{last}2")
    ws.row_dimensions[2].height = 30 if len(table.subtitle) < 220 else 45

    # Header
    for i, c in enumerate(table.columns, start=1):
        cell = ws.cell(4, i, c.header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
        ws.column_dimensions[get_column_letter(i)].width = c.width
    ws.row_dimensions[4].height = table.header_height

    # Rows
    first_col = table.columns[0].key
    for idx, row in enumerate(table.rows):
        r = FIRST_DATA_ROW + idx
        is_sum = row.kind in ("subtotal", "total")
        fill = None
        if row.kind == "total":
            fill = TOTAL_FILL
        elif row.kind == "subtotal":
            fill = REGION_FILL if row.level <= 2 else SUB_FILL
        elif row.style == "winner":
            fill = WIN_FILL
        for i, c in enumerate(table.columns, start=1):
            if i == 1 and table.columns[0].kind == "text" and first_col in ("label", "territory") and row.kind != "plain":
                value = row.label
            elif c.key == first_col and row.kind == "total":
                value = row.label
            else:
                value = row.values.get(c.key)
            if c.formula:
                value = c.formula.format(**{k: f"{L}{r}" for k, L in letters.items()})
            elif is_sum and c.kind != "text" and c.sum and row.children:
                refs = ",".join(f"{letters[c.key]}{FIRST_DATA_ROW + j}" for j in row.children)
                value = f"=SUM({refs})"
            cell = ws.cell(r, i, value)
            cell.number_format = FORMATS.get(c.kind, "General")
            cell.border = BORDER
            if c.kind == "text":
                cell.alignment = Alignment(horizontal="left")
            if is_sum:
                cell.font = Font(bold=True)
            if row.style == "red" and i == 1:
                cell.font = Font(color="C00000", bold=is_sum)
            if c.key == "winner":
                cell.alignment = Alignment(horizontal="center")
                if value == "Yes":
                    cell.font = Font(bold=True, color="13603F")
            if fill:
                cell.fill = fill
    ws.freeze_panes = table.freeze
    ws.sheet_view.zoomScale = 90
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = "4:4"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path
