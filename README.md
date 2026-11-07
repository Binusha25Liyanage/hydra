# Hydra — Work Automation Suite

Hydra is a desktop app for Lakmee Exports Lanka that automates each person's work. It signs in to SalesPro SFA with that person's own account, runs the reports and processes their role needs, and delivers the results (Excel, PDF, PNG, WhatsApp) once someone approves them. The first role built is the management sales reports: Day Report, Target vs Achievement, Sales Comparison, Daily Winners, Pending Orders and Finalized Target vs Achievement.

**This build is Phase 1 (Foundation):** the splash screen, users and roles, the setup wizard (SFA connection, page URLs, save location), the app shell, and the Dashboard, Notifications, Logs, Settings and About screens.

## Run it from source (Windows 10/11)

```bat
cd D:\projects\hydra
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
python main.py
```

- To get DevTools for debugging, run `set HYDRA_DEBUG=1` before `python main.py`.
- `run_hydra.bat` does the activate-and-start steps for you.

## Test without touching the real SFA

```bat
python tools\mock_sfa_server.py
```

In the wizard, use SFA URL `http://127.0.0.1:8765`, username `binusha` and password `Secret123`.

Automated tests: `python -m pytest -q tests`

## How the splash screen works

The splash screen has two modes.

**First run** (no admin account yet, or setup not finished):
- The real work is small: create the database and folders.
- The bar runs smoothly just for the look.
- It then opens "Create the administrator", followed by the Setup Wizard.

**Daily** (setup finished): the bar follows the real checks, weighted by how long each takes.

| Step | What it checks | If it fails |
|---|---|---|
| Configuration | SFA URL, username and password are saved | warning |
| Database | `PRAGMA quick_check`, size, schema | **stops Hydra** (Retry / Copy log) |
| Save location | the folder is writable and has more than 1 GB free | warning |
| Internet | the SFA host first, then 8.8.8.8 / 1.1.1.1 | warning |
| SFA server | HTTP response and latency | warning (the SFA sign-in is skipped) |
| **SFA sign-in** (about half the bar) | a live Playwright login: opening browser → opening SFA → saved session or entering credentials → verifying "Welcome, <name>" | warning, plus a notification |
| WhatsApp | the link status (linking arrives in Phase 9) | warning |
| Schedule | the scheduled times | info |
| Targets | this month's targets (from Phase 5) | warning |

How the SFA sign-in behaves:
- It saves the SFA session (cookies), so later runs that day skip the login form.
- If the SFA sign-in takes more than 4 seconds, a **Skip SFA check** button appears.
- Warnings never block Hydra. They appear on the Dashboard ("Startup check") and in Notifications.

## Where things are

- **App data:** `%LOCALAPPDATA%\Hydra\` contains `data\hydra.db`, `logs\hydra.log`, `profiles\` and `data\sfa_session.json`.
- **SFA password:** stored in Windows Credential Manager under "Hydra".
- **Reports:** in the folder you choose in the wizard (Save Location).

## Project layout

```
hydra/
├── main.py                 entry point (single instance, logging, pywebview window)
├── requirements.txt
├── run_hydra.bat
├── app/
│   ├── api.py              JS ⇄ Python bridge (every screen calls these methods)
│   ├── auth.py             users, roles, PBKDF2 passwords, remember-me, lockout
│   ├── db.py               SQLite + versioned migrations
│   ├── logging_setup.py    rotating file + database + memory logs
│   ├── net.py              internet / SFA reachability
│   ├── notify.py           in-app notifications
│   ├── paths.py            data folders
│   ├── settings.py         settings + Credential Manager secrets + page URLs
│   ├── startup.py          splash screen sequence (first_run / daily)
│   ├── version.py
│   ├── sfa/login.py        Playwright SFA sign-in + page checker
│   └── whatsapp/status.py  link status (full WhatsApp in Phase 9)
├── ui/
│   ├── splash.html  login.html  wizard.html  app.html
│   ├── css/hydra.css (design system)  css/shell.css (app layout)
│   ├── js/bridge.js  splash.js  wizard.js  app.js  pages.js
│   └── assets/img (logos, icon)  assets/fonts (bundled, offline)
├── tools/mock_sfa_server.py
└── tests/test_phase1.py
```
