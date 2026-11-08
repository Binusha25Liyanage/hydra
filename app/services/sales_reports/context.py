"""Everything a report needs for one report date, loaded once.

Rules confirmed from the Famulus source code and the 3 Nov 2026 sample reports:
  * GT vs SMMT: a territory whose name contains "SMMT" (or is flagged SMMT) is SMMT.
  * Day Target = max(T − achieved so far, 0) / max(NOWD − days this territory sold, 1);
    "so far" = the data dates of the month before the report date.
  * Cumulative Day Target = the Day Target of every earlier data date + today's.
  * Same day last month is clamped to the month's last day (31 Oct → 30 Sep);
    if that day has no sales, the nearest earlier day with sales is used.
  * Callage: Van territories use the report day, Pre territories the previous working day.
  * Winners: sale excludes outlet categories not in the competition (SMMT/MRP);
    bill count = productive calls − unplanned visits.
"""
from __future__ import annotations

import calendar
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from ... import db

EXCLUDED_SMMT = {"colombosmmt", "kandysmmt", "anuradhapurasmmt"}   # never in Winners / Pending Orders
LEVEL_NAMES = {0: "National", 1: "Region", 2: "RSM", 3: "ASM", 4: "DTM", 5: "ASE", 6: "Territory"}
DEFAULT_LIMITS = {"van": (100000, 20), "pre": (125000, 30)}


def key(name: str | None) -> str:
    """Matching key: 'Anuradhapura(SMMT)' == 'anuradhapura smmt', 'homagama' == 'Homagama'."""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def month_of(d: date) -> str:
    return d.strftime("%Y-%m")


