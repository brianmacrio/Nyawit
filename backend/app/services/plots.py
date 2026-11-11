"""Logika domain kebun: kode paspor, serialisasi, dan penerapan hasil analisis."""
from __future__ import annotations

import string
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Analysis, Farmer, Plot
from . import analysis as analysis_svc
from . import geo

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


def plot_summary(p: Plot) -> dict:
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


def plot_detail(p: Plot) -> dict:
    d = plot_summary(p)
    d.update({
        "planting_year_declared": p.planting_year_declared,
        "planting_year_detected": p.planting_year_detected,
        "planting_consistency": planting_consistency(p),
        "witness": p.witness,
        "consent": p.farmer.consent_given,
        "consent_at": p.farmer.consent_at.isoformat(timespec="seconds") if p.farmer.consent_at else None,
        "created_at": p.created_at.isoformat(timespec="seconds"),
        "analysis": analysis_dict(p.analyses[0] if p.analyses else None),
        "scenario": p.scenario,
    })
    return d


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
    """Kebun contoh fiktif dari seed tetap memakai peta ilustrasi saat dianalisis ulang."""
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
    db.flush()
    db.refresh(p)
    return a
