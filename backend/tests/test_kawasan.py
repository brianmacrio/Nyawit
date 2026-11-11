"""Cek kawasan hutan otomatis: klasifikasi atribut + alur HTTP ke server ArcGIS REST tiruan."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from app.services import evidence, kawasan

# kebun uji 200 m x 200 m; separuh barat masuk Hutan Lindung, separuh timur APL
LNG0, LAT0, D = 101.7505, -0.2055, 0.0018
PLOT = {"type": "Polygon", "coordinates": [[[LNG0, LAT0], [LNG0 + D, LAT0], [LNG0 + D, LAT0 + D], [LNG0, LAT0 + D], [LNG0, LAT0]]]}
MID = LNG0 + D / 2


def _rect(x0, y0, x1, y1):  # ring Esri: luar searah jarum jam
    return [[x0, y0], [x0, y1], [x1, y1], [x1, y0], [x0, y0]]


LAYERS = {"layers": [
    {"id": 0, "name": "Kawasan Hutan", "type": "Feature Layer", "geometryType": "esriGeometryPolygon",
     "fields": [{"name": "FUNGSIKWS", "alias": "Fungsi", "type": "esriFieldTypeInteger",
                 "domain": {"type": "codedValue", "codedValues": [{"code": 1003, "name": "Hutan Lindung"},
                                                                    {"code": 5003, "name": "Areal Penggunaan Lain"}]}},
                {"name": "NAMOBJ", "alias": "Nama", "type": "esriFieldTypeString"}]},
    {"id": 1, "name": "Perubahan Peruntukan Kawasan Hutan", "type": "Feature Layer", "geometryType": "esriGeometryPolygon",
     "fields": []},
]}
HL = {"rings": [_rect(LNG0 - 0.01, LAT0 - 0.01, MID, LAT0 + 0.01)]}
APL = {"rings": [_rect(MID, LAT0 - 0.01, LNG0 + 0.01, LAT0 + 0.01)]}


class FakeArcGIS(BaseHTTPRequestHandler):
    identify_broken = False
    calls: list[str] = []

    def log_message(self, *a):  # noqa: D401 - senyap
        pass

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        FakeArcGIS.calls.append(u.path)
        if u.path.endswith("/layers"):
            body = LAYERS
        elif u.path.endswith("/identify"):
            if FakeArcGIS.identify_broken:
                body = {"error": {"code": 400, "message": "Unable to complete operation."}}
            else:
                assert q["layers"] == "all:0"  # layer "Perubahan ..." tidak ikut
                body = {"results": [
                    {"layerId": 0, "layerName": "Kawasan Hutan", "attributes": {"FUNGSIKWS": "Hutan Lindung", "NAMOBJ": "HL Bukit Uji"},
                     "geometryType": "esriGeometryPolygon", "geometry": HL},
                    {"layerId": 0, "layerName": "Kawasan Hutan", "attributes": {"FUNGSIKWS": "Areal Penggunaan Lain", "NAMOBJ": "Null"},
                     "geometryType": "esriGeometryPolygon", "geometry": APL},
                ]}
        elif u.path.endswith("/0/query"):
            body = {"features": [{"attributes": {"FUNGSIKWS": 1003, "NAMOBJ": "HL Bukit Uji"}, "geometry": HL},
                                 {"attributes": {"FUNGSIKWS": 5003}, "geometry": APL}]}
        else:
            body = {"error": {"code": 404, "message": "not found"}}
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture()
def fake_service(tmp_path, monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), FakeArcGIS)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    monkeypatch.setattr(kawasan, "KAWASAN_URL", f"http://127.0.0.1:{srv.server_port}/arcgis/rest/services/Kawasan_Hutan/MapServer")
    monkeypatch.setattr(kawasan, "KAWASAN_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(kawasan, "local_areas", lambda: [])
    monkeypatch.setattr(kawasan, "local_extents", lambda: [])
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    kawasan._mem.clear()
    kawasan.reset_breaker()
    FakeArcGIS.calls = []
    FakeArcGIS.identify_broken = False
    yield srv
    srv.shutdown()
    kawasan._mem.clear()
    kawasan.reset_breaker()


@pytest.mark.parametrize("attrs,expected", [
    ({"FUNGSIKWS": "Hutan Lindung"}, "HL"),
    ({"Fungsi": "HPT"}, "HPT"),
    ({"FUNGSI": "Hutan Produksi yang dapat Dikonversi"}, "HPK"),
    ({"FUNGSI": "Hutan Produksi Tetap"}, "HP"),
    ({"FUNGSIKWS": "KSA/KPA", "NAMOBJ": "TN Tesso Nilo"}, "KSA_KPA"),
    ({"NAMA_KAWAS": "TN Tesso Nilo", "fungsikws": 1004}, "KSA_KPA"),
    ({"FUNGSIKWS": "APL"}, "APL"),
    ({"KETERANGAN": "Areal Penggunaan Lain"}, "APL"),
    ({"NAMOBJ": "Kelompok Hutan Air Sebakul"}, "?"),  # nama tidak boleh dibaca sebagai "tubuh air"
    ({"fungsikws": 1004}, "?"),  # kode angka tanpa domain: jujur "tidak terbaca"
])
def test_classify(attrs, expected):
    assert kawasan.classify(attrs) == expected


def test_online_lookup_identify_and_cache(fake_service):
    r = kawasan.lookup(PLOT, "online")
    assert r.checked and r.source == "kemenhut"
    assert 45 <= r.pct <= 55 and r.fungsi == "HL" and r.name == "HL Bukit Uji"
    assert {p["fungsi"] for p in r.parts} == {"HL", "APL"}
    n = len(FakeArcGIS.calls)
    # panggilan kedua dilayani cache tanpa menghubungi server
    r2 = kawasan.lookup(PLOT, "online")
    assert len(FakeArcGIS.calls) == n and r2.pct == r.pct
    # keputusan risiko memakai nama fungsi
    d = evidence.decide({}, None, r.pct, kawasan=r.to_dict(), strict=True)
    assert d.risk_level == "tinggi" and "Hutan Lindung" in d.headline


def test_query_fallback_decodes_domain(fake_service):
    FakeArcGIS.identify_broken = True
    r = kawasan.lookup(PLOT, "online")
    assert r.checked and r.fungsi == "HL" and 45 <= r.pct <= 55
    assert any(c.endswith("/0/query") for c in FakeArcGIS.calls)


def test_offline_falls_back_and_flags(monkeypatch, tmp_path):
    monkeypatch.setattr(kawasan, "KAWASAN_URL", "http://127.0.0.1:9/tidak-ada")
    monkeypatch.setattr(kawasan, "KAWASAN_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(kawasan, "local_areas", lambda: [])
    monkeypatch.setattr(kawasan, "local_extents", lambda: [])
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    kawasan._mem.clear()
    kawasan.reset_breaker()
    r = kawasan.lookup(PLOT, "auto")
    assert not r.checked and r.source == "tidak_ada" and r.warnings
    assert kawasan._state["offline_until"] > 0  # pemutus sirkuit aktif: panggilan berikut tidak menunggu
    # mode live: hasil satelit aman tidak boleh jadi "Aman" tanpa cek kawasan
    layers = {"tree_cover_2020": 0.0, "commodity_2020": 90.0, "disturbance_before_2021": 0.0, "disturbance_after_2020": 0.0}
    assert evidence.decide(layers, None, 0.0, kawasan=r.to_dict(), strict=True).risk_level == "perlu_cek"
    assert evidence.decide(layers, None, 0.0, kawasan=r.to_dict(), strict=False).risk_level == "rendah"
    kawasan.reset_breaker()
