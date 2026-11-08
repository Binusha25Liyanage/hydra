"""Hydra services — one folder per piece of work a role does.

Every service lives in app/services/<service_id>/ and exposes a SERVICE object
(see _template/ and docs/SERVICE_GUIDE.md). The core (login, SFA downloads, data
import, report writer, PDF/PNG, WhatsApp, scheduler) is shared by all services.

Services are listed explicitly in INSTALLED so that a Windows build (or a role
edition of Hydra) contains exactly the services named here.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

# The services compiled into this build of Hydra, in menu order.
INSTALLED = ["sales_reports"]


@dataclass
class ReportDef:
    id: str                                   # unique across Hydra, e.g. "day_report"
    name: str                                 # shown to users, e.g. "Day Report"
    build: Callable[[date], object]           # report date -> app.reports.table.Table
    description: str = ""
    default_on: bool = True                   # ticked by default in the Run Center


@dataclass
class Service:
    id: str
    name: str
    description: str
    roles: list[str]                          # role ids that get this service (Super Admin always does)
    sfa_pages: list[str] = field(default_factory=list)      # page profile keys it downloads
    reports: list[ReportDef] = field(default_factory=list)
    readiness: Callable[[date], list[dict]] | None = None   # data check shown before generating
    version: str = "1.0"


_cache: dict[str, Service] | None = None


def all_services() -> dict[str, Service]:
    global _cache
    if _cache is None:
        _cache = {}
        for sid in INSTALLED:
            mod = importlib.import_module(f"{__name__}.{sid}")
            svc: Service = mod.SERVICE
            _cache[svc.id] = svc
    return _cache


def all_reports() -> dict[str, tuple[Service, ReportDef]]:
    return {r.id: (s, r) for s in all_services().values() for r in s.reports}


def report(report_id: str) -> tuple[Service, ReportDef]:
    reps = all_reports()
    if report_id not in reps:
        raise KeyError(f"Unknown report: {report_id}")
    return reps[report_id]
