# PasporKebun

**Paspor digital kebun sawit rakyat: bukti uji tuntas EUDR yang bisa dicek siapa saja, dan penjaga di titik pengepul.**

| | |
|---|---|
| Kategori | **Web** |
| Subtema | Local MSME & Creative Economy (akses pasar ekspor petani swadaya), berdampak pada Green Environment & Sustainability |
| Tim | _[isi nama tim]_ |
| Anggota | _[isi: nama, peran, akun GitHub]_ |
| Aplikasi ter-deploy | _[isi URL setelah deploy, lihat bagian Deploy]_ |
| Video demo | _[isi tautan YouTube]_ |

---

## Masalah

| Fakta | Sumber |
|---|---|
| Mulai 30 Desember 2026 Uni Eropa hanya menerima minyak sawit yang terbukti tidak berasal dari deforestasi setelah 31 Des 2020, lengkap dengan geolokasi kebun asal | Regulasi (UE) 2023/1115 jo. 2025/2650 |
| Baru ~7% kebun sawit rakyat siap EUDR; STDB baru dimiliki sebagian kecil dari 6,8 juta ha kebun rakyat | APKASINDO (Okt 2026); EFI (2023) |
| 7 dari 10 petani belum punya data spasial kebun | INDEF |
| TBS dari kawasan hutan (mis. TN Tesso Nilo) tetap mengalir ke pabrik lewat pengepul | Mongabay, 30 Apr 2026 |
| Mengurus STDB di Kalimantan Tengah sekitar Rp415.000/ha karena pemetaan manual | EFI (2023) |

Akar masalahnya: **petani swadaya tidak punya bukti kebun yang dipercaya**, dan **pengepul adalah titik buta** tempat TBS
ilegal bercampur dengan TBS legal.

## Solusi dan target pengguna

PasporKebun memberi setiap kebun sebuah paspor: geolokasi, bukti lahan, hasil cek satelit dan peta kawasan hutan, serta
hasil verifikasi lapangan. Paspor dipakai di empat titik:

| Pengguna | Yang dilakukan di aplikasi |
|---|---|
| **Petugas koperasi** (pengguna utama) | Memetakan kebun bersama petani dan saksi: GPS "saya di kebun", draf batas AI, ciri batas tiap sisi, bukti lahan, STDB |
| **Pengepul** | Memindai kartu QR petani dan mencatat berat TBS; volume yang mustahil langsung ditahan |
| **Verifikator independen** | Mengunjungi sampel kebun berbasis risiko, mengunggah foto bergeotag, memutuskan keberatan |
| **Pabrik / eksportir** | Melihat porsi TBS tertelusur, pengepul yang perlu diaudit, dan membuat paket data uji tuntas untuk importir |
| **Petani & publik** | Membawa kartu QR (tanpa perlu ponsel); siapa pun bisa mengecek status paspor di `/cek/<kode>` |

Paspor Kebun **bukan sertifikat ISPO/RSPO** (itu hanya boleh diterbitkan lembaga sertifikasi terakreditasi KAN/ASI).
Paspor adalah bukti uji tuntas yang membuat sertifikasi kelompok dan pelaporan EUDR lebih murah.

## Fitur yang berhasil diimplementasikan

1. **Masuk berperan** (koperasi, pengepul, pabrik, verifikator, admin) dengan akun demo satu klik untuk juri.
2. **Pendaftaran kebun**: GPS "Saya sedang di kebun" (rata-rata beberapa bacaan), AI penggambar batas dari citra satelit,
   gambar manual, "Rapikan dengan kebun tetangga" (potong tumpang tindih), "Sudut ini = posisi saya" (GPS di sudut kebun).
3. **Data lapangan**: ciri batas tiap sisi (parit, jalan, kebun tetangga, ...), saksi batas, bukti lahan bertingkat
   (sertifikat / surat desa / pernyataan + 2 saksi), STDB, pernyataan sengketa, persetujuan petani.
