import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "@geoman-io/leaflet-geoman-free";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";
import { Circle, CircleMarker, GeoJSON, MapContainer, Polygon, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { useSearchParams } from "react-router-dom";
import { BadgeCheck, Crosshair, LocateFixed, MousePointerClick, PenLine, Plus, Scissors, Search, Sparkles } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ha, KAWASAN_SOURCE_SHORT, kawasanText, RISK_COLOR, riskLabel } from "../lib/format";
import { averageFix, distanceM, getFix, type GpsFix, watchFix } from "../lib/gps";
import type {
  DelineateResult,
  GeoPolygon,
  KawasanInfo,
  LandProof,
  Meta,
  OverlapCheck,
  PlotDetail,
  PlotSummary,
  ProtectedArea,
  Risk,
  SideKey,
  SideType,
  StdbStatus,
} from "../lib/types";
import { BaseLayers } from "../components/MapBase";
import { useKawasanLayerStatus } from "../components/KawasanLayer";
import { PassportPanel } from "../components/PassportPanel";
import { Notice, Spinner, StatusTag } from "../components/ui";

const CENTER: [number, number] = [-0.172, 101.893];
const toLatLngs = (g: GeoPolygon) => g.coordinates[0].map(([lng, lat]) => [lat, lng] as [number, number]);
const toGeo = (latlngs: L.LatLng[]): GeoPolygon => {
  const ring = latlngs.map((p) => [Number(p.lng.toFixed(7)), Number(p.lat.toFixed(7))]);
  ring.push(ring[0]);
  return { type: "Polygon", coordinates: [ring] };
};

type Mode = "idle" | "start" | "locating" | "pick" | "loading" | "edit" | "draw";
const SCENARIOS: [string, string][] = [
  ["", "Otomatis (sesuai lokasi)"],
  ["sawit_tua_stabil", "Sawit stabil sejak sebelum 2018"],
  ["dibuka_2019", "Dibuka 2019, sebelum batas EUDR"],
  ["peremajaan_2023", "Peremajaan sawit 2023 (PSR)"],
  ["hutan_dibuka_2022", "Hutan dibuka 2022"],
  ["data_kurang", "Citra berawan, bukti kurang"],
];

function FlyTo({ target, point }: { target: GeoPolygon | null; point?: [number, number] | null }) {
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
  useEffect(() => {
    if (point) map.flyTo(point, 18, { duration: 0.8 });
  }, [point, map]);
  return null;
}

/** Titik biru "Anda di sini" + lingkaran akurasi GPS. */
function BlueDot({ fix }: { fix: GpsFix | null }) {
  if (!fix) return null;
  return (
    <>
      {fix.accuracy > 0 && <Circle center={[fix.lat, fix.lng]} radius={fix.accuracy} pathOptions={{ color: "#4ea4ff", weight: 1, fillOpacity: 0.12 }} interactive={false} />}
      <CircleMarker center={[fix.lat, fix.lng]} radius={7} pathOptions={{ color: "#fff", weight: 2.5, fillColor: "#1a73e8", fillOpacity: 1 }} interactive={false}>
        <Tooltip permanent direction="top" offset={[0, -8]} className="pk-label">Anda di sini{fix.simulated ? " (simulasi)" : ""}</Tooltip>
      </CircleMarker>
    </>
  );
}

