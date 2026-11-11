import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { CircleCheck, CircleHelp, CircleMinus, CircleAlert, Download, Printer, RefreshCw, X } from "lucide-react";
import { api } from "../lib/api";
import { dateLabel, ha, KAWASAN_SOURCE_SHORT, kawasanText } from "../lib/format";
import type { EvidenceItem, PlotDetail } from "../lib/types";
import { NdviChart } from "./NdviChart";
import { Emblem, Notice, Spinner, Stamp } from "./ui";

const VERDICT_ICON = {
  mendukung_aman: { Icon: CircleCheck, color: "var(--aman)", label: "mendukung aman" },
  mendukung_risiko: { Icon: CircleAlert, color: "var(--risiko)", label: "menunjukkan risiko" },
  netral: { Icon: CircleMinus, color: "var(--tinta-3)", label: "netral" },
  tidak_tersedia: { Icon: CircleHelp, color: "var(--tinta-3)", label: "data tidak tersedia" },
} as const;

function mrz(p: PlotDetail): string[] {
  const clean = (s: string) => s.toUpperCase().normalize("NFD").replace(/[^A-Z0-9 ]/g, "").trim().replace(/\s+/g, "<");
  const parts = p.farmer.name.split(" ");
  const last = clean(parts.length > 1 ? parts[parts.length - 1] : parts[0]);
  const first = clean(parts.slice(0, -1).join(" ") || parts[0]);
  const pad = (s: string) => (s + "<".repeat(44)).slice(0, 44);
  const l1 = pad(`PK<IDN${p.code.replace(/-/g, "")}<<${last}<<${first}`);
  const l2 = pad(`${p.area_ha.toFixed(2).replace(".", "")}HA<${clean(p.farmer.village)}<${p.planting_year ?? "0000"}<${(p.risk_level ?? "NA").toUpperCase()}`);
  return [l1, l2];
}

