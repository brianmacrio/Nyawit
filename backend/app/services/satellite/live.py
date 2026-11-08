"""Penyedia data satelit NYATA (mode live, opsional).

* Time series NDVI: Sentinel-2 L2A dari Microsoft Planetary Computer (STAC publik,
  tanpa akun). Piksel awan/bayangan dibuang memakai lapisan SCL.
* Tutupan pohon & kehilangan tutupan: Hansen Global Forest Change (UMD/GLAD) dibaca
  langsung dari Google Cloud Storage (GeoTIFF publik) hanya pada jendela kebun.

Butuh internet + paket di `requirements-live.txt`. Hasil di-cache ke disk sehingga
setiap kebun cukup diunduh sekali (hemat energi & kuota).
CATATAN: modul ini belum bisa diuji di lingkungan pengembangan kami (akses ke server
satelit diblokir di sana); jalankan `python -m app.scripts.check_live` di laptop.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import numpy as np

from ...config import TS_CACHE_DIR, TS_START

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
HANSEN_VERSION = os.getenv("PK_HANSEN_VERSION", "GFC-2024-v1.12")
HANSEN_URL = "https://storage.googleapis.com/earthenginepartners-hansen/{v}/Hansen_{v}_{layer}_{tile}.tif"
HANSEN_LAST_YEAR = 2000 + int(os.getenv("PK_HANSEN_LAST", "24"))
SCL_OK = {4, 5, 6, 7, 11}  # vegetasi, non-vegetasi, air, tak terklasifikasi, salju

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")


def status() -> dict:
    missing = []
    for mod in ("pystac_client", "planetary_computer", "rasterio"):
        try:
            __import__(mod)
        except Exception:  # noqa: BLE001
            missing.append(mod)
    return {"available": not missing, "missing": missing}


def _key(geom: dict, extra: str) -> str:
    return hashlib.sha256((json.dumps(geom, sort_keys=True) + extra).encode()).hexdigest()[:20]


def _read_window(href: str, geom: dict, out_shape: tuple[int, int] | None = None):
    """Membaca jendela raster seluas kebun (+20 m). Mengembalikan (array, mask_dalam_kebun)."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.features import geometry_mask
    from rasterio.warp import transform_geom
    from rasterio.windows import from_bounds

    with rasterio.open(href) as src:
        g = transform_geom("EPSG:4326", src.crs, geom)
        xs = [p[0] for p in g["coordinates"][0]]
        ys = [p[1] for p in g["coordinates"][0]]
        win = from_bounds(min(xs) - 20, min(ys) - 20, max(xs) + 20, max(ys) + 20, src.transform)
        win = win.round_offsets().round_lengths()
        if out_shape is None:
            arr = src.read(1, window=win).astype("float32")
        else:
            arr = src.read(1, window=win, out_shape=out_shape, resampling=Resampling.nearest)
        tr = src.window_transform(win)
        if out_shape is not None:
            tr = tr * tr.scale(win.width / out_shape[1], win.height / out_shape[0])
        inside = geometry_mask([g], out_shape=arr.shape, transform=tr, invert=True, all_touched=True)
    return arr, inside


def _item_ndvi(item, geom: dict) -> tuple[str, float] | None:
    try:
        baseline = float(item.properties.get("s2:processing_baseline", "0") or 0)
        offset = 1000.0 if baseline >= 4.0 else 0.0  # baseline 04.00+ menambah offset 1000
        red, inside = _read_window(item.assets["B04"].href, geom)
        nir, _ = _read_window(item.assets["B08"].href, geom, out_shape=red.shape)
        scl, _ = _read_window(item.assets["SCL"].href, geom, out_shape=red.shape)
        valid = inside & np.isin(scl, list(SCL_OK)) & (red > 0) & (nir > 0)
        if inside.sum() == 0 or valid.sum() / inside.sum() < 0.6:
            return None
        r, n = red[valid] - offset, nir[valid] - offset
        ndvi = (n - r) / np.maximum(n + r, 1)
        return item.datetime.date().isoformat(), float(np.clip(np.nanmean(ndvi), -1, 1))
    except Exception:  # noqa: BLE001
        return None


