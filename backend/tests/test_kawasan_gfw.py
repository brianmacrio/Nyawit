"""Cadangan peta kawasan KLHK 2017 (Global Forest Watch): pembaca tile vektor + alur cek kebun."""
import math
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from shapely.geometry import box, shape

from app.services import kawasan, kawasan_gfw, mvt

FIXTURE = Path(__file__).parent / "fixtures" / "gfw_idn_forest_area_12_3206_2050.pbf"  # tile asli GFW, TN Tesso Nilo
TILE = (3206, 2050)
SYN_TILE = (3210, 2050)  # tile buatan: satu kotak Hutan Lindung di pojok kiri atas


def _sq(lng, lat, d=0.0012):
    return {"type": "Polygon", "coordinates": [[[lng, lat], [lng + d, lat], [lng + d, lat + d], [lng, lat + d], [lng, lat]]]}


def _sph_area_ha(ring):
    r, a = 6378137.0, 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        a += math.radians(x2 - x1) * (2 + math.sin(math.radians(y1)) + math.sin(math.radians(y2)))
    return abs(a * r * r / 2) / 1e4


# ------------------------------------------------------------------ pembaca MVT
def test_decodes_real_gfw_tile():
    layers = mvt.decode(FIXTURE.read_bytes())
    lyr = layers["idn_forest_area"]
    assert lyr["extent"] == 4096 and lyr["version"] == 2 and len(lyr["features"]) == 1
    f = lyr["features"][0]
    assert f["type"] == mvt.POLYGON and len(f["parts"]) == 1 and len(f["parts"][0]) == 476
    assert f["parts"][0][0] == (1543, -3785)  # sama dengan hasil @mapbox/vector-tile
    assert f["properties"]["desc_in"] == "Taman Nasional" and f["properties"]["gfw_fid"] == 14648
    g = mvt.feature_geojson(f, 12, *TILE, lyr["extent"])
    assert g["type"] == "Polygon"
    assert g["coordinates"][0][0] == pytest.approx([101.810452938, -0.094563918], abs=1e-8)
    # luas resmi TN Tesso Nilo di data ini 81.655 ha; poligon tile (presisi ~2 m) harus dekat
    assert 81_000 < _sph_area_ha(g["coordinates"][0]) < 83_000
    assert kawasan_gfw.fungsi_of(f["properties"]) == "KSA_KPA"


def _cmd(cid, count):
    return (cid & 7) | (count << 3)


def _zz(n):
    return (n << 1) ^ (n >> 31)


def _varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _ld(field, payload):
    return _varint(field << 3 | 2) + _varint(len(payload)) + payload


def _encode_polygon_tile(rings):
    cmds, x, y = [], 0, 0
    for ring in rings:
        (x0, y0), rest = ring[0], ring[1:]
        cmds += [_cmd(1, 1), _zz(x0 - x), _zz(y0 - y)]
        x, y = x0, y0
        cmds.append(_cmd(2, len(rest)))
        for px, py in rest:
            cmds += [_zz(px - x), _zz(py - y)]
            x, y = px, py
        cmds.append(_cmd(7, 1))
    geom = b"".join(_varint(c) for c in cmds)
    feat = _varint(3 << 3) + _varint(3) + _ld(4, geom) + _ld(2, _varint(0) + _varint(0))
    value = _ld(1, "Hutan Lindung".encode())
    layer = _ld(1, b"idn_forest_area") + _ld(2, feat) + _ld(3, b"desc_in") + _ld(4, value) + _varint(5 << 3) + _varint(4096)
    return _ld(3, layer)


def test_polygon_holes_and_parts_follow_winding():
    outer = [(0, 0), (1000, 0), (1000, 1000), (0, 1000)]   # luas positif (y ke bawah) = cincin luar
    hole = [(200, 200), (200, 400), (400, 400), (400, 200)]  # arah berlawanan = lubang
    second = [(2000, 0), (3000, 0), (3000, 1000), (2000, 1000)]  # cincin luar kedua = bagian baru
    data = _encode_polygon_tile([outer, hole, second])
    f = mvt.decode(data)["idn_forest_area"]["features"][0]
    assert f["properties"] == {"desc_in": "Hutan Lindung"}
    g = shape(mvt.feature_geojson(f, 12, *TILE, 4096))
    assert g.geom_type == "MultiPolygon" and len(g.geoms) == 2
    assert len(g.geoms[0].interiors) == 1
    assert kawasan_gfw.fungsi_of(f["properties"]) == "HL"


# ------------------------------------------------------------------ alur cek kebun
class FakeTiles(BaseHTTPRequestHandler):
    down = False
    calls: list[str] = []

    def log_message(self, *a):
        pass

    def do_GET(self):  # noqa: N802
        FakeTiles.calls.append(self.path)
        if FakeTiles.down:
            self.send_response(503)
            self.end_headers()
            return
        z, x, y = self.path.removesuffix(".pbf").split("/")[-3:]
        body = None
        if (int(x), int(y)) == TILE:
            body = FIXTURE.read_bytes()
        elif (int(x), int(y)) == SYN_TILE:
            body = _encode_polygon_tile([[(0, 0), (1000, 0), (1000, 1000), (0, 1000)]])
        if body is not None:
            self.send_response(200)
            self.send_header("Content-Type", "application/x-protobuf")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture()
