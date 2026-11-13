export type Risk = "rendah" | "perlu_cek" | "tinggi";

export interface GeoPolygon {
  type: "Polygon";
  coordinates: number[][][];
}

export interface PlotSummary {
  id: number;
  code: string;
  label: string;
  farmer: { id: number; name: string; village: string };
  geometry: GeoPolygon;
  area_ha: number;
  centroid: [number, number];
  risk_level: Risk | null;
  risk_headline: string | null;
  boundary_confirmed: boolean;
  planting_year: number | null;
  delineation_method: string;
  status_override?: boolean;
  eudr_ready?: boolean;
  readiness_missing?: number;
}

export interface EvidenceItem {
  key: string;
  label: string;
  value: string;
  verdict: "mendukung_aman" | "mendukung_risiko" | "netral" | "tidak_tersedia";
  source: string;
  detail: string;
}

export interface Break {
  date: string;
  magnitude: number;
  confidence: string;
  after_cutoff: boolean;
}

export interface TimeSeries {
  dates: string[];
  ndvi: number[];
  fitted: (number | null)[];
  is_outlier: boolean[];
  curve: { date: string; value: number; segment: number }[];
  segments: { start: string; end: string; mean_ndvi: number; cover: string }[];
  breaks: Break[];
  pending_change: { date: string; n_consecutive: number; needed: number } | null;
  planting_year: number | null;
  planting_note: string;
  n_obs: number;
  span_years: number;
}

export interface Analysis {
  id: number;
  created_at: string;
  risk_level: Risk;
  headline: string;
  confidence: number;
  evidence: {
    items: EvidenceItem[];
    notes: string[];
    rule: string;
    is_replanting: boolean;
    sources: string[];
    warnings: string[];
    cutoff: string;
    protected: KawasanInfo;
  };
  timeseries: TimeSeries;
  data_source: "simulasi" | "live" | "peta_nyata";
  compute_ms: number;
  model_version: string;
}

export interface Overlap {
  plot_id: number;
  code: string;
  farmer: string;
  overlap_ha: number;
  geometry: GeoPolygon | null;
}

export type SideKey = "utara" | "timur" | "selatan" | "barat";
export type SideType = "parit" | "jalan" | "kebun" | "hutan" | "sungai" | "lainnya";
export interface Side {
  jenis: SideType;
  tetangga?: string | null;
}
export interface Witness {
  name: string;
  relation: string;
  at: string | null;
}
export type LandProof = "sertifikat" | "surat_desa" | "pernyataan";
export type StdbStatus = "ada" | "proses" | "belum";

export interface ReadinessCheck {
  key: "lokasi" | "lahan" | "kawasan" | "hutan" | "verifikasi";
  label: string;
  ok: boolean;
  detail: string;
}
export interface Precision {
  level: number;
  of: number;
  label: string;
  gps: boolean;
  gps_accuracy_m: number | null;
}
export interface Readiness {
  ready: boolean;
  missing: number;
  checks: ReadinessCheck[];
  valid_until: string | null;
  expired: boolean;
  precision: Precision;
}

export interface InspectionBrief {
  id: number;
  batch: string;
  reason: string;
  status: "menunggu" | "selesai";
  result: "sesuai" | "tidak_sesuai" | null;
  notes: string | null;
  inspector: string | null;
  has_photo: boolean;
  photo_distance_m: number | null;
  created_at: string;
  done_at: string | null;
}

export interface Inspection extends InspectionBrief {
  plot_id: number;
  plot_code: string;
  farmer: string;
  village: string;
  area_ha: number;
  centroid: [number, number];
  risk_level: Risk | null;
  reason_label: string;
  photo_lat: number | null;
  photo_lng: number | null;
}

export type EvidenceType = "sk_pelepasan" | "sertifikat" | "surat_desa" | "foto_lapangan" | "lainnya";
export interface Appeal {
  id: number;
  plot_id: number;
  plot_code: string;
  farmer: string;
  submitted_by: string;
  reason: string;
  evidence_type: EvidenceType;
  status: "diajukan" | "diterima" | "ditolak";
  original_risk: Risk | null;
  new_risk: Risk | null;
  decision_note: string | null;
  decided_by: string | null;
  created_at: string;
  decided_at: string | null;
  current_risk: Risk | null;
  headline: string | null;
}

export interface AuditEvent {
  id: number;
  at: string;
  actor: string;
  role: string;
  action: string;
  entity: string;
  entity_id: number | null;
  summary: string;
  hash: string;
}

