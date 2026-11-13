from app.services.evidence import decide
from app.services.satellite.demo import simulate_layers, simulate_series
from app.services.timeseries import detect_changes


def _d(sc, prot=0.0, drop=None):
    s = simulate_series(sc, "e")
    layers = simulate_layers(sc, "e")
    if drop:
        layers[drop] = None
    return decide(layers, detect_changes(s.dates, s.ndvi), prot)


def test_rules():
    assert _d("sawit_tua_stabil").risk_level == "rendah"
    assert _d("dibuka_2019").risk_level == "rendah"
    assert _d("hutan_dibuka_2022").risk_level == "tinggi"
    assert _d("data_kurang").risk_level == "perlu_cek"


def test_replanting_is_not_deforestation():
    d = _d("peremajaan_2023")
    assert d.risk_level == "rendah" and d.is_replanting


def test_protected_area_overrides():
    d = _d("sawit_tua_stabil", prot=100)
    assert d.risk_level == "tinggi" and d.rule.startswith("aturan-0")


def test_missing_commodity_layer_is_cautious():
    # tanpa peta komoditas, peremajaan tidak boleh langsung dicap deforestasi
    assert _d("peremajaan_2023", drop="commodity_2020").risk_level == "perlu_cek"


def test_unreadable_real_map_never_yields_safe_from_simulation(monkeypatch):
    """Peta nyata aktif tetapi offline: lapisan simulasi tidak boleh menghasilkan status Aman."""
    from app.services import analysis

    geom = {"type": "Polygon", "coordinates": [[[102.3, -0.6], [102.301, -0.6], [102.301, -0.599], [102.3, -0.599], [102.3, -0.6]]]}
    monkeypatch.setattr(analysis.peta_gfw, "plot_layers", lambda g, p: (None, "tidak ada internet"))
    r = analysis.run(geom, "PK-UJI", "sawit_tua_stabil", force_demo=True, kawasan_policy="lokal")
    assert r["risk_level"] == "rendah" and r["data_source"] == "simulasi"  # PK_PETA_GFW=0: simulasi memang diminta
    monkeypatch.setattr(analysis, "PETA_GFW", True)
    r = analysis.run(geom, "PK-UJI", "sawit_tua_stabil", force_demo=True, kawasan_policy="lokal")
    assert r["risk_level"] == "perlu_cek" and r["evidence"]["rule"] == "aturan-peta-belum-terbaca"
    assert "simulasi" in r["headline"]
