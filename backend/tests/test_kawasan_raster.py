"""Peta Kemenhut yang hanya bisa ditampilkan (kemampuan "Map"): status kawasan dibaca dari gambarnya."""
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np
import pytest
from PIL import Image

from app.services import kawasan, kawasan_gfw, kawasan_raster

YELLOW, WHITE, PURPLE = (255, 255, 0), (255, 255, 255), (173, 63, 255)
LAYER = {
    "id": 0, "name": "KWSHUTAN_AR_250K_JUNI2026_REV1", "type": "Feature Layer", "geometryType": "esriGeometryPolygon",
    "fields": [{"name": "FUNGSIKWS", "type": "esriFieldTypeInteger"}],
    "drawingInfo": {"renderer": {"type": "uniqueValue", "field1": "FUNGSIKWS", "uniqueValueInfos": [
        {"value": "100000", "label": "Kawasan Konservasi", "symbol": {"color": [*PURPLE, 255], "style": "esriSFSSolid"}},
        {"value": "100201", "label": "Kawasan Konservasi Laut", "symbol": {"color": [0, 0, 0, 0], "style": "esriSFSSolid"}},
        {"value": "100300", "label": "Hutan Produksi Tetap", "symbol": {"color": [*YELLOW, 255], "style": "esriSFSSolid"}},
        {"value": "100700", "label": "Area Penggunaan Lain", "symbol": {"color": [*WHITE, 255], "style": "esriSFSSolid"}},
    ]}},
}
SPLIT = 102.005  # barat = Hutan Produksi, timur = APL
PURPLE_BOX = (102.0062, -0.4950, 102.0080, -0.4932)
ODD_BOX = (102.0085, -0.4990, 102.0095, -0.4980)  # warna yang tidak ada di palet
SEA_LAT = -0.4910  # utara garis ini: laut (tembus pandang)


def world_rgba(lng: np.ndarray, lat: np.ndarray) -> np.ndarray:
    out = np.zeros(lng.shape + (4,), np.uint8)
    out[..., :3] = np.where((lng < SPLIT)[..., None], YELLOW, WHITE)
    out[..., 3] = 255
    edge = np.abs(lng - SPLIT) < 0.000003  # piksel tepi yang tercampur (anti-alias)
    out[edge, :3] = (255, 255, 128)
    inp = (lng >= PURPLE_BOX[0]) & (lng <= PURPLE_BOX[2]) & (lat >= PURPLE_BOX[1]) & (lat <= PURPLE_BOX[3])
    out[inp, :3] = PURPLE
    odd = (lng >= ODD_BOX[0]) & (lng <= ODD_BOX[2]) & (lat >= ODD_BOX[1]) & (lat <= ODD_BOX[3])
    out[odd, :3] = (20, 20, 20)
    out[lat > SEA_LAT, 3] = 0
    return out


class MapOnly(BaseHTTPRequestHandler):
    calls: list[str] = []

    def log_message(self, *a):
        pass

    def _json(self, body):
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        MapOnly.calls.append(u.path)
        if u.path.endswith("/MapServer"):
            return self._json({"capabilities": "Map", "layers": [{"id": 0, "name": LAYER["name"]}]})
        if u.path.endswith("/layers"):
            return self._json({"layers": [LAYER]})
        if u.path.endswith("/export"):
            assert q["imageSR"] == "4326" and q["format"] == "png32" and q["layers"] == "show:0"
            xmin, ymin, xmax, ymax = map(float, q["bbox"].split(","))
            w, h = map(int, q["size"].split(","))
            xs = xmin + (np.arange(w) + 0.5) * (xmax - xmin) / w
            ys = ymax - (np.arange(h) + 0.5) * (ymax - ymin) / h
            lng, lat = np.meshgrid(xs, ys)
            buf = io.BytesIO()
            Image.fromarray(world_rgba(lng, lat), "RGBA").save(buf, "PNG")
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.end_headers()
            self.wfile.write(buf.getvalue())
            return
        # identify / query ditolak, seperti layanan Kemenhut asli
        return self._json({"error": {"code": 400, "message": "Requested operation is not supported by this service."}})


