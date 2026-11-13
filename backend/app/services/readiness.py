"""Aturan status "Siap EUDR" dan tingkat ketelitian lokasi.

Paspor Kebun BUKAN sertifikat ISPO/RSPO (itu hanya boleh diterbitkan lembaga sertifikasi
terakreditasi KAN/ASI). Paspor adalah bukti uji tuntas: data yang diminta EUDR, dicatat
koperasi sebagai sistem kendali internal, dan diperiksa verifikator independen lewat sampel.

Sebuah kebun Siap EUDR bila kelima syarat terpenuhi:
  1. Lokasi   : batas dipetakan dan disaksikan (kebun <= 4 ha cukup titik GPS menurut EUDR,
                tetapi poligon tetap dipakai untuk analisis satelit dan model kapasitas).
  2. Lahan    : ada bukti penguasaan (sertifikat / surat desa / pernyataan + 2 saksi),
                tidak ada sengketa yang dinyatakan, STDB sudah ada atau sedang diurus.
  3. Kawasan  : di luar kawasan hutan menurut peta resmi (<= 5% bersinggungan).
  4. Hutan    : satelit tidak menemukan pembukaan hutan setelah 31 Des 2020.
  5. Verifikasi: tidak sedang menunggu inspeksi lapangan dan tidak gagal inspeksi terakhir.
Status berlaku 12 bulan sejak cek satelit terakhir; satelit bisa menurunkan status kapan saja.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from ..config import READINESS_VALID_DAYS, SATELLITE_MODE
from ..models import Plot

LAND_PROOF_LABEL = {
    "sertifikat": "Sertifikat tanah (SHM/BPN)",
    "surat_desa": "Surat keterangan desa (SKT/SKGR)",
    "pernyataan": "Pernyataan penguasaan fisik + 2 saksi",
}
STDB_LABEL = {"ada": "STDB sudah terbit", "proses": "STDB sedang diurus", "belum": "STDB belum diurus"}
EUDR_POINT_MAX_HA = 4.0


def witness_list(p: Plot) -> list[dict]:
    w = list(p.witnesses or [])
    if not w and p.witness:
        w = [{"name": p.witness, "relation": "saksi", "at": None}]
    return w


def precision(p: Plot) -> dict:
    if p.land_proof == "sertifikat" and p.verified_result == "sesuai" and p.boundary_confirmed:
        lvl, label = 4, "Dicocokkan dengan sertifikat dan dicek di lapangan"
    elif p.boundary_confirmed:
        lvl, label = 3, "Batas disaksikan tetangga atau ketua kelompok tani"
    elif p.geometry:
        lvl, label = 2, "Draf batas (AI atau manual), belum disaksikan"
    else:
        lvl, label = 1, "Titik GPS saja"
    return {"level": lvl, "of": 4, "label": label, "gps": p.gps_lat is not None,
            "gps_accuracy_m": round(p.gps_accuracy_m, 1) if p.gps_accuracy_m else None}


def evaluate(p: Plot, pending_inspection: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    checks: list[dict] = []

    def add(key: str, label: str, ok: bool, detail: str) -> None:
        checks.append({"key": key, "label": label, "ok": bool(ok), "detail": detail})

    # 1. Lokasi
    area = p.area_ha or 0
    geo_note = ("EUDR: kebun di bawah 4 ha cukup satu titik koordinat" if area <= EUDR_POINT_MAX_HA
                else "EUDR: kebun di atas 4 ha wajib poligon batas")
    if p.boundary_confirmed:
        n = len(witness_list(p))
        add("lokasi", "Lokasi dan batas", True, f"Disaksikan {n} orang. {geo_note}; poligon tersedia.")
    else:
        add("lokasi", "Lokasi dan batas", False, "Batas belum disaksikan tetangga atau ketua kelompok tani.")

    # 2. Lahan
    wits = witness_list(p)
    if not p.farmer.consent_given:
        add("lahan", "Legalitas lahan", False, "Petani belum menyetujui pemakaian data kebun.")
    elif not p.land_proof:
        add("lahan", "Legalitas lahan", False, "Belum ada bukti penguasaan lahan (sertifikat, surat desa, atau pernyataan + 2 saksi).")
    elif p.land_proof == "pernyataan" and len(wits) < 2:
        add("lahan", "Legalitas lahan", False, f"Pernyataan penguasaan fisik butuh 2 saksi; baru {len(wits)}.")
    elif p.dispute:
        add("lahan", "Legalitas lahan", False, f"Ada sengketa yang dinyatakan{': ' + p.dispute_note if p.dispute_note else ''}.")
    elif p.stdb_status not in ("ada", "proses"):
        add("lahan", "Legalitas lahan", False, f"{LAND_PROOF_LABEL[p.land_proof]}, tetapi STDB belum diurus.")
    else:
        add("lahan", "Legalitas lahan", True, f"{LAND_PROOF_LABEL[p.land_proof]}; {STDB_LABEL[p.stdb_status]}; tidak ada sengketa.")

    # 3. Kawasan hutan
    pct = p.kawasan_pct
    demo_ok = SATELLITE_MODE != "live" and p.kawasan_source == "ilustrasi"
    if pct is None:
        add("kawasan", "Di luar kawasan hutan", False, "Belum dicek.")
    elif pct > 5:
        add("kawasan", "Di luar kawasan hutan", False, f"{pct:.0f}% kebun masuk kawasan hutan.")
    elif not (p.kawasan_checked or demo_ok):
        add("kawasan", "Di luar kawasan hutan", False, "Peta kawasan Kemenhut belum terjangkau saat dicek.")
    else:
        src = {"kemenhut": "peta Kemenhut", "klhk_gfw": "peta Kawasan Hutan KLHK 2017 (Global Forest Watch)",
               "lokal": "salinan lokal peta kawasan resmi", "ilustrasi": "peta ilustrasi demo"}.get(
            p.kawasan_source or "", "peta kawasan")
        add("kawasan", "Di luar kawasan hutan", True, f"Di luar kawasan hutan menurut {src}.")

    # 4. Bebas deforestasi
    if p.risk_level == "rendah":
        d = "Satelit tidak menemukan pembukaan hutan setelah 31 Des 2020."
        if p.status_override:
            d = f"Diputuskan verifikator setelah keberatan: {p.status_override.get('reason', '')}"
        add("hutan", "Bebas deforestasi", True, d)
    elif p.analysis_rule == "aturan-0-legalitas":
        add("hutan", "Bebas deforestasi", False, "Tidak dinilai terpisah karena kebun masuk kawasan hutan.")
    else:
        add("hutan", "Bebas deforestasi", False, p.risk_headline or "Belum dicek satelit.")

    # 5. Verifikasi lapangan
    if pending_inspection:
        add("verifikasi", "Verifikasi lapangan", False, "Terpilih sampel inspeksi; menunggu kunjungan verifikator.")
    elif p.verified_result == "tidak_sesuai":
        add("verifikasi", "Verifikasi lapangan", False, "Inspeksi lapangan terakhir menemukan ketidaksesuaian.")
    elif p.verified_result == "sesuai":
        when = p.verified_at.strftime("%d-%m-%Y") if p.verified_at else ""
        add("verifikasi", "Verifikasi lapangan", True, f"Lolos inspeksi lapangan {when} ({p.verified_by}).")
    else:
        add("verifikasi", "Verifikasi lapangan", True,
            "Belum terpilih sampel inspeksi; diterima berdasarkan catatan kendali internal koperasi.")

    valid_until = p.analyzed_at + timedelta(days=READINESS_VALID_DAYS) if p.analyzed_at else None
    expired = valid_until is not None and now > valid_until
    all_ok = all(c["ok"] for c in checks)
    return {
        "ready": all_ok and not expired,
        "missing": sum(not c["ok"] for c in checks) + (1 if expired else 0),
        "checks": checks,
        "valid_until": valid_until.isoformat(timespec="seconds") if valid_until else None,
        "expired": expired,
        "precision": precision(p),
    }