4. **Cek otomatis**: tumpang tindih antarkebun, status kawasan hutan dari peta resmi Kemenhut (cadangan otomatis: Peta Kawasan
   Hutan KLHK 2017 lewat Global Forest Watch), riwayat satelit 2018-kini
   (COLD-lite), keputusan multi-bukti, pembeda peremajaan sawit vs deforestasi. Bukti deforestasi dibaca dari peta nyata per
   piksel di dalam batas kebun: dua peta hutan 2020 (JRC acuan UE dan hutan alam SBTN) + kehilangan tutupan pohon 2001–2025 (Hansen, GFW).
5. **Paspor**: status **Siap EUDR** (5 syarat, berlaku 12 bulan), tingkat ketelitian lokasi, bukti satelit + grafik NDVI,
   QR, kartu cetak untuk petani, GeoJSON, tampilan publik dengan nama disamarkan, riwayat perubahan.
6. **Pengepul**: pindai QR dengan kamera atau ketik kode, sisa kapasitas 30 hari, keputusan diterima / catatan / ditahan.
7. **Pabrik**: dasbor ketertelusuran, skor anomali pengepul (Isolation Forest + alasan), penghambat Siap EUDR terbanyak,
   **paket data pengiriman ekspor** (ZIP: GeoJSON bukti, GeoJSON siap unggah TRACES yang sudah lolos pemeriksaan format, CSV,
   README, sidik SHA-256; kebun belum siap dipisahkan).
8. **Verifikasi**: sampel inspeksi berbasis risiko (rumus RSPO), hasil + foto + lokasi (jarak ke kebun dicek),
   keberatan & keputusan tertulis, pemeriksaan integritas riwayat (hash chain).
9. **Cara kerja AI**: akurasi, batasan, peran manusia, dan keamanan dijelaskan di aplikasi, plus **Uji indikator peta**:
   lima kebun uji di lokasi nyata yang sengaja melanggar (atau tidak) tiap indikator, diperiksa ke peta online saat itu juga.

## Arsitektur sistem

```mermaid
flowchart LR
  subgraph Pengguna
    K[Petugas koperasi]
    P[Pengepul]
    V[Verifikator]
    F[Pabrik]
    U[Publik / importir]
  end
  subgraph FE["Frontend: React + TypeScript + Vite + Leaflet"]
    UI[Halaman per peran<br/>peta, paspor, timbang, verifikasi, dasbor]
  end
  subgraph BE["Backend: FastAPI (Python)"]
    SEC[Keamanan<br/>sesi HMAC, peran, CSRF, CSP, batas laju]
    R[Router<br/>auth, kebun, AI, pengepul, verifikasi, pengiriman, dasbor]
    D[AI batas kebun<br/>watershed / SAM]
    T[COLD-lite<br/>riwayat NDVI]
    E[Mesin keputusan multi-bukti<br/>+ cek kawasan hutan]
    G[Penjaga pengepul<br/>kapasitas + Isolation Forest]
    RD[Aturan Siap EUDR<br/>+ sampel verifikasi]
    A[Riwayat berantai hash]
    S[Paket ekspor ZIP]
  end
  DB[(SQLite)]
  X1[Esri World Imagery]
  X2[Peta Kawasan Hutan<br/>Kemenhut SIGAP<br/>cadangan: KLHK 2017 via GFW]
  X3[Sentinel-2 + Hansen GFC<br/>mode live]
  K & P & V & F & U --> UI --> SEC --> R
  R --> D & T & E & G & RD & S
  R --> A
  D -- tile citra --> X1
  E -- query poligon --> X2
  T -- NDVI --> X3
  R & A & S --> DB
```

**Alur data utama**

