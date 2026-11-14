"""Penjaga titik pengepul: mencegah TBS ilegal "menumpang" paspor kebun petani jujur.

Dua lapis:
1. Pemeriksaan per transaksi (aturan yang bisa dijelaskan): kapasitas kebun 30 hari,
   rotasi panen, penjualan ke banyak pengepul, status risiko kebun, umur tanaman.
2. Deteksi anomali per pengepul (Isolation Forest, Liu et al. 2008) atas pola 90 hari:
   rasio kg/ha, porsi transaksi bermasalah, porsi setoran tak tertelusur, dll.
   Isolation Forest dipilih karena tidak butuh label kecurangan (yang memang belum ada),
   ringan (CPU, < 1 detik), dan hasilnya kami jelaskan dengan z-score per fitur.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

import numpy as np

from .fmt import dec, ton
from .yield_model import monthly_capacity_kg


@dataclass
class Flag:
    code: str
    severity: str  # tinggi | sedang | info
    title: str
    detail: str


@dataclass
class PlotInfo:
    code: str
    area_ha: float
    planting_year: int | None
    risk_level: str | None
    boundary_confirmed: bool = True


@dataclass
class TxnInfo:
    weight_kg: float
    collector_id: int
    created_at: datetime
    decision: str


@dataclass
class CheckResult:
    decision: str  # diterima | catatan | ditahan
    flags: list[Flag] = field(default_factory=list)
    used_kg_30d: float = 0.0
    upper_kg_30d: float = 0.0
    typical_kg_30d: float = 0.0
    capacity_used_pct: float = 0.0
    age: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def check_transaction(plot: PlotInfo, history: list[TxnInfo], weight_kg: float, collector_id: int, when: datetime) -> CheckResult:
    flags: list[Flag] = []
    cap = monthly_capacity_kg(plot.area_ha, plot.planting_year, when.month, when.date())
    window = [h for h in history if when - timedelta(days=30) <= h.created_at <= when and h.decision != "ditahan"]
    used = sum(h.weight_kg for h in window) + weight_kg
    upper = cap["upper_kg_30d"]
    pct = 100 * used / upper if upper > 0 else 999.0

    if plot.risk_level == "tinggi":
        flags.append(Flag("KEBUN_BERISIKO", "tinggi", "Kebun berstatus berisiko tinggi",
                          "Hasil analisis satelit menunjukkan risiko deforestasi/legalitas. TBS tidak boleh masuk rantai pasok ekspor."))
    elif plot.risk_level == "perlu_cek":
        flags.append(Flag("PERLU_CEK", "sedang", "Kebun masih perlu verifikasi",
                          "Bukti satelit belum cukup. Boleh diterima untuk pasar domestik, belum untuk ekspor UE."))
    elif plot.risk_level is None:
        flags.append(Flag("BELUM_DIANALISIS", "sedang", "Kebun belum dianalisis", "Jalankan cek satelit di menu Peta Kebun."))

    if cap["age"] is not None and cap["age"] < 3:
        flags.append(Flag("BELUM_MASA_PANEN", "tinggi", f"Tanaman baru berumur {cap['age']} tahun",
                          "Sawit umumnya mulai berbuah umur 3 tahun; penjualan dari kebun ini tidak wajar."))
    elif used > upper:
        flags.append(Flag("MELEBIHI_KAPASITAS", "tinggi",
                          f"Melebihi kapasitas kebun ({ton(used)} dari maks {ton(upper)} per 30 hari)",
                          f"Kebun {dec(plot.area_ha)} ha umur {cap['age'] if cap['age'] is not None else '?'} th maksimal "
                          f"sekitar {ton(upper)} dalam 30 hari (sudah dilonggarkan 15% di atas potensi PPKS). "
                          "Kemungkinan TBS dari kebun lain memakai paspor ini."))
    elif used > 0.85 * upper:
        flags.append(Flag("MENDEKATI_KAPASITAS", "info", f"Mendekati batas kapasitas ({pct:.0f}%)",
                          "Volume 30 hari terakhir sudah mendekati batas atas produksi kebun ini."))

    if upper > 0 and weight_kg > 0.6 * upper and not any(f.code == "MELEBIHI_KAPASITAS" for f in flags):
        flags.append(Flag("BERAT_TIDAK_WAJAR", "sedang", "Berat satu kali jual tidak wajar",
                          "Satu kali panen biasanya 1/2-1/3 produksi bulanan (rotasi 10-15 hari)."))

    recent_days = {h.created_at.date() for h in history
                   if when - timedelta(days=7) <= h.created_at < when and h.created_at.date() != when.date() and h.decision != "ditahan"}
    if len(recent_days) >= 2:
        flags.append(Flag("PANEN_TERLALU_RAPAT", "sedang", f"{len(recent_days) + 1} kali jual dalam 7 hari",
                          "Rotasi panen sawit normal 10-15 hari sekali."))

    others = {h.collector_id for h in history if when - timedelta(days=3) <= h.created_at <= when and h.collector_id != collector_id}
    if others:
        flags.append(Flag("MULTI_PENGEPUL", "sedang", "Paspor dipakai pengepul lain dalam 3 hari terakhir",
                          "Satu kebun dijual ke beberapa pengepul dalam waktu berdekatan; cek kemungkinan QR digandakan."))

    if any(f.severity == "tinggi" for f in flags):
        decision = "ditahan"
    elif any(f.severity == "sedang" for f in flags):
        decision = "catatan"
    else:
        decision = "diterima"
    return CheckResult(decision, flags, round(used), upper, cap["typical_kg_30d"], round(min(pct, 999), 1), cap["age"])


# ---------------- Deteksi anomali pengepul ----------------

FEATURE_LABELS = {
    "kg_per_ha_month": ("Rata-rata kg TBS per ha kebun pemasok per bulan", "{:.0f} kg/ha/bln"),
    "flagged_share": ("Porsi transaksi bertanda/ditahan", "{:.0%}"),
    "untraced_share": ("Porsi setoran ke pabrik yang tidak tertelusur ke kebun", "{:.0%}"),
    "near_cap_share": ("Porsi kebun pemasok yang menyentuh >85% kapasitas", "{:.0%}"),
    "txn_per_plot_month": ("Frekuensi jual per kebun per bulan", "{:.1f}x"),
}


# nilai minimum agar sebuah fitur layak dijadikan "alasan" (hindari alasan yang tidak bermakna)
MEANINGFUL_MIN = {"kg_per_ha_month": 1800, "flagged_share": 0.10, "untraced_share": 0.15,
                  "near_cap_share": 0.15, "txn_per_plot_month": 3.5}


_SCORE_CACHE: dict[tuple, dict[int, dict]] = {}


def score_collectors(features: dict[int, dict[str, float]]) -> dict[int, dict]:
    """Isolation Forest + penjelasan z-score robust. Mengembalikan skor 0-100 per pengepul.

    Model dilatih ulang hanya bila data pengepul berubah: random_state tetap, jadi hasil untuk data yang sama selalu sama
    dan bisa dipakai lagi (dasbor pabrik dibuka berulang tanpa transaksi baru tidak perlu melatih 150 pohon lagi).
    """
    ids = list(features)
    if not ids:
        return {}
    keys = list(FEATURE_LABELS)
    X = np.array([[features[i].get(k, 0.0) for k in keys] for i in ids], dtype=float)
    key = (tuple(ids), X.round(9).tobytes())
    if key in _SCORE_CACHE:
        return copy.deepcopy(_SCORE_CACHE[key])
    out = _score(ids, keys, X)
    if len(_SCORE_CACHE) >= 32:
        _SCORE_CACHE.clear()
    _SCORE_CACHE[key] = copy.deepcopy(out)
    return out


def _score(ids: list[int], keys: list[str], X: np.ndarray) -> dict[int, dict]:
    med = np.median(X, axis=0)
    mad = 1.4826 * np.median(np.abs(X - med), axis=0)
    scale = np.where(mad > 1e-9, mad, np.where(np.std(X, axis=0) > 1e-9, np.std(X, axis=0), 1.0))
    Z = (X - med) / scale

    if len(ids) >= 5:
        from sklearn.ensemble import IsolationForest

        iso = IsolationForest(n_estimators=150, contamination="auto", random_state=42)
        iso.fit(Z)
        raw = -iso.score_samples(Z)  # makin besar makin anomali
    else:
        raw = np.abs(Z).max(axis=1)
    lo, hi = float(raw.min()), float(raw.max())
    norm = (raw - lo) / (hi - lo) if hi > lo else np.zeros_like(raw)

    out: dict[int, dict] = {}
    for n, cid in enumerate(ids):
        reasons = []
        # hanya arah "lebih buruk" (nilai lebih tinggi) yang dijadikan alasan
        for j, k in enumerate(keys):
            if Z[n, j] >= 2.0 and X[n, j] >= MEANINGFUL_MIN[k]:
                label, fmt = FEATURE_LABELS[k]
                reasons.append({"feature": k, "label": label, "value": fmt.format(X[n, j]),
                                "typical": fmt.format(med[j]), "z": round(float(Z[n, j]), 1)})
        reasons.sort(key=lambda r: -r["z"])
        score = round(float(norm[n]) * 100)
        if not reasons:
            score = min(score, 35)  # tanpa alasan yang bisa dijelaskan, jangan dilabeli tinggi
        level = "tinggi" if score >= 70 else "sedang" if score >= 40 else "rendah"
        out[cid] = {"score": score, "level": level, "reasons": reasons[:3],
                    "features": {k: round(float(X[n, j]), 3) for j, k in enumerate(keys)}}
    return out
