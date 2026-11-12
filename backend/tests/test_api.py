import base64
import io
import os
import tempfile
import zipfile
from datetime import date, timedelta

os.environ["PK_DATA_DIR"] = tempfile.mkdtemp()
os.environ["PK_DB_URL"] = f"sqlite:///{os.environ['PK_DATA_DIR']}/test.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.config import DEMO_PASSWORD  # noqa: E402
from app.main import app  # noqa: E402
from app.security import limiter  # noqa: E402

CSRF = {"X-Requested-With": "PasporKebun"}


def sq(lng0: float, lat0: float, d: float = 0.001) -> dict:
    return {"type": "Polygon", "coordinates": [[[lng0, lat0], [lng0 + d, lat0], [lng0 + d, lat0 + d], [lng0, lat0 + d], [lng0, lat0]]]}


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        client.headers.update(CSRF)
        yield client


def as_(c: TestClient, username: str) -> dict:
    limiter.reset()
    r = c.post("/api/auth/demo", json={"username": username})
    assert r.status_code == 200, r.text
    return r.json()


def test_auth_and_csrf(c):
    c.post("/api/auth/logout")
    assert c.get("/api/health").json()["status"] == "ok"
    assert c.get("/api/plots").status_code == 401
    # tanpa header CSRF: ditolak sebelum menyentuh data
    assert c.post("/api/auth/login", json={"username": "koperasi", "password": DEMO_PASSWORD},
                  headers={"X-Requested-With": ""}).status_code == 403
    assert c.post("/api/auth/login", json={"username": "koperasi", "password": "salah"}).status_code == 401
    r = c.post("/api/auth/login", json={"username": "koperasi", "password": DEMO_PASSWORD})
    assert r.status_code == 200 and r.json()["role"] == "koperasi"
    assert "httponly" in r.headers["set-cookie"].lower()
    assert c.get("/api/auth/me").json()["user"]["username"] == "koperasi"
    # header keamanan
    h = c.get("/api/health").headers
    assert h["x-content-type-options"] == "nosniff" and "frame-ancestors 'none'" in h["content-security-policy"]


def test_role_enforced(c):
    as_(c, "pengepul")
    g = sq(102.095, -0.345)  # APL menurut salinan peta KLHK 2017 di area demo
    r = c.post("/api/plots", json={"farmer_name": "Uji", "village": "Desa", "geometry": g, "consent": True})
    assert r.status_code == 403 and "koperasi" in r.json()["detail"]
    assert c.get("/api/dashboard").status_code == 403
    assert c.post("/api/demo/reset").status_code == 403


def test_end_to_end_flow(c):
    as_(c, "koperasi")
    plots = c.get("/api/plots").json()
    assert len(plots) > 50 and "eudr_ready" in plots[0]
    p1 = plots[0]
    # tumpang tindih ditolak
    r = c.post("/api/plots", json={"farmer_name": "Uji Coba", "village": "Desa Uji", "geometry": p1["geometry"], "consent": True})
    assert r.status_code == 409
    g = sq(102.095, -0.345)  # APL menurut salinan peta KLHK 2017 di area demo
    assert c.post("/api/plots", json={"farmer_name": "Uji Coba", "village": "Desa Uji", "geometry": g, "consent": False}).status_code == 422
    r = c.post("/api/plots", json={"farmer_name": "Uji Coba", "village": "Desa Uji", "geometry": g, "consent": True,
                                   "demo_scenario": "hutan_dibuka_2022", "planting_year_declared": 2012})
    assert r.status_code == 201, r.text
    new = r.json()
    assert new["risk_level"] == "tinggi" and new["planting_consistency"]
    assert not new["readiness"]["ready"] and new["history"][0]["action"] == "cek_satelit"
    # transaksi dari kebun berisiko ditahan; pengepul tidak bisa memalsukan identitas pengepul lain
    as_(c, "pengepul")
    t = c.post("/api/transactions", json={"plot_code": new["code"], "collector_id": 3, "weight_kg": 800}).json()
    assert t["check"]["decision"] == "ditahan" and t["transaction"]["collector"] == "UD Tani Jaya"
    as_(c, "pabrik")
    d = c.get("/api/dashboard").json()
    assert d["kpi"]["plots"] == len(plots) + 1 and 0 < d["kpi"]["eudr_ready"] < d["kpi"]["plots"]
    assert d["collectors"][0]["ai_level"] == "tinggi"
    fc = c.get(f"/api/plots/{p1['id']}/eudr.geojson").json()
    props = fc["features"][0]["properties"]
    assert props["ProducerCountry"] == "ID" and "ProducerName" not in props  # tanpa data pribadi


