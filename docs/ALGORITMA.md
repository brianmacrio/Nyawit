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

## 5. Status kawasan hutan (legalitas)

EUDR tidak hanya meminta bebas deforestasi, tetapi juga lahan yang legal menurut hukum negara asal. Di Indonesia, kebun di
dalam kawasan hutan (konservasi, hutan lindung, hutan produksi) tanpa pelepasan kawasan tidak legal. Peta global (JRC, Hansen)
tidak tahu status hukum ini, jadi kami membaca peta resmi:

1. Sumber: layanan ArcGIS REST *Kawasan Hutan* Kementerian Kehutanan (KWSHUTAN_AR_250K, layanan yang dipakai Peta Interaktif
   SIGAP, dasar Permen LHK 7/2021). Skalanya 1:250.000, jadi batas di tingkat kebun bisa meleset puluhan sampai ratusan meter.
2. Area kebun dibagi ke sel grid 0,01° (~1,1 km). Sel yang belum ada di cache diminta lewat operasi `identify` (cadangan:
   `query` per layer), poligon digeneralisasi ~5 m, dipotong sebatas sel, lalu disimpan di disk. Cache membuat setiap sel
   hanya diunduh sekali dan demo tetap jalan saat offline. Bila layanan gagal, aplikasi berhenti mencoba selama 5 menit
   agar pendaftaran kebun tetap cepat.
3. Fungsi kawasan dibaca dari domain kode layanan, teks/singkatan (Hutan Lindung, HPT, HPK, TN, APL, ...), atau tabel kode
   buatan pengguna. Singkatan pendek hanya dibaca dari kolom fungsi, agar nama seperti "Kelompok Hutan Air ..." tidak
   terbaca sebagai tubuh air.
4. Persentase luas kebun per fungsi dihitung dengan irisan poligon (shapely). Aturan 0: > 5% di kawasan hutan → Berisiko,
   dengan arahan penyelesaian sesuai fungsi (konservasi/HL berbeda dari hutan produksi). 0–5% hanya diberi catatan karena
   bisa berasal dari ketelitian peta.
5. Kejujuran data: bila peta tidak terjangkau atau fungsi tidak terbaca, paspor menulisnya terang-terangan; di mode live
   status kebun menjadi Perlu cek, bukan Aman.
6. Cadangan otomatis (ditambahkan 12 Nov 2026, saat server peta Kemenhut mati): **Peta Kawasan Hutan Indonesia KLHK 2017**
   yang disediakan Global Forest Watch sebagai tile vektor publik (`idn_forest_area` v201709, tanpa kunci API).
   - Tile zoom 12 (~9,8 km) yang menutupi kebun diunduh sekali, dibaca dengan pembaca Mapbox Vector Tile buatan sendiri
     (`services/mvt.py`, tanpa dependensi; diuji terhadap tile asli GFW: 476 titik, 82.022 ha untuk TN Tesso Nilo), lalu
     disimpan di cache disk selama setahun.
   - Tile "dynamic" GFW berisi poligon utuh, jadi fitur yang sama di beberapa tile digabung per `gfw_fid`.
   - Fungsi dibaca dari teks `desc_in` ("Taman Nasional", "Hutan Produksi Terbatas", ...), kode `fungsikawa` sebagai cadangan.
   - Tile yang gagal diunduh (termasuk HTTP 404) membuat status "belum dicek", tidak pernah "di luar kawasan".
   - Paspor menyebut sumbernya ("Peta Kawasan Hutan KLHK 2017 (dataset Global Forest Watch)") dan memberi catatan bahwa data
     2017 bisa tertinggal dari SK sesudahnya; analisis ulang memakai peta Kemenhut begitu tersedia.
   - Peta aplikasi menampilkan lapisan "Kawasan hutan KLHK 2017 (otomatis, GFW)" untuk area yang sedang dilihat (zoom 12+),
     sehingga batas kawasan di mana pun di Indonesia muncul tanpa digambar.
