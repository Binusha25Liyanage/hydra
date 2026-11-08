"""A report as a table: columns (with Excel formulas) + rows (territories, subtotals, totals).

Values are calculated in Python (for previews, PNG and tests) and the same maths is
written into Excel as real formulas, so management can audit every number.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

LEVEL_NAMES = {0: "National", 1: "Region", 2: "RSM", 3: "ASM", 4: "DTM", 5: "ASE", 6: "Territory"}


@dataclass
class Column:
    key: str
    header: str
    kind: str = "money"            # text | money | int | pct | number
    width: float = 14
    sum: bool = True               # subtotals add up their children
    formula: str | None = None     # Excel template, e.g. "=IF({day_target}=0,0,{ach}/{day_target})"
    calc: Callable[[dict], float] | None = None   # the same formula in Python


@dataclass
class Row:
    kind: str                      # territory | subtotal | total | plain
    label: str
    values: dict = field(default_factory=dict)
    children: list[int] = field(default_factory=list)   # indexes of direct child rows (subtotal / total)
    level: int = 6
    style: str = ""                # red | winner | ...


@dataclass
class Table:
    report_type: str
    name: str
    title: str
    subtitle: str
    columns: list[Column]
    rows: list[Row]
    file_stem: str
    freeze: str = "A5"
    header_height: float = 30
    summary: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def col(self, key: str) -> Column:
        return next(c for c in self.columns if c.key == key)

    def total_row(self) -> Row | None:
        return next((r for r in self.rows if r.kind == "total"), None)

    def find(self, label: str) -> Row | None:
        return next((r for r in self.rows if r.label == label), None)


def subtotal_label(n) -> str:
    if n.level == 0:
        return "NATIONAL TOTAL"
    return f"{n.label}  ({LEVEL_NAMES[n.level]} Total)"


def apply_formulas(columns: list[Column], values: dict) -> None:
    for c in columns:
        if c.calc is not None:
            values[c.key] = c.calc(values)


def hierarchy_rows(root, columns: list[Column], territory_values: Callable[[object], dict],
                   extra_group: tuple[str, list[tuple[str, dict]]] | None = None) -> list[Row]:
    """Territories followed by their subtotal rows (bottom-up, like the NSM sheet), then NATIONAL TOTAL.
    `extra_group` = ("Unmatched Territories", [(name, values), ...]) is added under National."""
    rows: list[Row] = []
    sum_cols = [c.key for c in columns if c.sum and c.calc is None and c.kind != "text"]

    def emit(n) -> int:
        if n.is_territory:
            v = territory_values(n)
            apply_formulas(columns, v)
            rows.append(Row("territory", n.label, v, level=6, style="red" if n.flagged_red else ""))
            return len(rows) - 1
        kids = [emit(k) for k in n.children]
        if n.level == 0 and extra_group and extra_group[1]:
            sub = []
            for name, v in extra_group[1]:
                apply_formulas(columns, v)
                rows.append(Row("territory", name, v, level=6))
                sub.append(len(rows) - 1)
            gv = {k: sum(rows[i].values.get(k, 0) or 0 for i in sub) for k in sum_cols}
            apply_formulas(columns, gv)
            rows.append(Row("subtotal", f"{extra_group[0]}  (Total)", gv, sub, level=1))
            kids.append(len(rows) - 1)
        v = {k: sum(rows[i].values.get(k, 0) or 0 for i in kids) for k in sum_cols}
        apply_formulas(columns, v)
        rows.append(Row("total" if n.level == 0 else "subtotal", subtotal_label(n), v, kids, level=n.level))
        return len(rows) - 1

    emit(root)
    return rows


def pct(a: str, b: str) -> tuple[str, Callable]:
    return f"=IF({{{b}}}=0,0,{{{a}}}/{{{b}}})", (lambda v: 0 if not v.get(b) else (v.get(a) or 0) / v[b])


def diff(a: str, b: str) -> tuple[str, Callable]:
    return f"={{{a}}}-{{{b}}}", (lambda v: (v.get(a) or 0) - (v.get(b) or 0))
