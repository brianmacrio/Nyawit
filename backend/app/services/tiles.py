"""Mengambil citra satelit (XYZ tile) di sekitar titik klik, dengan cache disk.

Cache membuat setiap tile hanya diunduh sekali (hemat kuota & energi) dan membuat
demo tetap jalan saat internet lambat setelah area pernah dibuka.
"""
from __future__ import annotations

import io
import math
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

from ..config import TILE_CACHE_DIR, TILE_URL
from .geo import TILE_SIZE, latlng_to_global_px

UA = "PasporKebun/1.0 (hackathon MVP; contact: local)"


class TileFetchError(RuntimeError):
    pass


def _tile(z: int, x: int, y: int) -> np.ndarray:
    path = TILE_CACHE_DIR / str(z) / str(x) / f"{y}.jpg"
    if path.exists():
        return np.array(Image.open(path).convert("RGB"))
    url = TILE_URL.format(z=z, x=x, y=y)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
    except Exception as e:  # noqa: BLE001
        raise TileFetchError(f"Gagal mengunduh citra satelit ({e.__class__.__name__}).") from e
    img = Image.open(io.BytesIO(data)).convert("RGB")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, quality=90)
    return np.array(img)


def fetch_patch(lat: float, lng: float, z: int, radius_tiles: int = 1) -> tuple[np.ndarray, float, float]:
    """Mosaik (2r+1)^2 tile berpusat di titik. Mengembalikan (rgb, origin_px_x, origin_px_y)."""
    gx, gy = latlng_to_global_px(lat, lng, z)
    tx, ty = int(gx // TILE_SIZE), int(gy // TILE_SIZE)
    coords = [(tx + dx, ty + dy) for dy in range(-radius_tiles, radius_tiles + 1) for dx in range(-radius_tiles, radius_tiles + 1)]
    with ThreadPoolExecutor(max_workers=6) as ex:
        imgs = list(ex.map(lambda c: _tile(z, c[0], c[1]), coords))
    n = 2 * radius_tiles + 1
    mosaic = np.zeros((n * TILE_SIZE, n * TILE_SIZE, 3), dtype=np.uint8)
    for (cx, cy), im in zip(coords, imgs):
        ox, oy = (cx - tx + radius_tiles) * TILE_SIZE, (cy - ty + radius_tiles) * TILE_SIZE
        mosaic[oy : oy + TILE_SIZE, ox : ox + TILE_SIZE] = im[:TILE_SIZE, :TILE_SIZE]
    origin_x = (tx - radius_tiles) * TILE_SIZE
    origin_y = (ty - radius_tiles) * TILE_SIZE
    return mosaic, float(origin_x), float(origin_y)


def tile_xy(lat: float, lng: float, z: int) -> tuple[int, int]:
    gx, gy = latlng_to_global_px(lat, lng, z)
    return int(math.floor(gx / TILE_SIZE)), int(math.floor(gy / TILE_SIZE))
