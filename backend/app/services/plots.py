"""Logika domain kebun: kode paspor, serialisasi, dan penerapan hasil analisis."""
from __future__ import annotations

import string
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Analysis, Appeal, Farmer, Inspection, Plot
from . import analysis as analysis_svc
from . import audit, geo, readiness

_ALPHA = string.ascii_uppercase


def checksum(num: int) -> str:
    digits = f"{num:05d}"
    s = sum((i + 1) * int(d) for i, d in enumerate(digits))
    return _ALPHA[s % 26]


def make_code(num: int) -> str:
    return f"PK-{num:05d}-{checksum(num)}"


def parse_code(code: str) -> tuple[int | None, str | None]:
    """Mengembalikan (nomor, pesan_error). Menoleransi spasi/huruf kecil/tanpa tanda hubung."""
    c = code.strip().upper().replace(" ", "").replace("-", "")
    if not c.startswith("PK") or len(c) != 8 or not c[2:7].isdigit():
        return None, "Format kode paspor tidak dikenali (contoh: PK-00012-K)"
    num = int(c[2:7])
    if checksum(num) != c[7]:
        return None, "Kode paspor salah (huruf pemeriksa tidak cocok). Periksa salah ketik."
    return num, None


def effective_planting_year(p: Plot) -> int | None:
    return p.planting_year_declared or p.planting_year_detected


def planting_consistency(p: Plot) -> dict | None:
    if p.planting_year_declared and p.planting_year_detected:
        diff = p.planting_year_detected - p.planting_year_declared
        if abs(diff) >= 4:
            return {"declared": p.planting_year_declared, "detected": p.planting_year_detected,
                    "message": f"Petani menyebut tanam {p.planting_year_declared}, citra satelit memperkirakan "
                               f"{p.planting_year_detected}. Selisih {abs(diff)} tahun perlu dikonfirmasi."}
    return None


def mask_name(name: str) -> str:
    """'Budi Santoso' -> 'Budi S.' untuk tampilan publik (minimasi data pribadi)."""
    parts = name.split()
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][0]}."


def pending_inspections(db: Session) -> set[int]:
    return set(db.scalars(select(Inspection.plot_id).where(Inspection.status == "menunggu")))


def plot_summary(p: Plot, pending: set[int] | None = None) -> dict:
    d = _summary(p)
    if pending is not None:
        r = readiness.evaluate(p, p.id in pending)
        d["eudr_ready"] = r["ready"]
        d["readiness_missing"] = r["missing"]
    return d


def _summary(p: Plot) -> dict:
    return {
        "id": p.id,
        "code": p.code,
        "label": p.label,
        "farmer": {"id": p.farmer.id, "name": p.farmer.name, "village": p.farmer.village},
        "geometry": p.geometry,
        "area_ha": round(p.area_ha, 2),
        "centroid": [p.centroid_lat, p.centroid_lng],
        "risk_level": p.risk_level,
        "risk_headline": p.risk_headline,
        "boundary_confirmed": p.boundary_confirmed,
        "planting_year": effective_planting_year(p),
        "delineation_method": p.delineation_method,
        "status_override": bool(p.status_override),
    }


def analysis_dict(a: Analysis | None) -> dict | None:
    if a is None:
        return None
    return {
        "id": a.id,
        "created_at": a.created_at.isoformat(timespec="seconds"),
        "risk_level": a.risk_level,
        "headline": a.headline,
        "confidence": a.confidence,
        "evidence": a.evidence,
        "timeseries": a.timeseries,
        "data_source": a.data_source,
        "compute_ms": a.compute_ms,
        "model_version": a.model_version,
    }


def plot_detail(p: Plot, db: Session | None = None) -> dict:
    d = _summary(p)
    pending = False
    insps: list[dict] = []
    appeals: list[dict] = []
    history: list[dict] = []
    if db is not None:
        rows = db.scalars(select(Inspection).where(Inspection.plot_id == p.id).order_by(Inspection.id.desc()).limit(5)).all()
        pending = any(i.status == "menunggu" for i in rows)
        insps = [inspection_brief(i) for i in rows]
        appeals = [appeal_dict(a) for a in db.scalars(select(Appeal).where(Appeal.plot_id == p.id).order_by(Appeal.id.desc()))]
        history = audit.for_entity(db, "kebun", p.id, limit=30)
    d.update({
        "planting_year_declared": p.planting_year_declared,
        "planting_year_detected": p.planting_year_detected,
        "planting_consistency": planting_consistency(p),
        "witness": p.witness,
        "witnesses": readiness.witness_list(p),
        "boundary_sides": p.boundary_sides or {},
        "gps": {"lat": p.gps_lat, "lng": p.gps_lng, "accuracy_m": p.gps_accuracy_m} if p.gps_lat is not None else None,
        "land": {
            "proof": p.land_proof, "proof_label": readiness.LAND_PROOF_LABEL.get(p.land_proof or "", None),
            "ref": p.land_proof_ref, "stdb_status": p.stdb_status or "belum",
            "stdb_label": readiness.STDB_LABEL.get(p.stdb_status or "belum"), "stdb_number": p.stdb_number,
            "dispute": bool(p.dispute), "dispute_note": p.dispute_note,
        },
        "consent": p.farmer.consent_given,
        "consent_at": p.farmer.consent_at.isoformat(timespec="seconds") if p.farmer.consent_at else None,
        "created_at": p.created_at.isoformat(timespec="seconds"),
        "analysis": analysis_dict(p.analyses[0] if p.analyses else None),
        "scenario": p.scenario,
        "override": p.status_override,
        "verification": {"at": p.verified_at.isoformat(timespec="seconds") if p.verified_at else None,
                         "result": p.verified_result, "by": p.verified_by},
        "readiness": readiness.evaluate(p, pending),
        "inspections": insps,
        "appeals": appeals,
        "history": history,
    })
    return d


