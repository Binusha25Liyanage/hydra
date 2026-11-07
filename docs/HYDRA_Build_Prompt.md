# PROJECT HYDRA — Management Report Automation Desktop App
### Full build prompt (paste this into your AI coding assistant / UI designer)

---

## 0. Who I am and what I want

I am Binusha, IT Support Engineer at Lakmee Exports Lanka Company (Pvt) Ltd (Lakmee Holdings), Sri Lanka. I already built **Project Chimera**, a desktop app that logs into our SalesPro SFA (`https://lakmee.salespro.lk`) and generates operational reports automatically.

Build me **HYDRA**, a sister app built with the same technologies as Chimera. Hydra is the many-headed serpent of Greek myth: one body (a shared SFA engine and database) with many heads (the management reports), all reporting to **management**.

Hydra must:
1. Log into SalesPro SFA with the user's own credentials.
2. Download the input Excel reports using URLs and filters that the user sets up.
3. Clean the data. **All number columns must be converted from text to numbers before processing.**
4. Store the data in a local database, so history accumulates day by day.
5. Generate 5 management reports as Excel, PDF and WhatsApp-ready PNG.
6. Show a preview, wait for approval, then send the reports to WhatsApp groups or contacts.
7. Run on a schedule (including when the main window is closed) and on demand ("Generate Reports Now").

**Report titles.** By default a title is just `<Report Name> — <date>`, e.g. `Day Report — 2026-11-03`.
- Settings → Reports has an optional **"Title prefix"** field, empty by default. If the user fills it in (e.g. "Hydra" or "Famulus"), titles become `<Prefix> — <Report Name> — <date>`.
- Each report's display name is also editable in that screen. The defaults are below.

---

## 0.1 Branding
- **Logo:** `ui/assets/hydra_logo.png`. A five-headed Hydra in vintage engraved maroon line art on cream parchment, inside a circular Greek-key/spiral border. It is the sister emblem of the Chimera logo.
- Generate `ui/assets/hydra.ico` (16, 32, 48, 256 px) from the logo for the window, tray and installer icons. At 16–32 px, crop to the inner circle (drop the border) so the heads stay readable.
- **Brand colours:** Metallic Cherry Alloy Red `#B3172F`→`#D42A45` (primary actions and accents), Metallic Black `#0B0C0E`→`#1C1D21` (sidebar, splash, login), Metallic Mercury `#C4C9D0` (chrome, borders, secondary), Off-White `#F7F5F0` (content). The full palette is in `HYDRA_Stitch_UI_Prompt.md`.
- Use the logo on: the sidebar top, the setup wizard welcome screen, the splash screen while the worker starts, the installer, and the report PDF/PNG header (small, top-left).

