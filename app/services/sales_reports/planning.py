"""Planning data for the sales reports (Phase 5):

* Targets editor  — edit territory targets and flags, add / move / rename / delete
                    territories, start a new month from last month, lock a month.
* Competition     — rounds (name, colour, Van/Pre winner limits) and the days of each round.
* Aliases         — match SFA territory names to hierarchy territories.
* Outlet labels   — which outlet categories count for the Daily Winners competition.
"""
from __future__ import annotations

import calendar
import re
from datetime import date

from ... import db
from .context import DEFAULT_LIMITS, key


class PlanningError(Exception):
    pass


LEVEL_NAMES = {0: "National", 1: "Region", 2: "RSM", 3: "ASM", 4: "DTM", 5: "ASE", 6: "Territory"}
_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _check_month(month: str) -> str:
    if not _MONTH.match(month or ""):
        raise PlanningError(f"Bad month: {month!r} (use YYYY-MM)")
    return month


def _node(c, node_id: int):
    n = c.execute("SELECT * FROM hierarchy_nodes WHERE id=?", (int(node_id),)).fetchone()
    if not n:
        raise PlanningError("That row no longer exists — reload the page")
    return n


def _editable(c, month: str):
    m = c.execute("SELECT status FROM target_months WHERE month=?", (month,)).fetchone()
    if not m:
        raise PlanningError(f"No hierarchy for {month}")
    if m["status"] == "locked":
        raise PlanningError(f"{month} is locked — unlock it first")


def _touch(c, month: str):
    tot = c.execute("SELECT COALESCE(SUM(target),0) FROM hierarchy_nodes WHERE month=? AND level=6", (month,)).fetchone()[0]
    c.execute("UPDATE target_months SET updated_at=?, national_total=? WHERE month=?", (db.now_iso(), tot, month))


# =============================================================================== targets editor
EDITABLE = {"target", "is_smmt", "is_operating", "flagged_red", "label", "distributor", "csr", "db_code", "sfa_territory"}
TERRITORY_ONLY = {"target", "is_smmt", "is_operating", "distributor", "csr", "db_code", "sfa_territory"}


def update_nodes(changes: list[dict], user: str | None = None) -> int:
    """changes = [{"id": 12, "target": 4500000, "is_smmt": 0, ...}] — saved together or not at all."""
    n = 0
    with db.tx() as c:
        months = set()
        for ch in changes or []:
            row = _node(c, ch.get("id"))
            months.add(row["month"])
            _editable(c, row["month"])
            sets, args = [], []
            for f, v in ch.items():
                if f == "id":
                    continue
                if f not in EDITABLE:
                    raise PlanningError(f"Field {f} cannot be edited")
                if f in TERRITORY_ONLY and row["level"] != 6:
                    raise PlanningError(f"{row['label']}: {f.replace('_', ' ')} is set on territories only")
                if f == "target":
                    try:
                        v = round(float(str(v).replace(",", "") or 0), 2)
                    except ValueError:
                        raise PlanningError(f"{row['label']}: target must be a number")
                    if v < 0:
                        raise PlanningError(f"{row['label']}: target cannot be negative")
                elif f in ("is_smmt", "is_operating", "flagged_red"):
                    v = 1 if v in (True, 1, "1", "true") else 0
                elif f == "label":
                    v = (v or "").strip()
                    if not v:
                        raise PlanningError("Name cannot be empty")
                else:
                    v = (v or "").strip() or None
                sets.append(f"{f}=?")
                args.append(v)
            if sets:
                c.execute(f"UPDATE hierarchy_nodes SET {', '.join(sets)} WHERE id=?", (*args, row["id"]))
                n += 1
        for m in months:
            _touch(c, m)
    db.audit(user, "targets.edit", f"{n} row(s)")
    return n