export interface PlotDetail extends PlotSummary {
  planting_year_declared: number | null;
  planting_year_detected: number | null;
  planting_consistency: { declared: number; detected: number; message: string } | null;
  witness: string | null;
  witnesses: Witness[];
  boundary_sides: Partial<Record<SideKey, Side>>;
  gps: { lat: number; lng: number; accuracy_m: number | null } | null;
  land: {
    proof: LandProof | null;
    proof_label: string | null;
    ref: string | null;
    stdb_status: StdbStatus;
    stdb_label: string;
    stdb_number: string | null;
    dispute: boolean;
    dispute_note: string | null;
  };
  consent: boolean;
  consent_at: string | null;
  created_at: string;
  analysis: Analysis | null;
  scenario: string | null;
  override: { original: Risk; risk_level: Risk; reason: string; by: string; at: string } | null;
  verification: { at: string | null; result: "sesuai" | "tidak_sesuai" | null; by: string | null };
  readiness: Readiness;
  inspections: InspectionBrief[];
  appeals: Appeal[];
  history: AuditEvent[];
  overlaps?: Overlap[];
}

export type Role = "koperasi" | "pengepul" | "pabrik" | "verifikator" | "admin";
export interface User {
  id: number;
  username: string;
  name: string;
  role: Role;
  role_label: string;
  collector_id: number | null;
  organisation: string | null;
  is_demo: boolean;
}
export interface DemoAccount {
  username: string;
  name: string;
  role: Role;
  role_label: string;
  organisation: string | null;
}

export interface ShipmentEntry {
  plot_id: number;
  plot_code: string;
  village: string;
  area_ha: number;
  centroid: [number, number];
  volume_kg: number;
  n_purchases: number;
  production_start: string;
  production_end: string;
  collectors: string[];
  risk_level: Risk | null;
  land_proof: LandProof | null;
  stdb_status: StdbStatus;
  verified: string | null;
  precision_level: number;
  failed_checks: string[];
}
export interface Shipment {
  id: number;
  code: string;
  buyer: string;
  destination: string;
  period_start: string;
  period_end: string;
  created_by: string;
  created_at: string;
  summary: {
    included_kg: number;
    excluded_kg: number;
    held_kg: number;
    delivered_kg: number;
    untraced_kg: number;
    n_included: number;
    n_excluded: number;
    eligible_share: number | null;
    production_start: string | null;
    production_end: string | null;
    cutoff: string;
    rule: string;
  };
  /** hasil pemeriksaan GeoJSON paket terhadap aturan format TRACES (Sistem Informasi EUDR) */
  traces?: {
    ok: boolean;
    features: number;
    problems: { plot: string | null; issues: string[] }[];
    spec: string;
    checks: string[];
  };
  plots?: ShipmentEntry[];
  excluded?: ShipmentEntry[];
}

export interface PublicPassport {
  code: string;
  farmer: string;
  village: string;
  area_ha: number;
  risk_level: Risk | null;
  risk_headline: string | null;
  eudr_ready: boolean;
  checks: { label: string; ok: boolean }[];
  valid_until: string | null;
  analyzed_at: string | null;
  precision: string;
  note: string;
}

export interface FitResult {
  geometry: GeoPolygon;
  area_ha: number;
  removed_ha: number;
  neighbors: { code: string; farmer: string; overlap_ha: number }[];
}

export interface Flag {
  code: string;
  severity: "tinggi" | "sedang" | "info";
  title: string;
  detail: string;
}

export interface Txn {
  id: number;
  plot_code: string;
  plot_id: number;
  farmer: string;
  collector_id: number;
  collector: string;
  weight_kg: number;
  created_at: string;
  decision: "diterima" | "catatan" | "ditahan";
  flags: Flag[];
  capacity_used_pct: number;
}

export interface Capacity {
  age: number | null;
  potential_t_ha_year: number;
  typical_kg_30d: number;
  upper_kg_30d: number;
  season_factor: number;
  used_kg_30d: number;
  remaining_kg: number;
}

export interface PassportLookup {
  plot: PlotSummary;
  capacity: Capacity;
  last_sale: string | null;
  days_since_last_sale: number | null;
}

export interface CheckResult {
  decision: Txn["decision"];
  flags: Flag[];
  used_kg_30d: number;
  upper_kg_30d: number;
  typical_kg_30d: number;
  capacity_used_pct: number;
  age: number | null;
}

