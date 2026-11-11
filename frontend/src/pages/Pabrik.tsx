import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Download, PackageCheck } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dateLabel, dateTimeLabel, dec1, kg, monthLabel, num, pct } from "../lib/format";
import type { Dashboard, Shipment } from "../lib/types";
import { Notice, Spinner } from "../components/ui";

const BLOCKER_LABEL: Record<string, string> = {
  lahan: "bukti lahan / STDB",
  verifikasi: "menunggu atau gagal inspeksi",
  hutan: "status satelit",
  lokasi: "batas belum disaksikan",
  kawasan: "kawasan hutan",
};

const iso = (d: Date) => d.toISOString().slice(0, 10);

function Shipments() {
  const [list, setList] = useState<Shipment[] | null>(null);
  const [cur, setCur] = useState<Shipment | null>(null);
  const today = new Date();
  const [f, setF] = useState({
    buyer: "Rotterdam Oils B.V. (fiktif)",
    destination: "Uni Eropa",
    period_start: iso(new Date(today.getTime() - 30 * 864e5)),
    period_end: iso(today),
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => api.shipments().then(setList).catch(() => setList([])), []);
  useEffect(() => {
    load();
  }, [load]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      setCur(await api.createShipment(f));
      load();
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel" style={{ marginTop: 16 }} aria-label="Pengiriman ekspor">
      <div className="panel-pad" style={{ paddingBottom: 8 }}>
        <h2 style={{ fontSize: 18 }}>Paket data untuk pengiriman ekspor</h2>
        <p className="small muted" style={{ marginTop: 4, maxWidth: "86ch" }}>
          Importir di Uni Eropa wajib membuktikan asal setiap pengiriman. Paket ini berisi geolokasi semua kebun asal, rentang waktu panen,
          volume, serta bukti bebas deforestasi dan legalitas. Hanya TBS dari kebun Siap EUDR yang masuk; tidak ada pencampuran.
        </p>
      </div>
      <form className="panel-pad ship-form" onSubmit={create}>
        <label className="field"><span>Pembeli / importir</span><input className="input" value={f.buyer} onChange={(e) => setF({ ...f, buyer: e.target.value })} required minLength={3} /></label>
        <label className="field"><span>Tujuan</span><input className="input" value={f.destination} onChange={(e) => setF({ ...f, destination: e.target.value })} /></label>
        <label className="field"><span>Pembelian TBS dari</span><input className="input" type="date" value={f.period_start} onChange={(e) => setF({ ...f, period_start: e.target.value })} required /></label>
        <label className="field"><span>sampai</span><input className="input" type="date" value={f.period_end} onChange={(e) => setF({ ...f, period_end: e.target.value })} required /></label>
        <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? <Spinner /> : <PackageCheck />} Buat paket</button>
      </form>
      {err && <div className="panel-pad" style={{ paddingTop: 0 }}><Notice kind="danger">{err}</Notice></div>}
      {cur && (
        <div className="panel-pad ship-result">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
            <div>
              <strong className="num">{cur.code}</strong> <span className="muted">untuk {cur.buyer}</span>
              <div className="small muted">Periode {dateLabel(cur.period_start)} s.d. {dateLabel(cur.period_end)}</div>
            </div>
            <a className="btn btn-primary" href={api.shipmentZipUrl(cur.id)} download><Download /> Unduh paket (ZIP)</a>
          </div>
          <div className="ship-kpis">
            <div><b className="num" style={{ color: "var(--aman)" }}>{kg(cur.summary.included_kg)}</b><span>dari {cur.summary.n_included} kebun Siap EUDR, boleh dikirim</span></div>
            <div><b className="num" style={{ color: "var(--cek)" }}>{kg(cur.summary.excluded_kg)}</b><span>dari {cur.summary.n_excluded} kebun belum siap, dipisahkan</span></div>
            <div><b className="num" style={{ color: "var(--risiko)" }}>{kg(cur.summary.held_kg)}</b><span>ditahan di pengepul</span></div>
            <div><b className="num">{pct(cur.summary.eligible_share)}</b><span>dari {kg(cur.summary.delivered_kg)} setoran ke pabrik memenuhi syarat</span></div>
          </div>
          {!!cur.excluded?.length && (
            <details>
              <summary className="small">Kebun yang dikeluarkan dan alasannya ({cur.excluded.length})</summary>
              <ul className="small excluded-list">
                {cur.excluded.slice(0, 25).map((e) => (
                  <li key={e.plot_code}>
                    <Link to={`/peta?kebun=${e.plot_id}`} className="num">{e.plot_code}</Link> ({kg(e.volume_kg)}): {e.failed_checks.join("; ")}
                  </li>
                ))}
              </ul>
            </details>
          )}
          <p className="small faint">{cur.summary.rule} Paket ini adalah bukti uji tuntas, bukan sertifikat ISPO/RSPO.</p>
        </div>
      )}
      {!!list?.length && (
        <div style={{ overflowX: "auto" }}>
          <table className="table">
            <thead><tr><th>Kode</th><th>Pembeli</th><th>Periode</th><th>Masuk</th><th>Dipisahkan</th><th></th></tr></thead>
            <tbody>
              {list.map((s) => (
                <tr key={s.id}>
                  <td className="num">{s.code}</td>
                  <td>{s.buyer}<div className="small faint">{s.created_by}, {dateLabel(s.created_at)}</div></td>
                  <td className="small num">{dateLabel(s.period_start)} – {dateLabel(s.period_end)}</td>
                  <td className="num">{kg(s.summary.included_kg)} <span className="small faint">({s.summary.n_included} kebun)</span></td>
                  <td className="num">{kg(s.summary.excluded_kg)}</td>
                  <td><a href={api.shipmentZipUrl(s.id)} download className="small">ZIP</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function MonthlyBars({ data }: { data: Dashboard["monthly"] }) {
  const W = 560;
  const H = 220;
  const P = { l: 40, r: 8, t: 12, b: 34 };
  const max = Math.max(...data.map((d) => d.delivered_t), 1) * 1.1;
  const bw = (W - P.l - P.r) / data.length;
  const y = (v: number) => P.t + (1 - v / max) * (H - P.t - P.b);
  const ticks = [0, max / 3, (2 * max) / 3].map((v) => Math.round(v / 10) * 10);
  return (
    <figure style={{ margin: 0 }}>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Setoran TBS per bulan: tertelusur dan tidak tertelusur">
        {ticks.map((t) => (
          <g key={t}>
            <line className="grid" x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} />
            <text x={P.l - 6} y={y(t) + 4} textAnchor="end">{t} t</text>
          </g>
        ))}
        {data.map((d, i) => {
          const x = P.l + i * bw + bw * 0.2;
          const w = bw * 0.6;
          const untraced = Math.max(d.delivered_t - d.traced_t, 0);
          const share = d.delivered_t ? d.traced_t / d.delivered_t : 0;
          return (
            <g key={d.month}>
              <rect x={x} y={y(d.traced_t)} width={w} height={H - P.b - y(d.traced_t)} fill="#1e7a4b" rx={2} />
              <rect x={x} y={y(d.delivered_t)} width={w} height={Math.max(0, y(d.traced_t) - y(d.delivered_t) - 1.5)} fill="#d9a441" rx={2} opacity={d.partial ? 0.6 : 1} />
              <text x={x + w / 2} y={H - P.b + 15} textAnchor="middle">{monthLabel(d.month)}{d.partial ? "*" : ""}</text>
              {d.delivered_t > 0 && (
                <text x={x + w / 2} y={y(d.delivered_t) - 5} textAnchor="middle" style={{ fill: "#14231c", fontWeight: 600 }}>
                  {pct(share)}
                </text>
              )}
              <title>{`${monthLabel(d.month)}: setoran ${dec1(d.delivered_t)} t, tertelusur ${dec1(d.traced_t)} t, tak tertelusur ${dec1(untraced)} t`}</title>
            </g>
          );
        })}
      </svg>
      <figcaption className="small muted" style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <span><i className="swatch" style={{ display: "inline-block", background: "#1e7a4b", borderColor: "#1e7a4b", marginRight: 6 }} />Tertelusur ke kebun berpaspor</span>
        <span><i className="swatch" style={{ display: "inline-block", background: "#d9a441", borderColor: "#d9a441", marginRight: 6 }} />Tidak tertelusur</span>
        <span>* bulan berjalan</span>
      </figcaption>
    </figure>
  );
}

export default function Pabrik() {
  const { can } = useAuth();
  const [d, setD] = useState<Dashboard | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api.dashboard().then(setD).catch((e) => setErr(e.message));
  }, []);

  if (err) return <div className="page"><Notice kind="danger">{err}</Notice></div>;
  if (!d) return <div className="page"><Spinner label="Memuat dasbor…" /></div>;
  const k = d.kpi;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Dasbor pabrik</h1>
          <p className="muted">PKS Sejahtera (demo). Asal setiap TBS yang masuk, dan pengepul mana yang perlu diaudit.</p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <div className="countdown"><b>{d.days_to_eudr}</b> hari lagi EUDR berlaku</div>
          {can("pabrik") && <a className="btn" href={api.eudrAllUrl()} download><Download /> GeoJSON kebun siap</a>}
        </div>
      </div>

      <section className="panel kpis" aria-label="Ringkasan">
        <div className="kpi">
          <div className="v">{pct(k.traced_share_30d)}</div>
          <div className="l">TBS 30 hari tertelusur ke kebun ({dec1(k.traced_t_30d)} dari {dec1(k.delivered_t_30d)} t)</div>
        </div>
        <div className="kpi">
          <div className="v">{k.eudr_ready}<span className="faint" style={{ fontSize: 18 }}> / {k.plots}</span></div>
          <div className="l">
            Kebun Siap EUDR (5 syarat). Penghambat terbanyak:{" "}
            {Object.entries(k.blockers ?? {})
              .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))
              .slice(0, 2)
              .map(([key, n]) => `${BLOCKER_LABEL[key] ?? key} (${n})`)
              .join(", ")}
          </div>
        </div>
        <div className="kpi">
          <div className="v">{dec1(k.held_t_30d)} t</div>
          <div className="l">TBS ditahan di pengepul dalam 30 hari terakhir</div>
        </div>
        <div className="kpi">
          <div className="v" style={{ color: "var(--risiko)" }}>{k.risk.tinggi ?? 0}<span className="faint" style={{ fontSize: 18, color: "var(--cek)" }}> + {k.risk.perlu_cek ?? 0}</span></div>
          <div className="l">
            Kebun berisiko + perlu cek. <Link to="/peta">Buka di peta</Link>
          </div>
        </div>
      </section>

      <div className="grid-2">
        <section className="panel panel-pad">
          <h2 style={{ fontSize: 18, marginBottom: 4 }}>Setoran TBS per bulan</h2>
          <p className="small muted" style={{ marginBottom: 12 }}>Persentase di atas batang = porsi yang tertelusur ke kebun berpaspor.</p>
          <MonthlyBars data={d.monthly} />
        </section>
        <section className="panel panel-pad">
          <h2 style={{ fontSize: 18, marginBottom: 10 }}>Transaksi bermasalah terbaru</h2>
          <div style={{ maxHeight: 300, overflow: "auto" }}>
            {d.alerts.map((t) => (
              <div className="txn" key={t.id}>
                <span><strong>{t.collector}</strong> <span className="small faint num">{t.plot_code}</span></span>
                <span className={`tag tag-${t.decision === "ditahan" ? "tinggi" : "perlu_cek"}`}>{t.decision === "ditahan" ? "Ditahan" : "Catatan"}</span>
                <span className="small muted" style={{ gridColumn: "1 / -1" }}>
                  {dateTimeLabel(t.created_at)}, {kg(t.weight_kg)}: {t.flags.filter((f) => f.severity !== "info").map((f) => f.title).join("; ")}
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="panel" style={{ marginTop: 16 }}>
        <div className="panel-pad" style={{ paddingBottom: 6 }}>
          <h2 style={{ fontSize: 18 }}>Pengepul pemasok, diurutkan menurut skor anomali AI</h2>
          <p className="small muted" style={{ marginTop: 4, maxWidth: "80ch" }}>
            Isolation Forest membandingkan pola 90 hari setiap pengepul dengan pengepul lain. Skor tinggi bukan bukti kecurangan;
            artinya pengepul itu layak diaudit lebih dulu. Alasan ditampilkan agar keputusan bisa diperiksa.
          </p>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Pengepul</th>
                <th>Setoran 90 hari</th>
                <th>Tertelusur</th>
                <th>Transaksi bertanda</th>
                <th>Skor anomali</th>
                <th>Alasan utama</th>
              </tr>
            </thead>
            <tbody>
              {d.collectors.map((c) => (
                <tr key={c.id}>
                  <td><strong>{c.name}</strong><div className="small faint">{c.village}, {c.n_plots} kebun</div></td>
                  <td className="num">{kg(c.delivered_kg)}</td>
                  <td className="num" style={{ color: (c.traced_share ?? 1) < 0.8 ? "var(--risiko)" : undefined, fontWeight: 600 }}>{pct(c.traced_share)}</td>
                  <td className="num">{num(c.flagged)} dari {num(c.n_txn)}</td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div className="scorebar" aria-hidden="true">
                        <i style={{ width: `${c.ai_score ?? 0}%`, background: c.ai_level === "tinggi" ? "var(--risiko)" : c.ai_level === "sedang" ? "var(--cek)" : "var(--aman)" }} />
                      </div>
                      <span className="num" style={{ fontWeight: 600 }}>{c.ai_score}</span>
                    </div>
                  </td>
                  <td className="small">
                    {c.ai_reasons.length
                      ? c.ai_reasons.map((r) => <div key={r.feature}>{r.label}: <strong>{r.value}</strong> <span className="faint">(umumnya {r.typical})</span></div>)
                      : <span className="faint">Pola wajar</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {can("pabrik") && <Shipments />}
      <p className="small faint" style={{ marginTop: 12 }}>Dihitung {d.compute_ms} ms di server dari {num(d.kpi.plots)} kebun dan seluruh transaksi 6 bulan.</p>
    </div>
  );
}