def add_node(parent_id: int, label: str, target: float = 0, is_smmt: bool = False, user: str | None = None) -> int:
    """Add a child under parent: a territory under an ASE, or a manager position under a higher level."""
    label = (label or "").strip()
    if not label:
        raise PlanningError("Enter a name")
    with db.tx() as c:
        p = _node(c, parent_id)
        _editable(c, p["month"])
        if p["level"] >= 6:
            raise PlanningError("A territory cannot have rows under it")
        level = p["level"] + 1
        if level == 6 and c.execute("SELECT 1 FROM hierarchy_nodes WHERE month=? AND level=6 AND LOWER(label)=LOWER(?)",
                                    (p["month"], label)).fetchone():
            raise PlanningError(f"{label} is already in {p['month']}")
        last = c.execute("SELECT MAX(sort_order) FROM hierarchy_nodes WHERE parent_id=?", (p["id"],)).fetchone()[0]
        if last is None:
            last = c.execute("SELECT sort_order FROM hierarchy_nodes WHERE id=?", (p["id"],)).fetchone()[0]
        nid = c.execute("INSERT INTO hierarchy_nodes(month, parent_id, level, sort_order, label, is_operating, is_smmt, target) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (p["month"], p["id"], level, last + 0.5, label,
                         1 if level == 6 else None, 1 if is_smmt else 0, float(target or 0) if level == 6 else None)).lastrowid
        _renumber(c, p["month"])
        _touch(c, p["month"])
    db.audit(user, "targets.add", f"{label} ({LEVEL_NAMES[level]}) under {p['label']}")
    return nid


def move_node(node_id: int, new_parent_id: int, user: str | None = None) -> None:
    with db.tx() as c:
        n, p = _node(c, node_id), _node(c, new_parent_id)
        _editable(c, n["month"])
        if n["month"] != p["month"]:
            raise PlanningError("Rows can only move within the same month")
        if p["level"] != n["level"] - 1:
            raise PlanningError(f"A {LEVEL_NAMES[n['level']]} must go under a {LEVEL_NAMES[n['level'] - 1]}")
        last = c.execute("SELECT MAX(sort_order) FROM hierarchy_nodes WHERE parent_id=?", (p["id"],)).fetchone()[0]
        c.execute("UPDATE hierarchy_nodes SET parent_id=?, sort_order=? WHERE id=?",
                  (p["id"], (last if last is not None else p["sort_order"]) + 0.5, n["id"]))
        _renumber(c, n["month"])
        _touch(c, n["month"])
    db.audit(user, "targets.move", f"{n['label']} -> {p['label']}")


def delete_node(node_id: int, user: str | None = None) -> None:
    with db.tx() as c:
        n = _node(c, node_id)
        _editable(c, n["month"])
        if n["level"] == 0:
            raise PlanningError("The National row cannot be deleted")
        if c.execute("SELECT 1 FROM hierarchy_nodes WHERE parent_id=?", (n["id"],)).fetchone():
            raise PlanningError(f"Move or delete the rows under {n['label']} first")
        c.execute("DELETE FROM hierarchy_nodes WHERE id=?", (n["id"],))
        _touch(c, n["month"])
    db.audit(user, "targets.delete", f"{n['label']} ({n['month']})")


def _renumber(c, month: str) -> None:
    """Re-number sort_order in tree order (parents before children, siblings in order)."""
    rows = c.execute("SELECT id, parent_id, sort_order FROM hierarchy_nodes WHERE month=?", (month,)).fetchall()
    kids: dict = {}
    for r in rows:
        kids.setdefault(r["parent_id"], []).append(r)
    smin: dict = {}

    def subtree_min(r):   # same ordering the Hierarchy screen uses (a subtotal sits with its first child)
        if r["id"] not in smin:
            smin[r["id"]] = min([r["sort_order"]] + [subtree_min(k) for k in kids.get(r["id"], [])])
        return smin[r["id"]]
    order: list[int] = []

    def walk(pid):
        for r in sorted(kids.get(pid, []), key=lambda x: (subtree_min(x), x["id"])):
            order.append(r["id"])
            walk(r["id"])
    walk(None)
    for i, nid in enumerate(order, start=1):
        c.execute("UPDATE hierarchy_nodes SET sort_order=? WHERE id=?", (i * 10, nid))


