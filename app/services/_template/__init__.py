"""TEMPLATE — copy this folder to start a new service. See docs/SERVICE_GUIDE.md.

1. Copy app/services/_template  ->  app/services/<your_service_id>   (lowercase, underscores)
2. Fill in SERVICE below and write your report builders in reports.py
3. Add "<your_service_id>" to INSTALLED in app/services/__init__.py
4. Add a test in tests/test_<your_service_id>.py
The folder name starts with "_" so Hydra never loads the template itself.
"""
from __future__ import annotations

from datetime import date

from .. import ReportDef, Service
from .reports import example_report


def readiness(d: date) -> list[dict]:
    # One row per input the reports need (shown in the Run Center data check)
    return [{"item": "Example input", "ok": True, "detail": "Replace with a real check", "needed_by": "Example Report"}]


SERVICE = Service(
    id="example_service",
    name="Example Service",
    description="One line saying what work this service does for its role.",
    roles=["it_assistant"],              # role ids, e.g. hr_assistant, finance_executive
    sfa_pages=[],                        # page profile keys it downloads (Settings → SFA pages)
    reports=[ReportDef("example_report", "Example Report", example_report, "What the report shows")],
    readiness=readiness,
)
