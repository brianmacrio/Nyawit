"""Konfigurasi aplikasi. Semua nilai bisa diubah lewat environment variable."""
from __future__ import annotations

import os
import secrets
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # folder backend/

try:  # .env lokal (tidak di-commit; lihat .env.example)
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
    load_dotenv(BASE_DIR.parent / ".env")
except ImportError:  # pragma: no cover
    pass

def _env(name: str, default):
    """Nilai environment; string kosong (mis. dari .env.example yang disalin) dianggap tidak diisi."""
    v = os.getenv(name)
    return default if v is None or not v.strip() else v.strip()


DATA_DIR = Path(_env("PK_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_URL = _env("PK_DB_URL", f"sqlite:///{(DATA_DIR / 'pasporkebun.db').as_posix()}")

# demo  = data satelit simulasi (selalu jalan, untuk demo offline)
# live  = ambil Sentinel-2 + Hansen GFC sungguhan (butuh internet & paket di requirements-live.txt)
SATELLITE_MODE = _env("PK_SATELLITE_MODE", "demo").lower()

# Batas waktu EUDR: kebun tidak boleh berasal dari deforestasi setelah tanggal ini.
EUDR_CUTOFF = date(2020, 12, 31)
EUDR_APPLICATION = date(2026, 12, 30)

# Rentang analisis time series (>= 5 tahun ke belakang dari hari ini).
TS_START = date(2018, 1, 1)

# Citra satelit untuk AI penggambar batas kebun (XYZ tile).
TILE_URL = _env(
    "PK_TILE_URL",
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
)
TILE_ZOOM = int(_env("PK_TILE_ZOOM", "18"))
TILE_CACHE_DIR = DATA_DIR / "tile_cache"
TS_CACHE_DIR = DATA_DIR / "ts_cache"

# Segment Anything (opsional). Jika file checkpoint ada & paket terpasang, AI memakai SAM.
SAM_MODEL_TYPE = _env("PK_SAM_MODEL", "vit_b")
SAM_CHECKPOINT = Path(_env("PK_SAM_CHECKPOINT", BASE_DIR / "models" / "sam_vit_b_01ec64.pth"))

# Status kawasan hutan otomatis dari peta resmi Kementerian Kehutanan (ArcGIS REST, SIGAP).
#   auto   = peta online Kemenhut (hasil disimpan di cache) + GeoJSON lokal; bila offline pakai cache/lokal
#   online = hanya peta Kemenhut + cache
#   lokal  = hanya GeoJSON di data/kawasan/ (tanpa internet)
KAWASAN_SOURCE = _env("PK_KAWASAN_SOURCE", "auto").lower()
KAWASAN_URL = _env(
    "PK_KAWASAN_URL",
    # Sejak KLHK dipecah, domain geoportal.menlhk.go.id tidak aktif lagi. Layanan ini dipakai
    # oleh "Peta Interaktif" di sigap.kehutanan.go.id.
    "https://geoportal.planologi.kehutanan.go.id/server/rest/services/Peta_Interaktif_2026/KWSHUTAN_AR_250K/MapServer",
).rstrip("/")
# id layer yang dipakai (mis. "0" atau "0,3"); kosong = dipilih otomatis dari nama layer
KAWASAN_LAYERS = [int(x) for x in _env("PK_KAWASAN_LAYERS", "").split(",") if x.strip().isdigit()]
KAWASAN_TIMEOUT = float(_env("PK_KAWASAN_TIMEOUT", "10"))
KAWASAN_CACHE_DIR = DATA_DIR / "kawasan_cache"
# Cadangan otomatis bila peta Kemenhut tidak terjangkau: Peta Kawasan Hutan KLHK 2017 yang
# disediakan Global Forest Watch sebagai tile vektor publik (tanpa kunci API).
KAWASAN_GFW = _env("PK_KAWASAN_GFW", "1") not in ("0", "false", "no")
KAWASAN_GFW_URL = _env(
    "PK_KAWASAN_GFW_URL",
    "https://tiles.globalforestwatch.org/idn_forest_area/v201709/dynamic/{z}/{x}/{y}.pbf",
)

CORS_ORIGINS = [o.strip() for o in _env("PK_CORS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]


def _secret_key() -> str:
    """Kunci penandatangan sesi. Dari PK_SECRET_KEY; bila kosong dibuat acak dan disimpan di data/ (tidak di-commit)."""
    env = os.getenv("PK_SECRET_KEY", "").strip()
    if env:
        return env
    f = DATA_DIR / "secret.key"
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    key = secrets.token_urlsafe(48)
    f.write_text(key, encoding="utf-8")
    return key


SECRET_KEY = _secret_key()
SESSION_HOURS = int(_env("PK_SESSION_HOURS", "12"))
# "auto" = cookie Secure bila diakses lewat HTTPS (hasil deploy); "1"/"0" untuk memaksa
COOKIE_SECURE = _env("PK_COOKIE_SECURE", "auto").lower()
# Akun demo untuk penilaian juri (lihat README). Matikan di produksi: PK_DEMO_ACCOUNTS=0
DEMO_ACCOUNTS = _env("PK_DEMO_ACCOUNTS", "1") == "1"
DEMO_PASSWORD = _env("PK_DEMO_PASSWORD", "sawit2026")
UPLOAD_DIR = DATA_DIR / "uploads"
MAX_PHOTO_BYTES = 4 * 1024 * 1024

# Paspor Siap EUDR berlaku 12 bulan sejak cek satelit terakhir
READINESS_VALID_DAYS = 365

APP_VERSION = "1.1.0"
