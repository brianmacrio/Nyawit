"""Verifikasi independen: sampel inspeksi lapangan berbasis risiko dan keputusan keberatan.

Ukuran sampel mengikuti rumus inspeksi internal Standar Petani Swadaya RSPO 2024
(Milestone A): x = sqrt(n) x 2,5 x 1,5, dibulatkan ke atas, maksimal n.
Kebun dipilih berdasarkan risiko lebih dulu (berisiko, perlu cek, sengketa, bukti lahan lemah,
belum pernah dikunjungi), sisanya diundi acak berbobot luas supaya kebun besar lebih sering dicek.
"""
from __future__ import annotations

import base64
import io
import math
import random
from datetime import datetime

from PIL import Image, UnidentifiedImageError
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import MAX_PHOTO_BYTES, UPLOAD_DIR
from ..models import Appeal, Inspection, Plot
from . import geo

REASON_LABEL = {
    "berisiko": "Status satelit berisiko",
    "perlu_cek": "Status satelit perlu cek",
    "sengketa": "Ada sengketa lahan yang dinyatakan",
    "bukti_lemah": "Bukti lahan hanya pernyataan atau belum ada",
    "belum_pernah": "Belum pernah dikunjungi verifikator",
    "acak": "Diundi acak (berbobot luas)",
}
EVIDENCE_LABEL = {
    "sk_pelepasan": "SK pelepasan kawasan hutan",
    "sertifikat": "Sertifikat tanah",
    "surat_desa": "Surat keterangan desa",
    "foto_lapangan": "Foto lapangan / kesaksian",
    "lainnya": "Lainnya",
}
MAX_PHOTO_DISTANCE_M = 150.0


def sample_size(n: int) -> int:
    return 0 if n <= 0 else min(n, math.ceil(math.sqrt(n) * 2.5 * 1.5))


def _reason(p: Plot) -> tuple[int, str]:
    if p.risk_level == "tinggi":
        return 0, "berisiko"
    if p.risk_level == "perlu_cek":
        return 1, "perlu_cek"
    if p.dispute:
        return 2, "sengketa"
    if p.land_proof in (None, "pernyataan"):
        return 3, "bukti_lemah"
    if p.verified_at is None:
        return 4, "belum_pernah"
    return 5, "acak"


def generate_sample(db: Session, batch: str, seed: int | None = None) -> list[Inspection]:
    plots = db.scalars(select(Plot)).all()
    busy = set(db.scalars(select(Inspection.plot_id).where(Inspection.status == "menunggu")))
    free = [p for p in plots if p.id not in busy]
    k = sample_size(len(plots)) - len(busy)
    if k <= 0 or not free:
        return []
    ranked = sorted(free, key=lambda p: (_reason(p)[0], p.id))
    priority = [p for p in ranked if _reason(p)[0] <= 3]
    chosen = priority[:k]
    rest = [p for p in ranked if p not in chosen]
    rng = random.Random(seed if seed is not None else batch)
    while len(chosen) < k and rest:
        weights = [max(p.area_ha, 0.1) * (2.0 if p.verified_at is None else 1.0) for p in rest]
        pick = rng.choices(rest, weights=weights, k=1)[0]
        chosen.append(pick)
        rest.remove(pick)
    out = []
    for p in chosen:
        i = Inspection(plot_id=p.id, batch=batch, reason=_reason(p)[1])
        db.add(i)
        out.append(i)
    db.flush()
    return out


def inspection_dict(i: Inspection) -> dict:
    p = i.plot
    return {
        "id": i.id, "plot_id": p.id, "plot_code": p.code, "farmer": p.farmer.name, "village": p.farmer.village,
        "area_ha": round(p.area_ha, 2), "centroid": [p.centroid_lat, p.centroid_lng], "risk_level": p.risk_level,
        "batch": i.batch, "reason": i.reason, "reason_label": REASON_LABEL.get(i.reason, i.reason),
        "status": i.status, "result": i.result, "notes": i.notes, "inspector": i.inspector,
        "has_photo": bool(i.photo_path), "photo_lat": i.photo_lat, "photo_lng": i.photo_lng,
        "photo_distance_m": i.photo_distance_m,
        "created_at": i.created_at.isoformat(timespec="seconds"),
        "done_at": i.done_at.isoformat(timespec="seconds") if i.done_at else None,
    }


