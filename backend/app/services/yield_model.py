"""Model kapasitas produksi TBS per kebun.

Kurva produktivitas mengikuti standar potensi PPKS (Pusat Penelitian Kelapa Sawit)
untuk kelas lahan S2 (ton TBS/ha/tahun menurut umur tanaman). Rata-rata nasional
petani swadaya ~12-18 t/ha/th; kebun mitra terbaik ~20 t/ha/th (PalmCo 2026).

Batas atas kapasitas sengaja dibuat longgar (praktik terbaik x 1,15 x puncak musim)
agar petani jujur yang panennya bagus tidak ikut dicurigai. Prinsipnya:
lebih baik melewatkan sedikit kecurangan daripada menuduh petani jujur.
"""
from __future__ import annotations

from datetime import date

# umur (tahun setelah tanam) -> ton TBS/ha/tahun, potensi kebun dikelola baik
_PPKS_CURVE = {
    3: 7.0, 4: 13.0, 5: 17.0, 6: 20.0, 7: 23.0, 8: 25.0, 9: 26.5, 10: 27.0, 11: 27.0,
    12: 27.0, 13: 26.5, 14: 26.0, 15: 25.5, 16: 25.0, 17: 24.0, 18: 23.0, 19: 22.0,
    20: 21.0, 21: 20.0, 22: 19.0, 23: 18.0, 24: 17.0, 25: 16.0,
}
TYPICAL_SMALLHOLDER_FACTOR = 0.65  # petani swadaya ~65% potensi
UPPER_FACTOR = 1.15
UNKNOWN_AGE_POTENTIAL = 27.0  # umur tidak diketahui -> asumsi paling longgar

# Pola musiman panen sawit di Sumatra (puncak Sep-Nov, rendah Feb-Apr), rerata = 1
SEASONAL = {1: 0.92, 2: 0.82, 3: 0.82, 4: 0.88, 5: 0.95, 6: 0.98, 7: 1.02, 8: 1.08, 9: 1.15, 10: 1.18, 11: 1.14, 12: 1.06}


def potential_t_per_ha_year(age: int | None) -> float:
    if age is None:
        return UNKNOWN_AGE_POTENTIAL
    if age < 3:
        return 0.0
    return _PPKS_CURVE.get(age, 16.0 if age > 25 else 7.0)


def age_of(planting_year: int | None, today: date | None = None) -> int | None:
    if planting_year is None:
        return None
    return (today or date.today()).year - planting_year


def monthly_capacity_kg(area_ha: float, planting_year: int | None, month: int, today: date | None = None) -> dict:
    age = age_of(planting_year, today)
    pot = potential_t_per_ha_year(age)
    seas = SEASONAL.get(month, 1.0)
    typical = area_ha * pot * TYPICAL_SMALLHOLDER_FACTOR / 12 * seas * 1000
    upper = area_ha * pot * UPPER_FACTOR / 12 * seas * 1000
    return {
        "age": age,
        "potential_t_ha_year": pot,
        "typical_kg_30d": round(typical),
        "upper_kg_30d": round(upper),
        "season_factor": seas,
    }
