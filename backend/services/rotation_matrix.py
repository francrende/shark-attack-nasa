"""Matriz de Rotación Agronómica, Salud del Suelo (S_suelo) y Cobertura 12 Meses (ML-3).

Implementa el Pilar 2 del motor híbrido de Shark Attack:
- Evalúa la transición determinística ``cultivo_anterior -> cultivo_candidato``.
- Ajusta el puntaje según Carbono Orgánico del Suelo (``soc`` de ISRIC SoilGrids),
  pendiente topográfica (``pendiente_terreno_pct`` de NASA SRTM 30m), textura
  (``arcilla_pct`` de SoilGrids) y pH opcional.
- Calcula la línea de tiempo de cobertura de 12 meses (*bare-field periods*)
  distinguiendo cultivo candidato, antecesor, rastrojo protector y suelo desnudo.
- Expone el ``numeric_id`` (0..10) sincronizado 1:1 con ``ML-1`` (``generate_dataset.py``)
  y un comparador de estrategias de rotación para ``ML-4`` (``predictor.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Campaign = Literal["invierno", "verano"]
BotanicalFamily = Literal["graminea", "leguminosa", "oleaginosa", "crucifera"]
ResidueLevel = Literal["bajo", "medio", "alto"]
RiskLevel = Literal["bajo", "medio", "alto"]
MonthStatus = Literal[
    "cultivo_candidato",
    "cultivo_antecesor",
    "rastrojo_protector",
    "suelo_desnudo",
]

INVIERNO_CROPS: tuple[str, ...] = (
    "trigo",
    "cebada",
    "vicia_cobertura",
    "avena_cobertura",
    "camelina",
)

VERANO_CROPS: tuple[str, ...] = (
    "maiz_temprano",
    "maiz_tardio",
    "soja_primera",
    "soja_segunda",
    "girasol",
    "sorgo",
)

ALL_CROPS: tuple[str, ...] = INVIERNO_CROPS + VERANO_CROPS

NEUTRAL_PREVIOUS_VALUES: frozenset[str] = frozenset(
    {"", "ninguno", "barbecho", "sin_cultivo"}
)

MONTH_NAMES_ES: tuple[str, ...] = (
    "Ene",
    "Feb",
    "Mar",
    "Abr",
    "May",
    "Jun",
    "Jul",
    "Ago",
    "Sep",
    "Oct",
    "Nov",
    "Dic",
)

# Umbrales agronómicos de referencia (SoilGrids / SRTM)
SOC_LOW_THRESHOLD_G_KG = 15.0
SOC_MEDIUM_THRESHOLD_G_KG = 22.0
SLOPE_MODERATE_PCT = 1.0
SLOPE_HIGH_PCT = 2.0
CLAY_SANDY_MAX_PCT = 16.0
CLAY_HEAVY_MIN_PCT = 34.0
PH_LOW_THRESHOLD = 5.5
PH_HIGH_THRESHOLD = 8.0


@dataclass(frozen=True)
class CropProfile:
    """Metadatos agronómicos, codificación ML y perfil de mercado de un cultivo."""

    id: str
    numeric_id: int  # 0..10 sincronizado con CROP_CATALOG de ML-1 (generate_dataset.py)
    nombre_legible: str
    campana: Campaign
    familia: BotanicalFamily
    aporte_rastrojo: ResidueLevel
    carbon_balance: float  # [-1.0 extractor neto .. +1.0 gran aportador de C]
    fija_nitrogeno: bool
    es_cobertura: bool
    cobertura_inicial: ResidueLevel
    meses_activos: tuple[int, ...]
    meses_rastrojo: tuple[int, ...]
    cultivo_puente_ideal: str
    secuencia_sugerida: str
    perfil_mercado: str


@dataclass(frozen=True)
class MonthCoverage:
    """Estado de cobertura del suelo para un mes calendario (1..12)."""

    mes: int
    nombre: str
    estado: MonthStatus


@dataclass(frozen=True)
class SoilEvaluationResult:
    """Resultado completo de evaluación edáfica y de rotación para un cultivo candidato."""

    cultivo_candidato: str
    numeric_id: int
    cultivo_anterior: str | None
    campana: Campaign
    s_suelo: float
    puntaje_base_rotacion: float
    ajuste_carbono: float
    ajuste_pendiente: float
    ajuste_textura: float
    ajuste_ph: float
    riesgo_erosion_suelo: RiskLevel
    condicion_rotacion_previa: str
    secuencia_sugerida: str
    perfil_mercado: str
    meses_suelo_desnudo: int
    calendario_12m: tuple[MonthCoverage, ...]
    factores_suelo: tuple[str, ...]


@dataclass(frozen=True)
class RotationStrategyComparison:
    """Resumen comparativo de una estrategia de rotación anual (para ML-4 / Challenge)."""

    estrategia_id: str
    titulo: str
    cultivo_evaluado: str
    secuencia_anual: str
    s_suelo: float
    riesgo_erosion_suelo: RiskLevel
    meses_suelo_desnudo: int
    reduccion_suelo_desnudo_vs_testigo: int
    resumen_beneficios_riesgos: str


CROP_PROFILES: dict[str, CropProfile] = {
    # --- Campaña Fina (Invierno: IDs 0..4) ---
    "trigo": CropProfile(
        id="trigo",
        numeric_id=0,
        nombre_legible="Trigo",
        campana="invierno",
        familia="graminea",
        aporte_rastrojo="alto",
        carbon_balance=0.85,
        fija_nitrogeno=False,
        es_cobertura=False,
        cobertura_inicial="alto",
        meses_activos=(6, 7, 8, 9, 10, 11),
        meses_rastrojo=(12, 1, 2),
        cultivo_puente_ideal="soja_segunda",
        secuencia_sugerida="trigo (invierno) -> soja_segunda / maiz_tardio (verano)",
        perfil_mercado="Alta liquidez comercial y flujo de caja temprano; permite doble cultivo con soja de segunda.",
    ),
    "cebada": CropProfile(
        id="cebada",
        numeric_id=1,
        nombre_legible="Cebada",
        campana="invierno",
        familia="graminea",
        aporte_rastrojo="alto",
        carbon_balance=0.80,
        fija_nitrogeno=False,
        es_cobertura=False,
        cobertura_inicial="alto",
        meses_activos=(6, 7, 8, 9, 10),
        meses_rastrojo=(11, 12, 1),
        cultivo_puente_ideal="soja_segunda",
        secuencia_sugerida="cebada (invierno) -> soja_segunda (verano)",
        perfil_mercado="Cosecha más temprana que el trigo; buena demanda cervecera/forrajera y libera rápido el lote.",
    ),
    "vicia_cobertura": CropProfile(
        id="vicia_cobertura",
        numeric_id=2,
        nombre_legible="Vicia (Cultivo de Cobertura)",
        campana="invierno",
        familia="leguminosa",
        aporte_rastrojo="medio",
        carbon_balance=0.75,
        fija_nitrogeno=True,
        es_cobertura=True,
        cobertura_inicial="alto",
        meses_activos=(5, 6, 7, 8, 9, 10),
        meses_rastrojo=(11, 12),
        cultivo_puente_ideal="maiz_tardio",
        secuencia_sugerida="vicia_cobertura (invierno) -> maiz_tardio / sorgo (verano)",
        perfil_mercado="Inversión en servicio ecosistémico (no genera grano comercial): ahorra fertilizante nitrogenado al maíz o sorgo siguiente.",
    ),
    "avena_cobertura": CropProfile(
        id="avena_cobertura",
        numeric_id=3,
        nombre_legible="Avena (Cultivo de Cobertura)",
        campana="invierno",
        familia="graminea",
        aporte_rastrojo="alto",
        carbon_balance=0.95,
        fija_nitrogeno=False,
        es_cobertura=True,
        cobertura_inicial="alto",
        meses_activos=(4, 5, 6, 7, 8, 9, 10),
        meses_rastrojo=(11, 12, 1),
        cultivo_puente_ideal="soja_primera",
        secuencia_sugerida="avena_cobertura (invierno) -> soja_primera (verano)",
        perfil_mercado="Cultivo de servicio de bajo costo de implantación; aporta cobertura densa contra erosión y supresión de malezas.",
    ),
    "camelina": CropProfile(
        id="camelina",
        numeric_id=4,
        nombre_legible="Camelina",
        campana="invierno",
        familia="crucifera",
        aporte_rastrojo="bajo",
        carbon_balance=0.10,
        fija_nitrogeno=False,
        es_cobertura=False,
        cobertura_inicial="medio",
        meses_activos=(6, 7, 8, 9, 10),
        meses_rastrojo=(11,),
        cultivo_puente_ideal="soja_segunda",
        secuencia_sugerida="camelina (invierno) -> soja_segunda (verano)",
        perfil_mercado="Especialidad de nicho para biocombustibles (contrato requerido); ciclo corto y bajo requerimiento hídrico.",
    ),
    # --- Campaña Gruesa (Verano: IDs 5..10) ---
    "maiz_temprano": CropProfile(
        id="maiz_temprano",
        numeric_id=5,
        nombre_legible="Maíz Temprano",
        campana="verano",
        familia="graminea",
        aporte_rastrojo="alto",
        carbon_balance=1.0,
        fija_nitrogeno=False,
        es_cobertura=False,
        cobertura_inicial="medio",
        meses_activos=(9, 10, 11, 12, 1, 2),
        meses_rastrojo=(3, 4, 5, 6),
        cultivo_puente_ideal="trigo",
        secuencia_sugerida="vicia_cobertura (invierno) -> maiz_temprano (verano)",
        perfil_mercado="Alto potencial de rinde y gran liquidez, pero con mayor costo de implantación y exposición a estrés en floración.",
    ),
    "maiz_tardio": CropProfile(
        id="maiz_tardio",
        numeric_id=6,
        nombre_legible="Maíz Tardío",
        campana="verano",
        familia="graminea",
        aporte_rastrojo="alto",
        carbon_balance=1.0,
        fija_nitrogeno=False,
        es_cobertura=False,
        cobertura_inicial="medio",
        meses_activos=(12, 1, 2, 3, 4),
        meses_rastrojo=(5, 6, 7, 8),
        cultivo_puente_ideal="vicia_cobertura",
        secuencia_sugerida="vicia_cobertura (invierno) -> maiz_tardio (verano)",
        perfil_mercado="Estabilidad superior ante golpes de calor de enero; alto aporte de rastrojo de lenta descomposición.",
    ),
    "soja_primera": CropProfile(
        id="soja_primera",
        numeric_id=7,
        nombre_legible="Soja de Primera",
        campana="verano",
        familia="leguminosa",
        aporte_rastrojo="bajo",
        carbon_balance=-0.85,
        fija_nitrogeno=True,
        es_cobertura=False,
        cobertura_inicial="bajo",
        meses_activos=(11, 12, 1, 2, 3),
        meses_rastrojo=(4,),
        cultivo_puente_ideal="avena_cobertura",
        secuencia_sugerida="avena_cobertura (invierno) -> soja_primera (verano)",
        perfil_mercado="Máxima liquidez comercial; deja poco rastrojo de rápida mineralización, por lo que requiere gramínea o cobertura después.",
    ),
    "soja_segunda": CropProfile(
        id="soja_segunda",
        numeric_id=8,
        nombre_legible="Soja de Segunda",
        campana="verano",
        familia="leguminosa",
        aporte_rastrojo="bajo",
        carbon_balance=-0.50,
        fija_nitrogeno=True,
        es_cobertura=False,
        cobertura_inicial="medio",  # Se siembra sobre rastrojo abundante de fina
        meses_activos=(12, 1, 2, 3, 4),
        meses_rastrojo=(5,),
        cultivo_puente_ideal="trigo",
        secuencia_sugerida="trigo / cebada (invierno) -> soja_segunda (verano)",
        perfil_mercado="Complementa el doble cultivo tras trigo o cebada; mejora el margen anual manteniendo rastrojo invernal en superficie.",
    ),
    "girasol": CropProfile(
        id="girasol",
        numeric_id=9,
        nombre_legible="Girasol",
        campana="verano",
        familia="oleaginosa",
        aporte_rastrojo="bajo",
        carbon_balance=-0.45,
        fija_nitrogeno=False,
        es_cobertura=False,
        cobertura_inicial="bajo",
        meses_activos=(10, 11, 12, 1, 2),
        meses_rastrojo=(3,),
        cultivo_puente_ideal="trigo",
        secuencia_sugerida="avena_cobertura (invierno) -> girasol (verano)",
        perfil_mercado="Buena alternativa rústica con demanda aceitera firme; baja cobertura poscosecha en lotes con pendiente.",
    ),
    "sorgo": CropProfile(
        id="sorgo",
        numeric_id=10,
        nombre_legible="Sorgo",
        campana="verano",
        familia="graminea",
        aporte_rastrojo="alto",
        carbon_balance=1.0,
        fija_nitrogeno=False,
        es_cobertura=False,
        cobertura_inicial="alto",
        meses_activos=(11, 12, 1, 2, 3),
        meses_rastrojo=(4, 5, 6, 7),
        cultivo_puente_ideal="vicia_cobertura",
        secuencia_sugerida="vicia_cobertura (invierno) -> sorgo / maiz_tardio (verano)",
        perfil_mercado="Bajo costo de implantación y alta estabilidad defensiva; grano comercializable como forraje o exportación.",
    ),
}

# Overrides puntuales para transiciones específicas donde la interacción importa más que la regla general
SPECIFIC_TRANSITION_SCORES: dict[tuple[str, str], float] = {
    # Doble cultivo virtuoso (fina -> soja de segunda)
    ("trigo", "soja_segunda"): 88.0,
    ("cebada", "soja_segunda"): 89.0,
    ("avena_cobertura", "soja_segunda"): 85.0,
    ("camelina", "soja_segunda"): 82.0,
    ("vicia_cobertura", "soja_segunda"): 76.0,
    # Cultivo de cobertura leguminosa -> gramínea de verano
    ("vicia_cobertura", "maiz_temprano"): 91.0,
    ("vicia_cobertura", "maiz_tardio"): 93.0,
    ("vicia_cobertura", "sorgo"): 91.0,
    # Cultivo de cobertura gramínea -> soja de primera (corte de malezas + cama de rastrojo)
    ("avena_cobertura", "soja_primera"): 90.0,
    ("avena_cobertura", "girasol"): 82.0,
    # Repetición de soja (primera <-> segunda)
    ("soja_primera", "soja_segunda"): 28.0,
    ("soja_segunda", "soja_primera"): 28.0,
    # Repetición de maíz (temprano <-> tardío)
    ("maiz_temprano", "maiz_tardio"): 46.0,
    ("maiz_tardio", "maiz_temprano"): 46.0,
    # Trigo <-> cebada (mismo grupo sanitario de fina)
    ("trigo", "cebada"): 45.0,
    ("cebada", "trigo"): 45.0,
}


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def get_crops_for_campaign(campana: Campaign) -> tuple[str, ...]:
    """Devuelve los IDs de cultivos válidos para una campaña ('invierno' o 'verano')."""
    if campana == "invierno":
        return INVIERNO_CROPS
    if campana == "verano":
        return VERANO_CROPS
    raise ValueError(f"Campaña desconocida: {campana!r}. Usar 'invierno' o 'verano'.")


def get_crop_profile(cultivo: str) -> CropProfile:
    """Obtiene el perfil agronómico de un cultivo o lanza ValueError si no existe."""
    normalizado = cultivo.strip().lower()
    if normalizado not in CROP_PROFILES:
        raise ValueError(
            f"Cultivo desconocido: {cultivo!r}. Opciones válidas: {', '.join(ALL_CROPS)}"
        )
    return CROP_PROFILES[normalizado]


def get_crop_numeric_id(cultivo: str) -> int:
    """Devuelve el ID numérico (0..10) usado en la feature ``cultivo_candidato`` de ML-1/ML-2."""
    return get_crop_profile(cultivo).numeric_id


def _normalize_previous_crop(cultivo_anterior: str | None) -> str | None:
    if cultivo_anterior is None:
        return None
    normalizado = cultivo_anterior.strip().lower()
    if normalizado in NEUTRAL_PREVIOUS_VALUES:
        return None
    if normalizado not in CROP_PROFILES:
        return None
    return normalizado


def _compute_base_transition_score(
    prev_crop: CropProfile | None,
    candidate: CropProfile,
) -> tuple[float, str, list[str]]:
    """Calcula el puntaje base de transición (0..100), condición previa y factores."""
    factors: list[str] = []

    if prev_crop is None:
        if candidate.id == "soja_segunda":
            factors.append(
                "Soja de Segunda sin cultivo invernal previo: menor potencial que Soja de Primera en lote libre."
            )
            return 60.0, "sin_antecesor_definido", factors

        base = 68.0
        if candidate.es_cobertura or candidate.aporte_rastrojo == "alto":
            base += 10.0
            factors.append(
                f"{candidate.nombre_legible} aporta cobertura y rastrojo para salir de un lote sin antecesor definido."
            )
        else:
            factors.append(
                f"Sin cultivo antecesor registrado: {candidate.nombre_legible} parte de una base agronómica neutra."
            )
        return base, "sin_antecesor_definido", factors

    # Condición del rastrojo/suelo dejada por el antecesor
    if prev_crop.id in {"soja_primera", "soja_segunda"}:
        condicion = "deficit_rastrojo_por_soja"
    elif prev_crop.familia == "oleaginosa":
        condicion = "baja_cobertura_post_oleaginosa"
    elif prev_crop.es_cobertura:
        condicion = "cobertura_activa_previa"
    else:
        condicion = "buen_rastrojo_graminea"

    # 1. Monocultivo estricto
    if prev_crop.id == candidate.id:
        monoculture_scores = {
            "soja_primera": 25.0,
            "soja_segunda": 25.0,
            "girasol": 30.0,
            "camelina": 32.0,
            "trigo": 42.0,
            "cebada": 42.0,
            "maiz_temprano": 45.0,
            "maiz_tardio": 45.0,
            "sorgo": 48.0,
            "vicia_cobertura": 55.0,
            "avena_cobertura": 55.0,
        }
        score = monoculture_scores.get(candidate.id, 40.0)
        factors.append(
            f"Monocultivo repetido ({prev_crop.nombre_legible} → {candidate.nombre_legible}): "
            "aumenta presión de malezas, plagas y degradación edáfica."
        )
        return score, condicion, factors

    # 2. Override específico
    override = SPECIFIC_TRANSITION_SCORES.get((prev_crop.id, candidate.id))
    if override is not None:
        factors.append(
            f"Secuencia específica {prev_crop.nombre_legible} → {candidate.nombre_legible}: "
            "transición agronómica altamente documentada."
        )
        return override, condicion, factors

    # 3. Regla agronómica para Soja de Segunda viniendo de un cultivo de verano sin fina intermedia
    if candidate.id == "soja_segunda" and prev_crop.campana == "verano":
        factors.append(
            f"Soja de Segunda tras cultivo de verano ({prev_crop.nombre_legible}) sin fina intermedia: "
            "se desaprovecha la fecha óptima de Soja de Primera."
        )
        return 52.0, condicion, factors

    # 4. Reglas generales por alternancia de familia botánica
    score = 65.0
    if prev_crop.familia == "leguminosa" and candidate.familia == "graminea":
        score += 18.0
        if condicion == "deficit_rastrojo_por_soja" and candidate.carbon_balance >= 0.8:
            # Bonus adicional para gramíneas de alto rastrojo que recomponen carbono tras soja
            score += round(4.0 * candidate.carbon_balance, 2)
        factors.append(
            f"Rotación virtuosa leguminosa → gramínea ({prev_crop.nombre_legible} → {candidate.nombre_legible}): "
            "capitaliza nitrógeno residual y recompone rastrojo tras soja."
        )
    elif prev_crop.familia == "graminea" and candidate.familia == "leguminosa":
        score += 15.0
        factors.append(
            f"Alternancia gramínea → leguminosa ({prev_crop.nombre_legible} → {candidate.nombre_legible}): "
            "corta ciclo de enfermedades sobre rastrojo abundante."
        )
    elif prev_crop.familia == "oleaginosa" and candidate.familia == "graminea":
        score += 14.0 + round(3.0 * max(0.0, candidate.carbon_balance), 2)
        factors.append(
            f"Rotación oleaginosa → gramínea ({prev_crop.nombre_legible} → {candidate.nombre_legible}): "
            "recupera cobertura y estructura superficial."
        )
    elif prev_crop.familia == "graminea" and candidate.familia in {"oleaginosa", "crucifera"}:
        score += 11.0
        factors.append(
            f"Alternancia gramínea → {candidate.familia} ({prev_crop.nombre_legible} → {candidate.nombre_legible}): "
            "diversifica raíces y manejo de malezas."
        )
    elif prev_crop.familia == "leguminosa" and candidate.familia == "leguminosa":
        if candidate.es_cobertura:
            score += 8.0
            factors.append(
                f"{candidate.nombre_legible} aporta cobertura viva invernal tras {prev_crop.nombre_legible}."
            )
        else:
            score -= 10.0
            factors.append(
                f"Repetición de leguminosas ({prev_crop.nombre_legible} → {candidate.nombre_legible}): "
                "mayor riesgo sanitario y bajo aporte de carbono."
            )
    elif prev_crop.familia == "graminea" and candidate.familia == "graminea":
        score += 4.0
        factors.append(
            f"Secuencia entre gramíneas distintas ({prev_crop.nombre_legible} → {candidate.nombre_legible}): "
            "sostiene alta cobertura pero requiere monitorear disponibilidad de nitrógeno."
        )
    else:
        score += 6.0
        factors.append(
            f"Alternancia botánica ({prev_crop.nombre_legible} → {candidate.nombre_legible}): "
            "diversifica especies y corta ciclos sanitarios."
        )

    if candidate.es_cobertura:
        score += 8.0
        factors.append(
            f"{candidate.nombre_legible} reduce períodos de suelo desnudo y mejora la infiltración."
        )

    return score, condicion, factors


def _compute_carbon_adjustment(
    candidate: CropProfile,
    soc_g_kg: float | None,
) -> tuple[float, str | None]:
    if soc_g_kg is None:
        return 0.0, None

    if soc_g_kg < SOC_LOW_THRESHOLD_G_KG:
        if candidate.carbon_balance >= 0.75:
            return (
                10.0,
                f"Carbono orgánico bajo ({soc_g_kg:.1f} g/kg): {candidate.nombre_legible} ayuda a recomponer materia orgánica.",
            )
        if candidate.carbon_balance < 0:
            return (
                -12.0,
                f"Carbono orgánico bajo ({soc_g_kg:.1f} g/kg): {candidate.nombre_legible} agrava el déficit de rastrojo.",
            )
        return 0.0, None

    if soc_g_kg < SOC_MEDIUM_THRESHOLD_G_KG:
        if candidate.carbon_balance >= 0.75:
            return 4.0, None
        if candidate.carbon_balance < 0:
            return -4.0, None
        return 0.0, None

    # Suelo con buen nivel de carbono orgánico (>= 22 g/kg)
    return 2.0, None


def _compute_slope_adjustment(
    candidate: CropProfile,
    prev_crop: CropProfile | None,
    pendiente_pct: float | None,
) -> tuple[float, RiskLevel, str | None]:
    if pendiente_pct is None:
        return 0.0, "bajo", None

    if pendiente_pct >= SLOPE_HIGH_PCT:
        if candidate.cobertura_inicial == "bajo":
            return (
                -14.0,
                "alto",
                f"Pendiente elevada ({pendiente_pct:.1f}% SRTM): {candidate.nombre_legible} presenta alto riesgo de erosión hídrica por baja cobertura inicial.",
            )
        if candidate.cobertura_inicial == "medio":
            if prev_crop is not None and (
                prev_crop.es_cobertura or prev_crop.aporte_rastrojo == "alto"
            ):
                return (
                    0.0,
                    "medio",
                    f"Pendiente elevada ({pendiente_pct:.1f}% SRTM) amortiguada por rastrojo previo de {prev_crop.nombre_legible}.",
                )
            return (
                -4.0,
                "medio",
                f"Pendiente elevada ({pendiente_pct:.1f}% SRTM): cuidar cobertura superficial en implantación.",
            )
        return (
            8.0,
            "bajo",
            f"Pendiente elevada ({pendiente_pct:.1f}% SRTM): {candidate.nombre_legible} frena escorrentía con cobertura densa.",
        )

    if pendiente_pct >= SLOPE_MODERATE_PCT:
        if candidate.cobertura_inicial == "bajo":
            return (
                -6.0,
                "medio",
                f"Pendiente de {pendiente_pct:.1f}% (SRTM) requiere rastrojo de gramínea o cobertura para frenar escorrentía.",
            )
        if candidate.cobertura_inicial == "alto":
            return (
                4.0,
                "bajo",
                f"Pendiente de {pendiente_pct:.1f}% (SRTM) protegida por alta cobertura y rastrojo de {candidate.nombre_legible}.",
            )
        return 0.0, "medio", None

    return 0.0, "bajo", None


def _compute_texture_adjustment(
    candidate: CropProfile,
    arcilla_pct: float | None,
) -> tuple[float, str | None]:
    """Ajusta según textura extrema (suelos muy arenosos <16% o vertisoles pesados >34%)."""
    if arcilla_pct is None:
        return 0.0, None

    if arcilla_pct < CLAY_SANDY_MAX_PCT:
        if candidate.es_cobertura or candidate.aporte_rastrojo == "alto":
            return (
                5.0,
                f"Suelo arenoso ({arcilla_pct:.1f}% arcilla): las raíces y rastrojo de {candidate.nombre_legible} fijan la superficie y retienen humedad.",
            )
        if candidate.aporte_rastrojo == "bajo":
            return (
                -6.0,
                f"Suelo arenoso ({arcilla_pct:.1f}% arcilla): el bajo rastrojo de {candidate.nombre_legible} expone el lote a erosión y pérdida de agua.",
            )
        return 0.0, None

    if arcilla_pct > CLAY_HEAVY_MIN_PCT:
        if candidate.familia == "graminea" or candidate.es_cobertura:
            return (
                4.0,
                f"Suelo arcilloso pesado ({arcilla_pct:.1f}% arcilla): el sistema radicular de {candidate.nombre_legible} mejora la macroporosidad e infiltración.",
            )
        if candidate.aporte_rastrojo == "bajo":
            return (
                -4.0,
                f"Suelo arcilloso pesado ({arcilla_pct:.1f}% arcilla): baja cobertura favorece planchado superficial y escorrentía.",
            )
        return 0.0, None

    return 0.0, None


def _compute_ph_adjustment(
    candidate: CropProfile,
    phh2o: float | None,
) -> tuple[float, str | None]:
    if phh2o is None:
        return 0.0, None
    if phh2o < PH_LOW_THRESHOLD:
        if candidate.id in {"cebada", "vicia_cobertura"}:
            return (
                -8.0,
                f"pH ácido ({phh2o:.1f}): restringe implantación óptima de {candidate.nombre_legible}.",
            )
        return -4.0, f"pH ácido ({phh2o:.1f}): considerar encalado o cultivos tolerantes."
    if phh2o > PH_HIGH_THRESHOLD:
        return (
            -5.0,
            f"pH alcalino ({phh2o:.1f}): puede limitar disponibilidad de micronutrientes.",
        )
    return 0.0, None


def evaluate_bare_field_periods(
    prev_crop: CropProfile | None,
    candidate: CropProfile,
) -> tuple[int, tuple[MonthCoverage, ...]]:
    """Construye la línea de tiempo de 12 meses distinguiendo candidato, antecesor, rastrojo y suelo desnudo."""
    candidate_active = set(candidate.meses_activos)
    prev_active: set[int] = set()
    residue_months = set(candidate.meses_rastrojo)

    if prev_crop is not None:
        if prev_crop.campana != candidate.campana:
            prev_active.update(prev_crop.meses_activos)
        residue_months.update(prev_crop.meses_rastrojo)

    calendario: list[MonthCoverage] = []
    bare_months = 0

    for mes_idx in range(1, 13):
        if mes_idx in candidate_active:
            estado: MonthStatus = "cultivo_candidato"
        elif mes_idx in prev_active:
            estado = "cultivo_antecesor"
        elif mes_idx in residue_months:
            estado = "rastrojo_protector"
        else:
            estado = "suelo_desnudo"
            bare_months += 1

        calendario.append(
            MonthCoverage(
                mes=mes_idx,
                nombre=MONTH_NAMES_ES[mes_idx - 1],
                estado=estado,
            )
        )

    return bare_months, tuple(calendario)


def evaluate_soil_and_rotation(
    cultivo_candidato: str,
    cultivo_anterior: str | None = None,
    carbono_organico_g_kg: float | None = None,
    pendiente_terreno_pct: float | None = None,
    arcilla_pct: float | None = None,
    phh2o: float | None = None,
) -> SoilEvaluationResult:
    """Evalúa S_suelo (0..100) y cobertura anual para un cultivo candidato y lote."""
    candidate = get_crop_profile(cultivo_candidato)
    prev_id = _normalize_previous_crop(cultivo_anterior)
    prev_crop = CROP_PROFILES[prev_id] if prev_id is not None else None

    base_score, condicion, factors = _compute_base_transition_score(prev_crop, candidate)
    adj_soc, soc_factor = _compute_carbon_adjustment(candidate, carbono_organico_g_kg)
    adj_slope, erosion_risk, slope_factor = _compute_slope_adjustment(
        candidate, prev_crop, pendiente_terreno_pct
    )
    adj_texture, texture_factor = _compute_texture_adjustment(candidate, arcilla_pct)
    adj_ph, ph_factor = _compute_ph_adjustment(candidate, phh2o)

    for extra_factor in (soc_factor, slope_factor, texture_factor, ph_factor):
        if extra_factor is not None:
            factors.append(extra_factor)

    final_soil_score = _clamp_score(
        base_score + adj_soc + adj_slope + adj_texture + adj_ph
    )
    bare_months, calendario = evaluate_bare_field_periods(prev_crop, candidate)

    return SoilEvaluationResult(
        cultivo_candidato=candidate.id,
        numeric_id=candidate.numeric_id,
        cultivo_anterior=prev_id,
        campana=candidate.campana,
        s_suelo=final_soil_score,
        puntaje_base_rotacion=round(base_score, 2),
        ajuste_carbono=round(adj_soc, 2),
        ajuste_pendiente=round(adj_slope, 2),
        ajuste_textura=round(adj_texture, 2),
        ajuste_ph=round(adj_ph, 2),
        riesgo_erosion_suelo=erosion_risk,
        condicion_rotacion_previa=condicion,
        secuencia_sugerida=candidate.secuencia_sugerida,
        perfil_mercado=candidate.perfil_mercado,
        meses_suelo_desnudo=bare_months,
        calendario_12m=calendario,
        factores_suelo=tuple(factors),
    )


def evaluate_campaign_soil(
    campana: Campaign,
    cultivo_anterior: str | None = None,
    carbono_organico_g_kg: float | None = None,
    pendiente_terreno_pct: float | None = None,
    arcilla_pct: float | None = None,
    phh2o: float | None = None,
) -> dict[str, SoilEvaluationResult]:
    """Evalúa todos los cultivos de una campaña en una sola llamada (interfaz para ML-4)."""
    crops = get_crops_for_campaign(campana)
    return {
        crop_id: evaluate_soil_and_rotation(
            cultivo_candidato=crop_id,
            cultivo_anterior=cultivo_anterior,
            carbono_organico_g_kg=carbono_organico_g_kg,
            pendiente_terreno_pct=pendiente_terreno_pct,
            arcilla_pct=arcilla_pct,
            phh2o=phh2o,
        )
        for crop_id in crops
    }


def compare_rotation_strategies(
    campana: Campaign,
    cultivo_anterior: str | None = None,
    carbono_organico_g_kg: float | None = None,
    pendiente_terreno_pct: float | None = None,
    arcilla_pct: float | None = None,
    phh2o: float | None = None,
) -> tuple[RotationStrategyComparison, RotationStrategyComparison, RotationStrategyComparison]:
    """Compara 3 estrategias de rotación (Testigo vs. Defensiva Hídrica vs. Regenerativa de Suelo)."""
    evals = evaluate_campaign_soil(
        campana=campana,
        cultivo_anterior=cultivo_anterior,
        carbono_organico_g_kg=carbono_organico_g_kg,
        pendiente_terreno_pct=pendiente_terreno_pct,
        arcilla_pct=arcilla_pct,
        phh2o=phh2o,
    )

    prev_id = _normalize_previous_crop(cultivo_anterior)
    if prev_id in evals:
        testigo_res = evals[prev_id]
    else:
        default_testigo = "soja_primera" if campana == "verano" else "trigo"
        testigo_res = evaluate_soil_and_rotation(
            cultivo_candidato=default_testigo,
            cultivo_anterior=default_testigo,
            carbono_organico_g_kg=carbono_organico_g_kg,
            pendiente_terreno_pct=pendiente_terreno_pct,
            arcilla_pct=arcilla_pct,
            phh2o=phh2o,
        )

    defensiva_id = "sorgo" if campana == "verano" else "camelina"
    regenerativa_id = "maiz_tardio" if campana == "verano" else "vicia_cobertura"

    defensiva_res = evals[defensiva_id]
    regenerativa_res = evals[regenerativa_id]

    testigo_bare = testigo_res.meses_suelo_desnudo

    return (
        RotationStrategyComparison(
            estrategia_id="rotacion_actual_testigo",
            titulo="Estrategia Testigo (Repetir Cultivo / Barbecho Desnudo)",
            cultivo_evaluado=testigo_res.cultivo_candidato,
            secuencia_anual=f"barbecho_desnudo (invierno) -> {testigo_res.cultivo_candidato} (repetido)",
            s_suelo=testigo_res.s_suelo,
            riesgo_erosion_suelo=testigo_res.riesgo_erosion_suelo,
            meses_suelo_desnudo=testigo_bare,
            reduccion_suelo_desnudo_vs_testigo=0,
            resumen_beneficios_riesgos=testigo_res.factores_suelo[0],
        ),
        RotationStrategyComparison(
            estrategia_id="resiliencia_hidrica",
            titulo="Estrategia Defensiva Hídrica y Estabilidad",
            cultivo_evaluado=defensiva_res.cultivo_candidato,
            secuencia_anual=defensiva_res.secuencia_sugerida,
            s_suelo=defensiva_res.s_suelo,
            riesgo_erosion_suelo=defensiva_res.riesgo_erosion_suelo,
            meses_suelo_desnudo=defensiva_res.meses_suelo_desnudo,
            reduccion_suelo_desnudo_vs_testigo=max(
                0, testigo_bare - defensiva_res.meses_suelo_desnudo
            ),
            resumen_beneficios_riesgos=defensiva_res.factores_suelo[0],
        ),
        RotationStrategyComparison(
            estrategia_id="regenerativa_suelo",
            titulo="Estrategia Regenerativa de Suelo y Cobertura Continua",
            cultivo_evaluado=regenerativa_res.cultivo_candidato,
            secuencia_anual=regenerativa_res.secuencia_sugerida,
            s_suelo=regenerativa_res.s_suelo,
            riesgo_erosion_suelo=regenerativa_res.riesgo_erosion_suelo,
            meses_suelo_desnudo=regenerativa_res.meses_suelo_desnudo,
            reduccion_suelo_desnudo_vs_testigo=max(
                0, testigo_bare - regenerativa_res.meses_suelo_desnudo
            ),
            resumen_beneficios_riesgos=regenerativa_res.factores_suelo[0],
        ),
    )
