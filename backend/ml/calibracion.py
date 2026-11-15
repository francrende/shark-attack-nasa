"""Distribución predictiva del puntaje: probabilidad de año malo y rango real (ML-16).

El ensemble de años análogos solo mide cuánto cambia el clima entre años parecidos (P10 → promedio
≈ 6 puntos). El rinde real varía mucho más (desvío ≈ 24 puntos): fuera de muestra, el 39% de los
resultados cae debajo del P10 del ensemble. Para que el "año malo" y la probabilidad sean
honestos, este módulo arma una **distribución predictiva** por cultivo:

    puntaje_real ≈ promedio_del_ensemble + residuo,   residuo ~ errores reales fuera de muestra

- ``probabilidad de año malo`` = P(puntaje_real < 35), con tope (``tope_prob``) en el tramo donde
  la frecuencia real deja de acompañar a la predicha.
- ``año malo`` / ``año bueno`` = cuantiles 10 y 90 de esa distribución.
- La probabilidad solo se publica para los cultivos en los que le gana a la probabilidad típica
  fuera de muestra (``prob_valida_por_cultivo``); para el resto el sistema todavía no anticipa
  diferencias entre años: se muestra solo la frecuencia habitual, el esperado es un año normal
  (50) y el rango es el histórico del cultivo (cuantiles 10 y 90 del puntaje real), porque el
  desvío del modelo en esos cultivos es peor que decir "lo normal" (ML-17, error en kg/ha).

``train_baseline`` arma las predicciones fuera de muestra de las 19 campañas y llama a
``calibrar``; ``predictor`` usa ``prob_anio_malo`` y ``rango_predictivo``. Funciones puras.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

# Año malo: rinde 15% o más bajo la tendencia del departamento (misma definición que ML-8).
UMBRAL_ANIO_MALO = 35.0
VERSION_CALIBRACION = 3  # 3: cuantiles del puntaje real para los cultivos que no anticipan (ML-17)
METODO = "residuos_fuera_de_muestra_por_cultivo"

# Grilla de cuantiles del residuo que se guarda por cultivo (1%, 2%, …, 99%).
NIVELES: np.ndarray = np.round(np.arange(1, 100) / 100.0, 2)
Q_ANIO_MALO = 0.10
Q_ANIO_BUENO = 0.90
# Tramos del diagrama de calibración (probabilidad predicha).
BORDES_DIAGRAMA: tuple[float, ...] = (0.0, 0.1, 0.2, 0.3, 0.45, 1.0)
# Un tramo cuenta para el tope si tiene al menos esta fracción del peso total.
PESO_MINIMO_TRAMO = 0.01
PASO_TOPE = 0.05
# La campaña de la sequía 2022/23, que domina el test: se informa la métrica sin ella.
CAMPANA_SEQUIA = 2022


# ---------------------------------------------------------------------------
# Resumen del ensemble por fila
# ---------------------------------------------------------------------------


def resumen_ensemble(rid: np.ndarray, pred: np.ndarray, peso: np.ndarray, n: int, q: float = 10.0) -> tuple[np.ndarray, np.ndarray]:
    """Promedio ponderado y percentil ``q`` del ensemble de cada fila.

    ``rid`` identifica la fila evaluada (0..n-1) y cada entrada es un año análogo con su
    ``peso``. Los años con peso 0 se descartan, como en ``predictor._validate_ensemble_inputs``.
    El percentil usa la misma definición que ``predictor.weighted_percentile``.
    """
    rid = np.asarray(rid)
    pred = np.asarray(pred, dtype=float)
    peso = np.asarray(peso, dtype=float)
    keep = peso > 0.0
    rid, pred, peso = rid[keep], pred[keep], peso[keep]
    if len(np.unique(rid)) != n:
        raise ValueError("Hay filas sin años análogos con peso positivo")
    promedio = np.bincount(rid, weights=pred * peso, minlength=n) / np.bincount(rid, weights=peso, minlength=n)

    orden = np.lexsort((pred, rid))
    rid, pred, peso = rid[orden], pred[orden], peso[orden]
    inicios = np.flatnonzero(np.r_[True, rid[1:] != rid[:-1]])
    fines = np.r_[inicios[1:], len(rid)]
    pct = np.empty(n)
    for a, b in zip(inicios, fines):
        v, w = pred[a:b], peso[a:b]
        if b - a == 1:
            pct[rid[a]] = v[0]
            continue
        antes = np.cumsum(w) - w
        denom = antes[-1]
        pct[rid[a]] = v[-1] if denom <= 0.0 else float(np.interp(q / 100.0, antes / denom, v))
    return promedio, pct


# ---------------------------------------------------------------------------
# Distribución del residuo
# ---------------------------------------------------------------------------


def cuantiles_ponderados(valores: np.ndarray, pesos: np.ndarray, niveles: np.ndarray = NIVELES) -> np.ndarray:
    """Cuantiles ponderados (función de distribución empírica, punto medio de cada peso)."""
    orden = np.argsort(valores, kind="stable")
    v, w = np.asarray(valores, dtype=float)[orden], np.asarray(pesos, dtype=float)[orden]
    acum = (np.cumsum(w) - 0.5 * w) / w.sum()
    return np.interp(niveles, acum, v)


def _grilla_estricta(grilla: Sequence[float]) -> np.ndarray:
    """La grilla de cuantiles sin empates (``np.interp`` necesita valores crecientes)."""
    g = np.asarray(grilla, dtype=float)
    return g + np.arange(len(g)) * 1e-9


def prob_menor(grilla: Sequence[float], x: np.ndarray | float) -> np.ndarray:
    """P(residuo < x) a partir de la grilla de cuantiles ``NIVELES``."""
    g = _grilla_estricta(grilla)
    return np.interp(np.asarray(x, dtype=float), g, NIVELES, left=NIVELES[0] / 2.0, right=1.0 - NIVELES[0] / 2.0)


def cuantil(grilla: Sequence[float], q: float) -> float:
    return float(np.interp(q, NIVELES, np.asarray(grilla, dtype=float)))


def tasa_por_cultivo(cultivos: np.ndarray, malo: np.ndarray, w: np.ndarray) -> dict[str, float]:
    """Frecuencia ponderada de años malos por cultivo (la probabilidad típica)."""
    df = pd.DataFrame({"c": cultivos, "m": malo.astype(float) * w, "w": w})
    g = df.groupby("c")[["m", "w"]].sum()
    return {str(c): float(r["m"] / r["w"]) for c, r in g.iterrows()}


def _grillas_por_cultivo(cultivos: np.ndarray, residuo: np.ndarray, w: np.ndarray) -> dict[str, np.ndarray]:
    return {str(c): cuantiles_ponderados(residuo[cultivos == c], w[cultivos == c]) for c in np.unique(cultivos)}


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------


def brier(malo: np.ndarray, p: np.ndarray, w: np.ndarray) -> float:
    return float(np.average((np.asarray(p, dtype=float) - malo.astype(float)) ** 2, weights=w))


def _skill(b: float, b_base: float) -> float:
    return round(1.0 - b / b_base, 4) if b_base > 0 else 0.0


def diagrama_calibracion(malo: np.ndarray, p: np.ndarray, w: np.ndarray, bordes: Sequence[float] = BORDES_DIAGRAMA) -> list[dict[str, Any]]:
    """Por tramo de probabilidad predicha: probabilidad media, frecuencia real y peso."""
    tramos = []
    idx = np.clip(np.digitize(p, bordes[1:-1], right=False), 0, len(bordes) - 2)
    total = float(w.sum())
    for k in range(len(bordes) - 1):
        m = idx == k
        if not m.any():
            continue
        tramos.append({
            "desde": bordes[k], "hasta": bordes[k + 1], "filas": int(m.sum()),
            "fraccion_peso": round(float(w[m].sum()) / total, 4),
            "prob_media": round(float(np.average(p[m], weights=w[m])), 3),
            "frecuencia_real": round(float(np.average(malo[m], weights=w[m])), 3),
        })
    return tramos


def tope_desde_diagrama(tramos: Sequence[Mapping[str, Any]]) -> float:
    """Máxima frecuencia real observada en un tramo con peso suficiente, redondeada hacia arriba."""
    frec = [float(t["frecuencia_real"]) for t in tramos if float(t["fraccion_peso"]) >= PESO_MINIMO_TRAMO]
    if not frec:
        return 1.0
    return min(1.0, math.ceil(max(frec) / PASO_TOPE - 1e-9) * PASO_TOPE)


# ---------------------------------------------------------------------------
# Calibración completa (la llama train_baseline)
# ---------------------------------------------------------------------------


def calibrar(df: pd.DataFrame) -> dict[str, Any]:
    """Arma y valida la distribución predictiva con predicciones fuera de muestra.

    ``df`` tiene una fila por (departamento × campaña × cultivo × fecha de evaluación) con las
    columnas ``anio_campana``, ``cultivo_candidato``, ``promedio``, ``puntaje_real`` y ``peso``.
    La validación deja una campaña afuera: la grilla de residuos y la probabilidad típica de
    cada pliegue se calculan sin esa campaña. Lo que se guarda para producción usa todas.
    """
    anios = df["anio_campana"].to_numpy(int)
    cultivos = df["cultivo_candidato"].to_numpy(str)
    prom = df["promedio"].to_numpy(float)
    real = df["puntaje_real"].to_numpy(float)
    residuo = real - prom
    malo = real < UMBRAL_ANIO_MALO
    w = df["peso"].to_numpy(float)
    campanas = sorted(int(a) for a in np.unique(anios))

    p_crudo = np.empty(len(df))
    p_tip = np.empty(len(df))
    q_malo = np.empty(len(df))
    q_bueno = np.empty(len(df))
    for c in campanas:
        fuera = anios == c
        tipica = tasa_por_cultivo(cultivos[~fuera], malo[~fuera], w[~fuera])
        grillas = _grillas_por_cultivo(cultivos[~fuera], residuo[~fuera], w[~fuera])
        for cult in np.unique(cultivos[fuera]):
            m = fuera & (cultivos == cult)
            g = grillas[str(cult)]
            p_crudo[m] = prob_menor(g, UMBRAL_ANIO_MALO - prom[m])
            q_malo[m] = prom[m] + cuantil(g, Q_ANIO_MALO)
            q_bueno[m] = prom[m] + cuantil(g, Q_ANIO_BUENO)
            p_tip[m] = tipica[str(cult)]

    tope = tope_desde_diagrama(diagrama_calibracion(malo, p_crudo, w))
    p = np.minimum(p_crudo, tope)

    por_cultivo: dict[str, Any] = {}
    for cult in sorted(np.unique(cultivos)):
        m = cultivos == cult
        b, b_tip = brier(malo[m], p[m], w[m]), brier(malo[m], p_tip[m], w[m])
        por_cultivo[str(cult)] = {
            "brier": round(b, 4),
            "brier_tipica": round(b_tip, 4),
            "brier_skill": _skill(b, b_tip),
            "cobertura_anio_malo": round(float(np.average(real[m] < q_malo[m], weights=w[m])), 3),
            "cobertura_anio_bueno": round(float(np.average(real[m] > q_bueno[m], weights=w[m])), 3),
        }

    tipica = tasa_por_cultivo(cultivos, malo, w)
    grillas = _grillas_por_cultivo(cultivos, residuo, w)
    validos = {c: bool(v["brier_skill"] > 0.0) for c, v in por_cultivo.items()}
    con_skill = np.isin(cultivos, [c for c, v in validos.items() if v])
    return {
        "version": VERSION_CALIBRACION,
        "metodo": METODO,
        "umbral_anio_malo": UMBRAL_ANIO_MALO,
        "niveles": [float(x) for x in NIVELES],
        "cuantiles_residuo": {c: [round(float(x), 3) for x in g] for c, g in sorted(grillas.items())},
        "cuantiles_puntaje_real": {
            str(c): [round(float(x), 3) for x in cuantiles_ponderados(real[cultivos == c], w[cultivos == c])]
            for c in sorted(np.unique(cultivos))
        },
        "prob_tipica_por_cultivo": {k: round(v, 4) for k, v in sorted(tipica.items())},
        "prob_valida_por_cultivo": validos,
        "tope_prob": tope,
        "campanas": campanas,
        "filas": int(len(df)),
        "metricas": {
            **_metricas_globales(anios, malo, w, p, p_tip, campanas),
            "solo_cultivos_validos": _metricas_globales(
                anios[con_skill], malo[con_skill], w[con_skill], p[con_skill], p_tip[con_skill], campanas
            ) if con_skill.any() else None,
            "cobertura_anio_malo": round(float(np.average(real < q_malo, weights=w)), 3),
            "cobertura_anio_bueno": round(float(np.average(real > q_bueno, weights=w)), 3),
            "cobertura_p10_ensemble": round(float(np.average(real < df["p10"].to_numpy(float), weights=w)), 3)
            if "p10" in df else None,
            "por_cultivo": por_cultivo,
        },
    }


def _metricas_globales(anios: np.ndarray, malo: np.ndarray, w: np.ndarray, p: np.ndarray, p_tip: np.ndarray, campanas: list[int]) -> dict[str, Any]:
    b, b_tip = brier(malo, p, w), brier(malo, p_tip, w)
    sin = anios != CAMPANA_SEQUIA
    b_sin, b_tip_sin = brier(malo[sin], p[sin], w[sin]), brier(malo[sin], p_tip[sin], w[sin])
    por_campana = {}
    for c in campanas:
        m = anios == c
        if not m.any():
            continue
        por_campana[str(c)] = {
            "tasa_real": round(float(np.average(malo[m], weights=w[m])), 3),
            "prob_media": round(float(np.average(p[m], weights=w[m])), 3),
            "prob_tipica_media": round(float(np.average(p_tip[m], weights=w[m])), 3),
        }
    return {
        "brier": round(b, 4),
        "brier_tipica": round(b_tip, 4),
        "brier_skill": _skill(b, b_tip),
        "brier_skill_sin_sequia": _skill(b_sin, b_tip_sin),
        "tasa_anios_malos": round(float(np.average(malo, weights=w)), 3),
        "diagrama": diagrama_calibracion(malo, p, w),
        "por_campana": por_campana,
    }


# ---------------------------------------------------------------------------
# Producción (la usa el predictor)
# ---------------------------------------------------------------------------


def _bloque_valido(calibracion: Mapping[str, Any] | None, cultivo: str) -> bool:
    return bool(
        calibracion
        and calibracion.get("version") == VERSION_CALIBRACION
        and cultivo in calibracion.get("cuantiles_residuo", {})
    )


def prob_anio_malo(calibracion: Mapping[str, Any] | None, cultivo: str, promedio: float) -> dict[str, Any] | None:
    """Probabilidad de año malo del cultivo, o ``None`` si no hay distribución para él.

    Devuelve ``{"prob", "prob_tipica", "anticipa_diferencias"}``. ``prob`` es ``None`` cuando el
    cultivo no le gana a la probabilidad típica fuera de muestra: se muestra solo la habitual.
    """
    if not _bloque_valido(calibracion, cultivo):
        return None
    assert calibracion is not None
    tipica = float(calibracion["prob_tipica_por_cultivo"][cultivo])
    anticipa = bool(calibracion.get("prob_valida_por_cultivo", {}).get(cultivo, False))
    prob = None
    if anticipa:
        crudo = float(prob_menor(calibracion["cuantiles_residuo"][cultivo], UMBRAL_ANIO_MALO - float(promedio)))
        prob = round(min(crudo, float(calibracion.get("tope_prob", 1.0))), 2)
    return {"prob": prob, "prob_tipica": round(tipica, 2), "anticipa_diferencias": anticipa}


def anticipa(calibracion: Mapping[str, Any] | None, cultivo: str) -> bool:
    return bool(calibracion and calibracion.get("prob_valida_por_cultivo", {}).get(cultivo, False))


def puntaje_esperado(calibracion: Mapping[str, Any] | None, cultivo: str, promedio: float) -> float:
    """El promedio del ensemble si el cultivo anticipa; si no, un año normal (50).

    Sin calibración (bundles viejos) se usa el promedio, como antes de ML-16.
    """
    if _bloque_valido(calibracion, cultivo) and not anticipa(calibracion, cultivo):
        return 50.0
    return float(promedio)


def rango_predictivo(calibracion: Mapping[str, Any] | None, cultivo: str, promedio: float) -> tuple[float, float] | None:
    """Puntaje en un año malo (cuantil 10) y en un año bueno (cuantil 90).

    Si el cultivo anticipa: promedio + cuantiles del error real fuera de muestra. Si no: los
    cuantiles del puntaje real del cultivo (lo que pasa habitualmente).
    """
    if not _bloque_valido(calibracion, cultivo):
        return None
    assert calibracion is not None
    if not anticipa(calibracion, cultivo):
        g = calibracion["cuantiles_puntaje_real"][cultivo]
        return round(cuantil(g, Q_ANIO_MALO), 1), round(cuantil(g, Q_ANIO_BUENO), 1)
    g = calibracion["cuantiles_residuo"][cultivo]
    malo = float(np.clip(float(promedio) + cuantil(g, Q_ANIO_MALO), 0.0, 100.0))
    bueno = float(np.clip(float(promedio) + cuantil(g, Q_ANIO_BUENO), 0.0, 100.0))
    return round(malo, 1), round(bueno, 1)
