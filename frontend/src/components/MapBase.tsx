import { LayersControl, TileLayer } from "react-leaflet";

/**
 * Citra satelit asli (Esri World Imagery) + lapisan kehilangan tutupan pohon 2021-2025
 * dari Global Forest Watch (data Hansen/UMD asli, dimuat langsung oleh browser).
 */
export function BaseLayers() {
  return (
    <LayersControl position="topright">
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
      <LayersControl.Overlay name="Kehilangan tutupan pohon 2021–2024 (GFW)">
        <TileLayer
          url="https://tiles.globalforestwatch.org/umd_tree_cover_loss/latest/dynamic/{z}/{x}/{y}.png?start_year=2021&end_year=2024&tree_cover_density_threshold=30&render_type=true_color"
          attribution="Hansen/UMD/Google/USGS/NASA via Global Forest Watch"
          opacity={0.85}
          maxNativeZoom={12}
          maxZoom={20}
        />
      </LayersControl.Overlay>
    </LayersControl>
  );
}
