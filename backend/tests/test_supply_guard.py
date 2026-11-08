from datetime import datetime, timedelta

from app.services.supply_guard import PlotInfo, TxnInfo, check_transaction, score_collectors

NOW = datetime(2026, 10, 15, 10, 0)
PLOT = PlotInfo("PK-00001-F", 2.0, 2008, "rendah")


def test_normal_sale_accepted():
    hist = [TxnInfo(1100, 1, NOW - timedelta(days=13), "diterima")]
    r = check_transaction(PLOT, hist, 1150, 1, NOW)
    assert r.decision == "diterima"


def test_over_capacity_is_held():
    r = check_transaction(PLOT, [], 12000, 1, NOW)
    assert r.decision == "ditahan"
    assert any(f.code == "MELEBIHI_KAPASITAS" for f in r.flags)


def test_risky_plot_held():
    r = check_transaction(PlotInfo("X", 2, 2008, "tinggi"), [], 500, 1, NOW)
    assert r.decision == "ditahan"


def test_young_palm_cannot_be_harvested():
    r = check_transaction(PlotInfo("X", 2, NOW.year - 1, "rendah"), [], 300, 1, NOW)
    assert any(f.code == "BELUM_MASA_PANEN" for f in r.flags)


def test_rapid_resale_and_multi_collector():
    hist = [TxnInfo(800, 2, NOW - timedelta(days=2), "diterima"), TxnInfo(800, 1, NOW - timedelta(days=5), "diterima")]
    r = check_transaction(PLOT, hist, 700, 1, NOW)
    codes = {f.code for f in r.flags}
    assert {"PANEN_TERLALU_RAPAT", "MULTI_PENGEPUL"} <= codes
    assert r.decision == "catatan"


def test_isolation_forest_ranks_launderer_highest():
    base = {"kg_per_ha_month": 1100, "flagged_share": 0.02, "untraced_share": 0.06, "near_cap_share": 0.0, "txn_per_plot_month": 2.4}
    feats = {i: {k: v * (1 + 0.05 * (i % 3)) for k, v in base.items()} for i in range(1, 8)}
    feats[8] = {"kg_per_ha_month": 2600, "flagged_share": 0.35, "untraced_share": 0.6, "near_cap_share": 0.4, "txn_per_plot_month": 5}
    s = score_collectors(feats)
    assert max(s, key=lambda k: s[k]["score"]) == 8
    assert s[8]["level"] == "tinggi" and s[8]["reasons"]
