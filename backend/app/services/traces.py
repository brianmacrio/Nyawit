"""Format geolokasi untuk Sistem Informasi EUDR (TRACES): pembulatan 6 desimal dan pemeriksaan sebelum ekspor.

Mengikuti "GeoJSON File Description" Komisi Eropa v1.3 (29 Mei 2026):
  * WGS84, urutan [bujur, lintang]; sistem MEMOTONG koordinat ke 6 desimal sebelum menyimpan, sehingga
    presisi lebih tinggi tidak berguna dan dua titik yang berbeda di desimal ke-7 bisa menjadi titik kembar;
  * poligon harus tertutup (titik pertama = terakhir) dan punya minimal 4 pasang koordinat;
  * poligon berlubang tidak diproses; sisi yang berpotongan (angka delapan) atau berimpit ditolak;
  * `ProducerCountry` wajib kode ISO2; `Area` (ha) berupa angka, bukan teks; nama properti peka huruf besar/kecil;
  * hanya Point, Polygon, MultiPolygon (LineString ditolak).
Karena itu koordinat kebun disimpan dan diekspor 6 desimal (~11 cm), dan setiap berkas ekspor diperiksa di sini.
`ProducerName` sengaja tidak diisi: bersifat opsional, dan paket ekspor tidak memuat data pribadi petani.
"""
from __future__ import annotations

import re
from typing import Any

from shapely.geometry import Polygon
from shapely.validation import explain_validity, make_valid

SPEC = "GeoJSON File Description TRACES v1.3 (Komisi Eropa, 29 Mei 2026)"
DECIMALS = 6
MIN_PAIRS = 4
# kotak batas kasar per negara produsen (bujur min, lintang min, bujur maks, lintang maks): menangkap lintang/bujur tertukar
COUNTRY_BOX = {"ID": (94.0, -11.5, 141.5, 6.5)}
CHECKS = [
    "Koordinat WGS84 dengan urutan bujur lalu lintang, di dalam wilayah negara produsen",
    "Paling banyak 6 desimal (TRACES memotong ke 6 desimal)",
    "Poligon tertutup, minimal 4 pasang koordinat, tanpa titik kembar berurutan",
    "Tanpa lubang, tanpa sisi yang berpotongan atau berimpit",
    "ProducerCountry kode ISO2; Area berupa angka hektar",
]


class TracesError(ValueError):
    pass


def clean_ring(ring: list) -> list[list[float]]:
    """Bulatkan ke 6 desimal, buang titik kembar berurutan, tutup cincin."""
    out: list[list[float]] = []
    for pt in ring:
        p = [round(float(pt[0]), DECIMALS), round(float(pt[1]), DECIMALS)]
        if not out or out[-1] != p:
            out.append(p)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    if len(out) < 3:
        raise TracesError("poligon menyusut menjadi kurang dari 3 titik setelah dibulatkan ke 6 desimal")
    return out + [out[0]]


def to_traces_polygon(geom: dict[str, Any]) -> dict[str, Any]:
    """Poligon siap TRACES: cincin luar saja, 6 desimal, valid setelah pembulatan."""
    if geom.get("type") != "Polygon" or not geom.get("coordinates"):
        raise TracesError("geometri kebun harus Polygon")
    ring = clean_ring(geom["coordinates"][0])
    poly = Polygon(ring)
    if not poly.is_valid or poly.area == 0:
        fixed = make_valid(poly)
        if fixed.geom_type in ("MultiPolygon", "GeometryCollection"):
            polys = [g for g in fixed.geoms if g.geom_type == "Polygon"]
            fixed = max(polys, key=lambda g: g.area) if polys else fixed
        if fixed.geom_type != "Polygon" or fixed.area == 0:
            raise TracesError("poligon tidak valid setelah dibulatkan ke 6 desimal")
        ring = clean_ring([list(c) for c in fixed.exterior.coords])
    return {"type": "Polygon", "coordinates": [ring]}


def _decimals(v: float) -> int:
    s = repr(float(v))
    if "e" in s or "E" in s:
        s = f"{float(v):.12f}".rstrip("0")
    return len(s.split(".")[1]) if "." in s else 0


