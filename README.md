# PasporKebun

**Paspor digital kebun sawit rakyat untuk ketertelusuran EUDR.**
Petani menunjuk kebunnya di citra satelit, AI menggambar batas, satelit memeriksa 5+ tahun riwayat lahan, lalu QR paspor
dipakai pengepul setiap membeli TBS sehingga buah dari kawasan hutan tidak bisa menumpang nama petani jujur.

Subtema LOGICODIX 2026: **Local MSME & Creative Economy** (akses pasar ekspor petani swadaya), dengan dampak langsung pada
**Green Environment & Sustainability** (mencegah deforestasi lewat rantai pasok).

---

## Masalah

| Fakta | Sumber |
|---|---|
| EUDR berlaku 30 Desember 2026: minyak sawit harus terbukti tidak berasal dari deforestasi setelah 31 Des 2020, dengan bukti geolokasi kebun | Regulasi (EU) 2023/1115 jo. 2025/2650 |
| Baru ~7% kebun sawit rakyat siap EUDR; STDB baru dimiliki ~3% dari 6,87 juta ha | APKASINDO, Kontan 19 Okt 2026 |
| 7 dari 10 petani belum punya data spasial kebun | INDEF |
| TBS dari Taman Nasional Tesso Nilo tetap mengalir ke pabrik walau kebunnya sudah disegel | Mongabay, 30 Apr 2026 |
| Di titik pengumpulan, TBS banyak kebun tercampur sehingga rantai asal-usul putus | Koltiva, 2025 |

Akar masalahnya: **petani swadaya tidak punya peta kebun yang dipercaya**, dan **pengepul adalah titik buta** tempat TBS ilegal
bercampur dengan TBS legal.

## Solusi: satu paspor, tiga titik

1. **Peta kebun (koperasi/pendamping).** Klik di tengah kebun, AI menggambar draf batas dari citra satelit, petani mengoreksi,
   saksi mengesahkan. Tumpang tindih dengan kebun lain langsung terlihat, dan **status kawasan hutan dicek otomatis** ke peta
   resmi Kementerian Kehutanan (misalnya "50% Hutan Lindung").
2. **Cek satelit otomatis.** Riwayat NDVI Sentinel-2 sejak 2018 dianalisis AI (COLD-lite) dan digabung dengan peta global
   (JRC, Hansen/GLAD, RADD, peta sawit) memakai logika *convergence of evidence* ala Whisp FAO. Hasilnya cap **Aman / Perlu cek /
   Berisiko** dengan bukti dan tingkat keyakinan. Peremajaan sawit (PSR) dibedakan dari deforestasi.
3. **Penjaga titik pengepul.** Pengepul memindai QR dan mencatat berat. Volume yang mustahil untuk luas dan umur kebun itu
   (model kapasitas PPKS) langsung ditahan. Isolation Forest mengurutkan pengepul yang paling layak diaudit.
4. **Dasbor pabrik.** Porsi TBS yang tertelusur, transaksi bermasalah, skor anomali pengepul, dan unduhan GeoJSON format EUDR.

## Menjalankan di laptop (Windows)

Prasyarat: **Python 3.10+** dan **Node.js 18+** (cek: `python --version`, `node --version`).

```bat
setup.bat        :: sekali saja: membuat venv, memasang paket, membangun frontend
start.bat        :: menjalankan aplikasi -> buka http://localhost:8000
```

Mode pengembangan (hot reload): `start-dev.bat` (backend :8000 + frontend :5173).
macOS/Linux: `./setup.sh` lalu `./start.sh`.

Data demo dibuat otomatis saat server pertama kali jalan. Untuk mengulang dari awal: hapus folder `backend/data`, atau
`POST /api/demo/reset`. Dokumentasi API interaktif: http://localhost:8000/docs

### Data nyata vs simulasi

