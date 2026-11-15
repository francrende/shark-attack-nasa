"""Motor de Inferencia Online, Detección de Anomalías y Decisión Multicriterio (ML-4).

Implementa ``AgroPredictor`` (interfaz ``RecommendationEngine`` de CONTEXT.md):
1. Carga singleton en memoria de ``backend/ml/modelo_agro.joblib`` (< 15 ms por lote).
2. Aplica transformaciones internas de simulación *What-If* manteniendo controles
   independientes en la UI pero preservando la consistencia física del vector X.
3. Ejecuta inferencia en batch de ``S_hidroclimatico`` (Pilar 1, clippeado a [0, 100]).
4. Fusiona ``S_hidroclimatico`` con ``S_suelo`` (Pilar 2, de ``rotation_matrix.py``)
   usando pesos dinámicos según ``objetivo_productor`` y penalización no lineal por
   factor limitante crítico (< 35 pts, Ley del Mínimo de Liebig).
5. Clasifica el ``riesgo`` bidimensional (``bajo`` | ``medio`` | ``alto`` | ``critico``).
6. Detecta hasta 6 anomalías físicas en curso basadas en evidencia satelital.
7. Genera los Top 3 ``factores_clave_ml`` (usando ``feature_baselines`` por campaña +
   ``permutation_importance`` por cultivo + factores topográficos/edáficos) y la
   ``explicacion`` agronómica transparente para ``POST /api/v1/simulate``.
8. (ML-5) ``predict_ensemble``: en lugar de un único valor para la ventana futura
   ``[corte+1, corte+90]``, corre el modelo con los escenarios históricos reales de cada año
   (``BACK-6``) y devuelve la distribución del puntaje (promedio, P10, P90, años
   desfavorables y peor escenario).
"""

from __future__ import annotations

import threading
import warnings
from collections.abc import Mapping, Sequence
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
    )
except ImportError:
    from services.rotation_matrix import (  # type: ignore[no-redef]
        CROP_PROFILES,
        SoilEvaluationResult,
        compare_rotation_strategies,
        evaluate_campaign_soil,
        get_crop_profile,
        get_crops_for_campaign,
    )

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

# Orden estricto de las 12 features oficiales de CONTEXT.md (Sección 4.3)
FEATURE_COLUMNS: tuple[str, ...] = (
    "gwetroot_saturacion_pct",
    "gwettop_saturacion_pct",
    "tendencia_humedad_15d_pct",
    "anomalia_lluvia_90d_pct",
    "frecuencia_tormentas_extremas",
    "frecuencia_estres_termico",
    "frecuencia_riesgo_helada",
    "indice_aridez_evaporativa",
    "pendiente_terreno_pct",
    "elevacion_m",
    "textura_arcilla_pct",
    "cultivo_candidato",
)
NUMERIC_FEATURES: tuple[str, ...] = FEATURE_COLUMNS[:-1]

# ML-5: separación entre las features que se conocen al decidir (ventana pasada + terreno)
# y las de la ventana futura, que en producción llegan como escenarios por año (BACK-6).
# Deben coincidir con FEATURES_ACTUALES / FEATURES_FUTURAS de backend/providers/features.py.
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
FUTURE_FEATURES: tuple[str, ...] = (
    "frecuencia_tormentas_extremas",
    "frecuencia_estres_termico",
    "frecuencia_riesgo_helada",
)

# Umbral por defecto de "año desfavorable" (coincide con el corte 'critico' de S_hidro).
# Se recalibra al reentrenar con rindes MAGyP (50 = año normal) sin cambiar el contrato.
DEFAULT_UMBRAL_DESFAVORABLE = 50.0
# Si el P10 del ensemble cae por debajo de este valor, el riesgo sube un nivel.
CRITICAL_HYDRO_THRESHOLD = 50.0
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


