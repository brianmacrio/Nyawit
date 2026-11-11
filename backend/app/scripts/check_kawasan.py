"""Uji koneksi ke peta Kawasan Hutan Kemenhut dari laptop sendiri.

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
from ..services import kawasan

SAMPLES = [(-0.172, 101.893, "lokasi desa demo, Ukui, Pelalawan"), (-0.20, 101.75, "sekitar TN Tesso Nilo")]


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
        print(f"GAGAL terhubung ({time.perf_counter() - t0:.1f} s): {e}")
        print("Saran   :", _hint(str(e)))
        print("Aplikasi tetap jalan memakai cache dan peta lokal; status kawasan ditandai 'belum dicek'.")
        return 1
    print(f"Terhubung dalam {time.perf_counter() - t0:.1f} s. {len(info['layers'])} layer:")
    for l in info["layers"]:
        mark = "*" if l["id"] in info["selected"] else " "
        flds = ", ".join(f["name"] for f in l["fields"][:12])
        dom = f" | domain kode: {', '.join(l['domains'])}" if l.get("domains") else ""
        print(f" {mark} [{l['id']}] {l['name']} ({l.get('geometryType') or l.get('type')}) kolom: {flds}{dom}")
    print("   (* = dipakai otomatis; ubah dengan PK_KAWASAN_LAYERS=0,3)")

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
    print("\nSelesai. Hasil disimpan di backend/data/kawasan_cache agar demo tetap jalan saat offline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
