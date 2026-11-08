"""Layanan rantai pasok: pencatatan transaksi pengepul & statistik dashboard pabrik."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Collector, Delivery, Plot, Transaction
from . import supply_guard
from .plots import effective_planting_year


def plot_info(p: Plot) -> supply_guard.PlotInfo:
    return supply_guard.PlotInfo(p.code, p.area_ha, effective_planting_year(p), p.risk_level, p.boundary_confirmed)


def history_for(db: Session, plot_id: int, until: datetime) -> list[supply_guard.TxnInfo]:
    rows = db.scalars(
        select(Transaction).where(Transaction.plot_id == plot_id, Transaction.created_at >= until - timedelta(days=31),
                                  Transaction.created_at <= until)
    ).all()
    return [supply_guard.TxnInfo(t.weight_kg, t.collector_id, t.created_at, t.decision) for t in rows]


def record(db: Session, p: Plot, collector_id: int, weight_kg: float, when: datetime) -> tuple[Transaction, supply_guard.CheckResult]:
    res = supply_guard.check_transaction(plot_info(p), history_for(db, p.id, when), weight_kg, collector_id, when)
    t = Transaction(plot_id=p.id, collector_id=collector_id, weight_kg=weight_kg, created_at=when, decision=res.decision,
                    flags=[f.__dict__ for f in res.flags], capacity_used_pct=res.capacity_used_pct)
    db.add(t)
    db.flush()
    return t, res


def txn_dict(t: Transaction) -> dict:
    return {
        "id": t.id,
        "plot_code": t.plot.code,
        "plot_id": t.plot_id,
        "farmer": t.plot.farmer.name,
        "collector_id": t.collector_id,
        "collector": t.collector.name,
        "weight_kg": round(t.weight_kg),
        "created_at": t.created_at.isoformat(timespec="minutes"),
        "decision": t.decision,
        "flags": t.flags,
        "capacity_used_pct": t.capacity_used_pct,
    }


def collector_features_from(txns: list[Transaction], dels: list[Delivery], collectors: list[Collector], now: datetime,
                            days: int = 90) -> tuple[dict[int, dict], dict[int, dict]]:
    """Fitur perilaku pengepul 90 hari terakhir (input untuk Isolation Forest)."""
    since = now - timedelta(days=days)
    months = days / 30
    txns = [t for t in txns if t.created_at >= since]
    dels = [d for d in dels if d.created_at >= since]
    by_c: dict[int, list[Transaction]] = defaultdict(list)
    for t in txns:
        by_c[t.collector_id].append(t)
    delivered: dict[int, float] = defaultdict(float)
    for d in dels:
        delivered[d.collector_id] += d.weight_kg

    feats: dict[int, dict] = {}
    stats: dict[int, dict] = {}
    for c in collectors:
        ts = by_c.get(c.id, [])
        accepted = sum(t.weight_kg for t in ts if t.decision != "ditahan")
        held = sum(t.weight_kg for t in ts if t.decision == "ditahan")
        plots = {t.plot_id: t.plot.area_ha for t in ts}
        area = sum(plots.values()) or 1.0
        n = max(len(ts), 1)
        dv = delivered.get(c.id, 0.0)
        feats[c.id] = {
            "kg_per_ha_month": accepted / area / months,
            "flagged_share": sum(t.decision != "diterima" for t in ts) / n,
            "untraced_share": max(0.0, min(1.0, (dv - accepted) / dv)) if dv > 0 else 0.0,
            "near_cap_share": sum(t.capacity_used_pct > 85 for t in ts) / n,
            "txn_per_plot_month": len(ts) / max(len(plots), 1) / months,
        }
        stats[c.id] = {"delivered_kg": round(dv), "traced_kg": round(accepted), "held_kg": round(held),
                       "n_txn": len(ts), "n_plots": len(plots), "flagged": sum(t.decision != "diterima" for t in ts)}
    return feats, stats