7. Peta Kemenhut yang hanya bisa ditampilkan (12 Nov 2026). Layanan `KWSHUTAN_AR_250K` (layer
   `KWSHUTAN_AR_250K_JUNI2026_REV1`) hanya punya kemampuan "Map": `identify` dan `query` ditolak (HTTP 400), tetapi gambar
   peta (`export`) boleh diminta. Status kawasan dibaca dari gambar itu (`services/kawasan_raster.py`):
   - Palet diambil dari renderer resmi layanan (uniqueValue pada kolom `FUNGSIKWS`), misalnya Kawasan Konservasi 173,63,255;
     Hutan Lindung 2,173,0; Hutan Produksi Tetap 255,255,0; Hutan Produksi Terbatas 138,242,0; HPK 255,94,255;
     Area Penggunaan Lain 255,255,255; Tubuh Air 0,197,255. Label dipetakan ke fungsi dengan aturan teks yang sama.
   - Per sel 0,01 derajat diminta PNG 512 x 512 dalam EPSG:4326 (~2,2 m per piksel), lalu setiap warna unik dicocokkan ke warna
     palet terdekat. Piksel tepi hasil anti-alias (campuran dua warna palet) ikut warna yang lebih dekat; piksel tembus pandang
     dianggap tanpa data; piksel buram dengan warna asing dicatat "fungsi tidak terbaca" sehingga kebun menjadi Perlu cek,
     bukan Aman, bila simbol peta berubah.
   - Piksel per label diubah menjadi poligon (rentang per baris digabung lalu disatukan), disimpan di cache seperti hasil
     `query`, lalu persentase luas kebun di tiap fungsi dihitung seperti biasa. Paspor menulis "dibaca dari gambar peta resmi".
   - Uji silang 12 Nov 2026 di browser: 22 kebun contoh 100% APL dan kebun Rina 100% Hutan Produksi menurut peta Juni 2026,
     sama dengan hasil peta KLHK 2017.
   - Ini bukan AI dan sengaja tidak dibuat AI: warnanya ditetapkan pemilik peta, jadi pencocokan pasti lebih tepat dan bisa
     diaudit daripada model yang dilatih.
8. Data demo: kebun contoh ditempatkan di Areal Penggunaan Lain menurut peta yang sama (area "Kebun Swadaya" di sisi tenggara
   TN Tesso Nilo, Riau). Lokasi demo lama ternyata berada di dalam TN Tesso Nilo menurut peta resmi, jadi seluruh kebun contoh
   dipindahkan. Potongan peta di sekitar lokasi demo (bbox 102,02–102,13; -0,445–-0,30) disimpan di `app/seed_data/` agar demo
   tetap jalan tanpa internet; satu kebun (Rina Wati) sengaja diletakkan di Hutan Produksi.
9. Bila peta Kemenhut terbaru dan salinan peta KLHK 2017 berbeda di satu kebun (> 5% luas), paspor memberi peringatan dan
   keputusan memakai peta terbaru. Di sekitar lokasi demo kedua peta hampir sama; perbedaannya hanya potongan tipis di tepi batas
   (beda digitasi skala 1:250.000).

Batasan: peta kawasan berskala kecil dan bisa tertinggal dari SK pelepasan terbaru. Karena itu hasil "masuk kawasan" adalah
sinyal untuk diverifikasi (sertifikat, SK pelepasan, cek lapangan), bukan vonis.

## 6. Pemetaan oleh petani, status Siap EUDR, dan verifikasi

**Mengapa tidak meminta petani membaca citra satelit.** Program pemetaan yang berhasil tidak mengandalkan petani membaca citra
sendirian. Di Rwanda (11 juta bidang, sekitar US$6 per bidang, sengketa < 1%), petugas lokal menggambar batas di foto udara
bersama pemilik dan tetangga. Studi IFPRI di Kenya: hanya 70% rumah tangga bisa menggambar petaknya di tablet berisi citra
2,5 m. Studi drone di Rwanda: sudut tanpa penanda di lapangan meleset lebih dari 5 m. GPS ponsel di bawah kanopi pun meleset
sekitar 9-10 m. Karena itu alurnya: GPS saat berdiri di kebun (EUDR cukup satu titik untuk kebun < 4 ha), draf batas AI,
pertanyaan ciri batas per sisi, "sudut ini = posisi saya" untuk sudut yang tidak jelas, dan saksi tetangga.

**Lima syarat Siap EUDR** (services/readiness.py): lokasi disaksikan; bukti penguasaan lahan bertingkat (sertifikat / surat
desa / pernyataan + 2 saksi, sesuai Permentan 33/2025 yang tidak mewajibkan sertifikat) + STDB ada/diurus + tanpa sengketa;
di luar kawasan hutan; bebas deforestasi setelah 31 Des 2020; tidak menunggu atau gagal inspeksi. Berlaku 12 bulan.

