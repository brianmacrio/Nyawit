import { Link } from "react-router-dom";
import { Factory, Map as MapIcon, Scale } from "lucide-react";
import { Emblem, Stamp } from "../components/ui";

export default function Beranda() {
  return (
    <div className="home">
      <section className="hero">
        <div>
          <h1>Sawit petani jujur jangan ikut tertolak.</h1>
          <p className="lead">
            Mulai 30 Desember 2026 Uni Eropa hanya membeli minyak sawit dari kebun yang terbukti tidak membuka hutan setelah 2020.
            Petani swadaya belum punya peta kebun, dan buah dari kawasan hutan masih bisa menumpang lewat pengepul. PasporKebun
            menutup dua celah itu.
          </p>
          <div className="actions">
            <Link className="btn btn-primary btn-lg" to="/peta">Buka peta kebun</Link>
            <Link className="btn btn-lg" to="/pengepul">Coba sebagai pengepul</Link>
          </div>
        </div>
        <div className="panel" style={{ overflow: "hidden" }} aria-label="Contoh paspor kebun">
          <div className="passport-cover">
            <Emblem size={30} />
            <span className="t">Paspor Kebun</span>
            <span className="code">PK-00001-F</span>
          </div>
          <div style={{ padding: 22, display: "grid", gridTemplateColumns: "1fr auto", gap: 16, alignItems: "center" }}>
            <div>
              <h2 style={{ fontSize: 22 }}>Budi Santoso</h2>
              <p className="muted">Kebun Desa Sungai Harapan, 1,98 ha</p>
              <p style={{ marginTop: 10 }}>Sudah kebun sawit sebelum 2021. Diperiksa dari 190 citra Sentinel-2 dan 5 lapisan peta.</p>
            </div>
            <Stamp risk="rendah" sub="keyakinan 90%" />
          </div>
          <div className="mrz" style={{ margin: "0 22px 22px" }} aria-hidden="true">
            <div>PK&lt;IDNPK00001F&lt;&lt;SANTOSO&lt;&lt;BUDI&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;</div>
            <div>198HA&lt;SUNGAI&lt;HARAPAN&lt;2008&lt;RENDAH&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;</div>
          </div>
        </div>
      </section>

      <section className="facts-line" aria-label="Fakta masalah">
        <div><b>7%</b><span>kebun sawit rakyat yang siap memenuhi EUDR (APKASINDO, Okt 2026)</span></div>
        <div><b>7 dari 10</b><span>petani belum punya data spasial kebun (INDEF)</span></div>
        <div><b>41%</b><span>dari 16,8 juta ha kebun sawit Indonesia adalah kebun rakyat</span></div>
      </section>

      <section aria-label="Cara kerja">
        <h2 style={{ marginBottom: 16 }}>Satu paspor, dipakai di tiga titik</h2>
        <div className="steps">
          <div className="step">
            <MapIcon color="var(--sampul)" aria-hidden="true" />
            <h3>Petakan kebun</h3>
            <p className="muted">Petani menunjuk kebunnya di citra satelit, AI menggambar batas, saksi mengesahkan. Satelit lalu memeriksa 5+ tahun riwayat lahan.</p>
            <span className="who">Koperasi &amp; pendamping petani</span>
          </div>
          <div className="step">
            <Scale color="var(--sampul)" aria-hidden="true" />
            <h3>Pindai saat membeli</h3>
            <p className="muted">Pengepul memindai QR paspor dan mencatat berat. Volume yang mustahil untuk kebun itu langsung ditahan.</p>
            <span className="who">Pengepul / RAM</span>
          </div>
          <div className="step">
            <Factory color="var(--sampul)" aria-hidden="true" />
            <h3>Buktikan asal TBS</h3>
            <p className="muted">Pabrik melihat porsi TBS yang tertelusur, pengepul yang perlu diaudit, dan mengunduh berkas geolokasi EUDR.</p>
            <span className="who">Pabrik kelapa sawit &amp; eksportir</span>
          </div>
        </div>
      </section>
      <p className="small faint">
        Nama petani, desa, dan transaksi di aplikasi ini fiktif untuk demo. Citra satelit di peta adalah citra asli.{" "}
        <Link to="/transparansi">Lihat cara kerja AI dan batasannya</Link>.
      </p>
    </div>
  );
}
