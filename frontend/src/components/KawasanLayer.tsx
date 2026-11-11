import L from "leaflet";
import { createLayerComponent, type LayerProps } from "@react-leaflet/core";

/**
 * Lapisan peta dinamis dari ArcGIS MapServer (operasi `export`), dipakai untuk peta Kawasan Hutan
 * Kementerian Kehutanan. Gambar diminta ulang sesuai tampilan peta, langsung oleh browser.
 */
class ArcGisExportLayer extends L.Layer {
  private m?: L.Map;
  private cur?: L.ImageOverlay;
  private pending?: L.ImageOverlay;

  constructor(
    private url: string,
    private opts: { layers?: number[] | null; opacity: number; attribution: string },
  ) {
    super();
  }

  onAdd(map: L.Map) {
    this.m = map;
    if (!map.getPane("kawasan")) {
      const pane = map.createPane("kawasan");
      pane.style.zIndex = "350"; // di atas citra, di bawah poligon kebun
      pane.style.pointerEvents = "none";
    }
    map.on("moveend", this.refresh, this);
    this.refresh();
    return this;
  }

  onRemove(map: L.Map) {
    map.off("moveend", this.refresh, this);
    this.cur?.remove();
    this.pending?.remove();
    this.cur = this.pending = undefined;
    return this;
  }

  getAttribution() {
    return this.opts.attribution;
  }

  setUrl(url: string, layers?: number[] | null) {
    this.url = url;
    this.opts.layers = layers;
    this.refresh();
  }

  private refresh() {
    const map = this.m;
    if (!map) return;
    const b = map.getBounds();
    const size = map.getSize();
    const sw = L.CRS.EPSG3857.project(b.getSouthWest());
    const ne = L.CRS.EPSG3857.project(b.getNorthEast());
    const q = new URLSearchParams({
      bbox: `${sw.x},${sw.y},${ne.x},${ne.y}`,
      bboxSR: "3857",
      imageSR: "3857",
      size: `${size.x},${size.y}`,
      format: "png32",
      transparent: "true",
      dpi: "96",
      f: "image",
    });
    if (this.opts.layers?.length) q.set("layers", `show:${this.opts.layers.join(",")}`);
    const next = L.imageOverlay(`${this.url}/export?${q}`, b, { opacity: this.opts.opacity, pane: "kawasan", interactive: false });
    this.pending?.remove();
    this.pending = next;
    next.once("load", () => {
      if (this.pending !== next) return;
      this.cur?.remove();
      this.cur = next;
      this.pending = undefined;
    });
    next.once("error", () => {
      if (this.pending === next) {
        next.remove();
        this.pending = undefined;
      }
    });
    next.addTo(map);
  }
}

interface Props extends LayerProps {
  url: string;
  layers?: number[] | null;
  opacity?: number;
}

export const KawasanLayer = createLayerComponent<ArcGisExportLayer, Props>(
  ({ url, layers, opacity = 0.55 }, ctx) => ({
    instance: new ArcGisExportLayer(url, {
      layers,
      opacity,
      attribution: "Kawasan hutan &copy; Kementerian Kehutanan (SIGAP)",
    }),
    context: ctx,
  }),
  (instance, props, prev) => {
    if (props.url !== prev.url || props.layers?.join() !== prev.layers?.join()) instance.setUrl(props.url, props.layers);
  },
);
