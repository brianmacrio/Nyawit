import type { Risk } from "./types";

const nf1 = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const nf0 = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 });
const nf2 = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 2, minimumFractionDigits: 2 });

export const ha = (v: number) => `${nf2.format(v)} ha`;
export const kg = (v: number) => (v >= 1000 ? `${nf1.format(v / 1000)} t` : `${nf0.format(v)} kg`);
export const num = (v: number) => nf0.format(v);
export const dec1 = (v: number) => nf1.format(v);
export const pct = (v: number | null | undefined) => (v == null ? "–" : `${nf0.format(v * 100)}%`);

const months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
export const monthLabel = (ym: string) => {
  const [y, m] = ym.split("-").map(Number);
  return `${months[m - 1]} ${String(y).slice(2)}`;
};
export const dateLabel = (iso: string) => {
  const d = new Date(iso);
  return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
};
export const dateTimeLabel = (iso: string) => {
  const d = new Date(iso);
  return `${d.getDate()} ${months[d.getMonth()]}, ${String(d.getHours()).padStart(2, "0")}.${String(d.getMinutes()).padStart(2, "0")}`;
};

export const RISK_LABEL: Record<Risk, string> = { rendah: "Aman", perlu_cek: "Perlu cek", tinggi: "Berisiko" };
export const RISK_STAMP: Record<Risk, string> = { rendah: "AMAN EUDR", perlu_cek: "PERLU CEK", tinggi: "BERISIKO" };
export const riskLabel = (r: Risk | null) => (r ? RISK_LABEL[r] : "Belum dicek");

export const RISK_COLOR: Record<Risk | "none", string> = {
  rendah: "#1E7A4B",
  perlu_cek: "#B7791F",
  tinggi: "#B3261E",
  none: "#7A8780",
};

export const DECISION_LABEL = { diterima: "Diterima", catatan: "Diterima dengan catatan", ditahan: "Ditahan" } as const;
