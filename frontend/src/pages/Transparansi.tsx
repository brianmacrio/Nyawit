import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Meta } from "../lib/types";
import { Notice } from "../components/ui";

const MODELS = [
  {
    name: "AI penggambar batas kebun",
    rows: [
      ["Fungsinya", "Dari satu klik di tengah kebun, membuat draf garis batas dari citra satelit."],
      ["Data", "Citra satelit resolusi sangat tinggi (Esri World Imagery). Hanya 9 petak citra di sekitar klik yang diunduh, lalu disimpan di cache."],
      ["Algoritma", "Watershed berpenanda (OpenCV) setelah penghalusan mean-shift. Jika dipasang, memakai Segment Anything (SAM, Meta AI)."],
      ["Akurasi", "Validasi kami pada citra sintetis: IoU rata-rata 0,93. Literatur: SAM tanpa pelatihan pada lahan petani kecil di India, IoU 0,71 dan F1 0,82."],
      ["Batasannya", "Dua kebun bertetangga dengan umur dan perawatan sama bisa terlihat seperti satu kebun. Bayangan awan mengganggu."],
      ["Peran manusia", "Garis AI selalu draf. Petani menggeser titik yang meleset, lalu ketua kelompok tani atau tetangga menjadi saksi."],
    ],
  },
  {
    name: "Pendeteksi perubahan lahan 5+ tahun (COLD-lite)",
    rows: [
      ["Fungsinya", "Membaca riwayat kehijauan (NDVI) kebun sejak 2018, menemukan kapan lahan dibuka, dan memperkirakan tahun tanam."],
      ["Data", "Sentinel-2 L2A (10 m, tiap 5 hari) dari Microsoft Planetary Computer pada mode live. Pada mode demo, deret simulasi berlabel."],
      ["Algoritma", "Regresi harmonik robust (tren + musim). Perubahan baru diakui jika 5 citra berturut-turut menyimpang, sehingga awan tunggal tidak dianggap pembukaan lahan. Diadaptasi dari CCDC/COLD."],
      ["Akurasi", "Literatur (Landsat, 2025): COLD F1 81,8%, CCDC sekitar 76,5%, BFAST 70,6%; karena itu kami memilih pendekatan COLD. Validasi simulasi kami: F1 100%, uji ketahanan (derau 2,5x, separuh citra hilang) F1 99%, tahun tanam tepat ±1 tahun 98%."],
      ["Batasannya", "NDVI saja sulit membedakan hutan dan sawit tua. Musim hujan berawan mengurangi jumlah citra."],
      ["Peran manusia", "Hasil 'perlu cek' diteruskan ke verifikasi lapangan (foto bergeotag) atau citra resolusi lebih tinggi."],
    ],
  },
  {
    name: "Mesin keputusan multi-bukti",
    rows: [
      ["Fungsinya", "Menggabungkan beberapa sumber bukti menjadi status Aman, Perlu cek, atau Berisiko beserta alasannya."],
      ["Data", "Peta tutupan hutan 2020 JRC (akurasi 91%), kehilangan tutupan Hansen/GLAD, peringatan radar RADD (user's accuracy 97,6%), peta sawit Forest Data Partnership/Descals, kawasan hutan, dan time series di atas."],
      ["Algoritma", "Aturan 'convergence of evidence' dari Whisp (FAO), ditambah pembeda peremajaan dan deforestasi: lahan yang tahun 2020 sudah kebun sawit lalu dibuka lagi adalah peremajaan (mis. PSR), bukan deforestasi."],
      ["Transparansi", "Aturannya terbuka di kode (evidence.py). Setiap paspor menampilkan bukti, sumber, dan tingkat keyakinan."],
      ["Batasannya", "Peta global kurang tajam untuk kebun di bawah 1 ha. Status legalitas lahan butuh peta kawasan resmi."],
    ],
  },
  {
    name: "Penjaga titik pengepul",
    rows: [
      ["Fungsinya", "Menahan pembelian yang mustahil secara agronomi, dan mengurutkan pengepul yang paling layak diaudit."],
      ["Data", "Luas kebun, umur tanaman, kurva potensi produksi PPKS, pola musim panen, dan transaksi 90 hari."],
      ["Algoritma", "Aturan kapasitas 30 hari dan rotasi panen, ditambah Isolation Forest (tanpa label kecurangan) untuk pola pengepul. Alasan dijelaskan dengan z-score per fitur."],
      ["Prinsip", "Batas kapasitas sengaja dilonggarkan 15% di atas potensi terbaik: lebih baik melewatkan sedikit kecurangan daripada menuduh petani jujur. Skor anomali bukan vonis, hanya urutan audit."],
    ],
  },
];