```mermaid
sequenceDiagram
  participant K as Koperasi
  participant API as Backend
  participant Sat as Satelit & peta
  participant Pg as Pengepul
  participant Vf as Verifikator
  participant Pb as Pabrik
  K->>API: titik GPS / klik peta
  API->>Sat: unduh petak citra
  API-->>K: draf batas AI (dikoreksi + saksi)
  K->>API: simpan kebun + bukti lahan + STDB
  API->>Sat: cek kawasan hutan + riwayat NDVI 2018-kini
  API-->>K: paspor (status satelit + 5 syarat Siap EUDR)
  Pg->>API: pindai QR + berat TBS
  API-->>Pg: diterima / ditahan (model kapasitas)
  Vf->>API: hasil inspeksi sampel + foto, putusan keberatan
  Pb->>API: buat paket pengiriman (periode)
  API-->>Pb: ZIP: hanya kebun Siap EUDR + daftar yang dipisahkan
```

Struktur folder:

```
backend/app/
  main.py, config.py, db.py (migrasi aditif), models.py, schemas.py, security.py, seed.py
  routers/   auth, plots, ai, supply, verification, shipments, dashboard, meta
  services/  delineation, tiles, timeseries (COLD-lite), evidence, kawasan (+ kawasan_raster), kawasan_gfw + mvt, satellite/{demo,live},
             yield_model, supply_guard, readiness (Siap EUDR), verification, shipment, audit, geo
  scripts/   validate, check_live, check_kawasan
backend/tests/   97 tes pytest
frontend/src/
  pages/     Beranda, Masuk, PetaKebun, Pengepul, Pabrik, Verifikasi, Transparansi, CekPaspor, KartuPaspor
  components/ PassportPanel, NdviChart, MapBase, KawasanLayer, GfwKawasanLayer, QrScanner, RoleGate, ui
  lib/       api, auth, gps, format, types
```

## Teknologi

| Bagian | Yang dipakai |
|---|---|
| Frontend | React 18, TypeScript 5 (strict), Vite 6, React Router 6, Leaflet + react-leaflet, Leaflet-Geoman (edit poligon), qrcode, jsQR, lucide-react |
| Backend | Python 3.10+, FastAPI, Uvicorn, SQLAlchemy 2, Pydantic 2, python-dotenv |
| Database | SQLite (WAL), migrasi aditif otomatis |
| AI & geospasial | NumPy, OpenCV (headless), scikit-learn (Isolation Forest), Shapely, Pillow; opsional Segment Anything (PyTorch) |
| API / layanan pihak ketiga | Esri World Imagery (citra), Global Forest Watch tiles (kehilangan tutupan pohon; Peta Kawasan Hutan KLHK 2017 sebagai tile vektor), Geoportal Kemenhut (Kawasan Hutan, ArcGIS REST), Microsoft Planetary Computer (Sentinel-2, mode live), Google Cloud Storage (Hansen GFC, mode live) |
| Pengujian & mutu | pytest (97 tes, termasuk server peta tiruan), Playwright (uji alur di browser saat pengembangan) |
| Deploy | Docker (multi-stage), Render Blueprint (`render.yaml`) |

Tidak ada layanan AI pihak ketiga (API LLM dll.) yang dipanggil aplikasi; semua model berjalan di CPU server sendiri.

## Instalasi dan menjalankan (laptop, Windows)

Prasyarat: **Python 3.10+** dan **Node.js 18+**.

```bat
setup.bat        :: sekali saja: venv Python, paket backend, paket & build frontend
start.bat        :: buka http://localhost:8000
```

Mode pengembangan (hot reload): `start-dev.bat` (backend :8000 + frontend :5173). macOS/Linux: `./setup.sh` lalu `./start.sh`.
Data demo dibuat otomatis saat server pertama kali jalan. Untuk mengulang dari awal: hapus folder `backend/data`, atau masuk
sebagai admin lalu `POST /api/demo/reset`. Dokumentasi API interaktif: http://localhost:8000/docs

