import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { CircleCheck, CircleX, Search } from "lucide-react";
import { api } from "../lib/api";
import { dateLabel, ha } from "../lib/format";
import type { PublicPassport } from "../lib/types";
import { Emblem, Notice, Spinner, Stamp } from "../components/ui";

/** Cek paspor tanpa login: untuk pembeli atau siapa pun yang memindai QR. Nama petani disamarkan. */
export default function CekPaspor() {
  const { code } = useParams();
  const nav = useNavigate();
  const [q, setQ] = useState(code ?? "");
  const [data, setData] = useState<PublicPassport | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!code) return;
    setBusy(true);
    setErr(null);
    setData(null);
    api
      .publicPassport(code)
      .then(setData)
      .catch((e) => setErr(e.message))
      .finally(() => setBusy(false));
  }, [code]);

  return (
    <div className="page" style={{ maxWidth: 760 }}>
      <div className="page-head">
        <div>
          <h1>Cek paspor kebun</h1>
          <p className="muted">Masukkan kode di bawah QR. Halaman ini publik: nama petani disamarkan dan lokasi tepat tidak ditampilkan.</p>
        </div>
      </div>
      <form
        onSubmit={(e) => { e.preventDefault(); if (q.trim()) nav(`/cek/${encodeURIComponent(q.trim().replace("PASPORKEBUN:", ""))}`); }}
        style={{ display: "flex", gap: 8, marginBottom: 18 }}
      >
        <input className="input num" placeholder="mis. PK-00001-F" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Kode paspor" />
        <button className="btn btn-primary" type="submit"><Search /> Cek</button>
      </form>
      {busy && <Spinner label="Mencari…" />}
      {err && <Notice kind="danger">{err}</Notice>}
      {data && (
        <article className="panel" style={{ overflow: "hidden" }}>
          <div className="passport-cover">
            <Emblem size={30} />
            <span className="t">Paspor Kebun</span>
            <span className="code">{data.code}</span>
          </div>
          <div style={{ padding: 20, display: "grid", gridTemplateColumns: "1fr auto", gap: 16, alignItems: "start" }}>
            <div>
              <h2 style={{ fontSize: 21 }}>{data.farmer}</h2>
              <p className="muted">Desa {data.village}, {ha(data.area_ha)}</p>
              <p style={{ marginTop: 10, fontWeight: 600, color: data.eudr_ready ? "var(--aman)" : "var(--cek)" }}>
                {data.eudr_ready ? "Siap EUDR" : "Belum siap EUDR"}
              </p>
            </div>
            <Stamp risk={data.risk_level} />
          </div>
          <ul className="checklist" style={{ padding: "0 20px 16px" }}>
            {data.checks.map((c) => (
              <li key={c.label}>
                {c.ok ? <CircleCheck color="var(--aman)" aria-label="terpenuhi" /> : <CircleX color="var(--risiko)" aria-label="belum" />}
                <span>{c.label}</span>
              </li>
            ))}
          </ul>
          <div className="section small muted">
            Ketelitian lokasi: {data.precision}.{" "}
            {data.analyzed_at && <>Cek satelit terakhir {dateLabel(data.analyzed_at)}. </>}
            {data.valid_until && <>Berlaku sampai {dateLabel(data.valid_until)}.</>}
            <p className="faint" style={{ marginTop: 6 }}>{data.note}</p>
          </div>
        </article>
      )}
    </div>
  );
}
