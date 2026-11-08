from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Collector, Plot, Transaction
from ..schemas import TransactionIn
from ..services import plots as plot_svc
from ..services import supply as svc
from ..services.yield_model import monthly_capacity_kg

router = APIRouter(prefix="/api", tags=["Pengepul"])


def _plot_by_code(db: Session, code: str) -> Plot:
    code = code.replace("PASPORKEBUN:", "")
    num, err = plot_svc.parse_code(code)
    if err:
        raise HTTPException(422, err)
    p = db.scalar(select(Plot).where(Plot.code == plot_svc.make_code(num)))
    if not p:
        raise HTTPException(404, "Paspor kebun tidak terdaftar")
    return p


@router.get("/collectors")
def collectors(db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name, "village": c.village} for c in db.scalars(select(Collector).order_by(Collector.id))]


@router.get("/passport/{code}")
def lookup_passport(code: str, collector_id: int | None = None, db: Session = Depends(get_db)):
    """Dipanggil saat pengepul memindai QR: status kebun + sisa kapasitas 30 hari."""
    p = _plot_by_code(db, code)
    now = datetime.now()
    hist = svc.history_for(db, p.id, now)
    used = sum(h.weight_kg for h in hist if h.decision != "ditahan" and h.created_at >= now - timedelta(days=30))
    cap = monthly_capacity_kg(p.area_ha, plot_svc.effective_planting_year(p), now.month)
    last = max((h.created_at for h in hist if h.decision != "ditahan"), default=None)
    return {
        "plot": plot_svc.plot_summary(p),
        "capacity": {**cap, "used_kg_30d": round(used), "remaining_kg": max(0, round(cap["upper_kg_30d"] - used))},
        "last_sale": last.isoformat(timespec="minutes") if last else None,
        "days_since_last_sale": (now - last).days if last else None,
    }


@router.post("/transactions", status_code=201)
def create_transaction(body: TransactionIn, db: Session = Depends(get_db)):
    p = _plot_by_code(db, body.plot_code)
    if not db.get(Collector, body.collector_id):
        raise HTTPException(404, "Pengepul tidak ditemukan")
    when = body.created_at or datetime.now()
    t, res = svc.record(db, p, body.collector_id, body.weight_kg, when)
    db.commit()
    db.refresh(t)
    return {"transaction": svc.txn_dict(t), "check": res.to_dict(),
            "plot": plot_svc.plot_summary(p)}


@router.get("/transactions")
def list_transactions(collector_id: int | None = None, limit: int = Query(30, le=200), db: Session = Depends(get_db)):
    q = select(Transaction).order_by(Transaction.created_at.desc()).limit(limit)
    if collector_id:
        q = q.where(Transaction.collector_id == collector_id)
    return [svc.txn_dict(t) for t in db.scalars(q)]
