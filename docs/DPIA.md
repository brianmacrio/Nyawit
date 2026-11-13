# Penilaian Dampak Pelindungan Data Pribadi (DPIA) ringkas

Dokumen ini adalah penilaian dampak awal yang disusun tim pengembang PasporKebun. Isinya mengikuti empat unsur minimal
penilaian dampak: deskripsi dan tujuan pemrosesan, kebutuhan dan proporsionalitas, risiko terhadap subjek data, dan
langkah pelindungan. Ini bukan nasihat hukum dan belum ditinjau pejabat pelindungan data. Sebelum dipakai dengan data
petani sungguhan, dokumen ini harus ditinjau ulang bersama koperasi dan pabrik yang menjadi pengendali data.

| | |
|---|---|
| Versi | 1.0, 14 November 2026 |
| Sistem | PasporKebun 1.1 (lihat `README.md`) |
| Status data saat ini | Seluruh data di repositori dan demo FIKTIF (nama, desa, transaksi). Belum ada data petani sungguhan |
| Tinjau ulang | Sebelum pilot pertama, lalu setiap kali ada fitur baru yang memproses data pribadi atau mengubah keputusan otomatis |

## 1. Mengapa penilaian ini wajib

UU No. 27 Tahun 2022 Pasal 34 mewajibkan penilaian dampak bila pemrosesan berpotensi risiko tinggi. PasporKebun memenuhi
empat dari tujuh kriteria ayat (2):

| Kriteria Pasal 34 ayat (2) | Berlaku? | Alasan |
|---|---|---|
| a. Keputusan otomatis berdampak hukum atau signifikan | **Ya** | Status Aman / Perlu cek / Berisiko dan Siap EUDR menentukan apakah TBS petani boleh masuk rantai pasok ekspor; pembelian bisa ditahan otomatis di pengepul |
| b. Data pribadi spesifik | Tidak | Tidak ada data kesehatan, biometrik, genetika, catatan kejahatan, data anak, atau keuangan pribadi. Tidak ada NIK/KTP |
| c. Skala besar | Belum | Demo 63 kebun. Menjadi **ya** bila dipakai satu kabupaten (ribuan petani) |
| d. Evaluasi, penskoran, pemantauan sistematis | **Ya** | Skor risiko kebun, skor anomali pengepul, dan cek satelit berkala atas lahan milik orang tertentu |
| e. Pencocokan atau penggabungan data | **Ya** | Batas kebun digabung dengan peta hutan (JRC, SBTN, Hansen), peta kawasan hutan, dan riwayat transaksi |
| f. Teknologi baru | **Ya** | AI penggambar batas, deteksi perubahan dari deret citra satelit, deteksi anomali |
| g. Membatasi hak subjek data | Tidak | Lihat bagian 5; ada kekurangan yang dicatat di bagian 6 |

PP No. 33 Tahun 2026 (ditetapkan 16 Juli 2026, berlaku 16 Januari 2027) merinci kewajiban ini: penilaian dilakukan
sebelum pemrosesan berisiko tinggi, didokumentasikan, dan ditinjau ulang bila risikonya berubah.

## 2. Deskripsi dan tujuan pemrosesan

**Tujuan.** Membuktikan bahwa kebun sawit petani swadaya legal dan tidak berasal dari deforestasi setelah 31 Desember
2020 (EUDR), supaya TBS-nya tetap bisa dijual ke rantai pasok ekspor, dan mencegah TBS dari kebun lain menumpang
identitas kebun yang patuh.

**Peran.** Koperasi (atau pabrik yang membina petani) adalah pengendali data: ia yang menentukan tujuan dan mendaftarkan
petani. Penyelenggara PasporKebun adalah prosesor. Pengepul, pabrik, dan verifikator adalah penerima data dengan akses
terbatas per peran.

**Data yang diproses.**