**Sampel verifikasi.** Ukuran sampel mengikuti inspeksi internal Standar Petani Swadaya RSPO 2024: akar(n) x 2,5 x 1,5.
Kebun berisiko, perlu cek, bersengketa, dan berbukti lemah dipilih lebih dulu; sisanya diundi berbobot luas. Foto inspeksi
dicek jaraknya ke batas kebun (> 150 m diberi peringatan).

**Keberatan.** Diputuskan verifikator dengan alasan tertulis. Bila analisis satelit berikutnya menghasilkan bukti baru,
keputusan lama gugur otomatis dan kebun ditinjau ulang.

**Riwayat berantai hash** (services/audit.py). Setiap kejadian menyimpan SHA-256 dari isinya dan hash kejadian sebelumnya,
sehingga perubahan atau penghapusan diam-diam di database terdeteksi oleh `verify_chain`.

**Paket ekspor** (services/shipment.py). Mengikuti informasi uji tuntas EUDR: geolokasi semua kebun asal, rentang produksi,
volume, bukti bebas deforestasi dan legalitas. Hanya kebun Siap EUDR yang masuk; pedoman EUDR menyatakan pencampuran
(*mass balance*) tidak diterima. Nama petani tidak disertakan karena tidak diwajibkan.

## 7. Tiga indikator peta: apa yang diukur, uji pelanggaran, dan validitasnya

Peta Kebun punya tiga lapisan indikator. Masing-masing menjawab pertanyaan yang berbeda, jadi tidak ada satu pun yang boleh
dipakai sendirian untuk memvonis kebun.

| Indikator | Pertanyaan yang dijawab | Bila menyala, artinya | Batasan utama |
|---|---|---|---|
| 1. Kehilangan tutupan pohon 2021–2025 (Hansen/GLAD lewat GFW) | Apakah pohon di kebun ini hilang sesudah batas EUDR? | Ada penebangan/pembukaan; **belum tentu deforestasi** | Mencatat semua pohon > 5 m yang hilang, termasuk peremajaan dan panen kebun; tidak tahu apakah lahan itu hutan |
| 2. Kawasan hutan KLHK 2017 (GFW) | Apakah lahan ini kawasan hutan menurut peta resmi 2017? | Masalah **legalitas**: sawit hanya sah di luar kawasan atau setelah pelepasan | Data 2017, skala 1:250.000; tidak memuat SK pelepasan sesudahnya |
| 3. Kawasan hutan peta Kemenhut terbaru (Juni 2026) | Sama, menurut peta terbaru | Sama; peta ini yang dipakai untuk keputusan bila terjangkau | Skala 1:250.000 (tepi batas bisa bergeser puluhan–ratusan meter); bisa tertinggal dari SK terbaru |

**Mengapa indikator 1 dipadukan dengan peta hutan JRC 2020.** Definisi deforestasi EUDR adalah konversi *hutan* menjadi
lahan pertanian sesudah 31 Des 2020, dan kebun sawit bukan hutan. Global Forest Watch sendiri menegaskan bahwa kehilangan
tutupan pohon tidak sama dengan deforestasi (termasuk panen/peremajaan kebun). Karena itu sejak versi ini, di mode demo pun,
aplikasi membaca dua lapisan nyata per piksel di dalam batas kebun (`services/satellite/peta_gfw.py`):

- Hansen GFC (tile GFW render "encoded"): kanal biru = tahun kehilangan − 2000, ambang kerapatan tajuk 30%.
- JRC Global Forest Cover 2020 v2020.3: peta hutan acuan Komisi Eropa untuk EUDR, yang sengaja tidak menghitung kebun
  sawit/karet sebagai hutan.

Aturannya: kehilangan sesudah 2020 di lahan yang hutan pada 2020 → **Berisiko** (aturan 4); kehilangan sesudah 2020 di lahan
yang bukan hutan → **Aman, peremajaan** (aturan 1-peremajaan); hutan 2020 tanpa kehilangan → **Perlu cek** (aturan 5).

