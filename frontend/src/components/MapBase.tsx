import { LayersControl, TileLayer, useMapEvents } from "react-leaflet";
import { KawasanLayer } from "./KawasanLayer";
import { GfwKawasanOverlay } from "./GfwKawasanLayer";

export const LOSS_OVERLAY = "Kehilangan tutupan pohon 2021–2025 (GFW)";
export const JRC_OVERLAY = "Hutan 2020 (JRC, acuan Uni Eropa)";
export const OVERLAY_EVENT = "pk-overlay";

/** Memberi tahu halaman (legenda) lapisan mana yang sedang dicentang di kontrol lapisan. */
function OverlayWatcher() {
  const send = (name: string, on: boolean) => window.dispatchEvent(new CustomEvent(OVERLAY_EVENT, { detail: { name, on } }));
  useMapEvents({
    overlayadd: (e) => send(e.name, true),
    overlayremove: (e) => send(e.name, false),
  });
  return null;
}

/**
 * Citra satelit asli (Esri World Imagery) + lapisan kehilangan tutupan pohon 2021-2025
 * dan peta hutan JRC 2020, keduanya dari Global Forest Watch (data Hansen/UMD asli) + peta Kawasan Hutan Kemenhut (dimuat browser)
 * + Peta Kawasan Hutan KLHK 2017 yang diambil otomatis lewat backend dari Global Forest Watch.
 */
export function BaseLayers({
  kawasan,
  gfw = false,
}: {
  kawasan?: { service: string; layers: number[] | null } | null;
  /** tampilkan lapisan kawasan hutan otomatis (KLHK 2017 lewat GFW) */
  gfw?: boolean;
}) {
  return (
    <LayersControl position="topright">
      <OverlayWatcher />
      <LayersControl.BaseLayer checked name="Citra satelit">
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          attribution="Citra &copy; Esri, Maxar, Earthstar Geographics"
          maxNativeZoom={19}
          maxZoom={20}
        />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer name="Peta jalan">
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap" maxZoom={19} />
      </LayersControl.BaseLayer>
      <LayersControl.Overlay name={JRC_OVERLAY}>
        <TileLayer
          url="https://tiles.globalforestwatch.org/jrc_global_forest_cover/v2020.3/default/{z}/{x}/{y}.png"
          attribution="EC JRC Global Forest Cover 2020 via Global Forest Watch"
          opacity={0.6}
          maxNativeZoom={14}
          maxZoom={20}
        />
      </LayersControl.Overlay>
      <LayersControl.Overlay name={LOSS_OVERLAY}>
        <TileLayer
          url="https://tiles.globalforestwatch.org/umd_tree_cover_loss/latest/dynamic/{z}/{x}/{y}.png?start_year=2021&end_year=2025&tree_cover_density_threshold=30&render_type=true_color"
          attribution="Hansen/UMD/Google/USGS/NASA via Global Forest Watch"
          opacity={0.85}
          maxNativeZoom={14}
          maxZoom={20}
        />
      </LayersControl.Overlay>
      {gfw && <GfwKawasanOverlay />}
      {kawasan && (
        <LayersControl.Overlay name="Kawasan hutan (peta Kemenhut)">
          <KawasanLayer url={kawasan.service} layers={kawasan.layers} />
        </LayersControl.Overlay>
      )}
    </LayersControl>
  );
}
