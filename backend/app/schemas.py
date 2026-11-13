from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class GeoPolygon(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[list[float]]]

    @field_validator("coordinates")
    @classmethod
    def _ring(cls, v):
        if not v or len(v[0]) < 4:
            raise ValueError("Poligon minimal 3 titik (ring tertutup)")
        if len(v) > 5 or sum(len(r) for r in v) > 2000:
            raise ValueError("Poligon terlalu rumit (maksimal 2.000 titik)")
        for lng, lat in (p[:2] for p in v[0]):
            if not (-180 <= lng <= 180 and -90 <= lat <= 90):
                raise ValueError("Koordinat di luar rentang")
        return v


class DelineateIn(BaseModel):
    lat: float = Field(ge=-60, le=60)
    lng: float = Field(ge=-180, le=180)
    zoom: int | None = Field(default=None, ge=15, le=19)


class OverlapIn(BaseModel):
    geometry: GeoPolygon
    exclude_plot_id: int | None = None


SideType = Literal["parit", "jalan", "kebun", "hutan", "sungai", "lainnya"]
LandProof = Literal["sertifikat", "surat_desa", "pernyataan"]
StdbStatus = Literal["ada", "proses", "belum"]


class SideIn(BaseModel):
    jenis: SideType
    tetangga: str | None = Field(default=None, max_length=120)


class WitnessIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    relation: str = Field(default="saksi", max_length=60)


class GpsIn(BaseModel):
    lat: float = Field(ge=-60, le=60)
    lng: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, le=5000)


class PlotCreate(BaseModel):
    farmer_name: str = Field(min_length=2, max_length=120)
    village: str = Field(min_length=2, max_length=120)
    label: str = Field(default="Kebun", max_length=120)
    geometry: GeoPolygon
    planting_year_declared: int | None = Field(default=None, ge=1970, le=2030)
    witness: str | None = Field(default=None, max_length=120)
    witnesses: list[WitnessIn] = Field(default_factory=list, max_length=6)
    boundary_sides: dict[Literal["utara", "timur", "selatan", "barat"], SideIn] = Field(default_factory=dict)
    gps: GpsIn | None = None
    land_proof: LandProof | None = None
    land_proof_ref: str | None = Field(default=None, max_length=64)
    stdb_status: StdbStatus = "belum"
    stdb_number: str | None = Field(default=None, max_length=64)
    dispute: bool = False
    dispute_note: str | None = Field(default=None, max_length=240)
    consent: bool
    delineation_method: Literal["ai_sam", "ai_watershed", "manual"] = "manual"
    demo_scenario: str | None = Field(default=None, max_length=48)

    @field_validator("consent")
    @classmethod
    def _consent(cls, v):
        if not v:
            raise ValueError("Petani harus menyetujui pemakaian data kebun")
        return v


class PlotUpdate(BaseModel):
    geometry: GeoPolygon | None = None
    planting_year_declared: int | None = Field(default=None, ge=1970, le=2030)
    witness: str | None = Field(default=None, max_length=120)
    boundary_confirmed: bool | None = None
    label: str | None = Field(default=None, max_length=120)
    boundary_sides: dict[Literal["utara", "timur", "selatan", "barat"], SideIn] | None = None
    land_proof: LandProof | None = None
    land_proof_ref: str | None = Field(default=None, max_length=64)
    stdb_status: StdbStatus | None = None
    stdb_number: str | None = Field(default=None, max_length=64)
    dispute: bool | None = None
    dispute_note: str | None = Field(default=None, max_length=240)


class LoginIn(BaseModel):
    username: str = Field(min_length=2, max_length=48)
    password: str = Field(min_length=1, max_length=128)


class DemoLoginIn(BaseModel):
    username: str = Field(min_length=2, max_length=48)


class InspectionResultIn(BaseModel):
    result: Literal["sesuai", "tidak_sesuai"]
    notes: str | None = Field(default=None, max_length=1000)
    photo: str | None = Field(default=None, max_length=6_000_000)  # data URL base64, <= 4 MB setelah decode
    lat: float | None = Field(default=None, ge=-60, le=60)
    lng: float | None = Field(default=None, ge=-180, le=180)


class SampleIn(BaseModel):
    batch: str | None = Field(default=None, max_length=32)


class AppealIn(BaseModel):
    plot_id: int
    reason: str = Field(min_length=10, max_length=1000)
    evidence_type: Literal["sk_pelepasan", "sertifikat", "surat_desa", "foto_lapangan", "lainnya"]


class AppealDecisionIn(BaseModel):
    accept: bool
    note: str = Field(min_length=10, max_length=1000)
    new_risk: Literal["rendah", "perlu_cek"] | None = None


class ShipmentIn(BaseModel):
    buyer: str = Field(min_length=3, max_length=160)
    destination: str = Field(default="Uni Eropa", max_length=80)
    period_start: date
    period_end: date

    @field_validator("period_end")
    @classmethod
    def _order(cls, v, info):
        start = info.data.get("period_start")
        if start and v < start:
            raise ValueError("Tanggal akhir harus setelah tanggal awal")
        if start and (v - start).days > 366:
            raise ValueError("Periode maksimal 1 tahun")
        return v


class TransactionIn(BaseModel):
    plot_code: str = Field(min_length=6, max_length=40)
    collector_id: int | None = None  # diisi otomatis dari akun pengepul
    weight_kg: float = Field(gt=0, le=40_000)
    created_at: datetime | None = None
