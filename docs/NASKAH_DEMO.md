# Naskah video demo (3:00–5:00) dan pitching final

## Aturan video dari guidebook (yang memengaruhi cara merekam)

- Durasi **minimal 3:00, maksimal 5:00**. Unggah ke YouTube (Unlisted/Public), jangan dihapus sampai pengumuman akhir.
- Rekam **aplikasi yang benar-benar berjalan dari commit final**, lewat browser. Dilarang memakai slide, mockup, Figma,
  animasi, atau hasil rekayasa sebagai pengganti demonstrasi.
- Urutan wajib: (1) tampilan awal dan identitas aplikasi, (2) alur fitur utama dari input, proses, sampai output,
  (3) pembuktian fungsi utama, (4) proses dan hasil AI secara langsung.
- Rekaman utuh dan berkesinambungan. Boleh memotong waktu tunggu dan menambah teks/musik, tapi tidak boleh mengubah hasil.
- Narasi boleh ada boleh tidak. Naskah ini memakai caption singkat.

**Soal data simulasi.** Di mode demo, deret NDVI per kebun adalah simulasi berlabel (aplikasi menuliskannya di paspor).
Proses AI-nya nyata, tetapi agar tidak dianggap "simulasi hasil", lakukan dua hal: (a) tampilkan caption "mode demo: deret
NDVI simulasi berlabel; citra, peta kawasan, dan semua perhitungan berjalan sungguhan", dan (b) bila `check_live` berhasil
di laptop, rekam satu kebun nyata dengan `PK_SATELLITE_MODE=live`.

Persiapan: hapus `backend/data`, jalankan `start.bat`, pastikan internet aktif (citra & peta kawasan). Rekam 1440x900,
perbesar kursor, jeda 1-2 detik setelah setiap hasil muncul.

| Waktu | Layar dan aksi | Caption |
|---|---|---|
| 0:00–0:15 | **Beranda**: judul, paspor contoh, langkah empat pihak | "PasporKebun: paspor digital kebun sawit rakyat untuk EUDR." |
| 0:15–0:25 | **Masuk** → klik kartu "Petugas koperasi" | "Setiap peran punya akun sendiri." |
| 0:25–1:15 | **Peta kebun** → Daftarkan kebun → "Saya sedang di kebun" (di laptop: simulasikan posisi) → draf AI muncul; tunjukkan model, keyakinan, waktu proses | "Petugas berdiri di kebun. GPS mencatat titik, AI menggambar batas dari citra satelit." |
| 1:15–1:45 | Isi batas tiap sisi, 2 saksi, bukti lahan "Surat desa", STDB "Sedang diurus"; skenario "Hutan dibuka 2022"; setuju; Simpan | "Tidak perlu membaca citra: cukup sebutkan parit, jalan, dan tetangga di tiap sisi." |
| 1:45–2:20 | Paspor: cap BERISIKO, checklist Siap EUDR (syarat yang gagal), bukti satelit, grafik NDVI dengan garis merah | "AI membaca riwayat sejak 2018: hutan dibuka 2022, setelah batas EUDR." |
| 2:20–2:40 | Buka kebun Sutrisno (PK-00003-P) | "Peremajaan sawit 2023 bukan deforestasi. Petani PSR tetap aman." |
| 2:40–3:20 | Masuk sebagai pengepul **UD Sinar Jaya** → ketik PK-00001-F → 9.000 kg → **Ditahan** | "9 ton dari kebun 2 ha? Mustahil. TBS dari luar ditahan di titik pengepul." |
| 3:20–3:50 | Masuk sebagai **verifikator** → Inspeksi lapangan → isi satu hasil + foto → tab Keberatan (Joko Susilo) → tab Integritas | "Verifikator independen memeriksa sampel kebun; riwayat tidak bisa diubah diam-diam." |
| 3:50–4:30 | Masuk sebagai **pabrik** → tabel pengepul (UD Sinar Jaya skor tertinggi + alasan) → Buat paket ekspor → angka masuk/dipisahkan → unduh ZIP | "Pabrik hanya mengirim TBS dari kebun Siap EUDR, lengkap dengan bukti untuk importir." |
| 4:30–4:50 | **Cara kerja AI**: akurasi, batasan, keamanan | "Akurasi dan batasan AI dibuka; semua berjalan di CPU." |
| 4:50–5:00 | **Cek paspor publik** /cek/PK-00001-F | "Siapa pun bisa mengecek paspor. Nama petani disamarkan." |