@pytest.fixture()
def map_only(tmp_path, monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), MapOnly)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(kawasan, "KAWASAN_URL",
                        f"http://127.0.0.1:{srv.server_port}/server/rest/services/Peta_Interaktif_2026/KWSHUTAN_AR_250K/MapServer")
    monkeypatch.setattr(kawasan, "KAWASAN_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(kawasan, "local_areas", lambda: [])
    monkeypatch.setattr(kawasan, "local_extents", lambda: [])
    monkeypatch.setattr(kawasan_gfw, "ENABLED", False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    kawasan._mem.clear()
    kawasan.reset_breaker()
    MapOnly.calls = []
    yield srv
    srv.shutdown()
    kawasan._mem.clear()
    kawasan.reset_breaker()


def sq(lng, lat, d=0.0012):
    return {"type": "Polygon", "coordinates": [[[lng, lat], [lng + d, lat], [lng + d, lat + d], [lng, lat + d], [lng, lat]]]}


def test_palette_skips_transparent_symbols():
    pal = kawasan_raster.palette_from_layer(LAYER)
    assert [p["label"] for p in pal] == ["Kawasan Konservasi", "Hutan Produksi Tetap", "Area Penggunaan Lain"]


def test_pixels_matched_by_colour_with_tolerance():
    pal = kawasan_raster.palette_from_layer(LAYER)
    img = np.array([[[255, 255, 0, 255], [255, 255, 90, 255], [20, 20, 20, 255], [0, 0, 0, 0]]], np.uint8)  # 2: tepi kuning-putih
    idx, labels = kawasan_raster.classify_pixels(img, pal)
    assert [labels[i] if i >= 0 else None for i in idx[0]] == [
        "Hutan Produksi Tetap", "Hutan Produksi Tetap", kawasan_raster.UNKNOWN, None]


def test_plot_in_production_forest_is_read_from_image(map_only):
    r = kawasan.lookup(sq(102.0010, -0.4990), "online")
    assert r.checked and r.source == "kemenhut" and r.fungsi == "HP" and r.pct == pytest.approx(100, abs=0.5)
    assert "dibaca dari gambar" in r.source_label and "JUNI2026" in r.source_label
    assert not any("/identify" in c or "/query" in c for c in MapOnly.calls)  # tidak mencoba operasi yang ditolak
    n = len(MapOnly.calls)
    kawasan._mem.clear()
    kawasan.lookup(sq(102.0010, -0.4990), "online")  # dari cache disk
    assert len(MapOnly.calls) == n


def test_apl_conservation_and_boundary(map_only):
    apl = kawasan.lookup(sq(102.0060, -0.4990), "online")
    assert apl.checked and apl.pct == 0 and any(p["fungsi"] == "APL" for p in apl.parts)
    kons = kawasan.lookup(sq(102.0064, -0.4948, d=0.0012), "online")
    assert kons.fungsi == "KSA_KPA" and kons.pct == pytest.approx(100, abs=1)
    half = kawasan.lookup(sq(SPLIT - 0.0006, -0.4990), "online")  # setengah di hutan produksi
    assert half.fungsi == "HP" and half.pct == pytest.approx(50, abs=3)


def test_unknown_colour_is_flagged_not_cleared(map_only):
    r = kawasan.lookup(sq(102.0086, -0.4989, d=0.0008), "online")
    assert r.unknown_pct > 90 and r.pct == 0


def test_status_exposes_legend(map_only):
    kawasan.lookup(sq(102.0010, -0.4990), "online")
    st = kawasan.status()
    assert st["mode"] == "gambar" and st["layer_names"] == [LAYER["name"]]
    assert {(x["label"], x["fungsi"]) for x in st["legend"]} == {
        ("Kawasan Konservasi", "KSA_KPA"), ("Hutan Produksi Tetap", "HP"), ("Area Penggunaan Lain", "APL")}


# ----------------------------------------------------------------------------------------------
# Data asli: dua sel gambar peta Kemenhut Juni 2026 di lokasi demo (diambil 12 Nov 2026, piksel identik,
# SHA-256 dicocokkan) dan renderer resminya. Kebun Rina harus terbaca Hutan Produksi, kebun lain APL.
# ----------------------------------------------------------------------------------------------
from pathlib import Path  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
_UV = [("100000", "Kawasan Konservasi", (173, 63, 255, 255)), ("100200", "Kawasan Konservasi", (173, 63, 255, 255)),
       ("100201", "Kawasan Konservasi Laut", (0, 0, 0, 0)), ("100100", "Hutan Lindung", (2, 173, 0, 255)),
       ("100300", "Hutan Produksi Tetap", (255, 255, 0, 255)), ("100400", "Hutan Produksi Terbatas", (138, 242, 0, 255)),
       ("100500", "Hutan Produksi yang dapat di Konversi", (255, 94, 255, 255)),
       ("100700", "Area Penggunaan Lain", (255, 255, 255, 255)), ("500100", "Tubuh Air", (0, 197, 255, 255)),
       ("0", "Tidak Terdefinisi", (255, 0, 0, 255))]
REAL_LAYER = {**LAYER, "drawingInfo": {"renderer": {"type": "uniqueValue", "field1": "FUNGSIKWS", "uniqueValueInfos": [
    {"value": v, "label": lbl, "symbol": {"type": "esriSFS", "style": "esriSFSSolid", "color": list(c)}} for v, lbl, c in _UV]}}}
RINA = [[102.055021, -0.368102], [102.053734, -0.368085], [102.05366, -0.367036], [102.055018, -0.367051], [102.055021, -0.368102]]
JOKO = [[102.060705, -0.364856], [102.059121, -0.364881], [102.059094, -0.363662], [102.060633, -0.363596], [102.060705, -0.364856]]
SITI = [[102.064593, -0.366023], [102.06354, -0.365948], [102.063526, -0.364742], [102.06457, -0.364813], [102.064593, -0.366023]]


class RealCells(MapOnly):
    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        RealCells.calls.append(u.path)
        if u.path.endswith("/layers"):
            return self._json({"layers": [REAL_LAYER]})
        if u.path.endswith("/export"):
            xmin = float(q["bbox"].split(",")[0])
            f = FIX / f"kemenhut_2026_cell_-37_{round(xmin * 100)}.png"
            body = f.read_bytes() if f.exists() else b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "image/png" if f.exists() else "application/json")
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()


def test_real_kemenhut_cells_demo_plots(map_only, monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), RealCells)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(kawasan, "KAWASAN_URL", f"http://127.0.0.1:{srv.server_port}/server/rest/services/KWSHUTAN_AR_250K/MapServer")
    try:
        poly = lambda ring: {"type": "Polygon", "coordinates": [ring]}  # noqa: E731
        rina = kawasan.lookup(poly(RINA), "online")
        assert rina.source == "kemenhut" and rina.fungsi == "HP" and rina.pct == pytest.approx(100, abs=0.5)
        for ring in (JOKO, SITI):  # Joko melintasi dua sel
            r = kawasan.lookup(poly(ring), "online")
            assert r.checked and r.pct == 0 and r.unknown_pct == 0 and r.parts[0]["fungsi"] == "APL"
    finally:
        srv.shutdown()
