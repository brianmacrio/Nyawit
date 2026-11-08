"""Penyedia data satelit SIMULASI untuk mode demo.

Menghasilkan deret NDVI ala Sentinel-2 (revisit 5 hari, awan tropis, derau sensor)
dan persentase lapisan bukti (tutupan pohon 2020, sawit 2020, gangguan sebelum/sesudah
2020, kawasan hutan) per skenario. Semua keluaran diberi label `simulasi` di UI agar
juri/pengguna tahu mana data nyata dan mana data rekaan.

Bentuk kurva mengikuti literatur: NDVI hutan tropis ~0,85; sawit menghasilkan ~0,75-0,8;
lahan terbuka ~0,2-0,3; sawit muda menutup tajuk dalam ~5-6 tahun.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from ...config import TS_START
from ..timeseries import frac_year

SCENARIOS: dict[str, dict] = {
    "sawit_tua_stabil": {
        "label": "Sawit menghasilkan, stabil sejak sebelum 2018",
        "layers": {"tree_cover_2020": 62, "commodity_2020": 91, "disturbance_before_2021": 4, "disturbance_after_2020": 0},
    },
    "dibuka_2019": {
        "label": "Dibuka 2019 (sebelum batas EUDR), ditanam sawit",
        "layers": {"tree_cover_2020": 18, "commodity_2020": 58, "disturbance_before_2021": 86, "disturbance_after_2020": 0},
    },
    "peremajaan_2023": {
        "label": "Peremajaan sawit tua (PSR) tahun 2023",
        "layers": {"tree_cover_2020": 71, "commodity_2020": 94, "disturbance_before_2021": 0, "disturbance_after_2020": 83},
    },
    "hutan_dibuka_2022": {
        "label": "Hutan dibuka 2022 lalu ditanami sawit",
        "layers": {"tree_cover_2020": 96, "commodity_2020": 2, "disturbance_before_2021": 0, "disturbance_after_2020": 89},
    },
    "kawasan_hutan": {
        "label": "Sawit di dalam kawasan hutan (dibuka 2014)",
        "layers": {"tree_cover_2020": 66, "commodity_2020": 84, "disturbance_before_2021": 61, "disturbance_after_2020": 0},
    },
    "data_kurang": {
        "label": "Tutupan pohon, data sawit & citra minim (berawan)",
        "layers": {"tree_cover_2020": 81, "commodity_2020": 12, "disturbance_before_2021": 0, "disturbance_after_2020": 0},
    },
}

FOREST, PALM, BARE = 0.86, 0.785, 0.24


def _palm_growth(years_since_plant: float) -> float:
    """NDVI sawit muda: tanah + tanaman penutup -> tajuk menutup ~5-6 tahun."""
    return 0.34 + (PALM - 0.34) * (1 - math.exp(-max(years_since_plant, 0) / 1.9))


def _base_ndvi(scenario: str, d: date) -> float:
    t = frac_year(d)
    seas = 0.018 * math.sin(2 * math.pi * (t - 0.15))
    if scenario in ("sawit_tua_stabil", "kawasan_hutan"):
        return PALM + seas
    if scenario == "data_kurang":
        return 0.83 + seas
    if scenario == "dibuka_2019":
        clear, plant = frac_year(date(2019, 4, 10)), frac_year(date(2019, 9, 1))
        if t < clear:
            return FOREST + seas
        if t < plant:
            return BARE
        return _palm_growth(t - plant) + seas
    if scenario == "hutan_dibuka_2022":
        clear, plant = frac_year(date(2022, 6, 14)), frac_year(date(2022, 11, 20))
        if t < clear:
            return FOREST + seas
        if t < plant:
            return BARE
        return _palm_growth(t - plant) + seas
    if scenario == "peremajaan_2023":
        clear, plant = frac_year(date(2023, 3, 6)), frac_year(date(2023, 7, 15))
        if t < clear:
            return 0.73 + seas  # sawit tua (>25 th), tajuk mulai jarang
        if t < plant:
            return BARE + 0.03
        return _palm_growth(t - plant) + seas
    return PALM + seas


@dataclass
class SimulatedSeries:
    dates: list[date]
    ndvi: list[float]
    source: str = "Simulasi Sentinel-2 L2A (NDVI, revisit 5 hari, masker awan SCL)"


def _rng(key: str) -> np.random.Generator:
    seed = int(hashlib.sha256(key.encode()).hexdigest()[:12], 16)
    return np.random.default_rng(seed)


def simulate_series(scenario: str, key: str, end: date | None = None) -> SimulatedSeries:
    rng = _rng(f"{scenario}:{key}")
    end = end or date.today()
    d = TS_START + timedelta(days=int(rng.integers(0, 5)))
    dates, vals = [], []
    sparse = scenario == "data_kurang"
    while d <= end:
        m = d.month
        p_clear = 0.2 if m in (10, 11, 12, 1) else 0.45 if m in (6, 7, 8) else 0.3
        if sparse:
            p_clear *= 0.35
        if rng.random() < p_clear:
            v = _base_ndvi(scenario, d) + rng.normal(0, 0.022)
            if rng.random() < 0.07:  # sisa awan/bayangan yang lolos masker
                v -= rng.uniform(0.15, 0.45)
            dates.append(d)
            vals.append(float(np.clip(v, -0.1, 0.95)))
        d += timedelta(days=5)
    return SimulatedSeries(dates, vals)


def simulate_layers(scenario: str, key: str) -> dict[str, float]:
    rng = _rng(f"layers:{scenario}:{key}")
    base = SCENARIOS.get(scenario, SCENARIOS["sawit_tua_stabil"])["layers"]
    out = {}
    for k, v in base.items():
        jitter = rng.normal(0, 2.5) if 3 < v < 97 else 0
        out[k] = float(np.clip(round(v + jitter, 1), 0, 100))
    return out
