# Validasi teknis algoritma PasporKebun

Dibuat otomatis oleh `python -m app.scripts.validate` pada 2026-11-08.
Data uji: deret NDVI **simulasi** Sentinel-2 berlabel (6 skenario x 100 deret = 600 deret, awan & derau acak) dan citra sintetis kebun (10 adegan x 4 klik).
Angka ini membuktikan algoritma bekerja sesuai rancangan; akurasi lapangan perlu diukur dengan data referensi nyata.

## 1. Deteksi pembukaan lahan setelah 31 Des 2020 (COLD-lite)

| Metrik | Nilai |
|---|---|
| Presisi | 100.0% |
| Recall | 100.0% |
| F1 | 100.0% |
| Galat tanggal pembukaan (median) | 7 hari |
| Tahun tanam tepat +-1 tahun | 98.0% |
| Waktu komputasi per kebun (median, CPU) | 24.0 ms |
| **Uji ketahanan** (derau 2,5x, sisa awan +, 50% citra hilang): presisi / recall / F1 | 98.5% / 99.5% / 99.0% |

Pembanding literatur (data Landsat nyata, Tiongkok, 2025): COLD F1 81,8%, CCDC ~76,5%, BFAST 70,6%.

## 2. Keputusan risiko EUDR (convergence of evidence)

| Skenario | Label benar | Akurasi |
|---|---|---|
| Sawit menghasilkan, stabil sejak sebelum 2018 | rendah | 100% |
| Dibuka 2019 (sebelum batas EUDR), ditanam sawit | rendah | 100% |
| Peremajaan sawit tua (PSR) tahun 2023 | rendah | 100% |
| Hutan dibuka 2022 lalu ditanami sawit | tinggi | 100% |
| Sawit di dalam kawasan hutan (dibuka 2014) | tinggi | 100% |
| Tutupan pohon, data sawit & citra minim (berawan) | perlu_cek | 100% |

## 3. AI penggambar batas kebun (watershed berpenanda)

| Metrik | Nilai |
|---|---|
| IoU rata-rata | 0.928 |
| IoU minimum | 0.584 |
| Waktu per klik (median, CPU) | 1080 ms |

Pembanding literatur: SAM zero-shot pada lahan petani kecil (citra 2 m, India) IoU rata-rata 0,71.
Citra sintetis lebih bersih dari citra nyata, jadi angka di atas adalah batas atas.
