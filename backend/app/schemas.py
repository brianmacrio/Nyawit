from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class GeoPolygon(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[list[float]]]

    @field_validator("coordinates")
    @classmethod
    def _ring(cls, v):
        if not v or len(v[0]) < 4:
            raise ValueError("Poligon minimal 3 titik (ring tertutup)")
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


class PlotCreate(BaseModel):
    farmer_name: str = Field(min_length=2, max_length=120)
    village: str = Field(min_length=2, max_length=120)
    label: str = Field(default="Kebun", max_length=120)
    geometry: GeoPolygon
    planting_year_declared: int | None = Field(default=None, ge=1970, le=2030)
    witness: str | None = Field(default=None, max_length=120)
    consent: bool
    delineation_method: Literal["ai_sam", "ai_watershed", "manual"] = "manual"
    demo_scenario: str | None = None

    @field_validator("consent")
    @classmethod
    def _consent(cls, v):
        if not v:
            raise ValueError("Petani harus menyetujui pemakaian data kebun")
        return v


class PlotUpdate(BaseModel):
    geometry: GeoPolygon | None = None
    planting_year_declared: int | None = Field(default=None, ge=1970, le=2030)
    witness: str | None = None
    boundary_confirmed: bool | None = None
    label: str | None = None


class TransactionIn(BaseModel):
    plot_code: str
    collector_id: int
    weight_kg: float = Field(gt=0, le=40_000)
    created_at: datetime | None = None


class ApiMessage(BaseModel):
    detail: str
    extra: dict[str, Any] | None = None
