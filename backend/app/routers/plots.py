from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..config import EUDR_CUTOFF, SATELLITE_MODE
from ..db import get_db
from ..models import Plot, User
from ..schemas import OverlapIn, PlotCreate, PlotUpdate, WitnessIn
from ..security import require
from ..services import analysis as analysis_svc
from ..services import audit, geo, readiness, traces
from ..services import plots as svc

router = APIRouter(prefix="/api/plots", tags=["Kebun"])
EDIT = ("koperasi",)
FULL_DETAIL = ("koperasi", "verifikator", "admin")


def _for_role(d: dict, user: User) -> dict:
    """Minimasi data: pengepul dan pabrik cukup tahu JENIS bukti lahan dan statusnya, bukan nomor surat,
    catatan sengketa, atau nama lengkap saksi (lihat docs/DPIA.md)."""
    if user.role in FULL_DETAIL:
        return d
    d["land"] = {**d["land"], "ref": None, "stdb_number": None, "dispute_note": None}
    d["witness"] = svc.mask_name(d["witness"]) if d.get("witness") else None
    d["witnesses"] = [{**w, "name": svc.mask_name(w["name"])} for w in d.get("witnesses") or []]
    return d


def _get(db: Session, plot_id: int) -> Plot:
    p = db.get(Plot, plot_id)
    if not p:
        raise HTTPException(404, "Kebun tidak ditemukan")
    return p


@router.get("")
def list_plots(db: Session = Depends(get_db), _: User = Depends(require())):
    plots = db.scalars(select(Plot).options(selectinload(Plot.farmer)).order_by(Plot.id)).all()
    pending = svc.pending_inspections(db)
    return [svc.plot_summary(p, pending) for p in plots]


@router.get("/protected-areas")
def protected_areas():
    return [{k: v for k, v in pa.items()} for pa in analysis_svc.protected_areas()]


@router.post("/check-overlap")
def check_overlap(body: OverlapIn, db: Session = Depends(get_db), _: User = Depends(require(*EDIT))):
    """Dipanggil saat petani menggambar: tumpang tindih kebun lain + status kawasan hutan (peta Kemenhut)."""
    geom = body.geometry.model_dump()
    policy = None
    if body.exclude_plot_id:
        p = db.get(Plot, body.exclude_plot_id)
        policy = svc.kawasan_policy_for(p) if p else None
    return {
        "area_ha": round(geo.area_ha(geom), 3),
        "overlaps": svc.overlaps(db, geom, body.exclude_plot_id),
        "protected": analysis_svc.kawasan_check(geom, policy),
    }


@router.post("/fit-neighbors")
def fit_neighbors(body: OverlapIn, db: Session = Depends(get_db), _: User = Depends(require(*EDIT))):
    """Memotong bagian draf yang bertumpuk dengan kebun terdaftar, mengikuti batas tetangga."""
    try:
        return svc.fit_to_neighbors(db, body.geometry.model_dump(), body.exclude_plot_id)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


def _apply_fields(p: Plot, body: PlotCreate | PlotUpdate) -> None:
    if body.boundary_sides is not None:
        p.boundary_sides = {k: v.model_dump() for k, v in body.boundary_sides.items()}
    for f in ("land_proof", "land_proof_ref", "stdb_status", "stdb_number", "dispute", "dispute_note"):
        v = getattr(body, f)
        if v is not None:
            setattr(p, f, v.strip() if isinstance(v, str) else v)


