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
   dipindahkan. Potongan peta di sekitar lokasi demo disimpan di `app/seed_data/` agar demo tetap jalan tanpa internet;
   satu kebun (Rina Wati) sengaja diletakkan di Hutan Produksi.

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
- Layanan peta Kawasan Hutan Kemenhut (dipakai Peta Interaktif SIGAP, skala 1:250.000): https://geoportal.planologi.kehutanan.go.id/server/rest/services/Peta_Interaktif_2026/KWSHUTAN_AR_250K/MapServer
  (alamat lama geoportal.menlhk.go.id sudah tidak aktif sejak KLHK dipecah)
- Peta Kawasan Hutan Indonesia KLHK 2017 di Global Forest Watch: https://data-api.globalforestwatch.org/dataset/idn_forest_area
  (tile: https://tiles.globalforestwatch.org/idn_forest_area/v201709/dynamic/{z}/{x}/{y}.pbf, lisensi CC BY 4.0)
- Spesifikasi Mapbox Vector Tile 2.1: https://github.com/mapbox/vector-tile-spec
- RSPO Independent Smallholder Standard 2024: https://rspo.org/wp-content/uploads/Consolidated-ISH-2024_Adopted_13112024.pdf
- Permentan No. 33 Tahun 2025 (ISPO): https://peraturan.go.id/files/permentan-no-33-tahun-2025.pdf
- Pedoman EUDR C/2026/3896: https://eur-lex.europa.eu/eli/C/2026/3896/oj/eng
- Rwanda LTR: https://www.gim-international.com/content/article/spatial-initiatives-for-sustainable-land-management
- Pemetaan partisipatif drone Rwanda (FIG 2020): https://fig.net/resources/proceedings/fig_proceedings/fig2020/papers/ts07h/TS07H_stocker_koeva_et_al_10290.pdf
- IFPRI, pemetaan petak oleh petani di tablet: https://www.ifpri.org/blog/leveraging-local-knowledge-map-and-link-agricultural-plots-farmer-practices/
- Akurasi GPS ponsel di bawah kanopi (Forests 13:1591): https://mdpi.com/1999-4907/13/10/1591
