# HYDRA — Technology & Build Plan

## 1. Technology list

### Core
- [ ] **Python 3.11+**: all application logic
- [ ] **pywebview**: native Windows desktop window that hosts the HTML UI; JS ↔ Python bridge through `js_api`
- [ ] **HTML5 + CSS3 + vanilla JavaScript**: UI screens (no build step, same as Chimera)
- [ ] **Chart.js**: charts on the Dashboard, Activity Monitor and Activity Reports (bundled locally, works offline)

### Automation
- [ ] **Playwright (Python)**: SFA login, navigation, filters, clicking the green Excel icon, capturing downloads
- [ ] **Playwright persistent profile on WhatsApp Web**: link once by QR, then send PNG/PDF to groups and contacts
- [ ] **APScheduler**: run times with a Today / Yesterday report date, monthly jobs, Activity Report schedule
- [ ] **Background worker process + Windows Task Scheduler**: scheduled runs continue while the window is closed
- [ ] **pystray**: tray icon with Open, Generate Now, Pause, Stop all, Exit

### Data
- [ ] **pandas**: read SFA exports, text → number conversion, aggregation
- [ ] **openpyxl**: styled Excel outputs with **real formulas** (%, variance, SUM subtotals, AVG PC)
- [ ] **SQLite**: local database for settings, targets, calendar, history, runs, logs and users (indexed)
- [ ] **rapidfuzz**: fuzzy territory/rep name suggestions for the alias tables

### Output
- [ ] **Jinja2 HTML templates**: one layout per report
- [ ] **Playwright `page.pdf()` / `page.screenshot()`**: PDF + WhatsApp-ready PNG from the same layout

### Security & system
- [ ] **keyring**: SFA password in Windows Credential Manager
- [ ] **hashlib PBKDF2**: user passwords, compatible with Famulus users
- [ ] **psutil + Playwright response sizes**: data-burning meter
- [ ] **logging (rotating files) + SQLite log table**: Logs screen with Copy Log
- [ ] **winotify / plyer**: Windows toast notifications
- [ ] **PyInstaller + Inno Setup**: Windows installer with icons from the Hydra logo

## 2. Architecture

```
┌──────────────── UI process (main.py) ────────────────┐
│ pywebview window (HTML/CSS/JS)  ⇄  js_api (Python)   │
│ tray icon (pystray)                                  │
└──────────────┬───────────────────────────────────────┘
               │ commands / status (SQLite + local socket)
┌──────────────▼──────────── Worker process (worker.py) ┐
│ APScheduler → Runner (stop-flag checks every step)    │
│   ├─ SFA module (Playwright)   ─ downloads            │
│   ├─ Cleaner (pandas)          ─ text→number, header  │
│   ├─ Processing                ─ callage split/merge  │
│   ├─ Report engines            ─ 5 daily + monthly    │
│   ├─ Renderers                 ─ Excel / PDF / PNG    │
│   └─ WhatsApp sender (Playwright, after approval)     │
└──────────────┬────────────────────────────────────────┘
               ▼
        SQLite  hydra.db   +   Output folder / backups
```

## 3. Reports Hydra produces
- [ ] Day Report (daily)
- [ ] Target vs Achievement (daily, month to date)
- [ ] Sales Comparison (daily)
- [ ] Daily Winners (competition days only) + Winners Summary (per round)
- [ ] Pending Order Value (daily)
- [ ] Finalized Target vs Achievement (monthly / on demand)
- [ ] Activity Report (any period, scheduled or on demand)

## 4. SFA pages automated
- [ ] Outlet Wise SKU Sales Report
- [ ] Callage Summary (report date for Van, previous working day for Pre)
- [ ] View Pre-Selling / Sales Order (Active + Pending, report date)
- [ ] View Territory (Status = Active)
- [ ] Rep Performance Report (month to date / month end)

## 5. Build phases
- [ ] **Phase 1:** project skeleton, theme, login, settings storage, setup wizard UI
- [ ] **Phase 2:** SFA login + generic page/filter downloader + "Learn Filters"
- [ ] **Phase 3:** cleaner (header detection, text→number, totals-row removal) + database
- [ ] **Phase 4:** Famulus import (targets, history, users, outlet categories, selling modes, NOWD)
- [ ] **Phase 5:** Targets Editor, Calendar & Competition, aliases & label overrides
- [ ] **Phase 6:** Callage preparation + the 5 daily reports (Excel with formulas)
- [ ] **Phase 7:** Rep Performance + Finalized Target vs Achievement + Reconciliation
- [ ] **Phase 8:** PDF/PNG rendering + Preview & Send pop-up
- [ ] **Phase 9:** WhatsApp linking and sending
- [ ] **Phase 10:** scheduler, worker, tray, Today/Yesterday slots, Stop all
- [ ] **Phase 11:** Activity Monitor, Activity Reports, data meter, Logs, Notifications, About
- [ ] **Phase 12:** installer, backups, final verification

## 6. Verification checkpoints
- [ ] 3 Nov 2026 GT Day Achievement = **2,318,859.42**
- [ ] Kaduwela 3 Nov Day Target = **85,110.30**; Cumulative Day Target = **168,443.64**
- [ ] 3 Nov Daily Winners: 32 territories, 8 winners (Matara = No)
- [ ] 3 Nov Pending Orders: Puttlam 194,584.50 / 30
- [ ] October 2026 national GT = **60,736,895.79**; SMMT = **9,968,055.13**
- [ ] October AVG PC: Chilaw 22.6, Puttlam 17.2, Kirindiwela 14.4, ASM Milan 18.1
- [ ] November 2026 calendar: NOWD 24; Round 1 = 8 days; Round 2 = 7 days

## 7. Delivery rules
- Every code file states exactly where it goes in the project folder.
- Every code update comes with a GitHub commit message.