@router.post("", status_code=201)
def create_plot(body: PlotCreate, db: Session = Depends(get_db), user: User = Depends(require(*EDIT))):
    geom = body.geometry.model_dump()
    try:
        g = geo.validate_polygon(geom)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    clashes = svc.overlaps(db, g)
    big = [c for c in clashes if c["overlap_ha"] >= 0.05]
    if big:
        return JSONResponse(status_code=409, content={
            "detail": "Batas kebun bertumpuk dengan kebun lain. Pakai 'Rapikan dengan kebun tetangga' atau musyawarahkan batasnya.",
            "overlaps": big,
        })
    farmer = svc.find_or_create_farmer(db, body.farmer_name.strip(), body.village.strip(), body.consent)
    next_num = (db.scalar(select(func.max(Plot.id))) or 0) + 1
    now = datetime.now().isoformat(timespec="seconds")
    wits = [{"name": w.name.strip(), "relation": w.relation.strip() or "saksi", "at": now} for w in body.witnesses]
    if body.witness and not wits:
        wits = [{"name": body.witness.strip(), "relation": "saksi", "at": now}]
    p = Plot(
        code=svc.make_code(next_num), farmer_id=farmer.id, label=body.label, geometry=g, area_ha=0,
        centroid_lat=0, centroid_lng=0, planting_year_declared=body.planting_year_declared,
        witness=wits[0]["name"] if wits else None, witnesses=wits, boundary_confirmed=bool(wits),
        delineation_method=body.delineation_method,
        scenario=analysis_svc.scenario_for(g, body.demo_scenario) if SATELLITE_MODE != "live" else None,
    )
    if body.gps:
        p.gps_lat, p.gps_lng, p.gps_accuracy_m = body.gps.lat, body.gps.lng, body.gps.accuracy_m
    _apply_fields(p, body)
    svc.set_geometry(p, g)
    db.add(p)
    db.flush()
    db.refresh(p)
    audit.log_user(db, user, "kebun_didaftarkan", "kebun", p.id,
                   f"Kebun {p.code} didaftarkan ({p.area_ha:.2f} ha, {len(wits)} saksi)",
                   {"area_ha": round(p.area_ha, 3), "method": p.delineation_method, "land_proof": p.land_proof,
                    "stdb": p.stdb_status, "gps": bool(body.gps)})
    a = svc.apply_analysis(db, p)
    audit.log_user(db, user, "cek_satelit", "kebun", p.id, f"Cek satelit: {a.headline}",
                   {"risk": a.risk_level, "source": a.data_source})
    db.commit()
    return svc.plot_detail(p, db)


@router.get("/{plot_id}")
def get_plot(plot_id: int, db: Session = Depends(get_db), user: User = Depends(require())):
    p = _get(db, plot_id)
    d = _for_role(svc.plot_detail(p, db), user)
    d["overlaps"] = svc.overlaps(db, p.geometry, p.id)
    return d


@router.patch("/{plot_id}")
def update_plot(plot_id: int, body: PlotUpdate, db: Session = Depends(get_db), user: User = Depends(require(*EDIT))):
    p = _get(db, plot_id)
    before = {"land_proof": p.land_proof, "stdb": p.stdb_status, "dispute": p.dispute, "area_ha": round(p.area_ha, 3)}
    reanalyze = False
    if body.geometry is not None:
        try:
            g = geo.validate_polygon(body.geometry.model_dump())
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        big = [c for c in svc.overlaps(db, g, p.id) if c["overlap_ha"] >= 0.05]
        if big:  # aturan yang sama dengan pendaftaran kebun baru
            return JSONResponse(status_code=409, content={
                "detail": "Batas baru bertumpuk dengan kebun lain. Pakai 'Rapikan dengan kebun tetangga' atau musyawarahkan batasnya.",
                "overlaps": big,
            })
        svc.set_geometry(p, g)
        if SATELLITE_MODE != "live":  # deret NDVI simulasi harus mengikuti lokasi baru, bukan lokasi lama
            p.scenario = analysis_svc.scenario_for(g, None, svc.kawasan_policy_for(p))
        reanalyze = True
    if body.planting_year_declared is not None:
        p.planting_year_declared = body.planting_year_declared
    if body.witness is not None and body.witness.strip():
        p.witnesses = readiness.witness_list(p) + [
            {"name": body.witness.strip(), "relation": "saksi", "at": datetime.now().isoformat(timespec="seconds")}]
        p.witness = p.witness or body.witness.strip()
        p.boundary_confirmed = True
    if body.boundary_confirmed is not None and readiness.witness_list(p):
        p.boundary_confirmed = body.boundary_confirmed
    if body.label is not None:
        p.label = body.label
    _apply_fields(p, body)
    after = {"land_proof": p.land_proof, "stdb": p.stdb_status, "dispute": p.dispute, "area_ha": round(p.area_ha, 3)}
    audit.log_user(db, user, "kebun_diubah", "kebun", p.id, f"Data kebun {p.code} diperbarui",
                   {"sebelum": before, "sesudah": after})
    if reanalyze:
        a = svc.apply_analysis(db, p)
        audit.log_user(db, user, "cek_satelit", "kebun", p.id, f"Cek satelit setelah batas diubah: {a.headline}",
                       {"risk": a.risk_level})
    db.commit()
    db.refresh(p)
    return svc.plot_detail(p, db)


