"""Status kawasan hutan otomatis dari peta resmi Kementerian Kehutanan.

Sumber utama: layanan ArcGIS REST "Kawasan Hutan" di Geoportal Kemenhut (SIGAP Interaktif),
dasar hukum Permen LHK 7/2021. Untuk setiap kebun:

1. Area kebun dibagi ke sel grid 0,01 derajat (~1,1 km).
2. Sel yang belum ada di cache diminta ke layanan (operasi `identify`, cadangan `query`):
   poligon kawasan hutan yang beririsan dengan sel, digeneralisasi ~5 m, lalu dipotong
   sebatas sel dan disimpan di disk. Cache membuat demo tetap jalan saat internet putus
   dan setiap sel hanya diunduh sekali.
3. Fungsi kawasan (konservasi, HL, HPT, HP, HPK, APL) dibaca dari atribut: domain kode
   layanan, teks/singkatan, atau tabel kode buatan pengguna `data/kawasan/kode_fungsi.json`.
4. Persentase luas kebun di setiap fungsi dihitung dengan shapely.

GeoJSON di `data/kawasan/` (peta resmi yang diunduh pengguna, atau batas ilustrasi demo)
selalu ikut diperhitungkan. Sumber yang dipakai selalu disebut di paspor.

Batasan yang ditampilkan ke pengguna: peta kawasan berskala kecil dan bisa tertinggal dari
SK pelepasan terbaru, jadi hasil "masuk kawasan" adalah sinyal untuk diverifikasi, bukan vonis.
"""
from __future__ import annotations

import json
import math
import re
import ssl
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import shapely
from shapely.geometry import Polygon, box, mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid

from ..config import DATA_DIR, KAWASAN_CACHE_DIR, KAWASAN_LAYERS, KAWASAN_SOURCE, KAWASAN_TIMEOUT, KAWASAN_URL

UA = "PasporKebun/1.0 (cek status kawasan hutan kebun petani; MVP hackathon)"
CELL_DEG = 0.01
CACHE_DAYS = 30
SERVICE_CACHE_DAYS = 7
BREAKER_S = 300  # setelah gagal, jangan coba online lagi selama 5 menit (agar aplikasi tetap cepat)
GENERALIZE_DEG = 0.00005  # ~5,5 m; jauh di bawah ketelitian peta kawasan
T_SIGNIFICANT = 5.0
SOURCE_LABEL = "Peta Kawasan Hutan, Kementerian Kehutanan (SIGAP, Permen LHK 7/2021)"

FUNGSI: dict[str, dict[str, Any]] = {
    "KSA_KPA": {"label": "Kawasan konservasi", "kawasan": True,
                "long": "Kawasan Suaka Alam / Pelestarian Alam (taman nasional, cagar alam, suaka margasatwa, tahura)"},
    "HL": {"label": "Hutan Lindung", "kawasan": True, "long": "Hutan Lindung"},
    "HPT": {"label": "Hutan Produksi Terbatas", "kawasan": True, "long": "Hutan Produksi Terbatas"},
    "HP": {"label": "Hutan Produksi Tetap", "kawasan": True, "long": "Hutan Produksi Tetap"},
    "HPK": {"label": "Hutan Produksi Konversi", "kawasan": True, "long": "Hutan Produksi yang dapat Dikonversi"},
    "APL": {"label": "Areal Penggunaan Lain", "kawasan": False, "long": "Areal Penggunaan Lain (bukan kawasan hutan)"},
    "AIR": {"label": "Tubuh air", "kawasan": False, "long": "Tubuh air"},
    "?": {"label": "Fungsi tidak terbaca", "kawasan": None, "long": "Poligon di peta kawasan dengan fungsi yang tidak terbaca"},
}
KAWASAN_CODES = [k for k, v in FUNGSI.items() if v["kawasan"]]