Batas kawasan hutan di peta (garis putus-putus kuning = hutan produksi, merah = taman nasional) adalah data resmi, bukan
gambar: salinan Peta Kawasan Hutan KLHK 2017 untuk area demo, ditambah lapisan "Kawasan hutan KLHK 2017 (otomatis, GFW)"
yang muncul sendiri di mana pun peta digeser (zoom 12+). Momen yang bagus untuk kamera: kebun **Rina Wati (PK-00005-Z)**
berada di Hutan Produksi, tepat di seberang garis kuning dari kebun tetangganya.

(Opsional) Geser peta ke barat laut sampai TN Tesso Nilo, daftarkan kebun di dalamnya: paspor langsung menulis "masuk
Kawasan konservasi" dan menyebut sumber petanya. Uji sehari sebelumnya agar tile peta tersimpan di cache.

# Babak final (15 menit per tim)

Rincian slot: 1 menit persiapan laptop dan verifikasi localhost, **7 menit presentasi + live demo**, 3 menit tanya jawab,
4 menit penilaian. Aplikasi wajib jalan di localhost pada laptop yang dibawa.

1. **Masalah (1 menit).** Tenggat EUDR, 7% siap, Tesso Nilo. Akar masalah: petani tanpa bukti kebun + pengepul titik buta.
2. **Live demo (4 menit).** Koperasi daftarkan kebun → cap & checklist → pengepul ditahan → verifikator → paket ekspor pabrik.
   Siapkan akun demo di tab terpisah agar perpindahan peran cepat.
3. **Teknologi (1 menit).** Kenapa COLD (F1 tertinggi), convergence of evidence (cara FAO), Isolation Forest (tanpa label
   kecurangan), sampel verifikasi berbasis risiko (rumus RSPO). Sorot: AI dipakai di tempat yang tidak bisa dikerjakan saksi.
4. **Realisasi & dampak (1 menit).** Pengguna utama petugas koperasi; pembayar pabrik/eksportir (wajib membuktikan asal TBS);
   petani gratis dan mendapat peta untuk STDB/ISPO. Pilot: 1 koperasi (±100 kebun) + 1 pabrik. Metrik: % kebun Siap EUDR
   (baseline 7%), % TBS tertelusur, ton TBS ditahan, biaya pemetaan per ha dibanding Rp415.000/ha.

## Pertanyaan juri yang perlu disiapkan

- *Apakah paspor ini sertifikat?* Bukan. Sertifikat ISPO/RSPO hanya dari lembaga terakreditasi KAN/ASI. Paspor adalah bukti
  uji tuntas dan sistem kendali internal koperasi yang membuat sertifikasi kelompok dan laporan EUDR lebih murah.
- *Apakah petani harus punya sertifikat tanah?* Tidak. ISPO (Permentan 33/2025) menerima surat penguasaan fisik; pedoman EUDR
  hanya meminta dokumen yang diwajibkan hukum setempat. Kami memakai tingkat bukti dan saksi tetangga.
- *Bagaimana petani tahu batas kebun dari citra satelit?* Tidak perlu membaca citra: GPS saat berdiri di kebun, AI membuat
  draf, petani cukup menyebut apa yang ada di tiap sisi, dan tetangga menjadi saksi. EUDR cukup satu titik untuk kebun < 4 ha.
- *Apa keunggulan AI kalau tetap butuh saksi?* Saksi menjawab "milik siapa". AI menjawab hal yang tidak bisa dijawab saksi:
  riwayat lahan sejak 2018, status kawasan hutan, ribuan transaksi pengepul, dan kebun mana yang perlu didatangi.
- *Siapa yang membayar?* Pabrik/eksportir, karena merekalah yang harus membuktikan asal buah. Petani gratis.
- *Bagaimana jika pengepul tidak mau memindai?* Pabrik menimbang setoran; selisih setoran vs transaksi tertelusur terlihat di
  dasbor dan menaikkan skor anomali pengepul itu. Paket ekspor juga memisahkan TBS yang tidak tertelusur.
- *Akurasinya diuji dengan data nyata?* Validasi saat ini pada data simulasi berlabel; algoritma mengikuti metode yang sudah
  divalidasi di literatur. Pilot akan memakai titik referensi lapangan dari inspeksi verifikator.
- *Batas kawasan hutan itu digambar sendiri?* Tidak. Sumber utama peta Kawasan Hutan Kemenhut; bila servernya mati (seperti
  12 Nov 2026), aplikasi otomatis memakai Peta Kawasan Hutan KLHK 2017 dari Global Forest Watch, dan paspor menyebut sumbernya.
  Satelit tidak bisa melihat status hukum lahan; yang dilihat satelit adalah tutupan pohon dan riwayatnya.
- *Status hutan lindung dari mana?* Peta Kawasan Hutan resmi Kemenhut (SIGAP), dicek otomatis saat kebun digambar. Peta resmi
  bisa tertinggal dari SK pelepasan terbaru, jadi petani bisa mengajukan keberatan dengan bukti.
