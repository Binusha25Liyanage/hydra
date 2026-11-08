"""Report builders: take a date, return an app.reports.table.Table.

The core turns the Table into Excel (with formulas), PDF and WhatsApp PNGs,
records it in Reports History and offers it in Preview & Send — a service
never writes files itself.
"""
from __future__ import annotations

from datetime import date

from ...reports.table import Column, Row, Table


class ReportError(Exception):
    """Raise with a clear message when a report can't be built (e.g. data missing)."""


def example_report(d: date) -> Table:
    cols = [
        Column("label", "Name", "text", 28, sum=False),
        Column("value", "Value", "money", 14),
    ]
    rows = [Row("plain", "Example", {"label": "Example", "value": 1000.0})]
    return Table(report_type="example_report", name="Example Report",
                 title=f"Example Report — {d:%d %B %Y}", subtitle="", columns=cols, rows=rows,
                 file_stem=f"Example_Report_{d.isoformat()}")