def test_registration_with_land_and_readiness(c):
    as_(c, "koperasi")
    base = {"village": "Desa Uji", "consent": True, "demo_scenario": "sawit_tua_stabil",
            "witnesses": [{"name": "Ketua Poktan Uji", "relation": "ketua kelompok tani"},
                          {"name": "Tetangga Uji", "relation": "tetangga utara"}],
            "boundary_sides": {"utara": {"jenis": "parit"}, "timur": {"jenis": "kebun", "tetangga": "Pak X"}},
            "gps": {"lat": -0.3495, "lng": 102.1005, "accuracy_m": 6}}
    ok = c.post("/api/plots", json={**base, "farmer_name": "Petani Siap", "geometry": sq(102.100, -0.350),
                                    "land_proof": "surat_desa", "stdb_status": "proses"}).json()
    assert ok["readiness"]["ready"], ok["readiness"]
    assert ok["readiness"]["precision"]["level"] == 3 and ok["gps"]["accuracy_m"] == 6
    nope = c.post("/api/plots", json={**base, "farmer_name": "Petani Belum", "geometry": sq(102.103, -0.350),
                                      "land_proof": "surat_desa", "stdb_status": "belum"}).json()
    lahan = next(x for x in nope["readiness"]["checks"] if x["key"] == "lahan")
    assert not nope["readiness"]["ready"] and not lahan["ok"] and "STDB" in lahan["detail"]
    # melengkapi STDB membuat kebun siap, dan perubahannya tercatat di riwayat
    upd = c.patch(f"/api/plots/{nope['id']}", json={"stdb_status": "ada", "stdb_number": "STDB-9"}).json()
    assert upd["readiness"]["ready"] and upd["history"][0]["action"] == "kebun_diubah"
    # paspor publik: tanpa login, nama disamarkan
    c.post("/api/auth/logout")
    pub = c.get(f"/api/public/passport/{ok['code']}").json()
    assert pub["farmer"] == "Petani S." and pub["eudr_ready"] is True


def test_fit_neighbors(c):
    as_(c, "koperasi")
    plots = c.get("/api/plots").json()
    target = plots[0]
    ring = target["geometry"]["coordinates"][0]
    lngs = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    # draf yang melebar ke kebun tetangga di sebelah barat
    draft = {"type": "Polygon", "coordinates": [[[min(lngs) - 0.0012, min(lats)], [min(lngs) + 0.0005, min(lats)],
                                                  [min(lngs) + 0.0005, max(lats)], [min(lngs) - 0.0012, max(lats)],
                                                  [min(lngs) - 0.0012, min(lats)]]]}
    r = c.post("/api/plots/fit-neighbors", json={"geometry": draft}).json()
    assert r["removed_ha"] > 0 and any(n["code"] == target["code"] for n in r["neighbors"])
    chk = c.post("/api/plots/check-overlap", json={"geometry": r["geometry"]}).json()
    assert all(o["overlap_ha"] < 0.05 for o in chk["overlaps"])


def test_appeal_and_override(c):
    as_(c, "koperasi")
    plots = c.get("/api/plots").json()
    risky = next(p for p in plots if p["risk_level"] == "perlu_cek")
    a = c.post("/api/appeals", json={"plot_id": risky["id"], "reason": "Citra berawan; foto lapangan menunjukkan sawit tua.",
                                     "evidence_type": "foto_lapangan"})
    assert a.status_code == 201, a.text
    assert c.post(f"/api/appeals/{a.json()['id']}/decide", json={"accept": True, "note": "Foto lapangan meyakinkan.",
                                                                  "new_risk": "rendah"}).status_code == 403
    as_(c, "verifikator")
    d = c.post(f"/api/appeals/{a.json()['id']}/decide", json={"accept": True, "new_risk": "rendah",
                                                               "note": "Foto bergeotag menunjukkan sawit tua; awan menutupi citra."})
    assert d.status_code == 200 and d.json()["status"] == "diterima"
    p = c.get(f"/api/plots/{risky['id']}").json()
    assert p["risk_level"] == "rendah" and p["override"]["original"] == "perlu_cek"
    # bukti satelit baru menggantikan keputusan lama (harus ditinjau ulang)
    p = c.post(f"/api/plots/{risky['id']}/analyze").json()
    assert p["override"] is None and p["risk_level"] == "perlu_cek"
    v = c.get("/api/audit/verify").json()
    assert v["ok"] and v["events"] > 100