| Bagian | Status |
|---|---|
| Citra satelit di peta dan untuk AI penggambar batas | **Nyata** (Esri World Imagery, butuh internet; tile disimpan di cache) |
| Lapisan kehilangan tutupan pohon 2021–2024 di peta | **Nyata** (Global Forest Watch / Hansen UMD, toggle di kanan atas peta) |
| Time series NDVI & lapisan bukti per kebun | **Simulasi berlabel** di mode demo; **nyata** di mode live (lihat di bawah) |
| Nama petani, desa, transaksi, pengepul, pabrik | **Fiktif** |
| Status kawasan hutan kebun baru | **Nyata** bila peta Kemenhut terjangkau (lihat di bawah); kebun contoh memakai batas **ilustrasi** |

**Mode live (opsional, butuh internet):**
```bat
cd backend
.venv\Scripts\pip install -r requirements-live.txt
.venv\Scripts\python -m app.scripts.check_live
cd ..
set PK_SATELLITE_MODE=live
start.bat
```
Mode live mengambil Sentinel-2 L2A dari Microsoft Planetary Computer (tanpa akun) dan Hansen GFC dari Google Cloud Storage.
Kode ini belum bisa kami uji di lingkungan pengembangan (akses ke server satelit diblokir di sana); jalankan `check_live` dulu.

### Cek kawasan hutan otomatis (peta Kemenhut)

