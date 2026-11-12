"""Pembaca Mapbox Vector Tile (MVT v2) yang kecil, tanpa dependensi tambahan.

Dipakai untuk membaca tile vektor peta kawasan hutan dari Global Forest Watch. Hanya bagian
spesifikasi yang dibutuhkan: layer, atribut, dan geometri (titik, garis, poligon).
Spesifikasi: https://github.com/mapbox/vector-tile-spec/tree/master/2.1
"""
from __future__ import annotations

import gzip
import math
import struct
from typing import Any, Iterator

# --------------------------------------------------------------------------------------
# Protobuf minimal
# --------------------------------------------------------------------------------------


def _varint(buf: bytes, i: int) -> tuple[int, int]:
    shift = result = 0
    while True:
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, i
        shift += 7
        if shift > 70:
            raise ValueError("varint terlalu panjang")


def _fields(buf: bytes) -> Iterator[tuple[int, int, Any]]:
    i, n = 0, len(buf)
    while i < n:
        key, i = _varint(buf, i)
        num, wt = key >> 3, key & 7
        if wt == 0:
            v, i = _varint(buf, i)
        elif wt == 1:
            v, i = buf[i:i + 8], i + 8
        elif wt == 2:
            ln, i = _varint(buf, i)
            v, i = buf[i:i + ln], i + ln
        elif wt == 5:
            v, i = buf[i:i + 4], i + 4
        else:
            raise ValueError(f"wire type {wt} tidak didukung")
        yield num, wt, v


def _packed(buf: bytes) -> list[int]:
    out, i = [], 0
    while i < len(buf):
        v, i = _varint(buf, i)
        out.append(v)
    return out


def _zigzag(n: int) -> int:
    return (n >> 1) ^ -(n & 1)


def _value(buf: bytes) -> Any:
    for num, _wt, v in _fields(buf):
        if num == 1:
            return v.decode("utf-8", errors="replace")
        if num == 2:
            return struct.unpack("<f", v)[0]
        if num == 3:
            return struct.unpack("<d", v)[0]
        if num == 4:
            return v - (1 << 64) if v >= 1 << 63 else v
        if num == 5:
            return v
        if num == 6:
            return _zigzag(v)
        if num == 7:
            return bool(v)
    return None


# --------------------------------------------------------------------------------------
# Geometri
# --------------------------------------------------------------------------------------
POINT, LINESTRING, POLYGON = 1, 2, 3


def _geometry(cmds: list[int]) -> list[list[tuple[int, int]]]:
    """Perintah MoveTo/LineTo/ClosePath -> daftar bagian (cincin/garis/titik) dalam koordinat tile."""
    parts: list[list[tuple[int, int]]] = []
    cur: list[tuple[int, int]] = []
    x = y = 0
    i = 0
    while i < len(cmds):
        cid, count = cmds[i] & 7, cmds[i] >> 3
        i += 1
        if cid == 1:  # MoveTo
            for _ in range(count):
                x += _zigzag(cmds[i])
                y += _zigzag(cmds[i + 1])
                i += 2
                if cur:
                    parts.append(cur)
                cur = [(x, y)]
        elif cid == 2:  # LineTo
            for _ in range(count):
                x += _zigzag(cmds[i])
                y += _zigzag(cmds[i + 1])
                i += 2
                cur.append((x, y))
        elif cid == 7:  # ClosePath
            if cur:
                cur.append(cur[0])
        else:
            raise ValueError(f"perintah geometri {cid} tidak dikenal")
    if cur:
        parts.append(cur)
    return parts


def _signed_area(ring: list[tuple[float, float]]) -> float:
    s = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        s += x1 * y2 - x2 * y1
    return s / 2