# --------------------------------------------------------------------------------------
# Klasifikasi atribut -> fungsi kawasan
# --------------------------------------------------------------------------------------
_LONG = [
    ("KSA_KPA", r"SUAKA ALAM|PELESTARIAN ALAM|CAGAR ALAM|SUAKA MARGA ?SATWA|TAMAN NASIONAL|TAMAN WISATA ALAM|"
                r"TAMAN HUTAN RAYA|TAMAN BURU|KONSERVASI"),
    ("HL", r"HUTAN LINDUNG"),
    ("HPT", r"PRODUKSI TERBATAS"),
    ("HPK", r"DAPAT DI ?KONVERSI|PRODUKSI (YANG )?KONVERSI"),
    ("HP", r"HUTAN PRODUKSI|PRODUKSI TETAP"),
    ("APL", r"AREAL? PENGGUNAAN LAIN|BUKAN KAWASAN HUTAN|NON ?KAWASAN HUTAN|BUDIDAYA NON ?KEHUTANAN"),
    ("AIR", r"TUBUH AIR|DANAU|WADUK"),
]
_SHORT = [
    ("KSA_KPA", r"KSA|KPA|KSPA|CA|SM|TN|TWA|TAHURA|TB"),
    ("HL", r"HL|LINDUNG"),
    ("HPT", r"HPT"),
    ("HPK", r"HPK"),
    ("HP", r"HP|HPTETAP"),
    ("APL", r"APL|KBNK"),
    ("AIR", r"AIR|TA"),
]
_LONG_RE = [(c, re.compile(rf"\b({p})\b")) for c, p in _LONG]
_SHORT_RE = [(c, re.compile(rf"(?<![A-Z0-9])({p})(?![A-Z0-9])")) for c, p in _SHORT]
_FUNGSI_FIELD = re.compile(r"fungsi|fungsikws|^fgs|kws_?f|func|status_?k|ket(erangan)?$|^remark", re.I)
_NAME_FIELD = re.compile(r"^(nama|namobj|name|nm_?kws|nama_?kaw|nama_?kws|nama_?kh|kawasan)", re.I)


@lru_cache(maxsize=1)
def _code_map() -> dict[str, dict[str, str]]:
    """Tabel kode buatan pengguna, mis. {"FUNGSIKWS": {"1001": "HL"}} atau {"*": {...}}."""
    p = DATA_DIR / "kawasan" / "kode_fungsi.json"
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    out: dict[str, dict[str, str]] = {}
    for fld, mp in raw.items():
        if isinstance(mp, dict):
            out[fld.upper()] = {str(k).strip(): str(v).upper() for k, v in mp.items() if str(v).upper() in FUNGSI}
    return out


def _norm(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v).upper().replace("_", " ")).strip()


def _match(text: str, short: bool, kawasan_only: bool = False) -> str | None:
    for code, rx in _LONG_RE:
        if rx.search(text) and not (kawasan_only and not FUNGSI[code]["kawasan"]):
            return code
    if short:
        for code, rx in _SHORT_RE:
            if rx.search(text) and not (kawasan_only and not FUNGSI[code]["kawasan"]):
                return code
    return None


def classify(attrs: dict[str, Any]) -> str:
    """Membaca fungsi kawasan dari atribut satu poligon. Mengembalikan kode FUNGSI."""
    if not attrs:
        return "?"
    cm = _code_map()
    explicit = str(attrs.get("fungsi", "")).upper()
    if explicit in FUNGSI:  # GeoJSON lokal/ilustrasi yang sudah menyebut kodenya
        return explicit
    items = [(str(k), v) for k, v in attrs.items() if v not in (None, "")]
    if cm:
        for k, v in items:
            mp = cm.get(k.upper()) or (cm.get("*") if _FUNGSI_FIELD.search(k) else None)
            if mp and str(v).strip() in mp:
                return mp[str(v).strip()]
    for k, v in items:  # 1) kolom fungsi: teks panjang + singkatan
        if _FUNGSI_FIELD.search(k) and (c := _match(_norm(v), short=True)):
            return c
    for k, v in items:  # 2) kolom nama (TN Tesso Nilo, HL Bukit ...): hanya kelas kawasan
        if _NAME_FIELD.search(k) and (c := _match(_norm(v), short=True, kawasan_only=True)):
            return c
    for _, v in items:  # 3) kolom lain: hanya frasa panjang yang tidak ambigu
        if isinstance(v, str) and (c := _match(_norm(v), short=False)):
            return c
    return "?"


