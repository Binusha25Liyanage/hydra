"""Sales reports service: the five daily management reports. Each builder takes a Context and returns a Table."""
from __future__ import annotations

from datetime import date

from ... import db, settings
from ...reports.table import Column, Row, Table, diff, hierarchy_rows, pct
from .context import DEFAULT_LIMITS, EXCLUDED_SMMT, Context, ReportError, key, ordinal

REPORT_TYPES = {
    "day_report": "Day Report",
    "target_vs_achievement": "Target vs Achievement",
    "sales_comparison": "Sales Comparison",
    "daily_winners": "Daily Winners",
    "pending_orders": "Pending Order Value",
}


def _title(name: str, rest: str) -> str:
    prefix = (settings.get("reports.title_prefix") or "").strip()
    return f"{prefix} — {name} — {rest}" if prefix else f"{name} — {rest}"


def _fmt(n: float) -> str:
    return f"{n:,.0f}"


def _signed(n: float) -> str:
    return f"{n:+,.0f}"


def _long(d: date) -> str:
    return f"{d.day} {d:%B %Y}"


def _unmatched(ctx: Context, values) -> tuple[str, list] | None:
    if not ctx.unmatched:
        return None
    return ("Unmatched Territories", [(ctx.names.get(k, k), values(k)) for k in ctx.unmatched])


# ============================================================================ Day Report
def day_report(ctx: Context) -> Table:
    if not ctx.nowd:
        raise ReportError(f"Working days (NOWD) for {ctx.d:%B %Y} are not set — set them on Hierarchy & Targets")
    d, ds = ctx.d, ctx.d.isoformat()
    cmp = ctx.compare_day()
    month_start, lm_start = d.replace(day=1).isoformat(), cmp.replace(day=1).isoformat()
    callage = ctx.prepared_callage()
    cum_pc = ctx.cumulative_productive_calls()

    f_ach_pct, c_ach_pct = pct("ach", "day_target")
    f_var, c_var = diff("ach", "day_target")
    f_dvar, c_dvar = diff("ach", "lm")
    f_spct, c_spct = pct("smmt_ach", "smmt_day_target")
    f_svar, c_svar = diff("smmt_ach", "smmt_day_target")
    f_pvar, c_pvar = diff("cum_ach", "prev_cum")
    f_cpct, c_cpct = pct("cum_ach", "cum_target")
    f_cvar, c_cvar = diff("cum_ach", "cum_target")
    cols = [
        Column("label", "Territory", "text", 40, sum=False),
        Column("target", "Monthly Target", "money", 16),
        Column("day_target", "Day Target GT", "money", 14),
        Column("ach", "Day Achievement GT", "money", 14),
        Column("ach_pct", "Achievement %", "pct", 13, formula=f_ach_pct, calc=c_ach_pct),
        Column("var", "Variance from Day Target", "money", 15, formula=f_var, calc=c_var),
        Column("lm", f"Last Month Same Day Sale GT ({_long(cmp)})", "money", 14),
        Column("dvar", "Day Variance vs Last Month", "money", 13, formula=f_dvar, calc=c_dvar),
        Column("calls", "Calls Made", "int", 9),
        Column("pc", "Productive Calls", "int", 12),
        Column("smmt_day_target", "SMMT Day Target", "money", 12),
        Column("smmt_ach", "SMMT Day Achievement", "money", 13),
        Column("smmt_pct", "Achievement %", "pct", 13, formula=f_spct, calc=c_spct),
        Column("smmt_var", "SMMT Variance", "money", 13, formula=f_svar, calc=c_svar),
        Column("cum_target", "Cumulative Day Target GT", "money", 14),
        Column("cum_ach", "Cumulative Achievement GT", "money", 14),
        Column("prev_cum", "Prev. Month Same-Date Achievement GT", "money", 15),
        Column("pvar", "Variance vs Prev. Month", "money", 14, formula=f_pvar, calc=c_pvar),
        Column("cum_pct", "Cumulative Achievement %", "pct", 13, formula=f_cpct, calc=c_cpct),
        Column("cum_var", "Cumulative Variance", "money", 14, formula=f_cvar, calc=c_cvar),
        Column("cum_pc", "Cumulative Productive Calls", "int", 13),
    ]

    def values(k: str, monthly_gt: float, monthly_smmt: float, smmt: bool) -> dict:
        dt, ct = ctx.rolling_targets(monthly_gt, k) if not smmt else (0.0, 0.0)
        sdt, _ = ctx.rolling_targets(monthly_smmt, k) if smmt else (0.0, 0.0)
        cl = callage.get(k, {})
        return {
            "target": monthly_gt, "day_target": dt, "ach": 0.0 if smmt else ctx.sale(k, ds),
            "lm": 0.0 if smmt else ctx.sale(k, cmp.isoformat()),
            "calls": cl.get("calls_made", 0), "pc": cl.get("productive_calls", 0),
            "smmt_day_target": sdt, "smmt_ach": ctx.sale(k, ds) if smmt else 0.0,
            "cum_target": ct, "cum_ach": 0.0 if smmt else ctx.cum(k, month_start, ds),
            "prev_cum": 0.0 if smmt else ctx.cum(k, lm_start, cmp.isoformat()),
            "cum_pc": cum_pc.get(k, 0),
        }

    rows = hierarchy_rows(ctx.root, cols, lambda n: values(n.key, n.gt_target(), n.smmt_target(), n.is_smmt),
                          _unmatched(ctx, lambda k: values(k, 0.0, 0.0, "smmt" in k)))
    nat = rows[-1].values
    sub = (f"Working Days (NOWD): {ctx.nowd}   |   Day {d.day} of the month   |   GT Day Target: {_fmt(nat['day_target'])}   |   "
           f"GT Day Achievement: {_fmt(nat['ach'])}   |   SMMT Day Target: {_fmt(nat['smmt_day_target'])}   |   "
           f"SMMT Day Achievement: {_fmt(nat['smmt_ach'])}   |   Last Month Same Day (GT, {_long(cmp)}): {_fmt(nat['lm'])}   |   "
           f"Day Variance: {_signed(nat['dvar'])}   |   Prev. Month (GT, 1-{cmp.day} {cmp:%B %Y}): {_fmt(nat['prev_cum'])}   |   "
           f"Variance vs Prev. Month: {_signed(nat['pvar'])}")
    return Table("day_report", REPORT_TYPES["day_report"],
                 _title("Day Report", f"{ds} ({d:%B %Y})"), sub, cols, rows, f"Day_Report_{ds}",
                 summary={"GT day target": nat["day_target"], "GT day achievement": nat["ach"],
                          "Achievement %": nat["ach_pct"], "Cumulative achievement %": nat["cum_pct"]},
                 warnings=list(ctx.warnings))


