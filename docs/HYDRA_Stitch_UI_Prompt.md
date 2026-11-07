# HYDRA — Stitch AI UI Prompt

> **How to use:** paste **Part A (Design System)** first, together with the Hydra logo image. Then paste the screens in Part B one or two at a time, always starting with "Using the Hydra design system above, design…". Stitch gives better results with a few screens per prompt than with everything at once.

---

## PART A — Design system (paste first, with the logo)

Design a **Windows desktop application UI** (1440 × 900, also responsive down to 1280 × 720) called **HYDRA**, a management report automation app for Lakmee Exports Lanka (a Sri Lankan FMCG company). It logs into the company's SFA web system, downloads sales Excel reports, generates management reports (Excel / PDF / PNG) and sends them to WhatsApp groups after approval. Users are an IT support engineer and sales management. The feel should be **premium, calm, classical-meets-modern**: a mythological Greek emblem brand on a sleek, data-dense professional dashboard.

**Logo:** I am uploading the Hydra logo. It is a five-headed Hydra serpent in vintage engraved line art inside a circular Greek-key border, currently **maroon ink on cream**.
- **Recolour the logo to match this theme.**
  - On metallic black and metallic cherry alloy red surfaces (sidebar, splash, login, modal headers): use **liquid mercury / polished silver line art**. A faint cherry inner glow is optional on black.
  - On off-white surfaces: use **metallic cherry alloy red line art**, a deep metallic cherry. This is close to the logo's current maroon, so it only needs a richer, slightly glossy cherry.
  - The border ring can carry a thin mercury highlight.
- If a full recolour looks better, adapt the whole logo (lines, border and background) to the palette below. Keep the engraved line style and the five heads.
- Provide: the full emblem, a compact emblem for the sidebar (40 px), and a simplified icon version (heads only, no border) for 16–32 px.

**Colour palette: Metallic Cherry Alloy Red, Metallic Mercury, Metallic Black, Off-White.**
- Metal effects come from subtle linear gradients, a soft specular sheen and a faint brushed-metal texture. They should feel like anodised cherry-red aluminium, liquid mercury/chrome and polished gunmetal black, never flat or neon.
- **Metallic black** is the frame of the app (sidebar, splash, login, dark panels). **Metallic metallic cherry alloy red red** is the accent and action colour: a rich, glossy anodised cherry red, redder and brighter than maroon. **Mercury** is the chrome detail. **Off-white** is the calm reading surface.

| Token | Use | Value / gradient |
|---|---|---|
| `black-900` | **Metallic black**: sidebar, splash and login background, title bars | #0B0C0E → #1C1D21 (vertical gradient, brushed-gunmetal texture, a soft diagonal specular streak #2E3036) |
| `black-700` | Raised metallic black: sidebar hover, dark cards, the log viewer, Stop/destructive buttons | #1A1B1F → #2A2C31, with a 1 px top highlight #3D4047 |
| `cherry-900` | Modal header bars, calendar Sunday cells, deep red accents | #5A0C18 → #7E1324 (vertical gradient, brushed-metal texture) |
| `cherry-700` | Active nav pill, cherry cards on black | #8E1426 → #AC1A30 |
| `cherry-500` | **Primary buttons**, links, active tabs, key chart series | #B3172F → #D42A45, with a 1 px top highlight #EE7486 and a soft specular band (glossy metallic cherry alloy red red) |
| `mercury-100` | Table header fill, secondary surfaces, chips | #EDEFF2 → #DDE1E6 (soft chrome sheen) |
| `mercury-300` | Borders, dividers, input outlines, secondary buttons | #C4C9D0 → #A9AFB8 |
| `mercury-500` | Icons, sidebar text/icons on metallic black, toggles off, secondary chart series | #8E959F → #C9CED5 (liquid-silver gradient) |
| `offwhite` | Main content background, cards, modal bodies | #F7F5F0 (cards #FBFAF7) |
| `ink` | Body text on off-white | #1F1A1C |
| `text-on-cherry` | Text on cherry | #F3F1EC, with secondary text in mercury #C9CED5 |
| Success | | #2F8F6B (muted teal-green) |
| Warning | | #C9962E (antique gold) |
| Error | | #F0642E (orange-scarlet). It must look clearly different from the cherry red brand colour, and always comes with an ⚠ / ✕ icon and the word "Error" or "Failed". |
| Info | | #4F7C9A (steel blue) |