def _png(color=(30, 120, 60)) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def test_inspection_with_photo(c):
    as_(c, "verifikator")
    lst = c.get("/api/inspections").json()
    assert lst["sample_size"] >= 20
    c.post("/api/inspections/sample", json={"batch": "uji"})
    pend = [i for i in c.get("/api/inspections?status=menunggu").json()["items"]]
    assert pend
    i = pend[0]
    bad = c.post(f"/api/inspections/{i['id']}/result", json={"result": "sesuai", "photo": "data:image/png;base64,bm90IGFuIGltYWdl"})
    assert bad.status_code == 422
    far_lat = i["centroid"][0] + 0.01  # ~1,1 km dari kebun
    r = c.post(f"/api/inspections/{i['id']}/result", json={"result": "tidak_sesuai", "notes": "Batas tidak sesuai",
                                                             "photo": _png(), "lat": far_lat, "lng": i["centroid"][1]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["inspection"]["status"] == "selesai" and body["warnings"] and body["inspection"]["photo_distance_m"] > 900
    img = c.get(f"/api/inspections/{i['id']}/photo")
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    plot = c.get(f"/api/plots/{i['plot_id']}").json()
    assert not next(x for x in plot["readiness"]["checks"] if x["key"] == "verifikasi")["ok"]


def test_shipment_package(c):
    as_(c, "pabrik")
    today = date.today()
    r = c.post("/api/shipments", json={"buyer": "Importir Uji GmbH", "period_start": (today - timedelta(days=90)).isoformat(),
                                       "period_end": today.isoformat()})
    assert r.status_code == 201, r.text
    s = r.json()
    sm = s["summary"]
    assert sm["n_included"] > 0 and sm["n_excluded"] > 0 and sm["included_kg"] > 0
    assert all(not e["failed_checks"] for e in s["plots"]) and all(e["failed_checks"] for e in s["excluded"])
    z = zipfile.ZipFile(io.BytesIO(c.get(f"/api/shipments/{s['id']}/package.zip").content))
    assert {"README.txt", "geolokasi_kebun.geojson", "ringkasan_kebun.csv", "kebun_dikeluarkan.csv"} <= set(z.namelist())
    gj = z.read("geolokasi_kebun.geojson").decode()
    assert "Budi" not in gj and '"DeforestationFree": true' in gj


def test_audit_chain_detects_tampering(c):
    from sqlalchemy import text

    from app.db import engine

    as_(c, "verifikator")
    assert c.get("/api/audit/verify").json()["ok"]
    with engine.begin() as conn:
        conn.execute(text("UPDATE audit_events SET summary = 'diubah diam-diam' WHERE id = 5"))
    v = c.get("/api/audit/verify").json()
    assert not v["ok"] and v["broken_at"] == 5


def test_login_rate_limit(c):
    limiter.reset()
    codes = [c.post("/api/auth/login", json={"username": "xx", "password": "y"}).status_code for _ in range(12)]
    assert codes[0] == 401 and codes[-1] == 429
    limiter.reset()


def test_demo_plots_use_real_forest_map(c):
    """Batas kawasan di demo adalah salinan peta KLHK 2017 (GFW), bukan ilustrasi; hanya kebun Rina di dalamnya."""
    as_(c, "koperasi")
    areas = c.get("/api/plots/protected-areas").json()
    assert areas and not any(a["is_demo"] for a in areas) and all(a["gfw_fid"] for a in areas)
    assert {a["fungsi"] for a in areas} >= {"HP", "KSA_KPA"}
    seeded = [p for p in c.get("/api/plots").json() if p["code"].startswith("PK-000")]
    in_kawasan = [p["code"] for p in seeded if "masuk" in (p["risk_headline"] or "") and "Hutan" in p["risk_headline"]]
    assert in_kawasan == ["PK-00005-Z"]
