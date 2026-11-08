import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "@geoman-io/leaflet-geoman-free";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";
import { GeoJSON, MapContainer, Polygon, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { useSearchParams } from "react-router-dom";
import { MousePointerClick, PenLine, Plus, Search, Sparkles } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { ha, RISK_COLOR, riskLabel } from "../lib/format";
import type { DelineateResult, GeoPolygon, Meta, Overlap, PlotDetail, PlotSummary, ProtectedArea, Risk } from "../lib/types";
import { BaseLayers } from "../components/MapBase";
import { PassportPanel } from "../components/PassportPanel";
import { Notice, Spinner, StatusTag } from "../components/ui";

const CENTER: [number, number] = [-0.172, 101.893];
const toLatLngs = (g: GeoPolygon) => g.coordinates[0].map(([lng, lat]) => [lat, lng] as [number, number]);
const toGeo = (latlngs: L.LatLng[]): GeoPolygon => {
  const ring = latlngs.map((p) => [Number(p.lng.toFixed(7)), Number(p.lat.toFixed(7))]);
  ring.push(ring[0]);
  return { type: "Polygon", coordinates: [ring] };
};

type Mode = "idle" | "pick" | "loading" | "edit" | "draw";
const SCENARIOS: [string, string][] = [
  ["", "Otomatis (sesuai lokasi)"],
  ["sawit_tua_stabil", "Sawit stabil sejak sebelum 2018"],
  ["dibuka_2019", "Dibuka 2019, sebelum batas EUDR"],
  ["peremajaan_2023", "Peremajaan sawit 2023 (PSR)"],
  ["hutan_dibuka_2022", "Hutan dibuka 2022"],
  ["data_kurang", "Citra berawan, bukti kurang"],
];

function FlyTo({ target }: { target: GeoPolygon | null }) {
  const map = useMap();
  useEffect(() => {
    if (!target) return;
    map.flyToBounds(L.latLngBounds(toLatLngs(target)), {
      paddingTopLeft: [370, 40],
      paddingBottomRight: [470, 40],
      maxZoom: 18,
      duration: 0.8,
    });
  }, [target, map]);
  return null;
}

function PickHandler({ active, onPick }: { active: boolean; onPick: (lat: number, lng: number) => void }) {
  const map = useMapEvents({
    click(e) {
      if (active) onPick(e.latlng.lat, e.latlng.lng);
    },
  });
  useEffect(() => {
    map.getContainer().classList.toggle("picking", active);
  }, [active, map]);
  return null;
}

/** Poligon draf yang bisa diedit titik-titiknya (Leaflet-Geoman). */
function DraftLayer({ draft, mode, onChange }: { draft: GeoPolygon | null; mode: Mode; onChange: (g: GeoPolygon) => void }) {
  const map = useMap();
  const layerRef = useRef<L.Polygon | null>(null);
  const fromEdit = useRef<GeoPolygon | null>(null);
  const cb = useRef(onChange);
  cb.current = onChange;

  useEffect(() => {
    map.pm.setGlobalOptions({ snappable: true, allowSelfIntersection: false } as never);
  }, [map]);

  useEffect(() => {
    // perubahan yang berasal dari menggeser titik tidak perlu menggambar ulang poligon
    if (draft && draft === fromEdit.current) return;
    layerRef.current?.remove();
    layerRef.current = null;
    if (!draft) return;
    const poly = L.polygon(toLatLngs(draft).slice(0, -1), { color: "#e9d9b1", weight: 3, fillOpacity: 0.12, dashArray: "6 4" });
    poly.addTo(map);
    poly.pm.enable({ allowSelfIntersection: false });
    poly.on("pm:edit", () => {
      const g = toGeo(poly.getLatLngs()[0] as L.LatLng[]);
      fromEdit.current = g;
      cb.current(g);
    });
    layerRef.current = poly;
  }, [draft, map]);

  useEffect(() => () => { layerRef.current?.remove(); }, []);

  useEffect(() => {
    if (mode !== "draw") return;
    map.pm.enableDraw("Polygon", { finishOn: "dblclick" } as never);
    const onCreate = (e: { layer: L.Layer }) => {
      const lyr = e.layer as L.Polygon;
      const g = toGeo(lyr.getLatLngs()[0] as L.LatLng[]);
      lyr.remove();
      cb.current(g);
    };
    map.on("pm:create", onCreate as never);
    return () => {
      map.off("pm:create", onCreate as never);
      map.pm.disableDraw();
    };
  }, [mode, map]);
  return null;
}

export default function PetaKebun() {
  const [plots, setPlots] = useState<PlotSummary[]>([]);
  const [areas, setAreas] = useState<ProtectedArea[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [selected, setSelected] = useState<PlotDetail | null>(null);
  const [justAnalyzed, setJustAnalyzed] = useState(false);
  const [flyTarget, setFlyTarget] = useState<GeoPolygon | null>(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Risk | "all">("all");
  const [mode, setMode] = useState<Mode>("idle");
  const [draft, setDraft] = useState<GeoPolygon | null>(null);
  const [ai, setAi] = useState<DelineateResult | null>(null);
  const [aiErr, setAiErr] = useState<string | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [params, setParams] = useSearchParams();

  const load = useCallback(async () => {
    try {
      const [p, a, m] = await Promise.all([api.plots(), api.protectedAreas(), api.meta()]);
      setPlots(p);
      setAreas(a);
      setMeta(m);
      setLoadErr(null);
    } catch (e) {
      setLoadErr((e as Error).message);
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  const open = useCallback(async (id: number, fly = true) => {
    const d = await api.plot(id);
    setSelected(d);
    setJustAnalyzed(false);
    if (fly) setFlyTarget(d.geometry);
    setParams({ kebun: String(id) }, { replace: true });
  }, [setParams]);

  useEffect(() => {
    const k = params.get("kebun");
    if (k && !selected) open(Number(k));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visible = useMemo(() => {
    const s = q.trim().toLowerCase();
    return plots.filter(
      (p) =>
        (filter === "all" || p.risk_level === filter) &&
        (!s || p.farmer.name.toLowerCase().includes(s) || p.code.toLowerCase().includes(s) || p.farmer.village.toLowerCase().includes(s)),
    );
  }, [plots, q, filter]);
  const counts = useMemo(() => {
    const c: Record<string, number> = { rendah: 0, perlu_cek: 0, tinggi: 0 };
    plots.forEach((p) => p.risk_level && c[p.risk_level]++);
    return c;
  }, [plots]);

  const startAdd = () => {
    setSelected(null);
    setDraft(null);
    setAi(null);
    setAiErr(null);
    setMode("pick");
  };
  const cancelAdd = () => {
    setMode("idle");
    setDraft(null);
    setAi(null);
    setAiErr(null);
  };

  const onPick = async (lat: number, lng: number) => {
    setMode("loading");
    setAiErr(null);
    try {
      const r = await api.delineate(lat, lng);
      setAi(r);
      if (r.polygon) {
        setDraft(r.polygon);
        setMode("edit");
      } else {
        setAiErr(r.warnings.join(" "));
        setMode("draw");
      }
    } catch (e) {
      setAiErr((e as ApiError).message);
      setMode("draw");
    }
  };

  const showDrawer = selected || draft || mode === "loading";
  // ?pusat=lat,lng,zoom untuk membagikan tampilan peta
  const initial = useMemo(() => {
    const v = params.get("pusat")?.split(",").map(Number);
    return v && v.length >= 2 && v.every(Number.isFinite) ? { c: [v[0], v[1]] as [number, number], z: v[2] || 16 } : { c: CENTER, z: 15 };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className={`map-page ${showDrawer ? "has-drawer" : ""}`}>
      <MapContainer center={initial.c} zoom={initial.z} zoomControl={false} style={{ position: "absolute", inset: 0 }}>
        <BaseLayers />
        <FlyTo target={flyTarget} />
        <PickHandler active={mode === "pick"} onPick={onPick} />
        <DraftLayer draft={draft} mode={mode} onChange={(g) => { setDraft(g); if (mode === "draw") setMode("edit"); }} />
        {areas.map((a) => (
          <GeoJSON
            key={a.name}
            data={a.geometry as never}
            style={{ color: "#ff6b5e", weight: 2, dashArray: "8 6", fillOpacity: 0.06 }}
            interactive={false}
          />
        ))}
        {plots.map((p) => {
          const col = RISK_COLOR[p.risk_level ?? "none"];
          const sel = selected?.id === p.id;
          return (
            <Polygon
              key={p.id + (p.risk_level ?? "")}
              positions={toLatLngs(p.geometry)}
              pathOptions={{ color: sel ? "#e9d9b1" : col, weight: sel ? 4 : 2, fillColor: col, fillOpacity: sel ? 0.3 : 0.22 }}
              eventHandlers={{ click: () => mode === "idle" && open(p.id, false) }}
            >
              <Tooltip direction="top" sticky className="pk-label">
                {p.code} · {p.farmer.name}
              </Tooltip>
            </Polygon>
          );
        })}
      </MapContainer>

      <aside className="float plot-list" aria-label="Daftar kebun">
        <header>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ fontSize: 19 }}>Kebun terdaftar</h2>
            <span className="small muted num">{plots.length}</span>
          </div>
          <label style={{ position: "relative" }}>
            <Search size={16} style={{ position: "absolute", left: 10, top: 12, color: "var(--tinta-3)" }} aria-hidden="true" />
            <input className="input" style={{ paddingLeft: 34 }} placeholder="Cari nama, desa, atau kode" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Cari kebun" />
          </label>
          <div className="filters" role="group" aria-label="Saring status">
            <button className="chip" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>Semua</button>
            <button className="chip" aria-pressed={filter === "rendah"} onClick={() => setFilter("rendah")}>Aman {counts.rendah}</button>
            <button className="chip" aria-pressed={filter === "perlu_cek"} onClick={() => setFilter("perlu_cek")}>Perlu cek {counts.perlu_cek}</button>
            <button className="chip" aria-pressed={filter === "tinggi"} onClick={() => setFilter("tinggi")}>Berisiko {counts.tinggi}</button>
          </div>
        </header>
        {loadErr && <div style={{ padding: "0 16px 12px" }}><Notice kind="danger">{loadErr}</Notice></div>}
        <ul>
          {visible.map((p) => (
            <li key={p.id}>
              <button className={`plot-item ${selected?.id === p.id ? "sel" : ""}`} onClick={() => open(p.id)}>
                <span className="name">{p.farmer.name}</span>
                <StatusTag risk={p.risk_level} />
                <span className="sub num">{p.code}, {ha(p.area_ha)}, {p.farmer.village}</span>
              </button>
            </li>
          ))}
          {!visible.length && !loadErr && <li className="small muted" style={{ padding: 12 }}>Tidak ada kebun yang cocok.</li>}
        </ul>
      </aside>

      <div className="float map-toolbar">
        {mode === "idle" ? (
          <button className="btn btn-primary" onClick={startAdd}>
            <Plus /> Daftarkan kebun
          </button>
        ) : (
          <button className="btn" onClick={cancelAdd}>Batal</button>
        )}
      </div>

      {(mode === "pick" || mode === "loading" || mode === "draw") && (
        <div className="banner" role="status">
          {mode === "pick" && (
            <>
              <MousePointerClick size={18} /> Klik di tengah kebun. AI akan menggambar batasnya dari citra satelit.
              <button className="btn" onClick={() => setMode("draw")}><PenLine /> Gambar manual</button>
            </>
          )}
          {mode === "loading" && <Spinner label="AI membaca citra satelit dan menggambar batas…" />}
          {mode === "draw" && (
            <>
              <PenLine size={18} /> Klik titik-titik sudut kebun, klik dua kali untuk selesai.
            </>
          )}
        </div>
      )}

      <div className="float map-legend" aria-label="Keterangan peta">
        <div className="legend-row"><i className="swatch" style={{ borderColor: RISK_COLOR.rendah, background: "#1e7a4b44" }} /> {riskLabel("rendah")}</div>
        <div className="legend-row"><i className="swatch" style={{ borderColor: RISK_COLOR.perlu_cek, background: "#b7791f44" }} /> {riskLabel("perlu_cek")}</div>
        <div className="legend-row"><i className="swatch" style={{ borderColor: RISK_COLOR.tinggi, background: "#b3261e44" }} /> {riskLabel("tinggi")}</div>
        <div className="legend-row"><i className="swatch" style={{ borderColor: "#ff6b5e", borderStyle: "dashed" }} /> Kawasan konservasi (ilustrasi)</div>
      </div>

      {showDrawer && (
        <aside className="float drawer" aria-live="polite">
          {draft || mode === "loading" ? (
            <NewPlotForm
              draft={draft}
              ai={ai}
              aiErr={aiErr}
              loading={mode === "loading"}
              demo={meta?.satellite_mode !== "live"}
              onCancel={cancelAdd}
              onRedraw={() => { setDraft(null); setMode("pick"); }}
              onSaved={async (d) => {
                cancelAdd();
                await load();
                setSelected(d);
                setJustAnalyzed(true);
                setParams({ kebun: String(d.id) }, { replace: true });
              }}
            />
          ) : selected ? (
            <PassportPanel
              plot={selected}
              justAnalyzed={justAnalyzed}
              onClose={() => { setSelected(null); setParams({}, { replace: true }); }}
              onChanged={async (d, re) => {
                setSelected({ ...d, overlaps: selected.overlaps });
                setJustAnalyzed(!!re);
                load();
              }}
            />
          ) : null}
        </aside>
      )}
      {mode !== "idle" && !draft && aiErr && (
        <div className="float" style={{ top: 130, left: "50%", transform: "translateX(-50%)", padding: 12, width: 420, zIndex: 650 }}>
          <Notice kind="warn">{aiErr}</Notice>
        </div>
      )}
    </div>
  );
}

function NewPlotForm({
  draft,
  ai,
  aiErr,
  loading,
  demo,
  onCancel,
  onRedraw,
  onSaved,
}: {
  draft: GeoPolygon | null;
  ai: DelineateResult | null;
  aiErr: string | null;
  loading: boolean;
  demo: boolean;
  onCancel: () => void;
  onRedraw: () => void;
  onSaved: (d: PlotDetail) => void;
}) {
  const [form, setForm] = useState({ farmer_name: "", village: "Sungai Harapan", label: "Kebun", planting_year_declared: "", witness: "", demo_scenario: "", consent: false });
  const [check, setCheck] = useState<{ area_ha: number; overlaps: Overlap[]; protected: { pct: number; name: string | null } } | null>(null);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const set = (k: keyof typeof form, v: string | boolean) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    if (!draft) return;
    const t = setTimeout(() => api.checkOverlap(draft).then(setCheck).catch(() => setCheck(null)), 350);
    return () => clearTimeout(t);
  }, [draft]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!draft) return;
    if (form.farmer_name.trim().length < 2) return setErr("Isi nama petani.");
    if (!form.consent) return setErr("Petani perlu menyetujui pemakaian data kebun sebelum paspor dibuat.");
    setSaving(true);
    setErr(null);
    try {
      const d = await api.createPlot({
        farmer_name: form.farmer_name.trim(),
        village: form.village.trim(),
        label: form.label.trim() || "Kebun",
        geometry: draft,
        planting_year_declared: form.planting_year_declared ? Number(form.planting_year_declared) : null,
        witness: form.witness.trim() || null,
        consent: form.consent,
        delineation_method: ai?.polygon ? (ai.engine === "sam" ? "ai_sam" : "ai_watershed") : "manual",
        demo_scenario: form.demo_scenario || null,
      });
      onSaved(d);
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} style={{ display: "grid" }}>
      <div style={{ padding: "20px 20px 14px", display: "grid", gap: 6 }}>
        <h2 style={{ fontSize: 20 }}>Daftarkan kebun</h2>
        <p className="small muted">Tinjau garis batas di peta. Tarik titik sudut untuk memperbaiki.</p>
      </div>
      {loading && (
        <div className="section"><Spinner label="Menggambar batas…" /></div>
      )}
      {ai?.polygon && (
        <div className="section" style={{ display: "grid", gap: 8 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <Sparkles size={18} color="var(--emas)" aria-hidden="true" />
            <strong>Draf AI siap ditinjau</strong>
          </div>
          <dl className="facts">
            <div><dt>Model</dt><dd>{ai.engine_label}</dd></div>
            <div><dt>Keyakinan</dt><dd className="num">{Math.round(ai.confidence * 100)}%</dd></div>
            <div><dt>Waktu proses</dt><dd className="num">{ai.ms} ms (CPU)</dd></div>
            <div><dt>Luas draf</dt><dd className="num">{ha(check?.area_ha ?? ai.area_ha)}</dd></div>
          </dl>
          {ai.warnings.map((w) => <Notice key={w} kind="warn">{w}</Notice>)}
          <p className="small faint">{ai.note}</p>
          <button type="button" className="btn btn-quiet" style={{ justifySelf: "start" }} onClick={onRedraw}>Klik ulang di kebun</button>
        </div>
      )}
      {aiErr && !ai?.polygon && draft && <div className="section"><Notice kind="warn">{aiErr}</Notice></div>}
      {check && (check.overlaps.length > 0 || check.protected.pct > 0) && (
        <div className="section" style={{ display: "grid", gap: 8 }}>
          {check.overlaps.map((o) => (
            <Notice key={o.plot_id} kind="danger">
              Bertumpuk {ha(o.overlap_ha)} dengan kebun {o.code} milik {o.farmer}. Sepakati batas dengan pemilik sebelah, lalu geser garisnya.
            </Notice>
          ))}
          {check.protected.pct > 0 && (
            <Notice kind="danger">{check.protected.pct}% kebun masuk {check.protected.name}. Kebun akan berstatus berisiko (legalitas).</Notice>
          )}
        </div>
      )}
      <div className="section" style={{ display: "grid", gap: 12 }}>
        <label className="field"><span>Nama petani</span><input className="input" value={form.farmer_name} onChange={(e) => set("farmer_name", e.target.value)} autoComplete="off" required /></label>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <label className="field"><span>Desa</span><input className="input" value={form.village} onChange={(e) => set("village", e.target.value)} required /></label>
          <label className="field"><span>Tahun tanam (menurut petani)</span><input className="input num" inputMode="numeric" placeholder="mis. 2010" value={form.planting_year_declared} onChange={(e) => set("planting_year_declared", e.target.value.replace(/\D/g, "").slice(0, 4))} /></label>
        </div>
        <label className="field"><span>Saksi batas (ketua poktan / tetangga)</span><input className="input" value={form.witness} onChange={(e) => set("witness", e.target.value)} placeholder="Boleh diisi nanti" /></label>
        {demo && (
          <label className="field">
            <span>Skenario data satelit (mode demo)</span>
            <select className="select" value={form.demo_scenario} onChange={(e) => set("demo_scenario", e.target.value)}>
              {SCENARIOS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
        )}
        <label className="check">
          <input type="checkbox" checked={form.consent} onChange={(e) => set("consent", e.target.checked)} />
          <span>
            Petani setuju lokasi dan batas kebunnya dipakai untuk paspor kebun dan hanya dibagikan ke pembeli yang ia pilih. Tidak ada NIK
            atau foto KTP yang disimpan.
          </span>
        </label>
        {err && <Notice kind="danger">{err}</Notice>}
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-primary" type="submit" disabled={!draft || saving}>
            {saving ? <Spinner /> : null} Simpan &amp; cek satelit
          </button>
          <button className="btn btn-quiet" type="button" onClick={onCancel}>Batal</button>
        </div>
      </div>
    </form>
  );
}
