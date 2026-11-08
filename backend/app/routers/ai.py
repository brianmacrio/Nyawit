from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from ..config import TILE_ZOOM
from ..schemas import DelineateIn
from ..services import delineation, tiles

router = APIRouter(prefix="/api/ai", tags=["AI"])


@router.post("/delineate")
async def delineate(body: DelineateIn):
    z = body.zoom or TILE_ZOOM
    try:
        rgb, ox, oy = await run_in_threadpool(tiles.fetch_patch, body.lat, body.lng, z, 1)
    except tiles.TileFetchError as e:
        raise HTTPException(503, f"{e} Periksa koneksi internet atau gambar batas secara manual.") from e
    try:
        r = await run_in_threadpool(delineation.delineate, rgb, ox, oy, body.lat, body.lng, z)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return {
        "polygon": r.polygon,
        "area_ha": r.area_ha,
        "confidence": r.confidence,
        "engine": r.engine,
        "engine_label": "Segment Anything (SAM)" if r.engine == "sam" else "Watershed berpenanda (OpenCV)",
        "ms": r.ms,
        "warnings": r.warnings,
        "note": "Draf AI. Wajib ditinjau dan dikoreksi petani bersama saksi sebelum disimpan.",
    }