# ============================================================================ Target vs Achievement
def target_vs_achievement(ctx: Context) -> Table:
    d, ds = ctx.d, ctx.d.isoformat()
    start = d.replace(day=1).isoformat()
    f_gp, c_gp = pct("cum_gt", "target")
    f_gv, c_gv = diff("cum_gt", "target")
    f_sp, c_sp = pct("cum_smmt", "smmt_target")
    til = f"{ordinal(d.day)} {d:%B %Y}"
    cols = [
        Column("label", "Hierarchy", "text", 40, sum=False),
        Column("target", "Monthly Target", "money", 16),
        Column("cum_gt", f"Achievement GT til {til}", "money", 14),
        Column("gt_pct", "GT Tgt Vs Achive %", "pct", 8, formula=f_gp, calc=c_gp),
        Column("gt_var", "GT Variance", "money", 17, formula=f_gv, calc=c_gv),
        Column("smmt_target", "SMMT Target", "money", 15),
        Column("cum_smmt", f"Achievement SMMT till {til}", "money", 13),
        Column("smmt_pct", "SMMT Tgt Vs Achive %", "pct", 8, formula=f_sp, calc=c_sp),
        Column("balance", "Balance to be achieved", "money", 17,
               formula="={gt_var}+({cum_smmt}-{smmt_target})",
               calc=lambda v: (v.get("gt_var") or 0) + (v.get("cum_smmt") or 0) - (v.get("smmt_target") or 0)),
    ]

    def values(k, gt_t, sm_t, smmt):
        a = ctx.cum(k, start, ds)
        return {"target": gt_t, "cum_gt": 0.0 if smmt else a, "smmt_target": sm_t, "cum_smmt": a if smmt else 0.0}

    rows = hierarchy_rows(ctx.root, cols, lambda n: values(n.key, n.gt_target(), n.smmt_target(), n.is_smmt),
                          _unmatched(ctx, lambda k: values(k, 0.0, 0.0, "smmt" in k)))
    nat = rows[-1].values
    sub = (f"GT Target: {_fmt(nat['target'])}   |   GT Achievement: {_fmt(nat['cum_gt'])}   |   "
           f"SMMT Target: {_fmt(nat['smmt_target'])}   |   SMMT Achievement: {_fmt(nat['cum_smmt'])}")
    return Table("target_vs_achievement", REPORT_TYPES["target_vs_achievement"],
                 _title("Target vs Achievement Report", f"{d:%B %Y}  ({start} to {ds})"), sub, cols, rows,
                 f"Target_vs_Achievement_{start}_to_{ds}", header_height=42,
                 summary={"GT achievement %": nat["gt_pct"], "Balance to be achieved": nat["balance"]},
                 warnings=list(ctx.warnings))


