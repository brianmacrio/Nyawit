from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import UPLOAD_DIR
from ..db import get_db
from ..models import Appeal, Inspection, Plot, User
from ..schemas import AppealDecisionIn, AppealIn, InspectionResultIn, SampleIn
from ..security import rate_limit, require
from ..services import audit
from ..services import plots as plot_svc
from ..services import verification as svc

router = APIRouter(prefix="/api", tags=["Verifikasi"])


@router.get("/inspections")
def list_inspections(status: str | None = None, db: Session = Depends(get_db),
                     _: User = Depends(require("verifikator", "koperasi", "pabrik"))):
    q = select(Inspection).options(selectinload(Inspection.plot).selectinload(Plot.farmer)).order_by(
        Inspection.status, Inspection.id.desc())
    if status in ("menunggu", "selesai"):
        q = q.where(Inspection.status == status)
    rows = db.scalars(q).all()
    n_plots = db.query(Plot).count()
    return {"sample_size": svc.sample_size(n_plots), "n_plots": n_plots,
            "formula": "akar(n) x 2,5 x 1,5 (Standar Petani Swadaya RSPO 2024)",
            "items": [svc.inspection_dict(i) for i in rows]}


@router.post("/inspections/sample")
def make_sample(body: SampleIn, db: Session = Depends(get_db), user: User = Depends(require("verifikator"))):
    batch = body.batch or datetime.now().strftime("%Y-%m")
    made = svc.generate_sample(db, batch)
    audit.log_user(db, user, "sampel_inspeksi", "inspeksi", None,
                   f"Sampel inspeksi {batch}: {len(made)} kebun dipilih berbasis risiko",
                   {"plots": [i.plot_id for i in made]})
    db.commit()
    return {"created": len(made), "batch": batch}


@router.post("/inspections/{inspection_id}/result", dependencies=[Depends(rate_limit("upload", 20, 60))])
def inspection_result(inspection_id: int, body: InspectionResultIn, db: Session = Depends(get_db),
                      user: User = Depends(require("verifikator"))):
    i = db.get(Inspection, inspection_id)
    if not i:
        raise HTTPException(404, "Inspeksi tidak ditemukan")
    if i.status == "selesai":
        raise HTTPException(409, "Inspeksi ini sudah selesai.")
    try:
        warnings = svc.complete(db, i, body.result, (body.notes or "").strip() or None, user.display_name, body.photo,
                                body.lat, body.lng)
    except svc.PhotoError as e:
        raise HTTPException(422, str(e)) from e
    audit.log_user(db, user, "inspeksi_selesai", "kebun", i.plot_id,
                   f"Inspeksi lapangan {i.plot.code}: {'sesuai' if body.result == 'sesuai' else 'TIDAK sesuai'}",
                   {"inspection_id": i.id, "photo": bool(i.photo_path), "distance_m": i.photo_distance_m})
    db.commit()
    return {"inspection": svc.inspection_dict(i), "warnings": warnings}


@router.get("/inspections/{inspection_id}/photo")
def inspection_photo(inspection_id: int, db: Session = Depends(get_db),
                     _: User = Depends(require("verifikator", "koperasi", "pabrik"))):
    i = db.get(Inspection, inspection_id)
    if not i or not i.photo_path:
        raise HTTPException(404, "Foto tidak ada")
    f = (UPLOAD_DIR / i.photo_path).resolve()
    if not f.is_relative_to(UPLOAD_DIR.resolve()) or not f.exists():
        raise HTTPException(404, "Foto tidak ada")
    return FileResponse(f, media_type="image/jpeg")


@router.get("/appeals")
def list_appeals(db: Session = Depends(get_db), _: User = Depends(require("verifikator", "koperasi", "pabrik"))):
    rows = db.scalars(select(Appeal).options(selectinload(Appeal.plot).selectinload(Plot.farmer))
                      .order_by(Appeal.status != "diajukan", Appeal.id.desc())).all()
    return [plot_svc.appeal_dict(a) for a in rows]


@router.post("/appeals", status_code=201)
def create_appeal(body: AppealIn, db: Session = Depends(get_db), user: User = Depends(require("koperasi"))):
    p = db.get(Plot, body.plot_id)
    if not p:
        raise HTTPException(404, "Kebun tidak ditemukan")
    if p.risk_level == "rendah":
        raise HTTPException(409, "Kebun ini sudah berstatus aman; tidak ada yang perlu diajukan keberatan.")
    if db.scalar(select(Appeal).where(Appeal.plot_id == p.id, Appeal.status == "diajukan")):
        raise HTTPException(409, "Masih ada keberatan yang belum diputuskan untuk kebun ini.")
    a = Appeal(plot_id=p.id, submitted_by=user.display_name, reason=body.reason.strip(),
               evidence_type=body.evidence_type, original_risk=p.risk_level)
    db.add(a)
    db.flush()
    audit.log_user(db, user, "keberatan_diajukan", "kebun", p.id,
                   f"Keberatan atas status {p.code} ({svc.EVIDENCE_LABEL[body.evidence_type]})")
    db.commit()
    db.refresh(a)
    return plot_svc.appeal_dict(a)


@router.post("/appeals/{appeal_id}/decide")
def decide(appeal_id: int, body: AppealDecisionIn, db: Session = Depends(get_db), user: User = Depends(require("verifikator"))):
    a = db.get(Appeal, appeal_id)
    if not a:
        raise HTTPException(404, "Keberatan tidak ditemukan")
    if a.status != "diajukan":
        raise HTTPException(409, "Keberatan ini sudah diputuskan.")
    if body.accept and not body.new_risk:
        raise HTTPException(422, "Pilih status baru bila keberatan diterima.")
    before = a.plot.risk_level
    svc.decide_appeal(db, a, body.accept, body.note.strip(), body.new_risk, user.display_name)
    audit.log_user(db, user, "keberatan_diputuskan", "kebun", a.plot_id,
                   f"Keberatan {a.plot.code} {a.status}: {before} -> {a.plot.risk_level}",
                   {"appeal_id": a.id, "note": a.decision_note})
    db.commit()
    db.refresh(a)
    return plot_svc.appeal_dict(a)


@router.get("/audit")
def audit_list(entity: str = "kebun", entity_id: int | None = None, limit: int = 50, db: Session = Depends(get_db),
               _: User = Depends(require("verifikator", "koperasi", "pabrik"))):
    """Riwayat kejadian. Pengepul tidak boleh membaca pembelian pengepul lain (minimasi data)."""
    if entity_id is None:
        from ..models import AuditEvent

        rows = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(min(limit, 200)))
        return [audit.event_dict(e) for e in rows]
    return audit.for_entity(db, entity, entity_id, min(limit, 200))


@router.get("/audit/verify")
def audit_verify(db: Session = Depends(get_db), _: User = Depends(require())):
    return audit.verify_chain(db)
