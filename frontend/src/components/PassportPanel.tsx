import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import QRCode from "qrcode";
import {
  BadgeCheck,
  CircleAlert,
  CircleCheck,
  CircleHelp,
  CircleMinus,
  CircleX,
  Download,
  ExternalLink,
  History,
  IdCard,
  RefreshCw,
  X,
} from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dateLabel, dateTimeLabel, ha, KAWASAN_SOURCE_SHORT, kawasanText, riskLabel } from "../lib/format";
import type { EvidenceItem, EvidenceType, LandProof, PlotDetail, SideKey, StdbStatus } from "../lib/types";
import { NdviChart } from "./NdviChart";
import { Emblem, Notice, Spinner, Stamp } from "./ui";

const VERDICT_ICON = {
  mendukung_aman: { Icon: CircleCheck, color: "var(--aman)", label: "mendukung aman" },
  mendukung_risiko: { Icon: CircleAlert, color: "var(--risiko)", label: "menunjukkan risiko" },
  netral: { Icon: CircleMinus, color: "var(--tinta-3)", label: "netral" },
  tidak_tersedia: { Icon: CircleHelp, color: "var(--tinta-3)", label: "data tidak tersedia" },
} as const;

const SIDE_LABEL: Record<string, string> = {
  parit: "Parit/kanal",
  jalan: "Jalan",
  kebun: "Kebun tetangga",
  hutan: "Hutan/semak",
  sungai: "Sungai",
  lainnya: "Lainnya",
};
const EVIDENCE_OPTS: [EvidenceType, string][] = [
  ["foto_lapangan", "Foto lapangan / kesaksian"],
  ["sk_pelepasan", "SK pelepasan kawasan hutan"],
  ["sertifikat", "Sertifikat tanah"],
  ["surat_desa", "Surat keterangan desa"],
  ["lainnya", "Lainnya"],
];
const ACTION_LABEL: Record<string, string> = {
  kebun_didaftarkan: "Didaftarkan",
  cek_satelit: "Cek satelit",
  kebun_diubah: "Data diubah",
  saksi_batas: "Saksi batas",
  inspeksi_selesai: "Inspeksi",
  keberatan_diajukan: "Keberatan",
  keberatan_diputuskan: "Keputusan",
  transaksi_ditandai: "Transaksi",
};

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

