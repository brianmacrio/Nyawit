from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Collector, Plot, Transaction, User
from ..schemas import TransactionIn
from ..security import rate_limit, require
from ..services import audit, readiness
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
def collectors(db: Session = Depends(get_db), _: User = Depends(require())):
    return [{"id": c.id, "name": c.name, "village": c.village} for c in db.scalars(select(Collector).order_by(Collector.id))]


@router.get("/public/passport/{code}", dependencies=[Depends(rate_limit("public", 60, 60))])
def public_passport(code: str, db: Session = Depends(get_db)):
    """Cek paspor tanpa login (untuk pembeli/publik yang memindai QR). Nama petani disamarkan."""
    p = _plot_by_code(db, code)
    r = readiness.evaluate(p, p.id in plot_svc.pending_inspections(db))
    return {
        "code": p.code, "farmer": plot_svc.mask_name(p.farmer.name), "village": p.farmer.village,
        "area_ha": round(p.area_ha, 2), "risk_level": p.risk_level, "risk_headline": p.risk_headline,
        "eudr_ready": r["ready"], "checks": [{"label": c["label"], "ok": c["ok"]} for c in r["checks"]],
        "valid_until": r["valid_until"], "analyzed_at": p.analyzed_at.isoformat(timespec="seconds") if p.analyzed_at else None,
        "precision": r["precision"]["label"],
        "note": "Paspor Kebun adalah bukti uji tuntas, bukan sertifikat ISPO/RSPO.",
    }


@router.get("/passport/{code}")
def lookup_passport(code: str, db: Session = Depends(get_db), _: User = Depends(require("pengepul", "pabrik"))):
    """Dipanggil saat pengepul memindai QR: status kebun + sisa kapasitas 30 hari."""
    p = _plot_by_code(db, code)
    now = datetime.now()
    hist = svc.history_for(db, p.id, now)
    used = sum(h.weight_kg for h in hist if h.decision != "ditahan" and h.created_at >= now - timedelta(days=30))
    cap = monthly_capacity_kg(p.area_ha, plot_svc.effective_planting_year(p), now.month)
    last = max((h.created_at for h in hist if h.decision != "ditahan"), default=None)
    return {
        "plot": plot_svc.plot_summary(p, plot_svc.pending_inspections(db)),
        "capacity": {**cap, "used_kg_30d": round(used), "remaining_kg": max(0, round(cap["upper_kg_30d"] - used))},
        "last_sale": last.isoformat(timespec="minutes") if last else None,
        "days_since_last_sale": (now - last).days if last else None,
    }


@router.post("/transactions", status_code=201)
def create_transaction(body: TransactionIn, db: Session = Depends(get_db), user: User = Depends(require("pengepul"))):
    p = _plot_by_code(db, body.plot_code)
    # pengepul hanya bisa mencatat atas nama usahanya sendiri; admin boleh memilih (untuk demo)
    cid = user.collector_id if user.role == "pengepul" else (body.collector_id or user.collector_id)
    if not cid or not db.get(Collector, cid):
        raise HTTPException(404, "Pengepul tidak ditemukan")
    when = datetime.now() if user.role == "pengepul" else (body.created_at or datetime.now())
    t, res = svc.record(db, p, cid, body.weight_kg, when)
    if res.decision != "diterima":
        audit.log_user(db, user, "transaksi_ditandai", "kebun", p.id,
                       f"Pembelian {round(body.weight_kg):,} kg dari {p.code}: {res.decision}",
                       {"collector_id": cid, "flags": [f.code for f in res.flags]})
    db.commit()
    db.refresh(t)
    return {"transaction": svc.txn_dict(t), "check": res.to_dict(),
            "plot": plot_svc.plot_summary(p)}


@router.get("/transactions")
def list_transactions(collector_id: int | None = None, limit: int = Query(30, le=200), db: Session = Depends(get_db),
                      user: User = Depends(require("pengepul", "pabrik", "verifikator"))):
    if user.role == "pengepul":
        collector_id = user.collector_id
    q = select(Transaction).order_by(Transaction.created_at.desc()).limit(limit)
    if collector_id:
        q = q.where(Transaction.collector_id == collector_id)
    return [svc.txn_dict(t) for t in db.scalars(q)]