| Data | Subjek | Sumber | Dipakai untuk | Siapa yang melihat |
|---|---|---|---|---|
| Nama petani, desa | Petani | Diisi petugas koperasi bersama petani | Identitas pemilik paspor | Pengguna terdaftar; publik hanya nama tersamar (mis. "Budi S.") |
| Batas kebun (poligon), titik GPS, luas | Petani | GPS di kebun + AI penggambar batas, dikonfirmasi petani | Cek deforestasi, kawasan hutan, kapasitas panen | Pengguna terdaftar; publik hanya luas dan desa, tanpa lokasi |
| Bukti lahan (jenis dan nomor surat), status STDB, pernyataan sengketa | Petani | Diisi koperasi | Syarat legalitas | Koperasi, verifikator; paket ekspor hanya memuat jenisnya |
| Nama saksi batas dan hubungannya | Tetangga, ketua kelompok tani | Diisi koperasi | Bukti penguasaan lahan | Koperasi, verifikator |
| Tahun tanam | Petani | Pernyataan + hasil satelit | Kapasitas panen | Pengguna terdaftar |
| Transaksi TBS (berat, waktu, pengepul, keputusan) | Petani, pengepul | Dicatat pengepul saat memindai QR | Ketertelusuran, cegah pencucian TBS | Pengepul (miliknya sendiri), pabrik, koperasi |
| Hasil inspeksi, foto lapangan, lokasi foto | Petani, verifikator | Verifikator | Verifikasi independen | Verifikator, koperasi |
| Keberatan dan keputusannya | Petani | Koperasi atas nama petani | Hak membantah keputusan otomatis | Koperasi, verifikator |
| Akun (nama pengguna, peran, hash kata sandi) | Petugas | Pendaftaran akun | Kendali akses | Admin |
| Riwayat perubahan (siapa, kapan, apa) | Petugas | Otomatis | Akuntabilitas | Koperasi, pabrik, verifikator |

**Dasar pemrosesan.** Persetujuan eksplisit petani (Pasal 20 ayat (2) huruf a): paspor tidak bisa dibuat tanpa centang
persetujuan, dan waktu persetujuan dicatat (`Farmer.consent_given`, `consent_at`). Untuk pabrik dan eksportir, pemrosesan
juga diperlukan untuk memenuhi kewajiban uji tuntas pembelinya.

**Alur data ke luar sistem.**

| Tujuan | Yang dikirim | Yang TIDAK dikirim |
|---|---|---|
| Importir Uni Eropa (paket ekspor ZIP) | Poligon kebun, kode kebun, desa, luas, volume, jenis bukti lahan, status STDB | Nama petani, nama saksi, nomor surat, foto |
| Publik (cek paspor lewat QR) | Kode, nama tersamar, desa, luas, status | Lokasi dan batas kebun, nama lengkap, transaksi |
| Layanan peta (Esri, Global Forest Watch, Kemenhut) | Permintaan potongan peta di sekitar kebun | Nama, kode kebun, atau data lain. Lokasi yang diminta bisa disimpulkan oleh penyedia peta |

Paket ekspor dan permintaan potongan peta keluar dari Indonesia. Poligon kebun tanpa nama masih bisa mengarah ke orang
tertentu bila digabung dengan data lain, jadi keduanya diperlakukan sebagai transfer data pribadi ke luar negeri
(UU PDP Pasal 56; PP 33/2026 Pasal 160-166): petani diberi tahu di formulir persetujuan, dan Uni Eropa memiliki tingkat
pelindungan yang setara atau lebih tinggi (GDPR).

## 3. Kebutuhan dan proporsionalitas

