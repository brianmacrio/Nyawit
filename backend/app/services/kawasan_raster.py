"""Membaca peta Kawasan Hutan Kemenhut dari gambarnya.

Layanan peta Kemenhut terbaru (KWSHUTAN_AR_250K, revisi Juni 2026) hanya mengizinkan kemampuan
"Map": gambar peta boleh diminta (operasi `export`), tetapi `identify` dan `query` ditolak.
Gambar itu tetap memuat informasi lengkap, karena setiap fungsi kawasan digambar dengan warna
padat yang tercantum di renderer layanan (mis. Hutan Produksi Tetap = kuning 255,255,0).

Algoritma per sel 0,01 derajat (~1,1 km):
1. Minta gambar PNG sel itu dalam koordinat geografis (EPSG:4326), 512 x 512 piksel (~2,2 m/piksel).
2. Baca palet warna dari renderer layanan: nilai -> label ("Hutan Produksi Tetap") -> warna RGB.
3. Setiap piksel dicocokkan ke warna palet terdekat (jarak RGB). Piksel tembus pandang = tidak ada
   data (mis. laut); piksel buram yang warnanya tidak dikenal dicatat sebagai "fungsi tidak terbaca"
   agar perubahan simbol peta tidak diam-diam membuat kebun terbaca aman.
4. Piksel per label diubah kembali menjadi poligon (run-length per baris, digabung), lalu dipakai
   persis seperti poligon hasil `query`: persentase luas kebun di tiap fungsi kawasan.

Ini pemrosesan citra yang deterministik, bukan model yang dilatih: warnanya didefinisikan oleh
layanan itu sendiri, jadi aturan pasti lebih tepat dan bisa diaudit daripada tebakan model.
"""
from __future__ import annotations

import io
from typing import Any

import numpy as np
from PIL import Image
from shapely.geometry import box, mapping
from shapely.ops import unary_union

IMG_PX = 512
MATCH_TOL = 60  # jarak RGB maksimum untuk piksel tepi yang sedikit tercampur
UNKNOWN = "warna tidak dikenal"


def palette_from_layer(layer: dict) -> list[dict]:
    """Palet [{label, rgb}] dari renderer layer ArcGIS (uniqueValue, classBreaks, atau simple)."""
    r = (layer.get("drawingInfo") or {}).get("renderer") or {}
    items: list[tuple[str, Any]] = []
    t = r.get("type")
    if t == "uniqueValue":
        for u in r.get("uniqueValueInfos") or []:
            items.append((u.get("label") or str(u.get("value")), u.get("symbol")))
        if r.get("defaultSymbol"):
            items.append((r.get("defaultLabel") or "Lainnya", r.get("defaultSymbol")))
    elif t == "classBreaks":
        for c in r.get("classBreakInfos") or []:
            items.append((c.get("label") or "", c.get("symbol")))
    elif t == "simple":
        items.append((r.get("label") or layer.get("name") or "", r.get("symbol")))
    out = []
    seen = set()
    for label, sym in items:
        col = (sym or {}).get("color")
        if not col or len(col) < 3 or (len(col) > 3 and col[3] == 0):
            continue  # simbol tanpa warna isi (mis. kawasan konservasi laut yang transparan)
        key = (label, tuple(col[:3]))
        if key in seen:
            continue
        seen.add(key)
        out.append({"label": label, "rgb": [int(c) for c in col[:3]]})
    return out


