"""Format angka & tanggal gaya Indonesia untuk teks yang dibaca pengguna."""
from __future__ import annotations

BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]


def dec(v: float, n: int = 1) -> str:
    return f"{v:,.{n}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def ton(kg: float) -> str:
    return f"{dec(kg / 1000)} t"


def bulan(iso: str) -> str:
    """'2022-07-14' -> 'Juli 2022'."""
    y, m = iso[:4], int(iso[5:7])
    return f"{BULAN[m - 1]} {y}"