@router.post("/{plot_id}/witnesses")
def add_witness(plot_id: int, body: WitnessIn, db: Session = Depends(get_db), user: User = Depends(require(*EDIT))):
    p = _get(db, plot_id)
    wits = readiness.witness_list(p)
    if any(w["name"].lower() == body.name.strip().lower() for w in wits):
        raise HTTPException(409, "Saksi ini sudah tercatat.")
    wits.append({"name": body.name.strip(), "relation": body.relation.strip() or "saksi",
                 "at": datetime.now().isoformat(timespec="seconds")})
    p.witnesses = wits
    p.witness = p.witness or wits[0]["name"]
    p.boundary_confirmed = True
    audit.log_user(db, user, "saksi_batas", "kebun", p.id, f"{body.name.strip()} ({body.relation}) menyaksikan batas {p.code}")
    db.commit()
    db.refresh(p)
    return svc.plot_detail(p, db)


@router.post("/{plot_id}/analyze")
def analyze_plot(plot_id: int, db: Session = Depends(get_db), user: User = Depends(require("koperasi", "verifikator"))):
    p = _get(db, plot_id)
    a = svc.apply_analysis(db, p)
    audit.log_user(db, user, "cek_satelit", "kebun", p.id, f"Cek ulang satelit: {a.headline}",
                   {"risk": a.risk_level, "source": a.data_source})
    db.commit()
    db.refresh(p)
    return svc.plot_detail(p, db)


@router.get("/{plot_id}/passport")
def passport(plot_id: int, db: Session = Depends(get_db), _: User = Depends(require())):
    p = _get(db, plot_id)
    r = readiness.evaluate(p, p.id in svc.pending_inspections(db))
    return {
        "code": p.code,
        "qr_payload": f"PASPORKEBUN:{p.code}",  # QR hanya berisi kode, tanpa data pribadi
        "eudr_ready": r["ready"],
        "missing": [f"{c['label']}: {c['detail']}" for c in r["checks"] if not c["ok"]],
        "issued_at": datetime.now().isoformat(timespec="seconds"),
        "plot": svc.plot_summary(p),
    }


def eudr_feature(p: Plot) -> dict:
    return {
        "type": "Feature",
        "geometry": traces.to_traces_polygon(p.geometry),  # 6 desimal, tanpa titik kembar (aturan TRACES)
        "properties": {
            "ProducerCountry": "ID",
            "ProductionPlace": f"{p.label}, {p.farmer.village}",
            "Area": round(p.area_ha, 4),
            "PlotCode": p.code,
            "Commodity": "Oil palm (HS 1511)",
            "DeforestationCutOff": EUDR_CUTOFF.isoformat(),
            "RiskAssessment": p.risk_level,
            "AnalysisDate": p.analyzed_at.date().isoformat() if p.analyzed_at else None,
            "LandProof": p.land_proof,
            "STDB": p.stdb_status,
            "AnalysisMethod": ("PasporKebun convergence-of-evidence + COLD-lite Sentinel-2" if SATELLITE_MODE == "live" else
                               "PasporKebun convergence-of-evidence (JRC + SBTN + Hansen GFC); NDVI simulated in demo mode"),
        },
    }


@router.get("/{plot_id}/eudr.geojson")
def eudr_geojson(plot_id: int, db: Session = Depends(get_db), _: User = Depends(require())):
    p = _get(db, plot_id)
    fc = {"type": "FeatureCollection", "features": [eudr_feature(p)]}
    return JSONResponse(fc, headers={"Content-Disposition": f'attachment; filename="{p.code}.geojson"'})
