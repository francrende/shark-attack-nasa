"""Motor de Inferencia Online, Detección de Anomalías y Decisión Multicriterio (ML-4).

Implementa ``AgroPredictor`` (interfaz ``RecommendationEngine`` de CONTEXT.md):
1. Carga singleton en memoria de ``backend/ml/modelo_agro.joblib`` (< 15 ms por lote).
2. Aplica transformaciones internas de simulación *What-If* manteniendo controles
   independientes en la UI pero preservando la consistencia física del vector X.
3. Ejecuta inferencia en batch de ``S_hidroclimatico`` (Pilar 1, clippeado a [0, 100]).
4. Fusiona ``S_hidroclimatico`` con ``S_suelo`` (Pilar 2, de ``rotation_matrix.py``)
   usando pesos dinámicos según ``objetivo_productor`` y penalización no lineal por
   factor limitante crítico (< 35 pts, Ley del Mínimo de Liebig).
5. Clasifica el ``riesgo`` (``bajo`` | ``medio`` | ``alto`` | ``critico``) con los umbrales de ML-8.
6. Detecta hasta 6 anomalías físicas en curso basadas en evidencia satelital.
7. Genera los Top 3 ``factores_clave_ml`` (usando ``feature_baselines`` por campaña +
   ``permutation_importance`` por cultivo + factores topográficos/edáficos) y la
   ``explicacion`` agronómica transparente para ``POST /api/v1/simulate``.
8. (ML-5) ``predict_ensemble``: en lugar de un único valor para la ventana futura
   ``[corte+1, corte+90]``, corre el modelo con los escenarios históricos reales de cada año
   (``BACK-6``) y devuelve la distribución del puntaje (promedio, P10, P90, años
   desfavorables y peor escenario).
9. (ML-10) Los cultivos sin rinde MAGyP (coberturas y camelina) no pasan por el modelo: su
   puntaje es el de los cultivos con rinde real de la misma campaña, con el desvío respecto de
   un año normal escalado por el factor de respuesta del rinde ``Ky`` de FAO-56. Además, a todos
   los cultivos se les resta ``penalizacion_demanda_hidrica`` cuando el perfil está seco.
"""

from __future__ import annotations

import threading
import warnings
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
from sklearn.exceptions import InconsistentVersionWarning

try:
    from backend.services.rotation_matrix import (
        CROP_PROFILES,
        SoilEvaluationResult,
        compare_rotation_strategies,
        evaluate_campaign_soil,
        get_crop_profile,
        get_crops_for_campaign,
        motivo_lote_ocupado,
        penalizacion_demanda_hidrica,
    )
except ImportError:
    from services.rotation_matrix import (  # type: ignore[no-redef]
        CROP_PROFILES,
        SoilEvaluationResult,
        compare_rotation_strategies,
        evaluate_campaign_soil,
        get_crop_profile,
        get_crops_for_campaign,
        motivo_lote_ocupado,
        penalizacion_demanda_hidrica,
    )

try:
    from backend.ml import calendario_siembra as cal
    from backend.ml.fao_labels import CROP_CATALOG as FAO_CROP_CATALOG
    from backend.providers.enso import NOMBRE_FASE, fase_enso
except ImportError:
    from ml import calendario_siembra as cal  # type: ignore[no-redef]
    from ml.fao_labels import CROP_CATALOG as FAO_CROP_CATALOG  # type: ignore[no-redef]
    from providers.enso import NOMBRE_FASE, fase_enso  # type: ignore[no-redef]

Campaign = Literal["invierno", "verano"]
ProducerObjective = Literal[
    "resiliencia_hidroclimatica",
    "conservacion_suelo",
    "equilibrio",
]
CropRiskLevel = Literal["bajo", "medio", "alto", "critico"]
AnomalySeverity = Literal["baja", "media", "alta"]

ML_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = ML_DIR / "modelo_agro.joblib"

# Orden estricto de las 15 features del modelo ML-7 (CONTEXT.md §4.3). Debe coincidir con
# ``feature_columns`` del bundle (lo verifica ``AgroPredictor``).
FEATURE_COLUMNS: tuple[str, ...] = (
    "gwetroot_saturacion_pct",
    "gwettop_saturacion_pct",
    "tendencia_humedad_15d_pct",
    "anomalia_lluvia_90d_pct",
    "indice_aridez_evaporativa",
    "pendiente_terreno_pct",
    "elevacion_m",
    "textura_arcilla_pct",
    "frecuencia_tormentas_extremas",
    "frecuencia_estres_termico",
    "frecuencia_riesgo_helada",
    "lluvia_periodo_critico_mm",
    "dias_hasta_siembra",
    "oni_actual",
    "cultivo_candidato",
)
NUMERIC_FEATURES: tuple[str, ...] = FEATURE_COLUMNS[:-1]

# Se conocen al decidir (ventana pasada + terreno). Igual a FEATURES_ACTUALES del backend.
CURRENT_FEATURES: tuple[str, ...] = (
    "gwetroot_saturacion_pct",
    "gwettop_saturacion_pct",
    "tendencia_humedad_15d_pct",
    "anomalia_lluvia_90d_pct",
    "indice_aridez_evaporativa",
    "pendiente_terreno_pct",
    "elevacion_m",
    "textura_arcilla_pct",
)
# Período crítico del cultivo: en producción llegan como años análogos (ML-5/ML-7).
# Igual a FEATURES_PERIODO_CRITICO de backend/providers/features.py.
FUTURE_FEATURES: tuple[str, ...] = (
    "frecuencia_tormentas_extremas",
    "frecuencia_estres_termico",
    "frecuencia_riesgo_helada",
    "lluvia_periodo_critico_mm",
)
# Las 3 de eventos son obligatorias en un escenario; la lluvia usa la climatología si falta.
REQUIRED_FUTURE_FEATURES: tuple[str, ...] = FUTURE_FEATURES[:3]
DEFAULT_LLUVIA_CRITICA_MM = 250.0
ONI_NEUTRO = 0.0
# Puntaje de un año normal en la escala MAGyP (rinde igual a la tendencia).
PUNTAJE_ANIO_NORMAL = 50.0
# La oración de la explicación sobre demanda hídrica aparece desde esta penalización.
PENALIZACION_DEMANDA_VISIBLE = 2.0

# ML-8: umbrales en la escala MAGyP (50 = año normal), calibrados con el ensemble de producción
# en val + test 2019–2024. En promedio, 1 de cada 4 años es malo (rinde real 15% o más bajo la
# tendencia). Por tramo del promedio esperado:
#   < 40 → crítico (1 de cada 2 años malos) | 40–45 → alto (1 de 3)
#   45–50 → medio (1 de 4, la media)        | ≥ 50 → bajo (1 de 7)
HYDRO_RISK_THRESHOLDS: tuple[float, float, float] = (40.0, 45.0, 50.0)  # crítico / alto / medio
# Con el pilar suelo por debajo de este valor, el riesgo es al menos "alto".
SOIL_RISK_THRESHOLD = 35.0
# Un año análogo cuenta como desfavorable debajo de 40: el modelo achata hacia la media, y bajo
# 40 la mitad de los casos son años malos reales.
DEFAULT_UMBRAL_DESFAVORABLE = 40.0
# Si el P10 del ensemble cae debajo de 30, el riesgo sube un nivel (18% de los casos; en ellos
# 4 de cada 10 años son malos).
CRITICAL_HYDRO_THRESHOLD = 30.0
RISK_LEVELS: tuple[CropRiskLevel, ...] = ("bajo", "medio", "alto", "critico")

# Pesos de la fórmula dinámica (CONTEXT.md Sección 4.5)
OBJECTIVE_WEIGHTS: dict[str, tuple[float, float]] = {
    "resiliencia_hidroclimatica": (0.75, 0.25),
    "conservacion_suelo": (0.30, 0.70),
    "equilibrio": (0.50, 0.50),
}

# Umbral y factor de penalización por cuello de botella (Opción B - Ley del Mínimo)
LIMITING_PILLAR_THRESHOLD = 35.0
LIMITING_PILLAR_PENALTY_SLOPE = 0.165
LIMITING_PILLAR_MAX_PENALTY = 5.0


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return float(max(low, min(high, value)))


def classify_soil_texture(arcilla_pct: float, arena_pct: float | None = None) -> str:
    """Clasifica la textura predominante del lote según porcentaje de arcilla (y arena opcional)."""
    if arena_pct is not None and arena_pct >= 65.0 and arcilla_pct < 18.0:
        return "franco_arenoso"
    if arcilla_pct < 16.0:
        return "franco_arenoso"
    if arcilla_pct < 27.0:
        return "franco_limoso"
    if arcilla_pct < 35.0:
        return "franco_arcilloso"
    return "arcilloso"