**Konfigurasi.** Salin `.env.example` menjadi `.env` (file `.env` tidak ikut di-commit). Semua variabel opsional:

| Variabel | Arti | Bawaan |
|---|---|---|
| `PK_SECRET_KEY` | Kunci tanda tangan sesi login | dibuat acak di `backend/data/secret.key` |
| `PK_DEMO_ACCOUNTS`, `PK_DEMO_PASSWORD` | Akun demo juri aktif/mati, kata sandinya | `1`, `sawit2026` |
| `PK_COOKIE_SECURE` | Cookie Secure: `auto` / `1` / `0` | `auto` |
| `PK_SATELLITE_MODE` | `demo` (NDVI simulasi berlabel, lapisan hutan & kehilangan tutupan nyata dari GFW) atau `live` (Sentinel-2 + Hansen) | `demo` |
| `PK_PETA_GFW` | `0` = jangan unduh tile peta hutan (JRC, SBTN) dan kehilangan tutupan Hansen dari GFW (kebun contoh tetap memakai tabel bawaan) | `1` |
| `PK_KAWASAN_SOURCE` | `auto` / `online` / `lokal` untuk cek kawasan hutan | `auto` |
| `PK_KAWASAN_URL`, `PK_KAWASAN_LAYERS`, `PK_KAWASAN_TIMEOUT` | Layanan peta kawasan, layer, batas waktu | Geoportal Kemenhut, otomatis, 10 s |
| `PK_KAWASAN_GFW`, `PK_KAWASAN_GFW_URL` | Cadangan otomatis Peta Kawasan Hutan KLHK 2017 (Global Forest Watch) | aktif, tile `idn_forest_area` v201709 |
| `PK_DATA_DIR`, `PK_DB_URL` | Lokasi data dan database | `backend/data` |
| `PK_TILE_URL`, `PK_TILE_ZOOM` | Sumber citra untuk AI batas kebun | Esri World Imagery, 18 |
| `PK_CORS` | Asal yang boleh memanggil API (mode pengembangan) | `http://localhost:5173` |

**Fitur tambahan (opsional)**
- **Satelit live:** `pip install -r backend/requirements-live.txt`, uji dengan `python -m app.scripts.check_live`, lalu
  `PK_SATELLITE_MODE=live`. Belum bisa kami uji dari lingkungan pengembangan (server satelit terblokir di sana).
- **Cek kawasan hutan Kemenhut:** uji koneksi dengan `python -m app.scripts.check_kawasan` (sekaligus menguji cadangan
  KLHK 2017 dari Global Forest Watch). Bila ada fungsi yang terbaca "?",
  buat `backend/data/kawasan/kode_fungsi.json` sesuai contoh yang dicetak skrip. Peta resmi lain (GeoJSON) cukup ditaruh di
  `backend/data/kawasan/`.
- **Segment Anything:** `pip install -r backend/requirements-sam.txt`, unduh `sam_vit_b_01ec64.pth` ke `backend/models/`.

## Deploy

```bash
docker build -t pasporkebun .
docker run -p 8000:8000 -e PK_SECRET_KEY=<string-acak> pasporkebun
```

Render (gratis): buat akun di render.com, pilih **New + → Blueprint**, hubungkan repositori ini. `render.yaml` sudah mengatur
Docker, health check, `PK_SECRET_KEY` acak, dan cookie Secure. Free plan tidur setelah 15 menit tanpa akses (permintaan
pertama butuh sekitar 1 menit), dan datanya dibuat ulang setiap server mulai.

## Akun demonstrasi

Buka `/masuk` lalu klik salah satu kartu (tanpa mengetik), atau masuk manual dengan kata sandi **`sawit2026`**:

| Nama pengguna | Peran | Yang bisa dicoba |
|---|---|---|
| `koperasi` | Petugas koperasi | Daftarkan kebun, lengkapi bukti lahan, tambah saksi, ajukan keberatan |
| `pengepul` | Pengepul UD Tani Jaya | Pindai PK-00001-F, catat 1.100 kg (diterima) |
| `sinarjaya` | Pengepul UD Sinar Jaya | Catat 9.000 kg dari PK-00001-F (ditahan) |
| `pabrik` | Pabrik kelapa sawit | Dasbor, skor anomali pengepul, paket data ekspor |
| `verifikator` | Verifikator independen | Inspeksi sampel + foto, putuskan keberatan, cek integritas riwayat |
| `admin` | Admin | Semua akses, ulang data demo |

Akun demo hanya untuk penilaian. Matikan di produksi dengan `PK_DEMO_ACCOUNTS=0`.

## Dokumentasi penggunaan AI

**AI di dalam produk** (semua berjalan di CPU server sendiri, tanpa API AI pihak ketiga):

| Komponen | Model / metode | Bagian produk | Akurasi |
|---|---|---|---|
| Penggambar batas kebun | Watershed berpenanda (OpenCV); opsional Segment Anything (Meta AI, ViT-B) | Pendaftaran kebun | IoU 0,93 (citra sintetis); literatur SAM lahan kecil IoU 0,71 |
| Deteksi perubahan lahan 2018-kini | COLD-lite: regresi harmonik robust + konfirmasi 5 citra (implementasi sendiri, NumPy) | Bukti satelit, tahun tanam | F1 100%, uji ketahanan 99% (simulasi); literatur COLD F1 81,8% |
| Keputusan risiko EUDR | Convergence of evidence (diadaptasi dari Whisp FAO) + pembeda peremajaan + cek kawasan hutan | Cap Aman / Perlu cek / Berisiko | 100% per skenario simulasi |
| Penjaga pengepul | Model kapasitas PPKS + Isolation Forest (scikit-learn) dengan alasan z-score | Halaman pengepul, dasbor pabrik | Pencuci TBS di peringkat atas |
| Pemilih sampel verifikasi | Pemeringkatan risiko + undian berbobot luas (rumus RSPO ISH) | Halaman verifikasi | – |

**Bagian yang sengaja bukan AI.** Status kawasan hutan dibaca dengan aturan pasti, bukan model: dari poligon peta resmi,
atau, untuk layanan Kemenhut Juni 2026 yang hanya mengizinkan tampilan, dari warna gambar petanya (setiap fungsi kawasan punya
warna tetap di renderer resmi; piksel di bawah kebun dicocokkan ke warna itu lalu diubah kembali menjadi poligon). Peta itu
dasar hukum, jadi hasilnya harus bisa diaudit dan sama setiap kali; model yang dilatih hanya akan menambah kemungkinan salah.

Semua keluaran AI adalah draf atau sinyal: batas dikoreksi petani dan saksi, status "perlu cek" diteruskan ke verifikasi
lapangan, skor anomali hanya urutan audit, dan keputusan akhir atas keberatan diambil manusia dengan alasan tertulis.
Rincian: [docs/ALGORITMA.md](docs/ALGORITMA.md), [docs/VALIDASI.md](docs/VALIDASI.md), halaman **Cara kerja AI** di aplikasi.

**AI dalam pengembangan.** Tim memakai AI coding assistant **Claude (Anthropic)** untuk riset literatur, menulis dan meninjau
kode, tes, serta dokumentasi (diperbolehkan guidebook). Seluruh kode ditinjau, diuji, dan dipertanggungjawabkan tim.

## Data nyata vs simulasi

