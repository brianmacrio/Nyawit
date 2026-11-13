"""Membuat data demo yang realistis (nama, desa, dan transaksi FIKTIF).

Lokasi demo: area "Kebun Swadaya" di sisi tenggara Taman Nasional Tesso Nilo, Riau, wilayah
dengan kasus TBS ilegal yang terdokumentasi. Kebun contoh ditempatkan di Areal Penggunaan Lain
menurut Peta Kawasan Hutan KLHK 2017 (Global Forest Watch); satu kebun (Rina Wati) sengaja
berada di Hutan Produksi. Batas kawasan di demo adalah data resmi itu (salinan lokal di
app/seed_data/), bukan gambar tangan. Nama petani, desa, dan poligon kebun tetap fiktif.

Jalankan ulang:  python -m app.seed
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from sqlalchemy import select

from .config import DATA_DIR, DEMO_ACCOUNTS, DEMO_PASSWORD
from .db import Base, SessionLocal, engine, init_db
from .models import Appeal, Collector, Cooperative, Delivery, Farmer, Inspection, Mill, Plot, Transaction, User
from .security import hash_password
from .services import audit
from .services import kawasan as kawasan_svc
from .services import plots as plot_svc
from .services import supply as supply_svc
from .services import verification as verification_svc
from .services.satellite import demo as demo_sim
from .services.satellite import peta_gfw
from .services.yield_model import SEASONAL, TYPICAL_SMALLHOLDER_FACTOR, potential_t_per_ha_year

CENTER = (-0.3645, 102.0625)  # (lat, lng), di dalam APL "Kebun Swadaya" menurut data GFW
M_PER_DEG = 111_320.0
# Tata letak dicerminkan (timur-barat dan utara-selatan) agar seluruh kebun contoh muat di APL
# dan kelompok kebun utama menghadap batas Hutan Produksi di barat.
FLIP_X, FLIP_Y = -1, -1
KAWASAN_FILE = Path(__file__).parent / "seed_data" / "kawasan_klhk2017_sekitar_demo.geojson"

FIRST = ["Budi", "Siti", "Sutrisno", "Joko", "Rina", "Darmawan", "Wahyuni", "Agus", "Sri", "Hasan", "Rahmat", "Yanti",
         "Bambang", "Ernawati", "Slamet", "Fitri", "Taufik", "Murni", "Iwan", "Rohani", "Syahrul", "Desi", "Mulyadi",
         "Ratna", "Andi", "Nurhayati", "Herman", "Lina", "Yusuf", "Marlina", "Riduan", "Suryani"]
LAST = ["Santoso", "Aminah", "Wibowo", "Susilo", "Wati", "Lubis", "Harahap", "Pratama", "Rahayu", "Siregar", "Hidayat",
        "Nasution", "Saputra", "Simanjuntak", "Purba", "Hasibuan", "Tanjung", "Ginting", "Sitompul", "Rangkuti"]

# bukti lahan, nomor, status STDB, saksi kedua (fiktif)
HERO_LAND = {
    "Budi Santoso": ("sertifikat", "SHM No. 01234/Sungai Harapan", "ada", "Siti Aminah (tetangga timur)"),
    "Siti Aminah": ("surat_desa", "SKGR 141/SH/2019", "proses", "Budi Santoso (tetangga barat)"),
    "Sutrisno Wibowo": ("sertifikat", "SHM No. 00877/Sungai Harapan", "ada", "Hendra Purba (tetangga selatan)"),
    "Joko Susilo": ("pernyataan", None, "belum", None),
    "Rina Wati": ("surat_desa", "SKT 22/2014", "belum", None),
    "Darmawan Lubis": ("surat_desa", "SKGR 077/SH/2012", "proses", "Joko Susilo (tetangga barat)"),
    "Wahyuni Harahap": ("surat_desa", "SKGR 102/SH/2010", "belum", "Agus Pratama (tetangga timur)"),
    "Agus Pratama": ("sertifikat", "SHM No. 00412/Sungai Harapan", "ada", "Wahyuni Harahap (tetangga barat)"),
    "Sri Rahayu": ("pernyataan", None, "proses", "Agus Pratama (tetangga utara)"),
    "Hasan Siregar": ("sertifikat", "SHM No. 00203/Sungai Harapan", "ada", "Mulyadi Purba (tetangga utara)"),
}
SIDES_DEMO = [
    {"utara": {"jenis": "parit", "tetangga": None}, "timur": {"jenis": "kebun", "tetangga": "Siti Aminah"},
     "selatan": {"jenis": "jalan", "tetangga": None}, "barat": {"jenis": "kebun", "tetangga": None}},
    {"utara": {"jenis": "jalan", "tetangga": None}, "timur": {"jenis": "kebun", "tetangga": None},
     "selatan": {"jenis": "parit", "tetangga": None}, "barat": {"jenis": "kebun", "tetangga": None}},
]
DEMO_USERS = [
    # username, nama tampilan, peran, organisasi, nama pengepul terkait
    ("koperasi", "Rahmat Hidayat", "koperasi", "KUD Tani Makmur (demo)", None),
    ("pengepul", "UD Tani Jaya", "pengepul", "UD Tani Jaya", "UD Tani Jaya"),
    ("sinarjaya", "UD Sinar Jaya", "pengepul", "UD Sinar Jaya", "UD Sinar Jaya"),
    ("pabrik", "Dewi Lestari", "pabrik", "PKS Sejahtera (demo)", None),
    ("verifikator", "Andi Saputra", "verifikator", "Lembaga verifikasi independen (demo)", None),
    ("admin", "Admin PasporKebun", "admin", "PasporKebun", None),
]

# Kebun contoh yang sengaja melanggar indikator peta, dipilih dari data NYATA (dicek 13 Nov 2026):
# - Joko: hutan menurut JRC 2020, dibuka 2025 menurut Hansen/GFW, APL di peta KLHK 2017 & Kemenhut 2026
#   -> melanggar indikator "kehilangan tutupan" dan benar-benar deforestasi (berisiko).
# - Sutrisno: kehilangan tutupan 2023 di lahan yang BUKAN hutan pada 2020 (blok peremajaan) -> indikator
#   kehilangan tutupan menyala, tetapi bukan deforestasi (aman).
# - Rina: di dalam Hutan Produksi menurut peta KLHK 2017 (GFW) dan peta Kemenhut Juni 2026 -> berisiko legalitas.
# - Darmawan: hutan menurut JRC 2020, tanpa kehilangan tutupan -> bukti belum cukup (perlu cek lapangan).
# - Hasan: peta JRC menyebut hutan (95%) yang hilang 2021-2022, tetapi peta hutan alam SBTN menyebut 0% hutan alam
#   (dicek 14 Nov 2026). Dengan satu peta kebun ini langsung Berisiko; dengan dua peta -> perlu cek lapangan.
HERO = [
    # nama, desa, (dx_m, dy_m), (w, h), skenario, tahun tanam diklaim, saksi
    ("Budi Santoso", "Sungai Harapan", (-420, 160), (165, 128), "sawit_tua_stabil", 2008, "Ketua Poktan Sri Rejeki"),
    ("Siti Aminah", "Sungai Harapan", (-235, 165), (120, 132), "dibuka_2019", 2019, "Ketua Poktan Sri Rejeki"),
    ("Sutrisno Wibowo", "Sungai Harapan", (-3384, -757), (189, 167), "peremajaan_2023", 2023, "Ketua Poktan Sri Rejeki"),
    ("Joko Susilo", "Sungai Harapan", (-4041, 7637), (178, 134), "hutan_dibuka_2025", 2015, None),
    ("Rina Wati", "Sungai Harapan", (830, 406), (150, 126), "kawasan_hutan", 2014, "Kepala Dusun"),  # di Hutan Produksi
    ("Darmawan Lubis", "Sungai Harapan", (-4197, 7870), (156, 134), "data_kurang", 2012, "Ketua Poktan Sri Rejeki"),
    ("Wahyuni Harahap", "Sungai Harapan", (-240, -40), (118, 120), "sawit_tua_stabil", 2010, "Ketua Poktan Sri Rejeki"),
    ("Agus Pratama", "Sungai Harapan", (-90, -45), (160, 138), "sawit_tua_stabil", 2006, "Ketua Poktan Sri Rejeki"),
    ("Sri Rahayu", "Sungai Harapan", (-420, -215), (110, 100), "sawit_tua_stabil", 2013, "Ketua Poktan Sri Rejeki"),
    ("Hasan Siregar", "Sungai Harapan", (-2850, 7560), (120, 120), "peremajaan_2021", 2021, "Ketua Poktan Sri Rejeki"),
]

VILLAGES = [
    ("Bukit Makmur", (-1500, -900)),
    ("Lubuk Sejahtera", (-2300, 700)),
    ("Sungai Harapan", (-900, 900)),
]

COLLECTORS = [
    ("UD Tani Jaya", "Sungai Harapan", "bersih"),
    ("CV Sawit Bersama", "Bukit Makmur", "bersih"),
    ("UD Sinar Jaya", "Sungai Harapan", "mencuci"),
    ("UD Berkah Tani", "Lubuk Sejahtera", "bersih"),
    ("UD Maju Bersama", "Bukit Makmur", "bersih"),
    ("UD Rezeki Sawit", "Lubuk Sejahtera", "longgar"),
    ("CV Agro Lestari", "Sungai Harapan", "bersih"),
    ("UD Harapan Baru", "Lubuk Sejahtera", "bersih"),
]


def _offset(lat0: float, lng0: float, dx: float, dy: float) -> tuple[float, float]:
    return lat0 + FLIP_Y * dy / M_PER_DEG, lng0 + FLIP_X * dx / (M_PER_DEG * math.cos(math.radians(lat0)))


def _quad(lat0: float, lng0: float, dx: float, dy: float, w: float, h: float, rng: np.random.Generator) -> dict:
    j = lambda: float(rng.uniform(-7, 7))  # noqa: E731 - sudut tidak siku sempurna, seperti kebun asli
    corners = [(dx + j(), dy + j()), (dx + w + j(), dy + j()), (dx + w + j(), dy - h + j()), (dx + j(), dy - h + j())]
    ring = []
    for cx, cy in corners:
        la, ln = _offset(lat0, lng0, cx, cy)
        ring.append([round(ln, 7), round(la, 7)])
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _legacy_scenario(roll: float) -> str:
    """Cadangan bila tabel lapisan peta bawaan tidak ada (mis. lokasi demo diubah)."""
    return ("dibuka_2019" if roll < 0.08 else "peremajaan_2023" if roll < 0.14 else "data_kurang" if roll < 0.18
            else "sawit_tua_stabil")


def _real_scenario(geom: dict) -> str | None:
    real = peta_gfw.bundled(geom)
    if not real:
        return None
    kw = kawasan_svc.lookup(geom, "lokal")
    return demo_sim.scenario_from_layers(real, kw.pct)


def _write_kawasan() -> None:
    """Salin potongan peta kawasan resmi untuk area demo; hapus batas ilustrasi versi lama."""
    folder = DATA_DIR / "kawasan"
    folder.mkdir(parents=True, exist_ok=True)
    old = folder / "kawasan_demo.geojson"
    if old.exists():
        try:
            if all((f.get("properties") or {}).get("is_demo") for f in json.loads(old.read_text(encoding="utf-8"))["features"]):
                old.unlink()
        except (OSError, ValueError, KeyError):
            pass
    dst = folder / KAWASAN_FILE.name
    if not dst.exists() or dst.read_bytes() != KAWASAN_FILE.read_bytes():
        dst.write_bytes(KAWASAN_FILE.read_bytes())
    kawasan_svc.clear_caches()


def seed(reset: bool = False) -> dict:
    if reset:
        Base.metadata.drop_all(engine)
    init_db()
    _write_kawasan()
    rng = np.random.default_rng(42)
    now = datetime.now().replace(second=0, microsecond=0)

    with SessionLocal() as db:
        if db.scalar(select(Plot.id).limit(1)) is not None:
            return {"plots": 0, "skipped": True}
        coop = Cooperative(name="KUD Tani Makmur (demo)", village="Sungai Harapan", district="sekitar TN Tesso Nilo, Riau")
        mill = Mill(name="PKS Sejahtera (demo)", lat=CENTER[0] + 0.006, lng=CENTER[1] + 0.032)
        db.add_all([coop, mill])
        db.flush()

        farmers: dict[str, Farmer] = {}

        def farmer(name: str, village: str) -> Farmer:
            if name not in farmers:
                f = Farmer(name=name, village=village, cooperative_id=coop.id, consent_given=True,
                           consent_at=now - timedelta(days=int(rng.integers(30, 200))))
                db.add(f)
                db.flush()
                farmers[name] = f
            return farmers[name]

        plots: list[Plot] = []

        def add_plot(name, village, geom, scenario, declared, witness, method):
            f = farmer(name, village)
            n = len(plots) + 1
            created = now - timedelta(days=int(rng.integers(20, 160)))
            p = Plot(code=plot_svc.make_code(n), farmer_id=f.id, label=f"Kebun blok {'ABCDEFG'[int(rng.integers(0, 7))]}", geometry=geom, area_ha=0,
                     centroid_lat=0, centroid_lng=0, planting_year_declared=declared, witness=witness,
                     boundary_confirmed=witness is not None, delineation_method=method, scenario=scenario,
                     created_at=created)
            plot_svc.set_geometry(p, geom)
            wits = [{"name": witness, "relation": "ketua kelompok tani" if "Poktan" in witness else "saksi",
                     "at": created.isoformat(timespec="seconds")}] if witness else []
            if name in HERO_LAND:
                proof, ref, stdb, second = HERO_LAND[name]
                if second and witness:
                    wits.append({"name": second.split(" (")[0], "relation": second.split("(")[1].rstrip(")"),
                                 "at": created.isoformat(timespec="seconds")})
                p.land_proof, p.land_proof_ref, p.stdb_status = proof, ref, stdb
                p.boundary_sides = SIDES_DEMO[0] if name == "Budi Santoso" else SIDES_DEMO[n % 2]
            else:
                roll = rng.random()
                p.land_proof = "sertifikat" if roll < 0.25 else "surat_desa" if roll < 0.72 else "pernyataan" if roll < 0.88 else None
                p.stdb_status = ["ada", "proses", "belum"][int(rng.choice(3, p=[0.42, 0.36, 0.22]))]
                if p.land_proof == "pernyataan" and witness and rng.random() < 0.6:
                    wits.append({"name": f"{FIRST[int(rng.integers(len(FIRST)))]} (tetangga)", "relation": "tetangga",
                                 "at": created.isoformat(timespec="seconds")})
                if rng.random() < 0.03:
                    p.dispute, p.dispute_note = True, "Batas selatan masih diperdebatkan dengan tetangga"
                p.boundary_sides = SIDES_DEMO[n % 2] if rng.random() < 0.7 else None
            p.witnesses = wits
            if method == "ai_watershed" or rng.random() < 0.5:
                p.gps_lat, p.gps_lng, p.gps_accuracy_m = p.centroid_lat, p.centroid_lng, float(round(rng.uniform(4, 12), 1))
            db.add(p)
            db.flush()
            plots.append(p)
            return p

        for name, village, (dx, dy), (w, h), sc, year, wit in HERO:
            add_plot(name, village, _quad(CENTER[0], CENTER[1], dx, dy, w, h, rng), sc, year, wit,
                     "ai_watershed" if rng.random() < 0.7 else "manual")

        used_names = {h[0] for h in HERO}
        for village, (vx, vy) in VILLAGES:
            cols, rows = 5, 4 if village != "Sungai Harapan" else 3
            for r in range(rows):
                for c in range(cols):
                    if village == "Sungai Harapan" and r == 0 and c < 2:
                        continue
                    while True:
                        nm = f"{FIRST[int(rng.integers(len(FIRST)))]} {LAST[int(rng.integers(len(LAST)))]}"
                        if nm not in used_names:
                            used_names.add(nm)
                            break
                    w, h = float(rng.uniform(95, 190)), float(rng.uniform(90, 170))
                    dx, dy = vx + c * 215, vy - r * 200
                    roll, y_old, y_mid = rng.random(), int(rng.integers(1998, 2016)), int(rng.integers(2005, 2015))
                    geom = _quad(CENTER[0], CENTER[1], dx, dy, w, h, rng)
                    # skenario NDVI mengikuti peta nyata di lokasi kebun (bukan diacak), agar peta = hasil analisis
                    sc = _real_scenario(geom) or _legacy_scenario(roll)
                    kind, yr = demo_sim.parse(sc)
                    year = yr if kind in ("peremajaan", "dibuka") else y_old if sc == "sawit_tua_stabil" else y_mid
                    add_plot(nm, village, geom, sc,
                             year if rng.random() < 0.85 else None, "Ketua Poktan" if rng.random() < 0.9 else None,
                             "ai_watershed" if rng.random() < 0.6 else "manual")

        for p in plots:
            # kebun contoh: kawasan dicek ke salinan lokal peta KLHK 2017 agar demo sama walau tanpa internet
            # lapisan peta nyata dari tabel bawaan (hasil hitungan tile GFW), juga agar sama tanpa internet
            plot_svc.apply_analysis(db, p, force_demo=True, kawasan_policy="lokal", peta_policy="bundel")
            # analisis lama dibuat seolah-olah dijalankan saat kebun didaftarkan
            p.analyses[0].created_at = p.created_at + timedelta(minutes=3)
            p.analyzed_at = p.created_at + timedelta(minutes=3)
        for p in sorted(plots, key=lambda q: q.created_at):
            audit.log(db, "Rahmat Hidayat", "koperasi", "kebun_didaftarkan", "kebun", p.id,
                      f"Kebun {p.code} didaftarkan ({p.area_ha:.2f} ha, {len(p.witnesses or [])} saksi)",
                      {"area_ha": round(p.area_ha, 3), "method": p.delineation_method, "land_proof": p.land_proof},
                      at=p.created_at)
            audit.log(db, "Rahmat Hidayat", "koperasi", "cek_satelit", "kebun", p.id, f"Cek satelit: {p.risk_headline}",
                      {"risk": p.risk_level, "source": "simulasi"}, at=p.analyzed_at)

        collectors = []
        for i, (nm, village, _) in enumerate(COLLECTORS):
            vx, vy = dict(VILLAGES)[village]
            la, ln = _offset(CENTER[0], CENTER[1], vx - 150, vy + 120 + i * 30)
            c = Collector(name=nm, village=village, lat=la, lng=ln)
            db.add(c)
            collectors.append(c)
        db.flush()
        behaviour = {c.id: COLLECTORS[i][2] for i, c in enumerate(collectors)}
        by_village = {v: [c for c in collectors if c.village == v] for v, _ in VILLAGES}

        # ---------- transaksi 180 hari ----------
        events: list[tuple[datetime, Plot, int, float, str]] = []
        start = now - timedelta(days=180)
        for p in plots:
            vill = p.farmer.village
            primary = by_village[vill][0] if p.id % 3 else by_village[vill][-1]
            if p.code == plot_svc.make_code(1):
                primary = collectors[0]  # Pak Budi selalu jual ke UD Tani Jaya
            if p.id in (7, 9) or (p.id > 10 and p.id % 11 == 0):
                primary = collectors[2]  # pemasok UD Sinar Jaya
            age = (now.year - (plot_svc.effective_planting_year(p) or 2008))
            pot = potential_t_per_ha_year(age if age >= 0 else None)
            t = start + timedelta(days=float(rng.uniform(0, 12)))
            if p.code == plot_svc.make_code(1):
                # Pak Budi (kebun utama demo): panen teratur tiap 13 hari, terakhir 11 hari lalu
                t = now - timedelta(days=11 + 13 * 13)
            while t < now - timedelta(hours=6):
                month_kg = p.area_ha * pot * TYPICAL_SMALLHOLDER_FACTOR / 12 * 1000 * SEASONAL[t.month]
                kg = month_kg / 2.5 * float(rng.uniform(0.82, 1.15))
                if p.code == plot_svc.make_code(1):
                    kg = float(rng.uniform(1020, 1160))
                when = t.replace(hour=int(rng.integers(7, 16)), minute=int(rng.integers(0, 59)))
                cid = primary.id if rng.random() < 0.9 else by_village[vill][int(rng.integers(len(by_village[vill])))].id
                if p.risk_level == "tinggi" and rng.random() < 0.6:
                    t += timedelta(days=float(rng.uniform(10, 15)))
                    continue  # kebun berisiko lebih sering tidak menjual ke jalur terdaftar
                if p.code == plot_svc.make_code(1):
                    cid = primary.id
                if kg > 30:
                    events.append((when, p, cid, round(kg / 5) * 5, "normal"))
                t += timedelta(days=13.0 if p.code == plot_svc.make_code(1) else float(rng.uniform(10, 15)))

        # UD Sinar Jaya "mencuci" TBS dari luar memakai paspor pemasoknya
        sinar = collectors[2]
        own = [p for p in plots if p.id in (7, 9) or (p.id > 10 and p.id % 11 == 0)]
        t = start + timedelta(days=4)
        while t < now - timedelta(days=1):
            p = own[int(rng.integers(len(own)))]
            events.append((t.replace(hour=int(rng.integers(8, 17))), p, sinar.id, float(round(rng.uniform(1400, 3200) / 5) * 5), "cuci"))
            t += timedelta(days=float(rng.uniform(3, 6)))
        # UD Rezeki Sawit longgar: membeli dari kebun berisiko
        rezeki = collectors[5]
        risky = [p for p in plots if p.risk_level in ("tinggi", "perlu_cek")]
        for k in range(9):
            p = risky[k % len(risky)]
            when = (start + timedelta(days=float(rng.uniform(5, 175)))).replace(hour=10)
            events.append((when, p, rezeki.id, float(round(rng.uniform(600, 1500) / 5) * 5), "longgar"))

        events.sort(key=lambda e: e[0])
        for when, p, cid, kg, _ in events:
            supply_svc.record(db, p, cid, kg, when)

        # ---------- setoran ke pabrik (per 3 hari) ----------
        txns = db.scalars(select(Transaction)).all()
        for c in collectors:
            day = start
            while day < now:
                nxt = day + timedelta(days=3)
                traced = sum(t.weight_kg for t in txns if t.collector_id == c.id and day <= t.created_at < nxt and t.decision != "ditahan")
                extra_rate = {"bersih": 0.06, "mencuci": 0.55, "longgar": 0.25}[behaviour[c.id]]
                held = sum(t.weight_kg for t in txns if t.collector_id == c.id and day <= t.created_at < nxt and t.decision == "ditahan")
                total = traced * (1 + extra_rate * float(rng.uniform(0.6, 1.4)))
                if behaviour[c.id] != "bersih":
                    total += held  # TBS yang ditahan tetap dijual ke pabrik (tak tertelusur)
                if total > 0:
                    db.add(Delivery(collector_id=c.id, mill_id=mill.id, weight_kg=round(total),
                                    created_at=(nxt - timedelta(hours=8))))
                day = nxt
        _seed_verification(db, plots, now, rng)
        db.commit()
        summary = {
            "plots": len(plots), "farmers": len(farmers), "collectors": len(collectors),
            "transactions": db.query(Transaction).count(), "deliveries": db.query(Delivery).count(),
        }
    ensure_demo_users()
    return summary


def _seed_verification(db, plots: list[Plot], now: datetime, rng: np.random.Generator) -> None:
    """Riwayat verifikasi demo: satu putaran inspeksi selesai (Okt) dan putaran berjalan (Nov) + satu keberatan."""
    by_name = {p.farmer.name: p for p in plots[:10]}
    done_at = now - timedelta(days=24)
    done = [by_name[n] for n in ("Budi Santoso", "Agus Pratama", "Sri Rahayu", "Sutrisno Wibowo")]
    extra = [p for p in plots[10:] if p.risk_level == "rendah"][:6]
    for k, p in enumerate(done + extra):
        bad = k == len(done) + 2  # satu kebun tidak sesuai di lapangan
        i = Inspection(plot_id=p.id, batch="2026-10", reason="belum_pernah" if k < len(done) else "acak",
                       status="selesai", result="tidak_sesuai" if bad else "sesuai", inspector="Andi Saputra",
                       notes=("Batas timur di lapangan sekitar 20 m lebih sempit dari peta; sebagian kebun tetangga ikut "
                              "tergambar. Perlu digambar ulang.") if bad else "Batas, umur tanaman, dan patok sesuai peta.",
                       photo_lat=p.centroid_lat, photo_lng=p.centroid_lng, photo_distance_m=0.0,
                       created_at=done_at - timedelta(days=10), done_at=done_at + timedelta(hours=k))
        db.add(i)
        p.verified_at, p.verified_result, p.verified_by = i.done_at, i.result, "Andi Saputra"
        audit.log(db, "Andi Saputra", "verifikator", "inspeksi_selesai", "kebun", p.id,
                  f"Inspeksi lapangan {p.code}: {'TIDAK sesuai' if bad else 'sesuai'}", {"batch": "2026-10"}, at=i.done_at)
    pending = [by_name[n] for n in ("Joko Susilo", "Rina Wati", "Darmawan Lubis", "Hasan Siregar")]
    pending += [p for p in plots[10:] if p.risk_level in ("tinggi", "perlu_cek")][:4]
    for p in pending:
        reason = verification_svc.reason_for(p)
        db.add(Inspection(plot_id=p.id, batch="2026-11", reason=reason, status="menunggu", created_at=now - timedelta(days=3)))
    audit.log(db, "Andi Saputra", "verifikator", "sampel_inspeksi", "inspeksi", None,
              f"Sampel inspeksi 2026-11: {len(pending)} kebun dipilih berbasis risiko", None, at=now - timedelta(days=3))
    joko = by_name["Joko Susilo"]
    db.add(Appeal(plot_id=joko.id, submitted_by="Rahmat Hidayat", evidence_type="foto_lapangan",
                  original_risk=joko.risk_level, created_at=now - timedelta(days=2),
                  reason=("Menurut petani, lahan ini kebun karet tua sejak 2012, bukan hutan. Pertengahan 2025 karet ditebang lalu "
                          "ditanami sawit. Ada foto tunggul karet dan kesaksian kepala dusun.")))
    audit.log(db, "Rahmat Hidayat", "koperasi", "keberatan_diajukan", "kebun", joko.id,
              f"Keberatan atas status {joko.code} (Foto lapangan / kesaksian)", None, at=now - timedelta(days=2))
    db.flush()


def ensure_demo_users() -> int:
    """Membuat akun demo bila belum ada (idempoten). Kata sandi dari PK_DEMO_PASSWORD."""
    if not DEMO_ACCOUNTS:
        return 0
    made = 0
    with SessionLocal() as db:
        cols = {c.name: c.id for c in db.scalars(select(Collector))}
        for username, name, role, org, col in DEMO_USERS:
            if db.scalar(select(User).where(User.username == username)):
                continue
            db.add(User(username=username, display_name=name, role=role, organisation=org, is_demo=True,
                        collector_id=cols.get(col) if col else None, password_hash=hash_password(DEMO_PASSWORD)))
            made += 1
        db.commit()
    return made


if __name__ == "__main__":
    print(seed(reset=True))
