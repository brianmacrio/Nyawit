import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Camera, CircleCheck, CircleAlert, Hand, ScanLine } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { DECISION_LABEL, dateTimeLabel, ha, kg } from "../lib/format";
import type { CheckResult, PassportLookup, Txn } from "../lib/types";
import { QrScanner } from "../components/QrScanner";
import { Notice, Spinner, StatusTag } from "../components/ui";

const DEMO_CODES = [
  ["PK-00001-F", "kebun Pak Budi"],
  ["PK-00004-U", "kebun berisiko"],
  ["PK-00006-E", "perlu cek"],
];

function CapacityBar({ used, upper, typical }: { used: number; upper: number; typical: number }) {
  const p = Math.min(100, (used / Math.max(upper, 1)) * 100);
  const color = p > 100 || used > upper ? "var(--risiko)" : p > 85 ? "var(--cek)" : "var(--aman)";
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <div className="capbar" role="meter" aria-valuemin={0} aria-valuemax={upper} aria-valuenow={used} aria-label="Pemakaian kapasitas 30 hari">
        <i style={{ width: `${p}%`, background: color }} />
        <b style={{ left: `${(typical / Math.max(upper, 1)) * 100}%` }} title="Produksi tipikal petani swadaya" />
      </div>
      <div className="small muted num" style={{ display: "flex", justifyContent: "space-between" }}>
        <span>Terjual 30 hari: {kg(used)}</span>
        <span>Batas wajar: {kg(upper)}</span>
      </div>
    </div>
  );
}