| Bagian | Status |
|---|---|
| Citra satelit di peta dan untuk AI batas kebun | **Nyata** (Esri World Imagery) |
| Lapisan kehilangan tutupan pohon dan peta Kawasan Hutan | **Nyata** (Global Forest Watch; Kemenhut; Peta Kawasan Hutan KLHK 2017 via GFW) |
| Lapisan bukti deforestasi per kebun (hutan 2020, kehilangan tutupan sebelum/sesudah 2020) | **Nyata**: dua peta hutan 2020 (JRC GFC2020 dan hutan alam SBTN) + Hansen GFC dari tile Global Forest Watch, dihitung per piksel di dalam batas kebun (kebun contoh: tabel bawaan hasil hitungan yang sama). Berisiko hanya bila kedua peta hutan sepakat |
| Time series NDVI per kebun | **Simulasi berlabel** di mode demo, skenarionya mengikuti peta nyata; **nyata** (Sentinel-2) di mode live |
| Nama petani, desa, transaksi, pengepul, pabrik | **Fiktif** |
| Batas kawasan di sekitar kebun contoh | **Nyata**: salinan lokal Peta Kawasan Hutan KLHK 2017 (GFW) agar demo jalan tanpa internet; kebun baru dicek ke peta Kemenhut, cadangan KLHK 2017 |
| Lokasi kebun contoh | Poligon fiktif yang ditempatkan di Areal Penggunaan Lain (area "Kebun Swadaya") di sisi tenggara TN Tesso Nilo. Beberapa sengaja melanggar indikator peta di lokasi nyata: Joko (hutan dibuka 2025), Sutrisno (peremajaan 2023), Rina (Hutan Produksi), Darmawan (hutan tanpa kehilangan tutupan), Hasan (hutan menurut JRC, bukan hutan alam menurut SBTN: perlu cek, bukan berisiko). Uji: `python -m app.scripts.uji_indikator` atau halaman Cara kerja AI |

## Keamanan dan privasi

- Masuk per peran; setiap endpoint yang mengubah data menyebut peran yang boleh. Pengepul hanya mencatat atas nama usahanya.
- Kata sandi: hash PBKDF2-SHA256 (210.000 iterasi). Sesi: cookie HttpOnly + SameSite=Lax bertanda tangan HMAC-SHA256.
- CSRF (header wajib), Content-Security-Policy, X-Frame-Options, nosniff, Referrer-Policy, HSTS saat HTTPS.
- Batas laju: login 10/menit, AI 30/menit, unggahan 20/menit, cek paspor publik 60/menit.
- Validasi input (Pydantic): batas panjang teks, jumlah titik poligon, rentang koordinat, jenis & ukuran foto.
- Tanpa NIK/KTP. QR hanya berisi kode. Tampilan publik menyamarkan nama; paket ekspor dan GeoJSON tanpa nama petani.
  Pabrik hanya melihat status bukti lahan, bukan dokumennya. Foto inspeksi di-encode ulang (EXIF dibuang).
- Riwayat perubahan berantai hash SHA-256; perubahan diam-diam di database terdeteksi (`/api/audit/verify`).
- Rahasia di `.env` (tidak di-commit); contoh variabel di `.env.example`.
- Penilaian dampak pelindungan data pribadi (UU PDP Pasal 34, PP 33/2026): [`docs/DPIA.md`](docs/DPIA.md). Kebijakan privasi
  dalam bahasa sederhana untuk dibacakan ke petani: [`docs/KEBIJAKAN_PRIVASI.md`](docs/KEBIJAKAN_PRIVASI.md). Keduanya
  mencatat dengan jujur hal yang belum selesai (hapus data per petani, retensi otomatis, enkripsi basis data).
- Berkas geolokasi diperiksa terhadap aturan format TRACES sebelum diekspor (6 desimal, tertutup, tanpa lubang atau sisi
  berpotongan, `ProducerCountry` ISO2); kebun yang akan ditolak sistem UE tidak ikut pengiriman (`services/traces.py`).

## Pemetaan ke rubrik penilaian