def copy_month(src: str, dst: str, keep_targets: bool = True, user: str | None = None) -> int:
    """Start month `dst` from month `src`: same hierarchy, aliases and flags; targets kept or zeroed."""
    _check_month(src), _check_month(dst)
    with db.tx() as c:
        if not c.execute("SELECT 1 FROM target_months WHERE month=?", (src,)).fetchone():
            raise PlanningError(f"No hierarchy for {src}")
        if c.execute("SELECT 1 FROM target_months WHERE month=?", (dst,)).fetchone():
            raise PlanningError(f"{dst} already has a hierarchy — open it and edit, or delete it first")
        now = db.now_iso()
        c.execute("INSERT INTO target_months(month, status, nowd, nowd_manual, source, source_file, national_total, created_at, updated_at) "
                  "VALUES (?, 'draft', NULL, 0, 'editor', ?, NULL, ?, ?)", (dst, f"Copied from {src}", now, now))
        idmap: dict = {}
        for r in c.execute("SELECT * FROM hierarchy_nodes WHERE month=? ORDER BY level, sort_order, id", (src,)).fetchall():
            idmap[r["id"]] = c.execute(
                "INSERT INTO hierarchy_nodes(month, parent_id, level, sort_order, label, db_code, distributor, csr, is_operating, "
                "flagged_red, is_smmt, target, declared_total, sfa_territory) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NULL,?)",
                (dst, idmap.get(r["parent_id"]), r["level"], r["sort_order"], r["label"], r["db_code"], r["distributor"],
                 r["csr"], r["is_operating"], r["flagged_red"], r["is_smmt"],
                 (r["target"] if keep_targets else 0) if r["level"] == 6 else None, r["sfa_territory"])).lastrowid
        _touch(c, dst)
    db.audit(user, "targets.copy_month", f"{src} -> {dst} keep_targets={keep_targets}")
    return len(idmap)


def delete_month(month: str, user: str | None = None) -> None:
    with db.tx() as c:
        _editable(c, month)
        c.execute("DELETE FROM hierarchy_nodes WHERE month=?", (month,))
        c.execute("DELETE FROM target_months WHERE month=?", (month,))
    db.audit(user, "targets.delete_month", month)


def set_locked(month: str, locked: bool, user: str | None = None) -> None:
    with db.tx() as c:
        if not c.execute("UPDATE target_months SET status=?, updated_at=? WHERE month=?",
                         ("locked" if locked else "draft", db.now_iso(), month)).rowcount:
            raise PlanningError(f"No hierarchy for {month}")
    db.audit(user, "targets.lock" if locked else "targets.unlock", month)


def parents_for(month: str, level: int) -> list[dict]:
    """Rows a node of `level` can be moved under (with their path, for the Move dialog)."""
    c = db.conn()
    rows = {r["id"]: r for r in c.execute("SELECT id, parent_id, level, label FROM hierarchy_nodes WHERE month=?", (month,))}

    def path(r):
        out = []
        while r is not None and r["level"] > 0:
            out.append(r["label"])
            r = rows.get(r["parent_id"])
        return " › ".join(reversed(out))
    return sorted(({"id": r["id"], "label": r["label"], "path": path(r)} for r in rows.values() if r["level"] == level - 1),
                  key=lambda x: x["path"].lower())


# =============================================================================== competition calendar
def rounds(month: str) -> dict:
    _check_month(month)
    c = db.conn()
    out = []
    for r in c.execute("SELECT * FROM competition_rounds WHERE month=? ORDER BY id", (month,)):
        x = dict(r)
        x["days"] = [d[0] for d in c.execute("SELECT date FROM competition_days WHERE round_id=? ORDER BY date", (r["id"],))]
        out.append(x)
    y, m = map(int, month.split("-"))
    ndays = calendar.monthrange(y, m)[1]
    sundays = sum(1 for d in range(1, ndays + 1) if date(y, m, d).weekday() == 6)
    tm = c.execute("SELECT nowd FROM target_months WHERE month=?", (month,)).fetchone()
    winners = {r[0]: r[1] for r in c.execute(
        "SELECT report_date, MAX(status) FROM reports WHERE report_type='daily_winners' AND report_date LIKE ? GROUP BY report_date",
        (month + "%",))}
    return {"month": month, "rounds": out, "defaults": DEFAULT_LIMITS, "days_in_month": ndays, "sundays": sundays,
            "nowd": tm["nowd"] if tm else None, "has_targets": bool(tm), "winners": winners}