def inspection_brief(i: Inspection) -> dict:
    return {"id": i.id, "batch": i.batch, "reason": i.reason, "status": i.status, "result": i.result,
            "notes": i.notes, "inspector": i.inspector, "has_photo": bool(i.photo_path),
            "photo_distance_m": i.photo_distance_m,
            "created_at": i.created_at.isoformat(timespec="seconds"),
            "done_at": i.done_at.isoformat(timespec="seconds") if i.done_at else None}


def appeal_dict(a: Appeal) -> dict:
    return {"id": a.id, "plot_id": a.plot_id, "plot_code": a.plot.code, "farmer": a.plot.farmer.name,
            "submitted_by": a.submitted_by, "reason": a.reason, "evidence_type": a.evidence_type,
            "status": a.status, "original_risk": a.original_risk, "new_risk": a.new_risk,
            "decision_note": a.decision_note, "decided_by": a.decided_by,
            "created_at": a.created_at.isoformat(timespec="seconds"),
            "decided_at": a.decided_at.isoformat(timespec="seconds") if a.decided_at else None,
            "current_risk": a.plot.risk_level, "headline": a.plot.risk_headline}


def find_or_create_farmer(db: Session, name: str, village: str, consent: bool) -> Farmer:
    f = db.scalar(select(Farmer).where(Farmer.name == name, Farmer.village == village))
    if f is None:
        f = Farmer(name=name, village=village)
        db.add(f)
    if consent and not f.consent_given:
        f.consent_given, f.consent_at = True, datetime.now()
    db.flush()
    return f


def set_geometry(p: Plot, geom: dict) -> None:
    g = geo.validate_polygon(geom)
    p.geometry = g
    p.area_ha = geo.area_ha(g)
    p.centroid_lat, p.centroid_lng = geo.centroid(g)


def overlaps(db: Session, geom: dict, exclude_id: int | None = None) -> list[dict]:
    out = []
    minx, miny, maxx, maxy = geo.bbox(geom)
    for q in db.scalars(select(Plot)):
        if q.id == exclude_id:
            continue
        qx0, qy0, qx1, qy1 = geo.bbox(q.geometry)
        if qx0 > maxx or qx1 < minx or qy0 > maxy or qy1 < miny:
            continue
        ha, inter = geo.overlap(geom, q.geometry)
        if ha >= 0.01:
            out.append({"plot_id": q.id, "code": q.code, "farmer": q.farmer.name, "overlap_ha": round(ha, 3), "geometry": inter})
    return out


def kawasan_policy_for(p: Plot) -> str | None:
    """Kebun contoh dari seed tetap dicek ke salinan lokal peta kawasan saat dianalisis ulang (hasil demo stabil)."""
    prev = p.analyses[0] if p.analyses else None
    prot = (prev.evidence or {}).get("protected") if prev else None
    return "lokal" if isinstance(prot, dict) and prot.get("policy") == "lokal" else None


def apply_analysis(db: Session, p: Plot, force_demo: bool = False, kawasan_policy: str | None = None) -> Analysis:
    policy = kawasan_policy or kawasan_policy_for(p)
    r = analysis_svc.run(p.geometry, p.code, p.scenario, force_demo=force_demo, kawasan_policy=policy)
    a = Analysis(
        plot_id=p.id, risk_level=r["risk_level"], headline=r["headline"], confidence=r["confidence"],
        evidence=r["evidence"], timeseries=r["timeseries"], data_source=r["data_source"], compute_ms=r["compute_ms"],
    )
    db.add(a)
    p.risk_level, p.risk_headline = r["risk_level"], r["headline"]
    p.planting_year_detected = r["planting_year_detected"]
    prot = r["evidence"].get("protected") or {}
    p.analyzed_at = datetime.now()
    p.analysis_rule = r["evidence"].get("rule")
    p.kawasan_pct = prot.get("pct")
    p.kawasan_checked = bool(prot.get("checked"))
    p.kawasan_source = prot.get("source")
    # bukti satelit baru menggantikan keputusan keberatan sebelumnya (perlu ditinjau ulang bila berbeda)
    p.status_override = None
    db.flush()
    db.refresh(p)
    return a


def fit_to_neighbors(db: Session, geom: dict, exclude_id: int | None = None) -> dict:
    """Merapikan draf batas: bagian yang bertumpuk dengan kebun terdaftar dipotong mengikuti batas tetangga."""
    from shapely.geometry import shape

    g = shape(geo.validate_polygon(geom))
    before = geo.area_ha(geom)
    cut: list[dict] = []
    for o in overlaps(db, geom, exclude_id):
        q = db.get(Plot, o["plot_id"])
        g = g.difference(shape(q.geometry))
        cut.append({"code": o["code"], "farmer": o["farmer"], "overlap_ha": o["overlap_ha"]})
    if g.is_empty:
        raise ValueError("Seluruh draf berada di dalam kebun lain. Periksa lagi lokasi kebun.")
    if g.geom_type == "MultiPolygon":
        g = max(g.geoms, key=lambda x: x.area)
    g = g.simplify(0.0000015, preserve_topology=True)  # ~0,15 m: buang titik sisa pemotongan
    ring = [[round(x, 7), round(y, 7)] for x, y in g.exterior.coords]
    out = {"type": "Polygon", "coordinates": [ring]}
    return {"geometry": out, "area_ha": round(geo.area_ha(out), 3), "removed_ha": round(before - geo.area_ha(out), 3),
            "neighbors": cut}