def same_day_last_month(d: date) -> date:
    y, m = (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


class ReportError(Exception):
    """A report cannot be produced (missing targets, NOWD, data…)."""


@dataclass
class Node:
    id: int
    level: int
    label: str
    order: float
    target: float = 0.0
    is_smmt: bool = False
    children: list = field(default_factory=list)
    parent: "Node | None" = None
    key: str = ""
    flagged_red: bool = False

    @property
    def is_territory(self) -> bool:
        return self.level == 6

    def gt_target(self) -> float:
        return 0.0 if self.is_smmt else self.target

    def smmt_target(self) -> float:
        return self.target if self.is_smmt else 0.0

    def ancestors(self) -> dict:
        out, n = {}, self.parent
        while n is not None:
            out[n.level] = n.label
            n = n.parent
        return out


def load_hierarchy(month: str, fallback: bool = False) -> tuple[str, Node]:
    c = db.conn()
    use = month
    if not c.execute("SELECT 1 FROM hierarchy_nodes WHERE month=? LIMIT 1", (month,)).fetchone():
        if not fallback:
            raise ReportError(f"Targets for {date.fromisoformat(month + '-01'):%B %Y} are not set — import them on "
                              f"Hierarchy & Targets first")
        row = c.execute("SELECT month FROM hierarchy_nodes WHERE month<? ORDER BY month DESC LIMIT 1", (month,)).fetchone()
        if not row:
            raise ReportError("No targets / hierarchy in Hydra yet — import them on Hierarchy & Targets")
        use = row[0]
    rows = c.execute("SELECT * FROM hierarchy_nodes WHERE month=? ORDER BY level, sort_order, id", (use,)).fetchall()
    nodes = {r["id"]: Node(r["id"], r["level"], r["label"], r["sort_order"], r["target"] or 0.0, bool(r["is_smmt"]),
                           key=key(r["sfa_territory"] or r["label"]), flagged_red=bool(r["flagged_red"])) for r in rows}
    root = None
    for r in rows:
        n = nodes[r["id"]]
        if r["parent_id"] is None:
            root = n
        else:
            n.parent = nodes[r["parent_id"]]
            n.parent.children.append(n)

    def sort(n: Node) -> float:
        for k in n.children:
            sort(k)
        n.children.sort(key=lambda k: k.order)
        n.order = min([n.order] + [k.order for k in n.children])
        return n.order
    sort(root)
    return use, root


def territories(root: Node) -> list[Node]:
    out: list[Node] = []

    def walk(n):
        if n.is_territory:
            out.append(n)
        for k in n.children:
            walk(k)
    walk(root)
    return out


class Context:
    """Loads the data for report date `d` (sales are read for this month and last month)."""

    def __init__(self, d: date, fallback_hierarchy: bool = False):
        self.d = d
        self.month = month_of(d)
        self.warnings: list[str] = []
        c = db.conn()
        self.hier_month, self.root = load_hierarchy(self.month, fallback_hierarchy)
        if self.hier_month != self.month:
            self.warnings.append(f"Using the {self.hier_month} hierarchy (targets for {self.month} not set yet)")
        self.terrs = territories(self.root)
        self.by_key = {t.key: t for t in self.terrs}
        m = c.execute("SELECT nowd FROM target_months WHERE month=?", (self.month,)).fetchone()
        self.nowd = m["nowd"] if m and m["nowd"] else None

        # ---- sales (all outlet categories) by territory key and date, this month + last month
        self.lm_day = same_day_last_month(d)
        start_last = self.lm_day.replace(day=1)
        end_this = d.replace(day=calendar.monthrange(d.year, d.month)[1])
        self.sales: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.sales_comp: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))   # competition outlets only
        self.dates_with_data: set[str] = set()
        excluded = {r[0] for r in c.execute("SELECT category_key FROM outlet_categories WHERE include_in_competition=0")}
        self.names: dict[str, str] = {}
        for r in c.execute("SELECT date, territory, LOWER(TRIM(COALESCE(outlet_classification,''))) oc, SUM(sales_value) v "
                           "FROM sku_lines WHERE date BETWEEN ? AND ? GROUP BY date, territory, oc",
                           (start_last.isoformat(), end_this.isoformat())):
            k = key(r["territory"])
            self.names.setdefault(k, r["territory"])
            self.sales[k][r["date"]] += r["v"] or 0
            if r["oc"] not in excluded:
                self.sales_comp[k][r["date"]] += r["v"] or 0
            self.dates_with_data.add(r["date"])
        self.unmatched = sorted(k for k in self.sales if k not in self.by_key
                                and any(r.startswith(self.month) for r in self.sales[k]))
        if self.unmatched:
            self.warnings.append("Sales for territories not in the hierarchy: " +
                                 ", ".join(self.names.get(k, k) for k in self.unmatched))
        ds = d.isoformat()
        if ds not in self.dates_with_data:
            self.warnings.append(f"No SKU sales data for {ds}")
        # data dates of this month before d (what Famulus calls the prior working dates)
        self.prior_dates = sorted(x for x in self.dates_with_data if x.startswith(self.month) and x < ds)

        # ---- selling modes
        self.modes = {key(r["name"]): r["selling_mode"] for r in c.execute("SELECT name, selling_mode FROM territories")}

    # ------------------------------------------------------------------ sales helpers
    def sale(self, k: str, day: str, comp_only: bool = False) -> float:
        src = self.sales_comp if comp_only else self.sales
        return src.get(k, {}).get(day, 0.0)

    def cum(self, k: str, start: str, end: str) -> float:
        return sum(v for dd, v in self.sales.get(k, {}).items() if start <= dd <= end)

    def compare_day(self) -> date:
        """Same day last month; if it has no sales, the nearest earlier day that has."""
        lm = self.lm_day
        have = sorted(x for x in self.dates_with_data if x.startswith(lm.strftime("%Y-%m")) and x <= lm.isoformat())
        if lm.isoformat() in self.dates_with_data or not have:
            return lm
        return date.fromisoformat(have[-1])

    # ------------------------------------------------------------------ targets
    def rolling_targets(self, monthly: float, k: str) -> tuple[float, float]:
        """(day target, cumulative day target) — Famulus's rolling formula."""
        if not self.nowd:
            return 0.0, 0.0
        prior = [self.sale(k, x) for x in self.prior_dates]

        def for_day(earlier: list[float]) -> float:
            achieved = sum(earlier)
            worked = sum(1 for a in earlier if a)
            return max(monthly - achieved, 0.0) / max(self.nowd - worked, 1)

        cumulative = sum(for_day(prior[:i]) for i in range(len(prior)))
        today = for_day(prior)
        return today, cumulative + today

    # ------------------------------------------------------------------ callage
    def previous_working_day(self, day: date) -> date:
        holidays = set()
        if db.table_exists("calendar_days"):
            holidays = {r[0] for r in db.conn().execute("SELECT date FROM calendar_days WHERE is_working=0")}
        p = day - timedelta(days=1)
        while p.weekday() == 6 or p.isoformat() in holidays:
            p -= timedelta(days=1)
        return p

    def prepared_callage(self, day: date | None = None, build: bool = True) -> dict[str, dict]:
        """Per territory key: calls_made, productive_calls, unplanned_visits for `day` (prepared)."""
        day = day or self.d
        ds = day.isoformat()
        c = db.conn()
        if build:
            ensure_prepared_callage(day, self)
        out: dict[str, dict] = {}
        for r in c.execute("SELECT territory, SUM(calls_made) cm, SUM(productive_calls) pc, SUM(unplanned_visits) uv "
                           "FROM callage_prepared WHERE date=? GROUP BY territory", (ds,)):
            out[key(r["territory"])] = {"calls_made": r["cm"] or 0, "productive_calls": r["pc"] or 0,
                                        "unplanned_visits": r["uv"] or 0}
        return out

    def cumulative_productive_calls(self) -> dict[str, float]:
        # make sure every earlier day of the month that has raw Callage is prepared too
        c = db.conn()
        raw_days = [r[0] for r in c.execute("SELECT DISTINCT date FROM callage_lines WHERE date BETWEEN ? AND ?",
                                            (self.d.replace(day=1).isoformat(), self.d.isoformat()))]
        done = {r[0] for r in c.execute("SELECT DISTINCT date FROM callage_prepared WHERE date BETWEEN ? AND ?",
                                        (self.d.replace(day=1).isoformat(), self.d.isoformat()))}
        nxt = {(date.fromisoformat(x) + timedelta(days=1)).isoformat() for x in raw_days}
        for ds in sorted((set(raw_days) | nxt) - done):
            if ds <= self.d.isoformat() and date.fromisoformat(ds).weekday() != 6:
                ensure_prepared_callage(date.fromisoformat(ds), self)
        out: dict[str, float] = defaultdict(float)
        for r in db.conn().execute("SELECT territory, SUM(productive_calls) pc FROM callage_prepared "
                                   "WHERE date BETWEEN ? AND ? GROUP BY territory",
                                   (self.d.replace(day=1).isoformat(), self.d.isoformat())):
            out[key(r["territory"])] += r["pc"] or 0
        return out


