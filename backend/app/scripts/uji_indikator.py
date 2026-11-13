"""Uji tiga indikator peta dengan kebun yang SENGAJA melanggarnya, memakai data ONLINE terbaru.

    cd backend
    .venv\\Scripts\\python -m app.scripts.uji_indikator

Indikator yang diuji (sama dengan lapisan di Peta Kebun):
  1. Kehilangan tutupan pohon 2021-2025 (Hansen/GFW), dibaca bersama peta hutan JRC 2020
  2. Kawasan hutan KLHK 2017 (Global Forest Watch)
  3. Kawasan hutan peta Kemenhut terbaru (dibaca dari gambar peta resmi)

Setiap kebun uji punya harapan: indikator mana yang harus menyala dan apa keputusan akhirnya.
Lokasinya dipilih dari data nyata (13 Nov 2026), jadi bila suatu saat GAGAL, artinya salah satu
dari tiga hal: layanan peta berubah/terputus, data diperbarui, atau logika aplikasi rusak.
"""
from __future__ import annotations

import sys
import time

from ..services import evidence, kawasan
from ..services.satellite import peta_gfw


def _sq(lng: float, lat: float, d: float = 0.0006) -> dict:
    return {"type": "Polygon", "coordinates": [[[lng - d, lat - d], [lng + d, lat - d], [lng + d, lat + d],
                                                [lng - d, lat + d], [lng - d, lat - d]]]}


def _ring(pts: list[list[float]]) -> dict:
    return {"type": "Polygon", "coordinates": [pts]}


# nama, poligon, indikator yang harus menyala (1/2/3), keputusan yang diharapkan, alasan
CASES = [
    ("Joko Susilo (hutan dibuka 2025)",
     _ring([[102.098848, -0.433101], [102.097237, -0.433125], [102.09721, -0.431942], [102.098776, -0.431877],
            [102.098848, -0.433101]]),
     {1}, "tinggi", "hutan JRC 2020 lalu hilang 2025, di APL: melanggar syarat bebas deforestasi"),
    ("Sutrisno Wibowo (peremajaan 2023)",
     _ring([[102.09285, -0.357735], [102.09124, -0.357696], [102.091259, -0.356156], [102.092876, -0.35623],
            [102.09285, -0.357735]]),
     {1}, "rendah", "tutupan hilang 2023, tetapi bukan hutan pada 2020: peremajaan, bukan deforestasi"),
    ("Rina Wati (di Hutan Produksi)",
     _ring([[102.055021, -0.368102], [102.053734, -0.368085], [102.05366, -0.367036], [102.055018, -0.367051],
            [102.055021, -0.368102]]),
     {2, 3}, "tinggi", "di dalam kawasan hutan menurut peta 2017 dan peta terbaru: masalah legalitas"),
    ("Kebun uji di TN Tesso Nilo", _sq(102.04, -0.305), {2, 3}, "tinggi",
     "di dalam kawasan konservasi menurut kedua peta"),
    ("Budi Santoso (kebun aman)",
     _ring([[102.066238, -0.36593], [102.064746, -0.365962], [102.064842, -0.364847], [102.06624, -0.364823],
            [102.066238, -0.36593]]),
     set(), "rendah", "APL, bukan hutan 2020, tanpa kehilangan tutupan"),
]


def evaluate_case(name: str, geom: dict, expect_on: set[int], expect_risk: str, why: str) -> dict:
    """Satu kebun uji -> hasil tiap indikator, keputusan, dan LULUS/GAGAL (juga dipakai endpoint API)."""
    t0 = time.perf_counter()
    res: dict = {"name": name, "why": why, "expect_on": sorted(expect_on), "expect_risk": expect_risk,
                 "indicators": {}, "errors": []}
    layers, err = peta_gfw.plot_layers(geom, "online")
    k17 = kawasan.lookup(geom, "gfw")
    k26 = kawasan.lookup(geom, "online")
    on: set[int] = set()
    if layers is None:
        res["errors"].append(f"[1] tile GFW tidak terbaca: {err}")
    else:
        after, tree = layers["disturbance_after_2020"], layers["tree_cover_2020"]
        if after >= evidence.T_DIST_AFTER:
            on.add(1)
        res["indicators"]["1"] = {"on": 1 in on, "loss_after_pct": after, "by_year": layers["loss_after_by_year"],
                                  "forest_2020_pct": tree}
    if not k17.checked or k17.source != "klhk_gfw":
        res["errors"].append("[2] peta KLHK 2017 tidak terbaca: " + "; ".join(k17.warnings)[:160])
    else:
        if k17.pct > evidence.T_PROTECTED:
            on.add(2)
        res["indicators"]["2"] = {"on": 2 in on, "pct": k17.pct, "label": k17.label or "APL / di luar kawasan"}
    if not k26.checked or k26.source != "kemenhut":
        res["errors"].append("[3] peta Kemenhut tidak terbaca: " + "; ".join(k26.warnings)[:160])
    else:
        if k26.pct > evidence.T_PROTECTED:
            on.add(3)
        res["indicators"]["3"] = {"on": 3 in on, "pct": k26.pct, "label": k26.label or "APL / di luar kawasan"}
    if layers is not None:
        kw = (k26 if k26.checked else k17).to_dict()
        d = evidence.decide({k: v for k, v in layers.items() if not k.startswith("_")}, None, kw["pct"], kawasan=kw,
                            forest_map="jrc", layer_sources=peta_gfw.LAYER_SOURCES)
        res.update(risk=d.risk_level, headline=d.headline)
    res["on"] = sorted(on)
    res["passed"] = not res["errors"] and on == expect_on and res.get("risk") == expect_risk
    res["seconds"] = round(time.perf_counter() - t0, 1)
    return res


def evaluate() -> list[dict]:
    return [evaluate_case(*c) for c in CASES]


def run() -> int:
    print("Uji indikator peta PasporKebun (data online)\n")
    results = evaluate()
    for r in results:
        print(f"- {r['name']}\n  harapan: indikator {r['expect_on'] or 'tidak ada'} menyala, keputusan {r['expect_risk']} "
              f"({r['why']})")
        i = r["indicators"]
        if "1" in i:
            print(f"  [1] kehilangan tutupan 2021-2025: {i['1']['loss_after_pct']:.0f}% {i['1']['by_year'] or ''} | "
                  f"hutan JRC 2020: {i['1']['forest_2020_pct']:.0f}%")
        if "2" in i:
            print(f"  [2] KLHK 2017: {i['2']['pct']:.0f}% kawasan ({i['2']['label']})")
        if "3" in i:
            print(f"  [3] Kemenhut terbaru: {i['3']['pct']:.0f}% kawasan ({i['3']['label']})")
        for e in r["errors"]:
            print(f"  GAGAL {e}")
        if "risk" in r:
            print(f"  hasil: indikator {r['on'] or 'tidak ada'} menyala, keputusan {r['risk']} - {r['headline']}")
        print(f"  {'LULUS' if r['passed'] else 'GAGAL'} ({r['seconds']} dtk)\n")
    fails = sum(not r["passed"] for r in results)
    print("Semua kebun uji lulus." if not fails else f"{fails} kebun uji gagal. Baca keterangan di atas.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(run())
