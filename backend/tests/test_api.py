import os
import tempfile

os.environ["PK_DATA_DIR"] = tempfile.mkdtemp()
os.environ["PK_DB_URL"] = f"sqlite:///{os.environ['PK_DATA_DIR']}/test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_end_to_end_flow():
    with TestClient(app) as c:
        assert c.get("/api/health").json()["status"] == "ok"
        plots = c.get("/api/plots").json()
        assert len(plots) > 50
        p1 = plots[0]
        # tumpang tindih ditolak
        r = c.post("/api/plots", json={"farmer_name": "Uji Coba", "village": "Desa Uji", "geometry": p1["geometry"], "consent": True})
        assert r.status_code == 409
        # tanpa persetujuan ditolak
        g = {"type": "Polygon", "coordinates": [[[101.8, -0.3], [101.801, -0.3], [101.801, -0.299], [101.8, -0.299], [101.8, -0.3]]]}
        assert c.post("/api/plots", json={"farmer_name": "Uji Coba", "village": "Desa Uji", "geometry": g, "consent": False}).status_code == 422
        r = c.post("/api/plots", json={"farmer_name": "Uji Coba", "village": "Desa Uji", "geometry": g, "consent": True,
                                       "demo_scenario": "hutan_dibuka_2022", "planting_year_declared": 2012})
        assert r.status_code == 201, r.text
        new = r.json()
        assert new["risk_level"] == "tinggi" and new["planting_consistency"]
        # transaksi dari kebun berisiko ditahan
        t = c.post("/api/transactions", json={"plot_code": new["code"], "collector_id": 1, "weight_kg": 800}).json()
        assert t["check"]["decision"] == "ditahan"
        d = c.get("/api/dashboard").json()
        assert d["kpi"]["plots"] == len(plots) + 1
        top = d["collectors"][0]
        assert top["ai_level"] == "tinggi"
        fc = c.get(f"/api/plots/{p1['id']}/eudr.geojson").json()
        assert fc["features"][0]["properties"]["ProducerCountry"] == "ID"