export default function Transparansi() {
  const [meta, setMeta] = useState<Meta | null>(null);
  useEffect(() => {
    api.meta().then(setMeta).catch(() => setMeta(null));
  }, []);

  return (
    <div className="page doc">
      <div className="page-head">
        <div>
          <h1>Cara kerja AI</h1>
          <p className="muted">Apa yang dikerjakan AI di PasporKebun, seberapa akurat, di mana batasnya, dan di mana manusia tetap memutuskan.</p>
        </div>
      </div>

      {meta && (
        <Notice kind={meta.satellite_mode === "live" ? "ok" : "info"}>
          Mode data satelit: <strong>{meta.satellite_mode === "live" ? "live (Sentinel-2 dan Hansen asli)" : "demo (simulasi berlabel)"}</strong>.
          AI batas kebun: <strong>{meta.sam.available ? "Segment Anything" : "watershed bawaan"}</strong>
          {meta.sam.available ? "" : ` (${meta.sam.reason})`}. Batas EUDR: deforestasi setelah 31 Des 2020.
        </Notice>
      )}

      <section className="panel" style={{ marginTop: 16 }}>
        {MODELS.map((m) => (
          <article className="model" key={m.name}>
            <h2 style={{ fontSize: 19 }}>{m.name}</h2>
            <dl>
              {m.rows.map(([k, v]) => (
                <div key={k} style={{ display: "contents" }}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          </article>
        ))}
      </section>

      <div className="grid-2" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <section className="panel panel-pad">
          <h2 style={{ fontSize: 18, marginBottom: 10 }}>Perlindungan data petani</h2>
          <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 8 }}>
            <li>NIK, foto KTP, dan foto wajah tidak disimpan. QR hanya berisi kode paspor.</li>
            <li>Paspor baru terbit setelah petani menyetujui berbagi data, dan waktu persetujuannya tercatat.</li>
            <li>Berkas EUDR menyembunyikan nama petani yang belum memberi persetujuan.</li>
            <li>Data tersimpan di server koperasi sendiri (SQLite), bukan di layanan pihak ketiga.</li>
            <li>Pemindaian QR dengan kamera diproses di browser; gambar kamera tidak dikirim ke server.</li>
          </ul>
        </section>
        <section className="panel panel-pad">
          <h2 style={{ fontSize: 18, marginBottom: 10 }}>Hemat sumber daya</h2>
          <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 8 }}>
            <li>Semua model berjalan di CPU laptop biasa, tanpa GPU. Analisis satu kebun sekitar 25 ms.</li>
            <li>Hanya piksel di dalam batas kebun yang diolah, bukan seluruh citra satelit.</li>
            <li>Citra dan time series disimpan di cache, jadi setiap kebun cukup diunduh sekali.</li>
            <li>Respons API dikompresi; grafik dibuat dengan SVG ringan tanpa pustaka grafik besar.</li>
            <li>Huruf dan ikon dibundel di aplikasi, tanpa memanggil CDN saat dipakai.</li>
          </ul>
        </section>
      </div>
      <p className="small faint" style={{ marginTop: 16 }}>
        Rincian validasi: docs/VALIDASI.md. Rincian algoritma dan sumber: docs/ALGORITMA.md.
      </p>
    </div>
  );
}