function ReadinessCard({ plot }: { plot: PlotDetail }) {
  const r = plot.readiness;
  return (
    <div className={`ready-card ${r.ready ? "ok" : "no"}`}>
      <div className="ready-head">
        {r.ready ? <BadgeCheck aria-hidden="true" /> : <CircleAlert aria-hidden="true" />}
        <div>
          <strong>{r.ready ? "Siap EUDR" : "Belum siap EUDR"}</strong>
          <div className="small">
            {r.ready
              ? r.valid_until ? `Berlaku sampai ${dateLabel(r.valid_until)}, selama satelit tidak menemukan pembukaan baru.` : ""
              : `${r.missing} syarat belum terpenuhi.`}
            {r.expired && " Status kedaluwarsa: cek ulang satelit."}
          </div>
        </div>
      </div>
      <ul className="checklist">
        {r.checks.map((c) => (
          <li key={c.key}>
            {c.ok ? <CircleCheck color="var(--aman)" aria-label="terpenuhi" /> : <CircleX color="var(--risiko)" aria-label="belum terpenuhi" />}
            <span>
              <strong>{c.label}</strong>
              <span className="small muted"> {c.detail}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function LandEditor({ plot, onSaved }: { plot: PlotDetail; onSaved: (p: PlotDetail) => void }) {
  const [f, setF] = useState({
    land_proof: (plot.land.proof ?? "") as LandProof | "",
    land_proof_ref: plot.land.ref ?? "",
    stdb_status: plot.land.stdb_status as StdbStatus,
    stdb_number: plot.land.stdb_number ?? "",
    dispute: plot.land.dispute,
    dispute_note: plot.land.dispute_note ?? "",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const save = async () => {
    setBusy(true);
    setErr(null);
    try {
      onSaved(
        await api.updatePlot(plot.id, {
          land_proof: f.land_proof || null,
          land_proof_ref: f.land_proof_ref.trim() || null,
          stdb_status: f.stdb_status,
          stdb_number: f.stdb_number.trim() || null,
          dispute: f.dispute,
          dispute_note: f.dispute ? f.dispute_note.trim() || null : null,
        }),
      );
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="form-grid" style={{ marginTop: 10 }}>
      <div className="two">
        <label className="field"><span>Bukti penguasaan</span>
          <select className="select" value={f.land_proof} onChange={(e) => setF({ ...f, land_proof: e.target.value as LandProof | "" })}>
            <option value="">Belum ada</option>
            <option value="sertifikat">Sertifikat tanah (SHM/BPN)</option>
            <option value="surat_desa">Surat keterangan desa (SKT/SKGR)</option>
            <option value="pernyataan">Pernyataan + 2 saksi</option>
          </select>
        </label>
        <label className="field"><span>Nomor dokumen</span><input className="input" value={f.land_proof_ref} onChange={(e) => setF({ ...f, land_proof_ref: e.target.value })} /></label>
      </div>
      <div className="two">
        <label className="field"><span>STDB</span>
          <select className="select" value={f.stdb_status} onChange={(e) => setF({ ...f, stdb_status: e.target.value as StdbStatus })}>
            <option value="belum">Belum diurus</option>
            <option value="proses">Sedang diurus</option>
            <option value="ada">Sudah terbit</option>
          </select>
        </label>
        <label className="field"><span>Nomor STDB</span><input className="input" value={f.stdb_number} onChange={(e) => setF({ ...f, stdb_number: e.target.value })} /></label>
      </div>
      <label className="check"><input type="checkbox" checked={f.dispute} onChange={(e) => setF({ ...f, dispute: e.target.checked })} /><span>Ada sengketa atas lahan ini</span></label>
      {f.dispute && <input className="input" value={f.dispute_note} onChange={(e) => setF({ ...f, dispute_note: e.target.value })} placeholder="Keterangan sengketa" aria-label="Keterangan sengketa" />}
      {err && <Notice kind="danger">{err}</Notice>}
      <button className="btn" onClick={save} disabled={busy} style={{ justifySelf: "start" }}>{busy ? <Spinner /> : null} Simpan data lahan</button>
    </div>
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
  const { can } = useAuth();
  const isKoperasi = can("koperasi");
  const [qr, setQr] = useState("");
  const [busy, setBusy] = useState(false);
  const [witness, setWitness] = useState({ name: "", relation: "tetangga" });
  const [editLand, setEditLand] = useState(false);
  const [appeal, setAppeal] = useState({ open: false, reason: "", evidence: "foto_lapangan" as EvidenceType });
  const [err, setErr] = useState<string | null>(null);
  const a = plot.analysis;
  const r = plot.readiness;
  const pendingAppeal = plot.appeals.find((x) => x.status === "diajukan");

  useEffect(() => {
    QRCode.toString(`PASPORKEBUN:${plot.code}`, { type: "svg", margin: 0, color: { dark: "#14231c", light: "#ffffff" } })
      .then(setQr)
      .catch(() => setQr(""));
  }, [plot.code]);
  useEffect(() => {
    setEditLand(false);
    setAppeal({ open: false, reason: "", evidence: "foto_lapangan" });
    setErr(null);
  }, [plot.id]);

  const run = async (fn: () => Promise<PlotDetail>, re = false) => {
    setBusy(true);
    setErr(null);
    try {
      onChanged(await fn(), re);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const addWitness = () => {
    if (witness.name.trim().length < 3) return setErr("Tulis nama saksi (minimal 3 huruf).");
    run(() => api.addWitness(plot.id, { name: witness.name.trim(), relation: witness.relation })).then(() =>
      setWitness({ name: "", relation: "tetangga" }),
    );
  };
  const submitAppeal = () => {
    if (appeal.reason.trim().length < 10) return setErr("Tulis alasan keberatan (minimal 10 huruf).");
    run(async () => {
      await api.createAppeal(plot.id, appeal.reason.trim(), appeal.evidence);
      return api.plot(plot.id);
    }).then(() => setAppeal({ open: false, reason: "", evidence: "foto_lapangan" }));
  };

  const sides = Object.entries(plot.boundary_sides ?? {}) as [SideKey, { jenis: string; tetangga?: string | null }][];

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
          {a && <p style={{ marginTop: 10, fontWeight: 550 }}>{plot.override ? plot.risk_headline : a.headline}</p>}
          {plot.override && (
            <p className="small" style={{ marginTop: 4, color: "var(--cek)" }}>
              Hasil satelit: {riskLabel(plot.override.original)}. Diubah {plot.override.by} ({dateLabel(plot.override.at)}): {plot.override.reason}
            </p>
          )}
        </div>
        <Stamp key={a?.id} risk={plot.risk_level} animate={justAnalyzed} sub={a ? `keyakinan ${Math.round(a.confidence * 100)}%` : undefined} />
      </div>

      <div style={{ padding: "8px 20px 16px" }}>
        <ReadinessCard plot={plot} />
      </div>

      <div style={{ padding: "0 20px 16px" }}>
        <dl className="facts">
          <div><dt>Luas terukur</dt><dd className="num">{ha(plot.area_ha)}</dd></div>
          <div>
            <dt>Tahun tanam</dt>
            <dd>
              {plot.planting_year_declared ?? "–"} <span className="faint small">(petani)</span>
              {plot.planting_year_detected ? <> / {plot.planting_year_detected} <span className="faint small">(satelit)</span></> : null}
            </dd>
          </div>
          <div className="span-2">
            <dt>Ketelitian lokasi</dt>
            <dd>
              <span className="tier" role="img" aria-label={`tingkat ${r.precision.level} dari ${r.precision.of}`}>
                {Array.from({ length: r.precision.of }, (_, i) => <i key={i} className={i < r.precision.level ? "on" : ""} />)}
              </span>{" "}
              {r.precision.label}
              {plot.gps && <span className="faint small"> · titik GPS ±{Math.round(plot.gps.accuracy_m ?? 0)} m</span>}
            </dd>
          </div>
          <div>
            <dt>Bukti lahan</dt>
            <dd>{plot.land.proof_label ?? <span style={{ color: "var(--cek)" }}>Belum ada</span>}{plot.land.ref ? <span className="faint small"> · {plot.land.ref}</span> : null}</dd>
          </div>
          <div>
            <dt>STDB</dt>
            <dd style={{ color: plot.land.stdb_status === "belum" ? "var(--cek)" : undefined }}>
              {plot.land.stdb_label}{plot.land.stdb_number ? <span className="faint small"> · {plot.land.stdb_number}</span> : null}
            </dd>
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
        {plot.land.dispute && <div style={{ marginTop: 10 }}><Notice kind="warn">Sengketa dinyatakan: {plot.land.dispute_note ?? "tanpa keterangan"}</Notice></div>}
        {isKoperasi && (
          <button className="btn btn-quiet small" style={{ marginTop: 6 }} onClick={() => setEditLand(!editLand)}>
            {editLand ? "Tutup" : "Lengkapi data lahan"}
          </button>
        )}
        {editLand && <LandEditor plot={plot} onSaved={(p) => { setEditLand(false); onChanged(p); }} />}
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

      <div className="section">
        <h3>Batas &amp; saksi</h3>
        {sides.length > 0 ? (
          <ul className="sides">
            {sides.map(([k, v]) => (
              <li key={k}><span className="side-k">{k}</span> {SIDE_LABEL[v.jenis] ?? v.jenis}{v.tetangga ? `: ${v.tetangga}` : ""}</li>
            ))}
          </ul>
        ) : (
          <p className="small muted">Ciri batas tiap sisi belum dicatat.</p>
        )}
        <div style={{ marginTop: 10 }}>
          {plot.witnesses.length ? (
            <ul className="witnesses">
              {plot.witnesses.map((w) => (
                <li key={w.name}><strong>{w.name}</strong> <span className="small muted">{w.relation}{w.at ? `, ${dateLabel(w.at)}` : ""}</span></li>
              ))}
            </ul>
          ) : (
            <Notice kind="warn">Batas belum disaksikan. Batas sah setelah disaksikan ketua kelompok tani atau tetangga yang berbatasan.</Notice>
          )}
        </div>
        {isKoperasi && (
          <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
            <input className="input" style={{ flex: "1 1 160px" }} placeholder="Nama saksi" value={witness.name} onChange={(e) => setWitness({ ...witness, name: e.target.value })} aria-label="Nama saksi batas" />
            <select className="select" style={{ flex: "0 1 160px" }} value={witness.relation} onChange={(e) => setWitness({ ...witness, relation: e.target.value })} aria-label="Hubungan saksi">
              {["tetangga", "ketua kelompok tani", "kepala dusun", "saksi lain"].map((x) => <option key={x}>{x}</option>)}
            </select>
            <button className="btn" onClick={addWitness} disabled={busy}>Tambah saksi</button>
          </div>
        )}
      </div>

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
                <Notice kind={a.risk_level === "tinggi" ? "danger" : a.evidence.is_replanting ? "ok" : "info"}>{n}</Notice>
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
        <h3>Verifikasi &amp; keberatan</h3>
        {plot.inspections.length === 0 && <p className="small muted">Belum pernah terpilih sampel inspeksi lapangan.</p>}
        {plot.inspections.map((i) => (
          <div key={i.id} className="mini-row">
            <span className={`tag tag-${i.status === "menunggu" ? "perlu_cek" : i.result === "sesuai" ? "rendah" : "tinggi"}`}>
              {i.status === "menunggu" ? "Menunggu" : i.result === "sesuai" ? "Sesuai" : "Tidak sesuai"}
            </span>
            <span className="small">Inspeksi {i.batch}{i.inspector ? `, ${i.inspector}` : ""}{i.done_at ? `, ${dateLabel(i.done_at)}` : ""}{i.notes ? `: ${i.notes}` : ""}</span>
          </div>
        ))}
        {plot.appeals.map((ap) => (
          <div key={ap.id} className="mini-row">
            <span className={`tag tag-${ap.status === "diajukan" ? "perlu_cek" : ap.status === "diterima" ? "rendah" : "tinggi"}`}>
              Keberatan {ap.status}
            </span>
            <span className="small">{ap.reason}{ap.decision_note ? ` Keputusan: ${ap.decision_note}` : ""}</span>
          </div>
        ))}
        {isKoperasi && plot.risk_level !== "rendah" && !pendingAppeal && (
          appeal.open ? (
            <div className="form-grid" style={{ marginTop: 10 }}>
              <label className="field"><span>Bukti yang dilampirkan</span>
                <select className="select" value={appeal.evidence} onChange={(e) => setAppeal({ ...appeal, evidence: e.target.value as EvidenceType })}>
                  {EVIDENCE_OPTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </label>
              <label className="field"><span>Alasan keberatan</span>
                <textarea rows={3} value={appeal.reason} onChange={(e) => setAppeal({ ...appeal, reason: e.target.value })} maxLength={1000} placeholder="mis. Lahan ini kebun karet sejak 2012; ada SK pelepasan kawasan No. …" />
              </label>
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn" onClick={submitAppeal} disabled={busy}>Ajukan ke verifikator</button>
                <button className="btn btn-quiet" onClick={() => setAppeal({ ...appeal, open: false })}>Batal</button>
              </div>
            </div>
          ) : (
            <button className="btn btn-quiet small" style={{ marginTop: 6 }} onClick={() => setAppeal({ ...appeal, open: true })}>
              Ajukan keberatan atas status ini
            </button>
          )
        )}
      </div>

      <div className="section">
        <h3>Paspor &amp; ekspor</h3>
        <div style={{ display: "flex", gap: 16, marginTop: 10, alignItems: "flex-start", flexWrap: "wrap" }}>
          <div className="qr-frame" role="img" style={{ opacity: r.ready ? 1 : 0.35 }} aria-label={`Kode QR ${plot.code}`} dangerouslySetInnerHTML={{ __html: qr }} />
          <div style={{ flex: 1, minWidth: 180, display: "grid", gap: 10 }}>
            {r.ready ? (
              <p className="small">QR hanya berisi kode paspor, tanpa nama atau NIK. Pengepul memindainya setiap membeli TBS.</p>
            ) : (
              <Notice kind="warn">QR tetap bisa dipindai, tetapi TBS dari kebun ini belum boleh masuk pengiriman ekspor sampai semua syarat terpenuhi.</Notice>
            )}
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              <Link className="btn" to={`/kartu/${plot.id}`}><IdCard /> Kartu untuk petani</Link>
              <a className="btn btn-quiet" href={api.eudrPlotUrl(plot.id)} download><Download /> GeoJSON</a>
              <Link className="btn btn-quiet" to={`/cek/${plot.code}`} target="_blank"><ExternalLink /> Tampilan publik</Link>
            </div>
          </div>
        </div>
        <div className="mrz" style={{ marginTop: 12 }} aria-hidden="true">
          {mrz(plot).map((l) => <div key={l}>{l}</div>)}
        </div>
      </div>

      <details className="section history">
        <summary><History size={16} aria-hidden="true" /> Riwayat perubahan ({plot.history.length})</summary>
        <p className="small faint" style={{ margin: "6px 0 8px" }}>Setiap baris dikunci hash baris sebelumnya, jadi perubahan diam-diam bisa dideteksi.</p>
        <ol>
          {plot.history.map((h) => (
            <li key={h.id}>
              <span className="small faint num">{dateTimeLabel(h.at)}</span>
              <span><strong>{ACTION_LABEL[h.action] ?? h.action}</strong> <span className="small">{h.summary}</span></span>
              <span className="small faint">{h.actor} · #{h.hash}</span>
            </li>
          ))}
        </ol>
      </details>

      <div className="section" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span className="small faint">
          {a
            ? `Dianalisis ${dateLabel(a.created_at)}, ${a.compute_ms} ms di CPU. Data: ${
                a.data_source === "live" ? "satelit live" : a.data_source === "peta_nyata" ? "peta hutan & kehilangan tutupan nyata (GFW), NDVI simulasi" : "simulasi"
              }.`
            : "Belum dianalisis."}
        </span>
        {can("koperasi", "verifikator") && (
          <button className="btn btn-quiet" onClick={() => run(() => api.analyze(plot.id), true)} disabled={busy}>
            {busy ? <Spinner /> : <RefreshCw />} Cek ulang satelit
          </button>
        )}
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
      {a?.data_source === "peta_nyata" && (
        <div style={{ padding: "0 20px 18px" }}>
          <p className="small faint">
            Mode demo: hutan 2020 (JRC) dan kehilangan tutupan pohon (Hansen) dibaca dari peta nyata Global Forest Watch, sama
            dengan lapisan di Peta Kebun. Hanya deret NDVI yang masih simulasi; mode live membaca Sentinel-2 asli.
          </p>
        </div>
      )}
    </article>
  );
}
