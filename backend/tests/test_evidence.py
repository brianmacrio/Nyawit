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
