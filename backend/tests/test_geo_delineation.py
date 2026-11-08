import numpy as np

from app.services import geo
from app.services.delineation import _clean, _mask_watershed
from app.services.plots import make_code, parse_code
from synthetic_image import make_scene


def test_area_square_hectare():
    # 100 m x 100 m di khatulistiwa = 1 ha
    d = 100 / 111320
    g = {"type": "Polygon", "coordinates": [[[100, 0], [100 + d, 0], [100 + d, d], [100, d], [100, 0]]]}
    assert abs(geo.area_ha(g) - 1.0) < 0.01


def test_overlap_detected():
    a = {"type": "Polygon", "coordinates": [[[0, 0], [0.002, 0], [0.002, 0.002], [0, 0.002], [0, 0]]]}
    b = {"type": "Polygon", "coordinates": [[[0.001, 0], [0.003, 0], [0.003, 0.002], [0.001, 0.002], [0.001, 0]]]}
    ha, inter = geo.overlap(a, b)
    assert ha > 2 and inter is not None


def test_mercator_roundtrip():
    x, y = geo.latlng_to_global_px(-0.17, 101.89, 18)
    lat, lng = geo.global_px_to_latlng(x, y, 18)
    assert abs(lat + 0.17) < 1e-7 and abs(lng - 101.89) < 1e-7


def test_passport_code_checksum():
    code = make_code(12)
    assert parse_code(code) == (12, None)
    assert parse_code(code.lower().replace("-", "")) == (12, None)
    wrong = code[:-1] + ("A" if code[-1] != "A" else "B")
    assert parse_code(wrong)[1] is not None


def test_watershed_delineation_iou():
    img, masks = make_scene(3)
    for key, (x, y) in {"palm_old": (190, 220), "bare": (180, 560)}.items():
        m = _clean(_mask_watershed(img, x, y, 0.6), x, y)
        gt = masks[key]
        iou = (m & gt).sum() / (m | gt).sum()
        assert iou > 0.8, (key, iou)