Saat kebun digambar, backend menanyakan poligon kawasan hutan di lokasi itu ke layanan ArcGIS REST
[Kawasan Hutan Kemenhut (SIGAP)](https://geoportal.menlhk.go.id/server/rest/services/SIGAP_Interaktif/Kawasan_Hutan/MapServer),
membaca fungsinya (konservasi, hutan lindung, HPT, HP, HPK, APL), lalu menghitung persentase luas kebun di tiap fungsi. Kebun
yang lebih dari 5% masuk kawasan hutan langsung berstatus Berisiko. Hasil disimpan di `backend/data/kawasan_cache/`, jadi area
yang pernah dicek tetap bisa dipakai saat offline. Peta yang sama bisa ditampilkan di peta aplikasi lewat ikon lapisan
(kanan atas) → "Kawasan hutan (peta Kemenhut)".

Uji dulu di laptop (layanan ini belum bisa kami uji dari lingkungan pengembangan):
```bat
cd backend
.venv\Scripts\python -m app.scripts.check_kawasan
```
Skrip mencetak daftar layer, kolom, contoh poligon di sekitar Tesso Nilo, dan fungsi yang terbaca. Bila ada fungsi yang
terbaca "?", buat `backend/data/kawasan/kode_fungsi.json` sesuai contoh yang dicetak skrip.

| Variabel | Arti |
|---|---|
| `PK_KAWASAN_SOURCE` | `auto` (bawaan: online + cache + GeoJSON lokal), `online`, atau `lokal` (tanpa internet) |
| `PK_KAWASAN_LAYERS` | id layer yang dipakai, mis. `0` (bawaan: dipilih otomatis dari nama layer) |
| `PK_KAWASAN_TIMEOUT` | batas waktu per permintaan, detik (bawaan 10) |

Peta resmi lain (mis. unduhan GeoJSON per provinsi) cukup ditaruh di `backend/data/kawasan/`. Kebun contoh fiktif selalu
dicek ke batas ilustrasi agar alur demo tetap sama. Bila layanan tidak terjangkau, paspor menulis "belum bisa dicek" (mode
live: status menjadi Perlu cek), bukan "aman".

**Segment Anything (opsional):** `pip install -r backend/requirements-sam.txt`, unduh `sam_vit_b_01ec64.pth` ke
`backend/models/`. Tanpa itu, AI memakai watershed berpenanda (OpenCV) yang lebih ringan.

## Arsitektur

```
frontend/ (React + TypeScript + Vite, Leaflet)          backend/ (FastAPI + SQLite)
  Beranda | Peta kebun | Pengepul | Pabrik | Cara kerja AI
        │  fetch /api/*                                   routers/  plots · ai · supply · dashboard · meta
        └──────────────────────────────────────────────►  services/
                                                            delineation.py   AI batas kebun (SAM | watershed)
                                                            tiles.py         unduh + cache citra
                                                            timeseries.py    COLD-lite, tahun tanam
                                                            evidence.py      convergence of evidence (Whisp)
                                                            kawasan.py       status kawasan hutan (peta Kemenhut + cache)
                                                            satellite/       demo.py (simulasi) | live.py (S2 + Hansen)
                                                            yield_model.py   kapasitas produksi (PPKS)
                                                            supply_guard.py  cek transaksi + Isolation Forest
                                                          tests/ (pytest, 34 tes)  scripts/ validate · check_live · check_kawasan
```

## Komponen AI dan akurasinya

| Komponen | Algoritma | Akurasi (literatur) | Validasi kami (data simulasi) |
|---|---|---|---|
| Penggambar batas kebun | Watershed berpenanda; opsional SAM | SAM zero-shot lahan petani kecil: IoU 0,71, F1 0,82 | IoU 0,93 (citra sintetis) |
| Deteksi pembukaan lahan 2018–kini | COLD-lite (regresi harmonik robust + konfirmasi 5 citra) | COLD F1 81,8% > CCDC ~76,5% > BFAST 70,6% | F1 100%; uji ketahanan F1 99% |
| Estimasi tahun tanam | Lahan terbuka terakhir setelah pembukaan (Descals 2024) | RMSE 2,65 th (petani kecil 4,89 th) | ±1 th: 98% |
| Keputusan risiko EUDR | Convergence of evidence (Whisp FAO) + pembeda peremajaan | JRC GFC2020 OA 91%; RADD UA 97,6% | 100% per skenario |
| Status kawasan hutan | Irisan poligon kebun × peta Kawasan Hutan Kemenhut (shapely) | Mengikuti ketelitian peta resmi (skala kecil) | Server peta tiruan: 50% HL terbaca tepat |
| Anomali pengepul | Isolation Forest + z-score robust | – | Pencuci TBS di peringkat atas |

Rincian: [docs/ALGORITMA.md](docs/ALGORITMA.md) dan [docs/VALIDASI.md](docs/VALIDASI.md) (dihasilkan `python -m app.scripts.validate`).

## Pemetaan ke rubrik penilaian

| Kriteria (bobot) | Bukti di aplikasi |
|---|---|
| Problem-Solution Fit (25%) | Beranda memuat data masalah; tiga peran nyata (koperasi, pengepul, pabrik); tenggat EUDR dihitung mundur di dasbor; pembeda peremajaan agar petani PSR tidak dirugikan; status kawasan hutan dicek otomatis ke peta resmi Kemenhut (aspek legalitas EUDR) |
| Inovasi & AI (25%) | 4 komponen AI yang masing-masing mengubah keputusan; pilihan algoritma berdasarkan studi pembanding; time series 5+ tahun; deteksi pencucian TBS di pengepul (celah yang belum ditutup solusi lain) |
| Software Engineering (25%) | Arsitektur berlapis (router/service/algoritma), tipe ketat (Pydantic + TypeScript strict), 34 tes otomatis (termasuk server peta tiruan), skrip validasi, dokumentasi API otomatis, setup satu perintah |
| UI/UX (15%) | Satu alur per peran; draf AI yang bisa diedit; cap status yang langsung terbaca; tampilan pengepul ramah ponsel; pesan galat memberi arah |
| Green IT & Ethics (10%) | Semua AI di CPU; hanya piksel dalam kebun yang diolah; cache citra; GZip; tanpa NIK/KTP; QR tanpa data pribadi; persetujuan eksplisit; halaman "Cara kerja AI" berisi akurasi, batasan, dan peran manusia |

## Pengujian

```bat
cd backend
.venv\Scripts\python -m pytest -q          :: 34 tes
.venv\Scripts\python -m app.scripts.validate   :: menulis docs/VALIDASI.md
```

## Atribusi data

Citra: Esri, Maxar, Earthstar Geographics. Kawasan hutan: Kementerian Kehutanan (Direktorat Pengukuhan dan Penatagunaan
Kawasan Hutan), layanan SIGAP. Kehilangan tutupan pohon: Hansen/UMD/Google/USGS/NASA via Global Forest Watch.
Sentinel-2: Copernicus/ESA via Microsoft Planetary Computer. Logika keputusan diadaptasi dari Whisp (FAO, lisensi MIT).
