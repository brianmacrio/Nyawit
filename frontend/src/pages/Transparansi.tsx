import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { riskLabel } from "../lib/format";
import type { IndicatorTest, Meta } from "../lib/types";
import { Notice, Spinner } from "../components/ui";

const INDICATORS: [string, string][] = [
  ["1", "Kehilangan tutupan pohon 2021–2025 (GFW)"],
  ["2", "Kawasan hutan KLHK 2017 (GFW)"],
  ["3", "Kawasan hutan (peta Kemenhut)"],
];

function indicatorText(t: IndicatorTest, k: string): string {
  const i = t.indicators;
  if (k === "1" && i["1"]) {
    const yrs = Object.entries(i["1"].by_year).map(([y, v]) => `${y}: ${Math.round(v)}%`).join(", ");
    const nat = i["1"].natural_forest_2020_pct;
    return `${Math.round(i["1"].loss_after_pct)}% hilang${yrs ? ` (${yrs})` : ""}; hutan JRC 2020 ${Math.round(i["1"].forest_2020_pct)}%; hutan alam SBTN ${nat == null ? "tidak terbaca" : `${Math.round(nat)}%`}`;
  }
  if (k === "2" && i["2"]) return `${Math.round(i["2"].pct)}% · ${i["2"].label}`;
  if (k === "3" && i["3"]) return `${Math.round(i["3"].pct)}% · ${i["3"].label}`;
  return "tidak terbaca";
}