def classify_rings(rings: list[list[tuple[float, float]]]) -> list[list[int]]:
    """Kelompokkan cincin menjadi poligon [indeks luar, indeks lubang...] menurut arah putarnya
    (spesifikasi MVT 4.3.4.4). Arah cincin luar diambil dari cincin pertama, sehingga tile lama
    yang arah putarnya terbalik tetap terbaca."""
    polys: list[list[int]] = []
    outer_sign = 0
    for idx, r in enumerate(rings):
        if len(r) < 4:
            continue
        a = _signed_area(r)
        if a == 0:
            continue
        sign = 1 if a > 0 else -1
        if outer_sign == 0:
            outer_sign = sign
        if sign == outer_sign or not polys:
            polys.append([idx])
        else:
            polys[-1].append(idx)
    return polys


def tile_to_lnglat(z: int, tx: int, ty: int, extent: int, px: float, py: float) -> tuple[float, float]:
    n = 2 ** z
    lng = (tx + px / extent) / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (ty + py / extent) / n))))
    return lng, lat


def lnglat_to_tile(lng: float, lat: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    lat = max(min(lat, 85.0511), -85.0511)
    x = int((lng + 180.0) / 360.0 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def tiles_for_bounds(bounds: tuple[float, float, float, float], z: int) -> list[tuple[int, int]]:
    minx, miny, maxx, maxy = bounds
    x0, y0 = lnglat_to_tile(minx, maxy, z)
    x1, y1 = lnglat_to_tile(maxx, miny, z)
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


# --------------------------------------------------------------------------------------
# Tile
# --------------------------------------------------------------------------------------


def decode(data: bytes) -> dict[str, dict]:
    """{nama_layer: {"extent": int, "version": int, "features": [{"id", "type", "properties", "parts"}]}}"""
    for _ in range(3):  # tile bisa dikirim terkompresi (Content-Encoding: gzip), kadang dua lapis
        if data[:2] != b"\x1f\x8b":
            break
        data = gzip.decompress(data)
    layers: dict[str, dict] = {}
    for num, _wt, lbuf in _fields(data):
        if num != 3:
            continue
        name, extent, version = "", 4096, 1
        keys: list[str] = []
        values: list[Any] = []
        raw_feats: list[bytes] = []
        for fnum, _fwt, v in _fields(lbuf):
            if fnum == 1:
                name = v.decode("utf-8", errors="replace")
            elif fnum == 2:
                raw_feats.append(v)
            elif fnum == 3:
                keys.append(v.decode("utf-8", errors="replace"))
            elif fnum == 4:
                values.append(_value(v))
            elif fnum == 5:
                extent = v
            elif fnum == 15:
                version = v
        feats = []
        for fb in raw_feats:
            fid, gtype, tags, geom = None, 0, [], []
            for gnum, gwt, v in _fields(fb):
                if gnum == 1:
                    fid = v
                elif gnum == 2:
                    tags = _packed(v) if gwt == 2 else [v]
                elif gnum == 3:
                    gtype = v
                elif gnum == 4:
                    geom = _packed(v) if gwt == 2 else [v]
            props = {keys[tags[k]]: values[tags[k + 1]] for k in range(0, len(tags) - 1, 2)
                     if tags[k] < len(keys) and tags[k + 1] < len(values)}
            feats.append({"id": fid, "type": gtype, "properties": props, "parts": _geometry(geom)})
        layers[name] = {"extent": extent, "version": version, "features": feats}
    return layers


def feature_geojson(feat: dict, z: int, tx: int, ty: int, extent: int) -> dict | None:
    """Fitur MVT -> geometri GeoJSON (lng, lat)."""
    conv = [[list(tile_to_lnglat(z, tx, ty, extent, px, py)) for px, py in part] for part in feat["parts"]]
    if feat["type"] == POLYGON:
        # arah putar dihitung di koordinat tile (y ke bawah), sesuai spesifikasi
        groups = classify_rings(feat["parts"])
        polys = [[conv[i] for i in g] for g in groups]
        if not polys:
            return None
        return {"type": "Polygon", "coordinates": polys[0]} if len(polys) == 1 else {"type": "MultiPolygon", "coordinates": polys}
    if feat["type"] == LINESTRING:
        return {"type": "MultiLineString", "coordinates": conv}
    if feat["type"] == POINT:
        return {"type": "MultiPoint", "coordinates": [p[0] for p in conv if p]}
    return None
