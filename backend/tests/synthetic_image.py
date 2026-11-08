"""Citra sintetis mirip foto satelit kebun (untuk menguji AI penggambar batas)."""
import cv2
import numpy as np


def make_scene(seed: int = 0):
    rng = np.random.default_rng(seed)
    h = w = 768
    img = np.zeros((h, w, 3), np.uint8)
    img[:] = (52, 78, 40)  # latar hutan gelap (RGB)
    noise = rng.normal(0, 14, (h, w, 3))
    fields = [
        ((60, 80, 330, 360), "palm_old"),
        ((350, 70, 700, 300), "palm_young"),
        ((340, 330, 720, 700), "palm_old2"),
        ((50, 400, 310, 720), "bare"),
    ]
    masks = {}
    for (x0, y0, x1, y1), kind in fields:
        poly = np.array([[x0 + rng.integers(-15, 15), y0], [x1, y0 + rng.integers(-15, 15)], [x1 + rng.integers(-15, 5), y1], [x0, y1 + rng.integers(-10, 10)]], np.int32)
        m = np.zeros((h, w), np.uint8)
        cv2.fillPoly(m, [poly], 1)
        masks[kind] = m
        if kind.startswith("palm_old"):
            base = (70, 105, 45)
        elif kind == "palm_young":
            base = (120, 140, 70)
        else:
            base = (150, 120, 85)
        img[m == 1] = base
        if kind.startswith("palm"):
            # tajuk sawit: titik-titik berpola segitiga ~9 m
            step = 16 if kind != "palm_young" else 14
            r = 6 if kind != "palm_young" else 3
            for yy in range(y0, y1, step):
                off = (yy // step) % 2 * step // 2
                for xx in range(x0 + off, x1, step):
                    if 0 <= yy < h and 0 <= xx < w and m[yy, xx]:
                        cv2.circle(img, (xx, yy), r, (95, 135, 60), -1)
    # jalan tanah di antara kebun
    cv2.line(img, (0, 365), (w, 335), (170, 150, 120), 6)
    cv2.line(img, (335, 0), (325, h), (170, 150, 120), 6)
    img = np.clip(img.astype(float) + noise, 0, 255).astype(np.uint8)
    return img, masks
