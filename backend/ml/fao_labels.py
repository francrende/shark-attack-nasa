"""Label FAO GAEZ v4 / FAO-56 (fórmula agronómica) y catálogo de cultivos.

Desde ML-6 el label principal es el rinde real de MAGyP (`magyp.py`). Esta fórmula queda
solo para los cultivos de cobertura sin dato MAGyP y para las filas What-If (label delta).
Movido desde `generate_dataset.py` (ML-1) sin cambios en la fórmula.
"""

from __future__ import annotations

from typing import Any

import numpy as np

FEATURE_COLUMNS: list[str] = [
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
]

TARGET_COLUMN = "s_hidroclimatico"


CROP_CATALOG: dict[str, dict[str, Any]] = {
    # ================= CAMPAÑA FINA (INVIERNO) =================
    "trigo": {
        "id": 0,
        "campana": "invierno",
        "gwetroot_opt_min": 48.0,
        "gwetroot_opt_max": 78.0,
        "gwetroot_crit_min": 26.0,
        "gwetroot_waterlog_max": 86.0,
        "ky_drought": 1.08,
        "ky_waterlog": 1.10,
        "heat_tol": 4.0,
        "heat_sens": 1.8,
        "frost_tol": 22.0,
        "frost_sens": 0.75,
        "aridity_opt": 0.82,
        "runoff_sens": 0.95,
        "base_potential": 96.5,
    },
    "cebada": {
        "id": 1,
        "campana": "invierno",
        "gwetroot_opt_min": 46.0,
        "gwetroot_opt_max": 74.0,
        "gwetroot_crit_min": 25.0,
        "gwetroot_waterlog_max": 80.0,
        "ky_drought": 1.02,
        "ky_waterlog": 1.55,
        "heat_tol": 3.5,
        "heat_sens": 2.0,
        "frost_tol": 20.0,
        "frost_sens": 0.85,
        "aridity_opt": 0.78,
        "runoff_sens": 1.00,
        "base_potential": 95.0,
    },
    "vicia_cobertura": {
        "id": 2,
        "campana": "invierno",
        "gwetroot_opt_min": 38.0,
        "gwetroot_opt_max": 76.0,
        "gwetroot_crit_min": 20.0,
        "gwetroot_waterlog_max": 83.0,
        "ky_drought": 0.76,
        "ky_waterlog": 1.20,
        "heat_tol": 5.0,
        "heat_sens": 1.5,
        "frost_tol": 22.0,
        "frost_sens": 0.65,
        "aridity_opt": 0.70,
        "runoff_sens": 0.70,
        "base_potential": 91.0,
    },
    "avena_cobertura": {
        "id": 3,
        "campana": "invierno",
        "gwetroot_opt_min": 36.0,
        "gwetroot_opt_max": 82.0,
        "gwetroot_crit_min": 19.0,
        "gwetroot_waterlog_max": 88.0,
        "ky_drought": 0.74,
        "ky_waterlog": 0.88,
        "heat_tol": 5.0,
        "heat_sens": 1.6,
        "frost_tol": 22.0,
        "frost_sens": 0.70,
        "aridity_opt": 0.72,
        "runoff_sens": 0.65,
        "base_potential": 91.5,
    },
    "camelina": {
        "id": 4,
        "campana": "invierno",
        "gwetroot_opt_min": 30.0,
        "gwetroot_opt_max": 70.0,
        "gwetroot_crit_min": 16.0,
        "gwetroot_waterlog_max": 81.0,
        "ky_drought": 0.62,
        "ky_waterlog": 1.35,
        "heat_tol": 6.0,
        "heat_sens": 1.4,
        "frost_tol": 26.0,
        "frost_sens": 0.55,
        "aridity_opt": 0.60,
        "runoff_sens": 0.80,
        "base_potential": 88.0,
    },
    # ================= CAMPAÑA GRUESA (VERANO) =================
    "maiz_temprano": {
        "id": 5,
        "campana": "verano",
        "gwetroot_opt_min": 56.0,
        "gwetroot_opt_max": 82.0,
        "gwetroot_crit_min": 33.0,
        "gwetroot_waterlog_max": 88.0,
        "ky_drought": 1.38,
        "ky_waterlog": 1.10,
        "heat_tol": 4.0,
        "heat_sens": 3.1,
        "frost_tol": 2.5,
        "frost_sens": 2.5,
        "aridity_opt": 1.00,
        "runoff_sens": 1.15,
        "base_potential": 97.5,
    },
    "maiz_tardio": {
        "id": 6,
        "campana": "verano",
        "gwetroot_opt_min": 45.0,
        "gwetroot_opt_max": 78.0,
        "gwetroot_crit_min": 24.0,
        "gwetroot_waterlog_max": 88.0,
        "ky_drought": 0.84,
        "ky_waterlog": 1.05,
        "heat_tol": 8.0,
        "heat_sens": 1.6,
        "frost_tol": 3.0,
        "frost_sens": 2.2,
        "aridity_opt": 0.76,
        "runoff_sens": 0.90,
        "base_potential": 92.5,
    },
    "soja_primera": {
        "id": 7,
        "campana": "verano",
        "gwetroot_opt_min": 54.0,
        "gwetroot_opt_max": 80.0,
        "gwetroot_crit_min": 31.0,
        "gwetroot_waterlog_max": 87.0,
        "ky_drought": 1.25,
        "ky_waterlog": 1.15,
        "heat_tol": 5.0,
        "heat_sens": 2.5,
        "frost_tol": 2.0,
        "frost_sens": 2.6,
        "aridity_opt": 0.94,
        "runoff_sens": 1.45,
        "base_potential": 96.0,
    },
    "soja_segunda": {
        "id": 8,
        "campana": "verano",
        "gwetroot_opt_min": 50.0,
        "gwetroot_opt_max": 78.0,
        "gwetroot_crit_min": 29.0,
        "gwetroot_waterlog_max": 86.0,
        "ky_drought": 1.28,
        "ky_waterlog": 1.20,
        "heat_tol": 6.0,
        "heat_sens": 2.3,
        "frost_tol": 2.0,
        "frost_sens": 2.8,
        "aridity_opt": 0.92,
        "runoff_sens": 1.30,
        "base_potential": 90.5,
    },
    "girasol": {
        "id": 9,
        "campana": "verano",
        "gwetroot_opt_min": 40.0,
        "gwetroot_opt_max": 70.0,
        "gwetroot_crit_min": 19.0,
        "gwetroot_waterlog_max": 78.0,
        "ky_drought": 0.70,
        "ky_waterlog": 1.65,
        "heat_tol": 10.0,
        "heat_sens": 1.2,
        "frost_tol": 3.0,
        "frost_sens": 2.0,
        "aridity_opt": 0.66,
        "runoff_sens": 1.05,
        "base_potential": 90.2,
    },
    "sorgo": {
        "id": 10,
        "campana": "verano",
        "gwetroot_opt_min": 38.0,
        "gwetroot_opt_max": 76.0,
        "gwetroot_crit_min": 16.0,
        "gwetroot_waterlog_max": 90.0,
        "ky_drought": 0.56,
        "ky_waterlog": 0.85,
        "heat_tol": 12.0,
        "heat_sens": 1.0,
        "frost_tol": 2.5,
        "frost_sens": 2.2,
        "aridity_opt": 0.60,
        "runoff_sens": 0.72,
        "base_potential": 91.0,
    },
}


