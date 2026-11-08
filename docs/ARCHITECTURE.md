# Hydra — Architecture

Hydra is one codebase. Everything every role needs (sign-in, SFA browser, data
import, report writer, PDF/PNG, Preview & Send, WhatsApp, scheduler, logs) is the
**core**. The work a particular role does is a **service**.

```
hydra/
├─ main.py                     window, icon, title bar, single instance
├─ app/
│  ├─ api.py                   every button in the UI calls a method here
│  ├─ db.py  settings.py  auth.py  paths.py  logging_setup.py  notify.py
│  ├─ startup.py               splash-screen checks (SFA login, WhatsApp, …)
│  ├─ sfa/                     SFA sign-in and (Phase 2) downloads
│  ├─ data/                    read SFA Excel exports, Famulus import, targets
│  ├─ reports/                 CORE report output
│  │  ├─ table.py              Table / Column / Row — what every report builder returns
│  │  ├─ excel.py              Table -> styled .xlsx with real formulas
│  │  ├─ render.py             Table -> PDF (A4 landscape) + WhatsApp PNGs
│  │  └─ engine.py             generate / history / approve / preview images
│  ├─ services/                ROLE WORK — one folder per service
│  │  ├─ __init__.py           registry + INSTALLED list
│  │  ├─ sales_reports/        Sales Admin Coordinator: daily management sales reports
│  │  └─ _template/            copy this to start a new service
│  └─ whatsapp/                (Phase 9)
├─ ui/                         HTML / CSS / JS screens
├─ tests/
└─ docs/
```

## How a report is made

1. **Run Center** (or the schedule) calls `api.reports_generate(date, report_ids)`.
2. `engine.generate` asks the registry which service owns each report and calls
   its `build(date)` → a `Table`.
3. The core writes Excel (`excel.py`), then PDF + PNG images (`render.py`)
   through one headless browser per run.
4. A row is saved in the `reports` table (status `generated`).
5. **Preview & Send** shows the images; the user ticks reports and presses
   Approve (→ `approved`, and in Phase 9 sent to WhatsApp) or Save (→ `saved`).

## Roles and editions

Each service lists the roles that get it (`Service.roles`). The Super Admin gets
all services. Phase 12's build script can produce one Hydra.exe for everyone
(services unlocked by role from the Google Sheet) or a separate edition per role
by changing `INSTALLED` — both come from this same codebase, so a fix to the
core reaches every user.

## Updates (Hydra Cloud phase)

The Super Admin uploads a new build to the Drive *Releases* folder and sets the
version in the Sheet. Each Hydra checks on start, downloads, and restarts.
