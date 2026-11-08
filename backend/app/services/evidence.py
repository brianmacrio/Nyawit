"""Mesin keputusan risiko EUDR berbasis "convergence of evidence".

Mengikuti logika Whisp (FAO / Forest Data Partnership) untuk tanaman tahunan:
tidak ada satu peta pun yang selalu benar, jadi keputusan diambil dari kesepakatan
beberapa sumber bukti. Kami menambah dua hal:
  * bukti time series milik sendiri (COLD-lite, 5+ tahun data), dan
  * pembeda PEREMAJAAN vs DEFORESTASI: gangguan setelah 2020 pada lahan yang tahun
    2020 sudah kebun sawit adalah peremajaan (mis. program PSR), bukan deforestasi.

Aturan (urutan diterapkan):
  0. Kebun tumpang tindih kawasan hutan/konservasi > 5%       -> tinggi (legalitas)
  1. Tutupan pohon 2020 <= 10%                                -> rendah
  2. Ada tutupan pohon, tapi 2020 sudah komoditas (>= 50%)    -> rendah
  3. Ada tutupan pohon, gangguan sebelum 2021 (>= 50%)        -> rendah
  4. Ada tutupan pohon (hutan) dan gangguan sesudah 2020      -> tinggi
  5. Selain itu                                               -> perlu_cek (butuh info)
Ambang mengikuti default Whisp (10% / 50%).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .fmt import bulan, dec
from .timeseries import ChangeResult

T_TREE = 10.0
T_COMMODITY = 50.0
T_DIST_BEFORE = 50.0
T_DIST_AFTER = 10.0
T_PROTECTED = 5.0

LAYER_SOURCES = {
    "tree_cover_2020": "JRC Global Forest Cover 2020 (akurasi keseluruhan 91%)",
    "commodity_2020": "Peta probabilitas sawit Forest Data Partnership / Descals et al. 2021",
    "disturbance_before_2021": "Hansen Global Forest Change (kehilangan tutupan 2001-2020)",
    "disturbance_after_2020": "Hansen GFC 2021-2025 + peringatan RADD Sentinel-1",
    "protected": "Peta kawasan hutan / kawasan konservasi",
}


@dataclass
class EvidenceItem:
    key: str
    label: str
    value: str
    verdict: str  # mendukung_aman | mendukung_risiko | netral | tidak_tersedia
    source: str
    detail: str = ""


@dataclass
class RiskDecision:
    risk_level: str  # rendah | perlu_cek | tinggi
    headline: str
    rule: str
    confidence: float
    items: list[EvidenceItem] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    is_replanting: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _segment_before(ts: ChangeResult | None, break_date: str) -> float | None:
    if not ts:
        return None
    prev = [s for s in ts.segments if s.end <= break_date]
    return prev[-1].mean_ndvi if prev else None


def _pct(v: float | None) -> str:
    return "tidak tersedia" if v is None else f"{v:.0f}% luas kebun"


def decide(layers: dict[str, float | None], ts: ChangeResult | None, protected_pct: float) -> RiskDecision:
    tree = layers.get("tree_cover_2020")
    com = layers.get("commodity_2020")
    before = layers.get("disturbance_before_2021")
    after = layers.get("disturbance_after_2020")

    clearing_after = [b for b in (ts.breaks if ts else []) if b.after_cutoff and b.magnitude <= -0.2]
    clearing_before = [b for b in (ts.breaks if ts else []) if not b.after_cutoff and b.magnitude <= -0.2]
    ts_ok = ts is not None and ts.n_obs >= 40 and ts.span_years >= 5

    items: list[EvidenceItem] = []
    items.append(
        EvidenceItem(
            "protected", "Tumpang tindih kawasan hutan/konservasi", f"{protected_pct:.0f}% luas kebun",
            "mendukung_risiko" if protected_pct > T_PROTECTED else "mendukung_aman", LAYER_SOURCES["protected"],
            "Aspek legalitas EUDR: lahan harus legal menurut hukum negara asal.",
        )
    )
    items.append(
        EvidenceItem(
            "tree_cover_2020", "Tutupan pohon per 31 Des 2020", _pct(tree),
            "tidak_tersedia" if tree is None else ("netral" if tree > T_TREE else "mendukung_aman"),
            LAYER_SOURCES["tree_cover_2020"],
            "Tutupan pohon belum tentu hutan: kebun sawit tua juga terbaca sebagai pohon.",
        )
    )
    items.append(
        EvidenceItem(
            "commodity_2020", "Sudah kebun sawit pada 2020", _pct(com),
            "tidak_tersedia" if com is None else ("mendukung_aman" if com >= T_COMMODITY else "netral"),
            LAYER_SOURCES["commodity_2020"],
        )
    )
    items.append(
        EvidenceItem(
            "disturbance_before_2021", "Lahan dibuka sebelum 2021", _pct(before),
            "tidak_tersedia" if before is None else ("mendukung_aman" if before >= T_DIST_BEFORE else "netral"),
            LAYER_SOURCES["disturbance_before_2021"],
        )
    )
    items.append(
        EvidenceItem(
            "disturbance_after_2020", "Kehilangan tutupan setelah 2020", _pct(after),
            "tidak_tersedia" if after is None else ("mendukung_risiko" if after >= T_DIST_AFTER else "mendukung_aman"),
            LAYER_SOURCES["disturbance_after_2020"],
        )
    )
    if ts is None or ts.n_obs == 0:
        items.append(EvidenceItem("timeseries", "Analisis time series NDVI (AI)", "tidak tersedia", "tidak_tersedia", "Sentinel-2"))
    else:
        if clearing_after:
            b = clearing_after[-1]
            val = f"pembukaan lahan {bulan(b.date)} (NDVI turun {dec(abs(b.magnitude), 2)})"
            verdict = "mendukung_risiko"
        elif clearing_before:
            b = clearing_before[-1]
            val = f"pembukaan lahan {bulan(b.date)}, sebelum batas"
            verdict = "mendukung_aman"
        else:
            val = f"stabil, tanpa pembukaan lahan ({ts.n_obs} citra, {dec(ts.span_years)} th)"
            verdict = "mendukung_aman" if ts_ok else "netral"
        detail = "COLD-lite: model harmonik robust; perubahan dikonfirmasi oleh 5 citra berturut-turut."
        if not ts_ok:
            detail += " Citra bebas awan terlalu sedikit sehingga bobot bukti ini rendah."
        items.append(EvidenceItem("timeseries", "Analisis time series NDVI 2018-kini (AI)", val, verdict, "Sentinel-2 L2A", detail))

    notes: list[str] = []
    # ---- Aturan 0: legalitas ----
    if protected_pct > T_PROTECTED:
        return RiskDecision(
            "tinggi",
            f"Berisiko: {protected_pct:.0f}% kebun berada di kawasan hutan/konservasi",
            "aturan-0-legalitas",
            0.95,
            items,
            ["Arahkan petani ke skema penyelesaian (mis. perhutanan sosial / keterlanjuran) sebelum dijual ke rantai pasok ekspor."],
        )

    forest_2020 = tree is not None and tree > T_TREE
    if tree is None:
        notes.append("Lapisan tutupan pohon 2020 tidak tersedia; keputusan bersandar pada time series.")
        forest_2020 = bool(ts and ts.segments and ts.segments[0].mean_ndvi >= 0.8 and not clearing_before)

    post_layer = after is not None and after >= T_DIST_AFTER
    post_ts = bool(clearing_after) and ts_ok
    n_post = int(post_layer) + int(post_ts)
    n_avail = int(after is not None) + int(ts_ok)

    replant = post_layer or bool(clearing_after)
    if not forest_2020:
        return RiskDecision("rendah", "Aman: tidak ada tutupan pohon pada 31 Des 2020", "aturan-1", 0.85, items, notes,
                            is_replanting=replant)
    if com is not None and com >= T_COMMODITY:
        if replant:
            yr = clearing_after[-1].date[:4] if clearing_after else "setelah 2020"
            pre = _segment_before(ts, clearing_after[-1].date) if clearing_after else None
            if pre is not None and pre >= 0.83:
                notes.append(
                    f"Konflik bukti: peta komoditas menyebut sawit pada 2020, tetapi NDVI sebelum dibuka ({dec(pre, 2)}) "
                    "lebih mirip hutan (~0,85) daripada sawit tua (~0,75). Perlu verifikasi lapangan."
                )
                return RiskDecision("perlu_cek", f"Perlu cek: pembukaan lahan {yr}, peremajaan atau hutan?",
                                    "aturan-2-konflik", 0.55, items, notes)
            notes.append(f"Gangguan {yr} adalah peremajaan kebun sawit, bukan deforestasi: lahan sudah kebun sawit pada 2020.")
            return RiskDecision("rendah", f"Aman: peremajaan kebun sawit ({yr}), bukan deforestasi", "aturan-2-peremajaan",
                                0.8, items, notes, is_replanting=True)
        return RiskDecision("rendah", "Aman: lahan sudah menjadi kebun sawit sebelum 2021", "aturan-2", 0.9, items, notes)
    if before is not None and before >= T_DIST_BEFORE:
        return RiskDecision("rendah", "Aman: lahan dibuka sebelum batas EUDR (31 Des 2020)", "aturan-3", 0.85, items, notes)
    if n_post > 0 and com is None:
        pre = _segment_before(ts, clearing_after[-1].date) if clearing_after else None
        if pre is None or pre < 0.83:
            notes.append("Lapisan komoditas 2020 tidak tersedia sehingga peremajaan sawit dan pembukaan hutan "
                         "belum bisa dibedakan. Aktifkan lapisan sawit (Earth Engine/Whisp) atau cek lapangan.")
            return RiskDecision("perlu_cek", "Perlu cek: ada pembukaan lahan setelah 2020, jenis tutupan sebelumnya belum pasti",
                                "aturan-4-tanpa-komoditas", 0.5, items, notes)
    if n_post > 0:
        conf = 0.6 + 0.35 * (n_post / max(n_avail, 1))
        when = bulan(clearing_after[-1].date) if clearing_after else "setelah 2020"
        return RiskDecision("tinggi", f"Berisiko: hutan dibuka {when}, setelah batas EUDR", "aturan-4",
                            round(conf, 2), items, notes + [f"{n_post} dari {n_avail} sumber bukti menunjukkan pembukaan hutan setelah 2020."])
    notes.append("Ada tutupan pohon pada 2020 tetapi tidak ada bukti sawit maupun pembukaan lahan. Perlu verifikasi lapangan (foto geotag) atau citra resolusi tinggi.")
    return RiskDecision("perlu_cek", "Perlu cek: bukti satelit belum cukup untuk memutuskan", "aturan-5", 0.5, items, notes)
