"""Model database.

Prinsip privasi: kita TIDAK menyimpan NIK/KTP. Identitas cukup nama + desa, dan
data kebun hanya dibagikan ke pembeli yang dipilih petani (lihat `Farmer.consent_*`).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now()


class Cooperative(Base):
    __tablename__ = "cooperatives"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    village: Mapped[str] = mapped_column(String(120))
    district: Mapped[str] = mapped_column(String(120))


class Farmer(Base):
    __tablename__ = "farmers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    village: Mapped[str] = mapped_column(String(120))
    cooperative_id: Mapped[int | None] = mapped_column(ForeignKey("cooperatives.id"))
    # Persetujuan berbagi data (wajib sebelum paspor terbit).
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    plots: Mapped[list[Plot]] = relationship(back_populates="farmer")


class Plot(Base):
    __tablename__ = "plots"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id"))
    label: Mapped[str] = mapped_column(String(120), default="Kebun")
    geometry: Mapped[dict] = mapped_column(JSON)  # GeoJSON Polygon (lng, lat)
    area_ha: Mapped[float] = mapped_column(Float)
    centroid_lat: Mapped[float] = mapped_column(Float)
    centroid_lng: Mapped[float] = mapped_column(Float)
    planting_year_declared: Mapped[int | None] = mapped_column(Integer)
    planting_year_detected: Mapped[int | None] = mapped_column(Integer)
    delineation_method: Mapped[str] = mapped_column(String(32), default="manual")  # ai_sam|ai_watershed|manual
    witness: Mapped[str | None] = mapped_column(String(120))
    boundary_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_level: Mapped[str | None] = mapped_column(String(16))  # rendah|perlu_cek|tinggi
    risk_headline: Mapped[str | None] = mapped_column(String(240))
    scenario: Mapped[str | None] = mapped_column(String(48))  # hanya untuk mode demo
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # --- Pemetaan lapangan ---
    gps_lat: Mapped[float | None] = mapped_column(Float)  # titik GPS saat berdiri di kebun (cukup untuk EUDR < 4 ha)
    gps_lng: Mapped[float | None] = mapped_column(Float)
    gps_accuracy_m: Mapped[float | None] = mapped_column(Float)
    boundary_sides: Mapped[dict | None] = mapped_column(JSON)  # {"utara": {"jenis": "parit", "tetangga": "..."}, ...}
    witnesses: Mapped[list | None] = mapped_column(JSON)  # [{"name", "relation", "at"}]

    # --- Legalitas lahan (bukti penguasaan, bukan wajib sertifikat) ---
    land_proof: Mapped[str | None] = mapped_column(String(24))  # sertifikat|surat_desa|pernyataan
    land_proof_ref: Mapped[str | None] = mapped_column(String(64))
    stdb_status: Mapped[str | None] = mapped_column(String(16))  # ada|proses|belum
    stdb_number: Mapped[str | None] = mapped_column(String(64))
    dispute: Mapped[bool | None] = mapped_column(Boolean, default=False)
    dispute_note: Mapped[str | None] = mapped_column(String(240))

    # --- Ringkasan analisis terakhir (agar daftar & dasbor tidak memuat seluruh time series) ---
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime)
    analysis_rule: Mapped[str | None] = mapped_column(String(48))
    kawasan_pct: Mapped[float | None] = mapped_column(Float)
    kawasan_checked: Mapped[bool | None] = mapped_column(Boolean)
    kawasan_source: Mapped[str | None] = mapped_column(String(16))

    # --- Verifikasi lapangan & keputusan manusia ---
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_result: Mapped[str | None] = mapped_column(String(16))  # sesuai|tidak_sesuai
    verified_by: Mapped[str | None] = mapped_column(String(120))
    status_override: Mapped[dict | None] = mapped_column(JSON)  # keputusan keberatan

    farmer: Mapped[Farmer] = relationship(back_populates="plots")
    analyses: Mapped[list[Analysis]] = relationship(
        back_populates="plot", order_by="Analysis.created_at.desc()", cascade="all, delete-orphan"
    )


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    plot_id: Mapped[int] = mapped_column(ForeignKey("plots.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    risk_level: Mapped[str] = mapped_column(String(16))
    headline: Mapped[str] = mapped_column(String(240))
    confidence: Mapped[float] = mapped_column(Float)
    evidence: Mapped[dict] = mapped_column(JSON)
    timeseries: Mapped[dict] = mapped_column(JSON)
    data_source: Mapped[str] = mapped_column(String(32))
    compute_ms: Mapped[int] = mapped_column(Integer, default=0)
    model_version: Mapped[str] = mapped_column(String(32), default="cold-lite-1")

    plot: Mapped[Plot] = relationship(back_populates="analyses")


class Collector(Base):
    __tablename__ = "collectors"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    village: Mapped[str] = mapped_column(String(120))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)


class Mill(Base):
    __tablename__ = "mills"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)


class Transaction(Base):
    """Pembelian TBS oleh pengepul dari satu kebun (dicatat dengan scan QR paspor)."""

    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    plot_id: Mapped[int] = mapped_column(ForeignKey("plots.id"), index=True)
    collector_id: Mapped[int] = mapped_column(ForeignKey("collectors.id"), index=True)
    weight_kg: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    decision: Mapped[str] = mapped_column(String(16))  # diterima|catatan|ditahan
    flags: Mapped[list] = mapped_column(JSON, default=list)
    capacity_used_pct: Mapped[float] = mapped_column(Float, default=0.0)

    plot: Mapped[Plot] = relationship()
    collector: Mapped[Collector] = relationship()


class Delivery(Base):
    """Setoran pengepul ke pabrik (berat ditimbang di jembatan timbang pabrik)."""

    __tablename__ = "deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    collector_id: Mapped[int] = mapped_column(ForeignKey("collectors.id"), index=True)
    mill_id: Mapped[int] = mapped_column(ForeignKey("mills.id"))
    weight_kg: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    collector: Mapped[Collector] = relationship()


class User(Base):
    """Akun pengguna. Kata sandi disimpan sebagai hash PBKDF2-SHA256 (tidak pernah teks asli)."""

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16))  # koperasi|pengepul|pabrik|verifikator|admin
    password_hash: Mapped[str] = mapped_column(String(200))
    collector_id: Mapped[int | None] = mapped_column(ForeignKey("collectors.id"))
    organisation: Mapped[str | None] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AuditEvent(Base):
    """Riwayat perubahan berantai hash: setiap baris menyimpan hash baris sebelumnya,
    jadi mengubah atau menghapus satu baris di tengah langsung terdeteksi."""

    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    actor: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(48))
    entity: Mapped[str] = mapped_column(String(24), index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, index=True)
    summary: Mapped[str] = mapped_column(String(300))
    data: Mapped[dict | None] = mapped_column(JSON)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class Inspection(Base):
    """Inspeksi lapangan oleh verifikator untuk kebun yang terpilih sampel."""

    __tablename__ = "inspections"
    id: Mapped[int] = mapped_column(primary_key=True)
    plot_id: Mapped[int] = mapped_column(ForeignKey("plots.id"), index=True)
    batch: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(32))  # berisiko|perlu_cek|sengketa|bukti_lemah|belum_pernah|acak
    status: Mapped[str] = mapped_column(String(16), default="menunggu")  # menunggu|selesai
    result: Mapped[str | None] = mapped_column(String(16))  # sesuai|tidak_sesuai
    notes: Mapped[str | None] = mapped_column(Text)
    photo_path: Mapped[str | None] = mapped_column(String(200))
    photo_lat: Mapped[float | None] = mapped_column(Float)
    photo_lng: Mapped[float | None] = mapped_column(Float)
    photo_distance_m: Mapped[float | None] = mapped_column(Float)
    inspector: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    done_at: Mapped[datetime | None] = mapped_column(DateTime)

    plot: Mapped[Plot] = relationship()


class Appeal(Base):
    """Keberatan atas status kebun, diputuskan verifikator dengan alasan tertulis."""

    __tablename__ = "appeals"
    id: Mapped[int] = mapped_column(primary_key=True)
    plot_id: Mapped[int] = mapped_column(ForeignKey("plots.id"), index=True)
    submitted_by: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text)
    evidence_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="diajukan")  # diajukan|diterima|ditolak
    original_risk: Mapped[str | None] = mapped_column(String(16))
    new_risk: Mapped[str | None] = mapped_column(String(16))
    decision_note: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)

    plot: Mapped[Plot] = relationship()


class Shipment(Base):
    """Paket data uji tuntas untuk satu pengiriman ekspor (diserahkan ke importir Uni Eropa)."""

    __tablename__ = "shipments"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    buyer: Mapped[str] = mapped_column(String(160))
    destination: Mapped[str] = mapped_column(String(80))
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    summary: Mapped[dict] = mapped_column(JSON)
    plots: Mapped[list] = mapped_column(JSON)  # potret data tiap kebun saat paket dibuat
    excluded: Mapped[list] = mapped_column(JSON)
