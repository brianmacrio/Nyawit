"""Lapisan bukti dari peta nyata (Hansen + JRC lewat tile GFW): pembacaan piksel dan aturan keputusan."""
import numpy as np
import pytest

from app.services import evidence
from app.services.satellite import demo, peta_gfw as pg

Z = pg.Z


def _tiles_with(region_px, loss_b=None, forest=False, size=512, jsize=256):
    """Satu tile kehilangan (render 'encoded') + satu tile JRC; `region_px` = (i0, j0, i1, j1) di tile kehilangan."""
    loss = np.zeros((size, size, 4), np.uint8)
    loss[..., 0] = 1  # warna latar tile asli (tanpa kehilangan) memakai R=1, bukan 255
    jrc = np.zeros((jsize, jsize, 4), np.uint8)
    i0, j0, i1, j1 = region_px
    if loss_b is not None:
        loss[j0:j1, i0:i1] = (255, 120, loss_b, 255)
    if forest:
        s = jsize / size
        jrc[int(j0 * s):int(j1 * s), int(i0 * s):int(i1 * s)] = (114, 102, 249, 230)
    return {"loss": loss, "jrc": jrc}


def _box_for(tx, ty, i0, j0, i1, j1, size=512):
    """Poligon kebun yang menutupi persis piksel [i0,i1) x [j0,j1) pada tile (tx, ty)."""
    x0, y0 = tx * size + i0, ty * size + j0
    x1, y1 = tx * size + i1, ty * size + j1
    (lng0, lng1), (lat0, lat1) = pg.px_to_lnglat(np.array([x0, x1], float), np.array([y0, y1], float), Z, size)
    ring = [[lng0, lat1], [lng1, lat1], [lng1, lat0], [lng0, lat0], [lng0, lat1]]
    return {"type": "Polygon", "coordinates": [[[float(a), float(b)] for a, b in ring]]}


def _loader(tiles):
    return lambda kind, x, y: tiles[kind]


TX, TY = 12840, 8213  # tile zoom 14 di selatan desa demo (Riau)


def test_loss_year_decoding():
    px = np.array([[[255, 10, 23, 255], [255, 0, 5, 255], [1, 0, 0, 255], [255, 0, 23, 0]]], np.uint8)
    assert pg.loss_year(px).tolist() == [[2023, 2005, 0, 0]]


def test_projection_roundtrip():
    x, y = pg.lnglat_to_px(102.0625, -0.3645, Z, 512)
    lng, lat = pg.px_to_lnglat(np.array([x]), np.array([y]), Z, 512)
    assert abs(lng[0] - 102.0625) < 1e-9 and abs(lat[0] + 0.3645) < 1e-9
    assert pg.tiles_for((102.0972, -0.4331, 102.0988, -0.4319)) == [(12838, 8211)]


def test_forest_cleared_after_2020_counts_as_deforestation():
    region = (100, 100, 140, 140)
    tiles = _tiles_with(region, loss_b=25, forest=True)
    geom = _box_for(TX, TY, 100, 100, 140, 140)
    out = pg.compute(geom, _loader(tiles))
    assert out["pixels"] == 1600
    assert out["tree_cover_2020"] == 100.0 and out["disturbance_after_2020"] == 100.0
    assert out["loss_after_main_year"] == "2025" and out["disturbance_before_2021"] == 0.0
    d = evidence.decide(out, None, 0.0, forest_map="jrc", layer_sources=pg.LAYER_SOURCES)
    assert d.risk_level == "tinggi" and d.rule == "aturan-4" and "2025" in d.headline


def test_loss_on_non_forest_is_replanting_not_deforestation():
    tiles = _tiles_with((100, 100, 140, 140), loss_b=23, forest=False)
    out = pg.compute(_box_for(TX, TY, 100, 100, 140, 140), _loader(tiles))
    assert out["tree_cover_2020"] == 0.0 and out["disturbance_after_2020"] == 100.0
    d = evidence.decide(out, None, 0.0, forest_map="jrc")
    assert d.risk_level == "rendah" and d.rule == "aturan-1-peremajaan" and d.is_replanting
    item = next(i for i in d.items if i.key == "disturbance_after_2020")
    assert item.verdict == "netral" and "2023" in item.value  # indikator menyala, tetapi bukan bukti deforestasi


def test_partial_cover_and_pixel_counting():
    # kebun 40x40 px, hanya separuh barat yang hutan dan dibuka 2022
    tiles = _tiles_with((100, 100, 120, 140), loss_b=22, forest=True)
    out = pg.compute(_box_for(TX, TY, 100, 100, 140, 140), _loader(tiles))
    assert out["tree_cover_2020"] == 50.0 and out["loss_after_by_year"] == {"2022": 50.0}


def test_forest_without_loss_needs_field_check():
    tiles = _tiles_with((100, 100, 140, 140), loss_b=None, forest=True)
    out = pg.compute(_box_for(TX, TY, 100, 100, 140, 140), _loader(tiles))
    d = evidence.decide(out, None, 0.0, forest_map="jrc")
    assert d.risk_level == "perlu_cek" and d.rule == "aturan-5"