# ============================================================================ Sales Comparison
def sales_comparison(ctx: Context) -> Table:
    d, ds = ctx.d, ctx.d.isoformat()
    cmp = ctx.compare_day()
    start, lm_start = d.replace(day=1).isoformat(), cmp.replace(day=1).isoformat()
    f1, c1 = diff("day", "day_lm")
    f2, c2 = diff("cum", "cum_lm")
    cols = [
        Column("label", "Territory", "text", 40, sum=False),
        Column("day", f"Sale on {d:%d %b %Y}", "money", 14),
        Column("day_lm", f"Sale on {cmp:%d %b %Y}", "money", 14),
        Column("var", "Sales Variance", "money", 13, formula=f1, calc=c1),
        Column("cum", f"Cumulative Sale (1-{d.day} {d:%b %Y})", "money", 14),
        Column("cum_lm", f"Cumulative Sale (1-{cmp.day} {cmp:%b %Y})", "money", 14),
        Column("cum_var", "Cumulative Sales Variance", "money", 15, formula=f2, calc=c2),
    ]

    def values(k):
        return {"day": ctx.sale(k, ds), "day_lm": ctx.sale(k, cmp.isoformat()),
                "cum": ctx.cum(k, start, ds), "cum_lm": ctx.cum(k, lm_start, cmp.isoformat())}

    rows = hierarchy_rows(ctx.root, cols, lambda n: values(n.key), _unmatched(ctx, values))
    nat = rows[-1].values
    sub = (f"Day Sale: {_fmt(nat['day'])} vs {_fmt(nat['day_lm'])} (Variance {_signed(nat['var'])})   |   "
           f"Cumulative: {_fmt(nat['cum'])} vs {_fmt(nat['cum_lm'])} (Variance {_signed(nat['cum_var'])})   |   "
           f"Hierarchy: {date.fromisoformat(ctx.hier_month + '-01'):%B %Y} target")
    return Table("sales_comparison", REPORT_TYPES["sales_comparison"],
                 _title("Sales Comparison", f"{d:%d %b %Y} vs {cmp:%d %b %Y}"), sub, cols, rows,
                 f"Sales_Comparison_{ds}_vs_{cmp.isoformat()}", freeze="B5",
                 summary={"Day sale": nat["day"], "Day variance": nat["var"], "Cumulative variance": nat["cum_var"]},
                 warnings=list(ctx.warnings))


# ============================================================================ Daily Winners
def competition_for(d: date) -> tuple[bool, dict, str]:
    """(is competition day, limits per mode, round name). No rounds for the month → every day, default limits."""
    c = db.conn()
    month = d.strftime("%Y-%m")
    rounds = c.execute("SELECT * FROM competition_rounds WHERE month=?", (month,)).fetchall()
    if not rounds:
        return True, dict(DEFAULT_LIMITS), "Default limits (no competition calendar for this month)"
    r = c.execute("SELECT r.* FROM competition_rounds r JOIN competition_days cd ON cd.round_id=r.id "
                  "WHERE r.month=? AND cd.date=?", (month, d.isoformat())).fetchone()
    if not r:
        return False, {}, ""
    return True, {"van": (r["van_sale_limit"], r["van_bill_limit"]), "pre": (r["pre_sale_limit"], r["pre_bill_limit"])}, r["name"]