def save_round(month: str, data: dict, user: str | None = None) -> int:
    _check_month(month)
    name = (data.get("name") or "").strip()
    if not name:
        raise PlanningError("Give the round a name (e.g. Round 1)")
    vals = []
    for f in ("van_sale_limit", "van_bill_limit", "pre_sale_limit", "pre_bill_limit"):
        try:
            v = float(str(data.get(f, "")).replace(",", ""))
        except ValueError:
            raise PlanningError(f"{f.replace('_', ' ').title()} must be a number")
        if v < 0:
            raise PlanningError(f"{f.replace('_', ' ').title()} cannot be negative")
        vals.append(v)
    colour = data.get("colour") or "#B3172F"
    if not re.match(r"^#[0-9A-Fa-f]{6}$", colour):
        colour = "#B3172F"
    with db.tx() as c:
        if data.get("id"):
            if not c.execute("UPDATE competition_rounds SET name=?, colour=?, van_sale_limit=?, van_bill_limit=?, pre_sale_limit=?, "
                             "pre_bill_limit=? WHERE id=? AND month=?", (name, colour, *vals, int(data["id"]), month)).rowcount:
                raise PlanningError("That round no longer exists")
            rid = int(data["id"])
        else:
            rid = c.execute("INSERT INTO competition_rounds(month, name, colour, van_sale_limit, van_bill_limit, pre_sale_limit, "
                            "pre_bill_limit, created_at) VALUES (?,?,?,?,?,?,?,?)", (month, name, colour, *vals, db.now_iso())).lastrowid
    db.audit(user, "competition.round", f"{month} {name}")
    return rid


def delete_round(round_id: int, user: str | None = None) -> None:
    with db.tx() as c:
        r = c.execute("SELECT month, name FROM competition_rounds WHERE id=?", (int(round_id),)).fetchone()
        if not r:
            return
        c.execute("DELETE FROM competition_days WHERE round_id=?", (int(round_id),))
        c.execute("DELETE FROM competition_rounds WHERE id=?", (int(round_id),))
    db.audit(user, "competition.delete_round", f"{r['month']} {r['name']}")


def save_days(month: str, assignment: dict, user: str | None = None) -> int:
    """assignment = {"2026-11-02": round_id, ...} for the whole month; a day not listed has no round."""
    _check_month(month)
    with db.tx() as c:
        ids = {r[0] for r in c.execute("SELECT id FROM competition_rounds WHERE month=?", (month,))}
        c.execute(f"DELETE FROM competition_days WHERE round_id IN (SELECT id FROM competition_rounds WHERE month=?)", (month,))
        n = 0
        for ds, rid in (assignment or {}).items():
            if rid in (None, "", 0):
                continue
            rid = int(rid)
            if rid not in ids:
                raise PlanningError("A day points at a round that no longer exists — reload the page")
            d = date.fromisoformat(ds)
            if d.strftime("%Y-%m") != month:
                raise PlanningError(f"{ds} is not in {month}")
            c.execute("INSERT INTO competition_days(round_id, date) VALUES (?,?)", (rid, ds))
            n += 1
    db.audit(user, "competition.days", f"{month}: {n} day(s)")
    return n


def copy_rounds(src: str, dst: str, user: str | None = None) -> int:
    """Copy round names and limits (not days) from another month."""
    _check_month(src), _check_month(dst)
    with db.tx() as c:
        if c.execute("SELECT 1 FROM competition_rounds WHERE month=?", (dst,)).fetchone():
            raise PlanningError(f"{dst} already has rounds")
        src_rows = c.execute("SELECT * FROM competition_rounds WHERE month=? ORDER BY id", (src,)).fetchall()
        if not src_rows:
            raise PlanningError(f"{src} has no rounds to copy")
        for r in src_rows:
            c.execute("INSERT INTO competition_rounds(month, name, colour, van_sale_limit, van_bill_limit, pre_sale_limit, "
                      "pre_bill_limit, created_at) VALUES (?,?,?,?,?,?,?,?)",
                      (dst, r["name"], r["colour"], r["van_sale_limit"], r["van_bill_limit"], r["pre_sale_limit"],
                       r["pre_bill_limit"], db.now_iso()))
    db.audit(user, "competition.copy", f"{src} -> {dst}")
    return len(src_rows)