def ndvi_series(geom: dict, end: date | None = None) -> tuple[list[date], list[float], str]:
    end = end or date.today()
    cache = TS_CACHE_DIR / f"s2_{_key(geom, end.isoformat()[:7])}.json"
    if cache.exists():
        d = json.loads(cache.read_text())
        return [date.fromisoformat(x) for x in d["dates"]], d["ndvi"], d["source"] + " (cache)"

    import planetary_computer
    import pystac_client

    catalog = pystac_client.Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
    search = catalog.search(
        collections=["sentinel-2-l2a"], intersects=geom,
        datetime=f"{TS_START.isoformat()}/{end.isoformat()}", query={"eo:cloud_cover": {"lt": 60}},
    )
    items = list(search.items())
    if not items:
        return [], [], "Sentinel-2 L2A (Planetary Computer): tidak ada citra"
    # pakai satu petak MGRS saja agar geometri piksel konsisten
    tile = Counter(i.properties.get("s2:mgrs_tile") for i in items).most_common(1)[0][0]
    items = [i for i in items if i.properties.get("s2:mgrs_tile") == tile]
    with ThreadPoolExecutor(max_workers=12) as ex:
        rows = [r for r in ex.map(lambda it: _item_ndvi(it, geom), items) if r]
    by_date: dict[str, float] = {}
    for d, v in rows:
        by_date.setdefault(d, v)
    dates = sorted(by_date)
    src = f"Sentinel-2 L2A, Microsoft Planetary Computer, petak {tile}, {len(dates)} citra bebas awan"
    TS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"dates": dates, "ndvi": [by_date[d] for d in dates], "source": src}))
    return [date.fromisoformat(d) for d in dates], [by_date[d] for d in dates], src


def _hansen_tile(lat: float, lng: float) -> str:
    top = int(math.ceil(lat / 10.0) * 10)
    left = int(math.floor(lng / 10.0) * 10)
    return f"{abs(top):02d}{'N' if top >= 0 else 'S'}_{abs(left):03d}{'E' if left >= 0 else 'W'}"


def hansen_layers(geom: dict, lat: float, lng: float) -> dict[str, float | None]:
    cache = TS_CACHE_DIR / f"gfc_{_key(geom, HANSEN_VERSION)}.json"
    if cache.exists():
        return json.loads(cache.read_text())

    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.windows import from_bounds

    tile = _hansen_tile(lat, lng)
    xs = [p[0] for p in geom["coordinates"][0]]
    ys = [p[1] for p in geom["coordinates"][0]]

    def read(layer: str):
        url = "/vsicurl/" + HANSEN_URL.format(v=HANSEN_VERSION, layer=layer, tile=tile)
        with rasterio.open(url) as src:
            win = from_bounds(min(xs), min(ys), max(xs), max(ys), src.transform).round_offsets(op="floor").round_lengths(op="ceil")
            arr = src.read(1, window=win)
            m = geometry_mask([geom], out_shape=arr.shape, transform=src.window_transform(win), invert=True, all_touched=True)
        return arr, m

    tc, m = read("treecover2000")
    ly, _ = read("lossyear")
    n = max(int(m.sum()), 1)
    loss_before = (ly >= 1) & (ly <= 20)
    loss_after = (ly >= 21)
    out = {
        "tree_cover_2020": round(100 * float(((tc >= 30) & ~loss_before & m).sum()) / n, 1),
        "commodity_2020": None,  # butuh Earth Engine (Forest Data Partnership) - belum tersedia offline
        "disturbance_before_2021": round(100 * float((loss_before & m).sum()) / n, 1),
        "disturbance_after_2020": round(100 * float((loss_after & m).sum()) / n, 1),
        "_source": f"Hansen {HANSEN_VERSION} petak {tile} ({n} piksel 30 m)",
    }
    TS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out))
    return out