def test_hansen_tree_cover_without_commodity_layer_stays_cautious():
    """Tanpa peta JRC (tutupan pohon Hansen juga menangkap sawit), kehilangan sesudah 2020 belum tentu deforestasi."""
    layers = {"tree_cover_2020": 90, "commodity_2020": None, "disturbance_before_2021": 0, "disturbance_after_2020": 80}
    assert evidence.decide(layers, None, 0.0).risk_level == "perlu_cek"
    assert evidence.decide(layers, None, 0.0, forest_map="jrc").risk_level == "tinggi"


def test_plot_spanning_two_tiles():
    size = 512
    loss = np.zeros((size, size, 4), np.uint8)
    loss[..., 3] = 255
    jrc = np.zeros((256, 256, 4), np.uint8)
    tiles = {(TX, TY): {"loss": loss.copy(), "jrc": jrc}, (TX + 1, TY): {"loss": loss.copy(), "jrc": jrc}}
    tiles[(TX + 1, TY)]["loss"][100:140, 0:20] = (255, 0, 24, 255)  # separuh timur kebun: hilang 2024
    geom = _box_for(TX, TY, 492, 100, 532, 140)  # 20 px di tile barat + 20 px di tile timur
    out = pg.compute(geom, lambda k, x, y: tiles[(x, y)][k])
    assert out["pixels"] == 1600 and out["disturbance_after_2020"] == 50.0


def test_offline_without_cache_raises_cleanly(tmp_path, monkeypatch):
    monkeypatch.setattr(pg, "TS_CACHE_DIR", tmp_path)
    layers, err = pg.plot_layers(_box_for(TX, TY, 100, 100, 140, 140), "online")
    assert layers is None and err


def test_scenario_follows_real_map():
    f = demo.scenario_from_layers
    assert f({"tree_cover_2020": 100, "disturbance_after_2020": 100, "loss_after_main_year": "2025"}) == "hutan_dibuka_2025"
    assert f({"tree_cover_2020": 0, "disturbance_after_2020": 70, "loss_after_main_year": "2024"}) == "peremajaan_2024"
    assert f({"tree_cover_2020": 0, "disturbance_before_2021": 80, "loss_before_main_year": "2019"}) == "dibuka_2019"
    assert f({"tree_cover_2020": 92, "disturbance_after_2020": 0}) == "data_kurang"
    assert f({"tree_cover_2020": 0}, kawasan_pct=100) == "kawasan_hutan"
    assert f({"tree_cover_2020": 0, "disturbance_before_2021": 60, "loss_before_main_year": "2004"}) == "sawit_tua_stabil"


@pytest.mark.parametrize("sc", ["hutan_dibuka_2025", "peremajaan_2024", "dibuka_2020"])
def test_yearly_scenarios_simulate_break_in_that_year(sc):
    from app.config import EUDR_CUTOFF
    from app.services.timeseries import detect_changes

    s = demo.simulate_series(sc, "x")
    r = detect_changes(s.dates, s.ndvi, cutoff=EUDR_CUTOFF)
    years = {b.date[:4] for b in r.breaks if b.magnitude <= -0.2}
    assert sc[-4:] in years


def test_indicator_test_script_logic(monkeypatch):
    """Skrip/endpoint uji indikator: lulus bila indikator yang menyala dan keputusan sesuai harapan."""
    from app.scripts import uji_indikator as uji
    from app.services import kawasan

    class K:
        def __init__(self, pct, source, label=None):
            self.pct, self.source, self.label, self.checked, self.warnings = pct, source, label, True, []

        def to_dict(self):
            return {"pct": self.pct, "checked": True, "source": self.source, "parts": [], "unknown_pct": 0.0,
                    "label": self.label, "fungsi": "HP" if self.pct else None, "name": None, "source_label": "uji"}

    real = {"tree_cover_2020": 100.0, "commodity_2020": None, "disturbance_before_2021": 0.0,
            "disturbance_after_2020": 100.0, "loss_after_by_year": {"2025": 100.0}, "loss_after_main_year": "2025"}
    monkeypatch.setattr(uji.peta_gfw, "plot_layers", lambda g, p: (dict(real), None))
    monkeypatch.setattr(kawasan, "lookup", lambda g, p: K(0.0, "klhk_gfw" if p == "gfw" else "kemenhut"))
    r = uji.evaluate_case("deforestasi", {}, {1}, "tinggi", "uji")
    assert r["passed"] and r["on"] == [1] and r["risk"] == "tinggi"
    r = uji.evaluate_case("salah harapan", {}, {1}, "rendah", "uji")
    assert not r["passed"]
    monkeypatch.setattr(kawasan, "lookup", lambda g, p: K(100.0, "klhk_gfw" if p == "gfw" else "kemenhut", "Hutan Produksi"))
    r = uji.evaluate_case("kawasan", {}, {1, 2, 3}, "tinggi", "uji")
    assert r["passed"] and r["indicators"]["2"]["pct"] == 100.0
