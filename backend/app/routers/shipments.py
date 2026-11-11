from __future__ import annotations

from datetime import datetime, time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Shipment, User
from ..schemas import ShipmentIn
from ..security import require
from ..services import audit
from ..services import shipment as svc

router = APIRouter(prefix="/api/shipments", tags=["Pengiriman ekspor"])


@router.get("")
def list_shipments(db: Session = Depends(get_db), _: User = Depends(require("pabrik"))):
    return [svc.shipment_dict(s) for s in db.scalars(select(Shipment).order_by(Shipment.id.desc()))]


@router.post("", status_code=201)
def create_shipment(body: ShipmentIn, db: Session = Depends(get_db), user: User = Depends(require("pabrik"))):
    start = datetime.combine(body.period_start, time.min)
    end = datetime.combine(body.period_end, time.max)
    s = svc.build(db, body.buyer.strip(), body.destination.strip() or "Uni Eropa", start, end, user.display_name)
    sm = s.summary
    audit.log_user(db, user, "paket_ekspor", "pengiriman", s.id,
                   f"Paket {s.code} untuk {s.buyer}: {sm['n_included']} kebun masuk, {sm['n_excluded']} dikeluarkan",
                   {"included_kg": sm["included_kg"], "excluded_kg": sm["excluded_kg"]})
    db.commit()
    return svc.shipment_dict(s, full=True)


@router.get("/{shipment_id}")
def get_shipment(shipment_id: int, db: Session = Depends(get_db), _: User = Depends(require("pabrik"))):
    s = db.get(Shipment, shipment_id)
    if not s:
        raise HTTPException(404, "Pengiriman tidak ditemukan")
    return svc.shipment_dict(s, full=True)


@router.get("/{shipment_id}/package.zip")
def package(shipment_id: int, db: Session = Depends(get_db), _: User = Depends(require("pabrik"))):
    s = db.get(Shipment, shipment_id)
    if not s:
        raise HTTPException(404, "Pengiriman tidak ditemukan")
    return Response(svc.package_zip(s), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{s.code}_uji_tuntas.zip"'})