# Cortes de días con T2M_MAX > 34 °C en ~90 días: espejo de providers.nasa_telemetry
# (RIESGO_BAJO_HASTA / RIESGO_MEDIO_HASTA / RIESGO_ALTO_HASTA; test de paridad en test_predictor.py)
# para que `riesgo_termico_verano` y la anomalía `estres_termico_critico` usen la misma escala.
THERMAL_RISK_THRESHOLDS: tuple[float, float, float] = (15.0, 25.0, 40.0)


def classify_summer_thermal_risk(frecuencia_estres_termico: float) -> CropRiskLevel:
    """Clasifica días con T2M_MAX > 34 °C en una ventana de ~90 días (misma escala que BACK-2)."""
    dias = float(frecuencia_estres_termico)
    bajo_hasta, medio_hasta, alto_hasta = THERMAL_RISK_THRESHOLDS
    if dias < bajo_hasta:
        return "bajo"
    if dias < medio_hasta:
        return "medio"
    if dias <= alto_hasta:
        return "alto"
    return "critico"


def classify_slope_runoff_risk(
    pendiente_terreno_pct: float,
    frecuencia_tormentas_extremas: int = 0,
    arcilla_pct: float = 24.0,
) -> Literal["bajo", "medio", "alto"]:
    """Clasifica el riesgo topográfico de erosión y escorrentía superficial (SRTM 30m)."""
    effective_slope = float(pendiente_terreno_pct)
    if frecuencia_tormentas_extremas >= 2:
        effective_slope += 0.35
    if arcilla_pct >= 34.0:
        effective_slope += 0.25

    if effective_slope >= 2.2:
        return "alto"
    if effective_slope >= 1.0:
        return "medio"
    return "bajo"


def apply_what_if_simulation(
    base_features: dict[str, float],
    override_humedad_radicular_pct: float | None = None,
    variacion_lluvia_esperada_pct: float | None = None,
) -> dict[str, float]:
    """Recalcula internamente el vector de features bajo escenarios What-If.

    Los controles en la UI son independientes, pero internamente se actualizan las
    variables físicas derivadas para que el árbol de decisión no reciba combinaciones
    físicamente rotas (ej. +30% lluvia sin cambio en el índice de aridez, o cambio
    abrupto de humedad radicular con humedad superficial congelada).
    """
    sim = {k: float(v) for k, v in base_features.items() if k in NUMERIC_FEATURES}

    rain_delta = float(variacion_lluvia_esperada_pct or 0.0)
    has_manual_moisture = override_humedad_radicular_pct is not None

    # 1. Variación de lluvia esperada (-50% a +50%): "llueve X% más/menos" que lo observado,
    # es decir, multiplica la lluvia acumulada. Con anomalía a y variación v:
    # lluvia/clim = (1 + a/100)(1 + v/100) → nueva anomalía = (100 + a)(1 + v/100) - 100.
    if abs(rain_delta) > 1e-6:
        rain_delta_clamped = _clamp(rain_delta, -60.0, 60.0)
        sim["anomalia_lluvia_90d_pct"] = round(
            _clamp(
                (100.0 + sim["anomalia_lluvia_90d_pct"]) * (1.0 + rain_delta_clamped / 100.0) - 100.0,
                -80.0,
                150.0,
            ),
            2,
        )
        scale_factor = max(0.15, 1.0 + (rain_delta_clamped / 100.0))
        sim["indice_aridez_evaporativa"] = round(
            _clamp(sim["indice_aridez_evaporativa"] * scale_factor, 0.08, 2.80),
            3,
        )
        if "lluvia_periodo_critico_mm" in sim:
            sim["lluvia_periodo_critico_mm"] = round(
                max(0.0, sim["lluvia_periodo_critico_mm"] * (1.0 + rain_delta_clamped / 100.0)), 1
            )
        if rain_delta_clamped >= 25.0:
            sim["frecuencia_tormentas_extremas"] = float(
                min(10, int(round(sim["frecuencia_tormentas_extremas"])) + 1)
            )
        elif rain_delta_clamped <= -25.0:
            sim["frecuencia_tormentas_extremas"] = float(
                max(0, int(round(sim["frecuencia_tormentas_extremas"])) - 1)
            )

        # Si el usuario no fijó un override manual de humedad, acoplar físicamente la
        # recarga/secado que esa lluvia produce sobre el perfil para no romper el árbol
        if not has_manual_moisture:
            sim["gwetroot_saturacion_pct"] = round(
                _clamp(sim["gwetroot_saturacion_pct"] + 0.35 * rain_delta_clamped, 5.0, 100.0),
                2,
            )
            sim["gwettop_saturacion_pct"] = round(
                _clamp(sim["gwettop_saturacion_pct"] + 0.45 * rain_delta_clamped, 5.0, 100.0),
                2,
            )
            sim["tendencia_humedad_15d_pct"] = round(
                _clamp(sim["tendencia_humedad_15d_pct"] + 0.20 * rain_delta_clamped, -40.0, 40.0),
                2,
            )

    # 2. Override manual de humedad en zona radicular (0% a 100%)
    if has_manual_moisture:
        old_root = sim["gwetroot_saturacion_pct"]
        new_root = _clamp(float(override_humedad_radicular_pct), 0.0, 100.0)
        delta_root = new_root - old_root

        sim["gwetroot_saturacion_pct"] = round(new_root, 2)
        # Acompañar humedad superficial y tendencia de 15d para evitar falsas alarmas
        # de desacople superficial/profundo cuando el usuario simula perfil recargado o seco
        sim["gwettop_saturacion_pct"] = round(
            _clamp(sim["gwettop_saturacion_pct"] + 0.65 * delta_root, 5.0, 100.0),
            2,
        )
        sim["tendencia_humedad_15d_pct"] = round(
            _clamp(sim["tendencia_humedad_15d_pct"] + 0.30 * delta_root, -40.0, 40.0),
            2,
        )

    return sim


def compute_hybrid_final_score(
    s_hidroclimatico: float,
    s_suelo: float,
    objetivo_productor: ProducerObjective = "equilibrio",
) -> float:
    """Calcula el Score Final combinando ambos pilares + penalización por factor limitante (< 35)."""
    if objetivo_productor not in OBJECTIVE_WEIGHTS:
        raise ValueError(
            f"Objetivo '{objetivo_productor}' inválido. Opciones: {list(OBJECTIVE_WEIGHTS)}"
        )

    w_clima, w_suelo = OBJECTIVE_WEIGHTS[objetivo_productor]
    linear_score = (w_clima * float(s_hidroclimatico)) + (w_suelo * float(s_suelo))

    min_pillar = min(float(s_hidroclimatico), float(s_suelo))
    penalty = 0.0
    if min_pillar < LIMITING_PILLAR_THRESHOLD:
        deficit = LIMITING_PILLAR_THRESHOLD - min_pillar
        penalty = min(LIMITING_PILLAR_MAX_PENALTY, deficit * LIMITING_PILLAR_PENALTY_SLOPE)

    return round(_clamp(linear_score - penalty, 0.0, 100.0), 1)


def classify_crop_risk(s_hidroclimatico: float, s_suelo: float) -> CropRiskLevel:
    """Riesgo del cultivo (ML-8, escala MAGyP: 50 = año normal).

    - Por clima y agua, según el puntaje hidroclimático esperado: ``critico`` < 40,
      ``alto`` < 45, ``medio`` < 50, ``bajo`` desde 50 (``HYDRO_RISK_THRESHOLDS``).
    - Por suelo: con ``s_suelo`` < 35 (por ejemplo, repetir soja en pendiente) es al menos ``alto``.

    El escalón por P10 del ensemble se aplica aparte (``escalate_risk_level``).
    """
    critico, alto, medio = HYDRO_RISK_THRESHOLDS
    hidro = float(s_hidroclimatico)
    if hidro < critico:
        nivel: CropRiskLevel = "critico"
    elif hidro < alto:
        nivel = "alto"
    elif hidro < medio:
        nivel = "medio"
    else:
        nivel = "bajo"
    if float(s_suelo) < SOIL_RISK_THRESHOLD and RISK_LEVELS.index(nivel) < RISK_LEVELS.index("alto"):
        nivel = "alto"
    return nivel


# ---------------------------------------------------------------------------
# ML-5: helpers del ensemble de años análogos
# ---------------------------------------------------------------------------


def weighted_percentile(
    values: Sequence[float] | np.ndarray,
    q: float,
    weights: Sequence[float] | np.ndarray | None = None,
) -> float:
    """Percentil ``q`` (0-100) con pesos opcionales.

    Sin pesos (o con pesos iguales) coincide con ``numpy.percentile(method="linear")``:
    la posición de cada valor ordenado es ``(peso acumulado anterior) / (peso total menos el
    último)``, que con pesos iguales da ``(i - 1) / (n - 1)``.
    """
    vals = np.asarray(values, dtype=float)
    if vals.size == 0:
        raise ValueError("weighted_percentile requiere al menos un valor")
    if weights is None:
        return float(np.percentile(vals, q))

    w = np.asarray(weights, dtype=float)
    if w.shape != vals.shape:
        raise ValueError("values y weights deben tener el mismo largo")
    order = np.argsort(vals, kind="stable")
    vals, w = vals[order], w[order]
    if vals.size == 1:
        return float(vals[0])
    cum_before = np.cumsum(w) - w
    denom = cum_before[-1]
    if denom <= 0.0:  # todo el peso en el valor más alto
        return float(vals[-1])
    return float(np.interp(q / 100.0, cum_before / denom, vals))