def _ring_problems(ring: Any, country: str | None) -> list[str]:
    out: list[str] = []
    if not isinstance(ring, list) or len(ring) < MIN_PAIRS:
        return [f"poligon punya kurang dari {MIN_PAIRS} pasang koordinat"]
    try:
        pts = [(float(p[0]), float(p[1])) for p in ring]
    except (TypeError, ValueError, IndexError):
        return ["koordinat bukan pasangan angka [bujur, lintang]"]
    if pts[0] != pts[-1]:
        out.append("poligon tidak tertutup (titik pertama tidak sama dengan titik terakhir)")
    if any(not (-180 <= x <= 180 and -90 <= y <= 90) for x, y in pts):
        out.append("koordinat di luar rentang WGS84")
    box = COUNTRY_BOX.get(country or "")
    if box and any(not (box[0] <= x <= box[2] and box[1] <= y <= box[3]) for x, y in pts):
        out.append(f"koordinat di luar wilayah {country} (lintang dan bujur tertukar?)")
    if any(_decimals(v) > DECIMALS for p in pts for v in p):
        out.append("koordinat lebih dari 6 desimal (TRACES memotong ke 6 desimal)")
    if any(a == b for a, b in zip(pts, pts[1:])):
        out.append("ada titik kembar berurutan")
    if not out:
        poly = Polygon(pts)
        if not poly.is_valid:
            out.append("sisi poligon berpotongan atau berimpit (" + explain_validity(poly).split("[")[0].strip() + ")")
        elif poly.area == 0:
            out.append("poligon tidak punya luas (titik-titiknya segaris)")
    return out


def feature_problems(feature: dict[str, Any]) -> list[str]:
    """Daftar masalah satu Feature menurut aturan TRACES (kosong = lolos)."""
    props = feature.get("properties") or {}
    geom = feature.get("geometry") or {}
    out: list[str] = []
    country = props.get("ProducerCountry")
    if not isinstance(country, str) or not re.fullmatch(r"[A-Z]{2}", country):
        out.append("ProducerCountry harus kode negara ISO2 (mis. ID)")
        country = None
    if "Area" in props and (isinstance(props["Area"], (str, bool)) or not isinstance(props["Area"], (int, float))
                            or props["Area"] <= 0):
        out.append("Area harus angka hektar lebih dari 0 (bukan teks)")
    t = geom.get("type")
    coords = geom.get("coordinates")
    if t == "Polygon":
        if not coords:
            out.append("poligon tanpa koordinat")
        else:
            if len(coords) > 1:
                out.append("poligon berlubang tidak diproses TRACES")
            out += _ring_problems(coords[0], country)
    elif t == "MultiPolygon":
        for part in coords or []:
            if len(part) > 1:
                out.append("poligon berlubang tidak diproses TRACES")
            out += _ring_problems(part[0] if part else None, country)
    elif t == "Point":
        try:
            x, y = float(coords[0]), float(coords[1])
            if not (-180 <= x <= 180 and -90 <= y <= 90):
                out.append("koordinat di luar rentang WGS84")
        except (TypeError, ValueError, IndexError):
            out.append("koordinat titik harus [bujur, lintang]")
    else:
        out.append(f"jenis geometri {t!r} tidak diterima (hanya Point, Polygon, MultiPolygon)")
    return list(dict.fromkeys(out))


def validate_collection(fc: dict[str, Any]) -> dict[str, Any]:
    """Periksa seluruh FeatureCollection. Hasil dipakai dasbor pabrik dan README paket ekspor."""
    problems: list[dict[str, Any]] = []
    feats = fc.get("features") if fc.get("type") == "FeatureCollection" else None
    if feats is None:
        return {"ok": False, "features": 0, "problems": [{"plot": None, "issues": ["bukan FeatureCollection"]}],
                "spec": SPEC, "checks": CHECKS}
    for i, f in enumerate(feats):
        issues = feature_problems(f)
        if issues:
            problems.append({"plot": (f.get("properties") or {}).get("PlotCode") or f"fitur ke-{i + 1}", "issues": issues})
    return {"ok": not problems and len(feats) > 0, "features": len(feats), "problems": problems, "spec": SPEC,
            "checks": CHECKS}


def upload_collection(fc: dict[str, Any]) -> dict[str, Any]:
    """Salinan ramping untuk diunggah ke TRACES: hanya properti yang dikenal spesifikasi."""
    keep = ("ProducerCountry", "ProductionPlace", "Area")
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": f["geometry"],
         "properties": {k: f["properties"][k] for k in keep if f.get("properties", {}).get(k) is not None}}
        for f in fc.get("features", [])]}
