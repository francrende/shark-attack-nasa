"""Esquemas Pydantic de request y response para Auth, Campos, Campañas y Telemetría NASA."""
"""Esquemas Pydantic del contrato API (Telemetría NASA, Auth, Campos y Campañas)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


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


# ---------------------------------------------------------------------------
# Telemetría NASA (CONTEXT.md §5)
# Telemetría NASA y Simulación (CONTEXT.md §5)
# ---------------------------------------------------------------------------

RiesgoTermico = Literal["bajo", "medio", "alto", "critico"]
NivelRiesgo = Literal["bajo", "medio", "alto", "critico"]
Severidad = Literal["baja", "media", "alta"]
Campana = Literal["invierno", "verano"]
ObjetivoProductor = Literal["resiliencia_hidroclimatica", "conservacion_suelo", "equilibrio"]

# Espejo de services/rotation_matrix.ALL_CROPS + valores neutros (test de paridad en routers/test_simulate.py).
CULTIVOS_VALIDOS: tuple[str, ...] = (
    "trigo",
    "cebada",
    "vicia_cobertura",
    "avena_cobertura",
    "camelina",
    "maiz_temprano",
    "maiz_tardio",
    "soja_primera",
    "soja_segunda",
    "girasol",
    "sorgo",
)
CULTIVO_ANTERIOR_NEUTRO: tuple[str, ...] = ("ninguno", "barbecho", "sin_cultivo")


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


# ---------------------------------------------------------------------------
# Simulación / ML — Request (POST /api/v1/simulate)
# ---------------------------------------------------------------------------


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Coordenadas(_Estricto):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class SimulacionWhatIf(_Estricto):
    override_humedad_radicular_pct: float | None = Field(default=None, ge=0, le=100)
    variacion_lluvia_esperada_pct: float | None = Field(default=0, ge=-50, le=50)


class SimulateRequest(_Estricto):
    coordenadas: Coordenadas
    campana: Campana
    cultivo_anterior: str | None = None
    objetivo_productor: ObjetivoProductor = "equilibrio"
    simulacion_what_if: SimulacionWhatIf | None = None

    @field_validator("cultivo_anterior")
    @classmethod
    def _validar_cultivo_anterior(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalizado = v.strip().lower()
        if normalizado == "":
            return None
        if normalizado not in CULTIVOS_VALIDOS + CULTIVO_ANTERIOR_NEUTRO:
            opciones = ", ".join(CULTIVOS_VALIDOS + CULTIVO_ANTERIOR_NEUTRO)
            raise ValueError(f"Cultivo anterior desconocido: {v!r}. Opciones: {opciones}")
        return normalizado


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class Ubicacion(BaseModel):
    lat: float
    lon: float


class TopografiaSrtmOut(BaseModel):
    elevacion_m: float
    pendiente_terreno_pct: float
    riesgo_erosion_escorrentia: NivelRiesgo


class PerfilSueloOut(BaseModel):
    textura_predominante: str
    arcilla_pct: float
    carbono_organico_g_kg: float
    condicion_rotacion_previa: str


class AnomaliaDetectada(BaseModel):
    tipo: str
    severidad: Severidad
    evidencia: str


class SubScores(BaseModel):
    hidroclimatico: float
    suelo: float


class PeorEscenario(BaseModel):
    anio: int
    score: float
    frecuencia_tormentas_extremas: int
    frecuencia_estres_termico: int
    frecuencia_riesgo_helada: int


class DistribucionHidroclimatica(BaseModel):
    promedio: float
    p10: float
    p90: float
    anios_desfavorables: int
    anios_evaluados: int
    umbral_desfavorable: float
    peor_escenario: PeorEscenario


class RecomendacionPrincipal(BaseModel):
    cultivo: str
    secuencia_sugerida: str
    score_final: float
    sub_scores: SubScores
    distribucion_hidroclimatica: DistribucionHidroclimatica | None = None
    perfil_mercado: str
    factores_clave_ml: list[str]
    explicacion: str


class ItemRanking(BaseModel):
    cultivo: str
    score_final: float
    riesgo: NivelRiesgo
    score_hidroclimatico_p10: float | None = None
    anios_desfavorables: int | None = None
    anios_evaluados: int | None = None


class ValidacionLocal(BaseModel):
    nota_resolucion_satelital: str
    brechas_informacion: list[str]
    recomendacion_experto: str


class MesCobertura(BaseModel):
    mes: int
    nombre: str
    estado: str


class Cobertura12Meses(BaseModel):
    meses_suelo_desnudo: int
    calendario: list[MesCobertura]


class EstrategiaRotacion(BaseModel):
    estrategia_id: str
    titulo: str
    cultivo_evaluado: str
    secuencia_anual: str
    score_final: float
    s_hidroclimatico: float
    s_suelo: float
    riesgo_erosion_suelo: str
    meses_suelo_desnudo: int
    reduccion_suelo_desnudo_vs_testigo: int
    resumen_beneficios_riesgos: str


class SimulateResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"description": "Contrato de CONTEXT.md §5."})

    ubicacion: Ubicacion
    telemetria_nasa: TelemetriaNasa
    topografia_srtm: TopografiaSrtmOut
    perfil_suelo: PerfilSueloOut
    anomalias_detectadas: list[AnomaliaDetectada]
    recomendacion_principal: RecomendacionPrincipal
    ranking_cultivos: list[ItemRanking]
    validacion_local_requerida: ValidacionLocal
    cobertura_12_meses: Cobertura12Meses
    comparacion_estrategias: list[EstrategiaRotacion]
    advertencias: list[str] = Field(
        default_factory=list,
        description="Avisos de calidad de dato (fallbacks de SoilGrids/SRTM, propiedades faltantes).",
    )