def escalate_risk_level(
    riesgo: CropRiskLevel,
    p10: float,
    threshold: float = CRITICAL_HYDRO_THRESHOLD,
) -> CropRiskLevel:
    """Sube un nivel de riesgo (bajo → medio → alto → critico) si el P10 cae en zona crítica."""
    if p10 >= threshold:
        return riesgo
    idx = RISK_LEVELS.index(riesgo)
    return RISK_LEVELS[min(idx + 1, len(RISK_LEVELS) - 1)]


def _validate_ensemble_inputs(
    features_actuales: Mapping[str, Any],
    escenarios_historicos: Sequence[Mapping[str, Any]],
    pesos: Sequence[float] | None,
) -> tuple[list[Mapping[str, Any]], np.ndarray | None]:
    """Valida las entradas del ensemble y descarta los escenarios con peso 0.

    Devuelve los escenarios efectivos y sus pesos (``None`` si no se pasaron pesos).
    """
    faltantes = [f for f in CURRENT_FEATURES if f not in features_actuales]
    if faltantes:
        raise ValueError(f"features_actuales incompleto, faltan: {faltantes}")
    if not escenarios_historicos:
        raise ValueError("escenarios_historicos no puede estar vacío")
    for i, esc in enumerate(escenarios_historicos):
        faltan_esc = [f for f in REQUIRED_FUTURE_FEATURES if f not in esc]
        if faltan_esc:
            raise ValueError(f"escenario {i} incompleto, faltan: {faltan_esc}")

    if pesos is None:
        return list(escenarios_historicos), None

    w = np.asarray(pesos, dtype=float)
    if w.shape != (len(escenarios_historicos),):
        raise ValueError("pesos debe tener un valor por escenario")
    if not np.all(np.isfinite(w)) or np.any(w < 0.0):
        raise ValueError("pesos debe contener valores finitos y no negativos")
    if float(w.sum()) <= 0.0:
        raise ValueError("la suma de pesos debe ser mayor a 0")
    keep = w > 0.0
    escenarios = [esc for esc, k in zip(escenarios_historicos, keep) if k]
    return escenarios, w[keep]


