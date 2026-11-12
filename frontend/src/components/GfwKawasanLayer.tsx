import { useEffect, useRef, useState } from "react";
import type { LayersControlEvent } from "leaflet";
import { GeoJSON, LayerGroup, LayersControl, useMap } from "react-leaflet";
import type { KawasanMap } from "../lib/types";
import { api } from "../lib/api";
import { FUNGSI_COLOR } from "../lib/format";

export const GFW_LAYER_NAME = "Kawasan hutan KLHK 2017 (otomatis, GFW)";
export const GFW_STATUS_EVENT = "pk:gfw-kawasan-status";
export type GfwStatus = { state: "off" | "zoom" | "loading" | "ok" | "error"; codes?: string[]; message?: string };
const MIN_ZOOM = 12;

function emit(s: GfwStatus) {
  window.dispatchEvent(new CustomEvent<GfwStatus>(GFW_STATUS_EVENT, { detail: s }));
}

export function useGfwStatus(): GfwStatus {
  const [s, setS] = useState<GfwStatus>({ state: "off" });
  useEffect(() => {
    const h = (e: Event) => {
      const d = (e as CustomEvent<GfwStatus>).detail;
      // saat memuat ulang (geser peta), keterangan fungsi sebelumnya tetap ditampilkan
      setS((prev) => ({ ...d, codes: d.codes ?? (d.state === "loading" ? prev.codes : undefined) }));
    };
    window.addEventListener(GFW_STATUS_EVENT, h);
    return () => window.removeEventListener(GFW_STATUS_EVENT, h);
  }, []);
  return s;
}

/**
 * Lapisan kawasan hutan yang terdeteksi otomatis untuk area yang sedang dilihat: backend mengambil
 * Peta Kawasan Hutan KLHK 2017 dari Global Forest Watch (tile vektor), lalu memotongnya sesuai tampilan.
 * Selama lapisan ini menampilkan data, salinan lokal yang sama (punya gfw_fid) disembunyikan halaman peta.
 */
function GfwFeatures() {
  const map = useMap();
  const [on, setOn] = useState(true);
  const [data, setData] = useState<KawasanMap["features"]>([]);
  const ctrl = useRef<AbortController | null>(null);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    const add = (e: LayersControlEvent) => e.name === GFW_LAYER_NAME && setOn(true);
    const rem = (e: LayersControlEvent) => e.name === GFW_LAYER_NAME && setOn(false);
    map.on("overlayadd", add);
    map.on("overlayremove", rem);
    return () => {
      map.off("overlayadd", add);
      map.off("overlayremove", rem);
    };
  }, [map]);

  useEffect(() => {
    if (!on) {
      ctrl.current?.abort();
      emit({ state: "off" });
      return;
    }
    const load = () => {
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(async () => {
        if (map.getZoom() < MIN_ZOOM) {
          setData([]);
          emit({ state: "zoom" });
          return;
        }
        const b = map.getBounds().pad(0.15);
        ctrl.current?.abort();
        const c = new AbortController();
        ctrl.current = c;
        emit({ state: "loading" });
        try {
          const r = await api.kawasanMap([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()], c.signal);
          if (c.signal.aborted) return;
          if (r.error) {
            emit({ state: "error", message: r.error });
            return;
          }
          setData(r.features);
          emit({ state: "ok", codes: [...new Set(r.features.map((f) => f.properties.fungsi))] });
        } catch (e) {
          if (!c.signal.aborted) emit({ state: "error", message: e instanceof Error ? e.message : String(e) });
        }
      }, 350);
    };
    load();
    map.on("moveend", load);
    return () => {
      map.off("moveend", load);
      window.clearTimeout(timer.current);
    };
  }, [map, on]);

  useEffect(() => () => { ctrl.current?.abort(); emit({ state: "off" }); }, []);

  return (
    <>
      {data.map((f, i) => {
        const col = FUNGSI_COLOR[f.properties.fungsi] ?? FUNGSI_COLOR["?"];
        return (
          <GeoJSON
            key={`${f.properties.gfw_fid ?? i}-${JSON.stringify(f.geometry.coordinates).length}`}
            data={f as never}
            style={{ color: col, weight: 2, fillColor: col, fillOpacity: 0.12, dashArray: "6 4" }}
            interactive={false}
          />
        );
      })}
    </>
  );
}

export function GfwKawasanOverlay() {
  return (
    <LayersControl.Overlay checked name={GFW_LAYER_NAME}>
      <LayerGroup>
        <GfwFeatures />
      </LayerGroup>
    </LayersControl.Overlay>
  );
}
