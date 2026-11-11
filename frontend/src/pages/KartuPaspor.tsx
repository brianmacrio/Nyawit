import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import QRCode from "qrcode";
import { ArrowLeft, Printer } from "lucide-react";
import { api } from "../lib/api";
import { ha } from "../lib/format";
import type { PlotDetail } from "../lib/types";
import { Emblem, Notice, Spinner } from "../components/ui";

/** Kartu paspor seukuran kartu nama untuk dicetak dan dibawa petani saat menjual TBS (tanpa perlu ponsel). */
export default function KartuPaspor() {
  const { id } = useParams();
  const [p, setP] = useState<PlotDetail | null>(null);
  const [qr, setQr] = useState("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.plot(Number(id)).then(setP).catch((e) => setErr(e.message));
  }, [id]);
  useEffect(() => {
    if (!p) return;
    QRCode.toString(`PASPORKEBUN:${p.code}`, { type: "svg", margin: 0, color: { dark: "#14231c", light: "#ffffff" } })
      .then(setQr)
      .catch(() => setQr(""));
  }, [p]);

  if (err) return <div className="page"><Notice kind="danger">{err}</Notice></div>;
  if (!p) return <div className="page"><Spinner label="Memuat…" /></div>;
  const parts = p.farmer.name.split(" ");
  const shortName = parts.length > 1 ? `${parts[0]} ${parts[parts.length - 1][0]}.` : p.farmer.name;

  return (
    <div className="page">
      <div className="page-head no-print">
        <div>
          <h1>Kartu paspor kebun</h1>
          <p className="muted">Cetak di kertas tebal lalu laminasi. Kartu hanya berisi kode, nama singkat, dan desa; tanpa NIK.</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link className="btn btn-quiet" to={`/peta?kebun=${p.id}`}><ArrowLeft /> Kembali</Link>
          <button className="btn btn-primary" onClick={() => window.print()}><Printer /> Cetak</button>
        </div>
      </div>
      <div className="id-card" aria-label={`Kartu paspor ${p.code}`}>
        <div className="id-card-top">
          <Emblem size={26} />
          <span>PASPOR KEBUN</span>
        </div>
        <div className="id-card-body">
          <div className="qr" dangerouslySetInnerHTML={{ __html: qr }} />
          <div>
            <div className="code">{p.code}</div>
            <div className="nm">{shortName}</div>
            <div className="small">Desa {p.farmer.village}</div>
            <div className="small">{ha(p.area_ha)}</div>
          </div>
        </div>
        <div className="id-card-foot">Tunjukkan kartu ini ke pengepul setiap menjual TBS · cek: /cek/{p.code}</div>
      </div>
    </div>
  );
}
