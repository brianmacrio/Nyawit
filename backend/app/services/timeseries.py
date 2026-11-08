"""Deteksi perubahan tutupan lahan dari time series NDVI (COLD-lite).

Diadaptasi dari algoritma CCDC (Zhu & Woodcock, 2014) dan penyempurnaannya COLD
(Zhu et al., 2020). Dalam studi pembanding 6 algoritma (Remote Sensing 17:680,
2025), COLD meraih F1 tertinggi (81,8%) dibanding CCDC (~76,5%) dan BFAST (70,6%).

Versi ringan ini (satu indeks, NDVI) bekerja seperti berikut:
1. Inisialisasi: model harmonik (tren + musiman) dicocokkan dengan regresi robust
   (IRLS, bobot Tukey bisquare) pada >= 1 tahun observasi yang stabil.
2. Pemantauan: tiap observasi baru dibandingkan dengan prediksi model. Perubahan
   baru "dikonfirmasi" jika `consec` observasi berturut-turut menyimpang > z_thresh
   ke arah yang sama. Penyimpangan tunggal (awan, bayangan) dianggap derau.
3. Setelah perubahan, model diinisialisasi ulang (bisa mendeteksi pembukaan lahan
   lalu penanaman ulang dalam satu deret).
4. Estimasi tahun tanam: tanggal terakhir lahan terbuka (NDVI rendah) setelah
   pembukaan lahan, mengikuti pendekatan Descals et al. (2024, ESSD 16:5111).

Hanya numpy: cepat (< 5 ms per kebun) dan hemat energi, tanpa GPU.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

import numpy as np

from .fmt import bulan


@dataclass
class Break:
    date: str
    t: float
    magnitude: float  # perubahan NDVI (negatif = vegetasi hilang)
    z_median: float
    n_consecutive: int
    confidence: str  # tinggi | sedang
    after_cutoff: bool = False


@dataclass
class Segment:
    start: str
    end: str
    mean_ndvi: float
    rmse: float
    n_obs: int
    slope_per_year: float
    cover: str  # tafsiran kasar: vegetasi_rapat | vegetasi_sedang | lahan_terbuka


@dataclass
class ChangeResult:
    dates: list[str]
    ndvi: list[float]
    fitted: list[float | None]
    is_outlier: list[bool]
    curve: list[dict]
    segments: list[Segment] = field(default_factory=list)
    breaks: list[Break] = field(default_factory=list)
    pending_change: dict | None = None
    planting_year: int | None = None
    planting_note: str = ""
    n_obs: int = 0
    span_years: float = 0.0
    params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def frac_year(d: date) -> float:
    start = date(d.year, 1, 1)
    days = (date(d.year + 1, 1, 1) - start).days
    return d.year + (d - start).days / days


def from_frac_year(t: float) -> date:
    y = int(np.floor(t))
    start = date(y, 1, 1)
    days = (date(y + 1, 1, 1) - start).days
    return start + timedelta(days=int(round((t - y) * days)))


def _design(t: np.ndarray, t_ref: float, n_harm: int) -> np.ndarray:
    cols = [np.ones_like(t), t - t_ref]
    for k in range(1, n_harm + 1):
        w = 2 * np.pi * k * t
        cols.append(np.cos(w))
        cols.append(np.sin(w))
    return np.column_stack(cols)


def robust_fit(t: np.ndarray, y: np.ndarray, t_ref: float, n_harm: int, iters: int = 12):
    """Regresi harmonik robust (IRLS Tukey bisquare). Mengembalikan (beta, rmse_robust)."""
    X = _design(t, t_ref, n_harm)
    w = np.ones_like(y)
    beta = np.zeros(X.shape[1])
    for _ in range(iters):
        sw = np.sqrt(w)
        beta, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
        r = y - X @ beta
        s = 1.4826 * np.median(np.abs(r - np.median(r)))
        s = max(s, 1e-4)
        u = r / (4.685 * s)
        w = np.where(np.abs(u) < 1, (1 - u**2) ** 2, 0.0)
    r = y - X @ beta
    rmse = float(1.4826 * np.median(np.abs(r)))
    return beta, rmse


def _predict(beta: np.ndarray, t: np.ndarray, t_ref: float, n_harm: int) -> np.ndarray:
    return _design(np.atleast_1d(t), t_ref, n_harm) @ beta


def _cover(mean_ndvi: float) -> str:
    if mean_ndvi >= 0.7:
        return "vegetasi_rapat"
    if mean_ndvi >= 0.45:
        return "vegetasi_sedang"
    return "lahan_terbuka"


def detect_changes(
    dates: list[date],
    values: list[float],
    *,
    cutoff: date = date(2020, 12, 31),
    consec: int = 5,
    z_thresh: float = 3.0,
    min_init_obs: int = 12,
    init_span_years: float = 1.0,
    rmse_floor: float = 0.035,
    min_magnitude: float = 0.12,
) -> ChangeResult:
    order = np.argsort(np.array([d.toordinal() for d in dates]))
    d_sorted = [dates[i] for i in order]
    y = np.asarray(values, dtype=float)[order]
    keep = np.isfinite(y)
    d_sorted = [d for d, k in zip(d_sorted, keep) if k]
    y = y[keep]
    t = np.array([frac_year(d) for d in d_sorted])
    n = len(y)

    res = ChangeResult(
        dates=[d.isoformat() for d in d_sorted],
        ndvi=[round(float(v), 4) for v in y],
        fitted=[None] * n,
        is_outlier=[False] * n,
        curve=[],
        n_obs=n,
        span_years=float(t[-1] - t[0]) if n else 0.0,
        params={"consec": consec, "z_thresh": z_thresh, "min_init_obs": min_init_obs, "algoritma": "COLD-lite (harmonik robust + konfirmasi berturut-turut)"},
    )
    if n < min_init_obs:
        res.planting_note = "Observasi bebas awan terlalu sedikit untuk analisis."
        return res

    t_cut = frac_year(cutoff)
    i0 = 0
    while i0 < n:
        # ---------- 1. Inisialisasi segmen ----------
        init_end = i0
        while init_end < n and (t[init_end] - t[i0] < init_span_years or init_end - i0 < min_init_obs):
            init_end += 1
        if init_end - i0 < min_init_obs or init_end > n:
            # sisa observasi tidak cukup untuk segmen baru
            break
        idx = np.arange(i0, init_end)
        n_harm = 1 if len(idx) < 24 else 2
        t_ref = float(t[i0])
        beta, rmse = robust_fit(t[idx], y[idx], t_ref, n_harm)

        # uji stabilitas (CCDC/COLD): observasi pertama & terakhir masa inisialisasi
        # tidak boleh menyimpang jauh dari model (tanda masih ada perubahan mendadak).
        r_init = y[idx] - _predict(beta, t[idx], t_ref, n_harm)
        lim = 3 * max(rmse, rmse_floor)
        if (abs(r_init[0]) > lim or abs(r_init[-1]) > lim) and init_end < n - min_init_obs:
            i0 += 1
            continue

        seg_idx = list(idx)
        refit_at = len(seg_idx) + 6
        j = init_end
        run: list[int] = []
        run_sign = 0
        broke = False
        while j < n:
            pred = float(_predict(beta, t[j], t_ref, n_harm)[0])
            z = (y[j] - pred) / max(rmse, rmse_floor)
            sign = int(np.sign(z)) if abs(z) > z_thresh else 0
            if sign != 0 and (not run or sign == run_sign):
                run.append(j)
                run_sign = sign
                if len(run) >= consec:
                    # ---------- perubahan terkonfirmasi ----------
                    preds = _predict(beta, t[run], t_ref, n_harm)
                    diffs = y[run] - preds
                    zs = diffs / max(rmse, rmse_floor)
                    zmed = float(np.median(zs))
                    # besar perubahan diukur terhadap tingkat NDVI terakhir yang normal,
                    # bukan terhadap ekstrapolasi tren (agar pertumbuhan sawit muda yang
                    # melambat tidak terbaca sebagai pembukaan lahan).
                    recent = y[np.array(seg_idx[-8:])]
                    mag = float(np.median(y[run]) - np.median(recent))
                    if abs(mag) < min_magnitude or np.sign(mag) != run_sign:
                        # penyimpangan kecil = model perlu diperbarui (mis. kebun muda yang
                        # pertumbuhannya melambat), bukan perubahan tutupan lahan.
                        seg_idx.extend(run)
                        si = np.array(seg_idx)
                        n_harm = 1 if len(si) < 24 else 2
                        beta, rmse = robust_fit(t[si], y[si], t_ref, n_harm)
                        refit_at = len(seg_idx) + 6
                        run, run_sign = [], 0
                        j += 1
                        continue
                    conf = "tinggi" if abs(zmed) >= 2 * z_thresh and abs(mag) >= 0.15 else "sedang"
                    bdate = d_sorted[run[0]]
                    res.breaks.append(
                        Break(
                            date=bdate.isoformat(),
                            t=round(float(t[run[0]]), 3),
                            magnitude=round(mag, 3),
                            z_median=round(zmed, 2),
                            n_consecutive=len(run),
                            confidence=conf,
                            after_cutoff=bool(t[run[0]] > t_cut),
                        )
                    )
                    broke = True
                    break
            else:
                if run and sign == 0:
                    # anomali tidak berlanjut -> dianggap awan/derau
                    for k in run:
                        res.is_outlier[k] = True
                    run = []
                    run_sign = 0
                if sign != 0:  # arah berbalik: run lama dianggap derau, mulai run baru
                    for k in run:
                        res.is_outlier[k] = True
                    run = [j]
                    run_sign = sign
                else:
                    seg_idx.append(j)
                    if len(seg_idx) >= refit_at:
                        si = np.array(seg_idx)
                        n_harm = 1 if len(si) < 24 else 2
                        beta, rmse = robust_fit(t[si], y[si], t_ref, n_harm)
                        refit_at = len(seg_idx) + 6
            j += 1

        # ---------- simpan segmen ----------
        si = np.array(seg_idx)
        for k in si:
            res.fitted[k] = round(float(_predict(beta, t[k], t_ref, n_harm)[0]), 4)
        seg_end_t = t[run[0] - 1] if broke and run[0] > 0 else t[min(j, n - 1)]
        mean_ndvi = float(np.mean(y[si]))
        res.segments.append(
            Segment(
                start=d_sorted[si[0]].isoformat(),
                end=from_frac_year(seg_end_t).isoformat(),
                mean_ndvi=round(mean_ndvi, 3),
                rmse=round(rmse, 4),
                n_obs=len(si),
                slope_per_year=round(float(beta[1]), 4),
                cover=_cover(mean_ndvi),
            )
        )
        grid = np.arange(t[si[0]], seg_end_t + 1e-9, 1 / 24)
        for tt in grid:
            res.curve.append(
                {
                    "date": from_frac_year(float(tt)).isoformat(),
                    "value": round(float(_predict(beta, tt, t_ref, n_harm)[0]), 4),
                    "segment": len(res.segments) - 1,
                }
            )

        if not broke:
            if run:
                res.pending_change = {
                    "date": d_sorted[run[0]].isoformat(),
                    "n_consecutive": len(run),
                    "needed": consec,
                    "direction": "turun" if run_sign < 0 else "naik",
                }
            break
        i0 = run[0]

    _estimate_planting_year(res, t, y, d_sorted)
    return res


def _estimate_planting_year(res: ChangeResult, t: np.ndarray, y: np.ndarray, d: list[date]) -> None:
    """Tahun tanam = tanggal terakhir lahan terbuka setelah pembukaan lahan terakhir."""
    clearing = [b for b in res.breaks if b.magnitude <= -0.2]
    if not clearing:
        if res.segments and res.segments[0].mean_ndvi >= 0.6:
            res.planting_note = (
                f"Tidak ada pembukaan lahan sejak {d[0].year}. Kebun sudah bervegetasi rapat "
                f"sejak awal data, sehingga ditanam sebelum {d[0].year}."
            )
        else:
            res.planting_note = "Tahun tanam tidak dapat diperkirakan dari citra."
        return
    last = clearing[-1]
    window = (t >= last.t) & (t <= last.t + 1.75) & np.array([not o for o in res.is_outlier])
    if not window.any():
        return
    idx = np.where(window)[0]
    # haluskan dengan median bergerak 3 titik agar awan tunggal tidak terbaca sebagai lahan terbuka
    ys = np.array([np.median(y[max(i - 1, idx[0]) : min(i + 2, idx[-1] + 1)]) for i in idx])
    bare = idx[ys < 0.38]
    ref = bare[-1] if len(bare) else idx[int(np.argmin(ys))]
    res.planting_year = d[ref].year
    res.planting_note = (
        f"Lahan dibuka sekitar {bulan(last.date)}, lahan terbuka terakhir terlihat {bulan(d[ref].isoformat())}. "
        f"Perkiraan tahun tanam {d[ref].year} (galat tipikal metode ini ±2-5 tahun)."
    )
