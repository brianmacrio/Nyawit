from datetime import date

from app.services.satellite.demo import SCENARIOS, simulate_series
from app.services.timeseries import detect_changes


def _run(sc, key="t"):
    s = simulate_series(sc, key, end=date(2026, 10, 31))
    return detect_changes(s.dates, s.ndvi)


def test_stable_palm_has_no_break():
    r = _run("sawit_tua_stabil")
    assert r.breaks == []
    assert r.n_obs > 100
    assert any(r.is_outlier), "sisa awan harus terdeteksi sebagai outlier, bukan perubahan"


def test_forest_clearing_after_cutoff_detected():
    r = _run("hutan_dibuka_2022")
    big = [b for b in r.breaks if b.magnitude <= -0.2]
    assert big and big[0].after_cutoff
    assert big[0].date.startswith("2022")
    assert r.planting_year in (2022, 2023, 2024)


def test_clearing_before_cutoff_flagged_before():
    r = _run("dibuka_2019")
    big = [b for b in r.breaks if b.magnitude <= -0.2]
    assert big and not big[0].after_cutoff


def test_detection_robust_across_seeds():
    for sc in SCENARIOS:
        for k in range(15):
            r = _run(sc, f"s{k}")
            after = any(b.after_cutoff and b.magnitude <= -0.2 for b in r.breaks)
            assert after == (sc in ("hutan_dibuka_2022", "peremajaan_2023")), (sc, k)


def test_too_few_observations():
    r = detect_changes([date(2020, 1, 1), date(2020, 2, 1)], [0.8, 0.79])
    assert r.breaks == [] and "terlalu sedikit" in r.planting_note