def feature_name(attrs: dict[str, Any]) -> str | None:
    for k, v in attrs.items():
        t = v.strip() if isinstance(v, str) else ""
        if _NAME_FIELD.search(str(k)) and 2 < len(t) < 90 and not t.isdigit() and t.lower() not in ("null", "<null>"):
            return t
    return None


# --------------------------------------------------------------------------------------
# HTTP ke layanan ArcGIS REST
# --------------------------------------------------------------------------------------
class KawasanError(RuntimeError):
    pass


_state_lock = threading.Lock()
_state: dict[str, Any] = {"offline_until": 0.0, "last_error": None, "last_ok": None}


def _ssl_context() -> ssl.SSLContext:
    # truststore memakai penyimpanan sertifikat OS (Windows), yang bisa melengkapi rantai
    # sertifikat situs pemerintah yang kadang tidak lengkap.
    try:
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


def _get_json(url: str, params: dict[str, Any], timeout: float | None = None) -> Any:
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{q}", headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout or KAWASAN_TIMEOUT, context=_ssl_context()) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
    except KawasanError:
        raise
    except Exception as e:  # noqa: BLE001
        raise KawasanError(f"{e.__class__.__name__}: {e}") from e
    if isinstance(data, dict) and "error" in data:
        err = data["error"]
        raise KawasanError(f"layanan menjawab galat {err.get('code')}: {err.get('message')}")
    return data


def _mark_offline(err: Exception) -> None:
    with _state_lock:
        _state["offline_until"] = time.time() + BREAKER_S
        _state["last_error"] = str(err)[:300]


def _mark_ok() -> None:
    with _state_lock:
        _state["offline_until"] = 0.0
        _state["last_error"] = None
        _state["last_ok"] = datetime.now().isoformat(timespec="seconds")


def _online_allowed() -> bool:
    return time.time() >= _state["offline_until"]


def reset_breaker() -> None:
    with _state_lock:
        _state["offline_until"] = 0.0


# --------------------------------------------------------------------------------------
# Informasi layanan & pemilihan layer
# --------------------------------------------------------------------------------------
_EXCL = re.compile(r"perubahan|progres|pengukuhan|tata ?batas|review|rtrw|usulan|indikatif|label|anotasi|annotation|"
                   r"titik|garis|line|point|pal\b", re.I)
_INCL = re.compile(r"kawasan ?hutan|fungsi|penetapan|penunjukan|\bkh\b", re.I)


def _layer_summary(l: dict) -> dict:
    domains: dict[str, dict[str, str]] = {}
    fields = []
    for f in l.get("fields") or []:
        fields.append({"name": f.get("name"), "alias": f.get("alias"), "type": f.get("type")})
        d = f.get("domain") or {}
        if d.get("type") == "codedValue":
            domains[f["name"]] = {str(cv["code"]): str(cv["name"]) for cv in d.get("codedValues", [])}
    return {
        "id": l.get("id"), "name": l.get("name", ""), "type": l.get("type"), "geometryType": l.get("geometryType"),
        "subLayerIds": l.get("subLayerIds"), "maxRecordCount": l.get("maxRecordCount"), "fields": fields, "domains": domains,
    }


def select_layers(layers: list[dict]) -> list[int]:
    if KAWASAN_LAYERS:
        return list(KAWASAN_LAYERS)
    leaf = [l for l in layers if not l.get("subLayerIds") and l.get("type") in (None, "Feature Layer")
            and l.get("geometryType") in (None, "esriGeometryPolygon")]
    cand = [l for l in leaf if _INCL.search(l["name"]) and not _EXCL.search(l["name"])]
    if not cand:
        cand = [l for l in leaf if not _EXCL.search(l["name"])] or leaf
    return [int(l["id"]) for l in cand][:40]


