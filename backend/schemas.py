"""Esquemas Pydantic de request y response para Auth, Campos y Campañas."""

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Auth & Perfil
# ---------------------------------------------------------------------------

class AuthRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    nombre: str = Field(default="", max_length=120)


class AuthLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserProfileResponse(BaseModel):
    id: UUID
    email: EmailStr | None = None
    nombre: str | None = None
    created_at: datetime | None = None


class AuthResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserProfileResponse
    requiere_confirmacion_email: bool = False


# ---------------------------------------------------------------------------
# Campos / Lotes
# ---------------------------------------------------------------------------

def _validate_polygon_coords(
    value: list[list[float]] | None,
) -> list[list[float]] | None:
    if value is None:
        return None
    if len(value) < 3:
        raise ValueError("El polígono debe tener al menos 3 vértices.")
    for point in value:
        if len(point) != 2:
            raise ValueError("Cada vértice del polígono debe ser [lat, lon].")
        lat, lon = point
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            raise ValueError("Coordenadas de vértice fuera de rango válido.")
    return value


class FieldCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    hectareas: float | None = Field(default=None, gt=0)
    polygon: list[list[float]] | None = None

    @field_validator("polygon")
    @classmethod
    def check_polygon(
        cls, value: list[list[float]] | None
    ) -> list[list[float]] | None:
        return _validate_polygon_coords(value)


class FieldUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    lat: float | None = Field(default=None, ge=-90.0, le=90.0)
    lon: float | None = Field(default=None, ge=-180.0, le=180.0)
    hectareas: float | None = Field(default=None, gt=0)
    polygon: list[list[float]] | None = None

    @field_validator("polygon")
    @classmethod
    def check_polygon(
        cls, value: list[list[float]] | None
    ) -> list[list[float]] | None:
        return _validate_polygon_coords(value)


class FieldResponse(BaseModel):
    id: UUID
    user_id: UUID
    nombre: str
    lat: float
    lon: float
    hectareas: float | None = None
    polygon: list[list[float]] | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Campañas e Historial de Cultivos
# ---------------------------------------------------------------------------

CampanaTipo = Literal["invierno", "verano"]


class CampaignCreate(BaseModel):
    campana: CampanaTipo
    cultivo: str = Field(min_length=1, max_length=80)
    fecha_inicio: date
    fecha_fin: date | None = None
    rinde_kg_ha: float | None = Field(default=None, ge=0)
    resultado_notas: str | None = Field(default=None, max_length=1000)
    simulacion_json: dict[str, Any] | None = None


class CampaignUpdate(BaseModel):
    campana: CampanaTipo | None = None
    cultivo: str | None = Field(default=None, min_length=1, max_length=80)
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    rinde_kg_ha: float | None = Field(default=None, ge=0)
    resultado_notas: str | None = Field(default=None, max_length=1000)
    simulacion_json: dict[str, Any] | None = None


class CampaignResponse(BaseModel):
    id: UUID
    field_id: UUID
    user_id: UUID
    campana: CampanaTipo
    cultivo: str
    fecha_inicio: date
    fecha_fin: date | None = None
    rinde_kg_ha: float | None = None
    resultado_notas: str | None = None
    simulacion_json: dict[str, Any] | None = None
    created_at: datetime