def ensure_prepared_callage(day: date, ctx: Context | None = None) -> list[str]:
    """Build Hydra's prepared callage for `day` from the raw Callage downloads.

    Van territories: rows from `day`. Pre territories: rows from the previous working day.
    Famulus history (source='famulus') is never overwritten. Returns warnings."""
    c = db.conn()
    ds = day.isoformat()
    if c.execute("SELECT 1 FROM callage_prepared WHERE date=? AND source='famulus' LIMIT 1", (ds,)).fetchone():
        return []
    raw_today = c.execute("SELECT * FROM callage_lines WHERE date=?", (ds,)).fetchall()
    prev = (ctx.previous_working_day(day) if ctx else _prev_working(day)).isoformat()
    raw_prev = c.execute("SELECT * FROM callage_lines WHERE date=?", (prev,)).fetchall()
    if not raw_today and not raw_prev:
        return [f"No Callage data for {ds} or {prev}"]
    modes = {key(r["name"]): r["selling_mode"] for r in c.execute("SELECT name, selling_mode FROM territories")}
    warnings = []
    rows = []
    for r in raw_today:
        if modes.get(key(r["territory"])) != "pre":
            rows.append((r, "van", ds))
    for r in raw_prev:
        if modes.get(key(r["territory"])) == "pre":
            rows.append((r, "pre", prev))
    if not raw_prev and any(m == "pre" for m in modes.values()):
        warnings.append(f"No Callage for {prev}: Pre Selling calls for {ds} are missing")
    with db.tx() as cc:
        cc.execute("DELETE FROM callage_prepared WHERE date=? AND source='hydra'", (ds,))
        cc.executemany(
            "INSERT INTO callage_prepared(import_id, date, territory, rsm, asm, ase, sales_rep_code, sales_rep, selling_mode, "
            "source_date, ipd, nod, schedule_calls, calls_made, productive_calls, unproductive_calls, missed_calls, "
            "productivity_pct, unplanned_visits, source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'hydra')",
            [(r["import_id"], ds, r["territory"], r["rsm"], r["asm"], r["ase"], r["sales_rep_code"], r["sales_rep"], mode,
              src, r["ipd"], r["nod"], r["schedule_calls"], r["calls_made"], r["productive_calls"],
              r["unproductive_calls"], r["missed_calls"], r["productivity_pct"], r["unplanned_visits"])
             for r, mode, src in rows])
    return warnings


def _prev_working(day: date) -> date:
    p = day - timedelta(days=1)
    while p.weekday() == 6:
        p -= timedelta(days=1)
    return p
