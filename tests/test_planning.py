"""Phase 5: targets editor, competition calendar, aliases, outlet categories (no sample files needed)."""
import os
import tempfile
from datetime import date

os.environ.setdefault("HYDRA_DATA_DIR", tempfile.mkdtemp(prefix="hydra_test_"))

import pytest  # noqa: E402

from app import db  # noqa: E402
from app.data import famulus  # noqa: E402
from app.services.sales_reports import planning as P  # noqa: E402
from app.services.sales_reports.reports import competition_for  # noqa: E402

M = "2031-03"   # a month no other test uses


def _tree(month):
    """National > Region > RSM > ASM > DTM > ASE(A) > [Alpha 1,000, Beta 2,000];  ASE(B) > [Gamma 500 SMMT]"""
    with db.tx() as c:
        for t in ("hierarchy_nodes", "target_months"):
            c.execute(f"DELETE FROM {t} WHERE month=?", (month,))
        c.execute("INSERT INTO target_months(month, status, source, created_at, updated_at) VALUES (?, 'draft', 'test', 'x', 'x')", (month,))
        ids, parent = {}, None
        for lvl, name in enumerate(["National", "West", "RSM W", "ASM W", "DTM W", "ASE A"]):
            parent = c.execute("INSERT INTO hierarchy_nodes(month,parent_id,level,sort_order,label) VALUES (?,?,?,?,?)",
                               (month, parent, lvl, lvl, name)).lastrowid
            ids[name] = parent
        ids["ASE B"] = c.execute("INSERT INTO hierarchy_nodes(month,parent_id,level,sort_order,label) VALUES (?,?,5,50,'ASE B')",
                                 (month, ids["DTM W"])).lastrowid
        for name, par, tgt, smmt, so in (("Alpha", "ASE A", 1000, 0, 10), ("Beta", "ASE A", 2000, 0, 11), ("Gamma", "ASE B", 500, 1, 51)):
            ids[name] = c.execute("INSERT INTO hierarchy_nodes(month,parent_id,level,sort_order,label,target,is_smmt,is_operating) "
                                  "VALUES (?,?,6,?,?,?,?,1)", (month, ids[par], so, name, tgt, smmt)).lastrowid
    return ids


def _nat(month):
    t = famulus.month_tree(month)["tree"][0]
    return t["gt"], t["smmt"]


@pytest.fixture()
def ids():
    db.init()
    return _tree(M)


def test_edit_targets_and_flags(ids):
    assert _nat(M) == (3000, 500)
    P.update_nodes([{"id": ids["Alpha"], "target": "1,500"}, {"id": ids["Gamma"], "is_smmt": False}], "t")
    assert _nat(M) == (4000, 0)
    with pytest.raises(P.PlanningError):
        P.update_nodes([{"id": ids["ASE A"], "target": 5}])          # targets live on territories only
    with pytest.raises(P.PlanningError):
        P.update_nodes([{"id": ids["Beta"], "target": -1}])
    # all-or-nothing: the good change in a failing batch is not saved
    with pytest.raises(P.PlanningError):
        P.update_nodes([{"id": ids["Beta"], "target": 9}, {"id": ids["Beta"], "target": "abc"}])
    assert _nat(M) == (4000, 0)
    assert db.conn().execute("SELECT national_total FROM target_months WHERE month=?", (M,)).fetchone()[0] == 4000


def test_add_move_delete(ids):
    nid = P.add_node(ids["ASE B"], "Delta", 700)
    assert _nat(M) == (3700, 500)
    with pytest.raises(P.PlanningError):
        P.add_node(ids["ASE A"], "delta")                           # duplicate territory name
    P.move_node(ids["Beta"], ids["ASE B"])
    tree = famulus.month_tree(M)["tree"][0]
    ase = {n["label"]: n for n in tree["children"][0]["children"][0]["children"][0]["children"][0]["children"]}
    assert [k["label"] for k in ase["ASE B"]["children"]] == ["Gamma", "Delta", "Beta"]
    assert ase["ASE A"]["gt"] == 1000 and ase["ASE B"]["gt"] == 2700
    with pytest.raises(P.PlanningError):
        P.move_node(ids["Beta"], ids["DTM W"])                      # a territory must sit under an ASE
    with pytest.raises(P.PlanningError):
        P.delete_node(ids["ASE B"])                                 # still has territories
    P.delete_node(nid)
    assert _nat(M) == (3000, 500)
    assert [p["label"] for p in P.parents_for(M, 6)] == ["ASE A", "ASE B"]


