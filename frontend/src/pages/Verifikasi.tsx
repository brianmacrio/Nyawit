import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Camera, ClipboardCheck, LocateFixed, ShieldCheck, Shuffle } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dateLabel, dateTimeLabel, ha } from "../lib/format";
import { getFix } from "../lib/gps";
import type { Appeal, AuditEvent, Inspection } from "../lib/types";
import { Notice, Spinner, StatusTag } from "../components/ui";

type Tab = "inspeksi" | "keberatan" | "integritas";

/** Memperkecil foto di peramban (maks 1600 px, JPEG) agar unggahan ringan; server tetap memvalidasi ulang. */
async function shrink(file: File): Promise<string> {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((ok, bad) => {
      const i = new Image();
      i.onload = () => ok(i);
      i.onerror = () => bad(new Error("Berkas bukan gambar."));
      i.src = url;
    });
    const k = Math.min(1, 1600 / Math.max(img.width, img.height));
    const c = document.createElement("canvas");
    c.width = Math.round(img.width * k);
    c.height = Math.round(img.height * k);
    c.getContext("2d")!.drawImage(img, 0, 0, c.width, c.height);
    return c.toDataURL("image/jpeg", 0.82);
  } finally {
    URL.revokeObjectURL(url);
  }
}

function InspectionForm({ item, onDone }: { item: Inspection; onDone: (warnings: string[]) => void }) {
  const [result, setResult] = useState<"sesuai" | "tidak_sesuai">("sesuai");
  const [notes, setNotes] = useState("");
  const [photo, setPhoto] = useState<string | null>(null);
  const [pos, setPos] = useState<{ lat: number; lng: number; acc: number; sim?: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const locate = async () => {
    setErr(null);
    try {
      const f = await getFix();
      setPos({ lat: f.lat, lng: f.lng, acc: f.accuracy });
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  const submit = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await api.inspectionResult(item.id, {
        result,
        notes: notes.trim() || undefined,
        photo: photo ?? undefined,
        lat: pos?.lat,
        lng: pos?.lng,
      });
      onDone(r.warnings);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="form-grid insp-form">
      <div role="radiogroup" aria-label="Hasil inspeksi" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="chip" aria-pressed={result === "sesuai"} onClick={() => setResult("sesuai")}>Sesuai dengan paspor</button>
        <button type="button" className="chip" aria-pressed={result === "tidak_sesuai"} onClick={() => setResult("tidak_sesuai")}>Tidak sesuai</button>
      </div>
      <textarea rows={2} placeholder="Catatan: batas, patok, umur tanaman, tanda pembukaan baru…" value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={1000} aria-label="Catatan inspeksi" />
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <label className="btn">
          <Camera /> {photo ? "Ganti foto" : "Foto lapangan"}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            capture="environment"
            hidden
            onChange={async (e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              try {
                setPhoto(await shrink(f));
                if (!pos) locate();
              } catch (e2) {
                setErr((e2 as Error).message);
              }
            }}
          />
        </label>
        <button type="button" className="btn btn-quiet" onClick={locate}><LocateFixed /> Lokasi saya</button>
        <button type="button" className="btn btn-quiet small" onClick={() => setPos({ lat: item.centroid[0], lng: item.centroid[1], acc: 0, sim: true })} title="Untuk demo di laptop tanpa GPS">
          Simulasi: di tengah kebun
        </button>
      </div>
      {photo && <img src={photo} alt="Pratinjau foto inspeksi" className="insp-photo" />}
      {pos && (
        <p className="small muted">
          Lokasi {pos.sim ? "(simulasi) " : ""}{pos.lat.toFixed(6)}, {pos.lng.toFixed(6)}{pos.acc ? ` ±${Math.round(pos.acc)} m` : ""}. Jarak ke kebun dihitung server.
        </p>
      )}
      <p className="small faint">Metadata foto (EXIF) dibuang di server; yang disimpan hanya gambar, waktu, dan titik lokasi inspeksi.</p>
      {err && <Notice kind="danger">{err}</Notice>}
      <button className="btn btn-primary" onClick={submit} disabled={busy} style={{ justifySelf: "start" }}>
        {busy ? <Spinner /> : <ClipboardCheck />} Simpan hasil inspeksi
      </button>
    </div>
  );
}

function AppealCard({ a, canDecide, onDone }: { a: Appeal; canDecide: boolean; onDone: () => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const decide = async (accept: boolean, risk?: "rendah" | "perlu_cek") => {
    if (note.trim().length < 10) return setErr("Tulis alasan keputusan (minimal 10 huruf). Alasan ikut tercatat di riwayat.");
    setBusy(true);
    setErr(null);
    try {
      await api.decideAppeal(a.id, accept, note.trim(), risk);
      onDone();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="panel panel-pad appeal">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <div>
          <Link to={`/peta?kebun=${a.plot_id}`}><strong>{a.plot_code}</strong></Link> <span className="muted">{a.farmer}</span>
          <div className="small muted">Diajukan {a.submitted_by}, {dateLabel(a.created_at)}. Status saat diajukan: {a.original_risk}</div>
        </div>
        <span className={`tag tag-${a.status === "diajukan" ? "perlu_cek" : a.status === "diterima" ? "rendah" : "tinggi"}`}>{a.status}</span>
      </div>
      <p style={{ marginTop: 8 }}>{a.reason}</p>
      <p className="small faint">Bukti: {a.evidence_type.replace("_", " ")}. Status satelit kini: {a.headline}</p>
      {a.status !== "diajukan" && (
        <p className="small" style={{ marginTop: 6 }}>Keputusan {a.decided_by}{a.decided_at ? `, ${dateLabel(a.decided_at)}` : ""}: {a.decision_note}</p>
      )}
      {a.status === "diajukan" && canDecide && (
        <div className="form-grid" style={{ marginTop: 10 }}>
          <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Alasan keputusan (wajib, tercatat di riwayat)" aria-label="Alasan keputusan" maxLength={1000} />
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="btn" disabled={busy} onClick={() => decide(true, "perlu_cek")}>Terima: jadikan Perlu cek</button>
            <button className="btn" disabled={busy} onClick={() => decide(true, "rendah")}>Terima: jadikan Aman</button>
            <button className="btn btn-danger" disabled={busy} onClick={() => decide(false)}>Tolak</button>
          </div>
          <p className="small faint">Bila satelit kemudian menemukan bukti baru, keputusan ini otomatis gugur dan kebun ditinjau ulang.</p>
          {err && <Notice kind="danger">{err}</Notice>}
        </div>
      )}
    </div>
  );
}

export default function Verifikasi() {
  const { can } = useAuth();
  const isVerifier = can("verifikator");
  const [tab, setTab] = useState<Tab>("inspeksi");
  const [insp, setInsp] = useState<{ sample_size: number; n_plots: number; formula: string; items: Inspection[] } | null>(null);
  const [appeals, setAppeals] = useState<Appeal[] | null>(null);
  const [chain, setChain] = useState<{ ok: boolean; message: string; events: number } | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [open, setOpen] = useState<number | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "warn" | "danger"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.inspections().then(setInsp).catch((e) => setMsg({ kind: "danger", text: e.message }));
    api.appeals().then(setAppeals).catch(() => setAppeals([]));
  }, []);
  useEffect(load, [load]);
  useEffect(() => {
    if (tab !== "integritas") return;
    api.auditVerify().then(setChain).catch(() => setChain(null));
    api.auditRecent(40).then(setEvents).catch(() => setEvents([]));
  }, [tab]);

  const sample = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.makeSample();
      setMsg({ kind: "ok", text: r.created ? `${r.created} kebun ditambahkan ke sampel ${r.batch}.` : "Sampel sudah penuh; selesaikan inspeksi yang menunggu dulu." });
      load();
    } catch (e) {
      setMsg({ kind: "danger", text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const pending = insp?.items.filter((i) => i.status === "menunggu") ?? [];
  const done = insp?.items.filter((i) => i.status === "selesai") ?? [];
  const openAppeals = appeals?.filter((a) => a.status === "diajukan").length ?? 0;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Verifikasi independen</h1>
          <p className="muted">
            Aplikasi tidak memverifikasi dirinya sendiri. Verifikator dari luar koperasi mengunjungi sampel kebun yang dipilih berdasarkan
            risiko, dan memutuskan keberatan dengan alasan tertulis.
          </p>
        </div>
        {!isVerifier && <span className="small muted">Mode lihat saja. Tindakan hanya untuk verifikator.</span>}
      </div>

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "inspeksi"} onClick={() => setTab("inspeksi")}>Inspeksi lapangan {pending.length ? <b>{pending.length}</b> : null}</button>
        <button role="tab" aria-selected={tab === "keberatan"} onClick={() => setTab("keberatan")}>Keberatan {openAppeals ? <b>{openAppeals}</b> : null}</button>
        <button role="tab" aria-selected={tab === "integritas"} onClick={() => setTab("integritas")}>Integritas data</button>
      </div>
      {msg && <div style={{ marginBottom: 12 }}><Notice kind={msg.kind}>{msg.text}</Notice></div>}

      {tab === "inspeksi" && (
        <>
          <section className="panel panel-pad" style={{ marginBottom: 16, display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
            <div>
              <strong>Ukuran sampel: {insp?.sample_size ?? "…"} dari {insp?.n_plots ?? "…"} kebun</strong>
              <div className="small muted">Rumus {insp?.formula}. Kebun berisiko, perlu cek, bersengketa, atau berbukti lemah dipilih lebih dulu; sisanya diundi berbobot luas.</div>
            </div>
            {isVerifier && <button className="btn btn-primary" onClick={sample} disabled={busy}>{busy ? <Spinner /> : <Shuffle />} Lengkapi sampel bulan ini</button>}
          </section>
          <section className="panel">
            <div className="panel-pad" style={{ paddingBottom: 4 }}><h2 style={{ fontSize: 18 }}>Menunggu kunjungan ({pending.length})</h2></div>
            {!insp && <div className="panel-pad"><Spinner /></div>}
            {pending.map((i) => (
              <div key={i.id} className="insp-row">
                <div className="insp-main">
                  <div>
                    <Link to={`/peta?kebun=${i.plot_id}`}><strong className="num">{i.plot_code}</strong></Link> {i.farmer}
                    <div className="small muted">Desa {i.village}, {ha(i.area_ha)} · {i.reason_label}</div>
                  </div>
                  <StatusTag risk={i.risk_level} />
                  {isVerifier && (
                    <button className="btn" onClick={() => setOpen(open === i.id ? null : i.id)}>{open === i.id ? "Tutup" : "Isi hasil"}</button>
                  )}
                </div>
                {open === i.id && (
                  <InspectionForm
                    item={i}
                    onDone={(w) => {
                      setOpen(null);
                      setMsg(w.length ? { kind: "warn", text: `Tersimpan. ${w.join(" ")}` } : { kind: "ok", text: `Hasil inspeksi ${i.plot_code} tersimpan dan tercatat di riwayat.` });
                      load();
                    }}
                  />
                )}
              </div>
            ))}
            {insp && !pending.length && <p className="panel-pad small muted">Tidak ada inspeksi yang menunggu.</p>}
          </section>
          <section className="panel" style={{ marginTop: 16 }}>
            <div className="panel-pad" style={{ paddingBottom: 4 }}><h2 style={{ fontSize: 18 }}>Selesai ({done.length})</h2></div>
            <div style={{ overflowX: "auto" }}>
              <table className="table">
                <thead><tr><th>Kebun</th><th>Hasil</th><th>Inspektur</th><th>Tanggal</th><th>Bukti</th></tr></thead>
                <tbody>
                  {done.slice(0, 30).map((i) => (
                    <tr key={i.id}>
                      <td><Link to={`/peta?kebun=${i.plot_id}`} className="num">{i.plot_code}</Link><div className="small faint">{i.farmer}</div></td>
                      <td>
                        <span className={`tag tag-${i.result === "sesuai" ? "rendah" : "tinggi"}`}>{i.result === "sesuai" ? "Sesuai" : "Tidak sesuai"}</span>
                        {i.notes && <div className="small muted" style={{ maxWidth: 360 }}>{i.notes}</div>}
                      </td>
                      <td className="small">{i.inspector}</td>
                      <td className="small num">{i.done_at ? dateLabel(i.done_at) : "–"}</td>
                      <td className="small">
                        {i.has_photo ? <a href={api.inspectionPhotoUrl(i.id)} target="_blank" rel="noreferrer">Foto</a> : "Tanpa foto"}
                        {i.photo_distance_m != null && (
                          <span style={{ color: i.photo_distance_m > 150 ? "var(--risiko)" : undefined }}> · {Math.round(i.photo_distance_m)} m dari kebun</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {tab === "keberatan" && (
        <div style={{ display: "grid", gap: 12 }}>
          {!appeals && <Spinner />}
          {appeals?.length === 0 && <p className="muted">Belum ada keberatan.</p>}
          {appeals?.map((a) => <AppealCard key={a.id} a={a} canDecide={isVerifier} onDone={load} />)}
        </div>
      )}

      {tab === "integritas" && (
        <section className="panel panel-pad">
          <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12 }}>
            <ShieldCheck color={chain?.ok ? "var(--aman)" : "var(--risiko)"} aria-hidden="true" />
            {chain ? <strong>{chain.message}</strong> : <Spinner label="Memeriksa rantai riwayat…" />}
          </div>
          <p className="small muted" style={{ marginBottom: 12 }}>
            Setiap kejadian menyimpan sidik SHA-256 dari isinya dan dari kejadian sebelumnya. Bila satu baris di database diubah diam-diam,
            pemeriksaan ini menunjukkan baris pertama yang tidak cocok.
          </p>
          <ol className="audit-list">
            {events.map((e) => (
              <li key={e.id}>
                <span className="small faint num">{dateTimeLabel(e.at)}</span>
                <span className="small">{e.summary}</span>
                <span className="small faint">{e.actor} · #{e.hash}</span>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