def daily_winners(ctx: Context) -> Table:
    d, ds = ctx.d, ctx.d.isoformat()
    is_day, limits, round_name = competition_for(d)
    if not is_day:
        raise ReportError(f"{ds} is not a competition day — Daily Winners skipped")
    callage = ctx.prepared_callage()
    cols = [Column("region", "Region", "text", 20, sum=False), Column("rsm", "RSM", "text", 23, sum=False),
            Column("asm", "ASM", "text", 27, sum=False), Column("dtm", "DTM", "text", 25, sum=False),
            Column("ase", "ASE", "text", 23, sum=False), Column("territory", "Territory", "text", 17, sum=False),
            Column("mode", "Selling Mode", "text", 13, sum=False), Column("sale", "Sale Value", "int", 11),
            Column("smmt_sale", "SMMT Outlet Sale", "int", 10), Column("bills", "Bill Count", "int", 8),
            Column("sale_limit", "Sale Limit", "int", 10), Column("bill_limit", "Bill Limit", "int", 8),
            Column("winner", "Winner", "text", 9, sum=False)]
    rows: list[Row] = []
    for t in ctx.terrs:
        if t.is_smmt or t.key in EXCLUDED_SMMT:
            continue
        total = ctx.sale(t.key, ds)
        if total <= 0:
            continue
        comp = ctx.sale(t.key, ds, comp_only=True)
        mode = ctx.modes.get(t.key) or "van"
        sl, bl = limits.get(mode, DEFAULT_LIMITS[mode])
        cl = callage.get(t.key, {})
        bills = max((cl.get("productive_calls") or 0) - (cl.get("unplanned_visits") or 0), 0)
        anc = t.ancestors()
        win = comp >= sl and bills >= bl
        rows.append(Row("plain", t.label, {
            "region": anc.get(1), "rsm": anc.get(2), "asm": anc.get(3), "dtm": anc.get(4), "ase": anc.get(5),
            "territory": t.label, "mode": "Pre Selling" if mode == "pre" else "Van Selling", "sale": comp,
            "smmt_sale": total - comp, "bills": bills, "sale_limit": sl, "bill_limit": bl,
            "winner": "Yes" if win else "No"}, style="winner" if win else ""))
    rows.sort(key=lambda r: -r.values["sale"])
    winners = sum(1 for r in rows if r.values["winner"] == "Yes")
    w = list(ctx.warnings)
    if "Default limits" in round_name:
        w.append(round_name)
    return Table("daily_winners", REPORT_TYPES["daily_winners"], _title("Daily Winners", ds),
                 f"Territories with a sale today: {len(rows)}   |   Winners: {winners}", cols, rows,
                 f"Daily_Winners_{ds}", header_height=20,
                 summary={"Territories with a sale": len(rows), "Winners": winners,
                          "Winner list": [r.label for r in rows if r.values["winner"] == "Yes"]}, warnings=w)


# ============================================================================ Pending Order Value
def pending_orders(ctx: Context) -> Table:
    d, ds = ctx.d, ctx.d.isoformat()
    c = db.conn()
    snap = c.execute("SELECT s.import_id, i.generated_at, i.imported_at FROM sales_orders s JOIN imports i ON i.id=s.import_id "
                     "WHERE s.date=? GROUP BY s.import_id ORDER BY COALESCE(i.generated_at, i.imported_at) DESC, "
                     "s.import_id DESC LIMIT 1", (ds,)).fetchone()
    if not snap:
        raise ReportError(f"No View Pre-Selling (Sales Order) data for {ds}")
    agg: dict[str, dict] = {}
    for r in c.execute("SELECT territory, customer, net_amount, invoice_status FROM sales_orders WHERE import_id=? AND date=?",
                       (snap["import_id"], ds)):
        k = key(r["territory"])
        if k in EXCLUDED_SMMT or ctx.modes.get(k) != "pre":
            continue
        if r["invoice_status"] and r["invoice_status"].strip().lower() != "pending":
            continue
        a = agg.setdefault(k, {"name": r["territory"], "value": 0.0, "customers": set()})
        a["value"] += r["net_amount"] or 0
        a["customers"].add(r["customer"])
    cols = [Column("territory", "Territory", "text", 16, sum=False), Column("value", "Order Value", "int", 12),
            Column("count", "Order Count", "int", 10)]
    rows = [Row("plain", a["name"], {"territory": a["name"], "value": a["value"], "count": len(a["customers"])})
            for a in sorted(agg.values(), key=lambda x: -x["value"])]
    total = {"territory": "TOTAL", "value": sum(r.values["value"] for r in rows), "count": sum(r.values["count"] for r in rows)}
    rows.append(Row("total", "TOTAL", total, list(range(len(rows)))))
    w = list(ctx.warnings)
    no_mode = [ctx.names.get(k, k) for k in {key(r["territory"]) for r in c.execute(
        "SELECT DISTINCT territory FROM sales_orders WHERE import_id=?", (snap["import_id"],))} if not ctx.modes.get(k)]
    if no_mode:
        w.append("Territories with orders but no Van/Pre setting (left out): " + ", ".join(sorted(no_mode)))
    when = snap["generated_at"] or snap["imported_at"]
    return Table("pending_orders", REPORT_TYPES["pending_orders"], _title("Preselling Pending Order Value", ds),
                 f"Pre Selling territories with pending orders: {len(rows) - 1}   |   Total Pending Order Value: {_fmt(total['value'])}",
                 cols, rows, f"Pending_Order_Value_{ds}", header_height=20,
                 summary={"Total pending value": total["value"], "Orders (outlets)": total["count"], "Snapshot": when},
                 warnings=w)


BUILDERS = {"day_report": day_report, "target_vs_achievement": target_vs_achievement,
            "sales_comparison": sales_comparison, "daily_winners": daily_winners, "pending_orders": pending_orders}
