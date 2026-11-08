# Riset algoritma dan alasan pemilihan

Dokumen ini merangkum bagaimana lembaga dan startup di luar negeri membangun sistem serupa, seberapa akurat, dan
algoritma mana yang kami pilih untuk PasporKebun.

## 1. Siapa yang sudah mengerjakan masalah serupa

| Pemain | Pendekatan | Pelajaran untuk kami |
|---|---|---|
| **Whisp** (FAO / Forest Data Partnership) | Tidak ada satu peta yang selalu benar; risiko plot diputuskan dari kesepakatan banyak peta global (tutupan pohon 2020, komoditas 2020, gangguan sebelum/sesudah 2020). Open source, berbasis Google Earth Engine | Kami mengadopsi aturan keputusannya (ambang 10% / 50%) |
| **Global Forest Watch / GLAD** (UMD) | Peta kehilangan tutupan pohon tahunan dari Landsat 30 m | Dipakai sebagai bukti "gangguan sebelum/sesudah 2020" dan lapisan peta |
| **RADD** (Wageningen University) | Peringatan deforestasi dari radar Sentinel-1 (tembus awan). User's accuracy 97,6%, producer's 95,0% untuk kejadian ≥ 0,2 ha; terdeteksi 6–12 hari setelah kejadian | Penting untuk Indonesia yang sering berawan; dicantumkan sebagai sumber bukti |
| **JRC Global Forest Cover 2020** | Peta acuan hutan 2020 untuk EUDR. Akurasi keseluruhan 91% (komisi 18%, omisi 8%) | Bukti "tutupan pohon 31 Des 2020" |
| **Descals et al.** (peta sawit global) | DeepLabv3+ pada Sentinel-1 + Sentinel-2. User's accuracy sawit rakyat 76,6%, producer's 86,9% | Bukti "sudah kebun sawit 2020"; menunjukkan peta global kurang tajam untuk kebun kecil |
| **Satelligence** (Belanda), **Koltiva** (Indonesia/Swiss) | Pemetaan poligon oleh petugas lapangan + pemantauan satelit + laporan risiko untuk koperasi | Pemetaan sudah ada; celah yang belum tertutup ada di titik pengumpulan (pengepul) |

## 2. Deteksi perubahan lahan dari time series

Studi pembanding 6 algoritma pada 12.328 sampel referensi (Remote Sensing 17:680, 2025):

| Algoritma | Skala | F1 |
|---|---|---|
| VCT | tahunan | 52,8% |
| LandTrendr | tahunan | ~55,4% |
| mLandTrendr | tahunan | 73,0% |
| BFAST | harian | 70,6% |
| CCDC | harian | ~76,5% |
| **COLD** | harian | **81,8%** |

Algoritma berbasis semua observasi (harian) mengungguli komposit tahunan karena menangkap gangguan singkat. COLD unggul
berkat inisialisasi model yang lebih baik, pembuangan outlier, dan kriteria perubahan berbasis probabilitas.

**Pilihan kami: COLD-lite.** Model harmonik (tren + 2 harmonik musiman) dicocokkan dengan regresi robust (IRLS, bobot
Tukey); perubahan dikonfirmasi bila 5 citra berturut-turut menyimpang > 3 RMSE ke arah yang sama; besarnya perubahan
diukur terhadap tingkat NDVI terakhir yang normal agar pertumbuhan sawit muda yang melambat tidak terbaca sebagai
pembukaan lahan. Implementasi hanya numpy, ~25 ms per kebun di CPU.

**Tahun tanam** mengikuti Descals et al. (2024, ESSD 16:5111): tanggal lahan terbuka terakhir setelah pembukaan. Literatur
melaporkan RMSE 2,65 tahun (perkebunan 2,02; petani kecil 4,89), jadi aplikasi menampilkan selisih ≥ 4 tahun antara
pengakuan petani dan perkiraan satelit sebagai hal yang perlu dikonfirmasi, bukan sebagai pelanggaran.

## 3. Penggambar batas kebun

| Pendekatan | Akurasi | Catatan |
|---|---|---|
| SAM zero-shot (Meta AI), lahan petani kecil Bihar, citra 2 m | Deteksi 58% lahan; IoU rata-rata 0,71 dan F1 0,82 pada lahan terdeteksi | Multi-tanggal paling meningkatkan deteksi |
| Delineate Anything (2025), dilatih pada FBIS-22M (22,9 juta poligon lahan) | mAP@0,5 naik 88,5% dibanding metode sebelumnya | Kode & bobot terbuka; lebih berat |
| Watershed berpenanda (klasik) | IoU 0,93 pada citra sintetis kami | Ringan, tanpa unduhan model |

Dengan prompt klik dari petani, masalah *deteksi* hilang; tinggal *deliniasi*. Karena itu kami memakai watershed berpenanda
sebagai mesin bawaan (CPU, ~1 detik, tanpa model 375 MB) dan SAM sebagai opsi. Semua hasil adalah draf yang wajib dikoreksi
dan disaksikan.

## 4. Penjaga titik pengepul

- **Model kapasitas:** kurva potensi produksi PPKS menurut umur tanaman × luas × faktor musim, dilonggarkan 15% di atas
  praktik terbaik. Rata-rata petani swadaya 12–18 t/ha/th; kebun mitra terbaik ~20 t/ha/th.
- **Aturan:** melebihi kapasitas 30 hari, tanaman belum masa panen, rotasi panen < 7 hari, satu paspor dipakai beberapa
  pengepul dalam 3 hari, kebun berstatus berisiko.
- **Isolation Forest** (Liu et al. 2008) atas 5 fitur perilaku 90 hari per pengepul. Dipilih karena tidak butuh label
  kecurangan (memang belum ada datanya), ringan, dan bisa dijelaskan dengan z-score per fitur.

## Sumber

- Whisp: https://pypi.org/project/openforis-whisp/
- RADD: Reiche et al. 2021, Environ. Res. Lett. https://iopscience.iop.org/article/10.1088/1748-9326/abd0a8
- JRC GFC2020 accuracy: https://publications.jrc.ec.europa.eu/repository/handle/JRC141231
- Peta sawit global: Descals et al. 2021, ESSD 13:1211 https://essd.copernicus.org/articles/13/1211/2021/
- Tahun tanam sawit: Descals et al. 2024, ESSD 16:5111 https://essd.copernicus.org/articles/16/5111/2024/
- Pembanding algoritma perubahan: Remote Sensing 17:680 (2025)
- SAM untuk lahan petani kecil: https://arxiv.org/abs/2407.01846
- Delineate Anything: https://arxiv.org/abs/2504.02534
- Satelligence × Fairtrade: https://the-european.eu/story-50128/
- Koltiva × REA Kaltim: https://www.agtechnavigator.com/Article/2025/08/11/tackling-barriers-to-eudr-compliance-for-indonesian-smallholders
