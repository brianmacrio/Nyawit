# Kebijakan privasi PasporKebun

Berlaku untuk aplikasi PasporKebun versi 1.1 (14 November 2026). Ditulis untuk dibacakan petugas koperasi kepada petani,
jadi bahasanya sengaja sederhana. Penilaian risikonya ada di [`DPIA.md`](DPIA.md).

> Versi demo hanya berisi data fiktif. Kebijakan ini menjelaskan cara aplikasi memperlakukan data bila dipakai sungguhan,
> dan menandai dengan jujur bagian yang belum selesai.

## 1. Siapa yang bertanggung jawab

- **Pengendali data**: koperasi (atau pabrik pembina) yang mendaftarkan kebun Bapak/Ibu.
- **Prosesor**: penyelenggara aplikasi PasporKebun, yang hanya memproses data atas perintah pengendali.
- **Narahubung**: pengurus koperasi tempat Bapak/Ibu terdaftar. Untuk versi lomba: tim pengembang (lihat `README.md`).

## 2. Data apa yang dicatat

| Yang dicatat | Yang TIDAK dicatat |
|---|---|
| Nama dan desa petani | NIK, KTP, KK, nomor telepon, nomor rekening |
| Batas kebun, titik GPS, luas, tahun tanam | Alamat rumah |
| Jenis dan nomor bukti lahan, status STDB, ada tidaknya sengketa | Salinan atau foto sertifikat |
| Nama saksi batas dan hubungannya | Data lain tentang saksi |
| Penjualan TBS: berat, waktu, pengepul | Harga dan pembayaran |
| Hasil kunjungan verifikator dan foto kebun | Foto wajah (foto diminta hanya kebun; metadata foto dibuang) |

## 3. Untuk apa

1. Membuktikan kebun legal dan tidak membuka hutan setelah 31 Desember 2020, supaya TBS tetap bisa dijual ke pabrik yang
   memasok pasar ekspor.
2. Mencegah TBS dari kebun lain memakai nama kebun Bapak/Ibu.
3. Menyiapkan data yang juga diminta untuk STDB dan ISPO.

Data tidak dipakai untuk iklan, tidak dijual, dan tidak dipakai menilai kelayakan pinjaman tanpa persetujuan baru.

## 4. Dasar pemrosesan: persetujuan

Paspor kebun hanya dibuat setelah Bapak/Ibu menyetujui. Petugas mencentang persetujuan di depan Bapak/Ibu dan aplikasi
mencatat waktunya. Menolak adalah hak; akibatnya kebun tidak punya paspor dan pabrik mungkin tidak bisa memasukkan TBS-nya
ke pengiriman ekspor.

## 5. Siapa yang bisa melihat

| Pihak | Yang terlihat |
|---|---|
| Koperasi | Semua data kebun anggotanya |
| Verifikator independen | Data kebun yang diperiksa, bukti lahan, keberatan |
| Pengepul | Status paspor dan sisa kapasitas saat memindai kartu QR; transaksinya sendiri |
| Pabrik | Status kebun, volume, jenis bukti lahan (bukan nomornya) |
| Pembeli di luar negeri | Batas kebun, kode kebun, desa, luas, volume. **Tanpa nama** |
| Siapa pun yang memindai QR | Kode, nama tersamar, desa, luas, status. **Tanpa lokasi** |

Catatan jujur: pada versi 1.1, semua pengguna terdaftar masih bisa membuka nama dan batas kebun lewat halaman peta.
Pembatasan per peran yang lebih ketat masuk rencana perbaikan (DPIA bagian 6).

## 6. Keputusan oleh komputer

Aplikasi memberi status Aman, Perlu cek, atau Berisiko dari peta dan citra satelit. Peta bisa salah. Karena itu:

- kebun hanya disebut Berisiko karena membuka hutan bila dua peta hutan yang berbeda sepakat;
- bila ragu, statusnya Perlu cek dan verifikator datang ke kebun;
- Bapak/Ibu boleh **mengajukan keberatan** lewat koperasi dengan foto atau surat; yang memutuskan adalah orang
  (verifikator), dengan alasan tertulis;
- semua bukti dan sumbernya bisa dilihat di paspor.

## 7. Hak Bapak/Ibu

Sesuai UU No. 27 Tahun 2022: mendapat penjelasan, melihat dan menyalin data sendiri, memperbaiki data yang salah, menarik
persetujuan, meminta data dihapus, dan mengajukan keberatan atas keputusan otomatis. Sampaikan ke pengurus koperasi.

| Hak | Cara di versi 1.1 |
|---|---|
| Melihat data sendiri | Koperasi membuka paspor; kartu cetak dan QR untuk petani |
| Memperbaiki data | Koperasi mengubah data kebun; perubahan tercatat di riwayat |
| Keberatan atas status | Tersedia di aplikasi (menu Verifikasi) |
| Menarik persetujuan, menghapus data, menyalin semua data | **Belum ada tombolnya.** Dilayani manual oleh pengelola basis data; fitur masuk rencana perbaikan |

## 8. Keamanan dan bila terjadi kebocoran

Pengamanan: masuk dengan akun per peran, kata sandi disimpan sebagai hash, sambungan HTTPS saat di-deploy, pembatasan
percobaan masuk, dan riwayat perubahan yang tidak bisa diubah diam-diam.

Bila data bocor atau diakses tanpa hak:

1. Pengelola menutup akses yang bocor dan mengganti kunci (`PK_SECRET_KEY`), sehingga semua sesi lama gugur.
2. Pengelola memeriksa riwayat perubahan (`/api/audit/verify`) untuk melihat apa yang terdampak.
3. Pengendali memberi tahu petani yang terdampak dan lembaga pelindungan data secara tertulis **paling lambat 3 x 24 jam**
   sejak kebocoran diketahui: data apa, kapan dan bagaimana, dan apa yang sudah dilakukan.
4. Kejadian dicatat, lalu DPIA ditinjau ulang.

## 9. Berapa lama disimpan

Catatan uji tuntas disimpan 5 tahun sejak penjualan terakhir karena diminta aturan ekspor, lalu dihapus atau dijadikan
anonim. Penghapusan otomatis belum ada di versi 1.1.

## 10. Layanan pihak lain

Untuk menampilkan peta, aplikasi meminta potongan citra dan peta di sekitar kebun ke Esri, Global Forest Watch, dan
Kementerian Kehutanan. Nama dan kode kebun tidak ikut dikirim, tetapi penyedia peta bisa mengetahui lokasi yang diminta.
Server dua layanan pertama berada di luar Indonesia.

## 11. Perubahan kebijakan

Perubahan dicatat di riwayat Git berkas ini. Perubahan tujuan atau penerima data membutuhkan persetujuan baru dari petani.
