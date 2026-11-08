"""Konfigurasi aplikasi. Semua nilai bisa diubah lewat environment variable."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # folder backend/
DATA_DIR = Path(os.getenv("PK_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_URL = os.getenv("PK_DB_URL", f"sqlite:///{(DATA_DIR / 'pasporkebun.db').as_posix()}")

# demo  = data satelit simulasi (selalu jalan, untuk demo offline)
# live  = ambil Sentinel-2 + Hansen GFC sungguhan (butuh internet & paket di requirements-live.txt)
SATELLITE_MODE = os.getenv("PK_SATELLITE_MODE", "demo").lower()

# Batas waktu EUDR: kebun tidak boleh berasal dari deforestasi setelah tanggal ini.
EUDR_CUTOFF = date(2020, 12, 31)
EUDR_APPLICATION = date(2026, 12, 30)

# Rentang analisis time series (>= 5 tahun ke belakang dari hari ini).
TS_START = date(2018, 1, 1)

# Citra satelit untuk AI penggambar batas kebun (XYZ tile).
TILE_URL = os.getenv(
    "PK_TILE_URL",
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
)
TILE_ZOOM = int(os.getenv("PK_TILE_ZOOM", "18"))
TILE_CACHE_DIR = DATA_DIR / "tile_cache"
TS_CACHE_DIR = DATA_DIR / "ts_cache"

# Segment Anything (opsional). Jika file checkpoint ada & paket terpasang, AI memakai SAM.
SAM_MODEL_TYPE = os.getenv("PK_SAM_MODEL", "vit_b")
SAM_CHECKPOINT = Path(os.getenv("PK_SAM_CHECKPOINT", BASE_DIR / "models" / "sam_vit_b_01ec64.pth"))

CORS_ORIGINS = os.getenv("PK_CORS", "http://localhost:5173,http://127.0.0.1:5173").split(",")

APP_VERSION = "1.0.0"
