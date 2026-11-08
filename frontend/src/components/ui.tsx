import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, XOctagon } from "lucide-react";
import { RISK_STAMP, riskLabel } from "../lib/format";
import type { Risk } from "../lib/types";

export function Emblem({ size = 38 }: { size?: number }) {
  // daun sawit bergaya lambang; emas di atas hijau sampul
  return (
    <svg viewBox="0 0 40 40" width={size} height={size} aria-hidden="true">
      <rect x="1" y="1" width="38" height="38" rx="9" fill="#0a3a31" stroke="#b08a3e" strokeWidth="1.2" />
      <path d="M20 31V12" stroke="#e9d9b1" strokeWidth="1.8" strokeLinecap="round" />
      <path
        d="M20 13c-3-3-7-4-11-3M20 13c3-3 7-4 11-3M20 17c-3-2-6-2-9-1M20 17c3-2 6-2 9-1M20 21c-2-1-5-1-7 0M20 21c2-1 5-1 7 0"
        stroke="#c9a55a"
        strokeWidth="1.6"
        fill="none"
        strokeLinecap="round"
      />
      <circle cx="20" cy="27" r="2.6" fill="#c9a55a" />
    </svg>
  );
}

export function StatusTag({ risk }: { risk: Risk | null }) {
  return <span className={`tag tag-${risk ?? "none"}`}>{riskLabel(risk)}</span>;
}

export function Stamp({ risk, sub, animate }: { risk: Risk | null; sub?: string; animate?: boolean }) {
  return (
    <div className={`stamp stamp-${risk ?? "none"} ${animate ? "thunk" : ""}`} role="img" aria-label={`Status: ${riskLabel(risk)}`}>
      <span>{risk ? RISK_STAMP[risk] : "BELUM DICEK"}</span>
      {sub && <small>{sub}</small>}
    </div>
  );
}

export function Notice({ kind = "info", children }: { kind?: "info" | "warn" | "danger" | "ok"; children: ReactNode }) {
  const Icon = kind === "danger" ? XOctagon : kind === "warn" ? AlertTriangle : kind === "ok" ? CheckCircle2 : Info;
  return (
    <div className={`notice notice-${kind}`}>
      <Icon aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span role="status" style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <span className="spinner" aria-hidden="true" />
      {label && <span>{label}</span>}
    </span>
  );
}
