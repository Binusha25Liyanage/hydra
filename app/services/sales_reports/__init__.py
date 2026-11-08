"""Service: Management Sales Reports (Sales Admin Coordinator).

Daily: Day Report, Target vs Achievement, Sales Comparison, Daily Winners, Pending Order Value.
Inputs: Outlet Wise SKU Sales, Callage Summary (Van = report day, Pre = previous working day),
View Pre-Selling (Sales Order); targets + NOWD from Hierarchy & Targets.
"""
from __future__ import annotations

from datetime import date

from .. import ReportDef, Service
from .context import Context
from .readiness import readiness
from .reports import BUILDERS, REPORT_TYPES


def _builder(report_id: str):
    def build(d: date):
        ctx = Context(d, fallback_hierarchy=(report_id == "sales_comparison"))
        return BUILDERS[report_id](ctx)
    return build


SERVICE = Service(
    id="sales_reports",
    name="Management Sales Reports",
    description="Daily management sales reports from SFA SKU sales, Callage and Pre-Selling orders.",
    roles=["sales_admin_coordinator"],
    sfa_pages=["sku", "callage", "preselling", "territory"],
    reports=[ReportDef(rid, name, _builder(rid)) for rid, name in REPORT_TYPES.items()],
    readiness=readiness,
)