class PhotoError(ValueError):
    pass


def save_photo(inspection_id: int, data_url: str) -> str:
    """Validasi & simpan foto: hanya JPEG/PNG/WebP <= 4 MB. Gambar di-encode ulang (metadata EXIF dibuang
    demi privasi) dan diperkecil ke sisi terpanjang 1600 px (hemat ruang)."""
    if "," in data_url:
        header, b64 = data_url.split(",", 1)
        if not header.startswith("data:image/"):
            raise PhotoError("Berkas harus berupa gambar.")
    else:
        b64 = data_url
    try:
        raw = base64.b64decode(b64, validate=True)
    except Exception as e:  # noqa: BLE001
        raise PhotoError("Data foto rusak.") from e
    if len(raw) > MAX_PHOTO_BYTES:
        raise PhotoError("Foto terlalu besar (maksimal 4 MB).")
    try:
        img = Image.open(io.BytesIO(raw))
        if img.format not in ("JPEG", "PNG", "WEBP", "MPO"):
            raise PhotoError("Format foto harus JPEG, PNG, atau WebP.")
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise PhotoError("Berkas bukan gambar yang valid.") from e
    img = img.convert("RGB")
    img.thumbnail((1600, 1600))
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"inspeksi_{inspection_id}.jpg"
    img.save(UPLOAD_DIR / name, "JPEG", quality=80, optimize=True)  # tanpa EXIF
    return name


def distance_to_plot_m(p: Plot, lat: float, lng: float) -> float:
    lat0, lng0 = p.centroid_lat, p.centroid_lng
    poly = geo.to_local_m(p.geometry, lat0, lng0)
    k = math.cos(math.radians(lat0))
    pt = Point(geo.EARTH_R * math.radians(lng - lng0) * k, geo.EARTH_R * math.radians(lat - lat0))
    return round(float(poly.distance(pt)), 1)


def complete(db: Session, i: Inspection, result: str, notes: str | None, inspector: str,
             photo: str | None, lat: float | None, lng: float | None) -> list[str]:
    warnings: list[str] = []
    if photo:
        i.photo_path = save_photo(i.id, photo)
    if lat is not None and lng is not None:
        i.photo_lat, i.photo_lng = lat, lng
        i.photo_distance_m = distance_to_plot_m(i.plot, lat, lng)
        if i.photo_distance_m > MAX_PHOTO_DISTANCE_M:
            warnings.append(f"Lokasi pengambilan foto {i.photo_distance_m:.0f} m dari batas kebun. Pastikan inspeksi "
                            "dilakukan di kebun yang benar.")
    elif photo:
        warnings.append("Foto tanpa lokasi GPS; bukti lapangan lebih lemah.")
    i.result, i.notes, i.inspector = result, notes, inspector
    i.status, i.done_at = "selesai", datetime.now()
    p = i.plot
    p.verified_at, p.verified_result, p.verified_by = i.done_at, result, inspector
    db.flush()
    return warnings


def decide_appeal(db: Session, a: Appeal, accept: bool, note: str, new_risk: str | None, by: str) -> None:
    a.status = "diterima" if accept else "ditolak"
    a.decision_note, a.decided_by, a.decided_at = note, by, datetime.now()
    if accept and new_risk:
        p = a.plot
        last = p.analyses[0] if p.analyses else None
        p.status_override = {"original": p.risk_level, "risk_level": new_risk, "reason": note, "by": by,
                             "at": a.decided_at.isoformat(timespec="seconds"), "appeal_id": a.id,
                             "analysis_id": last.id if last else None}
        a.new_risk = new_risk
        p.risk_level = new_risk
        p.risk_headline = f"{'Aman' if new_risk == 'rendah' else 'Perlu cek'} (keputusan verifikator atas keberatan)"
    db.flush()