def service_info(refresh: bool = False) -> dict:
    """Daftar layer, kolom, dan domain kode layanan (disimpan 7 hari)."""
    path = KAWASAN_CACHE_DIR / "_layanan.json"
    if path.exists() and not refresh:
        try:
            info = json.loads(path.read_text(encoding="utf-8"))
            age = datetime.now() - datetime.fromisoformat(info["fetched_at"])
            if info.get("url") == KAWASAN_URL and age < timedelta(days=SERVICE_CACHE_DAYS):
                return info
        except Exception:  # noqa: BLE001
            pass
    try:
        layers = _get_json(f"{KAWASAN_URL}/layers", {"f": "json"}).get("layers", [])
    except KawasanError:
        root = _get_json(KAWASAN_URL, {"f": "json"})
        layers = []
        for l in root.get("layers", [])[:60]:
            if l.get("subLayerIds"):
                layers.append(l)
                continue
            try:
                layers.append(_get_json(f"{KAWASAN_URL}/{l['id']}", {"f": "json"}))
            except KawasanError:
                layers.append(l)
    summ = [_layer_summary(l) for l in layers]
    info = {"url": KAWASAN_URL, "fetched_at": datetime.now().isoformat(timespec="seconds"), "layers": summ,
            "selected": select_layers(summ)}
    _write_json(path, info)
    return info


# --------------------------------------------------------------------------------------
# Geometri
# --------------------------------------------------------------------------------------
def esri_polygon_to_shape(g: dict, clip=None):
    """Ring Esri (luar searah jarum jam, lubang berlawanan) -> shapely, aturan even-odd."""
    out = None
    for ring in g.get("rings") or []:
        if len(ring) < 4:
            continue
        p = _polygonal(Polygon([(pt[0], pt[1]) for pt in ring]))
        if p is not None and clip is not None:
            p = _polygonal(p.intersection(clip))
        if p is None:
            continue
        out = p if out is None else _polygonal(out.symmetric_difference(p))
    return out


def _polygonal(g):
    """Hanya bagian poligon dari geometri (make_valid bisa menghasilkan GeometryCollection)."""
    if g is None or g.is_empty:
        return None
    if not g.is_valid:
        g = make_valid(g)
    if g.geom_type in ("Polygon", "MultiPolygon"):
        return g
    polys = [p for p in getattr(g, "geoms", []) if p.geom_type in ("Polygon", "MultiPolygon") and not p.is_empty]
    return unary_union(polys) if polys else None


def _clean_geom(g):
    g = _polygonal(g)
    if g is None:
        return None
    g = _polygonal(shapely.set_precision(g, 1e-7))
    return None if g is None or g.area == 0 else g


def _cell_bounds(i: int, j: int) -> tuple[float, float, float, float]:
    return (round(j * CELL_DEG, 6), round(i * CELL_DEG, 6), round((j + 1) * CELL_DEG, 6), round((i + 1) * CELL_DEG, 6))


def cells_for(bounds: tuple[float, float, float, float]) -> list[tuple[int, int]]:
    minx, miny, maxx, maxy = bounds
    i0, i1 = math.floor(miny / CELL_DEG), math.floor(maxy / CELL_DEG)
    j0, j1 = math.floor(minx / CELL_DEG), math.floor(maxx / CELL_DEG)
    return [(i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)]


def _small_attrs(attrs: dict) -> dict:
    keep = {}
    for k, v in attrs.items():
        if k.lower().startswith(("shape", "objectid", "fid", "globalid", "st_area", "st_length")):
            continue
        if isinstance(v, str) and v.strip().lower() in ("", "null", "<null>", " "):
            continue
        if isinstance(v, (str, int, float)) and len(str(v)) <= 160:
            keep[k] = v
        if len(keep) >= 20:
            break
    return keep


