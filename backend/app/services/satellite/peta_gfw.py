"""Lapisan bukti deforestasi dari peta NYATA, dibaca langsung dari tile publik Global Forest Watch.

Mode demo memakai deret NDVI simulasi, tetapi tiga lapisan bukti peta tidak perlu disimulasikan:
lapisan yang sama yang tampil di peta ("Kehilangan tutupan pohon 2021-2025 (GFW)") dibaca per
piksel di dalam batas kebun, sehingga apa yang dilihat pengguna di peta = apa yang dihitung mesin.

Sumber (tanpa akun/kunci API, cukup Pillow + shapely, tanpa rasterio):
* Hansen Global Forest Change (UMD/GLAD), tile `umd_tree_cover_loss` dengan render "encoded":
  piksel kehilangan tutupan berwarna R=255 dan kanal biru = tahun kehilangan - 2000 (1..25),
  ambang kerapatan tajuk 30% (sama dengan peta GFW).
* JRC Global Forest Cover 2020 (versi 2020.3): peta hutan acuan Komisi Eropa untuk EUDR. Piksel
  hutan = buram (alfa > 127). Peta ini SENGAJA tidak menghitung kebun sawit/karet sebagai hutan,
  berbeda dengan "tutupan pohon" Hansen yang juga menangkap sawit tua.

Zoom 14: piksel ~4,8 m (tile kehilangan 512 px) dan ~9,6 m (tile JRC 256 px). Data aslinya
30 m (Hansen) dan 10 m (JRC), jadi tile ini tidak menambah detail, hanya cukup halus untuk kebun
swadaya 1-4 ha. Persentase dihitung dari pusat piksel yang jatuh di dalam poligon kebun.

Urutan sumber: (1) tabel bawaan `seed_data/lapisan_peta_demo.json` untuk kebun contoh (hasil
hitungan yang sama, disimpan agar demo identik tanpa internet), (2) cache tile di disk, (3) unduh
dari GFW. Bila semuanya gagal, analisis kembali ke lapisan simulasi dan memberi peringatan.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from ...config import PETA_GFW, PETA_JRC_URL, PETA_LOSS_URL, TS_CACHE_DIR

Z = 14
MAX_TILES = 16  # kebun > ~8 km tidak wajar untuk satu kebun swadaya
BREAKER_S = 120
RETRY_WAIT_S = (1.0, 2.5)
TIMEOUT_S = 15
UA = "PasporKebun/1.1 (cek bukti deforestasi kebun petani; hackathon)"
BUNDLE = Path(__file__).resolve().parents[2] / "seed_data" / "lapisan_peta_demo.json"
SOURCE_LABEL = ("Peta nyata: JRC Global Forest Cover 2020 + Hansen GFC kehilangan tutupan pohon 2001-2025 "
                "(tile Global Forest Watch, dihitung per piksel di dalam batas kebun)")
LAYER_SOURCES = {
    "tree_cover_2020": "JRC Global Forest Cover 2020 v2020.3",
    "disturbance_before_2021": "Hansen GFC, kehilangan tutupan pohon 2001-2020 (tile GFW)",
    "disturbance_after_2020": "Hansen GFC, kehilangan tutupan pohon 2021-2025 (tile GFW, lapisan yang sama dengan peta)",
}


class PetaError(RuntimeError):
    def __init__(self, msg: str, reachable: bool = False):
        super().__init__(msg)
        self.reachable = reachable


_lock = threading.Lock()
_state: dict[str, Any] = {"offline_until": 0.0, "last_error": None, "last_ok": None}


# ---------------------------------------------------------------- proyeksi web-mercator
def lnglat_to_px(lng: float, lat: float, z: int, size: int) -> tuple[float, float]:
    n = (2 ** z) * size
    x = (lng + 180.0) / 360.0 * n
    r = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(r)) / math.pi) / 2.0 * n
    return x, y


def px_to_lnglat(x: np.ndarray, y: np.ndarray, z: int, size: int) -> tuple[np.ndarray, np.ndarray]:
    n = (2 ** z) * size
    lng = x / n * 360.0 - 180.0
    lat = np.degrees(np.arctan(np.sinh(np.pi * (1.0 - 2.0 * y / n))))
    return lng, lat


def tiles_for(bounds: tuple[float, float, float, float], z: int = Z) -> list[tuple[int, int]]:
    minx, miny, maxx, maxy = bounds
    x0, y0 = lnglat_to_px(minx, maxy, z, 1)
    x1, y1 = lnglat_to_px(maxx, miny, z, 1)
    return [(x, y) for x in range(int(x0), int(x1) + 1) for y in range(int(y0), int(y1) + 1)]


# ---------------------------------------------------------------- tile
def _cache_path(kind: str, x: int, y: int) -> Path:
    return TS_CACHE_DIR / "peta_gfw" / f"{kind}_{Z}_{x}_{y}.png"


def _download(url: str) -> bytes:
    from ..kawasan import _ssl_context

    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/png,*/*"})
    last: PetaError | None = None
    for wait in (0.0, *RETRY_WAIT_S):
        if wait:
            time.sleep(wait)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=_ssl_context()) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = PetaError(f"HTTP {e.code} dari Global Forest Watch", reachable=True)
            if e.code < 500:
                raise last from e
        except Exception as e:  # noqa: BLE001
            raise PetaError(f"{e.__class__.__name__}: {e}") from e
    assert last is not None
    raise last


def read_rgba(data: bytes) -> np.ndarray:
    from PIL import Image

    return np.asarray(Image.open(io.BytesIO(data)).convert("RGBA"))


def get_tile(kind: str, x: int, y: int, online: bool = True) -> np.ndarray:
    p = _cache_path(kind, x, y)
    if p.exists():
        return read_rgba(p.read_bytes())
    if not online or not PETA_GFW:
        raise PetaError("tile belum ada di cache dan unduhan online dimatikan")
    if time.time() < _state["offline_until"]:
        raise PetaError(f"Global Forest Watch belum terjangkau ({_state['last_error']})")
    url = (PETA_LOSS_URL if kind == "loss" else PETA_JRC_URL).format(z=Z, x=x, y=y)
    try:
        data = _download(url)
        arr = read_rgba(data)
    except PetaError as e:
        with _lock:
            _state["last_error"] = str(e)
            if not e.reachable:
                _state["offline_until"] = time.time() + BREAKER_S
        raise
    except Exception as e:  # noqa: BLE001 - PNG rusak
        raise PetaError(f"tile tidak terbaca: {e}", reachable=True) from e
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    with _lock:
        _state["last_ok"], _state["last_error"] = time.strftime("%Y-%m-%dT%H:%M:%S"), None
    return arr


# ---------------------------------------------------------------- hitung lapisan
def loss_year(rgba: np.ndarray) -> np.ndarray:
    """Tahun kehilangan tutupan per piksel (0 = tidak ada) dari tile render 'encoded'."""
    r, b, a = rgba[..., 0], rgba[..., 2].astype(np.int16), rgba[..., 3]
    yr = np.where((r == 255) & (a > 0) & (b >= 1) & (b <= 60), 2000 + b, 0)
    return yr.astype(np.int16)


def forest_mask(rgba: np.ndarray) -> np.ndarray:
    return rgba[..., 3] > 127


def compute(geom: dict, tile_loader) -> dict:
    """Persentase luas kebun: hutan 2020 (JRC), kehilangan 2001-2020 dan 2021-2025 (Hansen).

    `tile_loader(kind, x, y) -> RGBA ndarray`. Dipisah agar bisa diuji dengan tile buatan.
    """
    import shapely
    from shapely.geometry import shape

    plot = shape(geom)
    tiles = tiles_for(plot.bounds)
    if len(tiles) > MAX_TILES:
        raise PetaError("batas kebun terlalu luas untuk dihitung per piksel")
    shapely.prepare(plot)
    n = forest = 0
    years: Counter = Counter()
    for tx, ty in tiles:
        loss = tile_loader("loss", tx, ty)
        jrc = tile_loader("jrc", tx, ty)
        size = loss.shape[1]
        # pusat piksel tile kehilangan (resolusi tertinggi) yang jatuh di dalam batas kebun
        minx, miny, maxx, maxy = plot.bounds
        px0, py0 = lnglat_to_px(minx, maxy, Z, size)
        px1, py1 = lnglat_to_px(maxx, miny, Z, size)
        i0, i1 = max(int(px0) - tx * size, 0), min(int(px1) - tx * size + 1, size - 1)
        j0, j1 = max(int(py0) - ty * size, 0), min(int(py1) - ty * size + 1, size - 1)
        if i0 > i1 or j0 > j1:
            continue
        ii, jj = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1))
        lng, lat = px_to_lnglat(tx * size + ii + 0.5, ty * size + jj + 0.5, Z, size)
        inside = shapely.contains_xy(plot, lng, lat)
        if not inside.any():
            continue
        yr = loss_year(loss)[jj[inside], ii[inside]]
        js = jrc.shape[1]
        fj = forest_mask(jrc)[((jj[inside] + 0.5) * js / size).astype(int), ((ii[inside] + 0.5) * js / size).astype(int)]
        n += int(inside.sum())
        forest += int(fj.sum())
        years.update(int(v) for v in yr[yr > 0])
    if n == 0:
        raise PetaError("kebun lebih kecil dari satu piksel peta")
    return summarize(n, forest, years)


def summarize(n: int, forest: int, years: dict[int, int]) -> dict:
    """Jumlah piksel -> persentase lapisan bukti (dipakai juga untuk membangun tabel bawaan)."""
    years = Counter({int(y): int(c) for y, c in years.items()})
    before = sum(c for y, c in years.items() if y <= 2020)
    after = sum(c for y, c in years.items() if y >= 2021)
    pct = lambda c: round(100.0 * c / n, 1)  # noqa: E731
    after_years = {str(y): pct(c) for y, c in sorted(years.items()) if y >= 2021 and pct(c) > 0}
    before_years = [(y, c) for y, c in years.items() if y <= 2020]
    return {
        "tree_cover_2020": pct(forest),
        "commodity_2020": None,  # peta sawit 2020 butuh Earth Engine; JRC sudah mengecualikan kebun sawit
        "disturbance_before_2021": pct(before),
        "disturbance_after_2020": pct(after),
        "loss_after_by_year": after_years,
        "loss_after_main_year": max(after_years, key=after_years.get) if after_years else None,
        "loss_before_main_year": str(max(before_years, key=lambda t: t[1])[0]) if before_years else None,
        "pixels": n,
    }


# ---------------------------------------------------------------- tabel bawaan kebun contoh
def geom_key(geom: dict) -> str:
    ring = [[round(float(x), 6), round(float(y), 6)] for x, y in geom["coordinates"][0]]
    return hashlib.sha256(json.dumps(ring, separators=(",", ":")).encode()).hexdigest()[:16]


@lru_cache(maxsize=1)
def _bundle() -> dict:
    try:
        return json.loads(BUNDLE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"plots": {}}


def bundled(geom: dict) -> dict | None:
    try:
        v = _bundle().get("plots", {}).get(geom_key(geom))
    except Exception:  # noqa: BLE001
        return None
    return dict(v) if v else None


def plot_layers(geom: dict, policy: str = "auto") -> tuple[dict | None, str | None]:
    """(lapisan, sumber) atau (None, alasan gagal).

    policy: "bundel" = hanya tabel bawaan (seed, deterministik); "auto" = tabel bawaan lalu
    cache/unduh online; "online" = abaikan tabel bawaan.
    """
    if geom.get("type") != "Polygon":
        return None, "geometri bukan poligon"
    if policy in ("auto", "bundel"):
        b = bundled(geom)
        if b:
            when = _bundle().get("_meta", {}).get("computed_at", "")
            return {**b, "_source": SOURCE_LABEL + (f", dihitung {when}" if when else "") + " (salinan bawaan demo)"}, None
        if policy == "bundel":
            return None, "kebun ini tidak ada di tabel bawaan"
    try:
        out = compute(geom, lambda k, x, y: get_tile(k, x, y, online=True))
    except PetaError as e:
        return None, str(e)
    return {**out, "_source": SOURCE_LABEL + f", diambil {time.strftime('%d-%m-%Y')}"}, None


def status() -> dict:
    d = TS_CACHE_DIR / "peta_gfw"
    return {
        "enabled": PETA_GFW,
        "bundled_plots": len(_bundle().get("plots", {})),
        "cached_tiles": len(list(d.glob("*.png"))) if d.exists() else 0,
        "last_ok": _state["last_ok"],
        "last_error": _state["last_error"],
    }


def reset_breaker() -> None:
    with _lock:
        _state["offline_until"] = 0.0
