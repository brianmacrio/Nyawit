import type {
  Appeal,
  AuditEvent,
  CheckResult,
  Dashboard,
  DelineateResult,
  DemoAccount,
  EvidenceType,
  FitResult,
  GeoPolygon,
  Inspection,
  KawasanMap,
  IndicatorTest,
  Meta,
  OverlapCheck,
  PassportLookup,
  PlotDetail,
  PlotSummary,
  ProtectedArea,
  PublicPassport,
  Shipment,
  Txn,
  User,
  Witness,
} from "./types";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

/** Dikirim ke AuthProvider saat sesi habis, agar pengguna diarahkan masuk lagi. */
export const UNAUTHORIZED_EVENT = "pk:unauthorized";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        // header anti-CSRF: situs lain tidak bisa menambahkannya tanpa izin CORS
        "X-Requested-With": "PasporKebun",
        ...(init?.headers || {}),
      },
    });
  } catch {
    throw new ApiError(0, "Server tidak bisa dihubungi. Pastikan backend berjalan di port 8000.", null);
  }
  const body = res.headers.get("content-type")?.includes("json") ? await res.json() : await res.text();
  if (!res.ok) {
    let msg = typeof body === "object" && body && "detail" in body ? (body as { detail: unknown }).detail : body;
    if (Array.isArray(msg)) msg = msg.map((m: { msg?: string }) => m.msg?.replace("Value error, ", "")).join("; ");
    if (res.status === 401 && !path.startsWith("/api/auth/")) window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    throw new ApiError(res.status, String(msg), body);
  }
  return body as T;
}

const post = <T>(path: string, data: unknown) => req<T>(path, { method: "POST", body: JSON.stringify(data) });

export const api = {
  // akun
  me: () => req<{ user: User | null }>("/api/auth/me"),
  login: (username: string, password: string) => post<User>("/api/auth/login", { username, password }),
  demoLogin: (username: string) => post<User>("/api/auth/demo", { username }),
  logout: () => post<{ detail: string }>("/api/auth/logout", {}),
  demoAccounts: () => req<DemoAccount[]>("/api/auth/demo-accounts"),

  meta: () => req<Meta>("/api/meta"),
  indicatorTest: () => req<{ results: IndicatorTest[]; passed: number; total: number }>("/api/uji-indikator"),
  plots: () => req<PlotSummary[]>("/api/plots"),
  plot: (id: number) => req<PlotDetail>(`/api/plots/${id}`),
  protectedAreas: () => req<ProtectedArea[]>("/api/plots/protected-areas"),
  kawasanMap: (bbox: [number, number, number, number], signal?: AbortSignal) =>
    req<KawasanMap>(`/api/kawasan/peta?bbox=${bbox.map((v) => v.toFixed(5)).join(",")}`, { signal }),
  analyze: (id: number) => post<PlotDetail>(`/api/plots/${id}/analyze`, {}),
  updatePlot: (id: number, data: Record<string, unknown>) =>
    req<PlotDetail>(`/api/plots/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  addWitness: (id: number, w: Pick<Witness, "name" | "relation">) => post<PlotDetail>(`/api/plots/${id}/witnesses`, w),
  createPlot: (data: Record<string, unknown>) => post<PlotDetail>("/api/plots", data),
  checkOverlap: (geometry: GeoPolygon, exclude_plot_id?: number) =>
    post<OverlapCheck>("/api/plots/check-overlap", { geometry, exclude_plot_id }),
  fitNeighbors: (geometry: GeoPolygon, exclude_plot_id?: number) =>
    post<FitResult>("/api/plots/fit-neighbors", { geometry, exclude_plot_id }),
  delineate: (lat: number, lng: number, zoom?: number) => post<DelineateResult>("/api/ai/delineate", { lat, lng, zoom }),
  publicPassport: (code: string) => req<PublicPassport>(`/api/public/passport/${encodeURIComponent(code)}`),

  // pengepul
  collectors: () => req<{ id: number; name: string; village: string }[]>("/api/collectors"),
  lookup: (code: string) => req<PassportLookup>(`/api/passport/${encodeURIComponent(code)}`),
  record: (plot_code: string, weight_kg: number, collector_id?: number) =>
    post<{ transaction: Txn; check: CheckResult }>("/api/transactions", { plot_code, collector_id, weight_kg }),
  transactions: (collector_id?: number) => req<Txn[]>(`/api/transactions${collector_id ? `?collector_id=${collector_id}` : ""}`),

  // pabrik
  dashboard: () => req<Dashboard>("/api/dashboard"),
  shipments: () => req<Shipment[]>("/api/shipments"),
  createShipment: (data: { buyer: string; destination: string; period_start: string; period_end: string }) =>
    post<Shipment>("/api/shipments", data),
  shipmentZipUrl: (id: number) => `/api/shipments/${id}/package.zip`,

  // verifikasi
  inspections: (status?: "menunggu" | "selesai") =>
    req<{ sample_size: number; n_plots: number; formula: string; items: Inspection[] }>(
      `/api/inspections${status ? `?status=${status}` : ""}`,
    ),
  makeSample: () => post<{ created: number; batch: string }>("/api/inspections/sample", {}),
  inspectionResult: (id: number, data: { result: "sesuai" | "tidak_sesuai"; notes?: string; photo?: string; lat?: number; lng?: number }) =>
    post<{ inspection: Inspection; warnings: string[] }>(`/api/inspections/${id}/result`, data),
  inspectionPhotoUrl: (id: number) => `/api/inspections/${id}/photo`,
  appeals: () => req<Appeal[]>("/api/appeals"),
  createAppeal: (plot_id: number, reason: string, evidence_type: EvidenceType) =>
    post<Appeal>("/api/appeals", { plot_id, reason, evidence_type }),
  decideAppeal: (id: number, accept: boolean, note: string, new_risk?: "rendah" | "perlu_cek") =>
    post<Appeal>(`/api/appeals/${id}/decide`, { accept, note, new_risk }),
  auditVerify: () => req<{ ok: boolean; events: number; broken_at: number | null; message: string; head?: string }>("/api/audit/verify"),
  auditRecent: (limit = 30) => req<AuditEvent[]>(`/api/audit?limit=${limit}`),

  eudrPlotUrl: (id: number) => `/api/plots/${id}/eudr.geojson`,
  eudrAllUrl: () => "/api/dashboard/eudr.geojson",
};
