"""Orkestrasi analisis satu kebun: ambil data satelit -> time series AI -> keputusan."""
from __future__ import annotations

import time

from ..config import EUDR_CUTOFF, SATELLITE_MODE
from . import evidence, geo, kawasan, timeseries
from .satellite import demo


def protected_areas() -> list[dict]:
    """Poligon kawasan dari GeoJSON lokal (peta resmi unduhan pengguna atau ilustrasi demo) untuk peta."""
    return [{k: v for k, v in a.items() if k != "file"} for a in kawasan.local_areas()]



def kawasan_check(geom: dict, policy: str | None = None) -> dict:
    """Status kawasan hutan kebun: peta Kemenhut online/cache + GeoJSON lokal."""
    return kawasan.lookup(geom, policy).to_dict()


def protected_overlap(geom: dict, policy: str | None = None) -> tuple[float, str | None]:
    r = kawasan.lookup(geom, policy)
    return r.pct, r.name


def scenario_for(geom: dict, requested: str | None, policy: str | None = None) -> str:
    if requested in demo.SCENARIOS:
        return requested
    pct, _ = protected_overlap(geom, policy)
    return "kawasan_hutan" if pct > evidence.T_PROTECTED else "sawit_tua_stabil"


def run(geom: dict, plot_code: str, scenario: str | None, force_demo: bool = False, kawasan_policy: str | None = None) -> dict:
    t0 = time.perf_counter()
    lat, lng = geo.centroid(geom)
    kw = kawasan_check(geom, kawasan_policy)
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
    decision = evidence.decide(layers or {}, ts, kw["pct"], kawasan=kw, strict=mode == "live")
    warnings += kw["warnings"]
    sources.append(kw["source_label"])
    ms = int((time.perf_counter() - t0) * 1000)
    return {
        "risk_level": decision.risk_level,
        "headline": decision.headline,
        "confidence": decision.confidence,
        "evidence": {
            **decision.to_dict(),
            "layers": layers,
            "protected": kw,
            "sources": sources,
            "warnings": warnings,
            "cutoff": EUDR_CUTOFF.isoformat(),
        },
        "timeseries": ts.to_dict() if ts else {},
        "data_source": "live" if mode == "live" else "simulasi",
        "compute_ms": ms,
        "planting_year_detected": ts.planting_year if ts else None,
    }