def classify_summer_thermal_risk(
    frecuencia_estres_termico: float,
    gwetroot_saturacion_pct: float,
) -> Literal["bajo", "medio", "alto"]:
    """Clasifica el riesgo térmico de verano combinando días > 34°C y reserva hídrica."""
    effective_days = float(frecuencia_estres_termico) + (
        2.0 if gwetroot_saturacion_pct < 38.0 and frecuencia_estres_termico >= 4 else 0.0
    )
    if effective_days >= 7.0:
        return "alto"
    if effective_days >= 3.5:
        return "medio"
    return "bajo"


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

    # 1. Variación de lluvia esperada (-50% a +50%)
    if abs(rain_delta) > 1e-6:
        rain_delta_clamped = _clamp(rain_delta, -60.0, 60.0)
        sim["anomalia_lluvia_90d_pct"] = round(
            _clamp(sim["anomalia_lluvia_90d_pct"] + rain_delta_clamped, -80.0, 150.0),
            2,
        )
        scale_factor = max(0.15, 1.0 + (rain_delta_clamped / 100.0))
        sim["indice_aridez_evaporativa"] = round(
            _clamp(sim["indice_aridez_evaporativa"] * scale_factor, 0.08, 2.80),
            3,
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


def classify_crop_risk(
    s_hidroclimatico: float,
    s_suelo: float,
    score_final: float,
) -> CropRiskLevel:
    """Regla bidimensional de riesgo agronómico (S_hidro, S_suelo y vulnerabilidad fisiológica).

    Reproduce exactamente el comportamiento del contrato de CONTEXT.md:
    - 'critico': Colapso hidroclimático/térmico en ventana crítica (S_hidro < 50) o score_final < 22.
    - 'alto': Degradación severa por monocultivo/erosión (S_suelo < 35) o S_hidro inestable (< 62) o score_final < 55.
    - 'medio': Exposición hidroclimática moderada (62 <= S_hidro < 84) o score_final < 75.
    - 'bajo': Alta resiliencia hidroclimática (S_hidro >= 84) y base edáfica sana (S_suelo >= 55).
    """
    if s_hidroclimatico < 50.0 or score_final < 22.0:
        return "critico"
    if s_suelo < 35.0 or s_hidroclimatico < 62.0 or score_final < 55.0:
        return "alto"
    if s_hidroclimatico < 83.0 or s_suelo < 55.0:
        return "medio"
    return "bajo"


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
        faltan_esc = [f for f in FUTURE_FEATURES if f not in esc]
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
    return {
        f: float(round(float(np.median([float(esc[f]) for esc in escenarios_historicos]))))
        for f in FUTURE_FEATURES
    }


def build_ensemble_risk_sentence(dist: Mapping[str, Any]) -> str:
    """Oración de riesgo del ganador para ``explicacion`` a partir de su distribución."""
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
    if campana == "verano" and estres_termico >= 8:
        sev = "alta" if estres_termico >= 12 else "media"
        anomalies.append(
            {
                "tipo": "estres_termico_critico",
                "severidad": sev,
                "evidencia": (
                    f"Alta exposición a golpes de calor con {estres_termico} días esperados "
                    f"con T2M_MAX > 34°C en ventana reproductiva (Climatología NASA POWER)."
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

    def predict_hydroclimatic_batch(
        self,
        features: dict[str, float],
        campana: Campaign,
    ) -> dict[str, float]:
        """Predice S_hidroclimatico (acotado a [0.0, 100.0]) en un único batch para la campaña."""
        crops = get_crops_for_campaign(campana)
        base_row = [float(features[col]) for col in NUMERIC_FEATURES]

        X_batch = np.asarray(
            [
                base_row + [float(self.crops_catalog["by_name"][crop_id]["id"])]
                for crop_id in crops
            ],
            dtype=float,
        )
        clipped_preds = self._predict_clipped(X_batch)

        return {
            crop_id: round(float(score), 1)
            for crop_id, score in zip(crops, clipped_preds)
        }

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
        escenarios_historicos: Sequence[Mapping[str, Any]],
        campana: Campaign,
        *,
        pesos: Sequence[float] | None = None,
        umbral_desfavorable: float = DEFAULT_UMBRAL_DESFAVORABLE,
        simulacion_what_if: Mapping[str, float | None] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Ensemble de años análogos de la ventana futura (ML-5).

        Para cada escenario histórico fija las 8 ``features_actuales``, reemplaza las 3 de la
        ventana futura por las de ese año y predice todos los cultivos de la campaña en un
        único batch. Devuelve, por cultivo, la distribución del puntaje hidroclimático:
        ``promedio`` (score principal), ``p10`` ("año malo"), ``p90`` ("año bueno"),
        ``anios_desfavorables`` (escenarios con score < ``umbral_desfavorable``),
        ``anios_evaluados``, ``umbral_desfavorable`` y ``peor_escenario``.

        ``simulacion_what_if`` se aplica al vector completo de cada escenario. Los escenarios
        con peso 0 se descartan.
        """
        escenarios, weights = _validate_ensemble_inputs(
            features_actuales, escenarios_historicos, pesos
        )
        override_humedad = None
        variacion_lluvia = None
        if simulacion_what_if:
            override_humedad = simulacion_what_if.get("override_humedad_radicular_pct")
            variacion_lluvia = simulacion_what_if.get("variacion_lluvia_esperada_pct")
        apply_sim = override_humedad is not None or bool(variacion_lluvia)

        crops = get_crops_for_campaign(campana)
        crop_ids = [float(self.crops_catalog["by_name"][c]["id"]) for c in crops]
        current = {f: float(features_actuales[f]) for f in CURRENT_FEATURES}

        rows: list[list[float]] = []
        for esc in escenarios:
            vec: dict[str, float] = {**current, **{f: float(esc[f]) for f in FUTURE_FEATURES}}
            if apply_sim:
                vec = apply_what_if_simulation(
                    base_features=vec,
                    override_humedad_radicular_pct=override_humedad,
                    variacion_lluvia_esperada_pct=variacion_lluvia,
                )
            base_row = [vec[col] for col in NUMERIC_FEATURES]
            rows.extend(base_row + [cid] for cid in crop_ids)

        preds = self._predict_clipped(np.asarray(rows, dtype=float)).reshape(
            len(escenarios), len(crops)
        )

        result: dict[str, dict[str, Any]] = {}
        for j, crop in enumerate(crops):
            scores = preds[:, j]
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
                    **{f: int(round(float(worst[f]))) for f in FUTURE_FEATURES},
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
    ) -> str:
        """Redacta la explicación agronómica transparente siguiendo el formato de CONTEXT.md."""
        winner_prof = get_crop_profile(winner_crop)
        winner_subs = sub_scores_by_crop[winner_crop]

        alt_phrase = ""
        if runner_up_crop is not None:
            runner_prof = get_crop_profile(runner_up_crop)
            if winner_crop == "sorgo" and runner_up_crop == "maiz_tardio":
                alt_phrase = " (o Maíz Tardío precedido por Vicia)"
            else:
                alt_phrase = f" (o {runner_prof.nombre_legible} como alternativa)"

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
        lowest_crop = ranking[-1]["cultivo"]
        lowest_prof = get_crop_profile(lowest_crop)
        contrast_parts: list[str] = []

        if "maiz_temprano" in sub_scores_by_crop and winner_crop != "maiz_temprano" and gwetroot <= 42.0:
            contrast_parts.append("el Maíz Temprano (riesgo crítico en floración)")

        prev_norm = (cultivo_anterior or "").strip().lower()
        if prev_norm in CROP_PROFILES and prev_norm != winner_crop:
            prev_prof = CROP_PROFILES[prev_norm]
            if prev_prof.aporte_rastrojo == "bajo":
                contrast_parts.append(
                    f"repetir {prev_prof.nombre_legible} (degradación de carbono y riesgo de erosión por suelo desnudo)"
                )
            else:
                contrast_parts.append(
                    f"repetir {prev_prof.nombre_legible} (penalización por monocultivo)"
                )
        elif lowest_crop != winner_crop:
            contrast_parts.append(f"{lowest_prof.nombre_legible} (menor adaptación al escenario actual)")

        contrast_clause = (
            f"A diferencia de {' o '.join(contrast_parts[:2])}, "
            if contrast_parts
            else ""
        )

        return (
            f"Recomendación: Sembrar {winner_prof.nombre_legible}{alt_phrase}. "
            f"Detectamos vía satélite {moisture_desc}, {rain_desc} y una pendiente del "
            f"{pendiente:.1f}% (SRTM). {contrast_clause}"
            f"el {winner_prof.nombre_legible} ofrece un {winner_subs['hidroclimatico']:.0f}% "
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
        escenarios_historicos: Sequence[Mapping[str, Any]] | None = None,
        umbral_desfavorable: float = DEFAULT_UMBRAL_DESFAVORABLE,
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
        """
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
            )
            hydro_scores = {crop: dist["promedio"] for crop, dist in ensemble.items()}
            # Vector representativo (mediana de los escenarios) para anomalías y explicación
            base_vector: dict[str, float] = {
                **{f: float(features[f]) for f in CURRENT_FEATURES},
                **representative_scenario(escenarios_historicos),
            }
        else:
            base_vector = dict(features)

        effective_features = apply_what_if_simulation(
            base_features=base_vector,
            override_humedad_radicular_pct=override_humedad,
            variacion_lluvia_esperada_pct=variacion_lluvia,
        )
        if ensemble is None:
            hydro_scores = self.predict_hydroclimatic_batch(effective_features, campana=campana)

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
            riesgo = classify_crop_risk(
                s_hidroclimatico=s_hidro,
                s_suelo=s_suelo,
                score_final=score_final,
            )
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
                }
            )

        ranking.sort(
            key=lambda item: (
                -item["score_final"],
                -item["sub_scores"]["hidroclimatico"],
                -item["sub_scores"]["suelo"],
            )
        )

        winner_item = ranking[0]
        winner_crop = winner_item["cultivo"]
        runner_up_crop = ranking[1]["cultivo"] if len(ranking) > 1 else None
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
        )
        if ensemble is not None:
            explicacion = f"{explicacion} {build_ensemble_risk_sentence(ensemble[winner_crop])}"

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
                    frecuencia_estres_termico=effective_features["frecuencia_estres_termico"],
                    gwetroot_saturacion_pct=effective_features["gwetroot_saturacion_pct"],
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
    escenarios_historicos: Sequence[Mapping[str, Any]] | None = None,
    umbral_desfavorable: float = DEFAULT_UMBRAL_DESFAVORABLE,
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
    )