def representative_scenario(escenarios_historicos: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """Escenario representativo: mediana por feature futura, redondeada a entero.

    Se usa para lo que necesita un único vector (anomalías, factores clave, clasificadores
    de riesgo térmico y de escorrentía) cuando la predicción es por ensemble.
    """
    out = {
        f: float(round(float(np.median([float(esc[f]) for esc in escenarios_historicos]))))
        for f in REQUIRED_FUTURE_FEATURES
    }
    lluvias = [float(e["lluvia_periodo_critico_mm"]) for e in escenarios_historicos if "lluvia_periodo_critico_mm" in e]
    if lluvias:
        out["lluvia_periodo_critico_mm"] = round(float(np.median(lluvias)), 1)
    return out


# Redacción en prosa: nombre sin paréntesis y artículo con el género correcto.
_NOMBRE_PROSA: dict[str, str] = {
    "vicia_cobertura": "Vicia de cobertura",
    "avena_cobertura": "Avena de cobertura",
}
_CULTIVOS_FEMENINOS: frozenset[str] = frozenset(
    {"cebada", "vicia_cobertura", "avena_cobertura", "camelina", "soja_primera", "soja_segunda"}
)


def crop_prose_name(crop_id: str) -> str:
    """Nombre del cultivo para usar dentro de una oración (sin paréntesis)."""
    return _NOMBRE_PROSA.get(crop_id, get_crop_profile(crop_id).nombre_legible)


def crop_with_article(crop_id: str) -> str:
    """'el Trigo', 'la Vicia de cobertura'."""
    articulo = "la" if crop_id in _CULTIVOS_FEMENINOS else "el"
    return f"{articulo} {crop_prose_name(crop_id)}"


def build_ensemble_risk_sentence(dist: Mapping[str, Any], oni_actual: float | None = None) -> str:
    """Oración de riesgo del ganador para ``explicacion`` a partir de su distribución.

    Con ``oni_actual`` aclara de qué fase ENSO son los años análogos (ML-12).
    """
    texto = _ensemble_risk_sentence(dist)
    if oni_actual is None:
        return texto
    fase = NOMBRE_FASE[fase_enso(float(oni_actual))]
    return f"Hoy rige {fase} (ONI {float(oni_actual):+.1f}); se comparó con los años de esa misma fase. {texto}"


def _ensemble_risk_sentence(dist: Mapping[str, Any]) -> str:
    n = int(dist["anios_evaluados"])
    k = int(dist["anios_desfavorables"])
    umbral = float(dist["umbral_desfavorable"])
    peor = dist["peor_escenario"]

    causas: list[str] = []
    if int(peor["frecuencia_estres_termico"]) > 0:
        causas.append(f"{int(peor['frecuencia_estres_termico'])} días con más de 34 °C")
    if int(peor["frecuencia_riesgo_helada"]) > 0:
        causas.append(f"{int(peor['frecuencia_riesgo_helada'])} heladas")
    if int(peor["frecuencia_tormentas_extremas"]) > 0:
        causas.append(f"{int(peor['frecuencia_tormentas_extremas'])} tormentas de más de 50 mm")
    causa_txt = f", con {' y '.join(causas)}" if causas else ""
    anio_txt = f"como en {peor['anio']}" if peor.get("anio") is not None else "histórico"

    if k > 0:
        return (
            f"En {k} de {n} años análogos el puntaje hidroclimático quedó por debajo de "
            f"{umbral:.0f}; el peor escenario ({anio_txt}{causa_txt}) lo lleva a {float(peor['score']):.0f}."
        )
    return (
        f"En los {n} años análogos el puntaje hidroclimático se mantuvo en {umbral:.0f} o más; "
        f"el peor escenario ({anio_txt}{causa_txt}) da {float(peor['score']):.0f}."
    )


def detect_physical_anomalies(
    features: dict[str, float],
    campana: Campaign = "verano",
    cultivo_anterior: str | None = None,
) -> list[dict[str, str]]:
    """Detecta hasta 6 anomalías físicas basadas en evidencia satelital (CONTEXT.md Sección 4.4)."""
    anomalies: list[dict[str, str]] = []

    gwetroot = float(features["gwetroot_saturacion_pct"])
    gwettop = float(features["gwettop_saturacion_pct"])
    tendencia_15d = float(features["tendencia_humedad_15d_pct"])
    anomalia_lluvia = float(features["anomalia_lluvia_90d_pct"])
    tormentas = int(round(float(features["frecuencia_tormentas_extremas"])))
    estres_termico = int(round(float(features["frecuencia_estres_termico"])))
    riesgo_helada = int(round(float(features["frecuencia_riesgo_helada"])))
    aridez = float(features["indice_aridez_evaporativa"])
    pendiente = float(features["pendiente_terreno_pct"])
    arcilla = float(features["textura_arcilla_pct"])

    # 1. Déficit Hídrico Radicular
    if gwetroot < 40.0 and anomalia_lluvia <= -12.0:
        sev: AnomalySeverity = (
            "alta" if (gwetroot <= 35.0 or anomalia_lluvia <= -20.0) else "media"
        )
        anomalies.append(
            {
                "tipo": "deficit_hidrico_radicular",
                "severidad": sev,
                "evidencia": (
                    f"Reserva radicular en {gwetroot:.0f}% con anomalía de lluvias de "
                    f"{anomalia_lluvia:+.1f}% en los últimos 90 días (NASA POWER / SMAP)."
                ),
            }
        )
    elif gwetroot < 30.0:
        anomalies.append(
            {
                "tipo": "deficit_hidrico_radicular",
                "severidad": "alta" if gwetroot < 24.0 else "media",
                "evidencia": (
                    f"Reserva radicular crítica en {gwetroot:.0f}% detectada por "
                    f"asimilación satelital NASA POWER / SMAP."
                ),
            }
        )

    # 2. Pulso de Secado Rápido (Flash Drought Onset)
    if tendencia_15d <= -10.0 and (aridez <= 0.75 or estres_termico >= 4 or tendencia_15d <= -14.0):
        sev = "alta" if (tendencia_15d <= -15.0 or aridez < 0.55) else "media"
        anomalies.append(
            {
                "tipo": "pulso_secado_rapido",
                "severidad": sev,
                "evidencia": (
                    f"Caída de humedad de {tendencia_15d:+.1f}% en los últimos 15 días "
                    f"con índice de aridez evaporativa de {aridez:.2f} (EVPTRNS / NASA POWER)."
                ),
            }
        )

    # 3. Trampa de "Falsa Recarga" Superficial (GWETTOP vs GWETROOT)
    if gwettop >= 58.0 and gwetroot <= 36.0 and (gwettop - gwetroot) >= 20.0:
        sev = "alta" if gwetroot < 30.0 else "media"
        anomalies.append(
            {
                "tipo": "falsa_recarga_superficial",
                "severidad": sev,
                "evidencia": (
                    f"Capa superficial húmeda (GWETTOP {gwettop:.0f}%), pero el perfil "
                    f"profundo sigue seco (GWETROOT {gwetroot:.0f}%): sin reserva para sostener "
                    f"cultivos demandantes si se cortan las lluvias."
                ),
            }
        )

    # 4. Peligro de Escorrentía y Erosión por Lluvias Torrenciales + Pendiente SRTM
    low_residue_prev = (cultivo_anterior or "").strip().lower() in {
        "soja_primera",
        "soja_segunda",
        "girasol",
    }
    if (pendiente >= 1.5 and tormentas >= 1) or (pendiente >= 2.0 and low_residue_prev):
        sev = "alta" if (pendiente >= 2.2 or (pendiente >= 1.8 and tormentas >= 2)) else "media"
        anomalies.append(
            {
                "tipo": "riesgo_escorrentia_erosion",
                "severidad": sev,
                "evidencia": (
                    f"Pendiente topográfica de {pendiente:.1f}% (NASA SRTM 30m) con "
                    f"{tormentas} evento(s) de lluvia torrencial (> 50 mm/día, GPM/POWER) "
                    f"incrementa pérdida de agua por escorrentía y lavado de suelo."
                ),
            }
        )

    # 5. Exceso Hídrico / Riesgo de Anegamiento
    if gwetroot >= 82.0 or (anomalia_lluvia >= 35.0 and arcilla >= 32.0 and pendiente < 0.6):
        sev = "alta" if gwetroot >= 88.0 else "media"
        anomalies.append(
            {
                "tipo": "exceso_hidrico_anegamiento",
                "severidad": sev,
                "evidencia": (
                    f"Saturación radicular elevada ({gwetroot:.0f}%) y anomalía de lluvias "
                    f"de {anomalia_lluvia:+.1f}% en suelo con {arcilla:.1f}% de arcilla "
                    f"y pendiente de {pendiente:.1f}%."
                ),
            }
        )

    # 6. Estrés Térmico Crítico (Verano) o Riesgo de Helada (Invierno/Temprana)
    nivel_termico = classify_summer_thermal_risk(estres_termico)
    if campana == "verano" and nivel_termico in ("alto", "critico"):
        sev = "alta" if nivel_termico == "critico" else "media"
        anomalies.append(
            {
                "tipo": "estres_termico_critico",
                "severidad": sev,
                "evidencia": (
                    f"Riesgo térmico {nivel_termico}: {estres_termico} días esperados con "
                    f"T2M_MAX > 34°C en el período crítico del cultivo (años análogos de NASA POWER)."
                ),
            }
        )
    elif campana == "invierno" and riesgo_helada >= 16:
        sev = "alta" if riesgo_helada >= 22 else "media"
        anomalies.append(
            {
                "tipo": "riesgo_helada_severa",
                "severidad": sev,
                "evidencia": (
                    f"Exposición térmica invernal con {riesgo_helada} días esperados "
                    f"con T2M_MIN < 2°C (NASA POWER)."
                ),
            }
        )

    return anomalies


class AgroPredictor:
    """Motor híbrido de inferencia agroclimática (ML-2) y matriz de rotación (ML-3)."""

    def __init__(self, model_path: Path | str = DEFAULT_MODEL_PATH) -> None:
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"No se encontró el artefacto del modelo en '{self.model_path}'. "
                f"Ejecutá primero 'backend/ml/train_baseline.py'."
            )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", InconsistentVersionWarning)
            bundle: dict[str, Any] = joblib.load(self.model_path)
        self.model = bundle["model"]
        # Asegurar ejecución single-thread sin overhead de procesos para latencia < 15 ms
        if hasattr(self.model, "n_jobs"):
            self.model.set_params(n_jobs=1)

        self.model_name: str = bundle["model_name"]
        self.feature_columns: list[str] = list(bundle["feature_columns"])
        self.crops_catalog: dict[str, Any] = bundle["crops_catalog"]
        self.feature_importances: dict[str, Any] = bundle["feature_importances"]
        self.feature_baselines: dict[str, Any] = bundle["feature_baselines"]
        self.training_metrics: dict[str, Any] = bundle.get("metrics", {})
        self.model_version: str = bundle.get("model_version", "ml2-fao")
        # ML-10: cultivos con rinde real que el modelo sabe puntuar (todos, en bundles previos).
        self.cultivos_entrenados: frozenset[str] = frozenset(
            bundle.get("cultivos_entrenados") or self.crops_catalog["by_name"]
        )
        # Columnas numéricas en el orden del bundle (la última es el cultivo codificado).
        self._numeric_cols: list[str] = self.feature_columns[:-1]

    # ------------------------------------------------------------------
    # Armado de filas
    # ------------------------------------------------------------------
    @staticmethod
    def _anio_campana_para(campana: Campaign, fecha: date) -> int:
        """Año de la campaña ``campana`` más próxima a ``fecha`` (la vigente o la siguiente)."""
        if cal.campana_de(fecha) == campana:
            return cal.anio_campana(fecha)
        return fecha.year if campana == "verano" or fecha.month < 7 else fecha.year + 1

    def _contexto_cultivo(self, crop: str, campana: Campaign, fecha: date) -> dict[str, float]:
        anio = self._anio_campana_para(campana, fecha)
        return {"dias_hasta_siembra": float(cal.dias_hasta_siembra(crop, fecha, anio))}

    def fuera_de_ventana_siembra(self, crop: str, campana: Campaign, fecha: date) -> bool:
        """La siembra del cultivo ya terminó en la campaña vigente (se marca, no se excluye)."""
        return fecha > cal.fin_siembra(crop, self._anio_campana_para(campana, fecha))

    def motivo_no_sembrable(
        self, crop: str, campana: Campaign, fecha: date, cultivo_anterior: str | None
    ) -> str | None:
        """Por qué no se puede sembrar ``crop`` hoy en este lote (None si se puede).

        ML-11: lote ocupado por el cultivo de invierno anterior; ML-7: siembra ya terminada.
        """
        motivo = motivo_lote_ocupado(campana, cultivo_anterior, crop)
        if motivo is not None:
            return motivo
        if self.fuera_de_ventana_siembra(crop, campana, fecha):
            fin = cal.fin_siembra(crop, self._anio_campana_para(campana, fecha))
            return f"La ventana de siembra de {crop_prose_name(crop)} terminó el {fin:%d/%m}."
        return None

    def _default(self, feat: str, campana: Campaign) -> float:
        if feat == "oni_actual":
            return ONI_NEUTRO
        base = self.feature_baselines.get("by_campana", {}).get(campana, {}).get(feat)
        if base is None:
            base = self.feature_baselines.get("global", {}).get(feat)
        if base is not None:
            return float(base["mean"])
        if feat == "lluvia_periodo_critico_mm":
            return DEFAULT_LLUVIA_CRITICA_MM
        raise KeyError(f"Falta la feature '{feat}' y no hay valor por defecto")

    def _fila(self, vec: Mapping[str, Any], crop: str, campana: Campaign) -> list[float]:
        fila = [float(vec[c]) if c in vec and vec[c] is not None else self._default(c, campana) for c in self._numeric_cols]
        return fila + [float(self.crops_catalog["by_name"][crop]["id"])]

    def predict_hydroclimatic_batch(
        self,
        features: dict[str, float],
        campana: Campaign,
        *,
        fecha_corte: date | None = None,
        oni_actual: float | None = None,
    ) -> dict[str, float]:
        """Predice S_hidroclimatico (acotado a [0.0, 100.0]) en un único batch para la campaña.

        ``features`` trae las actuales y las del período crítico; ``dias_hasta_siembra`` se
        calcula por cultivo con ``fecha_corte`` (hoy si no se pasa).
        """
        fecha = fecha_corte or datetime.now(timezone.utc).date()
        crops = get_crops_for_campaign(campana)
        ml_crops, relativos = self._separar_cultivos(crops)
        base = dict(features)
        if oni_actual is not None:
            base["oni_actual"] = oni_actual
        X_batch = np.asarray(
            [self._fila({**base, **self._contexto_cultivo(c, campana, fecha)}, c, campana) for c in ml_crops],
            dtype=float,
        )
        scores = dict(zip(ml_crops, self._predict_clipped(X_batch)))
        referencia = np.asarray([np.mean([scores[c] for c in ml_crops])])
        for crop in relativos:
            scores[crop] = self._score_relativo(crop, referencia, ml_crops)[0]
        gwetroot = float(base["gwetroot_saturacion_pct"])
        return {
            crop: round(_clamp(float(scores[crop]) - penalizacion_demanda_hidrica(crop, gwetroot)), 1)
            for crop in crops
        }

    def _separar_cultivos(self, crops: Sequence[str]) -> tuple[list[str], list[str]]:
        """(cultivos que puntúa el modelo, cultivos sin rinde MAGyP que se puntúan relativos)."""
        ml_crops = [c for c in crops if c in self.cultivos_entrenados]
        if not ml_crops:
            raise ValueError("La campaña no tiene cultivos entrenados con rinde real")
        return ml_crops, [c for c in crops if c not in self.cultivos_entrenados]

    @staticmethod
    def _score_relativo(crop: str, referencia: np.ndarray, ref_crops: Sequence[str]) -> np.ndarray:
        """Puntaje de un cultivo sin rinde MAGyP a partir de los cultivos con rinde real.

        FAO-56: la pérdida relativa de rinde es ``Ky`` × el déficit relativo de agua. Con el mismo
        déficit, el desvío respecto de un año normal escala con ``Ky_cultivo / Ky_referencia``
        (las coberturas, con Ky menor, se alejan menos de 50 que el trigo o la cebada).
        """
        ky_ref = float(np.mean([FAO_CROP_CATALOG[c]["ky_drought"] for c in ref_crops]))
        factor = float(FAO_CROP_CATALOG[crop]["ky_drought"]) / ky_ref
        return np.clip(PUNTAJE_ANIO_NORMAL + factor * (referencia - PUNTAJE_ANIO_NORMAL), 0.0, 100.0)

    def _predict_clipped(self, X: np.ndarray) -> np.ndarray:
        """Inferencia cruda del modelo acotada a [0, 100] (compartida por batch y ensemble)."""
        if hasattr(self.model, "_raw_predict") and hasattr(self.model, "_loss"):
            # HistGradientBoostingRegressor: forzar n_threads=1 en Cython evita el
            # overhead de sincronización de OpenMP en lotes chicos.
            raw_preds = self.model._loss.link.inverse(
                self.model._raw_predict(X, n_threads=1).ravel()
            )
        else:
            raw_preds = self.model.predict(X)
        return np.clip(np.asarray(raw_preds, dtype=float), 0.0, 100.0)

    def predict_ensemble(
        self,
        features_actuales: Mapping[str, Any],
        escenarios_historicos: Sequence[Mapping[str, Any]] | Mapping[str, Sequence[Mapping[str, Any]]],
        campana: Campaign,
        *,
        pesos: Sequence[float] | None = None,
        umbral_desfavorable: float = DEFAULT_UMBRAL_DESFAVORABLE,
        simulacion_what_if: Mapping[str, float | None] | None = None,
        fecha_corte: date | None = None,
        oni_actual: float | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Ensemble de años análogos (ML-5, por cultivo desde ML-7).

        ``escenarios_historicos`` puede ser:
        - una lista común a todos los cultivos (ML-5), con ``pesos`` opcionales; o
        - un dict ``{cultivo: [escenario, ...]}`` con los años análogos del **período crítico**
          de cada cultivo (``ml/escenarios.py``); cada escenario puede traer su ``peso`` (ONI).

        Para cada escenario fija las ``features_actuales``, reemplaza las del período crítico por
        las de ese año, agrega ``dias_hasta_siembra`` (desde ``fecha_corte``) y ``oni_actual`` y
        predice. Devuelve, por cultivo: ``promedio`` (ponderado), ``p10``, ``p90``,
        ``anios_desfavorables``, ``anios_evaluados``, ``umbral_desfavorable`` y ``peor_escenario``.
        """
        fecha = fecha_corte or datetime.now(timezone.utc).date()
        crops = get_crops_for_campaign(campana)
        ml_crops, relativos = self._separar_cultivos(crops)
        por_cultivo: dict[str, tuple[list[Mapping[str, Any]], np.ndarray | None]] = {}
        if isinstance(escenarios_historicos, Mapping):
            for crop in ml_crops:
                lista = list(escenarios_historicos.get(crop, []))
                w = [float(e.get("peso", 1.0)) for e in lista] if lista else None
                por_cultivo[crop] = _validate_ensemble_inputs(features_actuales, lista, w)
        else:
            validados = _validate_ensemble_inputs(features_actuales, escenarios_historicos, pesos)
            por_cultivo = {crop: validados for crop in ml_crops}

        override_humedad = None
        variacion_lluvia = None
        if simulacion_what_if:
            override_humedad = simulacion_what_if.get("override_humedad_radicular_pct")
            variacion_lluvia = simulacion_what_if.get("variacion_lluvia_esperada_pct")
        apply_sim = override_humedad is not None or bool(variacion_lluvia)

        current = {f: float(features_actuales[f]) for f in CURRENT_FEATURES}
        if oni_actual is not None:
            current["oni_actual"] = float(oni_actual)
        elif "oni_actual" in features_actuales:
            current["oni_actual"] = float(features_actuales["oni_actual"])

        rows: list[list[float]] = []
        cortes: list[tuple[str, int, int]] = []
        gwetroot = current["gwetroot_saturacion_pct"]
        for crop in ml_crops:
            escenarios, _ = por_cultivo[crop]
            contexto = self._contexto_cultivo(crop, campana, fecha)
            desde = len(rows)
            for esc in escenarios:
                vec: dict[str, float] = {**current, **{f: float(esc[f]) for f in FUTURE_FEATURES if f in esc}, **contexto}
                if "lluvia_periodo_critico_mm" not in vec:
                    vec["lluvia_periodo_critico_mm"] = self._default("lluvia_periodo_critico_mm", campana)
                if apply_sim:
                    vec = apply_what_if_simulation(
                        base_features=vec,
                        override_humedad_radicular_pct=override_humedad,
                        variacion_lluvia_esperada_pct=variacion_lluvia,
                    )
                    gwetroot = vec["gwetroot_saturacion_pct"]
                rows.append(self._fila(vec, crop, campana))
            cortes.append((crop, desde, len(rows)))

        preds = self._predict_clipped(np.asarray(rows, dtype=float))
        crudos = {crop: preds[desde:hasta] for crop, desde, hasta in cortes}

        # ML-10: cultivos sin rinde MAGyP = referencia de los cultivos reales escalada por Ky.
        # Año a año si los cultivos de referencia tienen la misma cantidad de años análogos; si
        # no, se usan solo los que coinciden con el que más años tiene.
        if relativos:
            base_ref = max(ml_crops, key=lambda c: len(crudos[c]))
            mismos = [c for c in ml_crops if len(crudos[c]) == len(crudos[base_ref])]
            referencia = np.mean([crudos[c] for c in mismos], axis=0)
            for crop in relativos:
                crudos[crop] = self._score_relativo(crop, referencia, mismos)
                por_cultivo[crop] = por_cultivo[base_ref]

        result: dict[str, dict[str, Any]] = {}
        for crop in crops:
            escenarios, weights = por_cultivo[crop]
            scores = np.clip(crudos[crop] - penalizacion_demanda_hidrica(crop, gwetroot), 0.0, 100.0)
            promedio = float(np.average(scores, weights=weights))
            worst_idx = int(np.argmin(scores))
            worst = escenarios[worst_idx]
            result[crop] = {
                "promedio": round(promedio, 1),
                "p10": round(weighted_percentile(scores, 10.0, weights), 1),
                "p90": round(weighted_percentile(scores, 90.0, weights), 1),
                "anios_desfavorables": int(np.sum(scores < umbral_desfavorable)),
                "anios_evaluados": len(escenarios),
                "umbral_desfavorable": float(umbral_desfavorable),
                "peor_escenario": {
                    "anio": worst.get("anio"),
                    "score": round(float(scores[worst_idx]), 1),
                    **{f: int(round(float(worst[f]))) for f in REQUIRED_FUTURE_FEATURES},
                },
            }
        return result

    def build_key_ml_factors(
        self,
        winner_crop: str,
        campana: Campaign,
        features: dict[str, float],
        soil_eval: SoilEvaluationResult,
    ) -> list[str]:
        """Construye los Top 3 factores_clave_ml combinando baselines por campaña,
        importancias por permutación del cultivo y factores topográficos/edáficos.
        """
        campaign_baselines = self.feature_baselines.get("by_campana", {}).get(
            campana, self.feature_baselines["global"]
        )
        crop_imp = self.feature_importances.get("per_crop", {}).get(
            winner_crop, self.feature_importances["global"]
        )

        gwetroot = float(features["gwetroot_saturacion_pct"])
        gwettop = float(features["gwettop_saturacion_pct"])
        tendencia = float(features["tendencia_humedad_15d_pct"])
        anomalia_lluvia = float(features["anomalia_lluvia_90d_pct"])
        tormentas = int(round(float(features["frecuencia_tormentas_extremas"])))
        estres = int(round(float(features["frecuencia_estres_termico"])))
        helada = int(round(float(features["frecuencia_riesgo_helada"])))
        aridez = float(features["indice_aridez_evaporativa"])
        pendiente = float(features["pendiente_terreno_pct"])
        arcilla = float(features["textura_arcilla_pct"])

        def _z_dev(feat_name: str) -> float:
            stats = campaign_baselines.get(feat_name, {"mean": 0.0, "std": 1.0})
            std = max(float(stats.get("std", 1.0)), 1e-4)
            return abs(float(features[feat_name]) - float(stats.get("mean", 0.0))) / std

        candidates: list[tuple[float, str]] = []

        # 1. Factor de Humedad Radicular (GWETROOT - SMAP/GLDAS)
        root_weight = float(crop_imp.get("gwetroot_saturacion_pct", 0.20))
        root_salience = (0.35 + root_weight) * (1.0 + _z_dev("gwetroot_saturacion_pct"))
        if gwetroot <= 40.0:
            root_text = (
                f"Baja saturación hídrica en zona radicular detectada por NASA ({gwetroot:.0f}%)"
            )
            root_salience += 1.5
        elif gwetroot >= 80.0:
            root_text = (
                f"Alta saturación hídrica en zona radicular detectada por NASA ({gwetroot:.0f}%)"
            )
            root_salience += 1.3
        else:
            root_text = (
                f"Reserva hídrica en zona radicular en rango adecuado ({gwetroot:.0f}%, NASA SMAP/GLDAS)"
            )
        candidates.append((root_salience, root_text))

        # 2. Factor Topográfico / Edáfico de Rotación (SRTM + Cultivo Anterior)
        prev_crop = soil_eval.cultivo_anterior
        prev_label = CROP_PROFILES[prev_crop].nombre_legible if prev_crop in CROP_PROFILES else None
        winner_profile = get_crop_profile(winner_crop)
        if pendiente >= 1.2:
            if prev_crop in {"soja_primera", "soja_segunda", "girasol"} and winner_profile.familia == "graminea":
                slope_text = (
                    f"Pendiente de {pendiente:.1f}% (SRTM) requiere rastrojo de gramínea "
                    f"tras {prev_label} para frenar escorrentía"
                )
            else:
                slope_text = (
                    f"Pendiente de {pendiente:.1f}% (SRTM) exige cobertura radicular activa "
                    f"para maximizar infiltración y controlar erosión"
                )
            slope_salience = 2.1 + (pendiente * 0.35)
            candidates.append((slope_salience, slope_text))
        elif soil_eval.factores_suelo:
            candidates.append((1.45, soil_eval.factores_suelo[0]))

        # 3. Factor de Anomalía de Lluvias de 90 días (GPM/IMERG/POWER)
        rain_weight = float(crop_imp.get("anomalia_lluvia_90d_pct", 0.08))
        if abs(anomalia_lluvia) >= 10.0:
            rain_salience = (0.40 + rain_weight) * (1.0 + _z_dev("anomalia_lluvia_90d_pct")) + 1.1
            rain_text = f"Anomalía de lluvias de {anomalia_lluvia:+.1f}% en los últimos 90 días"
            candidates.append((rain_salience, rain_text))

        # 4. Factor de Secado Rápido (15d) o Falsa Recarga Superficial
        if gwettop >= 58.0 and gwetroot <= 36.0:
            candidates.append(
                (
                    1.95,
                    f"Desacople hídrico: humedad superficial del {gwettop:.0f}% pero reserva profunda en {gwetroot:.0f}%",
                )
            )
        elif tendencia <= -10.0:
            candidates.append(
                (
                    1.75 + abs(tendencia) * 0.04,
                    f"Pulso de secado rápido ({tendencia:+.1f}% en 15 días) con índice de aridez {aridez:.2f}",
                )
            )

        # 5. Factor Térmico (Calor en verano / Heladas en invierno)
        if campana == "verano" and estres >= 6:
            heat_weight = float(crop_imp.get("frecuencia_estres_termico", 0.35))
            heat_salience = (0.25 + heat_weight) * (0.8 + _z_dev("frecuencia_estres_termico"))
            candidates.append(
                (
                    heat_salience,
                    f"Exposición a estrés térmico en período crítico ({estres} días esperados > 34°C)",
                )
            )
        elif campana == "invierno" and helada >= 10:
            frost_weight = float(crop_imp.get("frecuencia_riesgo_helada", 0.25))
            frost_salience = (0.25 + frost_weight) * (0.8 + _z_dev("frecuencia_riesgo_helada"))
            candidates.append(
                (
                    frost_salience,
                    f"Tolerancia a heladas requerida ({helada} días esperados < 2°C en campaña fina)",
                )
            )

        # 6. Factor de Tormentas Extremas o Textura Arcillosa
        if tormentas >= 2:
            candidates.append(
                (
                    1.35,
                    f"{tormentas} eventos de tormentas extremas (> 50 mm/día) aumentan pérdida por escorrentía",
                )
            )
        elif arcilla >= 34.0 or arcilla < 16.0:
            candidates.append(
                (
                    1.20,
                    f"Textura del suelo ({arcilla:.1f}% de arcilla, SoilGrids) condiciona retención y drenaje",
                )
            )

        # Garantizar al menos 3 factores ordenados por relevancia sin duplicados
        candidates.sort(key=lambda item: -item[0])
        selected: list[str] = []
        for _, text in candidates:
            if text not in selected:
                selected.append(text)
            if len(selected) == 3:
                break

        for factor in soil_eval.factores_suelo:
            if len(selected) >= 3:
                break
            if factor not in selected:
                selected.append(factor)

        return selected[:3]

    def build_explanation(
        self,
        winner_crop: str,
        runner_up_crop: str | None,
        ranking: list[dict[str, Any]],
        sub_scores_by_crop: dict[str, dict[str, float]],
        features: dict[str, float],
        cultivo_anterior: str | None,
        riesgo_por_cultivo: Mapping[str, str] | None = None,
    ) -> str:
        """Redacta la explicación agronómica transparente siguiendo el formato de CONTEXT.md.

        ``riesgo_por_cultivo`` (opcional): el contraste "riesgo crítico en floración" del Maíz
        Temprano solo se menciona si su riesgo es ``alto`` o ``critico``.
        """
        winner_subs = sub_scores_by_crop[winner_crop]

        alt_phrase = ""
        if runner_up_crop is not None:
            if winner_crop == "sorgo" and runner_up_crop == "maiz_tardio":
                alt_phrase = " (o Maíz Tardío precedido por Vicia)"
            else:
                alt_phrase = f" (o {crop_prose_name(runner_up_crop)} como alternativa)"

        gwetroot = float(features["gwetroot_saturacion_pct"])
        anomalia = float(features["anomalia_lluvia_90d_pct"])
        pendiente = float(features["pendiente_terreno_pct"])

        if gwetroot <= 40.0:
            moisture_desc = f"una reserva hídrica ajustada ({gwetroot:.0f}% de saturación radicular)"
        elif gwetroot >= 80.0:
            moisture_desc = f"un perfil con alta saturación hídrica ({gwetroot:.0f}% radicular)"
        else:
            moisture_desc = f"una disponibilidad hídrica radicular del {gwetroot:.0f}%"

        if anomalia < -5.0:
            rain_desc = f"un déficit de lluvias del {abs(anomalia):.0f}%"
        elif anomalia > 5.0:
            rain_desc = f"un excedente de lluvias del {anomalia:.0f}%"
        else:
            rain_desc = f"lluvias cercanas a la normal histórica ({anomalia:+.1f}%)"

        # Identificar cultivos de peor desempeño para contrastar el porqué
        # El peor entre los sembrables: los fuera de ventana van al final por fecha, no por aptitud.
        sembrables = [item for item in ranking if not item.get("motivo_no_sembrable")]
        lowest_crop = (sembrables or ranking)[-1]["cultivo"]
        contrast_parts: list[str] = []

        riesgo_maiz = (riesgo_por_cultivo or {}).get("maiz_temprano", "critico")
        if (
            "maiz_temprano" in sub_scores_by_crop
            and winner_crop != "maiz_temprano"
            and gwetroot <= 42.0
            and riesgo_maiz in ("alto", "critico")
        ):
            contrast_parts.append(f"{crop_with_article('maiz_temprano')} (riesgo crítico en floración)")

        prev_norm = (cultivo_anterior or "").strip().lower()
        # "Repetir" solo tiene sentido si el cultivo anterior es de la misma campaña.
        if prev_norm in sub_scores_by_crop and prev_norm != winner_crop:
            prev_prof = CROP_PROFILES[prev_norm]
            if prev_prof.aporte_rastrojo == "bajo":
                contrast_parts.append(
                    f"repetir {crop_prose_name(prev_norm)} (degradación de carbono y riesgo de erosión por suelo desnudo)"
                )
            else:
                contrast_parts.append(
                    f"repetir {crop_prose_name(prev_norm)} (penalización por monocultivo)"
                )
        elif lowest_crop != winner_crop:
            contrast_parts.append(f"{crop_with_article(lowest_crop)} (menor adaptación al escenario actual)")

        contrast_clause = ""
        if contrast_parts:
            contrastes = " o ".join(contrast_parts[:2])
            # Contracción obligatoria: "de el" -> "del"
            prep = "del " + contrastes[3:] if contrastes.startswith("el ") else "de " + contrastes
            contrast_clause = f"A diferencia {prep}, "
        sujeto = crop_with_article(winner_crop)
        if not contrast_clause:
            sujeto = sujeto[0].upper() + sujeto[1:]

        return (
            f"Recomendación: Sembrar {crop_prose_name(winner_crop)}{alt_phrase}. "
            f"Detectamos vía satélite {moisture_desc}, {rain_desc} y una pendiente del "
            f"{pendiente:.1f}% (SRTM). {contrast_clause}"
            f"{sujeto} ofrece un {winner_subs['hidroclimatico']:.0f}% "
            f"de aptitud hidroclimática y un {winner_subs['suelo']:.0f}% de beneficio edáfico "
            f"para proteger y recomponer la estructura del lote."
        )

    def predict_and_recommend(
        self,
        features: dict[str, float],
        campana: Campaign = "verano",
        cultivo_anterior: str | None = "soja_primera",
        objetivo_productor: ProducerObjective = "equilibrio",
        carbono_organico_g_kg: float | None = 18.4,
        phh2o: float | None = None,
        arena_pct: float | None = None,
        fecha_ultimo_dato_valido: str = "2026-11-08",
        ubicacion: dict[str, float] | None = None,
        simulacion_what_if: dict[str, float | None] | None = None,
        escenarios_historicos: Sequence[Mapping[str, Any]] | Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
        umbral_desfavorable: float = DEFAULT_UMBRAL_DESFAVORABLE,
        *,
        fecha_corte: date | None = None,
        oni_actual: float | None = None,
    ) -> dict[str, Any]:
        """Ejecuta el pipeline completo de decisión (ML + Matriz Agronómica + Anomalías).

        Devuelve un diccionario compatible 1:1 con el contrato JSON de ``POST /api/v1/simulate``
        (CONTEXT.md Sección 5) más los metadatos enriquecidos ``comparacion_estrategias``
        y ``cobertura_12_meses`` de ML-3.

        Con ``escenarios_historicos`` (ML-5, salida de ``BACK-6``), ``features`` solo necesita
        las 8 features actuales: S_hidro es el promedio del ensemble, el riesgo sube un nivel si
        el P10 cae en zona crítica y la respuesta agrega ``distribucion_hidroclimatica`` y los
        campos del ensemble en ``ranking_cultivos``. Sin escenarios, el comportamiento y el
        contrato son los de ML-4.

        ML-7: ``escenarios_historicos`` puede ser ``{cultivo: [...]}`` (período crítico de cada
        cultivo, con ``peso`` por ONI). ``fecha_corte`` (por defecto ``fecha_ultimo_dato_valido``)
        define ``dias_hasta_siembra`` y el flag ``fuera_de_ventana_siembra`` de cada cultivo.
        """
        fecha = fecha_corte or date.fromisoformat(str(fecha_ultimo_dato_valido)[:10])
        override_humedad = None
        variacion_lluvia = None
        if simulacion_what_if:
            override_humedad = simulacion_what_if.get("override_humedad_radicular_pct")
            variacion_lluvia = simulacion_what_if.get("variacion_lluvia_esperada_pct")

        # 1-2. Inferencia de S_hidroclimatico (Pilar 1): ensemble de años análogos (ML-5)
        # o vector único (ML-4). El What-If se aplica preservando la coherencia interna.
        ensemble: dict[str, dict[str, Any]] | None = None
        if escenarios_historicos is not None:
            ensemble = self.predict_ensemble(
                features_actuales=features,
                escenarios_historicos=escenarios_historicos,
                campana=campana,
                umbral_desfavorable=umbral_desfavorable,
                simulacion_what_if=simulacion_what_if,
                fecha_corte=fecha,
                oni_actual=oni_actual,
            )
            hydro_scores = {crop: dist["promedio"] for crop, dist in ensemble.items()}
            # Vector representativo (mediana de los escenarios) para anomalías y explicación
            base_vector: dict[str, float] = {
                **{f: float(features[f]) for f in CURRENT_FEATURES},
                **representative_scenario(
                    [e for lista in escenarios_historicos.values() for e in lista]
                    if isinstance(escenarios_historicos, Mapping)
                    else escenarios_historicos
                ),
            }
        else:
            base_vector = dict(features)

        effective_features = apply_what_if_simulation(
            base_features=base_vector,
            override_humedad_radicular_pct=override_humedad,
            variacion_lluvia_esperada_pct=variacion_lluvia,
        )
        if ensemble is None:
            hydro_scores = self.predict_hydroclimatic_batch(
                effective_features, campana=campana, fecha_corte=fecha, oni_actual=oni_actual
            )

        # 3. Evaluación determinística de S_suelo y cobertura 12m (Pilar 2 - ML-3)
        pendiente = float(effective_features["pendiente_terreno_pct"])
        arcilla = float(effective_features["textura_arcilla_pct"])
        soil_evals = evaluate_campaign_soil(
            campana=campana,
            cultivo_anterior=cultivo_anterior,
            carbono_organico_g_kg=carbono_organico_g_kg,
            pendiente_terreno_pct=pendiente,
            arcilla_pct=arcilla,
            phh2o=phh2o,
        )

        # 4. Fusión Multicriterio (Opción B) y clasificación bidimensional de riesgo
        ranking: list[dict[str, Any]] = []
        sub_scores_by_crop: dict[str, dict[str, float]] = {}

        for crop_id, s_hidro in hydro_scores.items():
            s_suelo = round(float(soil_evals[crop_id].s_suelo), 1)
            score_final = compute_hybrid_final_score(
                s_hidroclimatico=s_hidro,
                s_suelo=s_suelo,
                objetivo_productor=objetivo_productor,
            )
            riesgo = classify_crop_risk(s_hidroclimatico=s_hidro, s_suelo=s_suelo)
            if ensemble is not None:
                riesgo = escalate_risk_level(riesgo, ensemble[crop_id]["p10"])
            sub_scores_by_crop[crop_id] = {
                "hidroclimatico": s_hidro,
                "suelo": s_suelo,
            }
            ranking.append(
                {
                    "cultivo": crop_id,
                    "score_final": score_final,
                    "riesgo": riesgo,
                    "sub_scores": sub_scores_by_crop[crop_id],
                    "meses_suelo_desnudo": soil_evals[crop_id].meses_suelo_desnudo,
                    "fuera_de_ventana_siembra": self.fuera_de_ventana_siembra(crop_id, campana, fecha),
                    "motivo_no_sembrable": self.motivo_no_sembrable(crop_id, campana, fecha, cultivo_anterior),
                }
            )

        # Los cultivos que hoy no se pueden sembrar (lote ocupado o siembra terminada) siguen en el
        # ranking, pero detrás de los sembrables: nunca son el recomendado ni la alternativa.
        ranking.sort(
            key=lambda item: (
                item["motivo_no_sembrable"] is not None,
                -item["score_final"],
                -item["sub_scores"]["hidroclimatico"],
                -item["sub_scores"]["suelo"],
            )
        )

        winner_item = ranking[0]
        winner_crop = winner_item["cultivo"]
        # La alternativa también tiene que poder sembrarse (si hay otra sembrable).
        alternativas = [i["cultivo"] for i in ranking[1:] if i["motivo_no_sembrable"] is None]
        if not alternativas:
            alternativas = [i["cultivo"] for i in ranking[1:]]
        runner_up_crop = alternativas[0] if alternativas else None
        winner_soil = soil_evals[winner_crop]

        # 5. Explicabilidad (Top 3 factores_clave_ml + texto explicativo)
        factores_clave = self.build_key_ml_factors(
            winner_crop=winner_crop,
            campana=campana,
            features=effective_features,
            soil_eval=winner_soil,
        )
        explicacion = self.build_explanation(
            winner_crop=winner_crop,
            runner_up_crop=runner_up_crop,
            ranking=ranking,
            sub_scores_by_crop=sub_scores_by_crop,
            features=effective_features,
            cultivo_anterior=cultivo_anterior,
            riesgo_por_cultivo={item["cultivo"]: item["riesgo"] for item in ranking},
        )
        if ensemble is not None:
            con_fase = oni_actual if isinstance(escenarios_historicos, Mapping) else None
            explicacion = f"{explicacion} {build_ensemble_risk_sentence(ensemble[winner_crop], con_fase)}"
        gwetroot_efectivo = float(effective_features["gwetroot_saturacion_pct"])
        penalizaciones = {c: penalizacion_demanda_hidrica(c, gwetroot_efectivo) for c in hydro_scores}
        mas_penalizado = max(penalizaciones, key=penalizaciones.__getitem__)
        if penalizaciones[mas_penalizado] >= PENALIZACION_DEMANDA_VISIBLE:
            explicacion = (
                f"{explicacion} Con {gwetroot_efectivo:.0f}% de agua en las raíces se descontaron puntos a "
                f"los cultivos que más agua consumen (hasta {penalizaciones[mas_penalizado]:.0f} a "
                f"{crop_prose_name(mas_penalizado)})."
            )

        # 6. Detección de anomalías físicas en curso
        anomalias = detect_physical_anomalies(
            features=effective_features,
            campana=campana,
            cultivo_anterior=cultivo_anterior,
        )

        # 7. Comparación de las 3 estrategias de rotación enriquecida con Score Final híbrido
        raw_strategies = compare_rotation_strategies(
            campana=campana,
            cultivo_anterior=cultivo_anterior,
            carbono_organico_g_kg=carbono_organico_g_kg,
            pendiente_terreno_pct=pendiente,
            arcilla_pct=arcilla,
            phh2o=phh2o,
        )
        estrategias_enriquecidas: list[dict[str, Any]] = []
        for strat in raw_strategies:
            strat_crop = strat.cultivo_evaluado
            strat_hidro = hydro_scores.get(strat_crop, 50.0)
            strat_final = compute_hybrid_final_score(
                s_hidroclimatico=strat_hidro,
                s_suelo=strat.s_suelo,
                objetivo_productor=objetivo_productor,
            )
            estrategias_enriquecidas.append(
                {
                    "estrategia_id": strat.estrategia_id,
                    "titulo": strat.titulo,
                    "cultivo_evaluado": strat_crop,
                    "secuencia_anual": strat.secuencia_anual,
                    "score_final": strat_final,
                    "s_hidroclimatico": strat_hidro,
                    "s_suelo": round(float(strat.s_suelo), 1),
                    "riesgo_erosion_suelo": strat.riesgo_erosion_suelo,
                    "meses_suelo_desnudo": strat.meses_suelo_desnudo,
                    "reduccion_suelo_desnudo_vs_testigo": strat.reduccion_suelo_desnudo_vs_testigo,
                    "resumen_beneficios_riesgos": strat.resumen_beneficios_riesgos,
                }
            )

        ranking_public: list[dict[str, Any]] = []
        for item in ranking:
            public_item: dict[str, Any] = {
                "cultivo": item["cultivo"],
                "score_final": item["score_final"],
                "riesgo": item["riesgo"],
                "fuera_de_ventana_siembra": item["fuera_de_ventana_siembra"],
                "motivo_no_sembrable": item["motivo_no_sembrable"],
            }
            if ensemble is not None:
                dist = ensemble[item["cultivo"]]
                public_item["score_hidroclimatico_p10"] = dist["p10"]
                public_item["anios_desfavorables"] = dist["anios_desfavorables"]
                public_item["anios_evaluados"] = dist["anios_evaluados"]
            ranking_public.append(public_item)

        recomendacion_principal: dict[str, Any] = {
            "cultivo": winner_crop,
            "secuencia_sugerida": winner_soil.secuencia_sugerida,
            "score_final": winner_item["score_final"],
            "sub_scores": winner_item["sub_scores"],
        }
        if ensemble is not None:
            recomendacion_principal["distribucion_hidroclimatica"] = ensemble[winner_crop]
        recomendacion_principal.update(
            {
                "perfil_mercado": winner_soil.perfil_mercado,
                "factores_clave_ml": factores_clave,
                "explicacion": explicacion,
            }
        )

        return {
            "ubicacion": ubicacion or {"lat": -33.95, "lon": -60.57},
            "telemetria_nasa": {
                "fecha_ultimo_dato_valido": fecha_ultimo_dato_valido,
                "indice_humedad_radicular_pct": round(
                    float(effective_features["gwetroot_saturacion_pct"]), 1
                ),
                "indice_humedad_superficial_pct": round(
                    float(effective_features["gwettop_saturacion_pct"]), 1
                ),
                "tendencia_humedad_15d_pct": round(
                    float(effective_features["tendencia_humedad_15d_pct"]), 1
                ),
                "anomalia_lluvia_90d_pct": round(
                    float(effective_features["anomalia_lluvia_90d_pct"]), 1
                ),
                "frecuencia_tormentas_extremas_90d": int(
                    round(float(effective_features["frecuencia_tormentas_extremas"]))
                ),
                "riesgo_termico_verano": classify_summer_thermal_risk(
                    effective_features["frecuencia_estres_termico"]
                ),
            },
            "topografia_srtm": {
                "elevacion_m": round(float(effective_features["elevacion_m"]), 1),
                "pendiente_terreno_pct": round(pendiente, 1),
                "riesgo_erosion_escorrentia": classify_slope_runoff_risk(
                    pendiente_terreno_pct=pendiente,
                    frecuencia_tormentas_extremas=int(
                        round(float(effective_features["frecuencia_tormentas_extremas"]))
                    ),
                    arcilla_pct=arcilla,
                ),
            },
            "perfil_suelo": {
                "textura_predominante": classify_soil_texture(arcilla, arena_pct=arena_pct),
                "arcilla_pct": round(arcilla, 1),
                "carbono_organico_g_kg": round(float(carbono_organico_g_kg or 18.4), 1),
                "condicion_rotacion_previa": winner_soil.condicion_rotacion_previa,
            },
            "anomalias_detectadas": anomalias,
            "recomendacion_principal": recomendacion_principal,
            "ranking_cultivos": ranking_public,
            "validacion_local_requerida": {
                "nota_resolucion_satelital": (
                    "Humedad satelital (NASA POWER/SMAP) estimada a escala regional (~9 km), "
                    "topografía SRTM a 30 m y suelo a 250 m."
                ),
                "brechas_informacion": [
                    "No mide profundidad de napa freática local ni compactación subsuperficial (piso de arado)",
                    "No reemplaza el pronóstico meteorológico estacional ni el análisis químico de laboratorio (Fósforo/Nitrógeno)",
                ],
                "recomendacion_experto": (
                    "Validar agua útil real con muestreo de barreno a 1 metro y consultar al "
                    "ingeniero agrónomo local antes de definir la densidad de siembra."
                ),
            },
            "cobertura_12_meses": {
                "meses_suelo_desnudo": winner_soil.meses_suelo_desnudo,
                "calendario": [
                    {"mes": m.mes, "nombre": m.nombre, "estado": m.estado}
                    for m in winner_soil.calendario_12m
                ],
            },
            "comparacion_estrategias": estrategias_enriquecidas,
        }


_PREDICTOR_LOCK = threading.Lock()
_PREDICTOR_INSTANCE: AgroPredictor | None = None


def get_predictor(model_path: Path | str = DEFAULT_MODEL_PATH) -> AgroPredictor:
    """Devuelve la instancia Singleton de ``AgroPredictor`` cargada en memoria."""
    global _PREDICTOR_INSTANCE
    if _PREDICTOR_INSTANCE is None:
        with _PREDICTOR_LOCK:
            if _PREDICTOR_INSTANCE is None:
                _PREDICTOR_INSTANCE = AgroPredictor(model_path=model_path)
    return _PREDICTOR_INSTANCE


def run_recommendation(
    features: dict[str, float],
    campana: Campaign = "verano",
    cultivo_anterior: str | None = "soja_primera",
    objetivo_productor: ProducerObjective = "equilibrio",
    carbono_organico_g_kg: float | None = 18.4,
    phh2o: float | None = None,
    arena_pct: float | None = None,
    fecha_ultimo_dato_valido: str = "2026-11-08",
    ubicacion: dict[str, float] | None = None,
    simulacion_what_if: dict[str, float | None] | None = None,
    escenarios_historicos: Sequence[Mapping[str, Any]] | Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    umbral_desfavorable: float = DEFAULT_UMBRAL_DESFAVORABLE,
    *,
    fecha_corte: date | None = None,
    oni_actual: float | None = None,
) -> dict[str, Any]:
    """Función de alto nivel lista para ser invocada desde ``simulation_service.py``.

    Para el flujo online con ensemble (ML-5), pasar ``features=insumos.features_actuales`` y
    ``escenarios_historicos=insumos.escenarios_historicos`` de ``construir_insumos_ml`` (BACK-6).
    """
    return get_predictor().predict_and_recommend(
        features=features,
        campana=campana,
        cultivo_anterior=cultivo_anterior,
        objetivo_productor=objetivo_productor,
        carbono_organico_g_kg=carbono_organico_g_kg,
        phh2o=phh2o,
        arena_pct=arena_pct,
        fecha_ultimo_dato_valido=fecha_ultimo_dato_valido,
        ubicacion=ubicacion,
        simulacion_what_if=simulacion_what_if,
        escenarios_historicos=escenarios_historicos,
        umbral_desfavorable=umbral_desfavorable,
        fecha_corte=fecha_corte,
        oni_actual=oni_actual,
    )
