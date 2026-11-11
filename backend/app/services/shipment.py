"""Paket data uji tuntas per pengiriman ekspor (untuk importir yang membuat Due Diligence Statement EUDR).

Isi paket mengikuti informasi yang diminta EUDR dari rantai pasok:
  * geolokasi semua kebun asal (GeoJSON, koordinat >= 6 desimal),
  * rentang waktu produksi (tanggal pembelian TBS pertama-terakhir per kebun),
  * volume per kebun dan pengepul,
  * bukti bebas deforestasi (cek satelit vs 31 Des 2020) dan legalitas (bukti lahan, STDB, kawasan hutan),
  * TANPA pencampuran: hanya kebun berstatus Siap EUDR; kebun lain dikeluarkan beserta alasannya.
Data pribadi petani (nama) tidak ikut: EUDR tidak mewajibkannya, cukup kode kebun.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..config import EUDR_CUTOFF
from ..models import Delivery, Plot, Shipment, Transaction
from . import readiness
from .plots import pending_inspections


def _plot_entry(p: Plot, txns: list[Transaction], r: dict) -> dict:
    dates = sorted(t.created_at for t in txns)
    collectors = sorted({t.collector.name for t in txns})
    return {
        "plot_id": p.id, "plot_code": p.code, "village": p.farmer.village, "area_ha": round(p.area_ha, 4),
        "centroid": [round(p.centroid_lat, 7), round(p.centroid_lng, 7)], "geometry": p.geometry,
        "volume_kg": round(sum(t.weight_kg for t in txns)), "n_purchases": len(txns),
        "production_start": dates[0].date().isoformat(), "production_end": dates[-1].date().isoformat(),
        "collectors": collectors, "risk_level": p.risk_level,
        "analysis_date": p.analyzed_at.date().isoformat() if p.analyzed_at else None,
        "land_proof": p.land_proof, "stdb_status": p.stdb_status or "belum",
        "kawasan_pct": p.kawasan_pct, "kawasan_source": p.kawasan_source,
        "verified": p.verified_result, "precision_level": r["precision"]["level"],
        "failed_checks": [f"{c['label']}: {c['detail']}" for c in r["checks"] if not c["ok"]]
        + (["Status kedaluwarsa (cek satelit > 12 bulan)"] if r["expired"] else []),
    }


def build(db: Session, buyer: str, destination: str, start: datetime, end: datetime, created_by: str) -> Shipment:
    txns = db.scalars(
        select(Transaction).where(Transaction.created_at >= start, Transaction.created_at <= end)
        .options(selectinload(Transaction.plot).selectinload(Plot.farmer), selectinload(Transaction.collector))
    ).all()
    by_plot: dict[int, list[Transaction]] = defaultdict(list)
    held_kg = 0.0
    for t in txns:
        if t.decision == "ditahan":
            held_kg += t.weight_kg
        else:
            by_plot[t.plot_id].append(t)
    pending = pending_inspections(db)
    included, excluded = [], []
    for pid, ts in by_plot.items():
        p = ts[0].plot
        r = readiness.evaluate(p, pid in pending)
        e = _plot_entry(p, ts, r)
        (included if r["ready"] else excluded).append(e)
    included.sort(key=lambda e: e["plot_code"])
    excluded.sort(key=lambda e: -e["volume_kg"])
    delivered = db.scalar(select(func.coalesce(func.sum(Delivery.weight_kg), 0.0))
                          .where(Delivery.created_at >= start, Delivery.created_at <= end)) or 0.0
    inc_kg = sum(e["volume_kg"] for e in included)
    exc_kg = sum(e["volume_kg"] for e in excluded)
    summary = {
        "included_kg": inc_kg, "excluded_kg": exc_kg, "held_kg": round(held_kg),
        "delivered_kg": round(delivered), "untraced_kg": max(0, round(delivered - inc_kg - exc_kg)),
        "n_included": len(included), "n_excluded": len(excluded),
        "eligible_share": round(inc_kg / delivered, 3) if delivered else None,
        "production_start": min((e["production_start"] for e in included), default=None),
        "production_end": max((e["production_end"] for e in included), default=None),
        "cutoff": EUDR_CUTOFF.isoformat(),
        "rule": "Hanya TBS dari kebun berstatus Siap EUDR. Tanpa pencampuran (mass balance tidak diterima EUDR).",
    }
    n = (db.scalar(select(func.count(Shipment.id))) or 0) + 1
    s = Shipment(code=f"KRM-{datetime.now():%Y%m%d}-{n:03d}", buyer=buyer, destination=destination,
                 period_start=start, period_end=end, created_by=created_by, summary=summary,
                 plots=included, excluded=excluded)
    db.add(s)
    db.flush()
    return s


def shipment_dict(s: Shipment, full: bool = False) -> dict:
    d = {"id": s.id, "code": s.code, "buyer": s.buyer, "destination": s.destination,
         "period_start": s.period_start.date().isoformat(), "period_end": s.period_end.date().isoformat(),
         "created_by": s.created_by, "created_at": s.created_at.isoformat(timespec="seconds"), "summary": s.summary}
    if full:
        strip = lambda e: {k: v for k, v in e.items() if k != "geometry"}  # noqa: E731
        d["plots"] = [strip(e) for e in s.plots]
        d["excluded"] = [strip(e) for e in s.excluded]
    return d


def _geojson(s: Shipment) -> dict:
    feats = []
    for e in s.plots:
        feats.append({"type": "Feature", "geometry": e["geometry"], "properties": {
            "PlotCode": e["plot_code"], "ProducerCountry": "ID", "ProductionPlace": e["village"],
            "Area": e["area_ha"], "Commodity": "Oil palm fresh fruit bunches (HS 1511 chain)",
            "ProductionStart": e["production_start"], "ProductionEnd": e["production_end"],
            "VolumeKg": e["volume_kg"], "DeforestationCutOff": s.summary["cutoff"], "DeforestationFree": True,
            "SatelliteCheckDate": e["analysis_date"], "LandProof": e["land_proof"], "STDB": e["stdb_status"],
            "ForestAreaOverlapPct": e["kawasan_pct"], "ForestAreaMapSource": e["kawasan_source"],
            "FieldVerification": e["verified"] or "tidak_terpilih_sampel",
        }})
    return {"type": "FeatureCollection", "features": feats}


def _csv(rows: list[dict], cols: list[str]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow(["; ".join(r[c]) if isinstance(r[c], list) else r[c] for c in cols])
    return buf.getvalue()


def package_zip(s: Shipment) -> bytes:
    gj = json.dumps(_geojson(s), ensure_ascii=False, indent=1)
    cols = ["plot_code", "village", "area_ha", "centroid", "volume_kg", "n_purchases", "production_start",
            "production_end", "collectors", "land_proof", "stdb_status", "kawasan_pct", "kawasan_source", "verified",
            "analysis_date", "precision_level"]
    inc = _csv([{**e, "centroid": f"{e['centroid'][0]},{e['centroid'][1]}"} for e in s.plots], cols)
    exc = _csv(s.excluded, ["plot_code", "village", "volume_kg", "production_start", "production_end", "failed_checks"])
    digest = hashlib.sha256((gj + inc).encode("utf-8")).hexdigest()
    sm = s.summary
    readme = f"""PAKET DATA UJI TUNTAS - {s.code}