export default function Pengepul() {
  const { user, demo } = useAuth();
  const isAdmin = user?.role === "admin";
  const [collectors, setCollectors] = useState<{ id: number; name: string; village: string }[]>([]);
  const [cid, setCid] = useState<number>(user?.collector_id ?? 1);
  const [code, setCode] = useState("");
  const [scan, setScan] = useState(false);
  const [found, setFound] = useState<PassportLookup | null>(null);
  const [weight, setWeight] = useState("");
  const [result, setResult] = useState<{ check: CheckResult; transaction: Txn } | null>(null);
  const [history, setHistory] = useState<Txn[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const loadHistory = useCallback((id: number) => api.transactions(id).then(setHistory).catch(() => setHistory([])), []);
  useEffect(() => {
    api.collectors().then(setCollectors).catch((e) => setErr(e.message));
  }, []);
  useEffect(() => {
    if (user?.collector_id) setCid(user.collector_id);
  }, [user?.collector_id]);
  useEffect(() => {
    loadHistory(cid);
  }, [cid, loadHistory]);

  const lookup = useCallback(async (raw: string) => {
    const c = raw.replace("PASPORKEBUN:", "").trim();
    setScan(false);
    setCode(c);
    setErr(null);
    setResult(null);
    setFound(null);
    if (!c) return;
    setBusy(true);
    try {
      setFound(await api.lookup(c));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, []);

  const record = async (e: React.FormEvent) => {
    e.preventDefault();
    const w = Number(weight.replace(/\./g, "").replace(",", "."));
    if (!found) return;
    if (!w || w <= 0) return setErr("Isi berat TBS dalam kilogram.");
    setBusy(true);
    setErr(null);
    try {
      const r = await api.record(found.plot.code, w, isAdmin ? cid : undefined);
      setResult(r);
      setFound(await api.lookup(found.plot.code));
      loadHistory(cid);
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setFound(null);
    setResult(null);
    setWeight("");
    setCode("");
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Timbang &amp; catat</h1>
          <p className="muted">
            Setiap membeli TBS, pindai paspor kebun lalu catat beratnya. Sistem mengecek apakah volume itu masuk akal untuk kebun tersebut.
          </p>
        </div>
        {isAdmin ? (
          <label className="field" style={{ minWidth: 240 }}>
            <span>Catat atas nama pengepul (admin)</span>
            <select className="select" value={cid} onChange={(e) => { setCid(Number(e.target.value)); reset(); }}>
              {collectors.map((c) => <option key={c.id} value={c.id}>{c.name}, {c.village}</option>)}
            </select>
          </label>
        ) : (
          <div style={{ display: "grid", gap: 6, justifyItems: "end" }}>
            <span className="small muted">Masuk sebagai</span>
            <strong>{collectors.find((c) => c.id === cid)?.name ?? user?.name}</strong>
            {user?.is_demo && (
              <button className="btn btn-quiet small" onClick={() => { reset(); demo(user.username === "sinarjaya" ? "pengepul" : "sinarjaya"); }}>
                Ganti ke {user.username === "sinarjaya" ? "UD Tani Jaya" : "UD Sinar Jaya"} (demo)
              </button>
            )}
          </div>
        )}
      </div>

      <div className="collector">
        <section className="phone" aria-label="Aplikasi pengepul">
          {!found && (
            <>
              <h2 style={{ fontSize: 19 }}>Pindai paspor kebun</h2>
              {scan ? (
                <QrScanner onResult={lookup} onClose={() => setScan(false)} />
              ) : (
                <button className="btn btn-primary btn-lg" onClick={() => setScan(true)}>
                  <Camera /> Buka kamera
                </button>
              )}
              <form onSubmit={(e) => { e.preventDefault(); lookup(code); }} style={{ display: "flex", gap: 8 }}>
                <input className="input num" placeholder="atau ketik kode, mis. PK-00001-F" value={code} onChange={(e) => setCode(e.target.value)} aria-label="Kode paspor" />
                <button className="btn" type="submit" disabled={busy}><ScanLine /> Cari</button>
              </form>
              <div className="small muted" style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                Kode contoh:
                {DEMO_CODES.map(([c, l]) => (
                  <button key={c} className="chip num" onClick={() => lookup(c)} title={l}>{c}</button>
                ))}
              </div>
            </>
          )}
          {busy && !found && <Spinner label="Mencari paspor…" />}

          {found && (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", gap: 8 }}>
                <div>
                  <div className="small faint num">{found.plot.code}</div>
                  <h2 style={{ fontSize: 20 }}>{found.plot.farmer.name}</h2>
                  <div className="small muted">
                    {ha(found.plot.area_ha)}, Desa {found.plot.farmer.village}
                    {found.capacity.age != null ? `, sawit umur ${found.capacity.age} th` : ""}
                  </div>
                </div>
                <StatusTag risk={found.plot.risk_level} />
              </div>
              {found.plot.risk_level === "tinggi" && (
                <Notice kind="danger">{found.plot.risk_headline}. TBS dari kebun ini tidak boleh masuk rantai pasok ekspor.</Notice>
              )}
              <CapacityBar used={found.capacity.used_kg_30d} upper={found.capacity.upper_kg_30d} typical={found.capacity.typical_kg_30d} />
              <div className="small muted">
                {found.days_since_last_sale == null
                  ? "Belum ada penjualan tercatat. "
                  : found.days_since_last_sale === 0
                    ? "Sudah ada penjualan hari ini. "
                    : `Penjualan terakhir ${found.days_since_last_sale} hari lalu. `}
                Sisa wajar 30 hari: <strong className="num">{kg(found.capacity.remaining_kg)}</strong>
              </div>

              {!result ? (
                <form onSubmit={record} style={{ display: "grid", gap: 10 }}>
                  <label className="field">
                    <span>Berat TBS di timbangan (kg)</span>
                    <input className="input weight-input" inputMode="decimal" autoFocus value={weight} onChange={(e) => setWeight(e.target.value.replace(/[^\d.,]/g, ""))} placeholder="0" />
                  </label>
                  <button className="btn btn-primary btn-lg" type="submit" disabled={busy}>
                    {busy ? <Spinner /> : null} Catat pembelian
                  </button>
                  <button className="btn btn-quiet" type="button" onClick={reset}>Pindai kebun lain</button>
                </form>
              ) : (
                <>
                  <div className={`verdict verdict-${result.check.decision}`} role="status">
                    <div className="big">
                      {result.check.decision === "diterima" ? <CircleCheck /> : result.check.decision === "catatan" ? <CircleAlert /> : <Hand />}
                      {DECISION_LABEL[result.check.decision]}
                    </div>
                    <div className="num">{kg(result.transaction.weight_kg)} dari {found.plot.code}</div>
                    {result.check.flags.map((f) => (
                      <div key={f.code} style={{ borderTop: "1px solid rgba(0,0,0,0.08)", paddingTop: 8 }}>
                        <strong>{f.title}</strong>
                        <div className="small">{f.detail}</div>
                      </div>
                    ))}
                    {result.check.decision === "ditahan" && (
                      <div className="small">Pembelian tercatat tetapi tidak dihitung sebagai TBS tertelusur. Pabrik menerima peringatan.</div>
                    )}
                  </div>
                  <button className="btn btn-primary btn-lg" onClick={reset}>Pindai kebun berikutnya</button>
                </>
              )}
            </>
          )}
          {err && <Notice kind="danger">{err}</Notice>}
        </section>

        <section className="panel panel-pad" aria-label="Riwayat pembelian">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
            <h2 style={{ fontSize: 19 }}>Riwayat pembelian</h2>
            <Link to="/pabrik" className="small">Lihat dari sisi pabrik</Link>
          </div>
          {history.length === 0 && <p className="muted small">Belum ada pembelian tercatat.</p>}
          <div>
            {history.slice(0, 14).map((t) => (
              <div className="txn" key={t.id}>
                <span><strong>{t.farmer}</strong> <span className="faint small num">{t.plot_code}</span></span>
                <span className="num" style={{ fontWeight: 600, textAlign: "right" }}>{kg(t.weight_kg)}</span>
                <span className="small muted">{dateTimeLabel(t.created_at)}{t.flags[0] ? `, ${t.flags[0].title}` : ""}</span>
                <span style={{ textAlign: "right" }}>
                  <span className={`tag tag-${t.decision === "diterima" ? "rendah" : t.decision === "catatan" ? "perlu_cek" : "tinggi"}`}>
                    {DECISION_LABEL[t.decision].replace(" dengan catatan", "*")}
                  </span>
                </span>
              </div>
            ))}
          </div>
          <p className="small faint" style={{ marginTop: 10 }}>* diterima dengan catatan</p>
        </section>
      </div>
    </div>
  );
}
