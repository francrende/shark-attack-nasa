"""Modelos Pydantic del contrato API (CONTEXT.md §5)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
# Request
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
    fuera_de_ventana_siembra: bool = False  # ML-7: la siembra de este cultivo ya terminó
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
