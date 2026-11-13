"""Mesin keputusan risiko EUDR berbasis "convergence of evidence".

Mengikuti logika Whisp (FAO / Forest Data Partnership) untuk tanaman tahunan:
tidak ada satu peta pun yang selalu benar, jadi keputusan diambil dari kesepakatan
beberapa sumber bukti. Kami menambah dua hal:
  * bukti time series milik sendiri (COLD-lite, 5+ tahun data), dan
  * pembeda PEREMAJAAN vs DEFORESTASI: gangguan setelah 2020 pada lahan yang tahun
    2020 sudah kebun sawit adalah peremajaan (mis. program PSR), bukan deforestasi.

Aturan (urutan diterapkan):
  0. Kebun tumpang tindih kawasan hutan > 5% (peta Kemenhut)  -> tinggi (legalitas)
  1. Tutupan pohon 2020 <= 10%                                -> rendah
  2. Ada tutupan pohon, tapi 2020 sudah komoditas (>= 50%)    -> rendah
  3. Ada tutupan pohon, gangguan sebelum 2021 (>= 50%)        -> rendah
  4. Ada tutupan pohon (hutan) dan gangguan sesudah 2020      -> tinggi
  5. Selain itu                                               -> perlu_cek (butuh info)
Ambang mengikuti default Whisp (10% / 50%).
Setelah aturan 1-5: hasil "rendah" diturunkan menjadi perlu_cek bila fungsi kawasan tidak
terbaca, atau (mode live) bila status kawasan belum bisa dicek ke peta resmi.
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

NOTE_KONSERVASI = ("Kawasan konservasi dan hutan lindung umumnya tidak bisa dilepas untuk kebun. Penyelesaian kebun yang "
                   "telanjur ada diatur UU Cipta Kerja Pasal 110A/110B; arahkan petani ke pendamping atau KPH setempat "
                   "sebelum TBS dijual ke rantai pasok ekspor.")
NOTE_PRODUKSI = ("Kebun di hutan produksi perlu diselesaikan dulu, misalnya lewat pelepasan kawasan/TORA, perhutanan sosial, "
                 "atau mekanisme keterlanjuran UU Cipta Kerja Pasal 110A/110B. Arahkan petani ke pendamping atau KPH setempat.")
NOTE_BUKTI = ("Peta resmi bisa tertinggal dari SK pelepasan terbaru. Bila petani punya sertifikat atau SK pelepasan kawasan, "
              "lampirkan untuk verifikasi manual.")


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


def _kawasan_value(kw: dict) -> str:
    pct = kw.get("pct", 0.0)
    parts = [p for p in kw.get("parts", []) if p.get("kawasan") and p["pct"] >= 1]
    if pct > 0:
        main = ", ".join(f"{dec(p['pct'], 0)}% {p['label']}" for p in parts[:2]) or f"{dec(pct, 0)}% kawasan hutan"
        return main
    if kw.get("unknown_pct", 0) > 0:
        return f"{dec(kw['unknown_pct'], 0)}% di poligon tanpa fungsi terbaca"
    src = kw.get("source")
    if src == "tidak_ada":
        return "belum dicek"
    if any(p["fungsi"] == "APL" and p["pct"] >= 50 for p in kw.get("parts", [])):
        return "di luar kawasan hutan (APL)"
    return "di luar kawasan hutan" + (" (peta ilustrasi)" if src == "ilustrasi" else "")


def _kawasan_item(kw: dict, strict: bool) -> EvidenceItem:
    pct = kw.get("pct", 0.0)
    if pct > T_PROTECTED:
        verdict = "mendukung_risiko"
    elif kw.get("unknown_pct", 0) > T_PROTECTED:
        verdict = "netral"
    elif kw.get("checked") or (not strict and kw.get("source") == "ilustrasi"):
        verdict = "mendukung_aman"
    else:
        verdict = "tidak_tersedia"
    detail = ("Aspek legalitas EUDR: lahan harus legal menurut hukum negara asal. Peta kawasan berskala kecil, "
              "jadi batasnya bisa bergeser puluhan hingga ratusan meter.")
    return EvidenceItem("protected", "Status kawasan hutan", _kawasan_value(kw), verdict,
                        kw.get("source_label") or LAYER_SOURCES["protected"], detail)


def decide(layers: dict[str, float | None], ts: ChangeResult | None, protected_pct: float,
           kawasan: dict | None = None, strict: bool = False, forest_map: str | None = None,
           layer_sources: dict[str, str] | None = None) -> RiskDecision:
    """`kawasan` = hasil services.kawasan.lookup().to_dict(); `strict` = mode live (peta resmi wajib dicek).

    `forest_map="jrc"`: lapisan tutupan 2020 berasal dari peta HUTAN JRC GFC2020 yang sudah mengecualikan
    kebun sawit, jadi "ada tutupan + kehilangan sesudah 2020" tidak perlu menunggu peta komoditas.
    """
    src = {**LAYER_SOURCES, **(layer_sources or {})}
    jrc = forest_map == "jrc"
    tree = layers.get("tree_cover_2020")
    com = layers.get("commodity_2020")
    before = layers.get("disturbance_before_2021")
    after = layers.get("disturbance_after_2020")

    clearing_after = [b for b in (ts.breaks if ts else []) if b.after_cutoff and b.magnitude <= -0.2]
    clearing_before = [b for b in (ts.breaks if ts else []) if not b.after_cutoff and b.magnitude <= -0.2]
    ts_ok = ts is not None and ts.n_obs >= 40 and ts.span_years >= 5

    kw = kawasan or {"pct": protected_pct, "checked": True, "source": "lokal", "parts": [], "unknown_pct": 0.0,
                     "label": None, "name": None, "fungsi": None, "source_label": LAYER_SOURCES["protected"]}
    items: list[EvidenceItem] = [_kawasan_item(kw, strict)]
    items.append(
        EvidenceItem(
            "tree_cover_2020", "Hutan per 31 Des 2020 (peta JRC)" if jrc else "Tutupan pohon per 31 Des 2020", _pct(tree),
            "tidak_tersedia" if tree is None else ("netral" if tree > T_TREE else "mendukung_aman"),
            src["tree_cover_2020"],
            ("Peta hutan acuan UE: kebun sawit/karet tidak dihitung hutan. Peta ini bisa keliru menyebut kebun "
             "swadaya tua yang rapat sebagai hutan, jadi tetap perlu dicocokkan dengan bukti lain."
             if jrc else "Tutupan pohon belum tentu hutan: kebun sawit tua juga terbaca sebagai pohon."),
        )
    )
    items.append(
        EvidenceItem(
            "commodity_2020", "Sudah kebun sawit pada 2020", _pct(com),
            "tidak_tersedia" if com is None else ("mendukung_aman" if com >= T_COMMODITY else "netral"),
            src["commodity_2020"],
        )
    )
    items.append(
        EvidenceItem(
            "disturbance_before_2021", "Lahan dibuka sebelum 2021", _pct(before),
            "tidak_tersedia" if before is None else ("mendukung_aman" if before >= T_DIST_BEFORE else "netral"),
            src["disturbance_before_2021"],
        )
    )
    by_year = layers.get("loss_after_by_year") or {}
    after_val = _pct(after)
    if after and by_year:
        after_val += " (" + ", ".join(f"{y}: {dec(v, 0)}%" for y, v in sorted(by_year.items()) if v >= 1) + ")"
        after_val = after_val.replace(" ()", "")
    after_verdict = "tidak_tersedia" if after is None else ("mendukung_risiko" if after >= T_DIST_AFTER else "mendukung_aman")
    if jrc and after is not None and after >= T_DIST_AFTER and tree is not None and tree <= T_TREE:
        after_verdict = "netral"  # kehilangan tutupan di lahan yang bukan hutan 2020: peremajaan/panen, bukan deforestasi
    items.append(
        EvidenceItem(
            "disturbance_after_2020", "Kehilangan tutupan setelah 2020", after_val, after_verdict,
            src["disturbance_after_2020"],
            "Kehilangan tutupan pohon belum tentu deforestasi: peremajaan atau panen kebun juga terhitung."
            if after else "",
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

    # ---- Aturan 0: legalitas (status kawasan hutan) ----
    if protected_pct > T_PROTECTED:
        dom = next((p for p in kw.get("parts", []) if p.get("kawasan")), None)
        where = dom["label"] if dom else "kawasan hutan"
        if dom and dom["label"] == "Kawasan konservasi":
            where = "kawasan konservasi"
        notes = [NOTE_KONSERVASI if (dom is None or dom["fungsi"] in ("KSA_KPA", "HL")) else NOTE_PRODUKSI, NOTE_BUKTI]
        if dom and dom.get("name") and dom["name"] != dom["label"] and dom.get("source") != "ilustrasi":
            notes.insert(0, f"Poligon kawasan: {dom['name']} ({dom['label']}).")
        return RiskDecision("tinggi", f"Berisiko: {protected_pct:.0f}% kebun masuk {where}", "aturan-0-legalitas",
                            0.95 if kw.get("checked") or kw.get("source") == "ilustrasi" else 0.8, items, notes)

    r = _satellite_rules(items, tree, com, before, after, ts, clearing_after, clearing_before, ts_ok, jrc,
                         layers.get("loss_after_main_year"))
    if 0 < protected_pct <= T_PROTECTED:
        r.notes.append(f"{dec(protected_pct, 1)}% kebun bersinggungan dengan batas kawasan hutan. Selisih sekecil ini bisa "
                       "berasal dari ketelitian peta; pastikan patok batas di lapangan.")
    if r.risk_level == "rendah" and kw.get("unknown_pct", 0) > T_PROTECTED:
        return RiskDecision("perlu_cek", "Perlu cek: fungsi kawasan di lokasi kebun belum terbaca dari peta",
                            "aturan-0-fungsi-belum-terbaca", 0.5, items,
                            r.notes + ["Bukti satelit aman, tetapi kebun berada di poligon peta kawasan yang fungsinya tidak "
                                       "terbaca. Jalankan `python -m app.scripts.check_kawasan` untuk melihat kolomnya."],
                            is_replanting=r.is_replanting)
    if r.risk_level == "rendah" and strict and not kw.get("checked"):
        return RiskDecision("perlu_cek", "Perlu cek: status kawasan hutan belum bisa diperiksa", "aturan-0-belum-dicek", 0.5,
                            items, r.notes + ["Bukti satelit aman, tetapi peta kawasan Kemenhut belum terjangkau. Analisis "
                                              "ulang saat internet tersedia atau taruh peta kawasan resmi (GeoJSON) di "
                                              "backend/data/kawasan/."], is_replanting=r.is_replanting)
    return r


def _satellite_rules(items, tree, com, before, after, ts, clearing_after, clearing_before, ts_ok, jrc=False,
                     loss_year=None) -> RiskDecision:
    notes: list[str] = []
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
        if jrc and post_layer:
            yr = loss_year or (clearing_after[-1].date[:4] if clearing_after else "setelah 2020")
            notes.append(f"Peta GFW mencatat kehilangan tutupan pohon {yr} di {dec(after, 0)}% kebun, tetapi peta hutan JRC "
                         "menyebut lahan ini bukan hutan pada 2020. Artinya pohon yang ditebang adalah tanaman (mis. "
                         "peremajaan sawit), bukan hutan, sehingga tidak termasuk deforestasi menurut EUDR.")
            return RiskDecision("rendah", f"Aman: kehilangan tutupan {yr} di lahan yang bukan hutan pada 2020 (peremajaan)",
                                "aturan-1-peremajaan", 0.85, items, notes, is_replanting=True)
        return RiskDecision("rendah", "Aman: bukan hutan pada 31 Des 2020" if jrc else
                            "Aman: tidak ada tutupan pohon pada 31 Des 2020", "aturan-1", 0.85, items, notes,
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
    if n_post > 0 and com is None and not jrc:
        pre = _segment_before(ts, clearing_after[-1].date) if clearing_after else None
        if pre is None or pre < 0.83:
            notes.append("Lapisan komoditas 2020 tidak tersedia sehingga peremajaan sawit dan pembukaan hutan "
                         "belum bisa dibedakan. Aktifkan lapisan sawit (Earth Engine/Whisp) atau cek lapangan.")
            return RiskDecision("perlu_cek", "Perlu cek: ada pembukaan lahan setelah 2020, jenis tutupan sebelumnya belum pasti",
                                "aturan-4-tanpa-komoditas", 0.5, items, notes)
    if n_post > 0:
        conf = 0.6 + 0.35 * (n_post / max(n_avail, 1))
        when = bulan(clearing_after[-1].date) if clearing_after else (loss_year or "setelah 2020")
        if jrc and post_layer:
            notes.append(f"Peta hutan JRC: {dec(tree, 0)}% kebun masih hutan pada 2020; peta Hansen: {dec(after, 0)}% "
                         "kehilangan tutupan sesudah 2020. Bila petani punya bukti kebun sudah ditanam sebelum 2021 "
                         "(peta JRC bisa keliru di kebun tua), ajukan keberatan dengan foto dan dokumen.")
        return RiskDecision("tinggi", f"Berisiko: hutan dibuka {when}, setelah batas EUDR", "aturan-4",
                            round(conf, 2), items, notes + [f"{n_post} dari {n_avail} sumber bukti menunjukkan pembukaan hutan setelah 2020."])
    if jrc:
        notes.append(f"Peta hutan JRC menyebut {dec(tree, 0)}% kebun masih hutan pada 2020 dan tidak ada kehilangan tutupan "
                     "sesudahnya. Bisa jadi memang hutan (belum ditanami), atau kebun sawit tua yang rapat dan salah "
                     "terbaca sebagai hutan. Perlu verifikasi lapangan (foto geotag) atau citra resolusi tinggi.")
    else:
        notes.append("Ada tutupan pohon pada 2020 tetapi tidak ada bukti sawit maupun pembukaan lahan. Perlu verifikasi lapangan (foto geotag) atau citra resolusi tinggi.")
    return RiskDecision("perlu_cek", "Perlu cek: bukti satelit belum cukup untuk memutuskan", "aturan-5", 0.5, items, notes)