export interface CollectorRow {
  id: number;
  name: string;
  village: string;
  delivered_kg: number;
  traced_kg: number;
  held_kg: number;
  n_txn: number;
  n_plots: number;
  flagged: number;
  traced_share: number | null;
  ai_score: number | null;
  ai_level: "rendah" | "sedang" | "tinggi" | null;
  ai_reasons: { feature: string; label: string; value: string; typical: string; z: number }[];
}

export interface Dashboard {
  generated_at: string;
  days_to_eudr: number;
  kpi: {
    plots: number;
    farmers: number;
    area_ha: number;
    risk: Record<string, number>;
    eudr_ready: number;
    eudr_ready_share: number;
    blockers: Partial<Record<ReadinessCheck["key"], number>>;
    traced_share_30d: number | null;
    delivered_t_30d: number;
    traced_t_30d: number;
    held_t_30d: number;
  };
  monthly: { month: string; delivered_t: number; traced_t: number; held_t: number; partial: boolean }[];
  collectors: CollectorRow[];
  alerts: Txn[];
  supply_plots: { id: number; code: string; centroid: [number, number]; risk_level: Risk | null; kg_90d: number }[];
  compute_ms: number;
}

export interface KawasanPart {
  fungsi: string;
  label: string;
  pct: number;
  name: string | null;
  kawasan: boolean | null;
  source: string;
}

/** Status kawasan hutan kebun dari peta Kemenhut (online/cache) atau GeoJSON lokal. */
export interface KawasanInfo {
  pct: number;
  name: string | null;
  fungsi?: string | null;
  label?: string | null;
  parts?: KawasanPart[];
  unknown_pct?: number;
  source?: "kemenhut" | "klhk_gfw" | "lokal" | "ilustrasi" | "tidak_ada";
  source_label?: string;
  checked?: boolean;
  policy?: string;
  checked_at?: string | null;
  warnings?: string[];
}

export interface OverlapCheck {
  area_ha: number;
  overlaps: Overlap[];
  protected: KawasanInfo;
}

export interface Meta {
  version: string;
  satellite_mode: "demo" | "live";
  live_packages: { available: boolean; missing: string[] };
  sam: { available: boolean; reason: string };
  eudr_cutoff: string;
  eudr_application: string;
  imagery: string;
  kawasan?: {
    policy: "auto" | "online" | "lokal";
    service: string;
    layers: number[] | null;
    online: boolean | null;
    last_error: string | null;
    cached_cells: number;
    source_label: string;
    gfw?: { enabled: boolean; source_label: string; cached_tiles: number; online: boolean | null; last_error: string | null };
    /** "gambar" = layanan hanya mengizinkan tampilan peta, status dibaca dari warna gambar peta */
    mode?: "gambar" | "query" | null;
    layer_names?: string[];
    legend?: { label: string; rgb: [number, number, number]; fungsi: string; kawasan: boolean | null }[];
  };
  peta_gfw?: { enabled: boolean; bundled_plots: number; cached_tiles: number; last_ok: string | null; last_error: string | null };
}

export interface IndicatorTest {
  name: string;
  why: string;
  expect_on: number[];
  expect_risk: Risk;
  on: number[];
  risk?: Risk;
  headline?: string;
  passed: boolean;
  seconds: number;
  errors: string[];
  indicators: {
    "1"?: {
      on: boolean;
      loss_after_pct: number;
      by_year: Record<string, number>;
      forest_2020_pct: number;
      natural_forest_2020_pct?: number | null;
      loss_on_forest_both_pct?: number | null;
    };
    "2"?: { on: boolean; pct: number; label: string };
    "3"?: { on: boolean; pct: number; label: string };
  };
}

export interface DelineateResult {
  polygon: GeoPolygon | null;
  area_ha: number;
  confidence: number;
  engine: "sam" | "watershed";
  engine_label: string;
  ms: number;
  warnings: string[];
  note: string;
}

export interface ProtectedArea {
  name: string;
  status: string;
  fungsi?: string;
  fungsi_label?: string;
  is_demo: boolean;
  source_label?: string | null;
  gfw_fid?: number | null;
  geometry: GeoPolygon;
}

/** Poligon kawasan hutan untuk lapisan peta (Peta Kawasan Hutan KLHK 2017 lewat Global Forest Watch). */
export interface KawasanMap {
  features: { type: "Feature"; geometry: GeoPolygon; properties: { gfw_fid: number | null; fungsi: string; fungsi_label: string; name: string | null } }[];
  source_label: string;
  too_large?: boolean;
  error?: string;
}
