import type {
  CheckResult,
  Dashboard,
  DelineateResult,
  GeoPolygon,
  Meta,
  OverlapCheck,
  PassportLookup,
  PlotDetail,
  PlotSummary,
  ProtectedArea,
  Txn,
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

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    });
  } catch {
    throw new ApiError(0, "Server tidak bisa dihubungi. Pastikan backend berjalan di port 8000.", null);
  }
  const body = res.headers.get("content-type")?.includes("json") ? await res.json() : await res.text();
  if (!res.ok) {
    let msg = typeof body === "object" && body && "detail" in body ? (body as { detail: unknown }).detail : body;
    if (Array.isArray(msg)) msg = msg.map((m: { msg?: string }) => m.msg?.replace("Value error, ", "")).join("; ");
    throw new ApiError(res.status, String(msg), body);
  }
  return body as T;
}

const post = <T>(path: string, data: unknown) => req<T>(path, { method: "POST", body: JSON.stringify(data) });

export const api = {
  meta: () => req<Meta>("/api/meta"),
  plots: () => req<PlotSummary[]>("/api/plots"),
  plot: (id: number) => req<PlotDetail>(`/api/plots/${id}`),
  protectedAreas: () => req<ProtectedArea[]>("/api/plots/protected-areas"),
  analyze: (id: number) => post<PlotDetail>(`/api/plots/${id}/analyze`, {}),
  updatePlot: (id: number, data: Record<string, unknown>) =>
    req<PlotDetail>(`/api/plots/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  createPlot: (data: Record<string, unknown>) => post<PlotDetail>("/api/plots", data),
  checkOverlap: (geometry: GeoPolygon, exclude_plot_id?: number) =>
    post<OverlapCheck>("/api/plots/check-overlap", { geometry, exclude_plot_id }),
  delineate: (lat: number, lng: number, zoom?: number) => post<DelineateResult>("/api/ai/delineate", { lat, lng, zoom }),
  collectors: () => req<{ id: number; name: string; village: string }[]>("/api/collectors"),
  lookup: (code: string) => req<PassportLookup>(`/api/passport/${encodeURIComponent(code)}`),
  record: (plot_code: string, collector_id: number, weight_kg: number) =>
    post<{ transaction: Txn; check: CheckResult }>("/api/transactions", { plot_code, collector_id, weight_kg }),
  transactions: (collector_id?: number) => req<Txn[]>(`/api/transactions${collector_id ? `?collector_id=${collector_id}` : ""}`),
  dashboard: () => req<Dashboard>("/api/dashboard"),
  resetDemo: () => post<{ detail: string }>("/api/demo/reset", {}),
  eudrPlotUrl: (id: number) => `/api/plots/${id}/eudr.geojson`,
  eudrAllUrl: () => "/api/dashboard/eudr.geojson",
};
