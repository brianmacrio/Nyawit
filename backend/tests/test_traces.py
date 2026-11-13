"""Format geolokasi TRACES: pembulatan 6 desimal dan pemeriksaan sebelum ekspor."""
import pytest

from app.services import geo, traces


def _feat(ring, **props):
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"ProducerCountry": "ID", "Area": 1.5, **props}}


RING = [[102.066238, -0.36593], [102.064746, -0.365962], [102.064842, -0.364847], [102.06624, -0.364823],
        [102.066238, -0.36593]]


def test_valid_feature_passes():
    assert traces.feature_problems(_feat(RING)) == []
    r = traces.validate_collection({"type": "FeatureCollection", "features": [_feat(RING, PlotCode="PK-1")]})
    assert r["ok"] and r["features"] == 1 and r["problems"] == []


def test_truncation_to_6_decimals_cannot_create_duplicate_points():
    """Dua titik yang hanya berbeda di desimal ke-7 menjadi kembar setelah TRACES memotong ke 6 desimal."""
    ring = [[102.0662381, -0.3659301], [102.0662384, -0.3659303], [102.064746, -0.365962], [102.064842, -0.364847],
            [102.0662381, -0.3659301]]
    assert any("6 desimal" in p for p in traces.feature_problems(_feat(ring)))
    clean = traces.to_traces_polygon({"type": "Polygon", "coordinates": [ring]})["coordinates"][0]
    assert len(clean) == 4 and clean[0] == clean[-1]
    assert traces.feature_problems(_feat(clean)) == []
    # yang disimpan aplikasi sudah 6 desimal dan tanpa titik kembar
    stored = geo.validate_polygon({"type": "Polygon", "coordinates": [ring]})["coordinates"][0]
    assert stored == clean or traces.feature_problems(_feat(stored)) == []


@pytest.mark.parametrize("feature, expect", [
    (_feat(RING[:-1]), "tidak tertutup"),
    (_feat(RING[:2] + [RING[0]]), "kurang dari 4"),
    (_feat([[y, x] for x, y in RING]), "di luar wilayah ID"),
    (_feat([[102.0, -0.3], [102.001, -0.299], [102.001, -0.3], [102.0, -0.299], [102.0, -0.3]]), "berpotongan"),
    (_feat(RING, Area="1.5"), "Area harus angka"),
    (_feat(RING, ProducerCountry="Indonesia"), "ISO2"),
    ({"type": "Feature", "geometry": {"type": "LineString", "coordinates": RING}, "properties": {"ProducerCountry": "ID"}},
     "tidak diterima"),
    ({"type": "Feature", "properties": {"ProducerCountry": "ID"},
      "geometry": {"type": "Polygon", "coordinates": [RING, [[102.0652, -0.3655], [102.0655, -0.3655], [102.0655, -0.3652],
                                                             [102.0652, -0.3655]]]}}, "berlubang"),
])
def test_problems_are_reported(feature, expect):
    assert any(expect in p for p in traces.feature_problems(feature)), traces.feature_problems(feature)


def test_degenerate_polygon_is_rejected():
    with pytest.raises(traces.TracesError):
        traces.to_traces_polygon({"type": "Polygon", "coordinates": [[[102.0, -0.3], [102.0000001, -0.3], [102.0, -0.3]]]})
    with pytest.raises(ValueError):
        geo.validate_polygon({"type": "Polygon", "coordinates": [[[102.0, -0.3], [102.001, -0.3], [102.002, -0.3]]]})


def test_upload_collection_keeps_only_known_properties():
    fc = {"type": "FeatureCollection", "features": [_feat(RING, PlotCode="PK-1", ProductionPlace="Sungai Harapan")]}
    up = traces.upload_collection(fc)
    assert up["features"][0]["properties"] == {"ProducerCountry": "ID", "ProductionPlace": "Sungai Harapan", "Area": 1.5}