def gfw(tmp_path, monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), FakeTiles)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(kawasan_gfw, "URL", f"http://127.0.0.1:{srv.server_port}/idn/{{z}}/{{x}}/{{y}}.pbf")
    monkeypatch.setattr(kawasan_gfw, "ENABLED", True)
    monkeypatch.setattr(kawasan_gfw, "KAWASAN_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(kawasan, "KAWASAN_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(kawasan, "KAWASAN_URL", "http://127.0.0.1:9/kemenhut-mati")
    monkeypatch.setattr(kawasan, "local_areas", lambda: [])
    monkeypatch.setattr(kawasan, "local_extents", lambda: [])
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    kawasan._mem.clear()
    kawasan_gfw.clear_caches()
    kawasan.reset_breaker()
    FakeTiles.down = False
    FakeTiles.calls = []
    yield srv
    srv.shutdown()
    kawasan_gfw.clear_caches()
    kawasan.reset_breaker()


def _tn():
    lyr = mvt.decode(FIXTURE.read_bytes())["idn_forest_area"]
    return shape(mvt.feature_geojson(lyr["features"][0], 12, *TILE, lyr["extent"]))


def _points_in_tile(inside: bool):
    tn = _tn()
    w, n = mvt.tile_to_lnglat(12, *TILE, 4096, 0, 0)
    e, s = mvt.tile_to_lnglat(12, *TILE, 4096, 4096, 4096)
    for i in range(1, 20):
        for j in range(1, 20):
            lng, lat = w + (e - w) * i / 20, s + (n - s) * j / 20
            sq = shape(_sq(lng, lat))
            if box(w, s, e, n).contains(sq) and (tn.contains(sq) if inside else not tn.intersects(sq)):
                return lng, lat
    return None


def test_plot_inside_national_park_is_flagged(gfw):
    lng, lat = _points_in_tile(inside=True)
    r = kawasan.lookup(_sq(lng, lat), "gfw")
    assert r.checked and r.source == "klhk_gfw" and r.fungsi == "KSA_KPA" and r.pct == 100.0
    assert "KLHK 2017" in r.source_label


def test_auto_falls_back_to_gfw_when_kemenhut_is_down(gfw):
    lng, lat = _points_in_tile(inside=True)
    r = kawasan.lookup(_sq(lng, lat), "auto")
    assert r.checked and r.source == "klhk_gfw" and r.pct == 100.0
    assert any("KLHK 2017" in w for w in r.warnings)
    # tile kedua kali dibaca dari cache, tidak diunduh ulang
    n = len(FakeTiles.calls)
    kawasan_gfw.clear_caches()
    kawasan.lookup(_sq(lng, lat), "gfw")
    assert len(FakeTiles.calls) == n


def test_plot_outside_is_checked_and_clear(gfw):
    w, n = mvt.tile_to_lnglat(12, *SYN_TILE, 4096, 0, 0)
    e, s = mvt.tile_to_lnglat(12, *SYN_TILE, 4096, 4096, 4096)
    inside = kawasan.lookup(_sq(w + 0.002, n - 0.004), "gfw")
    assert inside.checked and inside.fungsi == "HL" and inside.pct == 100.0
    outside = kawasan.lookup(_sq((w + e) / 2, (n + s) / 2), "gfw")
    assert outside.checked and outside.pct == 0.0 and outside.source == "klhk_gfw"


def test_missing_tile_is_an_error_not_clear(gfw):
    r = kawasan.lookup(_sq(103.5, -0.5), "gfw")  # server menjawab 404
    assert not r.checked and r.warnings


def test_gfw_down_without_cache_is_not_checked(gfw):
    FakeTiles.down = True
    lng, lat = _points_in_tile(inside=True)
    r = kawasan.lookup(_sq(lng, lat), "auto")
    assert not r.checked and r.source == "tidak_ada" and r.warnings


def test_map_features_for_layer(gfw):
    w, n = mvt.tile_to_lnglat(12, *TILE, 4096, 0, 0)
    e, s = mvt.tile_to_lnglat(12, *TILE, 4096, 4096, 4096)
    w, s, e, n = w + 1e-4, s + 1e-4, e - 1e-4, n - 1e-4  # tetap di dalam satu tile
    feats = kawasan_gfw.map_features((w, s, e, n), tolerance=0.0001)
    assert len(feats) == 1 and feats[0]["properties"]["fungsi"] == "KSA_KPA"
    assert box(w - 1e-6, s - 1e-6, e + 1e-6, n + 1e-6).contains(shape(feats[0]["geometry"]))
