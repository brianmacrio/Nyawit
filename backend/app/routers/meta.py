from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import APP_VERSION, EUDR_APPLICATION, EUDR_CUTOFF, SATELLITE_MODE, TILE_URL
from ..db import get_db
from ..services import delineation
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
    }


@router.post("/demo/reset")
def reset_demo(db: Session = Depends(get_db)):
    from ..seed import seed

    db.close()
    summary = seed(reset=True)
    return {"detail": "Data demo dibuat ulang", **summary}
