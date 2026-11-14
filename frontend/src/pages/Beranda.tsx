import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ChevronDown, ClipboardCheck, Factory, Map as MapIcon, Scale, Search, type LucideIcon } from "lucide-react";
import { Emblem, Stamp } from "../components/ui";

const STEPS: { icon: LucideIcon; title: string; who: string; text: string }[] = [
  {
    icon: MapIcon,
    title: "Petakan kebun",
    who: "Koperasi & pendamping petani",
    text: "Berdiri di kebun, tekan satu tombol: GPS mencatat titik, AI menggambar batas, tetangga menjadi saksi. Satelit lalu memeriksa riwayat lahan sejak 2018 dan peta kawasan hutan.",
  },
  {
    icon: Scale,
    title: "Pindai saat membeli",
    who: "Pengepul / RAM",
    text: "Pengepul memindai kartu QR petani dan mencatat berat. Volume yang mustahil untuk luas dan umur kebun itu langsung ditahan.",
  },
  {
    icon: ClipboardCheck,
    title: "Periksa sampel",
    who: "Verifikator independen",
    text: "Verifikator independen mengunjungi kebun yang dipilih berdasarkan risiko, mengambil foto bergeotag, dan memutuskan keberatan petani.",
  },
  {
    icon: Factory,
    title: "Kirim dengan bukti",
    who: "Pabrik kelapa sawit & eksportir",
    text: "Pabrik memisahkan TBS dari kebun yang belum siap dan mengunduh paket data uji tuntas untuk importir Eropa.",
  },
];

export default function Beranda() {
  const nav = useNavigate();
  const [code, setCode] = useState("");
  const [open, setOpen] = useState<Record<number, boolean>>({});
  return (
    <div className="home">
      <section className="hero">
        <div>
          <h1>Sawit petani jujur jangan ikut tertolak.</h1>
          <p className="lead">
            Mulai 30 Desember 2026 Uni Eropa hanya membeli minyak sawit dari kebun yang terbukti tidak membuka hutan setelah 2020.
            Petani swadaya belum punya peta kebun, dan buah dari kawasan hutan masih bisa menumpang lewat pengepul. PasporKebun
            memberi setiap kebun bukti uji tuntas yang bisa dicek siapa saja, dan menutup celah di titik pengepul.
          </p>
          <div className="actions">
            <Link className="btn btn-primary btn-lg" to="/masuk">Masuk dan coba</Link>
            <Link className="btn btn-lg" to="/transparansi">Cara kerja AI</Link>
          </div>
          <form className="hero-check" onSubmit={(e) => { e.preventDefault(); if (code.trim()) nav(`/cek/${encodeURIComponent(code.trim())}`); }}>
            <input className="input num" placeholder="Cek paspor, mis. PK-00001-F" value={code} onChange={(e) => setCode(e.target.value)} aria-label="Kode paspor" />
            <button className="btn" type="submit"><Search /> Cek</button>
          </form>
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
              <p style={{ marginTop: 10 }}>Siap EUDR: 5 dari 5 syarat terpenuhi. Sudah kebun sawit sebelum 2021, diperiksa dari 190 citra Sentinel-2.</p>
            </div>
            <Stamp risk="rendah" sub="keyakinan 90%" />
          </div>
          <div className="mrz" style={{ margin: "0 22px 22px" }} aria-hidden="true">
            <div>PK&lt;IDNPK00001F&lt;&lt;SANTOSO&lt;&lt;BUDI&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;</div>
            <div>198HA&lt;SUNGAI&lt;HARAPAN&lt;2008&lt;RENDAH&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;</div>
          </div>
        </div>
      </section>

      <section className="facts-line facts-cards" aria-label="Fakta masalah">
        <div><b>7%</b><span>kebun sawit rakyat yang siap memenuhi EUDR (APKASINDO, Okt 2026)</span></div>
        <div><b>7 dari 10</b><span>petani belum punya data spasial kebun (INDEF)</span></div>
        <div><b>41%</b><span>dari 16,8 juta ha kebun sawit Indonesia adalah kebun rakyat</span></div>
      </section>

      <section aria-label="Cara kerja">
        <h2 className="acc-group acc-group-solo">Satu paspor, empat pihak yang saling memeriksa</h2>
        <p className="small muted tcards-hint">Arahkan kursor atau klik kartu untuk melihat penjelasannya.</p>
        <div className="tcards">
          {STEPS.map((st, i) => {
            const Icon = st.icon;
            return (
              <div key={st.title} className="tcard" data-open={open[i] || undefined}>
                <h3 className="tcard-h">
                  <button
                    type="button"
                    aria-expanded={!!open[i]}
                    aria-controls={`tcard-${i}`}
                    onClick={() => setOpen((o) => ({ ...o, [i]: !o[i] }))}
                  >
                    <span className="tcard-top">
                      <span className="tcard-ic"><Icon aria-hidden="true" /></span>
                      <span className="tcard-no">Langkah {i + 1}</span>
                      <ChevronDown className="tcard-chev" aria-hidden="true" />
                    </span>
                    <span className="tcard-title">{st.title}</span>
                    <span className="pill tcard-who">{st.who}</span>
                  </button>
                </h3>
                <div className="tcard-body" id={`tcard-${i}`}>
                  <div>
                    <p>{st.text}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>
      <p className="small faint">
        Paspor Kebun adalah bukti uji tuntas, bukan sertifikat ISPO/RSPO. Nama petani, desa, dan transaksi di aplikasi ini fiktif untuk
        demo; citra satelit dan peta kawasan hutan di peta adalah data asli.{" "}
        <Link to="/transparansi">Lihat cara kerja AI dan batasannya</Link>.
      </p>
    </div>
  );
}
