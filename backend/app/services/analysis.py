"""Orkestrasi analisis satu kebun: ambil data satelit -> time series AI -> keputusan."""
from __future__ import annotations

import time

from ..config import EUDR_CUTOFF, SATELLITE_MODE
from . import evidence, geo, kawasan, timeseries
from .satellite import demo, peta_gfw


def protected_areas() -> list[dict]:
    """Poligon kawasan dari GeoJSON lokal (peta resmi unduhan pengguna atau ilustrasi demo) untuk peta."""
    return [{k: v for k, v in a.items() if k != "file"} for a in kawasan.local_areas()]



def kawasan_check(geom: dict, policy: str | None = None) -> dict:
    """Status kawasan hutan kebun: peta Kemenhut online/cache + GeoJSON lokal."""
    return kawasan.lookup(geom, policy).to_dict()


def protected_overlap(geom: dict, policy: str | None = None) -> tuple[float, str | None]:
    r = kawasan.lookup(geom, policy)
    return r.pct, r.name


def scenario_for(geom: dict, requested: str | None, policy: str | None = None, peta_policy: str = "auto") -> str:
    """Skenario deret NDVI simulasi (mode demo) untuk kebun baru.

    Bila lapisan peta nyata terbaca, skenario mengikuti peta itu (mis. kebun di atas piksel kehilangan
    tutupan 2024 di lahan bukan hutan -> "peremajaan_2024") agar grafik NDVI tidak bertentangan dengan peta.
    """
    if demo.is_scenario(requested):
        return requested
    pct, _ = protected_overlap(geom, policy)
    real, _err = peta_gfw.plot_layers(geom, peta_policy)
    if real:
        return demo.scenario_from_layers(real, pct, evidence.T_TREE, evidence.T_DIST_AFTER, evidence.T_DIST_BEFORE)
    return "kawasan_hutan" if pct > evidence.T_PROTECTED else "sawit_tua_stabil"


def run(geom: dict, plot_code: str, scenario: str | None, force_demo: bool = False, kawasan_policy: str | None = None,
        peta_policy: str = "auto") -> dict:
    """`peta_policy`: sumber lapisan peta nyata di mode demo ("auto", "bundel" untuk seed, "mati")."""
    t0 = time.perf_counter()
    lat, lng = geo.centroid(geom)
    kw = kawasan_check(geom, kawasan_policy)
    mode = "demo" if force_demo else SATELLITE_MODE
    sources: list[str] = []
    warnings: list[str] = []

    dates, values, layers = [], [], None
    forest_map = None
    layer_sources = None
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
    real_layers = False
    if mode != "live":
        sc = scenario if demo.is_scenario(scenario) else "sawit_tua_stabil"
        s = demo.simulate_series(sc, plot_code)
        dates, values = s.dates, s.ndvi
        sources.append(s.source + " - deret NDVI disimulasikan: " + demo.info(sc)["label"])
        real, err = peta_gfw.plot_layers(geom, peta_policy) if peta_policy != "mati" else (None, "dimatikan")
        if real:
            layers = {k: v for k, v in real.items() if not k.startswith("_")}
            sources.append(real["_source"])
            forest_map, layer_sources, real_layers = "jrc", peta_gfw.LAYER_SOURCES, True
            expected = demo.scenario_from_layers(real, kw["pct"], evidence.T_TREE, evidence.T_DIST_AFTER,
                                                 evidence.T_DIST_BEFORE)
            post = lambda name: (demo.parse(name)[1] or 0) >= 2021  # noqa: E731 - ada pembukaan sesudah 2020?
            if post(expected) != post(sc) and kw["pct"] <= evidence.T_PROTECTED:
                warnings.append(f"Deret NDVI simulasi ({demo.info(sc)['label'].lower()}) tidak sejalan dengan peta nyata "
                                f"({demo.info(expected)['label'].lower()}). Keputusan memakai lapisan peta nyata.")
        else:
            layers = demo.simulate_layers(sc, plot_code)
            sources.append("Lapisan bukti simulasi: " + demo.info(sc)["label"])
            if peta_policy != "mati" and err:
                warnings.append(f"Lapisan peta nyata (JRC/Hansen dari Global Forest Watch) belum terbaca ({err[:100]}); "
                                "memakai lapisan simulasi.")

    ts = timeseries.detect_changes(dates, values, cutoff=EUDR_CUTOFF) if dates else None
    decision = evidence.decide(layers or {}, ts, kw["pct"], kawasan=kw, strict=mode == "live", forest_map=forest_map,
                               layer_sources=layer_sources)
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
        "data_source": "live" if mode == "live" else ("peta_nyata" if real_layers else "simulasi"),
        "compute_ms": ms,
        "planting_year_detected": ts.planting_year if ts else None,
    }
