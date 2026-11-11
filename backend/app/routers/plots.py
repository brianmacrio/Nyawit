from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import EUDR_CUTOFF, SATELLITE_MODE
from ..db import get_db
from ..models import Plot
from ..schemas import OverlapIn, PlotCreate, PlotUpdate
from ..services import analysis as analysis_svc
from ..services import plots as svc

router = APIRouter(prefix="/api/plots", tags=["Kebun"])


def _get(db: Session, plot_id: int) -> Plot:
    p = db.get(Plot, plot_id)
    if not p:
        raise HTTPException(404, "Kebun tidak ditemukan")
    return p


@router.get("")
def list_plots(db: Session = Depends(get_db)):
    plots = db.scalars(select(Plot).order_by(Plot.id)).all()
    return [svc.plot_summary(p) for p in plots]


@router.get("/protected-areas")
def protected_areas():
    return [{k: v for k, v in pa.items()} for pa in analysis_svc.protected_areas()]


@router.post("/check-overlap")
def check_overlap(body: OverlapIn, db: Session = Depends(get_db)):
    """Dipanggil saat petani menggambar: tumpang tindih kebun lain + status kawasan hutan (peta Kemenhut)."""
    geom = body.geometry.model_dump()
    from ..services import geo

    policy = None
    if body.exclude_plot_id:
        p = db.get(Plot, body.exclude_plot_id)
        policy = svc.kawasan_policy_for(p) if p else None
    return {
        "area_ha": round(geo.area_ha(geom), 3),
        "overlaps": svc.overlaps(db, geom, body.exclude_plot_id),
        "protected": analysis_svc.kawasan_check(geom, policy),
    }


@router.post("", status_code=201)
def create_plot(body: PlotCreate, db: Session = Depends(get_db)):
    geom = body.geometry.model_dump()
    try:
        from ..services import geo

        g = geo.validate_polygon(geom)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    clashes = svc.overlaps(db, g)
    big = [c for c in clashes if c["overlap_ha"] >= 0.05]
    if big:
        return JSONResponse(status_code=409, content={
            "detail": "Batas kebun bertumpuk dengan kebun lain. Selesaikan lewat musyawarah lalu perbaiki garis.",
            "overlaps": big,
        })
    farmer = svc.find_or_create_farmer(db, body.farmer_name.strip(), body.village.strip(), body.consent)
    next_num = (db.scalar(select(func.max(Plot.id))) or 0) + 1
    p = Plot(
        code=svc.make_code(next_num), farmer_id=farmer.id, label=body.label, geometry=g, area_ha=0,
        centroid_lat=0, centroid_lng=0, planting_year_declared=body.planting_year_declared, witness=body.witness,
        delineation_method=body.delineation_method, boundary_confirmed=bool(body.witness),
        scenario=analysis_svc.scenario_for(g, body.demo_scenario) if SATELLITE_MODE != "live" else None,
    )
    svc.set_geometry(p, g)
    db.add(p)
    db.flush()
    db.refresh(p)
    svc.apply_analysis(db, p)
    db.commit()
    return svc.plot_detail(p)


@router.get("/{plot_id}")
def get_plot(plot_id: int, db: Session = Depends(get_db)):
    p = _get(db, plot_id)
    d = svc.plot_detail(p)
    d["overlaps"] = svc.overlaps(db, p.geometry, p.id)
    return d


@router.patch("/{plot_id}")
def update_plot(plot_id: int, body: PlotUpdate, db: Session = Depends(get_db)):
    p = _get(db, plot_id)
    reanalyze = False
    if body.geometry is not None:
        svc.set_geometry(p, body.geometry.model_dump())
        reanalyze = True
    if body.planting_year_declared is not None:
        p.planting_year_declared = body.planting_year_declared
    if body.witness is not None:
        p.witness = body.witness
    if body.boundary_confirmed is not None:
        p.boundary_confirmed = body.boundary_confirmed
    if body.label is not None:
        p.label = body.label
    if reanalyze:
        svc.apply_analysis(db, p)
    db.commit()
    db.refresh(p)
    return svc.plot_detail(p)


@router.post("/{plot_id}/analyze")
def analyze_plot(plot_id: int, db: Session = Depends(get_db)):
    p = _get(db, plot_id)
    svc.apply_analysis(db, p)
    db.commit()
    db.refresh(p)
    return svc.plot_detail(p)


@router.get("/{plot_id}/passport")
def passport(plot_id: int, db: Session = Depends(get_db)):
    p = _get(db, plot_id)
    ready = p.risk_level == "rendah" and p.farmer.consent_given
    missing = []
    if p.risk_level != "rendah":
        missing.append("Status satelit belum aman")
    if not p.boundary_confirmed:
        missing.append("Batas kebun belum disaksikan kelompok tani")
    if not p.farmer.consent_given:
        missing.append("Belum ada persetujuan data dari petani")
    return {
        "code": p.code,
        "qr_payload": f"PASPORKEBUN:{p.code}",  # QR hanya berisi kode, tanpa data pribadi
        "eudr_ready": ready and p.boundary_confirmed,
        "missing": missing,
        "issued_at": datetime.now().isoformat(timespec="seconds"),
        "plot": svc.plot_summary(p),
    }


def eudr_feature(p: Plot) -> dict:
    a = p.analyses[0] if p.analyses else None
    return {
        "type": "Feature",
        "geometry": p.geometry,
        "properties": {
            "ProducerName": p.farmer.name if p.farmer.consent_given else "(disembunyikan)",
            "ProducerCountry": "ID",
            "ProductionPlace": f"{p.label}, {p.farmer.village}",
            "Area": round(p.area_ha, 4),
            "PlotCode": p.code,
            "Commodity": "Oil palm (HS 1511)",
            "DeforestationCutOff": EUDR_CUTOFF.isoformat(),
            "RiskAssessment": p.risk_level,
            "AnalysisDate": a.created_at.date().isoformat() if a else None,
            "AnalysisMethod": "PasporKebun convergence-of-evidence + COLD-lite Sentinel-2",
        },
    }


@router.get("/{plot_id}/eudr.geojson")
def eudr_geojson(plot_id: int, db: Session = Depends(get_db)):
    p = _get(db, plot_id)
    fc = {"type": "FeatureCollection", "features": [eudr_feature(p)]}
    return JSONResponse(fc, headers={"Content-Disposition": f'attachment; filename="{p.code}.geojson"'})
