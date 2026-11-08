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


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