def classify_pixels(rgba: np.ndarray, palette: list[dict], tol: int = MATCH_TOL) -> tuple[np.ndarray, list[str]]:
    """Larik indeks label per piksel (-1 = kosong/tembus pandang) dan daftar label.

    Label terakhir selalu UNKNOWN untuk piksel buram yang tidak cocok dengan palet mana pun.
    """
    labels: list[str] = []
    for p in palette:
        if p["label"] not in labels:
            labels.append(p["label"])
    labels.append(UNKNOWN)
    unk = len(labels) - 1
    cols = np.array([p["rgb"] for p in palette], dtype=np.int32).reshape(-1, 3)
    lab_of = np.array([labels.index(p["label"]) for p in palette], dtype=np.int16)
    rgb = rgba[..., :3].astype(np.int32)
    alpha = rgba[..., 3] if rgba.shape[-1] == 4 else np.full(rgba.shape[:2], 255, np.uint8)
    # cocokkan warna unik saja (biasanya < 50 warna), lalu petakan kembali ke piksel
    packed = (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2]
    uniq, inv = np.unique(packed.ravel(), return_inverse=True)
    ucol = np.stack([(uniq >> 16) & 255, (uniq >> 8) & 255, uniq & 255], axis=1)
    if len(cols):
        d = ((ucol[:, None, :] - cols[None, :, :]) ** 2).sum(-1)
        nearest = d.argmin(1)
        ulab = np.where(d[np.arange(len(uniq)), nearest] <= tol * tol, lab_of[nearest], unk)
        # piksel tepi hasil anti-alias = campuran dua warna palet: ikut warna yang lebih dekat
        for u in np.flatnonzero(ulab == unk):
            c = ucol[u].astype(float)
            best = None
            for a in range(len(cols)):
                for b in range(a + 1, len(cols)):
                    seg = (cols[b] - cols[a]).astype(float)
                    t = float(np.clip(np.dot(c - cols[a], seg) / max(np.dot(seg, seg), 1.0), 0, 1))
                    resid = float(np.sum((cols[a] + t * seg - c) ** 2))
                    if resid <= (tol / 3) ** 2 and (best is None or resid < best[0]):
                        best = (resid, a if t < 0.5 else b)
            if best is not None:
                ulab[u] = lab_of[best[1]]
    else:
        ulab = np.full(len(uniq), unk)
    out = ulab[inv].reshape(packed.shape).astype(np.int16)
    out[alpha < 128] = -1
    return out, labels


def vectorize(idx: np.ndarray, bounds: tuple[float, float, float, float]) -> dict[int, Any]:
    """Piksel berlabel -> poligon per label (koordinat geografis). Baris berurutan dengan rentang sama digabung."""
    h, w = idx.shape
    minx, miny, maxx, maxy = bounds
    sx, sy = (maxx - minx) / w, (maxy - miny) / h
    rects: dict[int, list] = {}
    open_runs: dict[tuple[int, int, int], int] = {}
    for r in range(h + 1):
        cur: set[tuple[int, int, int]] = set()
        if r < h:
            row = idx[r]
            change = np.flatnonzero(np.diff(row)) + 1
            starts = np.r_[0, change]
            ends = np.r_[change, w]
            for s, e in zip(starts.tolist(), ends.tolist()):
                v = int(row[s])
                if v >= 0:
                    cur.add((s, e, v))
        for key in list(open_runs):
            if key not in cur:
                s, e, v = key
                r0 = open_runs.pop(key)
                rects.setdefault(v, []).append(box(minx + s * sx, maxy - r * sy, minx + e * sx, maxy - r0 * sy))
        for key in cur:
            open_runs.setdefault(key, r)
    return {v: unary_union(bs).simplify(min(sx, sy) * 0.5, preserve_topology=True) for v, bs in rects.items()}


def read_png(data: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(data))
    return np.asarray(img.convert("RGBA"))


def features_from_image(data: bytes, bounds: tuple[float, float, float, float], palette: list[dict],
                        layer_id: int | None = None, layer_name: str = "") -> list[dict]:
    """Gambar export -> fitur seperti hasil query: {layer, layer_name, attrs, geometry}."""
    idx, labels = classify_pixels(read_png(data), palette)
    polys = vectorize(idx, bounds)
    out = []
    for v, g in polys.items():
        if g.is_empty:
            continue
        out.append({"layer": layer_id, "layer_name": layer_name, "attrs": {"fungsi_teks": labels[v]},
                    "geometry": mapping(g)})
    return out
