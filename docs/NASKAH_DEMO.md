# Naskah video demo (3–5 menit, tanpa suara presentasi)

Aturan guidebook: video menunjukkan alur dan cara kerja produk, termasuk fitur AI, **tanpa narasi**. Jadi cerita disampaikan
lewat teks layar singkat (caption) dan aksi di aplikasi. Rekam layar 1440×900, perbesar kursor, beri jeda 1–2 detik setelah
setiap hasil muncul.

Sebelum merekam: hapus `backend/data` lalu jalankan `start.bat` agar data demo bersih. Pastikan internet aktif (citra satelit).

| Waktu | Layar | Caption |
|---|---|---|
| 0:00–0:20 | Beranda | "30 Des 2026: Eropa hanya membeli sawit yang terbukti bebas deforestasi." lalu "Baru 7% kebun sawit rakyat siap." |
| 0:20–0:35 | Beranda, sorot paspor contoh | "PasporKebun: satu paspor untuk setiap kebun petani." |
| 0:35–1:20 | Peta kebun → Daftarkan kebun → klik di tengah kebun nyata | "Petani menunjuk kebunnya. AI menggambar batas dari citra satelit." Tunjukkan model, keyakinan, waktu proses. Geser satu titik. |
| 1:20–1:45 | Isi form, pilih skenario "Hutan dibuka 2022", centang persetujuan, simpan | "Satelit memeriksa riwayat lahan sejak 2018." Cap BERISIKO jatuh. |
| (opsional) | Daftarkan kebun di lokasi nyata yang masuk kawasan hutan, nyalakan lapisan "Kawasan hutan (peta Kemenhut)" | "AI juga mengecek peta resmi Kemenhut: kebun ini 60% di Hutan Lindung." Uji lokasinya dulu sehari sebelumnya agar tersimpan di cache. |
| 1:45–2:15 | Scroll paspor: bukti satelit + grafik NDVI | "AI menemukan hutan dibuka Juni 2022, setelah batas EUDR." Arahkan kursor ke titik merah di grafik. |
| 2:15–2:40 | Buka kebun Sutrisno (PK-00003-P) | "Peremajaan sawit 2023 bukan deforestasi. Petani PSR tetap aman." |
| 2:40–3:00 | Paspor Pak Budi (PK-00001-F): QR + unduh GeoJSON EUDR | "QR hanya berisi kode. Tanpa NIK, tanpa data pribadi." |
| 3:00–3:30 | Pengepul → pindai PK-00001-F → 1.100 kg → Diterima | "Pengepul memindai paspor setiap membeli TBS." |
| 3:30–3:55 | Ganti pengepul "UD Sinar Jaya" → PK-00001-F → 9.000 kg → Ditahan | "9 ton dari kebun 2 ha? Mustahil. TBS dari luar ditahan." |
| 3:55–4:30 | Pabrik: KPI, grafik bulanan, tabel pengepul | "Pabrik melihat asal setiap TBS." Sorot UD Sinar Jaya skor tinggi dan alasannya. |
| 4:30–4:50 | Cara kerja AI | "4 model AI, akurasi dan batasannya terbuka. Semua jalan di CPU." |
| 4:50–5:00 | Logo + nama tim | "PasporKebun. Sawit petani jujur jangan ikut tertolak." |

# Kerangka pitching final (7 menit termasuk live demo)

1. **Masalah (1 menit).** Tenggat EUDR, 7% siap, Tesso Nilo. Akar masalah: petani tanpa peta + pengepul titik buta.
2. **Live demo (4 menit).** Alur sama seperti video: daftarkan kebun → cap → pengepul diterima/ditahan → dasbor pabrik.
3. **Teknologi (1 menit).** Kenapa COLD (F1 tertinggi), kenapa convergence of evidence (cara FAO), kenapa Isolation Forest
   (tidak butuh label kecurangan). Tunjukkan halaman Cara kerja AI.
4. **Realisasi & dampak (1 menit).** Pilot: 1 koperasi (±100 kebun) + 1 pabrik. Pembayar: pabrik/eksportir (wajib tertelusur
   sebelum tenggat), petani gratis. Metrik: % kebun siap EUDR (baseline 7%), % TBS tertelusur, ton TBS ditahan.

## Pertanyaan juri yang perlu disiapkan

- *Apa bedanya dengan Koltiva / e-STDB?* Mereka memetakan kebun; kami menambah penjaga di titik pengepul (celah yang diakui
  Koltiva sendiri) dan pembeda peremajaan vs deforestasi.
- *Bagaimana jika pengepul tidak mau memindai?* Pabrik menimbang setoran; selisih setoran vs transaksi tertelusur terlihat di
  dasbor dan menaikkan skor anomali pengepul itu.
- *Akurasinya diuji dengan data nyata?* Validasi saat ini pada data simulasi berlabel; algoritma mengikuti metode yang sudah
  divalidasi di literatur (angka di halaman Cara kerja AI). Pilot akan memakai titik referensi lapangan.
- *Status hutan lindung dari mana?* Dicek otomatis ke peta Kawasan Hutan resmi Kemenhut (SIGAP) saat kebun digambar.
  Peta resmi bisa tertinggal dari SK pelepasan terbaru, jadi hasil "masuk kawasan" diverifikasi dengan sertifikat/SK, bukan
  vonis.
- *Bagaimana jika petani mengaku kebun orang lain?* Batas wajib disaksikan ketua poktan/tetangga; tumpang tindih otomatis
  terdeteksi dan diselesaikan lewat musyawarah.
