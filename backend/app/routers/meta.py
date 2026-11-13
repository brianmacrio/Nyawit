from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import APP_VERSION, EUDR_APPLICATION, EUDR_CUTOFF, SATELLITE_MODE, TILE_URL
from ..db import get_db
from ..models import User
from ..security import rate_limit, require
from ..services import delineation, kawasan, kawasan_gfw
from ..services.satellite import live, peta_gfw

router = APIRouter(prefix="/api", tags=["Meta"])


@router.get("/health")
def health():
    return {"status": "ok", "version": APP_VERSION}


@router.get("/meta")
def meta():
    return {
        "version": APP_VERSION,
        "satellite_mode": SATELLITE_MODE,
        "live_packages": live.status(),
        "sam": delineation.sam_status(),
        "eudr_cutoff": EUDR_CUTOFF.isoformat(),
        "eudr_application": EUDR_APPLICATION.isoformat(),
        "imagery": TILE_URL.split("/")[2],
        "kawasan": kawasan.status(),
        "peta_gfw": peta_gfw.status(),
    }


@router.get("/kawasan/status")
def kawasan_status(probe: bool = False, _: User = Depends(require())):
    """Status layanan peta kawasan Kemenhut. `probe=true` mencoba menghubungi layanan sekarang."""
    if probe:
        kawasan.reset_breaker()
        try:
            info = kawasan.service_info(refresh=True)
            kawasan._mark_ok()
            return {**kawasan.status(), "layers_found": len(info["layers"]), "selected_names": [
                l["name"] for l in info["layers"] if l["id"] in info["selected"]]}
        except Exception as e:  # noqa: BLE001
            kawasan._mark_offline(e)
    return kawasan.status()


@router.get("/kawasan/peta", dependencies=[Depends(rate_limit("kawasan_peta", 120, 60))])
def kawasan_peta(bbox: str = Query(..., description="minLng,minLat,maxLng,maxLat"), _: User = Depends(require())):
    """Poligon kawasan hutan (KLHK 2017, Global Forest Watch) di tampilan peta, untuk lapisan peta."""
    try:
        minx, miny, maxx, maxy = (float(v) for v in bbox.split(","))
    except ValueError as e:
        raise HTTPException(422, "bbox harus berupa empat angka: minLng,minLat,maxLng,maxLat") from e
    if not (-180 <= minx < maxx <= 180 and -90 <= miny < maxy <= 90):
        raise HTTPException(422, "bbox tidak valid")
    if maxx - minx > 0.4 or maxy - miny > 0.4:
        return {"features": [], "too_large": True, "source_label": kawasan_gfw.SOURCE_LABEL}
    try:
        feats = kawasan_gfw.map_features((minx, miny, maxx, maxy), tolerance=(maxx - minx) / 1500)
    except kawasan_gfw.GfwError as e:
        return {"features": [], "error": str(e)[:200], "source_label": kawasan_gfw.SOURCE_LABEL}
    return {"type": "FeatureCollection", "features": feats, "source_label": kawasan_gfw.SOURCE_LABEL}


@router.get("/uji-indikator", dependencies=[Depends(rate_limit("uji_indikator", 6, 300))])
def uji_indikator(_: User = Depends(require())):
    """Uji tiga indikator peta dengan kebun yang sengaja melanggarnya, memakai data online terbaru."""
    from ..scripts.uji_indikator import evaluate

    kawasan.reset_breaker()
    peta_gfw.reset_breaker()
    results = evaluate()
    return {"results": results, "passed": sum(r["passed"] for r in results), "total": len(results)}


@router.post("/demo/reset", dependencies=[Depends(rate_limit("reset", 3, 600))])
def reset_demo(db: Session = Depends(get_db), _: User = Depends(require("admin"))):
    from ..seed import seed

    db.close()
    summary = seed(reset=True)
    return {"detail": "Data demo dibuat ulang", **summary}
