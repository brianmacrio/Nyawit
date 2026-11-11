import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { LogIn } from "lucide-react";
import { DEMO_FOR, ROLE_LABEL, useAuth } from "../lib/auth";
import type { Role } from "../lib/types";
import { Notice, Spinner } from "./ui";

/**
 * Menampilkan halaman hanya untuk peran tertentu. `roles` kosong = cukup sudah masuk.
 * Untuk penilaian juri, tersedia tombol masuk satu klik dengan akun demo peran yang sesuai.
 */
export function RoleGate({ roles = [], title, children }: { roles?: Role[]; title: string; children: ReactNode }) {
  const { user, ready, can, demo } = useAuth();
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (!ready) return <div className="page"><Spinner label="Memeriksa sesi…" /></div>;
  if (user && (roles.length === 0 || can(...roles))) return <>{children}</>;
  const want: Role[] = roles.length ? roles : ["koperasi", "pabrik"];
  const go = async (r: Role) => {
    setBusy(true);
    setErr(null);
    try {
      await demo(DEMO_FOR[r]);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="page">
      <div className="panel panel-pad gate">
        <LogIn size={28} color="var(--sampul)" aria-hidden="true" />
        <h1 style={{ fontSize: 26 }}>{title}</h1>
        <p className="muted">
          {user
            ? `Halaman ini untuk ${want.map((r) => ROLE_LABEL[r].toLowerCase()).join(" atau ")}. Anda masuk sebagai ${user.role_label.toLowerCase()}.`
            : "Silakan masuk. Setiap peran hanya melihat dan mengubah data sesuai tugasnya."}
        </p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {want.map((r) => (
            <button key={r} className="btn btn-primary" onClick={() => go(r)} disabled={busy}>
              Masuk sebagai {ROLE_LABEL[r].toLowerCase()} (demo)
            </button>
          ))}
          <Link className="btn btn-quiet" to="/masuk">Pakai akun lain</Link>
        </div>
        {err && <Notice kind="danger">{err}</Notice>}
      </div>
    </div>
  );
}
