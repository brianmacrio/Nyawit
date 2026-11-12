"""Uji koneksi ke peta Kawasan Hutan Kemenhut dan cadangannya (KLHK 2017 lewat GFW) dari laptop sendiri.

    cd backend
    .venv\\Scripts\\python -m app.scripts.check_kawasan               (titik contoh di Riau)
    .venv\\Scripts\\python -m app.scripts.check_kawasan -0.20 101.75  (titik pilihan: lat lng)

Mencetak: status koneksi, daftar layer dan kolomnya, layer yang dipilih otomatis, atribut
poligon kawasan di sekitar titik, dan fungsi kawasan hasil bacaan aplikasi. Bila ada poligon
yang fungsinya "?", buat backend/data/kawasan/kode_fungsi.json sesuai petunjuk di akhir.
"""
from __future__ import annotations

import json
import sys
import time

from ..config import KAWASAN_URL
from ..services import kawasan, kawasan_gfw

SAMPLES = [
    (-0.3645, 102.0625, "desa demo, harus APL"),
    (-0.3676, 102.0544, "kebun demo Rina Wati, harus Hutan Produksi"),
    (-0.20, 101.80, "di dalam TN Tesso Nilo"),
]


def check_gfw(pts) -> int:
    print(f"\nCadangan: {kawasan_gfw.SOURCE_LABEL}")
    print(f"Tile    : {kawasan_gfw.URL}")
    ok = 0
    for lat, lng, label in pts:
        d = 0.0005
        t0 = time.perf_counter()
        try:
            feats, _ = kawasan_gfw.features_for((lng - d, lat - d, lng + d, lat + d))
        except kawasan_gfw.GfwError as e:
            print(f"  {label}: GAGAL ({e})\n  Saran: {_hint(str(e))}")
            continue
        from shapely.geometry import Point

        hit = [f for f in feats if f["geom"].contains(Point(lng, lat))]
        what = ", ".join(f"{kawasan.FUNGSI[f['fungsi']]['label']} ({f['name']})" for f in hit) or "tidak ada poligon"
        print(f"  {label}: {what}  [{time.perf_counter() - t0:.1f} s]")
        ok += 1
    return ok


def _hint(err: str) -> str:
    e = err.lower()
    if "certificate" in e or "ssl" in e:
        return "Masalah sertifikat HTTPS. Coba: .venv\\Scripts\\pip install truststore, lalu ulangi."
    if "timed out" in e or "timeout" in e:
        return "Layanan lambat/terblokir. Coba lagi, cek VPN/proxy kampus, atau naikkan PK_KAWASAN_TIMEOUT=20."
    if "403" in e or "forbidden" in e:
        return "Akses ditolak (firewall/proxy). Coba jaringan lain, mis. hotspot ponsel."
    if "getaddrinfo" in e or "name or service" in e or "nodename" in e:
        return "Nama server tidak ditemukan. Cek koneksi internet."
    return "Buka URL layanan di browser untuk memastikan layanan sedang aktif."