**Dua peta hutan, bukan satu (sejak 14 Nov 2026).** Makalah resmi peta JRC (Bourgoin dkk., ESSD 2026) melaporkan akurasi
91%, tetapi galat komisi kelas hutan 18%: peta itu lebih sering menyebut "hutan" pada lahan yang bukan hutan daripada
sebaliknya, terutama di kebun pohon dan agroforestri (sawit dan karet disebut), dan penulisnya menyarankan peta itu
dipasangkan dengan data lain atau foto lapangan. Studi lapangan kopi di Meksiko (Mongabay, Des 2025) menemukan peta global
menandai sekitar tiga perempat kebun lama sebagai tidak patuh. Kalau aturan 4 bersandar pada JRC saja, petani yang
meremajakan karet tua menjadi sawit sesudah 2020 akan divonis Berisiko. Karena itu setiap piksel yang hilang dicek juga ke
peta hutan kedua, kelas hutan alam **SBTN Natural Lands Map v1.1** (WRI/SBTN, 30 m; tile GFW
`sbtn_natural_forests_map/v202504/natural_forest`), peta yang juga dipakai GFW Pro ("pendekatan terdekat definisi hutan
EUDR") dan ditawarkan Koltiva sebagai lapisan pembanding:

| Kondisi per piksel di dalam batas kebun | Keputusan |
|---|---|
| Hutan menurut JRC **dan** SBTN, hilang sesudah 2020, di ≥ 10% luas kebun | **Berisiko** (aturan 4) |
| Hutan menurut JRC saja, hilang sesudah 2020 | **Perlu cek**, wajib masuk sampel inspeksi (aturan 4-peta-berbeda) |
| Hutan alam menurut SBTN saja, hilang sesudah 2020 | **Perlu cek** (aturan 1-peta-berbeda) |
| Kehilangan tutupan jatuh di luar bagian kebun yang berhutan | **Perlu cek** untuk sisa hutannya (aturan 4-di-luar-hutan) |
| Peta kedua tidak terbaca | Aturan satu peta tetap berlaku; paspor mencatat "bersandar pada satu peta hutan" |

Hasil "peta berbeda" sengaja **bukan Aman**: hutan tanaman tetap terhitung hutan menurut EUDR dan SBTN hanya memetakan hutan
alam, jadi yang memutuskan adalah verifikator di lapangan (tunggul, umur tanaman, foto geotag). Tumpang-tindih dihitung per
piksel (hutan ∧ hilang), bukan dari dua persentase per kebun, supaya hutan di satu sudut dan peremajaan di sudut lain tidak
terbaca sebagai deforestasi. Mengapa bukan *Natural Forests of the World 2020* (Google DeepMind/WRI, 10 m, akurasi 92,2%)?
Peta itu lebih tajam, tetapi hanya tersedia di Earth Engine (butuh akun); SBTN tersedia sebagai tile publik tanpa kunci.
Zoom 14 (piksel ~4,8 m dari data 30 m), hanya pusat piksel di dalam poligon yang dihitung. Untuk kebun contoh, hasil
hitungan disimpan di `seed_data/lapisan_peta_demo.json` (dibangun `python -m app.scripts.bangun_lapisan_demo`, algoritma yang sama) agar demo identik
tanpa internet; kebun baru dihitung online lalu tile disimpan di cache. Deret NDVI di mode demo tetap simulasi, tetapi
skenarionya mengikuti peta nyata, dan paspor memberi peringatan bila keduanya bertentangan.

**Kebun yang sengaja melanggar tiap indikator** (lokasi dipilih dari data nyata, lihat `seed.py` dan
`app/scripts/uji_indikator.py`; uji juga bisa dijalankan dari halaman *Cara kerja AI* → *Uji indikator peta*):

| Kebun uji | Indikator 1 | Indikator 2 | Indikator 3 | Hutan JRC 2020 | Keputusan yang benar |
|---|---|---|---|---|---|
| Joko Susilo (PK-00004-U) | menyala: 100% hilang 2025 | tidak (APL) | tidak (APL) | 100% (SBTN: 95%) | Berisiko: hutan dibuka 2025, dua peta sepakat |
| Sutrisno Wibowo (PK-00003-P) | menyala: 100% hilang 2023 | tidak | tidak | 0% | Aman: peremajaan, bukan deforestasi |
| Rina Wati (PK-00005-Z) | tidak | menyala: 100% Hutan Produksi | menyala: Hutan Produksi Tetap | 0% | Berisiko: legalitas |
| Kebun uji di TN Tesso Nilo | tidak (dibuka 2011) | menyala: konservasi | menyala: konservasi | 0% | Berisiko: legalitas, walau lolos uji deforestasi |
| Darmawan Lubis (PK-00006-E) | tidak | tidak | tidak | 92% | Perlu cek lapangan |
| Hasan Siregar (PK-00010-E) | menyala: 78% hilang 2021–2022 | tidak | tidak | 96% (SBTN: 0%) | Perlu cek: dua peta hutan tidak sepakat |
| Budi Santoso (PK-00001-F) | tidak | tidak | tidak | 0% | Aman |

Pemindaian 0,16° x 0,16° di sekitar desa demo menunjukkan pola yang penting untuk validitas: di APL, kehilangan tutupan
sesudah 2020 sangat sering (blok peremajaan 2023–2025), tetapi hampir semuanya di lahan yang bukan hutan menurut JRC.
Kehilangan hutan sesudah 2020 justru banyak terjadi di dalam kawasan hutan (TN Tesso Nilo, HP). Jadi indikator 1 sendirian
akan menuduh banyak petani peremajaan; indikator 2/3 sendirian akan melewatkan pembukaan hutan di APL (kasus Joko).

**Apakah ketiganya valid untuk memutuskan kebun berisiko?** Valid sebagai *bukti*, tidak sebagai *vonis*:

- Kehilangan tutupan (Hansen) tidak membedakan hutan dan kebun; tanpa peta hutan/komoditas, hasilnya bias ke positif palsu
  di daerah peremajaan.
- Peta hutan 2020 global punya galat. Studi 21 peta global (Freitas Beyer dkk., 2025, dilaporkan Mongabay) menemukan hanya 2
  yang memenuhi indikator kualitas untuk EUDR dan banyak yang melebih-lebihkan hutan; JRC sendiri menyatakan petanya tidak
  mengikat dan perlu dilengkapi data lokal. Sawit swadaya tua yang rapat bisa terbaca hutan (kasus Darmawan → Perlu cek).
- Pemetaan sawit rakyat oleh satelit masih sulit (akurasi pembeda swadaya/perkebunan ~64% di studi Gaveau dkk. 2022), sebab
  itu lapisan komoditas belum dipakai di mode demo dan JRC yang dipakai sebagai pemisah.
- Peta kawasan hutan adalah dasar legalitas, bukan tutupan lahan. Indonesia belum punya satu peta yang disepakati semua
  pihak; ±3,3 juta ha sawit berada di kawasan hutan dan sebagian sedang diproses lewat UU Cipta Kerja Pasal 110A/110B. Jadi
  "masuk kawasan" berarti perlu dokumen (SK pelepasan, keterlanjuran), bukan otomatis ilegal selamanya.
- Pendekatan yang dianjurkan (Whisp/FAO, pedoman Komisi Eropa): gabungkan beberapa peta (convergence of evidence), lalu
  verifikasi lapangan dan dokumen untuk kasus yang meragukan. Aplikasi mengikuti itu: tiga indikator + JRC + time series →
  Aman/Perlu cek/Berisiko dengan alasan, dan setiap status bisa diajukan keberatan dengan bukti.

## Sumber

- Whisp: https://pypi.org/project/openforis-whisp/
- RADD: Reiche et al. 2021, Environ. Res. Lett. https://iopscience.iop.org/article/10.1088/1748-9326/abd0a8
- JRC GFC2020 accuracy: https://publications.jrc.ec.europa.eu/repository/handle/JRC141231
- GFC2020, makalah data (Bourgoin dkk., ESSD 18:1331, 2026; galat komisi hutan 18%, kebun pohon): https://essd.copernicus.org/articles/18/1331/2026/essd-18-1331-2026-discussion.html
- SBTN Natural Lands Map v1.1, kelas hutan alam di GFW: https://data-api.globalforestwatch.org/dataset/sbtn_natural_forests_map
- GFW Pro dan EUDR (hutan alam SBTN, peringatan terintegrasi, verifikasi citra): https://pro-news.globalforestwatch.org/news-events/how-gfw-pro-supports-eudr-compliance
- Koltiva, kepatuhan EUDR (lapisan JRC, GFW, SBTN; agen lapangan): https://www.koltiva.com/eudrcompliance
- Natural Forests of the World 2020 (Google Research): https://research.google/blog/separating-natural-forests-from-other-tree-cover-with-ai-for-deforestation-free-supply-chains/
- Format GeoJSON TRACES v1.3 (Komisi Eropa): https://eudr.webcloud.ec.europa.eu/tracesnt/help/eudr-documentation/operator/geojson-description.html
- Peta sawit global: Descals et al. 2021, ESSD 13:1211 https://essd.copernicus.org/articles/13/1211/2021/
- Tahun tanam sawit: Descals et al. 2024, ESSD 16:5111 https://essd.copernicus.org/articles/16/5111/2024/
- Pembanding algoritma perubahan: Remote Sensing 17:680 (2025)
- SAM untuk lahan petani kecil: https://arxiv.org/abs/2407.01846
- Delineate Anything: https://arxiv.org/abs/2504.02534
- Satelligence × Fairtrade: https://the-european.eu/story-50128/
- Koltiva × REA Kaltim: https://www.agtechnavigator.com/Article/2025/08/11/tackling-barriers-to-eudr-compliance-for-indonesian-smallholders
- Layanan peta Kawasan Hutan Kemenhut (dipakai Peta Interaktif SIGAP, skala 1:250.000): https://geoportal.planologi.kehutanan.go.id/server/rest/services/Peta_Interaktif_2026/KWSHUTAN_AR_250K/MapServer
  (alamat lama geoportal.menlhk.go.id sudah tidak aktif sejak KLHK dipecah)
- Peta Kawasan Hutan Indonesia KLHK 2017 di Global Forest Watch: https://data-api.globalforestwatch.org/dataset/idn_forest_area
  (tile: https://tiles.globalforestwatch.org/idn_forest_area/v201709/dynamic/{z}/{x}/{y}.pbf, lisensi CC BY 4.0)
- Spesifikasi Mapbox Vector Tile 2.1: https://github.com/mapbox/vector-tile-spec
- Tile kehilangan tutupan Hansen dan JRC GFC2020 di GFW: https://data-api.globalforestwatch.org/dataset/umd_tree_cover_loss ,
  https://data-api.globalforestwatch.org/dataset/jrc_global_forest_cover
- GFW, data satelit untuk EUDR (kehilangan tutupan ≠ deforestasi): https://globalnaturewatch.org/blog/data/satellite-data-eu-regulation-deforestation-free-supply-chains/
- JRC GFC2020 di Earth Engine (tidak mengikat, sawit tidak dihitung hutan): https://developers.google.com/earth-engine/datasets/catalog/JRC_GFC2020_V3
- Kualitas 21 peta hutan global untuk EUDR (Mongabay, Des 2025): https://news.mongabay.com/2025/12/researchers-find-concerning-gaps-in-global-maps-used-for-eudr-compliance/
- Whisp, convergence of evidence (FAO): https://www.fao.org/fileadmin/user_upload/faoweb/NFM/WhispOverview.pdf
- Pemetaan sawit swadaya vs perkebunan (Gaveau dkk. 2022): https://pmc.ncbi.nlm.nih.gov/articles/PMC8963565
- Legalitas sawit di kawasan hutan (ClientEarth, Apr 2025): https://www.clientearth.org/media/hgvgx5wo/was-it-produced-legally_indonesia_clientearth_april-2025.pdf
- 3,3 juta ha sawit di kawasan hutan, kebutuhan satu peta (Antara 2025): https://kalbar.antaranews.com/berita/629045/satu-peta-hutan-diperlukan-untuk-tertibkan-lahan-sawit
- Proses keterlanjuran Pasal 110A/110B (Mongabay, Mar 2025): https://mongabay.co.id/2025/03/03/menyoal-pemutihan-sawit-hampir-800-ribu-hektar/amp/
- RSPO Independent Smallholder Standard 2024: https://rspo.org/wp-content/uploads/Consolidated-ISH-2024_Adopted_13112024.pdf
- Permentan No. 33 Tahun 2025 (ISPO): https://peraturan.go.id/files/permentan-no-33-tahun-2025.pdf
- Pedoman EUDR C/2026/3896: https://eur-lex.europa.eu/eli/C/2026/3896/oj/eng
- Rwanda LTR: https://www.gim-international.com/content/article/spatial-initiatives-for-sustainable-land-management
- Pemetaan partisipatif drone Rwanda (FIG 2020): https://fig.net/resources/proceedings/fig_proceedings/fig2020/papers/ts07h/TS07H_stocker_koeva_et_al_10290.pdf
- IFPRI, pemetaan petak oleh petani di tablet: https://www.ifpri.org/blog/leveraging-local-knowledge-map-and-link-agricultural-plots-farmer-practices/
- Akurasi GPS ponsel di bawah kanopi (Forests 13:1591): https://mdpi.com/1999-4907/13/10/1591
