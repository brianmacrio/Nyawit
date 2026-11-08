"""Utilitas geometri: luas, tumpang tindih, dan konversi koordinat Web Mercator.

Untuk kebun kecil (< 50 ha) proyeksi equirectangular lokal di sekitar centroid
memberi galat luas < 0,1%, cukup akurat tanpa dependensi pyproj (lebih ringan).
"""
from __future__ import annotations

import math
from typing import Any

from shapely.geometry import Polygon, mapping, shape
from shapely.validation import make_valid

EARTH_R = 6_371_008.8
TILE_SIZE = 256


def _ring(geom: dict[str, Any]) -> list[list[float]]:
    if geom.get("type") != "Polygon":
        raise ValueError("Geometri harus GeoJSON Polygon")
    return geom["coordinates"][0]


def centroid(geom: dict[str, Any]) -> tuple[float, float]:
    """Mengembalikan (lat, lng) centroid."""
    c = shape(geom).centroid
    return c.y, c.x


def to_local_m(geom: dict[str, Any], lat0: float, lng0: float) -> Polygon:
    k = math.cos(math.radians(lat0))
    pts = [
        (EARTH_R * math.radians(lng - lng0) * k, EARTH_R * math.radians(lat - lat0))
        for lng, lat in _ring(geom)
    ]
    poly = Polygon(pts)
    return poly if poly.is_valid else make_valid(poly)


def area_ha(geom: dict[str, Any]) -> float:
    lat0, lng0 = centroid(geom)
    return to_local_m(geom, lat0, lng0).area / 10_000


def perimeter_m(geom: dict[str, Any]) -> float:
    lat0, lng0 = centroid(geom)
    return to_local_m(geom, lat0, lng0).length


def validate_polygon(geom: dict[str, Any]) -> dict[str, Any]:
    """Menutup ring, memperbaiki self-intersection, membulatkan 7 desimal (~1 cm)."""
    ring = [[round(float(x), 7), round(float(y), 7)] for x, y in _ring(geom)]
    if len(ring) < 3:
        raise ValueError("Poligon minimal 3 titik")
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    poly = Polygon(ring)
    if not poly.is_valid:
        fixed = make_valid(poly)
        if fixed.geom_type == "MultiPolygon":
            fixed = max(fixed.geoms, key=lambda g: g.area)
        if fixed.geom_type != "Polygon":
            raise ValueError("Poligon tidak valid")
        poly = fixed
    return {"type": "Polygon", "coordinates": [[[round(x, 7), round(y, 7)] for x, y in poly.exterior.coords]]}


def overlap(geom_a: dict[str, Any], geom_b: dict[str, Any]) -> tuple[float, dict[str, Any] | None]:
    """Luas tumpang tindih (ha) dan geometri irisannya (GeoJSON) jika ada."""
    a, b = shape(geom_a), shape(geom_b)
    if not a.intersects(b):
        return 0.0, None
    inter = a.intersection(b)
    if inter.is_empty or inter.area == 0:
        return 0.0, None
    if inter.geom_type == "MultiPolygon":
        inter = max(inter.geoms, key=lambda g: g.area)
    if inter.geom_type != "Polygon":
        return 0.0, None
    g = mapping(inter)
    g = {"type": "Polygon", "coordinates": [list(map(list, g["coordinates"][0]))]}
    return area_ha(g), g


def overlap_fraction(geom: dict[str, Any], other: dict[str, Any]) -> float:
    a = shape(geom)
    if a.area == 0:
        return 0.0
    b = shape(other)
    if not a.intersects(b):
        return 0.0
    return float(a.intersection(b).area / a.area)


def bbox(geom: dict[str, Any]) -> tuple[float, float, float, float]:
    return shape(geom).bounds  # minx(lng), miny(lat), maxx, maxy


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a)) / 1000


# ---------- Web Mercator (slippy map) ----------

def latlng_to_global_px(lat: float, lng: float, z: int) -> tuple[float, float]:
    siny = min(max(math.sin(math.radians(lat)), -0.9999), 0.9999)
    scale = TILE_SIZE * (2**z)
    x = (lng + 180.0) / 360.0 * scale
    y = (0.5 - math.log((1 + siny) / (1 - siny)) / (4 * math.pi)) * scale
    return x, y


def global_px_to_latlng(x: float, y: float, z: int) -> tuple[float, float]:
    scale = TILE_SIZE * (2**z)
    lng = x / scale * 360.0 - 180.0
    n = math.pi - 2.0 * math.pi * y / scale
    lat = math.degrees(math.atan(math.sinh(n)))
    return lat, lng


def meters_per_px(lat: float, z: int) -> float:
    return 156_543.03392 * math.cos(math.radians(lat)) / (2**z)
