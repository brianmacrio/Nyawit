"""Membuat data demo yang realistis (nama, desa, dan transaksi FIKTIF).

Lokasi demo di sekitar Kec. Ukui, Pelalawan, Riau (dekat Taman Nasional Tesso Nilo),
wilayah dengan kasus TBS ilegal yang terdokumentasi. Batas "kawasan hutan" di sini
adalah ILUSTRASI untuk demo, bukan batas resmi. Untuk produksi, taruh GeoJSON resmi
(KLHK / WDPA) di backend/data/kawasan/.

Jalankan ulang:  python -m app.seed
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import select

from .config import DATA_DIR
from .db import Base, SessionLocal, engine, init_db
from .models import Collector, Cooperative, Delivery, Farmer, Mill, Plot, Transaction
from .services import kawasan as kawasan_svc
from .services import plots as plot_svc
from .services import supply as supply_svc
from .services.yield_model import SEASONAL, TYPICAL_SMALLHOLDER_FACTOR, potential_t_per_ha_year

CENTER = (-0.1720, 101.8930)  # (lat, lng)
M_PER_DEG = 111_320.0

KAWASAN = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "properties": {"name": "Kawasan konservasi (ILUSTRASI demo)", "status": "Taman Nasional - batas ilustratif",
                       "fungsi": "KSA_KPA", "is_demo": True},
        "geometry": {"type": "Polygon", "coordinates": [[
            [101.9046, -0.1580], [101.9330, -0.1545], [101.9420, -0.1820], [101.9280, -0.2030],
            [101.9046, -0.1990], [101.9046, -0.1580],
        ]]},
    }],
}

FIRST = ["Budi", "Siti", "Sutrisno", "Joko", "Rina", "Darmawan", "Wahyuni", "Agus", "Sri", "Hasan", "Rahmat", "Yanti",
         "Bambang", "Ernawati", "Slamet", "Fitri", "Taufik", "Murni", "Iwan", "Rohani", "Syahrul", "Desi", "Mulyadi",
         "Ratna", "Andi", "Nurhayati", "Herman", "Lina", "Yusuf", "Marlina", "Riduan", "Suryani"]
LAST = ["Santoso", "Aminah", "Wibowo", "Susilo", "Wati", "Lubis", "Harahap", "Pratama", "Rahayu", "Siregar", "Hidayat",
        "Nasution", "Saputra", "Simanjuntak", "Purba", "Hasibuan", "Tanjung", "Ginting", "Sitompul", "Rangkuti"]

HERO = [
    # nama, desa, (dx_m, dy_m), (w, h), skenario, tahun tanam diklaim, saksi
    ("Budi Santoso", "Sungai Harapan", (-420, 160), (165, 128), "sawit_tua_stabil", 2008, "Ketua Poktan Sri Rejeki"),
    ("Siti Aminah", "Sungai Harapan", (-235, 165), (120, 132), "dibuka_2019", 2019, "Ketua Poktan Sri Rejeki"),
    ("Sutrisno Wibowo", "Sungai Harapan", (-60, 150), (190, 168), "peremajaan_2023", 2023, "Ketua Poktan Sri Rejeki"),
    ("Joko Susilo", "Sungai Harapan", (205, 40), (175, 138), "hutan_dibuka_2022", 2015, None),
    ("Rina Wati", "Sungai Harapan", (1340, 40), (150, 126), "kawasan_hutan", 2014, "Kepala Dusun"),
    ("Darmawan Lubis", "Sungai Harapan", (-420, -40), (190, 148), "data_kurang", 2012, "Ketua Poktan Sri Rejeki"),
    ("Wahyuni Harahap", "Sungai Harapan", (-240, -40), (118, 120), "sawit_tua_stabil", 2010, "Ketua Poktan Sri Rejeki"),
    ("Agus Pratama", "Sungai Harapan", (-90, -45), (160, 138), "sawit_tua_stabil", 2006, "Ketua Poktan Sri Rejeki"),
    ("Sri Rahayu", "Sungai Harapan", (-420, -215), (110, 100), "sawit_tua_stabil", 2013, "Ketua Poktan Sri Rejeki"),
    ("Hasan Siregar", "Sungai Harapan", (-280, -230), (210, 172), "sawit_tua_stabil", 2004, "Ketua Poktan Sri Rejeki"),
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
    return lat0 + dy / M_PER_DEG, lng0 + dx / (M_PER_DEG * math.cos(math.radians(lat0)))


def _quad(lat0: float, lng0: float, dx: float, dy: float, w: float, h: float, rng: np.random.Generator) -> dict:
    j = lambda: float(rng.uniform(-7, 7))  # noqa: E731 - sudut tidak siku sempurna, seperti kebun asli
    corners = [(dx + j(), dy + j()), (dx + w + j(), dy + j()), (dx + w + j(), dy - h + j()), (dx + j(), dy - h + j())]
    ring = []
    for cx, cy in corners:
        la, ln = _offset(lat0, lng0, cx, cy)
        ring.append([round(ln, 7), round(la, 7)])
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _write_kawasan() -> None:
    folder = DATA_DIR / "kawasan"
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / "kawasan_demo.geojson"
    if not f.exists():
        f.write_text(json.dumps(KAWASAN, indent=2), encoding="utf-8")
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
        coop = Cooperative(name="KUD Tani Makmur (demo)", village="Sungai Harapan", district="Ukui, Pelalawan")
        mill = Mill(name="PKS Sejahtera (demo)", lat=CENTER[0] - 0.03, lng=CENTER[1] - 0.04)
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
            p = Plot(code=plot_svc.make_code(n), farmer_id=f.id, label=f"Kebun blok {'ABCDEFG'[int(rng.integers(0, 7))]}", geometry=geom, area_ha=0,
                     centroid_lat=0, centroid_lng=0, planting_year_declared=declared, witness=witness,
                     boundary_confirmed=witness is not None, delineation_method=method, scenario=scenario,
                     created_at=now - timedelta(days=int(rng.integers(20, 160))))
            plot_svc.set_geometry(p, geom)
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
                    sc = "sawit_tua_stabil"
                    roll = rng.random()
                    if roll < 0.08:
                        sc = "dibuka_2019"
                    elif roll < 0.14:
                        sc = "peremajaan_2023"
                    elif roll < 0.18:
                        sc = "data_kurang"
                    elif roll < 0.21:
                        sc = "hutan_dibuka_2022"
                    year = int(rng.integers(1998, 2016)) if sc == "sawit_tua_stabil" else (2019 if sc == "dibuka_2019" else 2023 if sc == "peremajaan_2023" else int(rng.integers(2005, 2015)))
                    add_plot(nm, village, _quad(CENTER[0], CENTER[1], dx, dy, w, h, rng), sc,
                             year if rng.random() < 0.85 else None, "Ketua Poktan" if rng.random() < 0.9 else None,
                             "ai_watershed" if rng.random() < 0.6 else "manual")

        for p in plots:
            # kebun contoh fiktif: kawasan dicek ke peta ilustrasi saja agar demo selalu sama
            plot_svc.apply_analysis(db, p, force_demo=True, kawasan_policy="lokal")
            # analisis lama dibuat seolah-olah dijalankan saat kebun didaftarkan
            p.analyses[0].created_at = p.created_at + timedelta(minutes=3)

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
        db.commit()
        summary = {
            "plots": len(plots), "farmers": len(farmers), "collectors": len(collectors),
            "transactions": db.query(Transaction).count(), "deliveries": db.query(Delivery).count(),
        }
    return summary


if __name__ == "__main__":
    print(seed(reset=True))