def main() -> int:
    pts = SAMPLES
    if len(sys.argv) >= 3:
        pts = [(float(sys.argv[1]), float(sys.argv[2]), "titik pilihan")]
    print(f"Layanan : {KAWASAN_URL}")
    t0 = time.perf_counter()
    try:
        info = kawasan.service_info(refresh=True)
    except Exception as e:  # noqa: BLE001
        print(f"GAGAL terhubung ke Kemenhut ({time.perf_counter() - t0:.1f} s): {e}")
        print("Saran   :", _hint(str(e)))
        if check_gfw(pts):
            print("\nAplikasi memakai cadangan KLHK 2017 (GFW) di atas sampai peta Kemenhut kembali aktif.")
            return 0
        print("Aplikasi tetap jalan memakai cache dan peta lokal; status kawasan ditandai 'belum dicek'.")
        return 1
    print(f"Terhubung dalam {time.perf_counter() - t0:.1f} s. {len(info['layers'])} layer:")
    for l in info["layers"]:
        mark = "*" if l["id"] in info["selected"] else " "
        flds = ", ".join(f["name"] for f in l["fields"][:12])
        dom = f" | domain kode: {', '.join(l['domains'])}" if l.get("domains") else ""
        print(f" {mark} [{l['id']}] {l['name']} ({l.get('geometryType') or l.get('type')}) kolom: {flds}{dom}")
    print("   (* = dipakai otomatis; ubah dengan PK_KAWASAN_LAYERS=0,3)")
    print(f"Kemampuan layanan: {info.get('capabilities') or '?'}")
    if info.get("render_only"):
        print("Layanan hanya mengizinkan tampilan peta -> status dibaca dari GAMBAR peta. Warna dari renderer layanan:")
        for l in info["layers"]:
            if l["id"] in info["selected"]:
                for p in l.get("palette") or []:
                    code = kawasan.classify({"fungsi_teks": p["label"]})
                    print(f"   RGB {tuple(p['rgb'])} = {p['label']} -> {code}")

    unknown_vals: dict[str, set] = {}
    for lat, lng, label in pts:
        i, j = int(lat // kawasan.CELL_DEG), int(lng // kawasan.CELL_DEG)
        print(f"\nTitik {lat}, {lng} ({label}), sel {i}_{j}:")
        try:
            t0 = time.perf_counter()
            data = kawasan.fetch_cell(i, j)
        except Exception as e:  # noqa: BLE001
            print(f"  gagal mengambil poligon: {e}\n  Saran: {_hint(str(e))}")
            continue
        print(f"  {len(data['features'])} poligon (metode {data['method']}, {time.perf_counter() - t0:.1f} s)")
        for f in data["features"][:8]:
            code = kawasan.classify(f["attrs"])
            print(f"  - layer {f['layer']} {f['layer_name']!r}: fungsi = {code} ({kawasan.FUNGSI[code]['label']})")
            print(f"    atribut: {json.dumps(f['attrs'], ensure_ascii=False)[:300]}")
            if code == "?":
                for k, v in f["attrs"].items():
                    unknown_vals.setdefault(k, set()).add(str(v))
        d = 0.00045  # kotak ~100 m tepat di titik
        sq = {"type": "Polygon", "coordinates": [[[lng - d, lat - d], [lng + d, lat - d], [lng + d, lat + d], [lng - d, lat + d], [lng - d, lat - d]]]}
        r = kawasan.lookup(sq, "online")
        parts = ", ".join(f"{p['pct']:.0f}% {p['label']}" for p in r.parts) or "tidak ada poligon kawasan"
        print(f"  Kotak 100 m di titik: {r.pct:.0f}% kawasan hutan -> {parts}")
        d = 0.0045  # kotak ~1 km di sekitar titik
        sq = {"type": "Polygon", "coordinates": [[[lng - d, lat - d], [lng + d, lat - d], [lng + d, lat + d], [lng - d, lat + d], [lng - d, lat - d]]]}
        r = kawasan.lookup(sq, "online")
        parts = ", ".join(f"{p['pct']:.0f}% {p['label']}" for p in r.parts) or "tidak ada poligon kawasan"
        print(f"  Kotak 1 km: {r.pct:.0f}% kawasan hutan -> {parts}")

    if unknown_vals:
        print("\nAda poligon yang fungsinya belum terbaca. Buat file backend/data/kawasan/kode_fungsi.json, contoh:")
        fld = next(iter(unknown_vals))
        sample = {v: "HL" for v in list(unknown_vals[fld])[:3]}
        print(json.dumps({fld: sample}, ensure_ascii=False, indent=2))
        print("Kode yang boleh dipakai: " + ", ".join(k for k in kawasan.FUNGSI if k != "?"))
    check_gfw(pts)
    print("\nSelesai. Hasil disimpan di backend/data/kawasan_cache agar demo tetap jalan saat offline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
