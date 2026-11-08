"""Orkestrasi analisis satu kebun: ambil data satelit -> time series AI -> keputusan."""
from __future__ import annotations

import json
import time
from functools import lru_cache
from pathlib import Path

from ..config import DATA_DIR, EUDR_CUTOFF, SATELLITE_MODE
from . import evidence, geo, timeseries
from .satellite import demo


@lru_cache(maxsize=1)
def protected_areas() -> list[dict]:
    """Memuat semua GeoJSON kawasan hutan/konservasi di data/kawasan/*.geojson."""
    out = []
    folder = DATA_DIR / "kawasan"
    for p in sorted(Path(folder).glob("*.geojson")) if folder.exists() else []:
        fc = json.loads(p.read_text(encoding="utf-8"))
        for f in fc.get("features", []):
            if f.get("geometry", {}).get("type") == "Polygon":
                out.append({"name": f.get("properties", {}).get("name", p.stem),
                            "status": f.get("properties", {}).get("status", ""),
                            "is_demo": bool(f.get("properties", {}).get("is_demo", False)),
                            "geometry": f["geometry"]})
    return out


def protected_overlap(geom: dict) -> tuple[float, str | None]:
    best, name = 0.0, None
    for pa in protected_areas():
        frac = geo.overlap_fraction(geom, pa["geometry"])
        if frac > best:
            best, name = frac, pa["name"]
    return round(best * 100, 1), name


def scenario_for(geom: dict, requested: str | None) -> str:
    if requested in demo.SCENARIOS:
        return requested
    pct, _ = protected_overlap(geom)
    return "kawasan_hutan" if pct > 5 else "sawit_tua_stabil"


def run(geom: dict, plot_code: str, scenario: str | None, force_demo: bool = False) -> dict:
    t0 = time.perf_counter()
    lat, lng = geo.centroid(geom)
    prot_pct, prot_name = protected_overlap(geom)
    mode = "demo" if force_demo else SATELLITE_MODE
    sources: list[str] = []
    warnings: list[str] = []

    dates, values, layers = [], [], None
    if mode == "live":
        try:
            from .satellite import live

            if not live.status()["available"]:
                raise RuntimeError("paket live belum terpasang: " + ", ".join(live.status()["missing"]))
            dates, values, src = live.ndvi_series(geom)
            sources.append(src)
            layers = live.hansen_layers(geom, lat, lng)
            sources.append(layers.pop("_source", "Hansen GFC"))
        except Exception as e:  # noqa: BLE001
            warnings.append(f"Mode live gagal ({e}); memakai data simulasi.")
            mode = "demo"
    if mode != "live":
        sc = scenario or "sawit_tua_stabil"
        s = demo.simulate_series(sc, plot_code)
        dates, values = s.dates, s.ndvi
        layers = demo.simulate_layers(sc, plot_code)
        sources.append(s.source)
        sources.append("Lapisan bukti simulasi: " + demo.SCENARIOS[sc]["label"])

    ts = timeseries.detect_changes(dates, values, cutoff=EUDR_CUTOFF) if dates else None
    decision = evidence.decide(layers or {}, ts, prot_pct)
    ms = int((time.perf_counter() - t0) * 1000)
    return {
        "risk_level": decision.risk_level,
        "headline": decision.headline,
        "confidence": decision.confidence,
        "evidence": {
            **decision.to_dict(),
            "layers": layers,
            "protected": {"pct": prot_pct, "name": prot_name},
            "sources": sources,
            "warnings": warnings,
            "cutoff": EUDR_CUTOFF.isoformat(),
        },
        "timeseries": ts.to_dict() if ts else {},
        "data_source": "live" if mode == "live" else "simulasi",
        "compute_ms": ms,
        "planting_year_detected": ts.planting_year if ts else None,
    }