# =============================================================================== aliases
def aliases(month: str) -> dict:
    """SFA territory names with sales in `month` that match no hierarchy territory, plus the aliases already set."""
    _check_month(month)
    c = db.conn()
    terrs = [dict(r) for r in c.execute("SELECT id, label, sfa_territory, is_smmt FROM hierarchy_nodes WHERE month=? AND level=6 "
                                        "ORDER BY label COLLATE NOCASE", (month,))]
    known = {key(t["sfa_territory"] or t["label"]) for t in terrs}
    sales = c.execute("SELECT territory, COUNT(DISTINCT date) days, SUM(sales_value) v FROM sku_lines WHERE date LIKE ? "
                      "GROUP BY territory ORDER BY territory COLLATE NOCASE", (month + "%",)).fetchall()
    seen, unmatched = set(), []
    for r in sales:
        k = key(r["territory"])
        if k in known or k in seen:
            continue
        seen.add(k)
        # suggest the hierarchy territory whose name is closest
        best = max(terrs, key=lambda t: _similar(k, key(t["label"])), default=None)
        unmatched.append({"name": r["territory"], "days": r["days"], "value": r["v"] or 0,
                          "suggest": best["id"] if best and _similar(k, key(best["label"])) >= 0.6 else None})
    sfa_names = {key(r["territory"]) for r in sales}
    no_sales = [t for t in terrs if key(t["sfa_territory"] or t["label"]) not in sfa_names]
    return {"month": month, "territories": terrs, "unmatched": unmatched,
            "aliases": [t for t in terrs if t["sfa_territory"] and key(t["sfa_territory"]) != key(t["label"])], "no_sales": no_sales,
            "has_targets": bool(terrs), "sales_names": len(sales)}


def _similar(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()


def set_alias(node_id: int, sfa_name: str | None, user: str | None = None) -> None:
    with db.tx() as c:
        n = _node(c, node_id)
        if n["level"] != 6:
            raise PlanningError("Aliases are set on territories")
        # the alias applies to every month that still has this territory without its own alias
        c.execute("UPDATE hierarchy_nodes SET sfa_territory=? WHERE id=?", ((sfa_name or "").strip() or None, n["id"]))
    db.audit(user, "aliases.set", f"{n['label']} ({n['month']}) = {sfa_name or '—'}")


# =============================================================================== outlet categories
def outlets(month: str | None = None) -> list[dict]:
    c = db.conn()
    cats = {r["category_key"]: dict(r) for r in c.execute("SELECT * FROM outlet_categories")}
    q = "SELECT LOWER(TRIM(outlet_classification)) k, MIN(outlet_classification) label, COUNT(*) n, SUM(sales_value) v " \
        "FROM sku_lines WHERE outlet_classification IS NOT NULL AND TRIM(outlet_classification)!=''"
    args: tuple = ()
    if month:
        q += " AND date LIKE ?"
        args = (month + "%",)
    for r in c.execute(q + " GROUP BY k", args):
        x = cats.setdefault(r["k"], {"category_key": r["k"], "label": r["label"], "pricing_scheme": None,
                                     "include_in_competition": None, "updated_at": None})
        x["lines"], x["value"] = r["n"], r["v"] or 0
    for x in cats.values():
        x.setdefault("lines", 0)
        x.setdefault("value", 0)
        if x["include_in_competition"] is None:          # new category, not decided yet: counts by default
            x["include_in_competition"] = 1
            x["new"] = True
    return sorted(cats.values(), key=lambda x: (-x["value"], x["label"].lower()))


def set_outlet(category_key: str, label: str, include: bool, user: str | None = None) -> None:
    k = (category_key or "").strip().lower()
    if not k:
        raise PlanningError("Missing category")
    with db.tx() as c:
        c.execute("INSERT INTO outlet_categories(category_key, label, include_in_competition, updated_at) VALUES (?,?,?,?) "
                  "ON CONFLICT(category_key) DO UPDATE SET include_in_competition=excluded.include_in_competition, "
                  "updated_at=excluded.updated_at", (k, label or k, 1 if include else 0, db.now_iso()))
    db.audit(user, "outlets.set", f"{label}: {'counts' if include else 'excluded'}")