function Evidence({ items }: { items: EvidenceItem[] }) {
  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 10 }}>
      {items.map((it) => {
        const v = VERDICT_ICON[it.verdict];
        return (
          <li key={it.key} style={{ display: "grid", gridTemplateColumns: "20px 1fr", gap: 10 }}>
            <v.Icon size={20} color={v.color} aria-label={v.label} />
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                <span style={{ fontWeight: 550 }}>{it.label}</span>
                <span className="num" style={{ color: v.color, fontWeight: 600, fontSize: 14 }}>{it.value}</span>
              </div>
              <div className="small faint">{it.source}{it.detail ? `. ${it.detail}` : ""}</div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function PassportPanel({
  plot,
  onClose,
  onChanged,
  justAnalyzed,
}: {
  plot: PlotDetail;
  onClose: () => void;
  onChanged: (p: PlotDetail, reanalyzed?: boolean) => void;
  justAnalyzed?: boolean;
}) {
  const [qr, setQr] = useState("");
  const [busy, setBusy] = useState(false);
  const [witness, setWitness] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const a = plot.analysis;
  const eligible = plot.risk_level === "rendah" && plot.consent;

  useEffect(() => {
    QRCode.toString(`PASPORKEBUN:${plot.code}`, { type: "svg", margin: 0, color: { dark: "#14231c", light: "#ffffff" } })
      .then(setQr)
      .catch(() => setQr(""));
  }, [plot.code]);

  const reanalyze = async () => {
    setBusy(true);
    setErr(null);
    try {
      onChanged(await api.analyze(plot.id), true);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const confirmBoundary = async () => {
    if (witness.trim().length < 3) {
      setErr("Tulis nama saksi batas (minimal 3 huruf).");
      return;
    }
    setErr(null);
    onChanged(await api.updatePlot(plot.id, { witness: witness.trim(), boundary_confirmed: true }));
  };

  return (
    <article aria-label={`Paspor kebun ${plot.code}`}>
      <div className="passport-cover">
        <Emblem size={30} />
        <span className="t">Paspor Kebun</span>
        <span className="code">{plot.code}</span>
        <button className="btn btn-quiet" style={{ color: "#fff", marginLeft: 4 }} onClick={onClose} aria-label="Tutup paspor">
          <X />
        </button>
      </div>

      <div style={{ padding: "20px 20px 6px", display: "grid", gridTemplateColumns: "1fr auto", gap: 16, alignItems: "start" }}>
        <div>
          <h2 style={{ fontSize: 21 }}>{plot.farmer.name}</h2>
          <p className="muted">{plot.label}, Desa {plot.farmer.village}</p>
          {a && <p style={{ marginTop: 10, fontWeight: 550 }}>{a.headline}</p>}
        </div>
        <Stamp
          key={a?.id}
          risk={plot.risk_level}
          animate={justAnalyzed}
          sub={a ? `keyakinan ${Math.round(a.confidence * 100)}%` : undefined}
        />
      </div>

      <div style={{ padding: "8px 20px 16px" }}>
        <dl className="facts">
          <div><dt>Luas terukur</dt><dd className="num">{ha(plot.area_ha)}</dd></div>
          <div>
            <dt>Tahun tanam</dt>
            <dd>
              {plot.planting_year_declared ?? "–"} <span className="faint small">(petani)</span>
              {plot.planting_year_detected ? <> / {plot.planting_year_detected} <span className="faint small">(satelit)</span></> : null}
            </dd>
          </div>
          <div><dt>Batas disaksikan</dt><dd>{plot.boundary_confirmed ? plot.witness : <span style={{ color: "var(--cek)" }}>Belum</span>}</dd></div>
          <div>
            <dt>Cara menggambar batas</dt>
            <dd>{plot.delineation_method === "manual" ? "Manual" : "Draf AI, dikoreksi petani"}</dd>
          </div>
          {a?.evidence.protected && (
            <div className="span-2">
              <dt>Status kawasan hutan</dt>
              <dd style={{ color: a.evidence.protected.pct > 5 ? "var(--risiko)" : undefined }}>
                {kawasanText(a.evidence.protected)}{" "}
                <span className="faint small">({KAWASAN_SOURCE_SHORT[a.evidence.protected.source ?? ""] ?? "peta kawasan"})</span>
              </dd>
            </div>
          )}
        </dl>
      </div>

      {(plot.planting_consistency || (plot.overlaps && plot.overlaps.length > 0)) && (
        <div style={{ padding: "0 20px 16px", display: "grid", gap: 8 }}>
          {plot.planting_consistency && <Notice kind="warn">{plot.planting_consistency.message}</Notice>}
          {plot.overlaps?.map((o) => (
            <Notice kind="danger" key={o.plot_id}>
              Batas bertumpuk {ha(o.overlap_ha)} dengan kebun {o.code} ({o.farmer}). Selesaikan lewat musyawarah.
            </Notice>
          ))}
        </div>
      )}

      {!plot.boundary_confirmed && (
        <div className="section">
          <h4>Konfirmasi batas</h4>
          <p className="small muted" style={{ marginBottom: 10 }}>
            Batas kebun sah setelah disaksikan ketua kelompok tani atau tetangga yang berbatasan.
          </p>
          <div style={{ display: "flex", gap: 8 }}>
            <input className="input" placeholder="Nama saksi" value={witness} onChange={(e) => setWitness(e.target.value)} aria-label="Nama saksi batas" />
            <button className="btn" onClick={confirmBoundary}>Konfirmasi</button>
          </div>
        </div>
      )}

      {a && (
        <>
          <div className="section">
            <h3>Bukti satelit</h3>
            <p className="small muted" style={{ marginBottom: 12 }}>
              Keputusan diambil dari kesepakatan beberapa sumber, bukan satu peta. Batas EUDR: tidak ada deforestasi setelah{" "}
              {dateLabel(a.evidence.cutoff)}.
            </p>
            <Evidence items={a.evidence.items} />
            {a.evidence.notes.map((n) => (
              <div key={n} style={{ marginTop: 10 }}>
                <Notice kind={plot.risk_level === "tinggi" ? "danger" : a.evidence.is_replanting ? "ok" : "info"}>{n}</Notice>
              </div>
            ))}
          </div>

          <div className="section">
            <h3>Riwayat vegetasi {a.timeseries.dates?.[0]?.slice(0, 4)}–kini</h3>
            <p className="small muted" style={{ marginBottom: 8 }}>
              NDVI tiap citra Sentinel-2. Garis hijau = model AI (COLD-lite); garis merah = pembukaan lahan terdeteksi.
            </p>
            {a.timeseries.dates ? <NdviChart ts={a.timeseries} cutoff={a.evidence.cutoff} /> : null}
            {a.timeseries.planting_note && <p className="small" style={{ marginTop: 6 }}>{a.timeseries.planting_note}</p>}
          </div>
        </>
      )}

      <div className="section">
        <h3>Paspor &amp; ekspor</h3>
        <div style={{ display: "flex", gap: 16, marginTop: 10, alignItems: "flex-start", flexWrap: "wrap" }}>
          <div className="qr-frame" style={{ opacity: eligible ? 1 : 0.25 }} aria-label={`Kode QR ${plot.code}`} dangerouslySetInnerHTML={{ __html: qr }} />
          <div style={{ flex: 1, minWidth: 180, display: "grid", gap: 10 }}>
            {eligible ? (
              <p className="small">
                QR hanya berisi kode paspor, tanpa nama atau NIK. Pengepul memindainya setiap membeli TBS.
              </p>
            ) : (
              <Notice kind="warn">QR belum berlaku untuk pasar ekspor: status satelit harus Aman dan petani menyetujui berbagi data.</Notice>
            )}
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              <a className="btn" href={api.eudrPlotUrl(plot.id)} download>
                <Download /> GeoJSON EUDR
              </a>
              <button className="btn btn-quiet" onClick={() => window.print()}>
                <Printer /> Cetak
              </button>
            </div>
          </div>
        </div>
        <div className="mrz" style={{ marginTop: 12 }} aria-hidden="true">
          {mrz(plot).map((l) => <div key={l}>{l}</div>)}
        </div>
      </div>

      <div className="section" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span className="small faint">
          {a
            ? `Dianalisis ${dateLabel(a.created_at)}, ${a.compute_ms} ms di CPU. Data: ${a.data_source === "live" ? "satelit live" : "simulasi"}.`
            : "Belum dianalisis."}
        </span>
        <button className="btn btn-quiet" onClick={reanalyze} disabled={busy}>
          {busy ? <Spinner /> : <RefreshCw />} Cek ulang satelit
        </button>
      </div>
      {err && <div style={{ padding: "0 20px 16px" }}><Notice kind="danger">{err}</Notice></div>}
      {a?.data_source === "simulasi" && (
        <div style={{ padding: "0 20px 18px" }}>
          <p className="small faint">
            Mode demo: deret NDVI dan lapisan bukti di kebun ini adalah simulasi berlabel. Aktifkan mode live untuk data Sentinel-2 dan
            Hansen asli.
          </p>
        </div>
      )}
    </article>
  );
}
