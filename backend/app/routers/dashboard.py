from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import EUDR_APPLICATION
from ..db import get_db
from ..models import Collector, Delivery, Farmer, Plot, Transaction, User
from ..security import require
from ..services import readiness
from ..services import plots as plot_svc
from ..services import supply as supply_svc
from ..services.supply_guard import score_collectors
from .plots import eudr_feature

router = APIRouter(prefix="/api/dashboard", tags=["Pabrik"])


def _month_start(d: datetime, back: int) -> datetime:
    y, m = d.year, d.month - back
    while m <= 0:
        m += 12
        y -= 1
    return datetime(y, m, 1)


@router.get("")
def dashboard(db: Session = Depends(get_db), _: User = Depends(require("pabrik", "verifikator"))):
    """Satu query per tabel lalu diolah di memori (hemat I/O, < 100 ms untuk ribuan transaksi)."""
    t0 = time.perf_counter()
    now = datetime.now()
    plots = db.scalars(select(Plot).options(selectinload(Plot.farmer))).all()
    since = _month_start(now, 5)
    txns = db.scalars(
        select(Transaction).where(Transaction.created_at >= since)
        .options(selectinload(Transaction.plot).selectinload(Plot.farmer), selectinload(Transaction.collector))
    ).all()
    dels = db.scalars(select(Delivery).where(Delivery.created_at >= since)).all()
    collectors = db.scalars(select(Collector).order_by(Collector.id)).all()

    by_risk: dict[str, int] = defaultdict(int)
    for p in plots:
        by_risk[p.risk_level or "belum"] += 1
    pending = plot_svc.pending_inspections(db)
    evals = {p.id: readiness.evaluate(p, p.id in pending, now) for p in plots}
    ready = [p for p in plots if evals[p.id]["ready"]]
    blockers: dict[str, int] = defaultdict(int)
    for r in evals.values():
        for c in r["checks"]:
            if not c["ok"]:
                blockers[c["key"]] += 1

    since30 = now - timedelta(days=30)
    t30 = [t for t in txns if t.created_at >= since30]
    delivered30 = sum(d.weight_kg for d in dels if d.created_at >= since30)
    traced30 = sum(t.weight_kg for t in t30 if t.decision != "ditahan")
    held30 = sum(t.weight_kg for t in t30 if t.decision == "ditahan")

    monthly = []
    for back in range(5, -1, -1):
        start, end = _month_start(now, back), _month_start(now, back - 1) if back > 0 else now + timedelta(days=1)
        dv = sum(d.weight_kg for d in dels if start <= d.created_at < end)
        tx = [t for t in txns if start <= t.created_at < end]
        tr = sum(t.weight_kg for t in tx if t.decision != "ditahan")
        monthly.append({"month": start.strftime("%Y-%m"), "delivered_t": round(dv / 1000, 1),
                        "traced_t": round(min(tr, dv) / 1000, 1),
                        "held_t": round(sum(t.weight_kg for t in tx if t.decision == "ditahan") / 1000, 1),
                        "partial": back == 0})

    feats, stats = supply_svc.collector_features_from(txns, dels, collectors, now)
    scores = score_collectors(feats)
    rows = []
    for c in collectors:
        s, st = scores.get(c.id, {}), stats.get(c.id, {})
        dv = st.get("delivered_kg", 0)
        rows.append({
            "id": c.id, "name": c.name, "village": c.village, **st,
            "traced_share": round(min(st.get("traced_kg", 0) / dv, 1.0), 3) if dv else None,
            "ai_score": s.get("score"), "ai_level": s.get("level"), "ai_reasons": s.get("reasons", []),
            "features": s.get("features", {}),
        })
    rows.sort(key=lambda c: -(c["ai_score"] or 0))

    alerts = sorted((t for t in txns if t.decision != "diterima"), key=lambda t: t.created_at, reverse=True)[:12]
    supply90: dict[int, float] = defaultdict(float)
    for t in txns:
        if t.created_at >= now - timedelta(days=90) and t.decision != "ditahan":
            supply90[t.plot_id] += t.weight_kg

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "days_to_eudr": (EUDR_APPLICATION - now.date()).days,
        "kpi": {
            "plots": len(plots),
            "farmers": db.query(Farmer).count(),
            "area_ha": round(sum(p.area_ha for p in plots), 1),
            "risk": dict(by_risk),
            "eudr_ready": len(ready),
            "eudr_ready_share": round(len(ready) / len(plots), 3) if plots else 0,
            "blockers": dict(blockers),
            "traced_share_30d": round(min(traced30 / delivered30, 1), 3) if delivered30 else None,
            "delivered_t_30d": round(delivered30 / 1000, 1),
            "traced_t_30d": round(traced30 / 1000, 1),
            "held_t_30d": round(held30 / 1000, 1),
        },
        "monthly": monthly,
        "collectors": rows,
        "alerts": [supply_svc.txn_dict(t) for t in alerts],
        "supply_plots": [
            {"id": p.id, "code": p.code, "centroid": [p.centroid_lat, p.centroid_lng], "risk_level": p.risk_level,
             "kg_90d": round(supply90.get(p.id, 0))} for p in plots
        ],
        "compute_ms": int((time.perf_counter() - t0) * 1000),
    }


@router.get("/eudr.geojson")
def eudr_all(db: Session = Depends(get_db), _: User = Depends(require("pabrik"))):
    pending = plot_svc.pending_inspections(db)
    ps = [p for p in db.scalars(select(Plot)) if readiness.evaluate(p, p.id in pending)["ready"]]
    fc = {"type": "FeatureCollection", "features": [eudr_feature(p) for p in ps]}
    return JSONResponse(fc, headers={"Content-Disposition": 'attachment; filename="eudr_kebun_siap.geojson"'})