## 0.2 Hydra must be better than Famulus
Famulus (the IT Manager's current tool) is the baseline. Hydra must reproduce every Famulus figure exactly, and improve on it:

| Area | Famulus today | Hydra |
|---|---|---|
| Inputs | Files downloaded from SFA by hand and uploaded one by one, with the date picked by hand | Downloads everything from SFA automatically on schedule, with date rules |
| Callage Van/Pre preparation | Manual Excel editing | Automatic split + merge |
| Finalized Target vs Achievement | The "AI file" is finished by hand (PC count, Avg PC, previous month) | Generated fully automatically in one step (report 6.6) |
| Excel outputs | Pasted values | Real **formulas** for %, variance, subtotals and averages, so they can be audited |
| Accuracy checks | Few | Verification against known totals, a **Reconciliation** screen (database vs SFA Rep Performance), alias tables, wrong-month warnings, duplicate-date confirmation |
| Competition | One start/end date | A **Competition Calendar** with several rounds per month and the exact competition days (as the NSM sends it) |
| Delivery | Manual | WhatsApp with preview + approval, schedules with Today/Yesterday |
| Transparency | — | Activity Monitor, **Activity Reports**, data meter, logs, notifications |
| Users | Roles + licence | Same roles (superadmin / admin / user), with PBKDF2 hashes compatible with Famulus so users can be migrated |

## 1. Technology stack (same as Chimera)

| Layer | Technology | Purpose |
|---|---|---|
| Language | **Python 3.11+** | All backend logic |
| Desktop shell | **pywebview** | Native window hosting the HTML UI; JS ↔ Python bridge through `js_api` |
| UI | **HTML + CSS + vanilla JavaScript** (or Alpine.js), no build step | Screens, modals, toasts |
| SFA automation | **Playwright (Python, sync API)** | Log in, navigate, apply filters, click the green Excel icon, capture the download |
| WhatsApp | **Playwright persistent browser profile on WhatsApp Web** | Link once by QR scan, then send PNG/PDF to groups or contacts |
| Data processing | **pandas** + **openpyxl** | Read exports, convert types, aggregate, write styled Excel |
| Database | **SQLite** (through `sqlite3` or SQLAlchemy) | Settings, masters, daily history, run log |
| Report rendering | HTML/CSS templates (**Jinja2**) → Playwright `page.pdf()` and `page.screenshot()` | Identical layout for PDF and PNG |
| Scheduling | **APScheduler** inside a background worker process + **Windows Task Scheduler** entry to launch the worker at logon | Runs even when the UI is closed |
| Tray | **pystray** | Tray icon: Open, Generate Now, Pause schedule, Stop all, Exit |
| Notifications | **win10toast / plyer** + in-app toasts | Per-run success/failure notices |
| Credentials | **keyring** (Windows Credential Manager) | SFA password is never stored in plain text |
| Data meter | Playwright response-size tracking + **psutil** network counters | "Data burning" meter per run, per day and per month |
| Logging | Python `logging` → rotating file + SQLite run log | Viewable log with a Copy button |
| Packaging | **PyInstaller** (one-folder) + **Inno Setup** installer | Windows installer with desktop and Start menu shortcuts |

Processes:
- **UI process.** pywebview window plus tray icon.
- **Worker process.** Scheduler and runner. It talks to the UI through SQLite status tables or a local socket.
- **Stop button.** "Stop" sets a kill flag that the worker checks between every step, and closes any open Playwright browsers.

---

## 2. Project folder structure

```
hydra/
├── main.py                    # launches UI (pywebview) + tray
├── worker.py                  # background scheduler/runner entry point
├── config/
│   └── defaults.json
├── app/
│   ├── api.py                 # js_api class exposed to the UI
│   ├── db.py                  # SQLite schema + helpers
│   ├── settings.py            # read/write settings, keyring
│   ├── sfa/
│   │   ├── login.py
│   │   ├── downloader.py      # generic "profile" downloader (URL + filters)
│   │   └── filters.py         # set select/date filters on SFA pages
│   ├── processing/
│   │   ├── cleaner.py         # header detection, text→number, drop total rows
│   │   ├── callage.py         # van/pre split + merge
│   │   ├── sales.py
│   │   └── preselling.py
│   ├── reports/
│   │   ├── hierarchy.py       # build Region→RSM→ASM→DTM→ASE→Territory tree with subtotals
│   │   ├── day_report.py
│   │   ├── target_vs_achievement.py
│   │   ├── sales_comparison.py
│   │   ├── daily_winners.py
│   │   ├── pending_orders.py
│   │   ├── excel_writer.py
│   │   └── render.py          # Jinja2 → PDF/PNG via Playwright
│   ├── whatsapp/
│   │   ├── link.py            # QR linking session
│   │   └── sender.py
│   ├── scheduler.py
│   ├── runner.py              # one full pipeline run, with stop-flag checks
│   ├── datameter.py
│   └── notify.py
├── templates/                 # Jinja2 HTML for each report
├── ui/
│   ├── index.html
│   ├── css/
│   └── js/
├── data/                      # hydra.db, browser profiles (gitignored)
└── logs/
```

---

## 3. First-run Setup Wizard (step by step, cannot be skipped)

**Step 1 — Welcome.** Hydra logo, short description, "Start Setup".

**Step 2 — SFA Connection**
- SFA Base URL (default `https://lakmee.salespro.lk`)
- Username
- Password, stored in keyring, with a show/hide eye icon
- Browser choice: Chromium (bundled), Microsoft Edge, Google Chrome
- Run browser: Headless / Visible (toggle)
- **"Test Login"** button. It opens a browser, logs in, and shows ✅ "Logged in as <name>" or ❌ with the error.

**Step 3 — Page URLs.** One editable row per page, each with a "Test URL" button:
| Page | Default URL |
|---|---|
| Outlet Wise SKU Sales Report | `/it/reports/outlet_wise_sku_sales` |
| Callage Summary | `/it/reports/callage_summary` |
| View Pre-Selling | `/it/pre_selling` |
| View Territory | `/it/level-six` |

**Step 4 — Filter Setup (one tab per page).**
- The user chooses the value for every filter field the page has. All fields default to "Not selected = All".
- Each date field has a rule dropdown: *Report Date*, *Report Date − 1 (previous working day)*, *Month Start → Report Date*, *Last Month Same Day*, *Last Month Start → Same Day*, or *Fixed date*.
- Filter fields for each page:
  - **Outlet Wise SKU:** SFA, Channel, Region, Area, Supervisor Area, Territory, Distributor, Sales Rep, RSM, ASM, ASE, Product Category, Product Sub Category, Product, Report Type (default "All Invoices"), Date From, Date To
  - **Callage Summary:** SFA, Channel, Region, Area, Supervisor Area, Territory, RSM, ASM, ASE, Date From, Date To
  - **View Pre-Selling:** SFA, Channel, Region, Area, Supervisor Area, Territory, Route, Outlet, Distributor, Sales Rep, Date From, Date To, SO Number, Invoice Status (default **Pending**), SO Status (default **Active**)
  - **View Territory:** SFA, Channel, Region, Area, Supervisor Area, Territory, Status (default **Active**)
- **"Learn Filters" button.** Hydra opens the page and reads every dropdown label and its available options, so the user picks from real values instead of typing them.
- **Download method.** After Search, click the **green Excel (X) icon** (above the table, right side) and capture the download with Playwright `expect_download()`.

**Step 5 — Territory Sync.** Download View Territory with Status = Active. Show a table of active territories and save it to the `territories` table.

**Step 6 — Selling Mode Assignment.** Show a table of all active territories with a toggle for each: **Van Selling / Pre Selling**.
- Pre-fill from the SKU report's `SALES REP MODEL` column ("Van Selling" / "Pre Order") if one has already been downloaded.
- Bulk actions: "Set selected → Van", "Set selected → Pre".

**Step 7 — Hierarchy & Targets.**
- Upload or edit the monthly hierarchy: Region → RSM → ASM → DTM → ASE → Territory, with GT Monthly Target and SMMT Monthly Target for each territory.
- Name mapping: SFA territory name → hierarchy territory name, with fuzzy match suggestions.
- "Copy last month's hierarchy" button.
- The **National Sales Manager assigns the monthly targets before the month starts** (or on the first days of the month at the latest). Hydra's Day Targets are always derived from these monthly targets. They are never entered by hand.
- Targets are entered and maintained in Hydra's own **Targets Editor** (section 4.6). The wizard opens the same editor.

**Step 8 — Working Calendar.**
- Month calendar with Sundays off by default. Click days to mark holidays (Poya days, public holidays).
- Shows **NOWD** (number of working days), e.g. November 2026 = 24.
- NOWD is calculated from the calendar but can be **overridden manually** per month, as Famulus does with "Set Working Days". The override wins. If a month has no NOWD, reports stop with "Set NOWD for <Month> first".

**Step 9 — Report Rules.**
- Winner limits:
  - Van Selling: Sale ≥ 100,000 AND Bills ≥ 20
  - Pre Selling: Sale ≥ 125,000 AND Bills ≥ 30
- Both are editable.
- **Competition period:** start date and end date. Winners are only calculated for dates inside the period (default: the whole current month).
- **Outlet Categories (competition eligibility).** A table of every SFA Outlet Classification with: Pricing Scheme (Wholesale / MRP) and an "Include in competition" tick. Defaults, taken from Famulus:
  - **Unticked (MRP):** SMMT & Whole Sales - (SMMT - WS), SMMT Small - (SMMT -S), SMMT Large - (SMMT - L), 25% SMMT all product Discount, 30% SMMT all product Discount, Coop - Special Operation (L/M/S), CG, LS, KL, AR, LF
  - **Ticked (Wholesale):** all others (Groceries L/S, Boutique, WS, Semi WS, Pharmacy, Coop City Mega/Mini, Veg Shop, Restaurant, Hotel, Eating House, Canteen, Welfare Shop, Institution, Co-operative, LK, Top 15)
  - New classifications seen in downloads are added automatically as ticked, with a notification.
- **Excluded national SMMT territories** (never in Winners or Pending Orders): Colombo SMMT, Kandy SMMT, Anuradhapura SMMT. The list is editable. Match by an alphanumeric-only lowercase key, so "Anuradhapura(SMMT)" = "Anuradhapura SMMT".

**Step 10 — Save Location.** Folder picker for the output root. Hydra creates `<root>/<YYYY-MM>/<YYYY-MM-DD>/` for each run, with `inputs/` (raw downloads) and `outputs/` subfolders.

**Step 11 — WhatsApp Link.**
- "Link WhatsApp" opens WhatsApp Web in Hydra's own persistent browser profile and shows the QR code inside an Hydra modal.
- After linking: ✅ Linked as <number>, with an "Unlink" button.
- Recipients: add groups or contacts by exact name, test-send a message, and choose which reports go to which recipient.

**Step 12 — Schedule.**
- List of run times (e.g. 10:00, 13:00, 16:00, 19:00), with add and remove.
- Days-of-week checkboxes.
- Option: "Auto-send without approval when the app is unattended" (default **OFF**).
- "Run in background when window is closed" (default ON).

**Step 13 — Finish.** Summary of all settings, then "Run first test now".

Every wizard step can be reopened later from **Settings**.

---

## 4. Main application screens

Layout: left sidebar navigation (dark), Hydra logo at the top, Lakmee red/maroon accent (#8B0000 / #D32F2F), and white content cards. Match Chimera's theme.

Sidebar items: **Dashboard · Run Center · Reports · Territories · Hierarchy & Targets · Calendar & Competition · Schedule · WhatsApp · Reconciliation · Activity Monitor · Notifications · Logs · Settings · About**. The UI theme is defined in `HYDRA_Stitch_UI_Prompt.md`.

### 4.1 Dashboard
- Status cards: SFA connection status, WhatsApp link status, next scheduled run (countdown), last run result, data used today and this month.
- KPI strip for the latest report date: GT Day Target vs Achievement, MTD Achievement %, Winners count, Pending Order Value.
- Big buttons: **⚡ Generate Reports Now**, **⏸ Pause Schedule**, **⛔ Stop All**.
- Mini timeline of today's runs.

### 4.2 Run Center (live view while a run is in progress)
- Report Date picker (default = today) and checkboxes to choose which of the 5 reports to generate.
- A live step list with status icons (⏳/✅/❌), elapsed time and MB used for each step:
  1. Login to SFA
  2. Download Outlet Wise SKU (report day)
  3. Download Outlet Wise SKU (month to date)
  4. Download Outlet Wise SKU (last month 1 → same day), only if not already in the database
  5. Download Callage (report day)
  6. Download Callage (previous working day)
  7. Prepare and merge Callage
  8. Download View Pre-Selling (Active + Pending, report day)
  9. Convert types and save to the database
  10. Build the 5 reports
  11. Render Excel / PDF / PNG
  12. Preview and approval
  13. Send to WhatsApp
- Live log panel at the bottom.
- **Stop** button (kills the run safely), **Retry failed step**.

### 4.3 Report Preview & Send Pop-up (after every generation, before anything is sent)
Nothing is ever sent to WhatsApp until the user confirms in this pop-up. The only exception is "Auto-send when unattended" being ON.

**Layout**
- **Left column: "Select reports to send".** One row for each report generated in this run:
  - `☑ Day Report — 2026-11-03` · thumbnail · status (Ready / Failed)
  - `☑ Target vs Achievement — 2026-11-01 to 2026-11-03`
  - `☑ Sales Comparison — 03 Nov vs 03 Oct`
  - `☑ Daily Winners — 2026-11-03`
  - `☑ Pending Order Value — 2026-11-03`
  - Each row has a selection control. It is **multi-select**: any combination of reports can be chosen. All are ticked by default; failed reports are unticked and disabled.
  - A **Select all / Clear all** toggle at the top, and a live counter "3 of 5 selected".
  - For each report, a small format choice: **PNG / PDF / Both** (default: PNG for WhatsApp).
- **Right panel: large preview** of the report clicked on the left. Zoom, scroll and page through multi-image reports (e.g. "Image 1 of 2"), with an "Open PDF" link.
- **Bottom: Recipients.** Checkboxes for the WhatsApp groups and contacts. Pre-ticked from each report's default recipients (set on the WhatsApp screen); the user can change them for this send.
- **Optional caption** text box, pre-filled e.g. "Day Report — 03 Nov 2026".

**Buttons**
- **✅ Approve & Send Selected.** Sends only the ticked reports to the ticked recipients, then shows per-message progress and the result (✓ sent / ✗ failed + Retry). It is disabled if no report or no recipient is selected.
- **💾 Save.** Keeps all generated files in the output folder without sending (status: "Saved, not sent").
- **⛔ Stop.** Stops all of the application's processing, including the scheduler, until resumed.
- **🔄 Refresh.** Re-runs this generation with fresh SFA downloads and reopens the pop-up.

**Rules**
- The selection is remembered as the default for next time (per schedule slot).
- Unselected reports are still saved and marked "Not sent" in Reports history, where they can be sent later from the Reports screen.
- If nobody responds within N minutes (setting), the reports are kept as "Awaiting approval" in the Activity Monitor and nothing is sent.

### 4.4 Reports (history)
- Table: Date, Report, Run time, Status (Generated / Approved / Sent / Failed), and buttons to open Excel, PDF or PNG, Resend, and Open folder.
- Filters by date range and report type.

### 4.5 Territories
- Active territory database (from View Territory). Columns: Territory, Region, Area, Supervisor Area, Channel, Status, Selling Mode (editable toggle), Mapped hierarchy name, Last synced.
- "Sync now" button. Shows the diff after a sync: new territories, territories no longer active, and changed territories.
- Monthly auto-sync option.

### 4.6 Hierarchy & Targets Editor
A full in-app editor. This is the **only source** of targets and the management hierarchy. Nothing comes from SFA except the territory list.

**Top bar**
- Month selector (◀ November 2026 ▶).
- Status badge: *Draft* / *Locked*.
- Buttons: **New Month**, **Copy from Previous Month**, **Import Excel**, **Export Excel Template**, **Save**, **Lock Month**, **Unlock**.

**Left panel: Hierarchy Tree**
- Collapsible tree: Region → RSM → ASM → DTM → ASE → Territory.
- Right-click a node (or use the ⋯ menu): Add child, Rename, Move (drag & drop to a new parent), Delete (only when empty), Mark as Vacant.
- Levels are optional. A territory can sit directly under an ASM with no DTM or ASE, or under an RSM. The report subtotals follow the tree exactly, so empty levels are skipped.
- Each node shows its rolled-up GT and SMMT target totals live.
- Badge on each territory: Van / Pre, SMMT, and ⚠ if the territory is not mapped to an active SFA territory.

**Right panel: Targets Grid (spreadsheet-like)**
- Columns: Sort Order, Region, RSM, ASM, DTM, ASE, Territory (display name), SFA Territory (dropdown of active territories from the database), Is SMMT (checkbox), GT Monthly Target, SMMT Monthly Target, Notes.
- Inline editing, Tab/Enter navigation, paste a column of numbers from Excel, and fill-down.
- Numbers are shown with thousand separators but stored as numbers.
- Bulk tools:
  - "Set target for selected"
  - "Increase selected by %"
  - "Distribute a total across selected" (equal split or proportional to last month)
- Each row shows last month's target and last month's achievement, read-only, for reference.
- Footer: Grand total GT and Grand total SMMT, plus a check against the "expected national target" the user types in (highlighted red if they don't match).

**Validation panel**
- Active SFA territories missing from this month's hierarchy (with an "Add" button).
- Hierarchy territories not mapped to any SFA territory.
- Duplicate mappings.
- Territories with a GT target of 0 (warning only, since some are deliberately 0, e.g. Avissawella, Kahawaththa).
- Negative or non-numeric values (blocked).

**Behaviour**
- Every month has its own copy of the hierarchy and targets. Changing November never changes October.
- Locking a month prevents accidental edits. Reports always use the hierarchy of the report date's month.
- An audit trail records who changed which target, from what to what, and when. It is viewable in a "History" drawer.
- Excel import/export uses the same columns as the grid. Import shows a diff preview before applying.
- **Import the NSM's target workbook (primary format, same as Famulus "Upload Target File").** Columns: **DB Code / Territory / Dis(tributor) Name / CSR Name / Target <Month> <Year>**.
  - Territory rows are interleaved with subtotal rows for Area (ASE), Zone (ASM or DTM), Region (RSM) and a final National row. Subtotals are not consistently indented or labelled, so parse with the "pending list" method: walk the rows in order; each subtotal row absorbs every pending node deeper than its own level, then itself becomes pending.
  - Keep each territory's Distributor, CSR, **Operating / Vacant** status (Vacant when Distributor/CSR = "Vacant") and **flagged red** (the cell's font is red in the NSM's sheet). Red-flagged territories show in red in the exported reports.
  - Check that each declared subtotal = the sum of its children. Flag mismatches as warnings.
- **Edit-template round trip (as Famulus does):** "Export Edit Template" writes a flat one-row-per-territory sheet with a hidden **Row ID** column. On re-import: a matching Row ID updates that territory, a blank or unknown Row ID adds a new territory, and a Row ID that is missing from the file removes that territory (after confirmation).
- **Migration:** a one-click "Import from Famulus" reads Famulus's `target_report.db` and brings in the September/October targets, daily SKU sales, callage, pending orders, selling modes, outlet categories and NOWD as Hydra history. Last-month comparisons then work from day one.
- **Import from a Target vs Achievement layout.** Hydra can also import the hierarchy and targets straight from a Target vs Achievement Excel (Hierarchy column + Monthly Target + SMMT Target, with subtotal rows):
  - Rows ending in `(ASE Total)`, `(DTM Total)`, `(ASM Total)`, `(RSM Total)` or `(Region Total)` are parent nodes. Every row above a subtotal that isn't yet assigned belongs under it.
  - `NATIONAL TOTAL` is the root.
  - A territory row has GT target > 0 → GT territory. A territory row has SMMT target > 0 → SMMT territory.
  - After import, check that each parent's total equals the sum of its children, and flag any mismatch.
- **Month workflow:** at month start (or when the NSM releases targets), the app shows a banner "Targets for <Month> not set". The user imports or edits the targets, then Locks the month. If a report run happens with no targets for the month, it stops with a clear message instead of using the old month's figures.
- Mid-month target changes are allowed (not locked). Reports regenerate using the new figures, and the Day Target formula automatically uses the updated T.

### 4.7 Working & Competition Calendar
Recreates the NSM's monthly **"Competition Calendar"** sheet inside the app.

**Calendar layout**
- A month grid with columns MON … SAT, **SUN** and a final **"Competition Day"** column showing the number of competition days in each round, merged across that round's weeks.
- Title bar: `COMPETITION CALENDAR – NOVEMBER 2026 (24 – W/Days)`.

**Day states (click a day to cycle, or right-click for a menu)**
- **Working day** (white)
- **Sunday / weekly off** (red cell, white number)
- **Holiday** (red number on a white cell, e.g. Poya 24 Nov, with a holiday name)
- **Competition Round N** (each round has its own colour, e.g. Round 1 grey, Round 2 green)

**Competition rounds**
- Rounds are a list: name, colour, and the exact days in the round. Days can be selected by dragging across the grid.
- Default limits per round: Van 100,000 / 20 bills, Pre 125,000 / 30 bills. Limits can be overridden per round.
- The round's day count is shown automatically.

**Example: November 2026, as the NSM sent it**
- NOWD = 24: 30 days − 5 Sundays − Poya 24 Nov.
- Round 1 (grey): 3, 4, 5, 6, 7, 9, 10, 11 = **8 days**.
- Round 2 (green): 13, 14, 16, 17, 18, 19, 20 = **7 days**.
- Working days that are not competition days: 2, 12, 21, 23, 25, 26, 27, 28, 30.

**Rules**
- NOWD = working days (white + competition days). It can be overridden manually.
- Daily Winners is only produced on competition days. On other days the report is skipped, with a note "Not a competition day".
- The Winners Summary is produced per round.

**Tools**
- **Import**: read the NSM's calendar Excel or an image of it. With an image, the user confirms the result.
- **Export**: the calendar as a PNG in the same look, to share on WhatsApp.
- **Copy previous month's pattern.**

### 4.8 Schedule
- A run times list. Each slot has:
  - Time
  - **Report date: Today / Yesterday**
  - Which reports to generate
  - Days of week
  - Enabled toggle
  - Auto-send when unattended toggle
- A preview of the next 5 run times.
- **Monthly jobs:**
  - Finalized Target vs Achievement on the last working day, plus "on demand".
  - Rep Performance download.
  - Territory sync.
- An **Activity Report** schedule (e.g. every Monday 8:30, for the last 7 days).

### 4.9 WhatsApp
- Link status, QR modal, recipients (group/contact name, which reports, active toggle), test message, and send history.

### 4.10 Activity Monitor
- **Run history:** each run with start and end time, trigger (Scheduled / Manual), duration, status, reports produced, and data used. Expand a run to see its steps and its log.
- **Earlier reports:** quick open of any past report.
- **Data Burning Meter:** a gauge for today, a bar chart for MB per day over the last 30 days, a breakdown by source (SFA downloads, WhatsApp uploads, page loads), and a monthly cap warning (user sets a cap, e.g. 2 GB).
- **Health:** last successful SFA login, last WhatsApp send, database size, free disk space.
- **Activity Reports.** Generate a report of what Hydra has done for a **selected period** (date range picker with presets: Today, Yesterday, Last 7 days, This month, Last month, Custom). It contains:
  - **Summary KPIs:** total runs, successful / failed / stopped, success rate %, average run duration, reports generated, reports sent, WhatsApp messages sent / failed, total data used (MB), SFA downloads (count and MB).
  - **Runs table:** date, time, trigger (Scheduled slot / Manual / Monthly), report date, duration, status, reports produced, sent to, MB used, error.
  - **Per-report table:** each report type with how many times it was generated, approved, sent, saved only, or failed.
  - **Failures & warnings:** grouped by cause, e.g. SFA login failed, download timeout, unmatched territories, missing NOWD or targets, WhatsApp not linked.
  - **Charts:** runs per day (stacked success/failure), data used per day, average duration trend.
  - **User actions:** approvals, manual runs, stops, settings and target changes, with who and when.
  - Output: on-screen preview + Excel + PDF (+ PNG for WhatsApp). It can be sent to WhatsApp after approval like any other report, and can be scheduled.

### 4.11 Logs
- Live tail with level filter (Info / Warning / Error), search, a run selector, **📋 Copy Log** (copies the visible log to the clipboard) and Export .txt.

### 4.12 Settings
- Reopens every wizard section: SFA connection, URLs, filters, save location, winner limits, report titles (optional prefix + report display names), notification preferences, appearance (light/dark), backup/restore database, and about/version.

### 4.12a Reconciliation
- Pick a month. The table lists, per territory: Hydra database achievement vs SFA Rep Performance **ACHIEVED SALES**, the difference, and the difference %.
- Rows outside a tolerance (setting, default 1%) are highlighted.
- Filters: only differences, by region.
- Possible-cause hints: returns netted, a reassigned rep, a missing daily download (lists the dates with no data).
- Export to Excel. The database figure is always the official one in reports; this screen only explains the gaps.

### 4.12b Aliases & Label Overrides
- **Territory alias table:** SFA name ↔ hierarchy name, seeded with the known variants: homagama, Nuwaraeliya/Nuwara Eliya, kalawanchikudy, AngunakolaPelessa/Angunakolapelessa, Anuradhapura(SMMT), Hangurankethe, Mathale.
- **Rep alias table:** e.g. "CSR Anutradhapura - Vacant" = "CSR Anuradhapura - Vacant". Days worked are counted by sales_rep_code where possible.
- **Label overrides per month:** e.g. "ASM Vacant - Uva & Sab" → "ASM Vidura - Uva & Sab". Applied to the outputs only; the stored target is not changed.
- **Excluded territories:** test or dummy territories (Test Territory, Lakmee TERRITORY, Sathosa) are left out of totals unless they have a target.

### 4.12c Login, Users & About
- **Login screen:** username + password, with Hydra logo. Roles:
  - **superadmin:** everything, including users and licence
  - **admin:** settings, targets, schedules, approve/send
  - **user:** view reports, Generate Now, approve/send if allowed
- Users can be imported from Famulus. PBKDF2 hashes are kept compatible.
- **About screen:** logo, version, build date, licence status/expiry, "Check for updates" (manual), credits, a link to the user guide, and a database and app-folder info panel.

### 4.13 Notifications
- Windows toast plus an in-app bell list for: run started, run finished (with a summary line, e.g. "5 reports generated, 2.3 MB used"), approval needed, sent to WhatsApp, and any failure (with the reason and an "Open log" link).

---

## 5. Data processing rules

### 5.1 Reading every SFA export
- The SFA Excel has a company header block: rows 1–3 (company name, address, contact), row 5 (report name), rows 7–8 (applied filters and dates, generated by/at). **The data header is on row 10.**
  - Detect the header row automatically by finding the row that contains the expected column names. Do not hard-code row 10.
- Drop fully empty rows and the **grand-total row** at the bottom (the row where Territory is empty but numbers exist).
- **TYPE CONVERSION (mandatory):** numeric columns arrive as text with thousands separators, e.g. `"2,325.00"`. For every numeric column: strip `,` and spaces, then `pd.to_numeric(errors="coerce")`, then fill NaN with 0. Without this step, sums come out wrong: 341,663 instead of the correct 2,318,859.42.
- Dates are text `YYYY-MM-DD`. Parse them to dates.
- Trim whitespace in every text column. Match territory names case-insensitively (e.g. "homagama" vs "Homagama").
- Save the raw file to `inputs/`, and save the cleaned rows to SQLite tagged with the report date.

### 5.2 Outlet Wise SKU Sales Report
Columns: RSM, ASM, ASE, TERRITORY, DISTRIBUTOR, SALES REP CODE, SALES REP TYPE, SALES REP MODEL, SALES REP, OUTLET CODE, OUTLET CLASSIFICATION, OUTLET, ROUTE CODE, ROUTE, INVOICE / TRANSACTION DATE, INVOICE / SO NUMBER, CATEGORY, BRAND, PRODUCT CODE, PRODUCT, WHOLESALE PRICE, MRP, TOTAL UNITS, SALES VALUE (NET SALES), SALES VOLUME (MT)

- **Numeric:** WHOLESALE PRICE, MRP, TOTAL UNITS, SALES VALUE (NET SALES), SALES VOLUME (MT)
- **Daily sale per territory** = SUM(SALES VALUE (NET SALES)) grouped by TERRITORY and date
- **Two different "SMMT" concepts. Do not mix them up:**
  1. **SMMT territory** = a territory whose name contains "SMMT" (e.g. Colombo SMMT, Gampaha SMMT, Anuradhapura(SMMT), Kandy SMMT). Its target and all its sales go into the **SMMT** columns of Target vs Achievement and the Day Report. Every other territory is **GT**. The Targets Editor also has an "Is SMMT" override tick, defaulting to the name rule.
  2. **SMMT Outlet Sale** = sales (in any territory) to outlets whose OUTLET CLASSIFICATION is **unticked** in Outlet Categories. These are removed from the competition Sale Value and shown separately in Daily Winners only. They are still counted in every other report.
- Daily totals per territory are stored by territory and outlet classification, so both splits can be done.

### 5.3 Callage Summary (special preparation)
Columns: RSM CODE, RSM, ASM CODE, ASM, ASE CODE, ASE, SALES REP CODE, SALES REP TYPE, TERRITORY, SALES REP, ITINERARY PLANNED DAYS, NOD, IPD vs NOD %, SCHEDULE CALLS, CALLS MADE, SC vs CM %, PRODUCTIVE CALLS, UNPRODUCTIVE CALLS, MISSED CALLS, PRODUCTIVITY %, UNPLANNED VISIT COUNT, LINES PER BILL

- **Numeric:** every column from ITINERARY PLANNED DAYS onward
- Steps:
  1. Download Callage filtered to **Report Date**. Keep only **Van Selling** territories and remove the Pre Selling rows.
  2. Download Callage filtered to the **previous working day**. Keep only **Pre Selling** territories and remove the Van Selling rows.
  3. Combine both into one **Prepared Callage** table and save it as `Callage_Prepared_<date>.xlsx` in `inputs/` as well as in the database.
- Reason: pre-sellers take orders the day before and those orders are invoiced on the report day.
- Selling mode comes from the user's Territory → Selling Mode assignment (Step 6).

### 5.4 View Pre-Selling
- Download with SO Status = **Active**, Invoice Status = **Pending**, Date From = Date To = **Report Date**.
- The SFA export is titled **"Sales Order"**. Its header row is row 10. Columns: SO NUMBER, TERRITORY, DISTRIBUTOR, SALES REP, ROUTE, CUSTOMER, PRICING SCHEME, GROSS AMOUNT, DISCOUNT, NET AMOUNT, BATTERY, APP VERSION, GPS LATITUDE, GPS LONGITUDE, CREATED BY, CREATED TAB DATE, CREATED TAB TIME, CREATED SERVER DATE, CREATED SERVER TIME, INVOICE STATUS
- **Numeric:** GROSS AMOUNT, DISCOUNT, NET AMOUNT, BATTERY, GPS LATITUDE, GPS LONGITUDE (strip commas, convert)
- Dates are text like "November 3, 2026" (format `%B %d, %Y`) and times like "7:59 PM".
- **Order Value = SUM(NET AMOUNT)** per TERRITORY. **Order Count = number of distinct CUSTOMER (outlets)** per TERRITORY, following Famulus. (On 3 Nov this equals the distinct SO count.)
- Exclude the national SMMT territories (Colombo / Kandy / Anuradhapura SMMT).
- Only include territories assigned as Pre Selling. Exclude any row whose INVOICE STATUS is not "Pending", as a safety check.
- The values change during the day as orders get invoiced, so the report reflects the moment of download. Store a snapshot for each run with the download timestamp.
- Verified against the 3 Nov export: Puttlam 194,584.50 / 30, Chilaw 175,241.66 / 33, Wennappuwa 66,451.75 / 24.

### 5.5 View Territory
- Download with Status = **Active**. Upsert into the `territories` table and keep a `last_seen` date. Mark territories missing from the latest sync as inactive. Never delete them.

### 5.5a Rep Performance Report (monthly, for report 6.6)
- SFA page: **Rep Performance Report**. The URL and filters are set up by the user like the other pages. Date range: month start → report date (or the whole month at month end).
- The sheet name is `Export`. There is one row per territory + rep (~115 rows, many zeros). **Skip the unlabelled totals row at the bottom**, which contains text numbers like "30,004".
- Columns: TERRITORY, SALES REP, TOTAL CUSTOMERS, SERVED CUSTOMERS, TOTAL BILLS, PRODUTIVE CALLS (sic), BILL DAYS, NO OF SKUs, SOLD SKUs, DISCOUNTED TOTAL SALES, TOTAL RETURNS, ITEM DISCOUNT, FREE ISSUE VALUATION, CASH COLLECTION, CHEQUE COLLECTION, OUTSTANDING, ACHIEVED SALES, ACHIEVED COLLECTION, LPB (LINES PER BILL). All numeric columns go through the text→number conversion.
- **Aggregate by territory**: the same territory can have several reps.
- `PRODUTIVE CALLS` = **Total PC Count** for report 6.6.
- `BILL DAYS` is the length of the period, **not** the days worked. Never use it as days worked.
- `ACHIEVED SALES` is used only in the Reconciliation screen.

### 5.6 History needed
Store daily sales per territory and daily prepared callage per territory. Reports need:
- month-to-date figures (this month)
- last month same day and last month 1 → same day
- cumulative productive calls

If history is missing for a past date, backfill by downloading that date range.

---

## 6. The output reports (5 daily + 1 monthly + Activity Report)

Common rules for all 5 reports:

**Title rows**
- Row 1 (merged, bold, 14pt): title.
- Row 2 (merged): summary line.
- Row 3: blank.
- Row 4: header row (white bold text on **#305496** fill).
- Data starts at row 5. Freeze panes at A5.

**Hierarchy grouping.** Territory rows, followed by subtotal rows in bold:
- `<ASE name>  (ASE Total)`
- `<DTM name>  (DTM Total)`
- `<ASM name>  (ASM Total)`
- `<RSM name>  (RSM Total)`
- `<Region>  (Region Total)`
- `NATIONAL TOTAL` (last row)

Order follows the hierarchy master.

**Number formats.** Money uses `#,##0.00`. Percentages use `0.0%`.

**Outputs for each report.** Excel (styled with openpyxl), PDF (landscape A4, fit to width) and PNG (WhatsApp-ready, readable on a phone, splitting long reports into several images if needed). Files are named `<Report>_<date>.xlsx/.pdf/.png`.

### Notation
- `T` = territory GT monthly target
- `S` = SMMT monthly target
- `NOWD` = number of working days in the month (from the calendar)
- `d` = report date
- `Ach_day` = sale on d
- `Ach_prior` = month-to-date sale before d
- `Ach_mtd` = Ach_prior + Ach_day

### 6.1 Day Report — `Day_Report_<d>.xlsx`
**Title:** `[Prefix — ]Day Report — <d> (<Month YYYY>)` (default name: **Day Report**)

**Summary line:**
> Working Days (NOWD): 24 | Day N of the month | GT Day Target | GT Day Achievement | SMMT Day Target | SMMT Day Achievement | Last Month Same Day (GT, <date>) | Day Variance | Prev. Month (GT, 1–N <month>) | Variance vs Prev. Month

**Columns and formulas:**
| # | Column | Formula |
|---|---|---|
| 1 | Territory | |
| 2 | Monthly Target | T |
| 3 | Day Target GT | `max(T − Ach_prior, 0) ÷ max(NOWD − days_worked, 1)`. `days_worked` = the number of prior dates this month (dates with sales data in the database, before d) on which **this territory** had a sale > 0. A day off or holiday with no sale does not use up a working day. A target that is already achieved gives 0. **Confirmed from the Famulus source code.** |
| 4 | Day Achievement GT | Ach_day |
| 5 | Achievement % | Ach_day ÷ Day Target |
| 6 | Variance from Day Target | Ach_day − Day Target |
| 7 | Last Month Same Day Sale GT | Sale on the same day-of-month last month, clamped to that month's last day (31 Oct → 30 Sep) |
| 8 | Day Variance vs Last Month | Ach_day − col 7 |
| 9 | Calls Made | CALLS MADE from Prepared Callage |
| 10 | Productive Calls | PRODUCTIVE CALLS from Prepared Callage |
| 11 | SMMT Day Target | Same rolling formula as col 3, applied to S and the SMMT sales |
| 12 | SMMT Day Achievement | SMMT sale on d |
| 13 | Achievement % | col 12 ÷ col 11 |
| 14 | SMMT Variance | col 12 − col 11 |
| 15 | Cumulative Day Target GT | Sum of the Day Targets calculated for **each prior data date** this month (each using only the sales before that date) + today's Day Target. E.g. Kaduwela 3 Nov = 83,333.33 (2 Nov) + 85,110.30 (3 Nov) = 168,443.64 ✓ |
| 16 | Cumulative Achievement GT | Ach_mtd |
| 17 | Prev. Month Same-Date Achievement GT | Last month, day 1 → same day-of-month (clamped to last month's last day) |
| 18 | Variance vs Prev. Month | col 16 − col 17 |
| 19 | Cumulative Achievement % | col 16 ÷ col 15 |
| 20 | Cumulative Variance | col 16 − col 15 |
| 21 | Cumulative Productive Calls | Sum of productive calls from month start to d |

- Subtotal rows sum every value column and recompute the % columns from the summed values.
- Division by zero gives 0.
- GT totals in the summary exclude SMMT territories.
- "Day N of the month" in the summary is the calendar day of d.
- Territories with sales but not in the hierarchy go under an **"Unmatched Territories"** group, so totals still reconcile. The run also warns about them.
- If the database is missing data for a prior date, regenerate after backfilling. The report lists "missing dates" in the preview.

**Verification:** for 2026-11-03, the GT Day Achievement must equal **2,318,859.42**. Kaduwela Day Target = (2,000,000 − 42,463) ÷ 23 = **85,110.30**.

### 6.2 Target vs Achievement — `Target_vs_Achievement_<month start>_to_<d>.xlsx`
**Title:** `[Prefix — ]Target vs Achievement Report — <Month YYYY>  (<start> to <d>)`

**Summary line:** GT Target | GT Achievement | SMMT Target | SMMT Achievement

**Columns:**
- Hierarchy
- Monthly Target (T)
- Achievement GT till <d> (Ach_mtd)
- GT Tgt Vs Achieve % (Ach_mtd ÷ T)
- GT Variance (Ach_mtd − T)
- SMMT Target (S)
- Achievement SMMT till <d>
- SMMT Tgt Vs Achieve %
- Balance to be achieved = GT Variance + (SMMT Achievement − S)

### 6.3 Sales Comparison — `Sales_Comparison_<d>_vs_<same day last month>.xlsx`
**Title:** `[Prefix — ]Sales Comparison — <dd Mon YYYY> vs <dd Mon YYYY last month>`

**Summary line:** Day Sale this vs last (Variance) | Cumulative this vs last (Variance) | Hierarchy: <Month> target

**Columns:**
- Territory
- Sale on <d>
- Sale on <same day last month>
- Sales Variance
- Cumulative Sale (1–N this month)
- Cumulative Sale (1–N last month)
- Cumulative Sales Variance

SMMT territories are included in these sale columns: "sale" is each territory's full sale, GT or SMMT. This is why the 1–3 Oct total here (5,085,384) is higher than the Day Report's GT-only figure (4,527,764). The difference is Colombo SMMT's 557,620.

**Comparison date rule (from Famulus):**
- Default = the same day-of-month last month, clamped to the last day of the month.
- If that date has no sales in the database, use the nearest earlier date that does. If there is none, use the earliest available date.
- Cumulative previous = 1st of last month → the comparison date.

**Hierarchy:** use the report month's hierarchy. If it isn't set yet (early in the month, before the NSM's targets arrive), use the most recent earlier month's hierarchy, so this report can still run.

### 6.4 Daily Winners — `Daily_Winners_<d>.xlsx`
**Title:** `[Prefix — ]Daily Winners — <d>`

**Summary line:** Territories with a sale today: N | Winners: M

**Rows:** only territories with a GT sale on d, excluding the national SMMT territories, sorted by Sale Value descending. No subtotal rows.

**Only on competition days** from the Competition Calendar (4.7). Limits come from the round that d belongs to.

**Extra report (optional head): Winners Summary.** Covers the whole competition period. Per territory: total Sale Value, total SMMT Outlet Sale, total Bill Count, and the number of Winning Days. Sorted by Winning Days, then Sale Value.

**Columns:**
- Region, RSM, ASM, DTM, ASE (from the hierarchy; blank if the level doesn't exist)
- Territory
- Selling Mode (Van Selling / Pre Selling)
- Sale Value (Ach_day)
- Sale Value = the day's sale **excluding unticked (SMMT/MRP) outlet categories**
- SMMT Outlet Sale = the day's sale to the unticked outlet categories (shown, not counted)
- Bill Count = `max(PRODUCTIVE CALLS − UNPLANNED VISIT COUNT, 0)` from Prepared Callage (Winners only. Other reports use plain Productive Calls)
- Sale Limit and Bill Limit (from the winner rules for that mode)
- Winner = "Yes" if Sale ≥ Sale Limit **AND** Bills ≥ Bill Limit, else "No"

Highlight "Yes" rows in green.

**Verification for 2026-11-03:** 32 territories, 8 winners. Matara has 106,936 with 18 bills, so it is "No".

### 6.5 Pending Order Value — `Pending_Order_Value_<d>.xlsx`
**Title:** `[Prefix — ]Preselling Pending Order Value — <d>`

**Summary line:** Pre Selling territories with pending orders: N | Total Pending Order Value: X

**Columns:** Territory, Order Value, Order Count. Sorted by value descending, with a TOTAL row at the end.

**Verification for 2026-11-03:** Puttlam 194,584.50 / 30 orders. Total 657,539.77 / 147 orders. Kuliyapitiya and Hingurakgoda in a later export are lower (112,095.31 / 29 and 69,502.55 / 25) because some orders were invoiced between the two downloads. This is expected.

### 6.6 Finalized Target vs Achievement (monthly) — `Finalized_Target_vs_Achievement_<start>_to_<end>.xlsx`
This replaces Famulus's "AI file" plus the manual finishing, in one step.
- Name the file from the **report period**. The October sample was wrongly named with September dates.
- Use a proper sheet name: **"Target vs Achievement"** (the sample's sheet was "eet1").

**Layout**
- Row 1: title.
- Row 2: the first date of the current month merged over B2:F2, and the first date of the previous month over H2.
- Row 3: headers. Freeze panes below the header.

**Columns**
| Col | Header | Formula |
|---|---|---|
| A | Territory | Territory or subtotal label (with label overrides applied) |
| B | Monthly Target | GT target |
| C | Achievement GT til <end date, e.g. 31st October 2026> | Sum of sales_value over the period (all outlet categories) |
| D | GT Tgt Vs Achive % | `=IF(B=0,0,C/B)` |
| E | GT Variance | `=C−B` |
| F | Total PC Count | Sum of PRODUTIVE CALLS from Rep Performance, all reps of the territory |
| G | AVG PC Count | `=IF(days=0,0,F/days)` (see rule below) |
| H | Achievement GT til <last day of previous month> | Previous month's GT achievement from the database |
| I | compare with <Mon> Month | `=C−H` |

**AVG PC Count rule (confirmed)**
- days worked = for each rep of the territory, count the distinct dates in the month with productive_calls > 0 in the daily callage; then add the counts across all reps of the territory.
- This handles rep changes inside a month, e.g. Kirindiwela: Dineth 2 + Tharusha 7 = 9.
- Subtotal rows use **sum of Total PC ÷ sum of days worked** of the territories below. Never average the averages.
- Keep a hidden helper sheet **"Days Worked"** showing the days per territory and per rep, for auditing.

**Other rules**
- **Subtotals** (ASE, DTM, ASM, RSM, Region, National) are always Excel `SUM` formulas; never hard-code them. Keep the target file's row order.
- **SMMT territories** (Colombo, Gampaha, Kandy, Anuradhapura(SMMT)) are listed with their PC count only and 0 in the GT columns. SMMT achievement and balance columns are dropped from this report.
- Rounding to 2 decimals.

**Verification (October 2026)**
- National GT achievement = **60,736,895.79**, SMMT = **9,968,055.13**, GT 48.7%.
- AVG PC: Chilaw 632 ÷ 28 = 22.6; Puttlam 499 ÷ 29 = 17.2; Dambulla 522 ÷ 26 = 20.1; Gampaha 245 ÷ 20 = 12.3; Kaduwela 222 ÷ 16 = 13.9; Kirindiwela 130 ÷ 9 = 14.4; Kegalle 158 ÷ 14 = 11.3; ASM Milan – North Western 4,103 ÷ 227 = 18.1.

### 6.7 Activity Report — `Hydra_Activity_<from>_to_<to>.xlsx/.pdf`
The contents are described in 4.10. Built from the `runs`, `run_steps`, `reports`, `sends`, `audit` and `logs` tables.

---

## 7. SQLite schema (minimum)

| Table | Columns |
|---|---|
| `settings` | key, value |
| `page_profiles` | id, name, url, filters_json, date_rules_json |
| `territories` | id, sfa_name, region, area, supervisor_area, channel, status, selling_mode, hierarchy_name, is_smmt, last_seen |
| `hierarchy_nodes` | id, month, parent_id, level (region/rsm/asm/dtm/ase/territory), name, sort_order, is_vacant |
| `targets` | month, node_id (territory), sfa_territory_id, is_smmt, gt_target, smmt_target, notes |
| `target_months` | month, status (draft/locked), expected_national_gt, expected_national_smmt |
| `target_audit` | ts, month, node_id, field, old_value, new_value |
| `calendar` | date, is_working, note |
| `daily_sales` | date, territory, sale_value, bill_count, smmt_value |
| `sales_lines` | raw cleaned SKU rows, optional, for drill-down |
| `daily_callage` | date, territory, selling_mode, source_date, calls_made, productive_calls, plus the other callage columns |
| `preselling_orders` | run_id, downloaded_at, date, territory, so_number, customer, gross_amount, discount, net_amount, invoice_status |
| `runs` | id, trigger, started_at, ended_at, status, report_date, mb_used, error |
| `run_steps` | run_id, step, status, started_at, ended_at, mb_used, message |
| `reports` | id, run_id, report_type, report_date, xlsx_path, pdf_path, png_paths, status, sent_at |
| `whatsapp_recipients` | id, name, type, reports_json, active |
| `logs` | ts, level, run_id, message |
| `competition_rounds` | id, month, name, colour, van_sale_limit, van_bill_limit, pre_sale_limit, pre_bill_limit |
| `competition_days` | round_id, date |
| `outlet_category_config` | category_key, label, pricing_scheme, include_in_competition |
| `rep_perf_uploads` / `rep_perf_lines` | month, period_from, period_to, territory, sales_rep, all columns of 5.5a |
| `territory_aliases` | sfa_name, hierarchy_name |
| `rep_aliases` | variant_name, canonical_name, sales_rep_code |
| `label_overrides` | month, node_id, original_label, display_label |
| `sends` | report_id, recipient, sent_at, status, error |
| `users` | username, role, pbkdf2_hash, salt, iterations, active |
| `audit` | ts, user, action, details |
| Indexes | On date, territory and upload/run ids (the database grows ~12 MB a month) |

---

## 8. Robustness requirements
- Every SFA step has a timeout and up to 2 retries. If the session expires, re-login automatically.
- Wait for the SFA table to finish loading before clicking the Excel icon, and verify that the downloaded file is not empty and that the dates in its row 8 match the requested dates.
- Only one run can happen at a time. If a schedule fires during a manual run, queue it or skip it with a log entry.
- Stop must be honoured within ~2 seconds: check the flag between steps and close the browsers.
- Never send to WhatsApp without approval unless "Auto-send when unattended" is ON.
- All paths, URLs and filters come from settings. Nothing about Lakmee is hard-coded except defaults.
- Back up the database daily to `<save root>/backups/`.

---

## 9. Delivery rules for the AI assistant
- For every code file delivered, state **exactly where it goes** in the folder structure above.
- Provide a **GitHub commit message** with every code update.
- Build in phases:
  1. Skeleton + settings + wizard UI
  2. SFA login + generic downloader
  3. Cleaner + database
  4. Callage preparation
  5. The 5 daily reports + Finalized monthly report + Activity Report (Excel)
  6. PDF/PNG render + preview pop-up
  7. WhatsApp
  8. Scheduler + worker + tray
  9. Activity Monitor + data meter + logs + notifications
  10. Installer
- Verify every report against the sample outputs for 2026-11-03 before moving on.

---

## 10. Open items (to be filled in)
1. ~~View Pre-Selling export sample~~ (done, see 5.4).
2. ~~Hierarchy & targets source~~ (done: in-app Targets Editor, see 4.6).
3. ~~Day Target rule~~ (done, see 6.1 col 3: derived from the NSM's monthly target).
4. ~~"Previous day" for Pre Selling callage~~ (done: the previous working day from the Calendar, e.g. Monday → Saturday; skips Sundays and holidays).

5. ~~SMMT definition, Bill Count, Order Count, comparison date, cumulative target~~ (done: confirmed from the Famulus source code, see 5.2, 6.1, 6.3, 6.4, 5.4).
6. ~~Report date for each schedule slot~~ (done: a Today / Yesterday setting per slot).
8. **SMMT worked days for AVG PC.** Callage shows 0 productive calls for SMMT reps. Default: show "—" for SMMT AVG PC. **[To confirm]**
9. **Do SMMT PC counts roll into parent subtotals?** Default: no. The sample is inconsistent (Kandy SMMT was added to DTM Suganta). **[To confirm]**
10. **National and some RSM/Region rows** were missing from the Finalized sample. Default: include all levels. **[To confirm]**
11. **Official achievement source** when the database and SFA Rep Performance differ. Default: the database (daily SKU). **[To confirm]**
12. **The "new report generation process"** Binusha mentioned. Assumed to be the Finalized Target vs Achievement (6.6). **[To confirm, or add the new one]**
7. Territory with no Van/Pre assignment: treat it as Van Selling and show a warning in the preview (default).