Dibuat oleh PasporKebun pada {s.created_at:%Y-%m-%d %H:%M}, oleh {s.created_by}.
Pembeli/importir : {s.buyer} ({s.destination})
Periode pembelian: {s.period_start:%Y-%m-%d} s.d. {s.period_end:%Y-%m-%d}

ISI
- geolokasi_kebun.geojson : poligon {sm['n_included']} kebun asal (WGS84, 7 desimal) + rentang produksi & volume
- ringkasan_kebun.csv     : data per kebun (tanpa nama petani; EUDR tidak mewajibkan data pribadi)
- kebun_dikeluarkan.csv   : {sm['n_excluded']} kebun yang TBS-nya tidak boleh masuk pengiriman ini, beserta alasannya

ANGKA
- TBS dari kebun Siap EUDR      : {sm['included_kg']:,} kg
- TBS dari kebun belum siap     : {sm['excluded_kg']:,} kg (tidak boleh dicampur)
- TBS ditahan di pengepul       : {sm['held_kg']:,} kg
- Total setoran ke pabrik       : {sm['delivered_kg']:,} kg

METODE (ringkas)
- Bebas deforestasi: riwayat NDVI Sentinel-2 sejak 2018 (COLD-lite) + peta global (convergence of evidence, Whisp FAO);
  batas waktu {sm['cutoff']}.
- Legalitas: bukti penguasaan lahan (sertifikat / surat desa / pernyataan + 2 saksi), status STDB, irisan dengan
  peta Kawasan Hutan Kementerian Kehutanan.
- Verifikasi: sampel inspeksi lapangan berbasis risiko (rumus RSPO ISH: akar(n) x 2,5 x 1,5).

BATASAN
- Paket ini adalah bukti uji tuntas, BUKAN sertifikat ISPO/RSPO.
- Uji tuntas EUDR tetap tanggung jawab importir (operator); data ini mendukung penilaian risikonya.
- Peta kawasan hutan berskala kecil; batas bisa bergeser puluhan hingga ratusan meter.

Sidik SHA-256 (geojson + csv): {digest}
"""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", readme)
        z.writestr("geolokasi_kebun.geojson", gj)
        z.writestr("ringkasan_kebun.csv", inc)
        z.writestr("kebun_dikeluarkan.csv", exc)
        z.writestr("ringkasan.json", json.dumps({**shipment_dict(s), "sha256": digest}, ensure_ascii=False, indent=1))
    return out.getvalue()
