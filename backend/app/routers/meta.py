from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import APP_VERSION, EUDR_APPLICATION, EUDR_CUTOFF, SATELLITE_MODE, TILE_URL
from ..db import get_db
from ..models import User
from ..security import rate_limit, require
from ..services import delineation, kawasan
from ..services.satellite import live

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


@router.post("/demo/reset", dependencies=[Depends(rate_limit("reset", 3, 600))])
def reset_demo(db: Session = Depends(get_db), _: User = Depends(require("admin"))):
    from ..seed import seed

    db.close()
    summary = seed(reset=True)
    return {"detail": "Data demo dibuat ulang", **summary}
