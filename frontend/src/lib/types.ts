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
    protected: { pct: number; name: string | null };
  };
  timeseries: TimeSeries;
  data_source: "simulasi" | "live";
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

export interface PlotDetail extends PlotSummary {
  planting_year_declared: number | null;
  planting_year_detected: number | null;
  planting_consistency: { declared: number; detected: number; message: string } | null;
  witness: string | null;
  consent: boolean;
  consent_at: string | null;
  created_at: string;
  analysis: Analysis | null;
  scenario: string | null;
  overlaps?: Overlap[];
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

export interface Meta {
  version: string;
  satellite_mode: "demo" | "live";
  live_packages: { available: boolean; missing: string[] };
  sam: { available: boolean; reason: string };
  eudr_cutoff: string;
  eudr_application: string;
  imagery: string;
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
  is_demo: boolean;
  geometry: GeoPolygon;
}
