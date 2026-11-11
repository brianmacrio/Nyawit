import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Building2, ClipboardCheck, Factory, Scale, ShieldCheck, Users } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { DemoAccount, Role } from "../lib/types";
import { Notice, Spinner } from "../components/ui";

const ROLE_INFO: Record<Role, { Icon: typeof Users; does: string; home: string }> = {
  koperasi: { Icon: Users, does: "Memetakan kebun bersama petani dan saksi, mencatat bukti lahan dan STDB, mengajukan keberatan.", home: "/peta" },
  pengepul: { Icon: Scale, does: "Memindai QR paspor dan mencatat berat TBS setiap membeli.", home: "/pengepul" },
  pabrik: { Icon: Factory, does: "Melihat asal TBS, pengepul yang perlu diaudit, dan membuat paket data ekspor.", home: "/pabrik" },
  verifikator: { Icon: ClipboardCheck, does: "Memeriksa sampel kebun di lapangan dan memutuskan keberatan.", home: "/verifikasi" },
  admin: { Icon: ShieldCheck, does: "Semua akses, termasuk mengulang data demo.", home: "/peta" },
};

export default function Masuk() {
  const { login, demo, user } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [accounts, setAccounts] = useState<DemoAccount[] | null>(null);
  const [form, setForm] = useState({ username: "", password: "" });
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const next = (loc.state as { from?: string } | null)?.from;

  useEffect(() => {
    api.demoAccounts().then(setAccounts).catch(() => setAccounts([]));
  }, []);

  const done = (role: Role) => nav(next || ROLE_INFO[role].home, { replace: true });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy("form");
    setErr(null);
    try {
      done((await login(form.username.trim().toLowerCase(), form.password)).role);
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(null);
    }
  };
  const quick = async (a: DemoAccount) => {
    setBusy(a.username);
    setErr(null);
    try {
      done((await demo(a.username)).role);
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Masuk</h1>
          <p className="muted">
            Setiap orang hanya bisa melihat dan mengubah data sesuai perannya. Kata sandi disimpan sebagai hash, sesi disimpan di cookie
            yang tidak bisa dibaca skrip.
          </p>
        </div>
        {user && <span className="small muted">Saat ini: {user.name} ({user.role_label})</span>}
      </div>
      <div className="login-grid">
        <section className="panel panel-pad" aria-label="Akun demo">
          <h2 style={{ fontSize: 19, marginBottom: 4 }}>Akun demo untuk juri</h2>
          <p className="small muted" style={{ marginBottom: 14 }}>Satu klik, tanpa mengetik kata sandi. Data di dalamnya fiktif.</p>
          {accounts === null && <Spinner label="Memuat…" />}
          {accounts?.length === 0 && <Notice kind="info">Akun demo dinonaktifkan di server ini.</Notice>}
          <div className="role-cards">
            {accounts?.map((a) => {
              const info = ROLE_INFO[a.role];
              return (
                <button key={a.username} className="role-card" onClick={() => quick(a)} disabled={!!busy}>
                  <info.Icon aria-hidden="true" />
                  <span className="r">{a.role_label}</span>
                  <span className="n">{a.name}{a.organisation && a.organisation !== a.name ? `, ${a.organisation}` : ""}</span>
                  <span className="d small muted">{info.does}</span>
                  {busy === a.username && <Spinner />}
                </button>
              );
            })}
          </div>
        </section>
        <section className="panel panel-pad" aria-label="Masuk dengan kata sandi">
          <Building2 color="var(--sampul)" aria-hidden="true" />
          <h2 style={{ fontSize: 19, margin: "6px 0 12px" }}>Masuk dengan kata sandi</h2>
          <form onSubmit={submit} style={{ display: "grid", gap: 12 }}>
            <label className="field"><span>Nama pengguna</span>
              <input className="input" autoComplete="username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
            </label>
            <label className="field"><span>Kata sandi</span>
              <input className="input" type="password" autoComplete="current-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
            </label>
            <button className="btn btn-primary" type="submit" disabled={!!busy}>{busy === "form" ? <Spinner /> : null} Masuk</button>
            <p className="small faint">Kata sandi akun demo tercantum di README. Percobaan masuk dibatasi 10 kali per menit.</p>
          </form>
          {err && <div style={{ marginTop: 12 }}><Notice kind="danger">{err}</Notice></div>}
        </section>
      </div>
    </div>
  );
}
