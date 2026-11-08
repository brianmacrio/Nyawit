"""AI penggambar batas kebun dari satu klik ("click-to-segment").

Dua mesin:
* SAM (Segment Anything, Meta AI) - dipakai bila paket `segment_anything` + checkpoint
  tersedia. Studi zero-shot pada lahan petani kecil (Bihar, India; citra 2 m) memberi
  IoU rata-rata 0,71 dan F1 0,82 untuk lahan yang terdeteksi. Dengan prompt klik dari
  petani, masalah "deteksi" hilang; tinggal deliniasi.
* Watershed berpenanda (bawaan, selalu tersedia, CPU ~1 detik): citra dihaluskan
  dengan mean-shift agar tekstur tajuk sawit menyatu, lalu watershed pada gradien warna
  dengan penanda latar depan di titik klik dan penanda latar belakang dari piksel yang
  warnanya jauh berbeda + tepi citra.

Keluaran selalu draf: petani wajib meninjau & mengoreksi garis (human-in-the-loop).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

from ..config import SAM_CHECKPOINT, SAM_MODEL_TYPE
from .geo import area_ha, global_px_to_latlng, meters_per_px

_sam_predictor = None
_sam_error: str | None = None


def sam_status() -> dict:
    try:
        import segment_anything  # noqa: F401
    except Exception:  # noqa: BLE001
        return {"available": False, "reason": "paket segment_anything belum terpasang"}
    if not SAM_CHECKPOINT.exists():
        return {"available": False, "reason": f"checkpoint tidak ditemukan: {SAM_CHECKPOINT.name}"}
    return {"available": True, "reason": f"SAM {SAM_MODEL_TYPE}"}


def _get_sam():
    global _sam_predictor, _sam_error
    if _sam_predictor is not None or _sam_error is not None:
        return _sam_predictor
    st = sam_status()
    if not st["available"]:
        _sam_error = st["reason"]
        return None
    try:
        from segment_anything import SamPredictor, sam_model_registry

        sam = sam_model_registry[SAM_MODEL_TYPE](checkpoint=str(SAM_CHECKPOINT))
        sam.eval()
        _sam_predictor = SamPredictor(sam)
    except Exception as e:  # noqa: BLE001
        _sam_error = str(e)
    return _sam_predictor


@dataclass
class DelineationResult:
    polygon: dict | None
    area_ha: float
    confidence: float
    engine: str
    ms: int
    warnings: list[str]


MAX_RADIUS_M = 400  # kebun petani jarang lebih dari 400 m dari titik klik


def _mask_watershed(rgb: np.ndarray, px: int, py: int, m_per_px: float) -> np.ndarray:
    h, w = rgb.shape[:2]
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    smooth = cv2.pyrMeanShiftFiltering(bgr, sp=9, sr=18)
    smooth = cv2.GaussianBlur(smooth, (5, 5), 0)
    lab = cv2.cvtColor(smooth, cv2.COLOR_BGR2LAB).astype(np.float32)

    seed_r = max(4, int(12 / m_per_px))  # ~12 m di sekitar titik klik
    yy, xx = np.ogrid[:h, :w]
    seed = (xx - px) ** 2 + (yy - py) ** 2 <= seed_r**2
    mean = lab[seed].mean(axis=0)
    std = lab[seed].std(axis=0).mean()
    dist = np.linalg.norm(lab - mean, axis=2)

    # gradien warna untuk "punggung" watershed
    grad = np.zeros((h, w), np.float32)
    for c in range(3):
        gx = cv2.Sobel(lab[:, :, c], cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(lab[:, :, c], cv2.CV_32F, 0, 1, ksize=3)
        grad += np.sqrt(gx**2 + gy**2)
    grad = cv2.normalize(grad, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    thr = max(18.0, 3.0 * float(std) + 10.0)
    markers = np.zeros((h, w), np.int32)
    markers[dist > thr * 1.6] = 1  # jelas berbeda -> latar belakang
    border = np.zeros((h, w), bool)
    border[:3, :] = border[-3:, :] = border[:, :3] = border[:, -3:] = True
    markers[border] = 1
    max_r = int(MAX_RADIUS_M / m_per_px)
    markers[(xx - px) ** 2 + (yy - py) ** 2 > max_r**2] = 1
    markers[seed] = 2
    cv2.watershed(cv2.cvtColor(grad, cv2.COLOR_GRAY2BGR), markers)
    mask = (markers == 2).astype(np.uint8)
    return mask


def _mask_sam(rgb: np.ndarray, px: int, py: int) -> np.ndarray | None:
    pred = _get_sam()
    if pred is None:
        return None
    pred.set_image(rgb)
    masks, scores, _ = pred.predict(point_coords=np.array([[px, py]]), point_labels=np.array([1]), multimask_output=True)
    # pilih mask skor tertinggi yang tidak menyentuh seluruh citra
    order = np.argsort(-scores)
    for i in order:
        m = masks[i].astype(np.uint8)
        if m.mean() < 0.6:
            return m
    return masks[order[0]].astype(np.uint8)


def _clean(mask: np.ndarray, px: int, py: int) -> np.ndarray:
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)
    n, lab = cv2.connectedComponents(mask)
    if n <= 1:
        return mask
    keep = lab[py, px]
    if keep == 0:
        sizes = [(lab == i).sum() for i in range(1, n)]
        keep = int(np.argmax(sizes)) + 1
    return (lab == keep).astype(np.uint8)


def delineate(rgb: np.ndarray, origin_x: float, origin_y: float, lat: float, lng: float, z: int, prefer_sam: bool = True) -> DelineationResult:
    from .geo import latlng_to_global_px

    t0 = time.perf_counter()
    gx, gy = latlng_to_global_px(lat, lng, z)
    px, py = int(round(gx - origin_x)), int(round(gy - origin_y))
    h, w = rgb.shape[:2]
    if not (0 <= px < w and 0 <= py < h):
        raise ValueError("Titik di luar citra")
    mpp = meters_per_px(lat, z)

    engine = "watershed"
    mask = None
    if prefer_sam:
        mask = _mask_sam(rgb, px, py)
        if mask is not None:
            engine = "sam"
    if mask is None:
        mask = _mask_watershed(rgb, px, py, mpp)
    mask = _clean(mask, px, py)

    warnings: list[str] = []
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return DelineationResult(None, 0.0, 0.0, engine, int((time.perf_counter() - t0) * 1000),
                                 ["AI tidak menemukan batas yang jelas. Silakan gambar manual."])
    cnt = max(contours, key=cv2.contourArea)
    peri = cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, 0.012 * peri, True).reshape(-1, 2)
    if len(approx) < 4:
        approx = cv2.boxPoints(cv2.minAreaRect(cnt)).astype(int)
    ring = []
    for x, y in approx:
        la, ln = global_px_to_latlng(origin_x + float(x), origin_y + float(y), z)
        ring.append([round(ln, 7), round(la, 7)])
    ring.append(ring[0])
    poly = {"type": "Polygon", "coordinates": [ring]}
    a = area_ha(poly)

    # keyakinan: kekompakan bentuk + kontras tepi + kewajaran luas
    area_px = cv2.contourArea(cnt)
    compact = 4 * np.pi * area_px / (peri**2 + 1e-9)
    touches_border = (mask[0, :].any() or mask[-1, :].any() or mask[:, 0].any() or mask[:, -1].any())
    conf = 0.45 + 0.35 * min(compact / 0.6, 1.0)
    if 0.3 <= a <= 25:
        conf += 0.15
    else:
        warnings.append(f"Luas {a:.2f} ha di luar rentang wajar kebun petani (0,3-25 ha). Periksa garis batas.")
    if touches_border:
        conf -= 0.25
        warnings.append("Batas menyentuh tepi citra; kebun mungkin lebih luas. Perbesar peta lalu klik lagi.")
    # batas yang hanya mengikuti lingkaran radius maksimum = AI tidak menemukan tepi kebun yang nyata
    pts = cnt.reshape(-1, 2).astype(float)
    r_cap = MAX_RADIUS_M / mpp
    on_cap = float(np.mean(np.hypot(pts[:, 0] - px, pts[:, 1] - py) >= 0.9 * r_cap))
    if on_cap > 0.15 or float(rgb.std()) < 6:
        conf -= 0.5
        warnings.append("Tepi kebun tidak terlihat jelas di citra. Gambar batas secara manual atau klik di bagian kebun yang lebih jelas.")
    if engine == "sam":
        conf += 0.05
    return DelineationResult(poly, round(a, 3), round(float(np.clip(conf, 0.05, 0.98)), 2), engine,
                             int((time.perf_counter() - t0) * 1000), warnings)
