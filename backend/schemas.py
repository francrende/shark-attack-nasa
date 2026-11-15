"""Esquemas Pydantic del contrato API (Auth, Campos, Campañas, Telemetría NASA y Simulación)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Telemetría NASA (CONTEXT.md §5)
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
    # Suelo propio del campo
    ph: float | None = None
    limo_pct: float | None = None
    arena_pct: float | None = None
    arcilla_pct: float | None = None
    textura_predominante: str | None = None
    carbono_organico_g_kg: float | None = None
    materia_organica_g_kg: float | None = None
    suelo_fuente: str | None = None
    suelo_advertencias: list[str] = Field(default_factory=list)
    suelo_localidad_fallback: str | None = None
    suelo_distancia_fuente_km: float | None = None
    reintentar_soilgrids: bool = True
    # Topografía propia del campo
    elevacion_m: float | None = None
    pendiente_terreno_pct: float | None = None
    fuente_elevacion: str | None = None
    topo_fuente: str | None = None
    topo_advertencias: list[str] = Field(default_factory=list)
    topo_localidad_fallback: str | None = None
    topo_distancia_fuente_km: float | None = None
    reintentar_srtm: bool = True
    # BACK-28: departamento MAGyP de referencia (ML-17); None fuera de cobertura o en campos viejos
    departamento_codigo: str | None = None
    departamento_nombre: str | None = None
    departamento_provincia: str | None = None
    departamento_distancia_km: float | None = None
    created_at: datetime
    # BACK-25: hay un reintento en segundo plano de ISRIC/SRTM para este campo. Mientras sea
    # true, el frontend consulta GET /fields/{id} cada 30 s para ver si llegó el dato real.
    reintento_en_curso: bool = False

    @field_validator("suelo_advertencias", "topo_advertencias", mode="before")
    @classmethod
    def _coerce_advertencias(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return [str(item) for item in value]

    @field_validator("reintentar_soilgrids", "reintentar_srtm", mode="before")
    @classmethod
    def _coerce_retry_flag(cls, value: Any) -> bool:
        if value is None:
            return True
        return bool(value)


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

    @model_validator(mode="after")
    def _cosecha_despues_de_siembra(self) -> "CampaignCreate":
        # BACK-30: fecha_inicio es la siembra y fecha_fin la cosecha (cierre de la campaña).
        if self.fecha_fin is not None and self.fecha_fin < self.fecha_inicio:
            raise ValueError("La fecha de cosecha no puede ser anterior a la de siembra.")
        return self


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
    # BACK-24: campo guardado. Con él, suelo y topografía salen de public.fields (si son reales)
    # y lo que falte se busca y se guarda. Requiere Bearer token. Sin él, todo sigue como §5.
    # BACK-28: el departamento guardado del campo define el rinde normal (ML-17).
    field_id: UUID | None = None

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


class RindeKgHaOut(BaseModel):
    """ML-17: rinde del departamento de referencia en kg/ha (redondeado a 50).

    En los cultivos que no anticipan diferencias, ``esperado`` es el rinde normal y el rango es
    el histórico del cultivo. Sin dato, los valores son ``None`` y ``motivo_sin_dato`` dice por qué.
    """

    esperado: float | None = None
    anio_malo: float | None = None
    anio_bueno: float | None = None
    normal: float | None = None
    motivo_sin_dato: str | None = None


class CamposDistribucionPredictiva(BaseModel):
    """ML-16: distribución predictiva con el error real del modelo (CONTEXT §4.8). Todo opcional."""

    prob_anio_malo: float | None = Field(
        default=None, ge=0, le=1,
        description="Probabilidad de rinde 15% o más bajo lo normal. None si el cultivo no anticipa diferencias.",
    )
    prob_anio_malo_tipica: float | None = Field(
        default=None, ge=0, le=1, description="Frecuencia habitual de años malos del cultivo."
    )
    anticipa_diferencias: bool | None = Field(
        default=None, description="Si el sistema anticipa diferencias entre años para este cultivo."
    )
    puntaje_anio_malo: float | None = Field(
        default=None, description="Puntaje en un año malo (cuantil 10 con el error real). No es el P10 del ensemble."
    )
    puntaje_anio_bueno: float | None = Field(
        default=None, description="Puntaje en un año bueno (cuantil 90 con el error real). No es el P90 del ensemble."
    )
    rinde_kg_ha: RindeKgHaOut | None = None


class DistribucionHidroclimatica(CamposDistribucionPredictiva):
    promedio: float
    p10: float = Field(description="P10 del clima de los años análogos (no el peor 10% de los rindes).")
    p90: float
    anios_desfavorables: int
    anios_evaluados: int
    umbral_desfavorable: float
    peor_escenario: PeorEscenario


class DepartamentoReferenciaOut(BaseModel):
    """ML-17: departamento MAGyP cuyo rinde normal se usa como referencia."""

    codigo: str
    nombre: str
    provincia: str
    distancia_km: float


class FaseEnsoOut(BaseModel):
    """Fase ENSO con la que se eligieron los años análogos (ML-12)."""

    fase: Literal["nina", "neutro", "nino"]
    oni: float
    anios_analogos_desde: int


class RecomendacionPrincipal(BaseModel):
    cultivo: str
    secuencia_sugerida: str
    score_final: float
    sub_scores: SubScores
    distribucion_hidroclimatica: DistribucionHidroclimatica | None = None
    rinde_kg_ha: RindeKgHaOut | None = None  # ML-17
    perfil_mercado: str
    factores_clave_ml: list[str]
    explicacion: str


class ItemRanking(CamposDistribucionPredictiva):
    cultivo: str
    score_final: float
    riesgo: NivelRiesgo
    # ML-16: aptitud frente al agua y el clima y aporte al suelo de cada cultivo (no solo del ganador)
    sub_scores: SubScores | None = None
    fuera_de_ventana_siembra: bool = False  # ML-7: la siembra de este cultivo ya terminó
    # ML-11: por qué hoy no se puede sembrar (lote ocupado por el antecesor o siembra terminada);
    # None si se puede. Los no sembrables van al final del ranking.
    motivo_no_sembrable: str | None = None
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
    departamento_referencia: DepartamentoReferenciaOut | None = None  # ML-17 (None fuera de cobertura)
    fase_enso: FaseEnsoOut | None = None
    advertencias: list[str] = Field(
        default_factory=list,
        description="Avisos de calidad de dato (fallbacks de SoilGrids/SRTM, propiedades faltantes).",
    )


# ---------------------------------------------------------------------------
# Telemetría Inmediata de Lote (GET /api/v1/telemetry — BACK-20)
# ---------------------------------------------------------------------------


class PerfilSueloTelemetriaOut(BaseModel):
    """Perfil edáfico 0-30 cm para lectura directa; preserva ``None`` ante fallback sin dato."""

    textura_predominante: str | None = None
    arcilla_pct: float | None = None
    arena_pct: float | None = None
    limo_pct: float | None = None
    carbono_organico_g_kg: float | None = None
    materia_organica_g_kg: float | None = None
    ph: float | None = None
    fuente: str
    localidad_fallback: str | None = None
    distancia_fuente_km: float
    reintentar_soilgrids: bool = False


class TopografiaTelemetriaOut(BaseModel):
    """Elevación y pendiente reales desde SRTM o respaldo regional."""

    elevacion_m: float
    pendiente_terreno_pct: float
    fuente: str
    fuente_elevacion: str | None = None
    localidad_fallback: str | None = None
    distancia_fuente_km: float
    reintentar_srtm: bool = False


class TelemetriaNasaInfoOut(BaseModel):
    """Bloque ``telemetria_nasa`` para ``GET /api/v1/telemetry`` (tolera métricas históricas ausentes)."""

    fecha_ultimo_dato_valido: date
    indice_humedad_radicular_pct: float
    indice_humedad_superficial_pct: float
    tendencia_humedad_15d_pct: float
    anomalia_lluvia_90d_pct: float | None = None
    frecuencia_tormentas_extremas_90d: int
    riesgo_termico_verano: RiesgoTermico | None = None


class TelemetryResponse(BaseModel):
    """Respuesta de ``GET /api/v1/telemetry`` para ``Info general`` al seleccionar un campo."""

    ubicacion: Ubicacion
    telemetria_nasa: TelemetriaNasaInfoOut | None = None
    topografia_srtm: TopografiaTelemetriaOut | None = None
    perfil_suelo: PerfilSueloTelemetriaOut
    advertencias: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Seguimiento de campaña (GET /api/v1/fields/{field_id}/campaigns/{campaign_id}/seguimiento — BACK-29)
# ---------------------------------------------------------------------------

EtapaSeguimiento = Literal["previa", "en_curso", "terminado"]


class PuntoSeguimientoOut(BaseModel):
    """Un punto de la serie semanal (ML-18): lo que se esperaba con lo observado hasta ``fecha``."""

    fecha: date
    dias_observados: int
    avance: float = Field(ge=0, le=1, description="Fracción del período crítico ya observada.")
    promedio: float
    prob_anio_malo: float | None = Field(default=None, ge=0, le=1)
    puntaje_anio_malo: float | None = None
    puntaje_anio_bueno: float | None = None
    rinde_kg_ha: RindeKgHaOut | None = None


class ClimaObservadoOut(BaseModel):
    """Clima de los días ya observados del período crítico (sin topes del modelo)."""

    desde: date
    dias: int
    lluvia_mm: float
    lluvia_normal_mm: float | None = Field(
        default=None, description="Lluvia mediana de los años análogos en los mismos días."
    )
    dias_calor: int = Field(description="Días con más de 34 °C.")
    heladas: int = Field(description="Días con menos de 2 °C.")
    tormentas: int = Field(description="Días con más de 50 mm.")


class FaseEnsoSiembraOut(BaseModel):
    fase: Literal["nina", "neutro", "nino"]
    oni: float


class SeguimientoResponse(BaseModel):
    """Cómo viene una campaña ya sembrada (ML-18 / BACK-29)."""

    campana_id: UUID
    cultivo: str
    campana: Campana
    fecha_siembra: date
    etapa: EtapaSeguimiento
    inicio_periodo_critico: date
    fin_periodo_critico: date
    dias_observados: int
    dias_periodo_critico: int
    fecha_ultimo_dato: date
    serie: list[PuntoSeguimientoOut]
    observado: ClimaObservadoOut | None = None
    prob_anio_malo_tipica: float | None = Field(default=None, ge=0, le=1)
    anticipa_diferencias: bool | None = None
    rinde_normal_kg_ha: float | None = None
    fase_enso_siembra: FaseEnsoSiembraOut | None = None
    departamento_referencia: DepartamentoReferenciaOut | None = None
    anios_analogos: int
    rango_por_avance: bool = Field(
        description="True si el rango usa la distribución medida para este avance (se achica al avanzar)."
    )
    calculado_el: date
    advertencias: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Historial del lote por campaña (GET /api/v1/historial — BACK-31)
# ---------------------------------------------------------------------------


class RindeZonaOut(BaseModel):
    """Rinde MAGyP del departamento en una campaña, contra su rinde normal (tendencia)."""

    cultivo: str = Field(description="Cultivo MAGyP: trigo, cebada, maiz, soja_primera, soja_segunda, girasol, sorgo.")
    rinde_kg_ha: float
    normal_kg_ha: float | None = None
    vs_normal_pct: int | None = None


class CosechaLoteOut(BaseModel):
    """Campaña guardada del lote (``public.campaigns``)."""

    id: str
    cultivo: str
    fecha_siembra: date
    fecha_cosecha: date | None = None
    rinde_kg_ha: float | None = None
    en_curso: bool


class CampanaHistorialOut(BaseModel):
    anio: int = Field(description="Año de inicio de la campaña agrícola (julio a junio).")
    etiqueta: str = Field(description='Rótulo de la campaña, por ejemplo "2022/23".')
    completa: bool = Field(description="False para la campaña en curso o con meses sin dato.")
    meses_con_dato: int
    lluvia_mm: float | None = None
    lluvia_vs_normal_pct: int | None = Field(
        default=None, description="Desvío contra lo normal; en la campaña en curso, solo de los meses completos."
    )
    lluvia_comparada_hasta: str | None = Field(
        default=None, description='Campaña en curso: último mes completo comparado, "AAAA-MM".'
    )
    agua_raices_promedio_pct: int | None = None
    mes_mas_seco: str | None = Field(default=None, description='Mes con menos agua en raíces, "AAAA-MM".')
    agua_raices_mes_mas_seco_pct: int | None = None
    agua_raices_mes_mas_seco_normal_pct: int | None = None
    rinde_zona: list[RindeZonaOut] = Field(default_factory=list)
    cosechas_lote: list[CosechaLoteOut] = Field(default_factory=list)


class NormalesHistorialOut(BaseModel):
    lluvia_mm: float | None = None
    agua_raices_pct: int | None = None
    campanas_completas: int


class HistorialResponse(BaseModel):
    """Información histórica real del lote por campaña agrícola (BACK-31)."""

    ubicacion: Ubicacion
    departamento_referencia: DepartamentoReferenciaOut | None = None
    normales: NormalesHistorialOut
    campanas: list[CampanaHistorialOut]
    advertencias: list[str] = Field(default_factory=list)