**Layout:**
- A fixed **left sidebar** (260 px, collapsible to 72 px icons) in **metallic black** (black-900), with a thin metallic cherry alloy red edge line on its right border.
  - The mercury-silver Hydra emblem and the "HYDRA" wordmark sit at the top.
  - Navigation text and icons are mercury.
  - The active item has a metallic cherry alloy red pill (cherry-500 gradient) with a thin mercury edge highlight. Hover uses black-700.
- The main content area is **off-white**, holding cards with 12 px radius, a soft shadow and a 1 px mercury border.
- A **top bar** (64 px, off-white with a mercury bottom border) shows:
  - page title, breadcrumb
  - a global "⚡ Generate Reports Now" button (metallic cherry alloy red)
  - a "⛔ Stop All" button (metallic black-700 with a scarlet icon)
  - the notification bell with a cherry unread badge
  - SFA and WhatsApp connection status chips (teal dot = connected)
  - a user avatar menu (profile, change password, logout)
- A **bottom status strip** (28 px, mercury-100) shows: the next scheduled run countdown, data used today (MB), worker status (Running / Paused / Stopped), and the app version.

**Typography:**
- **Cinzel** (or a similar classical Greek serif) for the wordmark, page titles and report titles only.
- **Inter** for all UI text.
- **JetBrains Mono** for logs and codes.
- Numbers in tables are right-aligned with tabular figures and thousand separators, e.g. 2,318,859.42.

