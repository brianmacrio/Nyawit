"""PasporKebun API.

Jalankan:  uvicorn app.main:app --reload --port 8000
Dokumentasi interaktif: http://localhost:8000/docs
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from .config import APP_VERSION, BASE_DIR, CORS_ORIGINS
from .db import SessionLocal, init_db
from .models import Plot
from .routers import ai, dashboard, meta, plots, supply


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with SessionLocal() as db:
        empty = (db.scalar(select(func.count(Plot.id))) or 0) == 0
    if empty:
        from .seed import seed

        seed(reset=False)
    yield


app = FastAPI(
    title="PasporKebun API",
    version=APP_VERSION,
    description="Paspor digital kebun sawit rakyat: peta batas berbantuan AI, cek deforestasi multi-bukti "
    "(EUDR), dan penjaga titik pengepul anti-pencucian TBS.",
    lifespan=lifespan,
)
app.add_middleware(GZipMiddleware, minimum_size=1024)  # hemat bandwidth (Green IT)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

for r in (meta.router, plots.router, ai.router, supply.router, dashboard.router):
    app.include_router(r)

# Jika frontend sudah di-build (npm run build), sajikan dari sini agar cukup 1 server.
DIST = (BASE_DIR.parent / "frontend" / "dist").resolve()
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        if path and f.is_file() and Path(f).resolve().is_relative_to(DIST):
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