| Pertanyaan | Jawaban |
|---|---|
| Apakah geolokasi kebun benar-benar perlu? | Ya. EUDR mewajibkan geolokasi setiap kebun asal; tanpa itu TBS petani tidak bisa dijual ke rantai ekspor |
| Apakah nama petani perlu ikut ke pembeli? | Tidak, dan tidak dikirim. `ProducerName` di format TRACES opsional, sehingga paket hanya memuat kode kebun |
| Apakah NIK/KTP perlu? | Tidak. Aplikasi tidak punya kolom NIK |
| Apakah sertifikat tanah wajib? | Tidak. Bukti bertingkat (sertifikat, surat desa, atau pernyataan + 2 saksi) supaya petani tanpa sertifikat tidak tersingkir |
| Apakah keputusan boleh sepenuhnya otomatis? | Tidak. Lihat bagian 5: verifikator manusia, keberatan, dan dua peta hutan sebelum vonis Berisiko |
| Berapa lama data disimpan? | EUDR meminta catatan uji tuntas disimpan 5 tahun. Usulan: 5 tahun sejak transaksi terakhir, lalu dihapus atau dianonimkan. **Belum diterapkan di kode** (bagian 6) |

## 4. Risiko terhadap petani dan pihak lain

Skala: kemungkinan dan dampak rendah / sedang / tinggi, dinilai sebelum langkah pelindungan.

| # | Risiko | Kemungkinan | Dampak | Langkah pelindungan yang sudah ada | Sisa risiko |
|---|---|---|---|---|---|
| 1 | Petani patuh divonis Berisiko karena peta salah (positif palsu), lalu TBS-nya ditolak | Sedang (peta JRC keliru di ~18% kelas hutan) | Tinggi (kehilangan pasar) | Dua peta hutan harus sepakat; pembeda peremajaan; hasil ragu = Perlu cek + inspeksi lapangan; keberatan diputus manusia dengan alasan tertulis; semua bukti dan sumbernya tampil di paspor | Sedang |
| 2 | Lokasi dan luas kebun dipakai pihak lain (pajak, penertiban kawasan, makelar tanah) | Sedang | Tinggi | Akses per peran; publik tidak melihat lokasi; paket ekspor tanpa nama; persetujuan eksplisit | Sedang |
| 3 | Kebocoran basis data (nama + lokasi + transaksi) | Rendah-sedang | Tinggi | Kata sandi PBKDF2 210.000 iterasi; cookie HttpOnly bertanda tangan; CSRF; CSP; batas laju; rahasia di `.env`; tanpa NIK | Sedang (lihat bagian 6: enkripsi basis data) |
| 4 | Data diubah diam-diam untuk meloloskan kebun atau menjatuhkan petani | Rendah | Tinggi | Riwayat perubahan berantai hash SHA-256, bisa diperiksa siapa saja yang berwenang (`/api/audit/verify`) | Rendah |
| 5 | Pengepul memakai paspor petani untuk mencuci TBS; petani ikut dicurigai | Sedang | Sedang | Batas kapasitas kebun 30 hari, rotasi panen, deteksi anomali pengepul dengan alasan; yang diaudit adalah pengepul, bukan petani | Rendah |
| 6 | Petani menyetujui tanpa paham (literasi digital rendah) | Tinggi | Sedang | Persetujuan dijelaskan petugas koperasi dalam bahasa sederhana; kartu cetak untuk petani tanpa ponsel | Sedang (perlu lembar persetujuan cetak) |
| 7 | Saksi batas dicatat tanpa tahu | Sedang | Rendah | Hanya nama dan hubungan; tidak tampil ke publik maupun paket ekspor | Rendah |
| 8 | Foto inspeksi memuat wajah atau metadata lokasi | Sedang | Rendah | Foto di-encode ulang, EXIF dibuang; jenis dan ukuran dibatasi | Rendah |
| 9 | Skor anomali salah menuduh pengepul | Sedang | Sedang | Skor hanya mengurutkan prioritas audit dan selalu disertai alasan; tidak ada sanksi otomatis | Rendah |

## 5. Keputusan otomatis dan campur tangan manusia

Petani berhak tidak tunduk pada keputusan yang semata-mata otomatis dan berhak mengajukan keberatan. Di aplikasi:

- Status satelit adalah **penilaian risiko**, bukan sanksi. Kebun yang ragu masuk "Perlu cek", bukan "Berisiko".
- Vonis Berisiko karena deforestasi butuh dua peta hutan independen yang sepakat; bila tidak sepakat, kebun wajib
  diperiksa verifikator di lapangan.
