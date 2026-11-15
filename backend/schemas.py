"""Esquemas Pydantic del contrato API (Telemetría NASA, Auth, Campos y Campañas)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Telemetría NASA (CONTEXT.md §5)
# ---------------------------------------------------------------------------

RiesgoTermico = Literal["bajo", "medio", "alto", "critico"]


class TelemetriaNasa(BaseModel):
    """Bloque ``telemetria_nasa`` de la respuesta de ``POST /api/v1/simulate`` (dato satelital real)."""

    fecha_ultimo_dato_valido: date
    indice_humedad_radicular_pct: float
    indice_humedad_superficial_pct: float
    tendencia_humedad_15d_pct: float
    anomalia_lluvia_90d_pct: float
    frecuencia_tormentas_extremas_90d: int
    riesgo_termico_verano: RiesgoTermico


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


PAMPEAN_PROVINCE_IDS = (
    "buenos_aires",
    "cordoba",
    "santa_fe",
    "entre_rios",
    "la_pampa",
)


class UserProfileResponse(BaseModel):
    id: UUID
    email: EmailStr | None = None
    nombre: str | None = None
    # None = el usuario aún no completó el filtro inicial de provincias.
    provincias: list[str] | None = None
    created_at: datetime | None = None


class ProfileProvincesUpdate(BaseModel):
    """Body de ``PATCH /api/v1/auth/me/provinces`` (Región Pampeana habilitada)."""

    provincias: list[str]

    @field_validator("provincias")
    @classmethod
    def check_provincias(cls, value: list[str]) -> list[str]:
        unique = list(dict.fromkeys(value))  # deduplica preservando orden
        if not unique:
            raise ValueError("Debe seleccionar al menos una provincia.")
        invalid = [p for p in unique if p not in PAMPEAN_PROVINCE_IDS]
        if invalid:
            raise ValueError(
                "Provincias no habilitadas: "
                + ", ".join(invalid)
                + ". Habilitadas: "
                + ", ".join(PAMPEAN_PROVINCE_IDS)
                + "."
            )
        return unique


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