def test_copy_lock_and_delete_month(ids):
    P.update_nodes([{"id": ids["Alpha"], "sfa_territory": "Alpha Town"}])
    dst = "2031-04"
    if db.conn().execute("SELECT 1 FROM target_months WHERE month=?", (dst,)).fetchone():
        P.set_locked(dst, False)
        P.delete_month(dst)
    assert P.copy_month(M, dst, keep_targets=False) == 10
    assert _nat(dst) == (0, 0)
    assert db.conn().execute("SELECT sfa_territory FROM hierarchy_nodes WHERE month=? AND label='Alpha'", (dst,)).fetchone()[0] == "Alpha Town"
    with pytest.raises(P.PlanningError):
        P.copy_month(M, dst)                                        # already exists
    P.set_locked(dst, True)
    with pytest.raises(P.PlanningError):
        P.update_nodes([{"id": db.conn().execute("SELECT id FROM hierarchy_nodes WHERE month=? AND label='Alpha'", (dst,)).fetchone()[0], "target": 1}])
    P.set_locked(dst, False)
    P.delete_month(dst)
    assert not db.conn().execute("SELECT 1 FROM hierarchy_nodes WHERE month=?", (dst,)).fetchone()


def test_competition_calendar(ids):
    with db.tx() as c:
        c.execute("DELETE FROM competition_rounds WHERE month IN (?, '2031-05')", (M,))
    assert competition_for(date(2031, 3, 3))[0] is True            # no rounds -> every day, default limits
    r1 = P.save_round(M, {"name": "Round 1", "colour": "#2E7D5B", "van_sale_limit": "90,000", "van_bill_limit": 18,
                          "pre_sale_limit": 120000, "pre_bill_limit": 25})
    r2 = P.save_round(M, {"name": "Round 2", "van_sale_limit": 110000, "van_bill_limit": 22, "pre_sale_limit": 130000, "pre_bill_limit": 30})
    with pytest.raises(P.PlanningError):
        P.save_round(M, {"name": "", "van_sale_limit": 1, "van_bill_limit": 1, "pre_sale_limit": 1, "pre_bill_limit": 1})
    assert P.save_days(M, {"2031-03-03": r1, "2031-03-04": r1, "2031-03-17": r2, "2031-03-18": None}) == 3
    is_day, lim, name = competition_for(date(2031, 3, 3))
    assert is_day and name == "Round 1" and lim["van"] == (90000, 18)
    assert competition_for(date(2031, 3, 17))[1]["pre"] == (130000, 30)
    assert competition_for(date(2031, 3, 10))[0] is False          # rounds exist, day not in any
    with pytest.raises(P.PlanningError):
        P.save_days(M, {"2031-04-01": r1})
    m = P.rounds(M)
    assert [len(r["days"]) for r in m["rounds"]] == [2, 1] and m["sundays"] == 5 and m["days_in_month"] == 31
    assert P.copy_rounds(M, "2031-05") == 2
    assert [r["days"] for r in P.rounds("2031-05")["rounds"]] == [[], []]
    P.delete_round(r2)
    assert competition_for(date(2031, 3, 17))[0] is False


def test_aliases_and_outlets(ids):
    with db.tx() as c:
        c.execute("DELETE FROM imports WHERE sha256='plan-test'")
        imp = c.execute("INSERT INTO imports(kind,file_name,sha256,rows,imported_at) VALUES ('sku','t','plan-test',0,'x')").lastrowid
        for terr, oc, v in (("Alpha", "Groceries - Large", 100), ("Betaa", "SMMT Outlets", 50), ("Gamma", "Groceries - Large", 10)):
            c.execute("INSERT INTO sku_lines(import_id,date,territory,outlet_classification,sales_value) VALUES (?,?,?,?,?)",
                      (imp, M + "-03", terr, oc, v))
    a = P.aliases(M)
    assert [u["name"] for u in a["unmatched"]] == ["Betaa"]
    assert a["unmatched"][0]["suggest"] == ids["Beta"]             # closest name suggested
    assert [t["label"] for t in a["no_sales"]] == ["Beta"]
    P.set_alias(ids["Beta"], "Betaa")
    a = P.aliases(M)
    assert not a["unmatched"] and not a["no_sales"] and [x["label"] for x in a["aliases"]] == ["Beta"]
    out = {o["category_key"]: o for o in P.outlets(M)}
    assert out["smmt outlets"]["include_in_competition"] == 1
    P.set_outlet("smmt outlets", "SMMT Outlets", False)
    assert {o["category_key"]: o for o in P.outlets(M)}["smmt outlets"]["include_in_competition"] == 0