| Kriteria (bobot) | Bukti di aplikasi |
|---|---|
| Kesesuaian Masalah & Solusi (25%) | Empat peran nyata; syarat Siap EUDR mengikuti EUDR, ISPO (Permentan 33/2025), dan RSPO; sertifikat tanah tidak diwajibkan; pembeda peremajaan agar petani PSR tidak dirugikan; keberatan petani |
| Inovasi & Implementasi Teknologi (25%) | 4 komponen AI yang masing-masing mengubah keputusan; riwayat satelit 5+ tahun; cek kawasan hutan otomatis; penjaga pengepul (celah yang belum ditutup solusi lain); sampel verifikasi berbasis risiko |
| Rekayasa Perangkat Lunak (25%) | Arsitektur berlapis, tipe ketat (Pydantic + TypeScript strict), 97 tes otomatis, migrasi aditif, Docker + Render, dokumentasi API otomatis, setup satu perintah |
| Desain & Pengalaman Pengguna (15%) | GPS "saya di kebun" alih-alih membaca citra; pertanyaan per sisi batas; satu alur per peran; checklist Siap EUDR yang menyebut apa yang kurang; kartu QR cetak untuk petani tanpa ponsel |
| Etika & Keamanan Digital (10%) | Lihat bagian Keamanan dan privasi; DPIA dan kebijakan privasi di `docs/`; vonis Berisiko butuh dua peta hutan sepakat + verifikator manusia; transparansi AI di halaman Cara kerja AI; atribusi lengkap di bawah |

## Pengujian

```bat
cd backend
.venv\Scripts\python -m pytest -q              :: 97 tes
.venv\Scripts\python -m app.scripts.validate   :: menulis docs/VALIDASI.md
```

## Atribusi

**Data & layanan:** citra Esri World Imagery (Esri, Maxar, Earthstar Geographics); peta OpenStreetMap (© kontributor
OpenStreetMap, ODbL); kehilangan tutupan pohon Hansen/UMD/Google/USGS/NASA via Global Forest Watch (CC BY 4.0); peta hutan JRC Global Forest
Cover 2020 (Komisi Eropa, JRC) dan kelas hutan alam SBTN Natural Lands Map v1.1 (Mazur dkk. 2025, WRI/SBTN), keduanya via
Global Forest Watch; Peta
Kawasan Hutan Kementerian Kehutanan (Direktorat Pengukuhan dan Penatagunaan Kawasan Hutan, layanan SIGAP); Peta Kawasan Hutan
Indonesia KLHK 2017 lewat Global Forest Watch (dataset `idn_forest_area`, CC BY 4.0); Sentinel-2
(Copernicus/ESA) via Microsoft Planetary Computer; Hansen Global Forest Change v1.12 (Google Cloud Storage).

**Metode:** logika keputusan diadaptasi dari Whisp (FAO / Forest Data Partnership, MIT); COLD/CCDC (Zhu dkk.); tahun tanam
mengikuti Descals dkk. (2024); kurva potensi produksi PPKS; rumus sampel inspeksi dari Standar Petani Swadaya RSPO 2024;
syarat bukti lahan dari Permentan 33/2025 (ISPO) dan pedoman EUDR C/2026/3896. Daftar pustaka lengkap di docs/ALGORITMA.md.

**Pustaka kode:** React, React Router, Vite, TypeScript (MIT/Apache-2.0); Leaflet (BSD-2), react-leaflet (Hippocratic-2.1),
Leaflet-Geoman Free (MIT); qrcode (MIT); jsQR (Apache-2.0); lucide-react (ISC); FastAPI, SQLAlchemy, Pydantic, Uvicorn,
python-dotenv (MIT/BSD); NumPy, Shapely, scikit-learn (BSD); OpenCV (Apache-2.0); Pillow (MIT-CMU); truststore (MIT);
Segment Anything (Apache-2.0, opsional). **Huruf:** Instrument Sans, Saira Stencil One, Space Mono (SIL OFL 1.1, via Fontsource).
Tidak ada template aplikasi jadi yang dipakai; desain antarmuka dibuat tim.
