import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Download } from "lucide-react";
import { api } from "../lib/api";
import { dateTimeLabel, dec1, kg, monthLabel, num, pct } from "../lib/format";
import type { Dashboard } from "../lib/types";
import { Notice, Spinner } from "../components/ui";

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
          <a className="btn" href={api.eudrAllUrl()} download><Download /> GeoJSON EUDR</a>
        </div>
      </div>

      <section className="panel kpis" aria-label="Ringkasan">
        <div className="kpi">
          <div className="v">{pct(k.traced_share_30d)}</div>
          <div className="l">TBS 30 hari tertelusur ke kebun ({dec1(k.traced_t_30d)} dari {dec1(k.delivered_t_30d)} t)</div>
        </div>
        <div className="kpi">
          <div className="v">{k.eudr_ready}<span className="faint" style={{ fontSize: 18 }}> / {k.plots}</span></div>
          <div className="l">Kebun siap EUDR: aman, batas disaksikan, setuju berbagi data</div>
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
      <p className="small faint" style={{ marginTop: 12 }}>Dihitung {d.compute_ms} ms di server dari {num(d.kpi.plots)} kebun dan seluruh transaksi 6 bulan.</p>
    </div>
  );
}
