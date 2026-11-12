"""Uji koneksi data satelit NYATA di laptop Anda.

    pip install -r requirements-live.txt
    python -m app.scripts.check_live

Mengambil time series Sentinel-2 dan lapisan Hansen untuk satu kebun contoh, lalu
menjalankan analisis. Jika berhasil, jalankan server dengan PK_SATELLITE_MODE=live.
"""
from __future__ import annotations

import time

from ..services.satellite import live
from ..services.timeseries import detect_changes

# kebun contoh ~2 ha di area demo (APL di sisi tenggara TN Tesso Nilo, Riau)
GEOM = {"type": "Polygon", "coordinates": [[[102.0610, -0.3630], [102.0625, -0.3630], [102.0625, -0.3642],
                                             [102.0610, -0.3642], [102.0610, -0.3630]]]}

if __name__ == "__main__":
    st = live.status()
    if not st["available"]:
        raise SystemExit(f"Paket belum lengkap: {st['missing']}. Jalankan: pip install -r requirements-live.txt")
    t0 = time.time()
    layers = live.hansen_layers(GEOM, -0.3636, 102.0618)
    print("Hansen:", layers, f"({time.time() - t0:.1f} dtk)")
    t0 = time.time()
    dates, vals, src = live.ndvi_series(GEOM)
    print(src, f"({time.time() - t0:.1f} dtk)")
    if dates:
        r = detect_changes(dates, vals)
        print("Perubahan:", [(b.date, b.magnitude) for b in r.breaks], "| tahun tanam:", r.planting_year)