function CenterReader({ onReady }: { onReady: (get: () => [number, number]) => void }) {
  const map = useMap();
  useEffect(() => {
    onReady(() => {
      const c = map.getCenter();
      return [c.lat, c.lng];
    });
  }, [map, onReady]);
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
  const { can } = useAuth();
  const canEdit = can("koperasi");
  const [plots, setPlots] = useState<PlotSummary[]>([]);
  const [areas, setAreas] = useState<ProtectedArea[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [selected, setSelected] = useState<PlotDetail | null>(null);
  const [justAnalyzed, setJustAnalyzed] = useState(false);
  const [flyTarget, setFlyTarget] = useState<GeoPolygon | null>(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Risk | "all" | "siap">("all");
  const [mode, setMode] = useState<Mode>("idle");
  const kawasanLayer = useKawasanLayerStatus();
  const [draft, setDraft] = useState<GeoPolygon | null>(null);
  const [ai, setAi] = useState<DelineateResult | null>(null);
  const [aiErr, setAiErr] = useState<string | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [fix, setFix] = useState<GpsFix | null>(null);
  const [gpsProgress, setGpsProgress] = useState<{ n: number; best: number | null; secs: number } | null>(null);
  const [gpsErr, setGpsErr] = useState<string | null>(null);
  const [flyPoint, setFlyPoint] = useState<[number, number] | null>(null);
  const stopWatch = useRef<(() => void) | null>(null);
  const centerGetter = useRef<() => [number, number]>(() => CENTER);
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
        (filter === "all" || (filter === "siap" ? p.eudr_ready : p.risk_level === filter)) &&
        (!s || p.farmer.name.toLowerCase().includes(s) || p.code.toLowerCase().includes(s) || p.farmer.village.toLowerCase().includes(s)),
    );
  }, [plots, q, filter]);
  const counts = useMemo(() => {
    const c: Record<string, number> = { rendah: 0, perlu_cek: 0, tinggi: 0, siap: 0 };
    plots.forEach((p) => {
      if (p.risk_level) c[p.risk_level]++;
      if (p.eudr_ready) c.siap++;
    });
    return c;
  }, [plots]);

  const startAdd = () => {
    setSelected(null);
    setDraft(null);
    setAi(null);
    setAiErr(null);
    setFix(null);
    setGpsErr(null);
    setMode("start");
  };
  const cancelAdd = () => {
    stopWatch.current?.();
    setMode("idle");
    setDraft(null);
    setAi(null);
    setAiErr(null);
    setFix(null);
    setGpsProgress(null);
    setGpsErr(null);
  };

  /** "Saya sedang di kebun": kumpulkan beberapa bacaan GPS, rata-ratakan yang paling akurat. */
  const locate = () => {
    setGpsErr(null);
    setMode("locating");
    const samples: GpsFix[] = [];
    const t0 = Date.now();
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      window.clearTimeout(timer);
      stopWatch.current?.();
      setGpsProgress(null);
      const avg = averageFix(samples);
      if (!avg || avg.accuracy > 60) {
        setGpsErr(
          avg
            ? `Sinyal GPS kurang tepat (±${Math.round(avg.accuracy)} m). Coba di tempat lebih terbuka, atau tunjuk kebun di peta.`
            : "Tidak ada bacaan GPS. Tunjuk kebun di peta, atau simulasikan posisi.",
        );
        setMode("start");
        return;
      }
      applyFix(avg);
    };
    const timer = window.setTimeout(finish, 20000);
    const stop = watchFix(
      (f) => {
        samples.push(f);
        const best = Math.min(...samples.map((x) => x.accuracy));
        setGpsProgress({ n: samples.length, best, secs: Math.round((Date.now() - t0) / 1000) });
        if (samples.length >= 5 && best <= 10) finish();
      },
      (msg) => {
        if (done) return;
        done = true;
        window.clearTimeout(timer);
        stopWatch.current?.();
        setGpsProgress(null);
        setGpsErr(msg);
        setMode("start");
      },
    );
    stopWatch.current = () => {
      done = true;
      window.clearTimeout(timer);
      stop();
    };
  };
  const simulate = () => {
    const [lat, lng] = centerGetter.current();
    applyFix({ lat, lng, accuracy: 0, simulated: true });
  };
  const applyFix = (f: GpsFix) => {
    setFix(f);
    setFlyPoint([f.lat, f.lng]);
    onPick(f.lat, f.lng);
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
        <BaseLayers kawasan={meta?.kawasan && meta.kawasan.policy !== "lokal" ? meta.kawasan : null} />
        <FlyTo target={flyTarget} point={flyPoint} />
        <CenterReader onReady={useCallback((g: () => [number, number]) => { centerGetter.current = g; }, [])} />
        <BlueDot fix={mode !== "idle" ? fix : null} />
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
            <button className="chip" aria-pressed={filter === "siap"} onClick={() => setFilter("siap")}>Siap EUDR {counts.siap}</button>
          </div>
        </header>
        {loadErr && <div style={{ padding: "0 16px 12px" }}><Notice kind="danger">{loadErr}</Notice></div>}
        <ul>
          {visible.map((p) => (
            <li key={p.id}>
              <button className={`plot-item ${selected?.id === p.id ? "sel" : ""}`} onClick={() => open(p.id)}>
                <span className="name">
                  {p.farmer.name}
                  {p.eudr_ready && <BadgeCheck size={15} color="var(--aman)" aria-label="Siap EUDR" style={{ marginLeft: 5, verticalAlign: -2 }} />}
                </span>
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
          canEdit ? (
            <button className="btn btn-primary" onClick={startAdd}>
              <Plus /> Daftarkan kebun
            </button>
          ) : (
            <span className="small muted" style={{ padding: "8px 12px" }}>Pendaftaran kebun dilakukan petugas koperasi.</span>
          )
        ) : (
          <button className="btn" onClick={cancelAdd}>Batal</button>
        )}
      </div>

      {mode === "start" && (
        <div className="float start-card" role="dialog" aria-label="Cara menentukan lokasi kebun">
          <h3>Di mana kebunnya?</h3>
          <button className="start-opt primary" onClick={locate}>
            <LocateFixed aria-hidden="true" />
            <span><strong>Saya sedang di kebun</strong><span className="small">Pakai GPS ponsel. AI menggambar batas dari titik Anda; cukup untuk EUDR bila kebun di bawah 4 ha.</span></span>
          </button>
          <button className="start-opt" onClick={() => setMode("pick")}>
            <MousePointerClick aria-hidden="true" />
            <span><strong>Tunjuk di peta</strong><span className="small">Klik tengah kebun di citra satelit.</span></span>
          </button>
          <button className="start-opt" onClick={() => setMode("draw")}>
            <PenLine aria-hidden="true" />
            <span><strong>Gambar manual</strong><span className="small">Klik sudut-sudut kebun satu per satu.</span></span>
          </button>
          {gpsErr && (
            <>
              <Notice kind="warn">{gpsErr}</Notice>
              <button className="btn btn-quiet" onClick={simulate}>
                <Crosshair /> Pakai titik tengah peta (simulasi posisi)
              </button>
            </>
          )}
          {!gpsErr && meta?.satellite_mode !== "live" && (
            <button className="btn btn-quiet small" onClick={simulate} title="Untuk demo di laptop yang tidak punya GPS">
              <Crosshair /> Demo di laptop: simulasikan posisi di tengah peta
            </button>
          )}
        </div>
      )}
      {mode === "locating" && (
        <div className="banner" role="status">
          <Spinner
            label={gpsProgress ? `Membaca GPS… ${gpsProgress.n} bacaan, terbaik ±${Math.round(gpsProgress.best ?? 0)} m (${gpsProgress.secs} dtk)` : "Menunggu izin dan sinyal GPS…"}
          />
          <button className="btn" onClick={() => { stopWatch.current?.(); setMode("start"); }}>Batal</button>
        </div>
      )}
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
        {areas.length > 0 && (
          <div className="legend-row">
            <i className="swatch" style={{ borderColor: "#ff6b5e", borderStyle: "dashed" }} />{" "}
            {areas.every((a) => a.is_demo) ? "Kawasan konservasi ilustrasi demo (bukan peta resmi)" : "Kawasan hutan (peta lokal)"}
          </div>
        )}
        {kawasanLayer === "loading" && <div className="legend-row faint">Memuat peta kawasan Kemenhut…</div>}
        {kawasanLayer === "ok" && <div className="legend-row"><i className="swatch" style={{ borderColor: "#2f6f4f", background: "#7fbf7f88" }} /> Kawasan hutan (Kemenhut, 1:250.000)</div>}
        {kawasanLayer === "error" && (
          <div className="legend-row legend-error" role="status">
            Peta kawasan Kemenhut gagal dimuat: server Kemenhut sedang tidak merespons. Coba lagi nanti.
          </div>
        )}
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
              fix={fix}
              onDraft={setDraft}
              onCancel={cancelAdd}
              onRedraw={() => { setDraft(null); setMode("start"); }}
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

const SIDE_KEYS: SideKey[] = ["utara", "timur", "selatan", "barat"];
const SIDE_OPTS: [SideType | "", string][] = [
  ["", "Pilih…"],
  ["parit", "Parit / kanal"],
  ["jalan", "Jalan"],
  ["kebun", "Kebun tetangga"],
  ["hutan", "Hutan / semak"],
  ["sungai", "Sungai"],
  ["lainnya", "Lainnya"],
];
const RELATIONS = ["ketua kelompok tani", "tetangga utara", "tetangga timur", "tetangga selatan", "tetangga barat", "kepala dusun", "saksi lain"];
const LAND_OPTS: [LandProof | "", string][] = [
  ["", "Belum ada"],
  ["sertifikat", "Sertifikat tanah (SHM/BPN)"],
  ["surat_desa", "Surat keterangan desa (SKT/SKGR)"],
  ["pernyataan", "Pernyataan penguasaan fisik + 2 saksi"],
];
const STDB_OPTS: [StdbStatus, string][] = [
  ["belum", "Belum diurus"],
  ["proses", "Sedang diurus"],
  ["ada", "Sudah terbit"],
];

/** Mengganti titik sudut poligon yang paling dekat dengan posisi GPS (petani berdiri di sudut kebun). */
function snapCorner(g: GeoPolygon, at: [number, number]): { geom: GeoPolygon; moved: number } {
  const ring = g.coordinates[0].slice(0, -1);
  let best = 0;
  let bestD = Infinity;
  ring.forEach(([lng, lat], i) => {
    const d = distanceM([lat, lng], at);
    if (d < bestD) {
      bestD = d;
      best = i;
    }
  });
  const next = ring.map((c, i) => (i === best ? [Number(at[1].toFixed(7)), Number(at[0].toFixed(7))] : c));
  next.push(next[0]);
  return { geom: { type: "Polygon", coordinates: [next] }, moved: bestD };
}

function NewPlotForm({
  draft,
  ai,
  aiErr,
  loading,
  demo,
  fix,
  onDraft,
  onCancel,
  onRedraw,
  onSaved,
}: {
  draft: GeoPolygon | null;
  ai: DelineateResult | null;
  aiErr: string | null;
  loading: boolean;
  demo: boolean;
  fix: GpsFix | null;
  onDraft: (g: GeoPolygon) => void;
  onCancel: () => void;
  onRedraw: () => void;
  onSaved: (d: PlotDetail) => void;
}) {
  const [form, setForm] = useState({
    farmer_name: "",
    village: "Sungai Harapan",
    label: "Kebun",
    planting_year_declared: "",
    demo_scenario: "",
    consent: false,
    land_proof: "" as LandProof | "",
    land_proof_ref: "",
    stdb_status: "belum" as StdbStatus,
    stdb_number: "",
    dispute: false,
    dispute_note: "",
  });
  const [sides, setSides] = useState<Record<SideKey, { jenis: SideType | ""; tetangga: string }>>({
    utara: { jenis: "", tetangga: "" },
    timur: { jenis: "", tetangga: "" },
    selatan: { jenis: "", tetangga: "" },
    barat: { jenis: "", tetangga: "" },
  });
  const [wits, setWits] = useState([
    { name: "", relation: "ketua kelompok tani" },
    { name: "", relation: "tetangga utara" },
  ]);
  const [check, setCheck] = useState<OverlapCheck | null>(null);
  const [checking, setChecking] = useState(false);
  const [fitting, setFitting] = useState(false);
  const [fitMsg, setFitMsg] = useState<string | null>(null);
  const [cornerMsg, setCornerMsg] = useState<{ kind: "ok" | "warn"; text: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    if (!draft) return;
    let live = true;
    const t = setTimeout(() => {
      setChecking(true);
      api
        .checkOverlap(draft)
        .then((r) => live && setCheck(r))
        .catch(() => live && setCheck(null))
        .finally(() => live && setChecking(false));
    }, 350);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [draft]);

  const fit = async () => {
    if (!draft) return;
    setFitting(true);
    setFitMsg(null);
    try {
      const r = await api.fitNeighbors(draft);
      onDraft(r.geometry);
      setFitMsg(`Dipotong ${ha(r.removed_ha)} mengikuti batas ${r.neighbors.map((n) => `${n.code} (${n.farmer})`).join(", ")}. Tetap konfirmasi dengan pemilik sebelah.`);
    } catch (e) {
      setFitMsg((e as Error).message);
    } finally {
      setFitting(false);
    }
  };

  const corner = async () => {
    if (!draft) return;
    setCornerMsg(null);
    try {
      const f = await getFix();
      const r = snapCorner(draft, [f.lat, f.lng]);
      if (r.moved > 60) {
        setCornerMsg({ kind: "warn", text: `Posisi Anda ${Math.round(r.moved)} m dari sudut terdekat. Berdirilah tepat di sudut kebun lalu coba lagi.` });
        return;
      }
      onDraft(r.geom);
      setCornerMsg({ kind: "ok", text: `Sudut digeser ${Math.round(r.moved)} m ke posisi GPS Anda (±${Math.round(f.accuracy)} m).` });
    } catch (e) {
      setCornerMsg({ kind: "warn", text: (e as Error).message });
    }
  };

  const filledWits = wits.filter((w) => w.name.trim().length >= 3);
  const landWarn =
    form.land_proof === "pernyataan" && filledWits.length < 2
      ? "Pernyataan penguasaan fisik butuh 2 saksi."
      : !form.land_proof
        ? "Tanpa bukti penguasaan lahan, kebun belum bisa berstatus Siap EUDR. Paspor tetap dibuat."
        : form.stdb_status === "belum"
          ? "STDB belum diurus: kebun belum Siap EUDR sampai STDB diajukan."
          : null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!draft) return;
    if (form.farmer_name.trim().length < 2) return setErr("Isi nama petani.");
    if (!form.consent) return setErr("Petani perlu menyetujui pemakaian data kebun sebelum paspor dibuat.");
    setSaving(true);
    setErr(null);
    try {
      const boundary_sides = Object.fromEntries(
        SIDE_KEYS.filter((k) => sides[k].jenis).map((k) => [k, { jenis: sides[k].jenis, tetangga: sides[k].tetangga.trim() || null }]),
      );
      const d = await api.createPlot({
        farmer_name: form.farmer_name.trim(),
        village: form.village.trim(),
        label: form.label.trim() || "Kebun",
        geometry: draft,
        planting_year_declared: form.planting_year_declared ? Number(form.planting_year_declared) : null,
        witnesses: filledWits.map((w) => ({ name: w.name.trim(), relation: w.relation })),
        boundary_sides,
        gps: fix && !fix.simulated ? { lat: fix.lat, lng: fix.lng, accuracy_m: fix.accuracy } : null,
        land_proof: form.land_proof || null,
        land_proof_ref: form.land_proof_ref.trim() || null,
        stdb_status: form.stdb_status,
        stdb_number: form.stdb_number.trim() || null,
        dispute: form.dispute,
        dispute_note: form.dispute ? form.dispute_note.trim() || null : null,
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

  const overlapsBig = (check?.overlaps ?? []).filter((o) => o.overlap_ha >= 0.01);

  return (
    <form onSubmit={submit} style={{ display: "grid" }}>
      <div style={{ padding: "20px 20px 14px", display: "grid", gap: 6 }}>
        <h2 style={{ fontSize: 20 }}>Daftarkan kebun</h2>
        <p className="small muted">Tinjau garis batas di peta bersama petani dan saksi. Tarik titik sudut untuk memperbaiki.</p>
        {fix && (
          <p className="small" style={{ color: fix.simulated ? "var(--cek)" : "var(--aman)" }}>
            {fix.simulated
              ? "Posisi disimulasikan dari tengah peta (demo). Titik GPS tidak disimpan."
              : `Titik GPS tersimpan (±${Math.round(fix.accuracy)} m). Untuk kebun di bawah 4 ha, titik ini sudah memenuhi syarat geolokasi EUDR.`}
          </p>
        )}
      </div>
      {loading && <div className="section"><Spinner label="AI menggambar batas dari citra satelit…" /></div>}
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
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <button type="button" className="btn btn-quiet" onClick={onRedraw}>Ulangi dari awal</button>
            <button type="button" className="btn btn-quiet" onClick={corner} title="Berdiri di salah satu sudut kebun, lalu tekan">
              <LocateFixed /> Sudut ini = posisi saya
            </button>
          </div>
          {cornerMsg && <Notice kind={cornerMsg.kind}>{cornerMsg.text}</Notice>}
        </div>
      )}
      {aiErr && !ai?.polygon && draft && <div className="section"><Notice kind="warn">{aiErr}</Notice></div>}
      {draft && (checking || check) && (
        <div className="section" style={{ display: "grid", gap: 8 }}>
          {overlapsBig.map((o) => (
            <Notice key={o.plot_id} kind="danger">
              Bertumpuk {ha(o.overlap_ha)} dengan kebun {o.code} milik {o.farmer}.
            </Notice>
          ))}
          {overlapsBig.length > 0 && (
            <button type="button" className="btn" onClick={fit} disabled={fitting} style={{ justifySelf: "start" }}>
              {fitting ? <Spinner /> : <Scissors />} Rapikan dengan kebun tetangga
            </button>
          )}
          {fitMsg && <Notice kind="info">{fitMsg}</Notice>}
          {checking && !check ? <Spinner label="Mengecek status kawasan hutan di peta Kemenhut…" /> : check && <KawasanNotice k={check.protected} />}
        </div>
      )}

      <div className="section form-grid">
        <h4>Petani</h4>
        <label className="field"><span>Nama petani</span><input className="input" value={form.farmer_name} onChange={(e) => set("farmer_name", e.target.value)} autoComplete="off" required /></label>
        <div className="two">
          <label className="field"><span>Desa</span><input className="input" value={form.village} onChange={(e) => set("village", e.target.value)} required /></label>
          <label className="field"><span>Tahun tanam (menurut petani)</span><input className="input num" inputMode="numeric" placeholder="mis. 2010" value={form.planting_year_declared} onChange={(e) => set("planting_year_declared", e.target.value.replace(/\D/g, "").slice(0, 4))} /></label>
        </div>
      </div>

      <div className="section form-grid">
        <h4>Batas di lapangan</h4>
        <p className="small muted">Lebih mudah daripada membaca citra: sebutkan apa yang ada di tiap sisi kebun.</p>
        {SIDE_KEYS.map((k) => (
          <div className="side-row" key={k}>
            <span className="side-k">{k[0].toUpperCase() + k.slice(1)}</span>
            <select className="select" value={sides[k].jenis} aria-label={`Batas ${k}`} onChange={(e) => setSides({ ...sides, [k]: { ...sides[k], jenis: e.target.value as SideType } })}>
              {SIDE_OPTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            {sides[k].jenis === "kebun" ? (
              <input className="input" placeholder="Nama tetangga" value={sides[k].tetangga} onChange={(e) => setSides({ ...sides, [k]: { ...sides[k], tetangga: e.target.value } })} aria-label={`Nama tetangga ${k}`} />
            ) : <span />}
          </div>
        ))}
      </div>

      <div className="section form-grid">
        <h4>Saksi batas</h4>
        {wits.map((w, i) => (
          <div className="two" key={i}>
            <input className="input" placeholder={`Nama saksi ${i + 1}`} value={w.name} onChange={(e) => setWits(wits.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} aria-label={`Nama saksi ${i + 1}`} />
            <select className="select" value={w.relation} onChange={(e) => setWits(wits.map((x, j) => (j === i ? { ...x, relation: e.target.value } : x)))} aria-label={`Hubungan saksi ${i + 1}`}>
              {RELATIONS.map((r) => <option key={r} value={r}>{r[0].toUpperCase() + r.slice(1)}</option>)}
            </select>
          </div>
        ))}
        <p className="small faint">Boleh diisi nanti dari paspor. Batas belum sah sebelum ada saksi.</p>
      </div>

      <div className="section form-grid">
        <h4>Bukti lahan</h4>
        <div className="two">
          <label className="field"><span>Bukti penguasaan</span>
            <select className="select" value={form.land_proof} onChange={(e) => set("land_proof", e.target.value as LandProof | "")}>
              {LAND_OPTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className="field"><span>Nomor dokumen (opsional)</span><input className="input" value={form.land_proof_ref} onChange={(e) => set("land_proof_ref", e.target.value)} disabled={!form.land_proof || form.land_proof === "pernyataan"} /></label>
        </div>
        <div className="two">
          <label className="field"><span>STDB (Surat Tanda Daftar Budidaya)</span>
            <select className="select" value={form.stdb_status} onChange={(e) => set("stdb_status", e.target.value as StdbStatus)}>
              {STDB_OPTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className="field"><span>Nomor STDB (opsional)</span><input className="input" value={form.stdb_number} onChange={(e) => set("stdb_number", e.target.value)} disabled={form.stdb_status === "belum"} /></label>
        </div>
        <label className="check">
          <input type="checkbox" checked={form.dispute} onChange={(e) => set("dispute", e.target.checked)} />
          <span>Ada sengketa atau klaim lain atas lahan ini</span>
        </label>
        {form.dispute && <input className="input" placeholder="Jelaskan singkat" value={form.dispute_note} onChange={(e) => set("dispute_note", e.target.value)} maxLength={240} aria-label="Keterangan sengketa" />}
        {landWarn && <Notice kind="info">{landWarn}</Notice>}
        <p className="small faint">Sertifikat tanah tidak wajib: ISPO menerima surat penguasaan fisik, dan EUDR hanya meminta dokumen yang diwajibkan hukum setempat.</p>
      </div>

      <div className="section form-grid">
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

/** Status kawasan hutan saat kebun digambar: hasil cek otomatis ke peta Kemenhut. */
function KawasanNotice({ k }: { k: KawasanInfo }) {
  const src = KAWASAN_SOURCE_SHORT[k.source ?? "tidak_ada"] ?? "peta kawasan";
  const pct = Math.round(k.pct);
  if (k.pct > 5)
    return (
      <Notice kind="danger">
        <strong>{kawasanText(k)}</strong> menurut {src}
        {k.name && k.name !== k.label ? ` (${k.name})` : ""}. Kebun akan berstatus berisiko karena aspek legalitas lahan.
      </Notice>
    );
  if (k.pct > 0)
    return (
      <Notice kind="warn">
        {pct < 1 ? "Sedikit" : `${pct}%`} bagian kebun bersinggungan dengan batas {k.label ?? "kawasan hutan"} ({src}). Bisa karena
        ketelitian peta; pastikan patok batas di lapangan.
      </Notice>
    );
  if ((k.unknown_pct ?? 0) > 5)
    return <Notice kind="warn">Kebun berada di poligon {src} yang fungsinya belum terbaca. Status akan menjadi perlu cek.</Notice>;
  if (k.source === "tidak_ada" || (k.warnings?.length && k.source !== "kemenhut"))
    return (
      <Notice kind="info">
        Status kawasan hutan belum bisa dicek ke peta Kemenhut (layanan tidak terjangkau)
        {k.source === "ilustrasi" ? "; sementara memakai peta ilustrasi demo" : ""}. Akan dicek ulang saat analisis.
      </Notice>
    );
  return <Notice kind="ok">{kawasanText(k)} menurut {src}.</Notice>;
}