# --------------------------------------------------------------------------------------
# Unduh per sel + cache
# --------------------------------------------------------------------------------------
def _write_json(path: Path, data: Any) -> None:
    """Tulis atomik; gagal menulis cache tidak boleh menggagalkan pengecekan."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def _features_from_results(results: list[dict], cell, layer_names: dict[int, str], domains: dict[int, dict]) -> list[dict]:
    out = []
    for r in results:
        geom = r.get("geometry") or {}
        g = _clean_geom(esri_polygon_to_shape(geom, clip=cell))
        if g is None:
            continue
        lid = r.get("layerId", r.get("_layer"))
        attrs = dict(r.get("attributes") or {})
        for fld, mp in (domains.get(lid) or {}).items():  # kode domain -> nama (untuk hasil `query`)
            if fld in attrs and str(attrs[fld]) in mp:
                attrs[f"{fld}_label"] = mp[str(attrs[fld])]
        out.append({"layer": lid, "layer_name": r.get("layerName") or layer_names.get(lid, ""),
                    "attrs": _small_attrs(attrs), "geometry": mapping(g)})
    return out


def fetch_cell(i: int, j: int) -> dict:
    info = service_info()
    sel = info.get("selected") or []
    names = {l["id"]: l["name"] for l in info["layers"]}
    domains = {l["id"]: l.get("domains") or {} for l in info["layers"]}
    xmin, ymin, xmax, ymax = _cell_bounds(i, j)
    cell = box(xmin - 1e-6, ymin - 1e-6, xmax + 1e-6, ymax + 1e-6)
    env = f"{xmin},{ymin},{xmax},{ymax}"
    method = "identify"
    try:
        data = _get_json(f"{KAWASAN_URL}/identify", {
            "geometry": env, "geometryType": "esriGeometryEnvelope", "sr": 4326,
            "layers": "all:" + ",".join(map(str, sel)) if sel else "all", "tolerance": 0, "mapExtent": env,
            "imageDisplay": "800,800,96", "returnGeometry": "true", "maxAllowableOffset": GENERALIZE_DEG,
            "geometryPrecision": 6, "returnFieldName": "true", "f": "json",
        })
        feats = _features_from_results(data.get("results", []), cell, names, domains)
    except KawasanError:
        method = "query"
        results = []
        for lid in sel or list(names):
            d = _get_json(f"{KAWASAN_URL}/{lid}/query", {
                "where": "1=1", "geometry": env, "geometryType": "esriGeometryEnvelope", "inSR": 4326,
                "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "returnGeometry": "true", "outSR": 4326,
                "maxAllowableOffset": GENERALIZE_DEG, "geometryPrecision": 6, "f": "json",
            })
            results += [{**f, "_layer": lid} for f in d.get("features", [])]
        feats = _features_from_results(results, cell, names, domains)
    return {"v": 1, "cell": [i, j], "bounds": [xmin, ymin, xmax, ymax], "service": KAWASAN_URL, "method": method,
            "layers": sel, "fetched_at": datetime.now().isoformat(timespec="seconds"), "features": feats}


_mem: dict[tuple[int, int], dict] = {}


def _cell_path(i: int, j: int) -> Path:
    return KAWASAN_CACHE_DIR / f"{i}_{j}.json"


def get_cell(i: int, j: int, allow_online: bool = True) -> tuple[dict | None, str]:
    """Mengembalikan (data sel, asal) dengan asal 'online' | 'cache' | 'cache_lama' | 'tidak_ada'."""
    path = _cell_path(i, j)
    cached = _mem.get((i, j))
    if cached is None and path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached.get("service") != KAWASAN_URL:
                cached = None
            else:
                _mem[(i, j)] = cached
        except Exception:  # noqa: BLE001
            cached = None
    fresh = cached is not None and datetime.now() - datetime.fromisoformat(cached["fetched_at"]) < timedelta(days=CACHE_DAYS)
    if fresh:
        return cached, "cache"
    if allow_online and _online_allowed():
        try:
            data = fetch_cell(i, j)
            _write_json(path, data)
            _mem[(i, j)] = data
            _mark_ok()
            return data, "online"
        except Exception as e:  # noqa: BLE001
            _mark_offline(e)
    if cached is not None:
        return cached, "cache_lama"
    return None, "tidak_ada"


# --------------------------------------------------------------------------------------
# Peta lokal (GeoJSON) di data/kawasan/
# --------------------------------------------------------------------------------------
@lru_cache(maxsize=1)
def local_areas() -> list[dict]:
    out = []
    folder = DATA_DIR / "kawasan"
    for p in sorted(folder.glob("*.geojson")) if folder.exists() else []:
        try:
            fc = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for f in fc.get("features", []):
            g = f.get("geometry") or {}
            if g.get("type") not in ("Polygon", "MultiPolygon"):
                continue
            props = f.get("properties") or {}
            fungsi = classify(props)
            out.append({
                "name": props.get("name") or feature_name(props) or p.stem,
                "status": props.get("status", ""),
                "fungsi": fungsi,
                "fungsi_label": FUNGSI[fungsi]["label"],
                "is_demo": bool(props.get("is_demo", False)),
                "file": p.name,
                "geometry": g,
            })
    return out


@lru_cache(maxsize=1)
def local_extents() -> list[dict]:
    """Cakupan (bbox) tiap file GeoJSON lokal: kebun di dalam cakupan peta resmi dianggap sudah diperiksa."""
    ext: dict[str, list] = {}
    demo: dict[str, bool] = {}
    for a in local_areas():
        b = shape(a["geometry"]).bounds
        e = ext.get(a["file"])
        ext[a["file"]] = list(b) if e is None else [min(e[0], b[0]), min(e[1], b[1]), max(e[2], b[2]), max(e[3], b[3])]
        demo[a["file"]] = demo.get(a["file"], True) and a["is_demo"]
    return [{"file": f, "extent": e, "is_demo": demo[f]} for f, e in ext.items()]


def _contains_bounds(outer, inner) -> bool:
    return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[2] >= inner[2] and outer[3] >= inner[3]


def clear_caches() -> None:
    local_extents.cache_clear()
    local_areas.cache_clear()
    _code_map.cache_clear()
    _mem.clear()


# --------------------------------------------------------------------------------------
# Hasil per kebun
# --------------------------------------------------------------------------------------
@dataclass
class KawasanResult:
    pct: float  # % luas kebun di kawasan hutan (semua fungsi kawasan)
    name: str | None  # nama/fungsi dominan, untuk judul
    fungsi: str | None  # kode fungsi dominan di dalam kawasan
    label: str | None
    parts: list[dict] = field(default_factory=list)  # [{fungsi, label, pct, name, source}]
    unknown_pct: float = 0.0
    source: str = "tidak_ada"  # kemenhut | lokal | ilustrasi | tidak_ada
    source_label: str = ""
    checked: bool = False  # True bila peta resmi (online/cache/GeoJSON resmi) benar-benar diperiksa
    policy: str = "auto"
    checked_at: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _fmt_date(iso: str) -> str:
    from .fmt import BULAN

    return f"{int(iso[8:10])} {BULAN[int(iso[5:7]) - 1]} {iso[:4]}" if iso else ""


def lookup(geom: dict, policy: str | None = None) -> KawasanResult:
    policy = (policy or KAWASAN_SOURCE).lower()
    plot = shape(geom)
    if not plot.is_valid:
        plot = make_valid(plot)
    area = plot.area
    feats: list[tuple[str, Any, str | None, str]] = []  # (fungsi, geometri, nama, sumber)
    warnings: list[str] = []
    kemenhut_ok = False
    fetched: list[str] = []
    stale = False

    if policy in ("auto", "online"):
        cells = cells_for(plot.bounds)
        got = 0
        for i, j in cells:
            data, how = get_cell(i, j)
            if data is None:
                continue
            got += 1
            stale |= how == "cache_lama"
            fetched.append(data["fetched_at"])
            for f in data["features"]:
                g = shape(f["geometry"])
                if not g.intersects(plot):
                    continue
                attrs = f.get("attrs") or {}
                feats.append((classify(attrs), g, feature_name(attrs), "kemenhut"))
        kemenhut_ok = got == len(cells) and got > 0
        if not kemenhut_ok:
            err = _state.get("last_error") or "tidak terjangkau"
            warnings.append(f"Peta kawasan Kemenhut belum bisa diakses ({err[:120]}). Analisis ulang saat internet tersedia.")
        elif stale:
            warnings.append("Memakai salinan peta Kemenhut yang disimpan lebih dari 30 hari lalu; layanan sedang tidak terjangkau.")

    local_used: set[str] = set()
    local_covers = any(not a["is_demo"] and _contains_bounds(a["extent"], plot.bounds) for a in local_extents())
    for la in local_areas():
        g = _polygonal(shape(la["geometry"]))
        if g is None or not g.intersects(plot):
            continue
        src = "ilustrasi" if la["is_demo"] else "lokal"
        local_used.add(src)
        # batas ilustrasi demo tanpa kode fungsi dianggap kawasan konservasi (seperti di peta demo)
        code = "KSA_KPA" if la["is_demo"] and la["fungsi"] == "?" else la["fungsi"]
        feats.append((code, g, la["name"], src))

    by: dict[str, list] = {}
    names: dict[str, str] = {}
    srcs: dict[str, set] = {}
    for code, g, nm, src in feats:
        inter = plot.intersection(g)
        if inter.is_empty or inter.area <= 0:
            continue
        by.setdefault(code, []).append(inter)
        srcs.setdefault(code, set()).add(src)
        if nm and code not in names:
            names[code] = nm

    def pct_of(gs: list) -> float:
        return 0.0 if not gs or area == 0 else round(min(unary_union(gs).area / area, 1.0) * 100, 1)

    kaw_geoms = [g for c in KAWASAN_CODES for g in by.get(c, [])]
    pct = pct_of(kaw_geoms)
    kaw_union = unary_union(kaw_geoms) if kaw_geoms else None
    unknown_pct = 0.0
    if by.get("?"):
        u = unary_union(by["?"])
        if kaw_union is not None:
            u = u.difference(kaw_union)
        unknown_pct = round(min(u.area / area, 1.0) * 100, 1) if area else 0.0

    parts = []
    for code, gs in by.items():
        p = pct_of(gs)
        if p <= 0:
            continue
        parts.append({"fungsi": code, "label": FUNGSI[code]["label"], "pct": p, "name": names.get(code),
                      "kawasan": FUNGSI[code]["kawasan"], "source": sorted(srcs[code])[0]})
    parts.sort(key=lambda x: (-(x["kawasan"] is True), -x["pct"]))
    dom = next((p for p in parts if p["kawasan"]), None)

    if kemenhut_ok:
        source = "kemenhut"
        when = max(fetched) if fetched else None
        label = SOURCE_LABEL + (f", diambil {_fmt_date(when)}" if when else "")
    elif "lokal" in local_used or local_covers:
        source, label, when = "lokal", "Peta kawasan resmi (GeoJSON lokal)", None
    elif "ilustrasi" in local_used or (local_areas() and all(a["is_demo"] for a in local_areas())):
        source, label, when = "ilustrasi", "Peta ilustrasi demo (bukan batas resmi)", None
    else:
        source, label, when = "tidak_ada", "Belum ada peta kawasan yang bisa diperiksa", None
    if kemenhut_ok and "ilustrasi" in local_used:
        label += " + peta ilustrasi demo"

    checked = kemenhut_ok or "lokal" in local_used or local_covers
    return KawasanResult(
        pct=pct,
        name=(dom["name"] or dom["label"]) if dom else None,
        fungsi=dom["fungsi"] if dom else None,
        label=dom["label"] if dom else None,
        parts=parts,
        unknown_pct=unknown_pct,
        source=source,
        source_label=label,
        checked=checked,
        policy=policy,
        checked_at=when,
        warnings=warnings,
    )


def status() -> dict:
    n = len(list(KAWASAN_CACHE_DIR.glob("*_*.json"))) if KAWASAN_CACHE_DIR.exists() else 0
    selected = None
    p = KAWASAN_CACHE_DIR / "_layanan.json"
    if p.exists():
        try:
            selected = json.loads(p.read_text(encoding="utf-8")).get("selected")
        except Exception:  # noqa: BLE001
            selected = None
    return {
        "policy": KAWASAN_SOURCE,
        "service": KAWASAN_URL,
        "layers": selected or KAWASAN_LAYERS or None,
        "online": None if _state["last_ok"] is None and _state["last_error"] is None else _state["last_error"] is None,
        "last_ok": _state["last_ok"],
        "last_error": _state["last_error"],
        "cached_cells": n,
        "source_label": SOURCE_LABEL,
    }