/** Uji tiga indikator peta dengan kebun yang sengaja melanggarnya (data online saat tombol ditekan). */
function IndicatorTestPanel() {
  const [res, setRes] = useState<{ results: IndicatorTest[]; passed: number; total: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const go = () => {
    setBusy(true);
    setErr(null);
    api
      .indicatorTest()
      .then(setRes)
      .catch((e) => setErr(e instanceof ApiError ? e.message : "Uji gagal dijalankan"))
      .finally(() => setBusy(false));
  };
  return (
    <section className="panel panel-pad" style={{ marginTop: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "baseline" }}>
        <h2 style={{ fontSize: 18, marginBottom: 6 }}>Uji indikator peta</h2>
        <button className="btn btn-quiet" onClick={go} disabled={busy}>
          {busy ? <Spinner label="Membaca peta online" /> : "Jalankan uji sekarang"}
        </button>
      </div>
      <p className="small muted" style={{ marginBottom: 10 }}>
        Enam kebun uji dengan lokasi nyata, masing-masing sengaja melanggar (atau tidak melanggar) indikator tertentu. Uji membaca peta
        online saat ini juga, lalu membandingkan indikator yang menyala dan keputusan akhir dengan harapan. Perhatikan kebun peremajaan:
        indikator kehilangan tutupan menyala, tetapi keputusannya tetap aman karena lahannya bukan hutan pada 2020. Kebun Hasan menunjukkan
        guna peta hutan kedua: peta JRC menyebutnya hutan, peta hutan alam SBTN tidak, sehingga hasilnya perlu cek lapangan, bukan langsung berisiko.
      </p>
      {err && <Notice kind="danger">{err}</Notice>}
      {res && (
        <>
          <Notice kind={res.passed === res.total ? "ok" : "warn"}>
            {res.passed} dari {res.total} kebun uji lulus.
          </Notice>
          <div style={{ overflowX: "auto", marginTop: 10 }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Kebun uji</th>
                  {INDICATORS.map(([k, l]) => <th key={k}>{l}</th>)}
                  <th>Keputusan</th>
                  <th>Hasil</th>
                </tr>
              </thead>
              <tbody>
                {res.results.map((t) => (
                  <tr key={t.name}>
                    <td>
                      <strong>{t.name}</strong>
                      <div className="small faint">{t.why}</div>
                    </td>
                    {INDICATORS.map(([k]) => {
                      const on = t.on.includes(Number(k));
                      const want = t.expect_on.includes(Number(k));
                      return (
                        <td key={k} className="small">
                          <strong style={{ color: on ? "var(--risiko)" : undefined }}>{on ? "Menyala" : "Tidak"}</strong>
                          {on !== want && <span className="faint"> (harapan: {want ? "menyala" : "tidak"})</span>}
                          <div className="faint">{indicatorText(t, k)}</div>
                        </td>
                      );
                    })}
                    <td className="small">
                      <strong>{t.risk ? riskLabel(t.risk) : "-"}</strong>
                      {t.risk !== t.expect_risk && <span className="faint"> (harapan: {riskLabel(t.expect_risk)})</span>}
                      <div className="faint">{t.headline}</div>
                    </td>
                    <td className="small">
                      <strong>{t.passed ? "Lulus" : "Gagal"}</strong>
                      {t.errors.map((e) => <div key={e} className="faint">{e}</div>)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

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
      ["Data", "Dua peta hutan 2020: JRC GFC2020 (acuan UE, akurasi 91%) dan hutan alam SBTN Natural Lands Map (WRI/SBTN); kehilangan tutupan Hansen/GLAD, peringatan radar RADD (user's accuracy 97,6%), peta sawit Forest Data Partnership/Descals, peta Kawasan Hutan Kementerian Kehutanan, dan time series di atas."],
      ["Cek kawasan otomatis", "Saat kebun digambar, aplikasi menanyakan poligon kawasan hutan di lokasi itu ke layanan peta resmi Kemenhut, membaca fungsinya (konservasi, hutan lindung, hutan produksi, APL), lalu menghitung persentase luas kebun di tiap fungsi. Layanan Kemenhut terbaru (revisi Juni 2026) hanya mengizinkan tampilan peta, jadi aplikasi membaca gambarnya: setiap fungsi kawasan punya warna tetap di legenda resmi (kuning = hutan produksi tetap, ungu = konservasi, putih = APL, dan seterusnya), lalu setiap piksel di bawah kebun dicocokkan ke warna itu. Ini aturan pasti, bukan model AI, karena warnanya ditetapkan oleh pemilik peta. Bila server Kemenhut tidak terjangkau, aplikasi otomatis memakai Peta Kawasan Hutan KLHK 2017 yang disediakan Global Forest Watch, dan paspor menyebut sumber mana yang dipakai. Hasilnya disimpan di cache agar tetap jalan saat offline. Kebun yang lebih dari 5% masuk kawasan hutan langsung berstatus Berisiko. Tidak ada batas kawasan yang digambar tangan."],
      ["Bukti deforestasi", "Lapisan 'Kehilangan tutupan pohon' di peta (Hansen/GLAD lewat Global Forest Watch) dibaca per piksel di dalam batas kebun, bersama peta hutan JRC 2020 yang dipakai Uni Eropa. Kehilangan tutupan pohon belum tentu deforestasi: peremajaan atau panen kebun juga tercatat. Karena itu kebun baru berstatus Berisiko bila tutupan hilang sesudah 2020 DAN lahannya masih hutan pada 2020; bila bukan hutan, statusnya Aman (peremajaan)."],
      ["Dua peta hutan", "Makalah resmi peta JRC (Bourgoin dkk., ESSD 2026) mencatat peta itu keliru menyebut 'hutan' pada sekitar 18% kasus, terutama di kebun pohon dan agroforestri seperti karet dan sawit tua, dan menyarankan peta itu dipasangkan dengan data lain. Maka setiap piksel yang hilang dicek ke peta kedua, kelas hutan alam SBTN Natural Lands Map (peta yang juga dipakai GFW Pro dan Koltiva). Berisiko hanya bila kedua peta sepakat piksel itu hutan di minimal 10% luas kebun. Bila hanya satu peta yang menyebut hutan, hasilnya Perlu cek dan kebun wajib masuk sampel inspeksi lapangan; tidak otomatis Aman karena hutan tanaman tetap terhitung hutan menurut EUDR. Bila peta kedua tidak terbaca, paspor mencatat bahwa keputusan memakai satu peta."],
      ["Algoritma", "Aturan 'convergence of evidence' dari Whisp (FAO), ditambah pembeda peremajaan dan deforestasi: lahan yang tahun 2020 sudah kebun sawit lalu dibuka lagi adalah peremajaan (mis. PSR), bukan deforestasi."],
      ["Transparansi", "Aturannya terbuka di kode (evidence.py). Setiap paspor menampilkan bukti, sumber, dan tingkat keyakinan."],
      ["Batasannya", "Peta global kurang tajam untuk kebun di bawah 1 ha. Peta kawasan hutan berskala kecil dan bisa tertinggal dari SK pelepasan terbaru, jadi status 'masuk kawasan' adalah sinyal untuk diverifikasi (sertifikat, SK pelepasan), bukan vonis."],
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
          Mode data satelit:{" "}
          <strong>
            {meta.satellite_mode === "live"
              ? "live (Sentinel-2 dan Hansen asli)"
              : "demo: dua peta hutan 2020 (JRC dan SBTN) dan kehilangan tutupan (Hansen) dari peta nyata GFW, deret NDVI simulasi berlabel"}
          </strong>
          .
          AI batas kebun: <strong>{meta.sam.available ? "Segment Anything" : "watershed bawaan"}</strong>
          {meta.sam.available ? "" : ` (${meta.sam.reason})`}. Cek kawasan hutan:{" "}
          <strong>
            {!meta.kawasan || meta.kawasan.policy === "lokal"
              ? "peta lokal saja"
              : meta.kawasan.online === false
                ? meta.kawasan.gfw?.enabled
                  ? "peta Kemenhut tidak terjangkau, memakai cadangan Peta Kawasan Hutan KLHK 2017 (GFW)"
                  : "peta Kemenhut tidak terjangkau, memakai cache/peta lokal"
                : meta.kawasan.gfw?.enabled
                  ? `otomatis ke peta Kemenhut${meta.kawasan.mode === "gambar" ? " (dibaca dari gambar peta)" : ""}, cadangan KLHK 2017 (GFW)`
                  : "otomatis ke peta Kemenhut"}
          </strong>
          {meta.kawasan && meta.kawasan.cached_cells > 0 ? ` (${meta.kawasan.cached_cells} sel tersimpan)` : ""}. Batas EUDR: deforestasi
          setelah 31 Des 2020.
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

      <IndicatorTestPanel />

      <div className="grid-2" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <section className="panel panel-pad">
          <h2 style={{ fontSize: 18, marginBottom: 10 }}>Perlindungan data petani</h2>
          <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 8 }}>
            <li>NIK, foto KTP, dan foto wajah tidak disimpan. QR hanya berisi kode paspor.</li>
            <li>Paspor baru terbit setelah petani menyetujui berbagi data, dan waktu persetujuannya tercatat.</li>
            <li>Berkas EUDR dan paket ekspor tidak memuat nama petani (EUDR tidak memintanya); tampilan publik paspor menyamarkan nama.</li>
            <li>Pabrik hanya melihat status bukti lahan, bukan salinan dokumen; dokumen tetap di koperasi.</li>
            <li>Data tersimpan di server koperasi sendiri (SQLite), bukan di layanan pihak ketiga.</li>
            <li>Pemindaian QR dengan kamera diproses di browser; gambar kamera tidak dikirim ke server.</li>
            <li>
              Status dari komputer bukan vonis: kebun baru disebut Berisiko bila dua peta hutan sepakat, petani bisa mengajukan keberatan,
              dan yang memutus adalah verifikator. Penilaian dampak pelindungan data (UU PDP Pasal 34) dan kebijakan privasi, termasuk
              kekurangan yang belum selesai, ada di <span className="num">docs/DPIA.md</span> dan{" "}
              <span className="num">docs/KEBIJAKAN_PRIVASI.md</span>.
            </li>
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
      <section className="panel panel-pad" style={{ marginTop: 16 }}>
        <h2 style={{ fontSize: 18, marginBottom: 6 }}>Kapan kebun berstatus "Siap EUDR"</h2>
        <p className="small muted" style={{ marginBottom: 10 }}>
          Paspor Kebun adalah bukti uji tuntas, bukan sertifikat ISPO/RSPO (sertifikat itu hanya boleh diterbitkan lembaga sertifikasi
          terakreditasi KAN atau ASI). Kebun Siap EUDR bila kelima syarat terpenuhi, dan statusnya berlaku 12 bulan sejak cek satelit terakhir.
        </p>
        <ol style={{ margin: 0, paddingLeft: 20, display: "grid", gap: 6 }}>
          <li><strong>Lokasi:</strong> batas dipetakan dan disaksikan tetangga atau ketua kelompok tani. EUDR cukup meminta satu titik GPS untuk kebun di bawah 4 ha.</li>
          <li><strong>Lahan:</strong> ada bukti penguasaan (sertifikat, surat desa, atau pernyataan + 2 saksi), tidak ada sengketa, STDB sudah ada atau sedang diurus. Sertifikat tidak wajib: ISPO menerima surat penguasaan fisik.</li>
          <li><strong>Kawasan:</strong> di luar kawasan hutan menurut peta resmi Kementerian Kehutanan.</li>
          <li><strong>Hutan:</strong> satelit tidak menemukan pembukaan hutan setelah 31 Desember 2020.</li>
          <li><strong>Verifikasi:</strong> tidak sedang menunggu atau gagal inspeksi lapangan oleh verifikator independen.</li>
        </ol>
      </section>

      <div className="grid-2" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <section className="panel panel-pad">
          <h2 style={{ fontSize: 18, marginBottom: 10 }}>Siapa memeriksa siapa</h2>
          <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 8 }}>
            <li><strong>Petugas koperasi</strong> memetakan kebun bersama petani dan saksi, mencatat bukti lahan (sistem kendali internal).</li>
            <li><strong>AI</strong> memeriksa riwayat satelit dan kawasan hutan, menjaga titik pengepul, dan memilih kebun yang paling perlu didatangi.</li>
            <li><strong>Verifikator independen</strong> mengunjungi sampel kebun (akar(n) x 2,5 x 1,5, rumus RSPO) dan memutuskan keberatan dengan alasan tertulis.</li>
            <li><strong>Pabrik</strong> menerima status, bukan salinan dokumen petani, lalu menyusun paket data untuk importir.</li>
            <li><strong>Petani</strong> bisa mengajukan keberatan atas status kebunnya; keputusan gugur otomatis bila satelit menemukan bukti baru.</li>
          </ul>
        </section>
        <section className="panel panel-pad">
          <h2 style={{ fontSize: 18, marginBottom: 10 }}>Keamanan aplikasi</h2>
          <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 8 }}>
            <li>Masuk per peran; setiap endpoint yang mengubah data menyebut peran yang boleh. Pengepul hanya bisa mencatat atas nama usahanya.</li>
            <li>Kata sandi disimpan sebagai hash PBKDF2-SHA256 (210.000 iterasi); sesi di cookie HttpOnly + SameSite yang ditandatangani HMAC.</li>
            <li>Perlindungan CSRF, Content-Security-Policy, dan header keamanan lain; batas laju untuk login, AI, dan unggahan.</li>
            <li>Riwayat perubahan berantai hash: mengubah satu baris diam-diam langsung terdeteksi (halaman Verifikasi, tab Integritas).</li>
            <li>Rahasia (kunci sesi) disimpan di .env, tidak di kode. Foto inspeksi divalidasi, diperkecil, dan metadata EXIF-nya dibuang.</li>
          </ul>
        </section>
      </div>

      <p className="small faint" style={{ marginTop: 16 }}>
        Rincian validasi: docs/VALIDASI.md. Rincian algoritma dan sumber: docs/ALGORITMA.md. Kode aplikasi ini dikembangkan tim dengan bantuan
        AI coding assistant (Claude, Anthropic); fitur AI di dalam produk tidak memakai layanan AI pihak ketiga dan berjalan di server sendiri.
      </p>
    </div>
  );
}