- Petani (lewat koperasi) bisa mengajukan **keberatan** dengan bukti; verifikator independen memutus dengan alasan
  tertulis dan keputusannya mengganti status otomatis (`status_override`).
- Setiap paspor menampilkan bukti, sumber data, aturan yang dipakai, dan tingkat keyakinan. Halaman *Cara kerja AI*
  menjelaskan algoritma, akurasi, dan batasannya.
- Transaksi yang ditahan di pengepul menampilkan alasannya; pengepul dan koperasi bisa menindaklanjuti.

## 6. Kekurangan yang diketahui dan rencana perbaikan

Bagian ini sengaja jujur: hal berikut **belum ada di kode** dan harus selesai sebelum memproses data petani sungguhan.

| Kekurangan | Risiko terkait | Rencana |
|---|---|---|
| Belum ada fitur tarik persetujuan, hapus data, atau unduh data per petani | Hak subjek data (UU PDP Pasal 5-13) | Endpoint dan tombol di halaman koperasi; riwayat perubahan tetap menyimpan jejak tanpa data pribadi |
| Belum ada masa retensi otomatis | Penyimpanan berlebih | Tugas terjadwal: anonimkan 5 tahun setelah transaksi terakhir |
| Basis data SQLite tidak dienkripsi saat disimpan | #3 | PostgreSQL terkelola dengan enkripsi dan cadangan terenkripsi |
| Semua pengguna terdaftar melihat nama petani dan batas kebun | #2 | Pengepul cukup melihat kode, status, dan sisa kapasitas; pabrik cukup kode dan status |
| Potongan peta dimuat langsung dari Esri/GFW oleh browser | Lokasi bisa disimpulkan penyedia peta | Perantara potongan peta di server sendiri dengan cache |
| Belum ada prosedur insiden tertulis yang diuji | Pemberitahuan 3 x 24 jam (PP 33/2026 Pasal 114) | Lihat `KEBIJAKAN_PRIVASI.md` bagian 8; latihan sebelum pilot |
| Belum ada pejabat pelindungan data | PP 33/2026 Pasal 142-147 (wajib bila pemantauan sistematis skala besar) | Ditunjuk oleh pengendali (koperasi/pabrik) saat pilot; untuk hackathon, narahubungnya tim pengembang |
| Lembar persetujuan cetak belum ada | #6 | Satu halaman, bahasa sederhana, dibacakan petugas |

## 7. Kesimpulan

Pemrosesan ini berisiko tinggi menurut Pasal 34, tetapi perlu dan proporsional untuk tujuannya: tanpa geolokasi dan bukti,
petani swadaya kehilangan akses pasar. Risiko terbesar bagi petani bukan kebocoran data, melainkan **vonis otomatis yang
salah**; karena itu pelindungan utama ada di rancangan keputusan (dua peta hutan, Perlu cek, verifikator, keberatan).
Dengan kekurangan di bagian 6, aplikasi **belum layak** memproses data petani sungguhan; layak untuk demo dengan data fiktif.

## Rujukan

- UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi, Pasal 34: https://pasal.id/peraturan/uu/uu-no-27-tahun-2022/pasal-34
- PP No. 33 Tahun 2026 (ringkasan Veritask; teks resmi perlu dirujuk sebelum pilot): https://veritask.ai/id/artikel/pengaturan-teknis-pelindungan-data-pribadi-dan-kewajiban-pengendali-serta-prosesor-akhirnya-terbit-lewat-pp-33-2026
- Rekomendasi EUDR untuk Indonesia, Zero Deforestation Hub (persetujuan tertulis, ID anonim, simpan catatan 5 tahun): https://zerodeforestationhub.eu/wp-content/uploads/2026/02/FINAL-EUDR-Recommendations-IDN.pdf
- Format GeoJSON TRACES v1.3 (`ProducerName` opsional): https://eudr.webcloud.ec.europa.eu/tracesnt/help/eudr-documentation/operator/geojson-description.html
