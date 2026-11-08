import { useMemo, useState } from "react";
import { dateLabel } from "../lib/format";
import type { TimeSeries } from "../lib/types";

const W = 400;
const H = 190;
const P = { l: 34, r: 10, t: 14, b: 26 };

/** Riwayat NDVI: titik = citra bebas awan, garis = model AI, garis putus = batas EUDR. */
export function NdviChart({ ts, cutoff }: { ts: TimeSeries; cutoff: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const data = useMemo(() => {
    const t = ts.dates.map((d) => new Date(d).getTime());
    const t0 = t[0];
    const t1 = Math.max(t[t.length - 1], new Date().getTime());
    const x = (ms: number) => P.l + ((ms - t0) / (t1 - t0)) * (W - P.l - P.r);
    const y = (v: number) => P.t + (1 - (v - 0) / 1) * (H - P.t - P.b);
    const segs: Record<number, string[]> = {};
    ts.curve.forEach((c) => {
      (segs[c.segment] ||= []).push(`${x(new Date(c.date).getTime()).toFixed(1)},${y(c.value).toFixed(1)}`);
    });
    const years: number[] = [];
    for (let yr = new Date(t0).getFullYear() + 1; yr <= new Date(t1).getFullYear(); yr++) years.push(yr);
    return { t, x, y, segs, years };
  }, [ts]);

  if (!ts.dates.length) return <p className="muted small">Tidak ada data citra.</p>;
  const cutX = data.x(new Date(cutoff).getTime());
  const h = hover != null ? { d: ts.dates[hover], v: ts.ndvi[hover], o: ts.is_outlier[hover] } : null;

  return (
    <figure style={{ margin: 0 }}>
      <svg
        className="chart"
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        role="img"
        aria-label={`Grafik NDVI ${ts.n_obs} citra satelit sejak ${ts.dates[0].slice(0, 4)}`}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          const mx = ((e.clientX - r.left) / r.width) * W;
          let best = 0;
          let bd = Infinity;
          data.t.forEach((ms, i) => {
            const d = Math.abs(data.x(ms) - mx);
            if (d < bd) { bd = d; best = i; }
          });
          setHover(best);
        }}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((v) => (
          <g key={v}>
            <line className="grid" x1={P.l} x2={W - P.r} y1={data.y(v)} y2={data.y(v)} />
            <text x={P.l - 6} y={data.y(v) + 4} textAnchor="end">{v.toFixed(2).replace(".", ",")}</text>
          </g>
        ))}
        {data.years.map((yr) => {
          const xx = data.x(new Date(`${yr}-01-01`).getTime());
          return <text key={yr} x={xx} y={H - 8} textAnchor="middle">{yr}</text>;
        })}
        <rect x={cutX} y={P.t} width={W - P.r - cutX} height={H - P.t - P.b} fill="#0e4d41" opacity={0.04} />
        <line x1={cutX} x2={cutX} y1={P.t - 4} y2={H - P.b} stroke="#b08a3e" strokeDasharray="4 3" strokeWidth={1.4} />
        <text x={cutX + 4} y={P.t + 6} style={{ fill: "#8a6a2a", fontWeight: 600 }}>Batas EUDR</text>
        {ts.dates.map((d, i) => (
          <circle
            key={d + i}
            cx={data.x(data.t[i])}
            cy={data.y(Math.max(0, ts.ndvi[i]))}
            r={ts.is_outlier[i] ? 1.8 : 2.2}
            fill={ts.is_outlier[i] ? "none" : "#6f8f7c"}
            stroke={ts.is_outlier[i] ? "#9aa59f" : "none"}
            opacity={0.75}
          />
        ))}
        {Object.values(data.segs).map((pts, i) => (
          <polyline key={i} points={pts.join(" ")} fill="none" stroke="#0e4d41" strokeWidth={2} />
        ))}
        {ts.breaks.map((b) => {
          const bx = data.x(new Date(b.date).getTime());
          const c = b.after_cutoff ? "#b3261e" : "#a86a12";
          return (
            <g key={b.date}>
              <line x1={bx} x2={bx} y1={P.t} y2={H - P.b} stroke={c} strokeWidth={1.5} />
              <circle cx={bx} cy={P.t + 2} r={4} fill={c} />
            </g>
          );
        })}
        {h && (
          <g pointerEvents="none">
            <line x1={data.x(data.t[hover!])} x2={data.x(data.t[hover!])} y1={P.t} y2={H - P.b} stroke="#14231c" opacity={0.25} />
            <circle cx={data.x(data.t[hover!])} cy={data.y(Math.max(0, h.v))} r={4} fill="#14231c" />
          </g>
        )}
      </svg>
      <figcaption className="small muted" style={{ minHeight: 20 }}>
        {h
          ? `${dateLabel(h.d)}: NDVI ${h.v.toFixed(2).replace(".", ",")}${h.o ? " (sisa awan, diabaikan model)" : ""}`
          : `${ts.n_obs} citra bebas awan, ${ts.span_years.toFixed(1).replace(".", ",")} tahun. Arahkan kursor untuk detail.`}
      </figcaption>
    </figure>
  );
}
