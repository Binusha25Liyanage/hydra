"""SQLite database: one file, versioned migrations, one connection per thread.

Later phases add their tables as new entries in MIGRATIONS — never edit an
existing migration once it has shipped.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime

from . import paths

_local = threading.local()
_init_lock = threading.Lock()
_initialised = False

MIGRATIONS: list[tuple[int, str]] = [
    (1, """
    CREATE TABLE settings (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE users (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        username     TEXT NOT NULL UNIQUE COLLATE NOCASE,
        display_name TEXT NOT NULL DEFAULT '',
        role         TEXT NOT NULL CHECK (role IN ('superadmin','admin','user')),
        pw_hash      TEXT NOT NULL,
        salt         TEXT NOT NULL,
        iterations   INTEGER NOT NULL,
        active       INTEGER NOT NULL DEFAULT 1,
        failed_count INTEGER NOT NULL DEFAULT 0,
        locked_until TEXT,
        created_at   TEXT NOT NULL,
        last_login   TEXT
    );

    CREATE TABLE remember_tokens (
        token_hash TEXT PRIMARY KEY,
        user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at TEXT NOT NULL
    );

    CREATE TABLE audit (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        ts       TEXT NOT NULL,
        username TEXT,
        action   TEXT NOT NULL,
        details  TEXT
    );
    CREATE INDEX ix_audit_ts ON audit(ts);

    CREATE TABLE logs (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        ts      TEXT NOT NULL,
        level   TEXT NOT NULL,
        source  TEXT NOT NULL,
        run_id  INTEGER,
        message TEXT NOT NULL
    );
    CREATE INDEX ix_logs_ts ON logs(ts);
    CREATE INDEX ix_logs_run ON logs(run_id);

    CREATE TABLE notifications (
        id     INTEGER PRIMARY KEY AUTOINCREMENT,
        ts     TEXT NOT NULL,
        kind   TEXT NOT NULL,
        level  TEXT NOT NULL CHECK (level IN ('info','success','warning','error')),
        title  TEXT NOT NULL,
        body   TEXT,
        action TEXT,
        read   INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX ix_notif_ts ON notifications(ts);

    CREATE TABLE page_profiles (
        key             TEXT PRIMARY KEY,
        name            TEXT NOT NULL,
        url             TEXT NOT NULL,
        filters_json    TEXT NOT NULL DEFAULT '{}',
        date_rules_json TEXT NOT NULL DEFAULT '{}',
        updated_at      TEXT NOT NULL
    );

    CREATE TABLE startup_history (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ts          TEXT NOT NULL,
        mode        TEXT NOT NULL,
        duration_ms INTEGER NOT NULL,
        result      TEXT NOT NULL,
        steps_json  TEXT NOT NULL
    );
    """),
    (2, """
    -- Every SFA Excel file Hydra reads (downloaded automatically or imported by hand)
    CREATE TABLE imports (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        kind          TEXT NOT NULL,          -- sku | callage | sales_order | rep_performance
        file_name     TEXT NOT NULL,
        sha256        TEXT NOT NULL,
        title         TEXT,
        period_from   TEXT,
        period_to     TEXT,
        generated_at  TEXT,
        rows          INTEGER NOT NULL,
        check_field   TEXT,
        check_total   REAL,
        file_total    REAL,
        meta_json     TEXT NOT NULL DEFAULT '{}',
        warnings_json TEXT NOT NULL DEFAULT '[]',
        source        TEXT NOT NULL DEFAULT 'manual',   -- manual | auto
        run_id        INTEGER,
        imported_at   TEXT NOT NULL,
        imported_by   TEXT,
        status        TEXT NOT NULL DEFAULT 'active'    -- active | replaced
    );
    CREATE INDEX ix_imports_kind ON imports(kind, period_from);
    CREATE INDEX ix_imports_sha ON imports(sha256);

    CREATE TABLE sku_lines (
        import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
        date TEXT, rsm TEXT, asm TEXT, ase TEXT, territory TEXT, distributor TEXT,
        sales_rep_code TEXT, sales_rep_type TEXT, sales_rep_model TEXT, sales_rep TEXT,
        outlet_code TEXT, outlet_classification TEXT, outlet TEXT, route_code TEXT, route TEXT,
        invoice_no TEXT, category TEXT, brand TEXT, product_code TEXT, product TEXT,
        wholesale_price REAL, mrp REAL, units REAL, sales_value REAL, sales_volume_mt REAL
    );
    CREATE INDEX ix_sku_date_terr ON sku_lines(date, territory);
    CREATE INDEX ix_sku_import ON sku_lines(import_id);

    CREATE TABLE callage_lines (
        import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
        date TEXT NOT NULL,
        rsm_code TEXT, rsm TEXT, asm_code TEXT, asm TEXT, ase_code TEXT, ase TEXT,
        sales_rep_code TEXT, sales_rep_type TEXT, territory TEXT, sales_rep TEXT,
        ipd REAL, nod REAL, ipd_nod_pct REAL, schedule_calls REAL, calls_made REAL, sc_cm_pct REAL,
        productive_calls REAL, unproductive_calls REAL, missed_calls REAL, productivity_pct REAL,
        unplanned_visits REAL, lines_per_bill REAL
    );
    CREATE INDEX ix_callage_date_terr ON callage_lines(date, territory);
    CREATE INDEX ix_callage_import ON callage_lines(import_id);

    CREATE TABLE sales_orders (
        import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
        date TEXT,
        so_number TEXT, territory TEXT, distributor TEXT, sales_rep TEXT, route TEXT, customer TEXT,
        pricing_scheme TEXT, gross_amount REAL, discount REAL, net_amount REAL, battery REAL, app_version TEXT,
        gps_lat REAL, gps_lng REAL, created_by TEXT, created_tab_date TEXT, created_tab_time TEXT,
        created_server_date TEXT, created_server_time TEXT, invoice_status TEXT
    );
    CREATE INDEX ix_so_date_terr ON sales_orders(date, territory);
    CREATE INDEX ix_so_import ON sales_orders(import_id);

    CREATE TABLE rep_perf_lines (
        import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
        period_from TEXT, period_to TEXT, territory TEXT, sales_rep TEXT,
        total_customers REAL, served_customers REAL, total_bills REAL, productive_calls REAL, bill_days REAL,
        no_of_skus REAL, sold_skus REAL, discounted_total_sales REAL, total_returns REAL, item_discount REAL,
        free_issue_valuation REAL, cash_collection REAL, cheque_collection REAL, outstanding REAL,
        achieved_sales REAL, achieved_collection REAL, lpb REAL
    );
    CREATE INDEX ix_rp_period ON rep_perf_lines(period_from, territory);

    -- Territories seen in SFA data (Territory Sync adds region/status later)
    CREATE TABLE territories (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        name         TEXT NOT NULL UNIQUE COLLATE NOCASE,
        selling_mode TEXT CHECK (selling_mode IN ('van','pre')),
        mode_source  TEXT,                 -- auto (from SKU "SALES REP MODEL") | manual
        is_smmt      INTEGER NOT NULL DEFAULT 0,
        first_seen   TEXT NOT NULL,
        last_seen    TEXT NOT NULL
    );
    """),
    (3, """
    -- Monthly hierarchy + targets (from the NSM's target workbook or Famulus)
    CREATE TABLE target_months (
        month          TEXT PRIMARY KEY,          -- YYYY-MM
        status         TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','locked')),
        nowd           INTEGER,                   -- number of working days
        nowd_manual    INTEGER NOT NULL DEFAULT 0,
        source         TEXT,                      -- famulus | nsm_workbook | editor
        source_file    TEXT,
        national_total REAL,
        created_at     TEXT NOT NULL,
        updated_at     TEXT NOT NULL
    );

    CREATE TABLE hierarchy_nodes (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        month          TEXT NOT NULL REFERENCES target_months(month) ON DELETE CASCADE,
        parent_id      INTEGER REFERENCES hierarchy_nodes(id) ON DELETE CASCADE,
        level          INTEGER NOT NULL,          -- 0 National 1 Region 2 RSM 3 ASM 4 DTM 5 ASE 6 Territory
        sort_order     INTEGER NOT NULL,
        label          TEXT NOT NULL,
        db_code        TEXT,
        distributor    TEXT,
        csr            TEXT,
        is_operating   INTEGER,
        flagged_red    INTEGER NOT NULL DEFAULT 0,
        is_smmt        INTEGER NOT NULL DEFAULT 0,
        target         REAL,                      -- territory rows: monthly target
        declared_total REAL,                      -- subtotal printed in the source file
        sfa_territory  TEXT                       -- matching SFA territory name
    );
    CREATE INDEX ix_hier_month ON hierarchy_nodes(month, level);

    -- Callage ready for reports: Van rows from the report day + Pre rows from the previous working day
    CREATE TABLE callage_prepared (
        import_id          INTEGER REFERENCES imports(id) ON DELETE CASCADE,
        date               TEXT NOT NULL,
        territory          TEXT,
        rsm TEXT, asm TEXT, ase TEXT,
        sales_rep_code     TEXT,
        sales_rep          TEXT,
        selling_mode       TEXT,
        source_date        TEXT,
        ipd REAL, nod REAL, schedule_calls REAL, calls_made REAL, productive_calls REAL,
        unproductive_calls REAL, missed_calls REAL, productivity_pct REAL, unplanned_visits REAL,
        source             TEXT NOT NULL           -- hydra | famulus
    );
    CREATE INDEX ix_cprep_date_terr ON callage_prepared(date, territory);

    CREATE TABLE outlet_categories (
        category_key           TEXT PRIMARY KEY,  -- lower-case label
        label                  TEXT NOT NULL,
        pricing_scheme         TEXT,
        include_in_competition INTEGER NOT NULL DEFAULT 1,
        updated_at             TEXT NOT NULL
    );

    CREATE TABLE competition_rounds (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        month          TEXT NOT NULL,
        name           TEXT NOT NULL,
        colour         TEXT,
        van_sale_limit REAL NOT NULL DEFAULT 100000,
        van_bill_limit REAL NOT NULL DEFAULT 20,
        pre_sale_limit REAL NOT NULL DEFAULT 125000,
        pre_bill_limit REAL NOT NULL DEFAULT 30,
        created_at     TEXT NOT NULL
    );
    CREATE TABLE competition_days (
        round_id INTEGER NOT NULL REFERENCES competition_rounds(id) ON DELETE CASCADE,
        date     TEXT NOT NULL,
        PRIMARY KEY (round_id, date)
    );
    """),
    (4, """
    -- Every report file Hydra generates
    CREATE TABLE reports (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id        INTEGER,
        report_type   TEXT NOT NULL,     -- day_report | target_vs_achievement | sales_comparison | daily_winners | pending_orders
        report_date   TEXT NOT NULL,
        title         TEXT NOT NULL,
        xlsx_path     TEXT,
        pdf_path      TEXT,
        png_paths     TEXT,
        status        TEXT NOT NULL DEFAULT 'generated',   -- generated | approved | sent | saved | failed | skipped
        summary_json  TEXT NOT NULL DEFAULT '{}',
        warnings_json TEXT NOT NULL DEFAULT '[]',
        created_at    TEXT NOT NULL,
        created_by    TEXT
    );
    CREATE INDEX ix_reports_date ON reports(report_date, report_type);
    """),
    (5, """
    -- WhatsApp (Phase 9): who gets what, and every message Hydra sends
    CREATE TABLE wa_recipients (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        name       TEXT NOT NULL,                 -- group or contact name exactly as WhatsApp shows it
        kind       TEXT NOT NULL DEFAULT 'group' CHECK (kind IN ('group','contact')),
        phone      TEXT,                          -- contacts: 94771234567 (opens the chat directly)
        active     INTEGER NOT NULL DEFAULT 1,
        notes      TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE wa_routes (
        report_type  TEXT NOT NULL,
        recipient_id INTEGER NOT NULL REFERENCES wa_recipients(id) ON DELETE CASCADE,
        PRIMARY KEY (report_type, recipient_id)
    );
    CREATE TABLE wa_sends (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        batch        TEXT NOT NULL,               -- one Approve & Send press
        report_id    INTEGER REFERENCES reports(id) ON DELETE SET NULL,
        recipient_id INTEGER REFERENCES wa_recipients(id) ON DELETE SET NULL,
        recipient    TEXT NOT NULL,               -- name at the time of sending
        files_json   TEXT NOT NULL DEFAULT '[]',
        caption      TEXT,
        status       TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','sending','sent','failed','cancelled')),
        error        TEXT,
        created_at   TEXT NOT NULL,
        sent_at      TEXT,
        created_by   TEXT
    );
    CREATE INDEX ix_wa_sends_batch ON wa_sends(batch);
    CREATE INDEX ix_wa_sends_status ON wa_sends(status, created_at);
    """),
    (6, """
    -- Schedule (Phase 10): automatic runs, and a record of every run (manual or scheduled)
    CREATE TABLE schedules (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        name         TEXT NOT NULL,
        time         TEXT NOT NULL,                  -- HH:MM, this PC's local time
        days         TEXT NOT NULL DEFAULT '1111110', -- Mon..Sun, 1 = runs that day
        date_mode    TEXT NOT NULL DEFAULT 'yesterday' CHECK (date_mode IN ('today','yesterday','last_working')),
        report_types TEXT NOT NULL DEFAULT '[]',     -- JSON list; empty = all reports
        formats      TEXT NOT NULL DEFAULT '["pdf","png"]',
        delivery     TEXT NOT NULL DEFAULT 'preview' CHECK (delivery IN ('preview','send','save')),
        retry_min    INTEGER NOT NULL DEFAULT 15,    -- data not there yet: try again every N minutes
        retry_max    INTEGER NOT NULL DEFAULT 4,
        catch_up_min INTEGER NOT NULL DEFAULT 120,   -- Hydra was closed at run time: still run if opened within N minutes
        active       INTEGER NOT NULL DEFAULT 1,
        created_at   TEXT NOT NULL,
        updated_at   TEXT NOT NULL,
        created_by   TEXT
    );
    CREATE TABLE runs (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        schedule_id  INTEGER REFERENCES schedules(id) ON DELETE SET NULL,
        slot         TEXT,                           -- schedule slot 'YYYY-MM-DDTHH:MM' (one run per slot)
        trigger      TEXT NOT NULL,                  -- manual | schedule | catch_up
        report_date  TEXT,
        delivery     TEXT,
        status       TEXT NOT NULL,                  -- waiting | running | done | partial | failed | stopped | missed
        attempts     INTEGER NOT NULL DEFAULT 0,
        next_try_at  TEXT,
        started_at   TEXT NOT NULL,
        finished_at  TEXT,
        generated    INTEGER NOT NULL DEFAULT 0,
        failed       INTEGER NOT NULL DEFAULT 0,
        wa_batch     TEXT,
        message      TEXT,
        user         TEXT
    );
    CREATE UNIQUE INDEX ux_runs_slot ON runs(schedule_id, slot) WHERE slot IS NOT NULL;
    CREATE INDEX ix_runs_started ON runs(started_at);
    """),
]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(paths.db_path(), timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=30000")
    return con


def conn() -> sqlite3.Connection:
    """Connection for the current thread (opened on first use)."""
    init()
    c = getattr(_local, "con", None)
    if c is None:
        c = _local.con = _connect()
    return c


@contextmanager
def tx():
    """Transaction block: commits on success, rolls back on error."""
    c = conn()
    c.execute("BEGIN IMMEDIATE")
    try:
        yield c
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise


def schema_version(c: sqlite3.Connection | None = None) -> int:
    c = c or conn()
    c.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = c.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    return row["v"] or 0


def init() -> int:
    """Create the database file and apply pending migrations. Safe to call often."""
    global _initialised
    if _initialised:
        return 0
    with _init_lock:
        if _initialised:
            return 0
        c = _connect()
        try:
            applied = 0
            current = schema_version(c)
            for version, sql in MIGRATIONS:
                if version > current:
                    # executescript runs the whole migration; the version row is
                    # written in the same script so a half-applied migration is
                    # never recorded as done.
                    c.executescript(
                        "BEGIN;\n" + sql
                        + f"\nINSERT INTO schema_version(version) VALUES ({int(version)});\nCOMMIT;"
                    )
                    applied += 1
        finally:
            c.close()
        _initialised = True
        return applied


def quick_check() -> str:
    """'ok' when the database file is healthy."""
    row = conn().execute("PRAGMA quick_check").fetchone()
    return row[0]


def table_exists(name: str) -> bool:
    row = conn().execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def audit(username: str | None, action: str, details: str = "") -> None:
    conn().execute(
        "INSERT INTO audit(ts, username, action, details) VALUES (?,?,?,?)",
        (now_iso(), username, action, details),
    )