**Components:**
- Primary buttons: metallic cherry alloy red gradient with a glossy sheen and a darker pressed state.
- Secondary buttons: mercury chrome gradient with ink text.
- Destructive buttons: metallic black with a scarlet icon.
- Inputs and dropdowns: off-white with mercury outlines and **cherry focus rings**.
- Toggles: cherry when on, mercury when off.
- Data tables: sticky header with a mercury chrome fill, zebra rows (#F2F0EA), hover row highlight, and subtotal rows bold with a light cherry tint (#F6E6E9).
- Also: status chips, tabs, stepper, toasts (bottom-right), modals (off-white body, cherry header bar with the mercury logo), empty states (engraved-style line illustrations in cherry), skeleton loaders, and progress rings (cherry arc on a mercury track).
- Icons: thin line icons (Lucide style), cherry on off-white and mercury on cherry.
- Decoration: a very subtle Greek-key border motif in mercury on modal headers and the login screen. Keep it light and never distracting.

**Light/Dark:** the default is described above (metallic black + cherry chrome, off-white content). Also provide a **"full dark" variant**: metallic black (#111215) content background, #1E2024 cards with mercury borders, off-white text, and cherry and mercury accents.

---

## PART B — Screens (paste one or two at a time)

### 1. Splash screen
- Centred mercury-silver Hydra emblem on **metallic black**, with a soft cherry radial glow behind it and a slow sheen animation across the metal.
- "HYDRA" in Cinzel and the tagline "Management Report Automation".
- A thin mercury progress bar with a cherry fill with status text ("Starting worker…", "Checking SFA connection…") and the version number at the bottom.

### 2. Login
- A split layout. **Left 55%:** metallic black with a deep cherry gradient glow from the bottom-left, the large mercury emblem, the wordmark, and a short line "Watching every territory. Reporting every head."
- **Right 45%:** an off-white card containing:
  - Username and Password fields (show/hide eye icon), "Remember me", and a **Sign in** button (metallic cherry alloy red).
  - An error state: "Incorrect username or password".
  - The role shown after sign-in: superadmin / admin / user.
  - Footer: licence status chip ("Licensed until 30 Nov 2026") and version.

### 3. First-run Setup Wizard (one screen design, with a vertical stepper)
The stepper sits on the left with 13 steps, each with a check mark when done. The right side shows the step content, with Back / Next / Save & Exit buttons.
1. **Welcome:** emblem, description, "Start Setup".
2. **SFA Connection:** SFA URL, Username, Password, Browser (Chromium / Edge / Chrome) as cards, a Headless toggle, and a **Test Login** button with ✅ / ❌ result states.
3. **Page URLs:** a table with rows for Outlet Wise SKU Sales, Callage Summary, View Pre-Selling, View Territory and Rep Performance Report. Columns: editable URL and a "Test" button.
4. **Filter Setup:** tabs per page. A grid of dropdowns that mirrors the SFA filter form (SFA, Channel, Region, Area, Supervisor Area, Territory, Distributor, Sales Rep, RSM, ASM, ASE, Product Category, Sub Category, Product, Report Type, Invoice Status, SO Status, Status). Each date field has a "Date rule" dropdown: Report Date / Previous Working Day / Month Start → Report Date / Last Month Same Day / Fixed. Include a **"Learn Filters from SFA"** button with a loading state.
5. **Territory Sync:** "Sync Active Territories" button, results table, and new / removed counts.
6. **Selling Mode:** a territory table with a Van / Pre segmented toggle on each row, bulk-select actions, and a search box.
7. **Targets:** choices: Import NSM Target Workbook, Import from Famulus, or Open Targets Editor.
8. **Working & Competition Calendar:** a compact version of screen 10.
9. **Report Rules:** winner limits per selling mode, outlet category eligibility table, and excluded SMMT territories (chips).
10. **Save Location:** folder picker and folder-structure preview.
11. **WhatsApp Link:** QR code panel, then a linked state, then a recipients list.
12. **Schedule:** run-time slots (see screen 11).
13. **Finish:** settings summary cards and "Run first test now".

### 4. Dashboard
- **Row 1: status cards.**
  - SFA Connection (Connected, last login time)
  - WhatsApp (Linked as +94…)
  - Next Run (countdown + report date Today/Yesterday)
  - Last Run (✅ 5 reports, 3 min 12 s)
  - Data Used (today / this month, small ring gauge)
- **Row 2: KPI strip for the latest report date.**
  - GT Day Target vs Achievement with %
  - MTD Achievement % (progress bar)
  - Winners today (8 / 32)
  - Pending Order Value (657,540)
  - Competition: "Round 2 · Day 4 of 7"
- **Row 3, left:** today's runs timeline (vertical, coloured dots per status).
- **Row 3, right:** a mini chart of national GT daily achievement vs day target for this month.
- Large buttons: **⚡ Generate Reports Now**, **⏸ Pause Schedule**, **⛔ Stop All**.
- Banners when needed:
  - "Targets for December 2026 not set — Open Targets Editor" (antique gold warning)
  - "WhatsApp not linked" (scarlet, with icon)

### 5. Run Center (live run)
- A header with a Report Date picker (default Today), report checkboxes (Day Report, Target vs Achievement, Sales Comparison, Daily Winners, Pending Order Value, Finalized Target vs Achievement), and a **Start** button.
- **Live step list:** a vertical stepper with 13 steps (Login → Download SKU → Download Callage today → Download Callage previous working day → Prepare & merge Callage → Download Pre-Selling → Convert & save → Build reports → Render → Preview → Send). Each step shows a status icon (pending / spinning / ✅ / ❌), elapsed time and MB.
- An overall progress ring.
- **Stop** and **Retry failed step** buttons.
- **Bottom: live log panel** (monospace, auto-scroll, level colours) with a **📋 Copy Log** button.

### 6. Report Preview & Send pop-up (modal, large: 90% of the window)
- A metallic cherry alloy red header bar with the mercury emblem and the title "Review reports — 03 Nov 2026".
- **Left column (320 px): "Select reports to send"**
  - A list of generated reports. Each row has a checkbox, a thumbnail, the name and date, a status chip (Ready / Failed / Not a competition day), and a format segmented control (PNG / PDF / Both).
  - "Select all / Clear all" and the counter "3 of 5 selected".
  - Failed rows are greyed out and disabled.
- **Centre: large preview** of the selected report image, with zoom, fit to width, page arrows ("Image 1 of 2") and an "Open PDF" link.
- **Bottom: recipients** as checkbox chips (WhatsApp groups and contacts) and an editable caption field.
- **Footer buttons:** **✅ Approve & Send Selected** (primary metallic cherry alloy red, disabled when nothing is selected), **💾 Save** (mercury chrome), **⛔ Stop** (metallic black with a scarlet icon), and a **🔄 Refresh** icon button.
- **Sending state:** per-message progress list (✓ sent / ✗ failed with Retry).

### 7. Reports (history)
- Filters: date range, report type, status (Generated / Approved / Sent / Saved only / Failed).
- Table: Date, Report, Run time, Trigger, Status chip, Sent to, and actions (Open Excel, Open PDF, View PNG, Resend, Open folder).
- A right-side drawer previews the selected report.

### 8. Territories
- Toolbar: search, region filter, "Sync now", and "Last synced: 05 Nov 2026 09:00".
- Table: Territory, Region, Area, Supervisor Area, Channel, Status chip, Selling Mode toggle (Van / Pre), GT / SMMT badge, Mapped hierarchy name, Last seen.
- After a sync, a "Changes" panel shows: new, inactive and renamed territories.

### 9. Hierarchy & Targets Editor
- **Top bar:**
  - Month selector (◀ November 2026 ▶) and a status chip (Draft / Locked 🔒)
  - Buttons: Import NSM Workbook, Import from Famulus, Copy Previous Month, Export Edit Template, Save, Lock Month
- **Left panel (35%):** collapsible tree National → Region → RSM → ASM → DTM → ASE → Territory.
  - Each node shows its rolled-up GT / SMMT totals.
  - Badges: Van / Pre, SMMT, Vacant, red flag, ⚠ unmapped.
  - Drag-and-drop handles and a right-click menu.
- **Right panel (65%):** a spreadsheet-like grid.
  - Columns: Sort, Territory, SFA Territory (dropdown), Distributor, CSR, Operating / Vacant, Is SMMT, GT Target, SMMT Target, Last month target, Last month achievement, Notes.
  - Inline editing, with a bulk-action bar (Set value, Increase by %, Distribute total).
- **Footer:** Grand total GT and SMMT, plus an "Expected national target" check (teal tick or scarlet mismatch).
- **Validation drawer:** missing territories, unmapped, duplicates, subtotal mismatches.
- **History drawer:** an audit list.

### 10. Calendar & Competition
Recreate the NSM's competition calendar look in the Hydra theme:
- **Title band:** "COMPETITION CALENDAR – NOVEMBER 2026 (24 – W/Days)".
- **Grid:** columns MON TUE WED THU FRI SAT **SUN**, plus a final **"Competition Day"** column showing each round's day count, merged vertically across that round's weeks.
- **Cell styles:**
  - Working day: off-white
  - Sunday: solid metallic cherry alloy red cell, off-white number
  - Holiday: cherry number on an off-white cell with a small label, e.g. "24 Poya"
  - Round 1: mercury/silver fill
  - Round 2: soft rose-cherry tint fill (#F2D9DE)
- **Example data:**
  - Round 1 = 3, 4, 5, 6, 7, 9, 10, 11 (8 days)
  - Round 2 = 13, 14, 16, 17, 18, 19, 20 (7 days)
- **Right panel: "Rounds"**
  - A list of rounds with colour swatch, name, dates, day count, and limits (Van 100,000 / 20 bills, Pre 125,000 / 30 bills).
  - Buttons: "+ Add Round", "Select days by dragging", Import NSM Calendar (Excel / image), Export as PNG, Copy previous month.
- **Bottom:** NOWD 24 (auto), with a "Manual override" toggle.

### 11. Schedule
- A list of schedule slots, as cards.
- **Each card has:**
  - Time (e.g. 10:00)
  - **Report date** segmented control **Today / Yesterday**
  - Report checkboxes
  - Day-of-week pills (M T W T F S S)
  - Enabled toggle
  - "Auto-send when unattended" toggle (off by default, with a warning tooltip)
- "+ Add time" button.
- **Monthly jobs section:** Finalized Target vs Achievement (last working day), Rep Performance download, and Territory sync.
- **Activity Report schedule:** e.g. every Monday 08:30, last 7 days.
- Side panel: "Next 5 runs" preview list. Pause all / Resume all.

### 12. WhatsApp
- **Link card:**
  - Not linked state: a "Link WhatsApp" button.
  - Linking state: a large QR code with "Open WhatsApp → Linked devices → Scan" instructions.
  - Linked state: the number, a teal chip, and Unlink.
- **Recipients table:** Name, Type (Group / Contact), Default reports (chips), Active toggle, Test message button.
- **Send history table:** time, report, recipient, status.

### 13. Reconciliation
- Month picker and tolerance input (1%).
- Table: Territory, Hydra Achievement, SFA Rep Performance Achieved Sales, Difference, Difference %, Possible cause. Rows outside the tolerance are highlighted in a gold tint.
- Toggle "Only differences" and an Export button.
- A side card explains possible causes (returns netted, reassigned reps, missing daily downloads with their dates).

### 14. Aliases & Label Overrides (tabs)
- **Territory Aliases:** SFA name ↔ hierarchy name, with fuzzy suggestions.
- **Rep Aliases:** variant name, canonical name, rep code.
- **Label Overrides:** month, original label, display label.
- **Excluded territories:** chips such as Test Territory, Lakmee TERRITORY, Sathosa.

### 15. Activity Monitor
- Tabs: **Run History · Data Meter · Health · Activity Reports**.
- **Run History:** an expandable table (start, end, trigger, report date, duration, status, reports, MB). Expanding a row shows its step timeline and log excerpt.
- **Data Meter:**
  - A large ring gauge for today (MB), a bar chart of MB per day for the last 30 days, and a donut by source (SFA downloads, WhatsApp uploads, page loads).
  - A monthly cap setting with a warning bar.
- **Health:** cards for last SFA login, last WhatsApp send, database size, free disk space, and worker uptime.
- **Activity Reports:**
  - A period picker (Today, Yesterday, Last 7 days, This month, Last month, Custom range) and a **Generate Activity Report** button.
  - The preview shows:
    - KPI tiles: total runs, success rate %, failed, stopped, average duration, reports generated, reports sent, WhatsApp messages sent/failed, data used
    - A runs-per-day stacked bar chart and a data-per-day line chart
    - A per-report table, a failures-by-cause table, and a user-actions table
  - Buttons: Export Excel, Export PDF, Send to WhatsApp (opens the Preview & Send pop-up).

### 16. Notifications
- **Bell dropdown panel (from the top bar):** a list grouped by Today / Earlier. Each item has an icon by type:
  - run started
  - run finished ("5 reports generated · 2.3 MB")
  - approval needed (with an action button "Review")
  - sent to WhatsApp
  - failure (scarlet, with "Open log")
  - targets missing, competition day starting
- "Mark all as read".
- **Full Notifications page:** filters by type and date, a search box, and a settings link.
- **Toast designs (bottom-right):** success, warning, error and info, with auto-dismiss and an action link.
- A **Windows toast** mock-up using the small Hydra icon.

### 17. Logs
- Toolbar: run selector, level filter chips (Info / Warning / Error / Debug), search box, date range, **📋 Copy Log** (with a "Copied!" confirmation), Export .txt, and a Clear view button.
- Main area: a monospace log viewer on metallic black (black-700), with off-white text, mercury for info, antique gold for warnings and scarlet for errors. It shows timestamps and run IDs, and has line wrapping and an auto-scroll toggle.

### 18. Settings
A left sub-navigation lists these sections, with a form on the right and Save / Cancel buttons.
- **General:** language, start with Windows, minimise to tray, theme (Black & Cherry chrome / Full dark).
- **SFA Connection:** URL, username, password, browser, headless, Test Login.
- **Pages & Filters:** opens the filter setup.
- **Save Location & Backups:** folder, daily backup toggle, backup now, restore.
- **Reports:**
  - Title prefix (empty by default), editable report display names, number formats, PNG size
  - Winner limits, outlet categories, excluded SMMT territories
- **Schedule & Approval:** approval timeout minutes, auto-send when unattended.
- **WhatsApp:** link status shortcut.
- **Notifications:** toggles per notification type, Windows toasts on/off, sound.
- **Data Meter:** monthly cap.
- **Users & Roles** (superadmin only): users table (username, role, active, last login), add/edit user, reset password, import from Famulus.
- **Licence:** status, expiry, apply licence key.
- **Advanced:** timeouts, retries, log retention days, open the app data folder.

### 19. About
- An off-white card centred on a metallic black background with a cherry glow:
  - Large cherry-on-off-white Hydra emblem, "HYDRA" in Cinzel, and the tagline.
  - Version, build date, licence status and expiry.
  - "Developed by Binusha Liyanage — IT Department, Lakmee Exports Lanka".
  - Buttons: User Guide, Check for updates, View licences.
  - A database info panel: path, size, months stored.
- A small myth note: "Hydra — the many-headed serpent: one body, many heads. One engine, many reports."

### 20. Dialogs & states (design these too)
- **Stop All confirmation:** "Stop all processing? Running downloads will be cancelled and the scheduler paused until you resume." Buttons: Stop / Cancel.
- **Replace existing data:** "Data for 03 Nov 2026 already exists. Replace?"
- **Wrong month warning:** "This file looks like October but November is selected."
- **Empty states:** no reports yet, WhatsApp not linked, no targets for this month.
- **Error page:** "SFA login failed", with Retry and Open Settings.
- **Loading skeletons** for tables and charts.