def compute_fao_hydroclimatic_score(
    features: dict[str, Any],
    crop_name: str,
    rng: np.random.Generator | None = None,
    noise_std: float = 1.5,
) -> float:
    """
    Calcula el Puntaje de Aptitud Hidroclimática y Topográfica (S_hidroclimatico, 0 a 100)
    integrando las curvas de respuesta FAO GAEZ v4 / FAO-56 y las interacciones no lineales
    documentadas en CONTEXT.md (Sección 4.2, 4.3 y 4.4).
    """
    p = CROP_CATALOG[crop_name]

    gwetroot = float(features["gwetroot_saturacion_pct"])
    gwettop = float(features["gwettop_saturacion_pct"])
    tendencia_15d = float(features["tendencia_humedad_15d_pct"])
    anomalia_lluvia = float(features["anomalia_lluvia_90d_pct"])
    tormentas = int(features["frecuencia_tormentas_extremas"])
    estres_termico = int(features["frecuencia_estres_termico"])
    riesgo_helada = int(features["frecuencia_riesgo_helada"])
    aridez = float(features["indice_aridez_evaporativa"])
    pendiente = float(features["pendiente_terreno_pct"])
    elevacion = float(features["elevacion_m"])
    arcilla = float(features["textura_arcilla_pct"])

    # 1. Humedad efectiva en zona radicular ajustada por pérdida de infiltración en pendiente
    # y retención por textura arcillosa (interacción SRTM + SoilGrids + GPM).
    runoff_loss_pct = 0.0
    if pendiente > 1.2:
        infiltration_resistance = 1.0 + max(0.0, (arcilla - 28.0) / 35.0)
        storm_amplifier = 1.0 + 0.22 * tormentas
        runoff_loss_pct = (
            (pendiente - 1.2)
            * 1.65
            * infiltration_resistance
            * storm_amplifier
            * p["runoff_sens"]
        )

    clay_retention_bonus = np.clip((arcilla - 20.0) * 0.14, -1.8, 2.5)
    effective_gwetroot = gwetroot - 0.55 * runoff_loss_pct + clay_retention_bonus

    score = float(p["base_potential"])

    # 2. Respuesta al déficit hídrico radicular (Curva no lineal FAO-56 Ky)
    opt_min = p["gwetroot_opt_min"]
    opt_max = p["gwetroot_opt_max"]
    crit_min = p["gwetroot_crit_min"]
    ky = p["ky_drought"]

    if effective_gwetroot < opt_min:
        deficit_ratio = (opt_min - effective_gwetroot) / max(10.0, (opt_min - crit_min))
        drought_penalty = 24.0 * ky * (deficit_ratio**1.35)
        score -= drought_penalty
    elif effective_gwetroot <= opt_max:
        mid_opt = 0.5 * (opt_min + opt_max)
        half_span = max(8.0, 0.5 * (opt_max - opt_min))
        center_bonus = (1.8 + 1.8 * ky) * (1.0 - abs(effective_gwetroot - mid_opt) / half_span)
        score += max(0.0, center_bonus)

    # 3. Respuesta al exceso hídrico / anegamiento (GWETROOT > umbral + arcilla alta + pendiente plana)
    waterlog_max = p["gwetroot_waterlog_max"]
    if gwetroot > waterlog_max:
        excess = gwetroot - waterlog_max
        poor_drainage_factor = 1.0
        if arcilla > 32.0:
            poor_drainage_factor += (arcilla - 32.0) / 25.0
        if pendiente < 0.6:
            poor_drainage_factor += (0.6 - pendiente) * 0.65
        waterlog_penalty = (
            1.45 * p["ky_waterlog"] * (excess**1.25) * poor_drainage_factor
        )
        score -= waterlog_penalty

    # 4. Anomalía de precipitación de 90 días e Índice de Aridez Evaporativa (PRECTOTCORR / EVPTRNS)
    if anomalia_lluvia < -10.0:
        rain_def_scale = abs(anomalia_lluvia + 10.0) / 25.0
        score -= 7.2 * (ky**1.15) * rain_def_scale
    elif anomalia_lluvia > 35.0 and gwetroot > 78.0:
        score -= 4.5 * p["ky_waterlog"] * ((anomalia_lluvia - 35.0) / 30.0)

    if aridez < p["aridity_opt"]:
        aridity_gap = (p["aridity_opt"] - aridez) / max(0.35, p["aridity_opt"])
        score -= 8.0 * ky * (aridity_gap**1.2)

    # 5. Interacción crítica NO LINEAL: Golpes de Calor (T2M_MAX > 34°C) x Sequía Radicular (FAO-56)
    # Con buena humedad radicular (>= 50%), la transpiración refrigera el canopeo y amplía la
    # tolerancia térmica; con sequía (< 42%), el cierre estomático multiplica el daño por calor.
    transpiration_heat_buffer = max(0.0, (effective_gwetroot - 46.0) * 0.28)
    effective_heat_tol = p["heat_tol"] + transpiration_heat_buffer
    if estres_termico > effective_heat_tol:
        excess_heat_days = estres_termico - effective_heat_tol
        if effective_gwetroot < 42.0:
            moisture_stress_multiplier = 1.0 + 1.15 * ((42.0 - effective_gwetroot) / 20.0)
            heat_penalty = excess_heat_days * p["heat_sens"] * moisture_stress_multiplier
        else:
            # Suelo húmedo: enfriamiento transpirativo amortigua la pendiente (sublineal y acotado)
            cooling_factor = np.clip(0.68 - 0.011 * (effective_gwetroot - 42.0), 0.26, 0.68)
            heat_penalty = min(
                22.0,
                (excess_heat_days**0.82) * p["heat_sens"] * cooling_factor,
            )
        score -= float(heat_penalty)

    # 6. Riesgo de Helada (T2M_MIN < 2°C) e interacción con altitud (SRTM elevacion_m)
    effective_frost_days = float(riesgo_helada) + max(0.0, (elevacion - 220.0) / 140.0)
    if effective_frost_days > p["frost_tol"]:
        excess_frost = effective_frost_days - p["frost_tol"]
        score -= (excess_frost**0.90) * p["frost_sens"]

    # 7. Anomalías físicas en curso (CONTEXT.md Sección 4.4):
    # 7a. Pulso de Secado Rápido (Flash Drought Onset: tendencia_15d < -10%)
    if tendencia_15d < -10.0:
        drying_severity = abs(tendencia_15d + 10.0) / 12.0
        evap_multiplier = 1.25 if aridez < 0.65 else 1.0
        score -= 5.8 * ky * drying_severity * evap_multiplier

    # 7b. Trampa de "Falsa Recarga" Superficial (GWETTOP > 58% pero GWETROOT < 36%)
    if gwettop > 58.0 and gwetroot < 36.0:
        decouple_gap = (gwettop - gwetroot) / 25.0
        score -= 6.5 * (ky**1.3) * decouple_gap

    # 7c. Suelo superficial extremadamente seco para emergencia/implantación (GWETTOP < 22%)
    if gwettop < 22.0:
        score -= (22.0 - gwettop) * 0.45 * ky

    # 8. Penalización directa por escorrentía y tormentas torrenciales (> 50 mm/día) en pendiente
    score -= 0.75 * runoff_loss_pct

    # 9. Bonus de rusticidad defensiva en escenarios restrictivos (sequía radicular / déficit de lluvias)
    if gwetroot <= 44.0 and anomalia_lluvia < -10.0:
        rusticity_factor = max(0.0, 1.05 - ky)
        drought_intensity = np.clip((44.0 - gwetroot) / 14.0, 0.3, 1.4)
        score += 11.5 * rusticity_factor * drought_intensity

    # 10. Ruido gaussiano leve (±1.5 pts) para evitar sobreajuste determinístico
    if rng is not None and noise_std > 0.0:
        score += float(rng.normal(0.0, noise_std))

    return float(np.clip(round(score, 2), 0.0, 100.0))
