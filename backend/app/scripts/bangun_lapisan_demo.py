"""Membangun ulang tabel bawaan lapisan peta kebun contoh (seed_data/lapisan_peta_demo.json).

    cd backend
    .venv\\Scripts\\python -m app.scripts.bangun_lapisan_demo

Dijalankan setelah lokasi kebun contoh di seed.py diubah atau sumber peta diperbarui. Skrip
membuat data demo di folder sementara, lalu menghitung tiap kebun dengan fungsi yang sama dengan
aplikasi (peta_gfw.compute) dari tile Global Forest Watch (cache di data/ts_cache/peta_gfw, atau
diunduh). Tabel disimpan agar hasil demo sama walau tanpa internet.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path


def run() -> int:
    cache = Path(os.getenv("PK_DATA_DIR") or Path(__file__).resolve().parents[2] / "data") / "ts_cache"
    tmp = tempfile.mkdtemp(prefix="pk_lapisan_")
    os.environ["PK_DATA_DIR"] = tmp
    os.environ["PK_DB_URL"] = f"sqlite:///{Path(tmp, 'x.db').as_posix()}"
    from sqlalchemy import select

    from .. import seed
    from ..db import SessionLocal
    from ..models import Plot
    from ..services.satellite import peta_gfw

    peta_gfw.TS_CACHE_DIR = cache  # tile yang sudah ada dipakai dulu; sisanya diunduh
    seed.seed(reset=True)
    plots: dict[str, dict] = {}
    with SessionLocal() as db:
        for p in db.scalars(select(Plot).order_by(Plot.id)):
            try:
                out = peta_gfw.compute(p.geometry, lambda k, x, y: peta_gfw.get_tile(k, x, y, online=True))
            except peta_gfw.PetaError as e:
                print(f"GAGAL {p.code}: {e}")
                return 1
            if out["natural_forest_2020"] is None:
                print(f"GAGAL {p.code}: tile peta hutan kedua (SBTN) tidak terbaca")
                return 1
            plots[peta_gfw.geom_key(p.geometry)] = {**out, "code_demo": p.code}
    meta = {
        "computed_at": time.strftime("%d-%m-%Y"),
        "method": "Pusat piksel tile zoom 14 di dalam batas kebun (sama dengan services/satellite/peta_gfw.compute)",
        "sources": list(peta_gfw.TILE_URLS.values()),
        "note": ("Lapisan peta nyata untuk kebun contoh demo, disimpan agar hasil demo sama tanpa internet. "
                 "Kunci = sha256 cincin poligon (6 desimal)."),
    }
    peta_gfw.BUNDLE.write_text(json.dumps({"_meta": meta, "plots": plots}, ensure_ascii=False, indent=1) + "\n",
                               encoding="utf-8")
    print(f"{len(plots)} kebun ditulis ke {peta_gfw.BUNDLE}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
