"""Cadangan otomatis status kawasan hutan: Peta Kawasan Hutan KLHK 2017 lewat Global Forest Watch.

Global Forest Watch (WRI) menyediakan dataset `idn_forest_area` (Kawasan Hutan Indonesia, KLHK,
versi 2017) sebagai tile vektor publik. Dipakai bila layanan peta Kemenhut tidak terjangkau,
sehingga setiap kebun tetap dicek ke peta resmi, bukan ke batas yang digambar tangan.

- Tile zoom 12 (~9,8 km) yang menutupi kebun diunduh sekali lalu disimpan di cache disk.
- Tile "dynamic" GFW berisi poligon utuh, jadi fitur yang sama bisa muncul di beberapa tile:
  digabung per `gfw_fid`.
- Fungsi kawasan dibaca dari teks `desc_in` / `legend_in` (mis. "Taman Nasional",
  "Hutan Produksi Terbatas"), dengan kode `fungsikawa` sebagai cadangan.

Batasan yang harus disebut: data 2017 dan skala provinsi, jadi tidak memuat perubahan SK
sesudahnya. Hasilnya tetap sinyal untuk diverifikasi, dan peta Kemenhut tetap sumber utama.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import shapely
from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

from ..config import KAWASAN_CACHE_DIR, KAWASAN_GFW, KAWASAN_GFW_URL, KAWASAN_TIMEOUT
from . import mvt

ENABLED = KAWASAN_GFW
URL = KAWASAN_GFW_URL
Z = 12
LAYER = "idn_forest_area"
CACHE_DAYS = 365  # data statis (versi 2017)
BREAKER_S = 120  # hanya untuk gangguan jaringan; galat server per tile tidak menghentikan tile lain
RETRY_WAIT_S = (1.0, 2.5)  # tile besar kadang dijawab HTTP 500 saat pertama kali dibuat server GFW
SOURCE_LABEL = "Peta Kawasan Hutan KLHK 2017 (dataset Global Forest Watch)"
UA = "PasporKebun/1.1 (cek status kawasan hutan kebun petani; hackathon)"
KEEP = ("gfw_fid", "fungsikawa", "desc_in", "kelas", "legend_in", "namobj")

# kode `fungsikawa` yang terlihat di data; teks tetap diutamakan
CODE = {"1001": "HL", "1002": "HL", "1003": "HP", "1004": "HPT", "1005": "HPK", "1007": "APL"}


class GfwError(RuntimeError):
    def __init__(self, msg: str, reachable: bool = False):
        super().__init__(msg)
        self.reachable = reachable  # True = server menjawab (galat per tile), bukan putus jaringan


_lock = threading.Lock()
_state: dict[str, Any] = {"offline_until": 0.0, "last_error": None, "last_ok": None}
_mem: dict[tuple[int, int], dict] = {}


def _cache_dir() -> Path:
    return KAWASAN_CACHE_DIR / "gfw"


def _path(x: int, y: int) -> Path:
    return _cache_dir() / f"{Z}_{x}_{y}.json"


def reset_breaker() -> None:
    with _lock:
        _state["offline_until"] = 0.0


def clear_caches() -> None:
    _mem.clear()


def status() -> dict:
    d = _cache_dir()
    return {
        "enabled": ENABLED,
        "source_label": SOURCE_LABEL,
        "cached_tiles": len(list(d.glob("*.json"))) if d.exists() else 0,
        "online": None if _state["last_ok"] is None and _state["last_error"] is None else _state["last_error"] is None,
        "last_ok": _state["last_ok"],
        "last_error": _state["last_error"],
    }


def fungsi_of(attrs: dict) -> str:
    from .kawasan import FUNGSI, classify

    text = attrs.get("desc_in") or attrs.get("legend_in") or ""
    code = classify({"fungsi_teks": text}) if text else "?"
    if code == "?":
        fk = str(attrs.get("fungsikawa") or "").split(".")[0]
        code = CODE.get(fk) or ("KSA_KPA" if fk.startswith("100") and len(fk) == 5 else "?")
    return code if code in FUNGSI else "?"


def _download(x: int, y: int) -> bytes:
    url = URL.format(z=Z, x=x, y=y)
    # Accept-Encoding seperti browser: tile terkompresi lebih kecil dan memakai salinan CDN yang sama
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/x-protobuf,*/*",
                                               "Accept-Encoding": "gzip"})
    from .kawasan import _ssl_context

    last: GfwError | None = None
    for wait in (0.0, *RETRY_WAIT_S):
        if wait:
            time.sleep(wait)
        try:
            with urllib.request.urlopen(req, timeout=KAWASAN_TIMEOUT, context=_ssl_context()) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            # 404 juga dianggap gagal: bila alamat dataset berubah, semua tile 404 dan kebun
            # di dalam kawasan tidak boleh terbaca "aman".
            last = GfwError(f"HTTP {e.code} dari Global Forest Watch (tile {Z}/{x}/{y})", reachable=True)
            if e.code < 500:
                raise last from e
        except Exception as e:  # noqa: BLE001
            raise GfwError(f"{e.__class__.__name__}: {e}") from e
    assert last is not None
    raise last


def fetch_tile(x: int, y: int) -> dict:
    data = _download(x, y)
    feats = []
    if data:
        try:
            layers = mvt.decode(data)
        except Exception as e:  # noqa: BLE001
            raise GfwError(f"tile tidak terbaca: {e}") from e
        lyr = layers.get(LAYER) or next(iter(layers.values()), None)
        if lyr:
            for f in lyr["features"]:
                g = mvt.feature_geojson(f, Z, x, y, lyr["extent"])
                if not g or g["type"] not in ("Polygon", "MultiPolygon"):
                    continue
                attrs = {k: f["properties"].get(k) for k in KEEP if f["properties"].get(k) not in (None, "")}
                feats.append({"attrs": attrs, "geometry": g})
    return {"v": 1, "tile": [Z, x, y], "url": URL, "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "features": feats}


def _write(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def get_tile(x: int, y: int, allow_online: bool = True) -> tuple[dict | None, str]:
    """(data tile, asal) dengan asal 'cache' | 'online' | 'cache_lama' | 'tidak_ada'."""
    cached = _mem.get((x, y))
    path = _path(x, y)
    if cached is None and path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached.get("url") != URL:
                cached = None
        except Exception:  # noqa: BLE001
            cached = None
    if cached is not None and datetime.now() - datetime.fromisoformat(cached["fetched_at"]) < timedelta(days=CACHE_DAYS):
        _mem[(x, y)] = cached
        return cached, "cache"
    if ENABLED and allow_online and time.time() >= _state["offline_until"]:
        try:
            data = fetch_tile(x, y)
            _write(path, data)
            _mem[(x, y)] = data
            with _lock:
                _state.update(last_ok=datetime.now().isoformat(timespec="seconds"), last_error=None)
            return data, "online"
        except GfwError as e:
            with _lock:
                _state["last_error"] = str(e)[:300]
                if not e.reachable:
                    _state["offline_until"] = time.time() + BREAKER_S
    if cached is not None:
        return cached, "cache_lama"
    return None, "tidak_ada"


def features_for(bounds: tuple[float, float, float, float], allow_online: bool = True) -> tuple[list[dict], str | None]:
    """Poligon kawasan (sudah digabung per gfw_fid) yang menyentuh bbox.

    Mengembalikan (fitur, waktu unduh tertua). Melempar GfwError bila ada tile yang tidak bisa didapat,
    karena hasil sebagian bisa membuat kebun di dalam kawasan terbaca aman.
    """
    tiles = mvt.tiles_for_bounds(bounds, Z)
    if len(tiles) > 16:
        raise GfwError("area terlalu luas untuk dicek sekaligus")
    bbox = box(*bounds)
    groups: dict[Any, list] = {}
    attrs_of: dict[Any, dict] = {}
    when: list[str] = []
    for x, y in tiles:
        data, how = get_tile(x, y, allow_online)
        if data is None:
            raise GfwError(_state.get("last_error") or "peta GFW tidak terjangkau dan belum ada di cache")
        when.append(data["fetched_at"])
        for i, f in enumerate(data["features"]):
            g = shape(f["geometry"])
            if not g.intersects(bbox):
                continue
            if not g.is_valid:
                g = shapely.make_valid(g)
            key = f["attrs"].get("gfw_fid", f"{x}_{y}_{i}")
            groups.setdefault(key, []).append(g)
            attrs_of[key] = f["attrs"]
    out = []
    for key, gs in groups.items():
        # fitur utuh yang sama di beberapa tile: cukup satu; potongan berbeda: digabung
        uniq = []
        for g in gs:
            if not any(g.equals_exact(u, 1e-9) for u in uniq):
                uniq.append(g)
        g = uniq[0] if len(uniq) == 1 else unary_union(uniq)
        a = attrs_of[key]
        out.append({"gfw_fid": a.get("gfw_fid"), "fungsi": fungsi_of(a), "name": a.get("desc_in") or a.get("legend_in"),
                    "attrs": a, "geom": g})
    return out, (min(when) if when else None)


def map_features(bounds: tuple[float, float, float, float], tolerance: float) -> list[dict]:
    """GeoJSON kawasan (tanpa APL) untuk ditampilkan di peta, dipotong ke bbox dan disederhanakan."""
    from .kawasan import FUNGSI

    feats, _ = features_for(bounds)
    clip = box(*bounds)
    out = []
    for f in feats:
        if not FUNGSI[f["fungsi"]]["kawasan"] and f["fungsi"] != "?":
            continue
        g = f["geom"].intersection(clip)
        if g.is_empty:
            continue
        if tolerance > 0:
            g = g.simplify(tolerance, preserve_topology=True)
        g = shapely.set_precision(g, 1e-6)
        if g.is_empty or g.geom_type not in ("Polygon", "MultiPolygon"):
            polys = [p for p in getattr(g, "geoms", []) if p.geom_type in ("Polygon", "MultiPolygon")]
            if not polys:
                continue
            g = unary_union(polys)
        out.append({"type": "Feature", "geometry": mapping(g), "properties": {
            "gfw_fid": f["gfw_fid"], "fungsi": f["fungsi"], "fungsi_label": FUNGSI[f["fungsi"]]["label"], "name": f["name"]}})
    return out
