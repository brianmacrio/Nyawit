import type { KawasanInfo, Risk } from "./types";

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
export const RISK_STAMP: Record<Risk, string> = { rendah: "AMAN", perlu_cek: "PERLU CEK", tinggi: "BERISIKO" };
export const riskLabel = (r: Risk | null) => (r ? RISK_LABEL[r] : "Belum dicek");

export const RISK_COLOR: Record<Risk | "none", string> = {
  rendah: "#1E7A4B",
  perlu_cek: "#B7791F",
  tinggi: "#B3261E",
  none: "#7A8780",
};

export const DECISION_LABEL = { diterima: "Diterima", catatan: "Diterima dengan catatan", ditahan: "Ditahan" } as const;

/** Ringkasan status kawasan hutan untuk dibaca manusia, mis. "64% Hutan Lindung". */
/** Warna poligon kawasan hutan di peta, per fungsi. */
export const FUNGSI_COLOR: Record<string, string> = {
  KSA_KPA: "#e5383b",
  HL: "#f77f00",
  HP: "#f4d35e",
  HPT: "#f4d35e",
  HPK: "#f4d35e",
  "?": "#b5179e",
};
export const FUNGSI_LEGEND: { codes: string[]; label: string; color: string }[] = [
  { codes: ["KSA_KPA"], label: "Kawasan konservasi (TN, CA, SM, ...)", color: FUNGSI_COLOR.KSA_KPA },
  { codes: ["HL"], label: "Hutan lindung", color: FUNGSI_COLOR.HL },
  { codes: ["HP", "HPT", "HPK"], label: "Hutan produksi (HP, HPT, HPK)", color: FUNGSI_COLOR.HP },
  { codes: ["?"], label: "Kawasan, fungsi tidak terbaca", color: FUNGSI_COLOR["?"] },
];

export function kawasanText(k: KawasanInfo | undefined | null): string {
  if (!k) return "–";
  const parts = (k.parts ?? []).filter((p) => p.kawasan && p.pct >= 1);
  if (k.pct > 0) return parts.length ? parts.slice(0, 2).map((p) => `${nf0.format(p.pct)}% ${p.label}`).join(", ") : `${nf0.format(k.pct)}% kawasan hutan`;
  if ((k.unknown_pct ?? 0) > 0) return "Fungsi kawasan belum terbaca";
  if (k.source === "tidak_ada") return "Belum bisa dicek";
  if ((k.parts ?? []).some((p) => p.fungsi === "APL" && p.pct >= 50)) return "Di luar kawasan hutan (APL)";
  return "Di luar kawasan hutan";
}

export const KAWASAN_SOURCE_SHORT: Record<string, string> = {
  kemenhut: "peta Kemenhut",
  klhk_gfw: "peta kawasan KLHK 2017 (Global Forest Watch)",
  lokal: "salinan lokal peta kawasan resmi",
  ilustrasi: "peta ilustrasi demo",
  tidak_ada: "peta tidak terjangkau",
};
