"""Validasi algoritma pada data simulasi berlabel. Hasil ditulis ke docs/VALIDASI.md.

    python -m app.scripts.validate

PENTING: ini validasi teknis pada data SIMULASI (label diketahui pasti). Akurasi di
lapangan harus diukur ulang dengan titik referensi nyata (foto geotag / citra resolusi
tinggi), seperti dilakukan JRC, WUR (RADD), dan GLAD.
"""
from __future__ import annotations

import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

from ..services.delineation import _clean, _mask_watershed
from ..services.evidence import decide
from ..services.satellite.demo import SCENARIOS, simulate_layers, simulate_series
from ..services.timeseries import detect_changes

TRUTH_CLEAR = {"hutan_dibuka_2022": date(2022, 6, 14), "peremajaan_2023": date(2023, 3, 6), "dibuka_2019": date(2019, 4, 10)}
TRUTH_PLANT = {"hutan_dibuka_2022": 2022, "peremajaan_2023": 2023, "dibuka_2019": 2019}
TRUTH_RISK = {"sawit_tua_stabil": "rendah", "dibuka_2019": "rendah", "peremajaan_2023": "rendah",
              "hutan_dibuka_2022": "tinggi", "kawasan_hutan": "tinggi", "data_kurang": "perlu_cek"}


def main(n: int = 100) -> str:
    tp = fp = fn = tn = 0
    date_err, plant_err, ms = [], [], []
    risk_ok = defaultdict(int)
    for sc in SCENARIOS:
        for k in range(n):
            s = simulate_series(sc, f"v{k}", end=date(2026, 10, 31))
            t0 = time.perf_counter()
            r = detect_changes(s.dates, s.ndvi)
            ms.append((time.perf_counter() - t0) * 1000)
            pred = any(b.after_cutoff and b.magnitude <= -0.2 for b in r.breaks)
            truth = sc in ("hutan_dibuka_2022", "peremajaan_2023")
            tp += pred and truth
            fp += pred and not truth
            fn += truth and not pred
            tn += (not pred) and (not truth)
            if sc in TRUTH_CLEAR:
                big = [b for b in r.breaks if b.magnitude <= -0.2]
                if big:
                    date_err.append(abs((date.fromisoformat(big[0].date) - TRUTH_CLEAR[sc]).days))
                if r.planting_year:
                    plant_err.append(abs(r.planting_year - TRUTH_PLANT[sc]))
            d = decide(simulate_layers(sc, f"v{k}"), r, 100.0 if sc == "kawasan_hutan" else 0.0)
            risk_ok[sc] += d.risk_level == TRUTH_RISK[sc]

    # uji ketahanan: derau 2,5x lipat, sisa awan lebih banyak, 50% citra hilang
    rng = np.random.default_rng(7)
    stp = stfp = stfn = 0
    for sc in SCENARIOS:
        for k in range(n):
            s = simulate_series(sc, f"st{k}", end=date(2026, 10, 31))
            keep = rng.random(len(s.ndvi)) > 0.5
            d = [x for x, kk in zip(s.dates, keep) if kk]
            v = np.array([x for x, kk in zip(s.ndvi, keep) if kk]) + rng.normal(0, 0.035, keep.sum())
            cloud = rng.random(len(v)) < 0.08
            v[cloud] -= rng.uniform(0.15, 0.45, cloud.sum())
            r = detect_changes(d, list(v))
            pred = any(b.after_cutoff and b.magnitude <= -0.2 for b in r.breaks)
            truth = sc in ("hutan_dibuka_2022", "peremajaan_2023")
            stp += pred and truth
            stfp += pred and not truth
            stfn += truth and not pred
    sprec, srec = stp / max(stp + stfp, 1), stp / max(stp + stfn, 1)
    sf1 = 2 * sprec * srec / max(sprec + srec, 1e-9)

    ious, dms = [], []
    clicks = {"palm_old": (190, 220), "palm_young": (520, 180), "palm_old2": (530, 520), "bare": (180, 560)}
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))
    from synthetic_image import make_scene

    for seed in range(10):
        img, masks = make_scene(seed)
        for key, (x, y) in clicks.items():
            t0 = time.perf_counter()
            m = _clean(_mask_watershed(img, x, y, 0.6), x, y)
            dms.append((time.perf_counter() - t0) * 1000)
            ious.append((m & masks[key]).sum() / (m | masks[key]).sum())

    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-9)
    lines = [
        "# Validasi teknis algoritma PasporKebun",
        "",
        f"Dibuat otomatis oleh `python -m app.scripts.validate` pada {date.today().isoformat()}.",
        "Data uji: deret NDVI **simulasi** Sentinel-2 berlabel (6 skenario x "
        f"{n} deret = {6 * n} deret, awan & derau acak) dan citra sintetis kebun (10 adegan x 4 klik).",
        "Angka ini membuktikan algoritma bekerja sesuai rancangan; akurasi lapangan perlu diukur dengan data referensi nyata.",
        "",
        "## 1. Deteksi pembukaan lahan setelah 31 Des 2020 (COLD-lite)",
        "",
        "| Metrik | Nilai |",
        "|---|---|",
        f"| Presisi | {prec:.1%} |",
        f"| Recall | {rec:.1%} |",
        f"| F1 | {f1:.1%} |",
        f"| Galat tanggal pembukaan (median) | {np.median(date_err):.0f} hari |",
        f"| Tahun tanam tepat +-1 tahun | {np.mean(np.array(plant_err) <= 1):.1%} |",
        f"| Waktu komputasi per kebun (median, CPU) | {np.median(ms):.1f} ms |",
        f"| **Uji ketahanan** (derau 2,5x, sisa awan +, 50% citra hilang): presisi / recall / F1 | {sprec:.1%} / {srec:.1%} / {sf1:.1%} |",
        "",
        "Pembanding literatur (data Landsat nyata, Tiongkok, 2025): COLD F1 81,8%, CCDC ~76,5%, BFAST 70,6%.",
        "",
        "## 2. Keputusan risiko EUDR (convergence of evidence)",
        "",
        "| Skenario | Label benar | Akurasi |",
        "|---|---|---|",
    ]
    for sc in SCENARIOS:
        lines.append(f"| {SCENARIOS[sc]['label']} | {TRUTH_RISK[sc]} | {risk_ok[sc] / n:.0%} |")
    lines += [
        "",
        "## 3. AI penggambar batas kebun (watershed berpenanda)",
        "",
        "| Metrik | Nilai |",
        "|---|---|",
        f"| IoU rata-rata | {np.mean(ious):.3f} |",
        f"| IoU minimum | {np.min(ious):.3f} |",
        f"| Waktu per klik (median, CPU) | {np.median(dms):.0f} ms |",
        "",
        "Pembanding literatur: SAM zero-shot pada lahan petani kecil (citra 2 m, India) IoU rata-rata 0,71.",
        "Citra sintetis lebih bersih dari citra nyata, jadi angka di atas adalah batas atas.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    md = main(int(sys.argv[1]) if len(sys.argv) > 1 else 100)
    out = Path(__file__).resolve().parents[3] / "docs" / "VALIDASI.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(md)
