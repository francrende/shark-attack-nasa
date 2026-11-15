"""Entrenamiento del modelo S_hidroclimatico con rindes reales de MAGyP (ML-7).

Uso (desde ``backend/``)::

    python -m ml.train_baseline                 # búsqueda por CV + entrenamiento + evaluación
    python -m ml.train_baseline --solo-evaluar  # reevalúa el modelo guardado (~1 min), sin reentrenar

``--solo-evaluar`` sirve cuando cambia algo de la evaluación y no del modelo (por ejemplo, cómo se
eligen los años análogos): conserva el modelo, los hiperparámetros y la CV del bundle.

1. Dataset de ML-6 (15 features: estado actual, período crítico del cultivo, días hasta la
   siembra y ONI; label = rinde vs. tendencia de largo plazo; ``sample_weight``). Desde ML-10
   solo entran los 8 cultivos con rinde MAGyP (más sus filas What-If); las coberturas no.
2. HistGradientBoosting con **monotonía** (el puntaje no sube con más calor ni con más heladas
   en el período crítico). Hiperparámetros e iteraciones por **validación cruzada dejando una
   campaña afuera** sobre las 16 campañas de train + val (con tan pocas campañas, un val fijo
   de 3 años "normales" elige mal).
3. Refit con train + val y evaluación en test en dos regímenes:
   - **Producción**: años análogos del período crítico ponderados por ONI (``ml/escenarios.py``).
   - **What-If**: clima observado del período crítico (techo de lo que sabe el modelo).
4. Aceptación (acordada con el desarrollador): en producción ≥ 5% mejor que "año normal" y
   ≥ 10% mejor que FAO mapeado; en What-If ≥ 15% mejor que "año normal".
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score

from ml.calibracion import UMBRAL_ANIO_MALO, calibrar, resumen_ensemble
from ml.escenarios import pesos_analogos
from ml.rinde import rinde_normal_kg_ha
from ml.fao_labels import CROP_CATALOG, compute_fao_hydroclimatic_score
from ml.generate_dataset import (
    DATA_DIR,
    FEATURE_COLUMNS_V2,
    METADATA_JSON,
    ML_DIR,
    NUMERIC_FEATURES_V2,
    ORIGEN_COBERTURA,
    ORIGEN_MAGYP,
    SALIDA_ESCENARIOS,
    SALIDA_SPLIT,
    TARGET_COLUMN,
    aplicar_mapeo,
)
from providers.features import FEATURES_PERIODO_CRITICO

SEED = 42
MODEL_PATH = ML_DIR / "modelo_agro.joblib"
METRICS_PATH = DATA_DIR / "training_metrics.json"
MODEL_VERSION = "ml10-magyp"
BUNDLE_VERSION = "2.2.0"  # ML-16: calibracion_anio_malo; ML-18: seguimiento

FEATURE_COLUMNS = FEATURE_COLUMNS_V2
NUMERIC_FEATURES = NUMERIC_FEATURES_V2
FUTURE_FEATURES = list(FEATURES_PERIODO_CRITICO)
MONOTONIC_DECRECIENTES = ("frecuencia_estres_termico", "frecuencia_riesgo_helada")
MONOTONIC_CST = [-1 if f in MONOTONIC_DECRECIENTES else 0 for f in NUMERIC_FEATURES] + [0]
CATEGORICAL_MASK = [False] * len(NUMERIC_FEATURES) + [True]

MAX_ITER = 1500  # la CV de 500 quedó en el tope (494 y 491 iteraciones)
GRID: list[dict[str, Any]] = [
    {"learning_rate": 0.03, "max_leaf_nodes": 7, "min_samples_leaf": 1500, "l2_regularization": 20.0},
    {"learning_rate": 0.03, "max_leaf_nodes": 15, "min_samples_leaf": 800, "l2_regularization": 10.0},
    {"learning_rate": 0.03, "max_leaf_nodes": 7, "min_samples_leaf": 3000, "l2_regularization": 30.0},
    {"learning_rate": 0.05, "max_leaf_nodes": 15, "min_samples_leaf": 1500, "l2_regularization": 20.0},
]

# Criterio de aceptación: mejora relativa mínima del MAE de test
MEJORA_PROD_VS_NORMAL = 0.05
MEJORA_PROD_VS_FAO = 0.10
MEJORA_WHATIF_VS_NORMAL = 0.15
MAX_LATENCY_MS = 15.0

# Caso de sequía de CONTEXT §5 (chequeo informativo)
DROUGHT_BENCHMARK_FEATURES: dict[str, float] = {
    "gwetroot_saturacion_pct": 34.0,
    "gwettop_saturacion_pct": 28.5,
    "tendencia_humedad_15d_pct": -12.0,
    "anomalia_lluvia_90d_pct": -24.2,
    "indice_aridez_evaporativa": 0.52,
    "pendiente_terreno_pct": 1.8,
    "elevacion_m": 78.5,
    "textura_arcilla_pct": 24.5,
    "frecuencia_tormentas_extremas": 1,
    "frecuencia_estres_termico": 6,
    "frecuencia_riesgo_helada": 0,
    "lluvia_periodo_critico_mm": 220.0,
    "dias_hasta_siembra": 15,
    "oni_actual": -1.0,
}
DROUGHT_WINNERS = ["sorgo", "girasol"]
DROUGHT_LOSERS = ["maiz_temprano", "soja_primera"]
DROUGHT_MIN_MARGIN = 10.0


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------


def build_crops_catalog() -> dict[str, Any]:
    by_name = {name: {"id": int(v["id"]), "campana": v["campana"]} for name, v in CROP_CATALOG.items()}
    return {"by_name": by_name, "by_id": {v["id"]: name for name, v in by_name.items()}}


def load_split(split: str) -> pd.DataFrame:
    return pd.read_csv(SALIDA_SPLIT.with_name(SALIDA_SPLIT.name.format(split=split)), dtype={"departamento_id": str})


def to_xyw(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    X = np.column_stack([df[NUMERIC_FEATURES].to_numpy(dtype=float), df["cultivo_id"].to_numpy(dtype=float)])
    return X, df[TARGET_COLUMN].to_numpy(dtype=float), df["sample_weight"].to_numpy(dtype=float)


def expandir_ensemble(df: pd.DataFrame, escenarios: pd.DataFrame, ponderar_oni: bool = True) -> pd.DataFrame:
    """Una fila por (fila real × año análogo ≠ año evaluado), con las features críticas de ese año.

    ``_peso`` es la ponderación por ONI de ``ml/escenarios.py`` (1 si ``ponderar_oni`` es False).
    """
    base = df.reset_index(drop=True).assign(_rid=lambda d: np.arange(len(d))).drop(columns=FUTURE_FEATURES)
    exp = base.merge(escenarios, on=["departamento_id", "cultivo_candidato"], how="inner")
    exp = exp[exp["anio"] != exp["anio_campana"]].reset_index(drop=True)
    faltan = set(base["_rid"]) - set(exp["_rid"])
    if faltan:
        raise ValueError(f"{len(faltan)} filas sin años análogos en {SALIDA_ESCENARIOS.name}")
    if not ponderar_oni:
        return exp.assign(_peso=1.0)
    anios_hist = sorted(int(a) for a in escenarios["anio"].unique())
    cache: dict[tuple[str, int, float], dict[int, float]] = {}
    pesos = np.empty(len(exp))
    for i, (fecha_t, anio_c, oni, anio) in enumerate(exp[["fecha_t", "anio_campana", "oni_actual", "anio"]].itertuples(index=False)):
        clave = (fecha_t, int(anio_c), float(oni))
        if clave not in cache:
            cache[clave] = pesos_analogos(date.fromisoformat(fecha_t), int(anio_c), anios_hist, float(oni))
        pesos[i] = cache[clave][int(anio)]
    return exp.assign(_peso=pesos)


def promedio_por_fila(exp: pd.DataFrame, pred: np.ndarray, n: int) -> np.ndarray:
    w = exp["_peso"].to_numpy(float)
    rid = exp["_rid"].to_numpy()
    return np.bincount(rid, weights=pred * w, minlength=n) / np.bincount(rid, weights=w, minlength=n)


def predict_clipped(model: Any, X: np.ndarray) -> np.ndarray:
    return np.clip(model.predict(X), 0.0, 100.0)


def resumen_produccion(model: Any, df: pd.DataFrame, escenarios: pd.DataFrame) -> pd.DataFrame:
    """Promedio y P10 del ensemble de producción (misma fase ENSO) para cada fila real de ``df``."""
    exp = expandir_ensemble(df, escenarios, ponderar_oni=True)
    X = np.column_stack([exp[NUMERIC_FEATURES].to_numpy(float), exp["cultivo_id"].to_numpy(float)])
    promedio, p10 = resumen_ensemble(exp["_rid"].to_numpy(), predict_clipped(model, X), exp["_peso"].to_numpy(float), len(df))
    return pd.DataFrame({
        "anio_campana": df["anio_campana"].to_numpy(int),
        "departamento_id": df["departamento_id"].to_numpy(str),
        "cultivo_candidato": df["cultivo_candidato"].to_numpy(str),
        "promedio": promedio,
        "p10": p10,
        "puntaje_real": df[TARGET_COLUMN].to_numpy(float),
        "peso": df["sample_weight"].to_numpy(float),
    })


def predicciones_fuera_de_muestra(
    model: Any, params: dict[str, Any], n_iter: int, tv: pd.DataFrame, test: pd.DataFrame, escenarios: pd.DataFrame
) -> pd.DataFrame:
    """Ensemble de producción fuera de muestra en las 19 campañas (ML-16).

    Test (2022–2024) con el modelo final. Cada campaña de train + val con un modelo entrenado
    sin esa campaña (mismos hiperparámetros e iteraciones). El modelo final vio train + val, así
    que sus predicciones ahí serían demasiado confiadas para calibrar una probabilidad.
    """
    partes = [resumen_produccion(model, test, escenarios)]
    reales = (tv["origen_muestra"] == ORIGEN_MAGYP).to_numpy()
    for anio in sorted(tv["anio_campana"].unique()):
        t0 = time.perf_counter()
        fuera = (tv["anio_campana"] == anio).to_numpy()
        X_tr, y_tr, w_tr = to_xyw(tv[~fuera])
        modelo_pliegue = nuevo_modelo(params, n_iter).fit(X_tr, y_tr, sample_weight=w_tr)
        partes.append(resumen_produccion(modelo_pliegue, tv[fuera & reales].reset_index(drop=True), escenarios))
        print(f"  - campaña {anio}/{(anio + 1) % 100:02d} fuera de muestra ({time.perf_counter() - t0:.0f}s)")
    return pd.concat(partes, ignore_index=True)


def mae_kg_ha_por_cultivo(df: pd.DataFrame, pred: np.ndarray) -> dict[str, Any]:
    """ML-17: error en kg/ha del rinde estimado contra decir "rinde normal" (la tendencia).

    Con ``rinde = normal × (1 + (puntaje − 50) / 100)``, el error en kg/ha es
    ``normal × |predicho − real| / 100`` (y el de la tendencia sola, ``normal × |50 − real| / 100``).
    """
    normal = np.array([
        rinde_normal_kg_ha(c, d, int(a)) or np.nan
        for c, d, a in df[["cultivo_candidato", "departamento_id", "anio_campana"]].itertuples(index=False)
    ])
    y = df[TARGET_COLUMN].to_numpy(float)
    w = df["sample_weight"].to_numpy(float)
    ok = np.isfinite(normal)
    out: dict[str, Any] = {}
    for crop in sorted(df["cultivo_candidato"].unique()):
        m = ok & (df["cultivo_candidato"] == crop).to_numpy()
        modelo = float(np.average(normal[m] * np.abs(pred[m] - y[m]) / 100.0, weights=w[m]))
        tendencia = float(np.average(normal[m] * np.abs(50.0 - y[m]) / 100.0, weights=w[m]))
        out[crop] = {
            "modelo": round(modelo), "tendencia": round(tendencia), "mejora": round(1.0 - modelo / tendencia, 4),
            "rinde_normal_medio": round(float(np.average(normal[m], weights=w[m]))),
        }
    return out


NIVELES_AVANCE: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0)


def _casos_seguimiento(df: pd.DataFrame) -> pd.DataFrame:
    """Un caso por departamento × campaña × cultivo, con sus estáticos, label y peso total."""
    reales = df[df["origen_muestra"] == ORIGEN_MAGYP]
    return (
        reales.groupby(["departamento_id", "anio_campana", "cultivo_candidato"], as_index=False)
        .agg(
            pendiente_terreno_pct=("pendiente_terreno_pct", "first"),
            elevacion_m=("elevacion_m", "first"),
            textura_arcilla_pct=("textura_arcilla_pct", "first"),
            cultivo_id=("cultivo_id", "first"),
            puntaje_real=(TARGET_COLUMN, "first"),
            peso=("sample_weight", "sum"),
        )
    )


def filas_seguimiento(casos: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Filas del modelo para el seguimiento retrospectivo de cada caso en cada nivel de avance.

    Para cada caso: siembra en el inicio del calendario, estado del suelo y ONI de ese día, y en
    cada nivel la ventana mezclada (días observados de esa campaña + resto de cada año análogo de
    la misma fase ENSO, ``ml/escenarios.escenarios_en_curso``), igual que producción.
    Devuelve ``(X, caso, nivel, peso_analogo, anio_campana_del_caso)``.
    """
    from ml import calendario_siembra as cal
    from ml.escenarios import escenarios_en_curso, inicio_periodo_critico_real
    from ml.generate_dataset import features_actuales_en, leer_serie_celda, referencia_historica
    from providers.cache import clave_celda_power

    centroides = json.loads((DATA_DIR / "departamentos_pampa.json").read_text(encoding="utf-8"))
    refs: dict[str, Any] = {}
    X: list[list[float]] = []
    idx_caso: list[int] = []
    idx_nivel: list[int] = []
    pesos: list[float] = []
    cache_pesos: dict[Any, dict[int, float]] = {}
    t0 = time.perf_counter()
    for i, caso in enumerate(casos.itertuples(index=False)):
        dep = centroides.get(caso.departamento_id)
        if dep is None:
            continue
        clave = clave_celda_power(dep["lat"], dep["lon"])
        if clave not in refs:
            serie = leer_serie_celda(clave)
            refs[clave] = None if serie is None else (serie, referencia_historica(serie))
        if refs[clave] is None:
            continue
        serie, ref = refs[clave]
        anio = int(caso.anio_campana)
        siembra = cal.inicio_siembra(caso.cultivo_candidato, anio)
        estaticos = {
            "pendiente_terreno_pct": float(caso.pendiente_terreno_pct),
            "elevacion_m": float(caso.elevacion_m),
            "textura_arcilla_pct": float(caso.textura_arcilla_pct),
        }
        actuales = features_actuales_en(serie, ref, siembra, estaticos)
        if actuales is None:
            continue
        inicio = inicio_periodo_critico_real(caso.cultivo_candidato, siembra)
        for k, nivel in enumerate(NIVELES_AVANCE):
            d = int(round(nivel * cal.DIAS_PERIODO_CRITICO))
            escenarios, _ = escenarios_en_curso(
                ref.calendario_eventos, ref.calendario_lluvia, ref.calendario_eventos, ref.calendario_lluvia,
                caso.cultivo_candidato, siembra, inicio + timedelta(days=d - 1), actuales["oni_actual"],
                anio_campana=anio, cache_pesos=cache_pesos,
            )
            for esc in escenarios:
                vec = {**actuales, **esc, "dias_hasta_siembra": 0.0}
                X.append([float(vec[f]) for f in NUMERIC_FEATURES] + [float(caso.cultivo_id)])
                idx_caso.append(i)
                idx_nivel.append(k)
                pesos.append(float(esc["peso"]))
        if (i + 1) % 3000 == 0:
            print(f"  - {i + 1}/{len(casos)} casos ({time.perf_counter() - t0:.0f}s)", flush=True)
    anio_caso = casos["anio_campana"].to_numpy(int)
    caso_arr = np.asarray(idx_caso)
    return np.asarray(X, dtype=float), caso_arr, np.asarray(idx_nivel), np.asarray(pesos), anio_caso[caso_arr]


def seguimiento_retrospectivo(
    model: Any, params: dict[str, Any], n_iter: int, tv: pd.DataFrame, test: pd.DataFrame
) -> dict[str, Any]:
    """ML-18: distribución predictiva por nivel de avance del período crítico (fuera de muestra).

    Mismo esquema que ML-16: test con el modelo final y cada campaña de train + val con un modelo
    que no la vio. Con el clima observado el error se achica, así que cada nivel guarda su propia
    grilla de residuos (``calibrar``) y el rango se angosta a medida que avanza la campaña.
    """
    casos = pd.concat([_casos_seguimiento(tv), _casos_seguimiento(test)], ignore_index=True)
    print(f"  {len(casos)} casos (departamento × campaña × cultivo), {len(NIVELES_AVANCE)} niveles de avance")
    X, caso, nivel, peso, anio = filas_seguimiento(casos)
    pred = np.empty(len(X))
    anios_test = set(int(a) for a in test["anio_campana"].unique())
    for a in sorted(set(int(x) for x in anio)):
        m = anio == a
        if a in anios_test:
            modelo = model
        else:
            fuera = (tv["anio_campana"] == a).to_numpy()
            X_tr, y_tr, w_tr = to_xyw(tv[~fuera])
            modelo = nuevo_modelo(params, n_iter).fit(X_tr, y_tr, sample_weight=w_tr)
        pred[m] = predict_clipped(modelo, X[m])
    clave = caso * len(NIVELES_AVANCE) + nivel
    n_claves = len(casos) * len(NIVELES_AVANCE)
    suma_w = np.bincount(clave, weights=peso, minlength=n_claves)
    promedio = np.bincount(clave, weights=pred * peso, minlength=n_claves) / np.where(suma_w > 0, suma_w, 1.0)

    por_nivel: dict[str, Any] = {}
    resumen: dict[str, Any] = {}
    for k, nv in enumerate(NIVELES_AVANCE):
        con_dato = suma_w[k :: len(NIVELES_AVANCE)] > 0
        df = casos.loc[con_dato, ["anio_campana", "cultivo_candidato", "puntaje_real", "peso"]].assign(
            promedio=promedio[k :: len(NIVELES_AVANCE)][con_dato]
        )
        bloque = calibrar(df)
        met = bloque["metricas"]
        malo = (df["puntaje_real"] < UMBRAL_ANIO_MALO).to_numpy()
        w = df["peso"].to_numpy(float)
        sequia = met["por_campana"].get(str(CAMPANA_SEQUIA_SEGUIMIENTO), {})
        resumen[f"{nv:.2f}"] = {
            "casos": int(con_dato.sum()),
            "mae": round(float(np.average(np.abs(df["puntaje_real"] - df["promedio"]), weights=w)), 3),
            "auc_anios_malos": round(float(roc_auc_score(malo, -df["promedio"], sample_weight=w)), 3),
            "brier": met["brier"],
            "brier_skill": met["brier_skill"],
            "brier_skill_sin_sequia": met["brier_skill_sin_sequia"],
            "cobertura_anio_malo": met["cobertura_anio_malo"],
            "cobertura_anio_bueno": met["cobertura_anio_bueno"],
            "ancho_rango_medio": round(float(np.mean([
                np.interp(0.9, bloque["niveles"], g) - np.interp(0.1, bloque["niveles"], g)
                for g in bloque["cuantiles_residuo"].values()
            ])), 1),
            "sequia_2022_prob_media": sequia.get("prob_media"),
            "sequia_2022_prob_tipica": sequia.get("prob_tipica_media"),
            "cultivos_que_anticipan": sorted(c for c, v in bloque["prob_valida_por_cultivo"].items() if v),
        }
        por_nivel[f"{nv:.2f}"] = bloque
        r = resumen[f"{nv:.2f}"]
        print(f"  - avance {nv:>4.0%}: MAE {r['mae']:.2f} | AUC {r['auc_anios_malos']:.3f} | Brier skill {r['brier_skill']:+.1%} "
              f"| rango ±{r['ancho_rango_medio'] / 2:.0f} pts | 2022/23 prob {r['sequia_2022_prob_media']} vs {r['sequia_2022_prob_tipica']} "
              f"| anticipan: {len(r['cultivos_que_anticipan'])}")
    detecta = next(
        (nv for nv, r in resumen.items()
         if r["sequia_2022_prob_media"] and r["sequia_2022_prob_media"] >= 2 * (r["sequia_2022_prob_tipica"] or 1)),
        None,
    )
    briers = [resumen[f"{nv:.2f}"]["brier"] for nv in NIVELES_AVANCE]
    return {
        "niveles": [f"{nv:.2f}" for nv in NIVELES_AVANCE],
        "por_nivel": por_nivel,
        "resumen": resumen,
        "sequia_2022_detectada_desde_avance": detecta,
        "criterio_brier_final_menor_que_inicial": bool(briers[-1] < briers[0]),
        "generado_en": datetime.now(timezone.utc).isoformat(),
    }


CAMPANA_SEQUIA_SEGUIMIENTO = 2022


def calibrar_bundle(model: Any, params: dict[str, Any], n_iter: int, tv: pd.DataFrame, test: pd.DataFrame, escenarios: pd.DataFrame) -> dict[str, Any]:
    oos = predicciones_fuera_de_muestra(model, params, n_iter, tv, test, escenarios)
    cal = calibrar(oos)
    m = cal["metricas"]
    print(f"  => Brier {m['brier']} contra {m['brier_tipica']} de la probabilidad típica (skill {m['brier_skill']:+.1%}; "
          f"sin 2022/23 {m['brier_skill_sin_sequia']:+.1%}); tope de probabilidad {cal['tope_prob']:.2f}")
    print(f"     cobertura del rango: {m['cobertura_anio_malo']:.1%} debajo del año malo, {m['cobertura_anio_bueno']:.1%} "
          f"arriba del año bueno (P10 del ensemble solo: {m['cobertura_p10_ensemble']:.1%} debajo)")
    for t in m["diagrama"]:
        print(f"     prob {t['desde']:.2f}–{t['hasta']:.2f}: predicha {t['prob_media']:.2f} | real {t['frecuencia_real']:.2f} ({t['filas']} filas)")
    for c, v in m["por_cultivo"].items():
        print(f"     {c:<14} skill {v['brier_skill']:+.1%} → {'anticipa' if cal['prob_valida_por_cultivo'][c] else 'solo frecuencia habitual'}"
              f" | cobertura {v['cobertura_anio_malo']:.0%}/{v['cobertura_anio_bueno']:.0%}")
    return cal


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------


def weighted_metrics(y: np.ndarray, p: np.ndarray, w: np.ndarray) -> dict[str, float]:
    err = p - y
    mae = float(np.average(np.abs(err), weights=w))
    rmse = float(np.sqrt(np.average(err**2, weights=w)))
    ss_res = float(np.sum(w * err**2))
    ss_tot = float(np.sum(w * (y - np.average(y, weights=w)) ** 2))
    return {"n": int(len(y)), "mae": round(mae, 3), "rmse": round(rmse, 3), "r2": round(1.0 - ss_res / ss_tot, 4)}


def metricas_completas(df: pd.DataFrame, pred: np.ndarray) -> dict[str, Any]:
    """Globales, por cultivo, ranking entre cultivos (Spearman) y detección de años malos."""
    y = df[TARGET_COLUMN].to_numpy(float)
    w = df["sample_weight"].to_numpy(float)
    out: dict[str, Any] = {"global": weighted_metrics(y, pred, w), "por_cultivo": {}, "por_anio": {}}
    for crop, idx in df.groupby("cultivo_candidato").indices.items():
        out["por_cultivo"][crop] = weighted_metrics(y[idx], pred[idx], w[idx])["mae"]
    for anio, idx in df.groupby("anio_campana").indices.items():
        out["por_anio"][str(anio)] = {
            "real": round(float(np.average(y[idx], weights=w[idx])), 1),
            "predicho": round(float(np.average(pred[idx], weights=w[idx])), 1),
        }

    camp = df.assign(_p=pred * w, _w=w).groupby(["departamento_id", "anio_campana", "campana", "cultivo_candidato"]).agg(
        p=("_p", "sum"), w=("_w", "sum"), y=(TARGET_COLUMN, "first")
    )
    camp["p"] = camp["p"] / camp["w"]
    rhos = []
    for _, g in camp.groupby(level=["departamento_id", "anio_campana", "campana"]):
        if len(g) >= 3 and g["y"].nunique() > 1 and g["p"].nunique() > 1:
            rhos.append(spearmanr(g["p"], g["y"]).statistic)
    malo = (camp["y"] < UMBRAL_ANIO_MALO).to_numpy()
    out["spearman_cultivos_medio"] = round(float(np.nanmean(rhos)), 3) if rhos else None
    out["anios_malos"] = {
        "umbral": UMBRAL_ANIO_MALO,
        "n": int(malo.sum()),
        "auc": round(float(roc_auc_score(malo, -camp["p"])), 3) if 0 < malo.sum() < len(malo) else None,
    }
    return out


# ---------------------------------------------------------------------------
# Líneas base
# ---------------------------------------------------------------------------


def base_anio_normal(train: pd.DataFrame, df: pd.DataFrame) -> np.ndarray:
    medias = train.groupby("cultivo_candidato").apply(
        lambda g: np.average(g[TARGET_COLUMN], weights=g["sample_weight"]), include_groups=False
    )
    return df["cultivo_candidato"].map(medias).fillna(50.0).to_numpy(float)


def base_fao_ensemble(df: pd.DataFrame, exp: pd.DataFrame, mapeos: dict[str, Any]) -> np.ndarray:
    filas = exp.to_dict("records")
    crudo = np.array([compute_fao_hydroclimatic_score(r, r["cultivo_candidato"], rng=None, noise_std=0.0) for r in filas])
    mapeado = np.empty_like(crudo)
    campanas = exp["campana"].to_numpy()
    for campana, m in mapeos.items():
        mask = campanas == campana
        mapeado[mask] = aplicar_mapeo(crudo[mask], (np.array(m["fao"]), np.array(m["magyp"])))
    return promedio_por_fila(exp, mapeado, len(df))


# ---------------------------------------------------------------------------
# Búsqueda: validación cruzada dejando una campaña afuera
# ---------------------------------------------------------------------------


def nuevo_modelo(params: dict[str, Any], max_iter: int) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss="squared_error",
        categorical_features=CATEGORICAL_MASK,
        monotonic_cst=MONOTONIC_CST,
        early_stopping=False,
        max_iter=max_iter,
        random_state=SEED,
        **params,
    )


def buscar_loso(tv: pd.DataFrame) -> tuple[dict[str, Any], int, dict[str, Any]]:
    """Elige hiperparámetros e iteraciones por el MAE de las campañas dejadas afuera."""
    anios = sorted(tv["anio_campana"].unique())
    reales = (tv["origen_muestra"] == ORIGEN_MAGYP).to_numpy()
    comparacion: dict[str, Any] = {}
    mejor: tuple[float, dict[str, Any], int] | None = None
    for i, params in enumerate(GRID, 1):
        t0 = time.perf_counter()
        err = np.zeros(MAX_ITER)
        wtot = 0.0
        for anio in anios:
            fuera = (tv["anio_campana"] == anio).to_numpy()
            X_tr, y_tr, w_tr = to_xyw(tv[~fuera])
            X_h, y_h, w_h = to_xyw(tv[fuera & reales])
            model = nuevo_modelo(params, MAX_ITER).fit(X_tr, y_tr, sample_weight=w_tr)
            for k, pred in enumerate(model.staged_predict(X_h)):
                err[k] += float(np.sum(w_h * np.abs(np.clip(pred, 0.0, 100.0) - y_h)))
            wtot += float(w_h.sum())
        curva = err / wtot
        n_iter = int(np.argmin(curva)) + 1
        nombre = f"hgb_v{i}"
        comparacion[nombre] = {
            **params, "mejor_iteracion": n_iter, "cv_mae": round(float(curva[n_iter - 1]), 3),
            "cv_mae_ultima_iteracion": round(float(curva[-1]), 3), "segundos": round(time.perf_counter() - t0, 1),
        }
        print(f"  - {nombre} {params} → iter {n_iter}, CV MAE {curva[n_iter - 1]:.3f}  ({comparacion[nombre]['segundos']}s)")
        if mejor is None or curva[n_iter - 1] < mejor[0]:
            mejor = (float(curva[n_iter - 1]), params, n_iter)
    assert mejor is not None
    return mejor[1], mejor[2], comparacion


def cv_base_anio_normal(tv: pd.DataFrame) -> float:
    err = wtot = 0.0
    reales = tv[tv["origen_muestra"] == ORIGEN_MAGYP]
    for anio in sorted(reales["anio_campana"].unique()):
        fuera = reales["anio_campana"] == anio
        hold = reales[fuera]
        err += float(np.sum(hold["sample_weight"] * np.abs(base_anio_normal(reales[~fuera], hold) - hold[TARGET_COLUMN])))
        wtot += float(hold["sample_weight"].sum())
    return round(err / wtot, 3)


# ---------------------------------------------------------------------------
# Explicabilidad y chequeos
# ---------------------------------------------------------------------------


def _normalizar(raw: np.ndarray, nombres: list[str]) -> dict[str, float]:
    c = np.clip(raw, 0.0, None)
    tot = c.sum()
    pesos = c / tot if tot > 0 else np.full_like(c, 1.0 / len(c))
    return {f: round(float(v), 5) for f, v in zip(nombres, pesos)}


def compute_importances(model: Any, df: pd.DataFrame, n_max: int = 20000) -> dict[str, Any]:
    muestra = df.sample(n=min(n_max, len(df)), random_state=SEED)
    X, y, w = to_xyw(muestra)
    glob = permutation_importance(model, X, y, sample_weight=w, n_repeats=5, random_state=SEED, scoring="neg_mean_absolute_error")
    per_crop: dict[str, Any] = {}
    for crop, idx in muestra.groupby("cultivo_candidato").indices.items():
        if len(idx) < 200:
            continue
        r = permutation_importance(model, X[idx], y[idx], sample_weight=w[idx], n_repeats=5, random_state=SEED, scoring="neg_mean_absolute_error")
        imp = _normalizar(r.importances_mean, FEATURE_COLUMNS)
        imp.pop("cultivo_candidato", None)
        tot = sum(imp.values()) or 1.0
        per_crop[crop] = {k: round(v / tot, 5) for k, v in imp.items()}
    return {
        "method": "permutation_importance (neg MAE ponderado, n_repeats=5, test real, clima observado)",
        "global": _normalizar(glob.importances_mean, FEATURE_COLUMNS),
        "global_raw_mae_increase": {f: round(float(v), 4) for f, v in zip(FEATURE_COLUMNS, glob.importances_mean)},
        "per_crop": per_crop,
    }


def compute_feature_baselines(df: pd.DataFrame) -> dict[str, Any]:
    def stats(s: pd.Series) -> dict[str, float]:
        return {
            "mean": round(float(s.mean()), 4), "std": round(float(s.std()), 4),
            "p05": round(float(s.quantile(0.05)), 4), "p50": round(float(s.quantile(0.5)), 4),
            "p95": round(float(s.quantile(0.95)), 4),
        }

    return {
        "global": {f: stats(df[f].astype(float)) for f in NUMERIC_FEATURES},
        "by_campana": {
            c: {f: {"mean": round(float(g[f].mean()), 4), "std": round(float(g[f].std()), 4)} for f in NUMERIC_FEATURES}
            for c, g in df.groupby("campana")
        },
    }


def chequeos(model: Any, catalog: dict[str, Any], test: pd.DataFrame) -> dict[str, Any]:
    out: dict[str, Any] = {}
    muestra = test.sample(n=min(3000, len(test)), random_state=SEED)
    X, _, _ = to_xyw(muestra)
    base = model.predict(X)
    for feat in MONOTONIC_DECRECIENTES:
        Xp = X.copy()
        Xp[:, NUMERIC_FEATURES.index(feat)] += 10
        sube = float(np.max(model.predict(Xp) - base))
        out[f"monotonia_{feat}"] = {"max_subida": round(sube, 6), "passed": sube <= 1e-9}

    verano = [c for c, v in catalog["by_name"].items() if v["campana"] == "verano"]
    fila = [float(DROUGHT_BENCHMARK_FEATURES[f]) for f in NUMERIC_FEATURES]
    X_lote = np.asarray([fila + [float(catalog["by_name"][c]["id"])] for _ in range(20) for c in verano])

    def raw(Xb: np.ndarray) -> np.ndarray:
        return model._loss.link.inverse(model._raw_predict(Xb, n_threads=1).ravel())

    for _ in range(10):
        raw(X_lote)
    tiempos = []
    for _ in range(200):
        t0 = time.perf_counter()
        raw(X_lote)
        tiempos.append((time.perf_counter() - t0) * 1000)
    p95 = float(np.percentile(tiempos, 95))
    out["latencia_ms_ensemble_6x20"] = {"p95": round(p95, 3), "umbral": MAX_LATENCY_MS, "passed": p95 < MAX_LATENCY_MS}

    X_s = np.asarray([fila + [float(catalog["by_name"][c]["id"])] for c in verano])
    scores = {c: round(float(p), 2) for c, p in zip(verano, predict_clipped(model, X_s))}
    margen = min(scores[w] for w in DROUGHT_WINNERS) - max(scores[l] for l in DROUGHT_LOSERS)
    out["benchmark_sequia_informativo"] = {
        "scores": dict(sorted(scores.items(), key=lambda kv: -kv[1])),
        "margen": round(float(margen), 2),
        "regla": f"min({DROUGHT_WINNERS}) - max({DROUGHT_LOSERS}) >= {DROUGHT_MIN_MARGIN}",
        "cumple": bool(margen >= DROUGHT_MIN_MARGIN),
    }
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def guardar_bundle(bundle: dict[str, Any], catalog: dict[str, Any]) -> None:
    """Escribe el bundle y ``training_metrics.json`` (el mismo contenido sin el modelo)."""
    joblib.dump(bundle, MODEL_PATH, compress=3)
    report = {k: v for k, v in bundle.items() if k != "model"}
    report["crops_catalog"] = {"by_name": catalog["by_name"], "by_id": {str(k): v for k, v in catalog["by_id"].items()}}
    report["model_file_size_kb"] = round(MODEL_PATH.stat().st_size / 1024, 1)
    METRICS_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  - {MODEL_PATH} ({report['model_file_size_kb']} KB)\n  - {METRICS_PATH}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Entrenamiento y evaluación del modelo S_hidroclimatico")
    parser.add_argument("--solo-evaluar", action="store_true", help="reevaluar el modelo guardado sin reentrenar")
    parser.add_argument("--solo-calibrar", action="store_true", help="recalibrar la probabilidad de año malo (ML-16) del modelo guardado")
    parser.add_argument("--seguimiento", action="store_true", help="prueba retrospectiva del seguimiento en campaña (ML-18) con el modelo guardado")
    args = parser.parse_args(argv)
    print("=" * 78)
    print("ML-7 | Entrenamiento con rindes reales MAGyP (período crítico + ENSO)")
    print("=" * 78)
    catalog = build_crops_catalog()
    meta = json.loads(METADATA_JSON.read_text(encoding="utf-8"))
    escenarios = pd.read_csv(SALIDA_ESCENARIOS, dtype={"departamento_id": str})
    train, val, test = (load_split(s) for s in ("train", "val", "test"))
    tv = pd.concat([train, val], ignore_index=True)
    # ML-10: las coberturas (label de fórmula FAO, sin rinde MAGyP) no entran al modelo. El
    # predictor las puntúa relativo a los cultivos con rinde real (FAO-56 Ky).
    tv = tv[tv["origen_muestra"] != ORIGEN_COBERTURA].reset_index(drop=True)
    test = test[test["origen_muestra"] == ORIGEN_MAGYP].reset_index(drop=True)
    tv_real = tv[tv["origen_muestra"] == ORIGEN_MAGYP]
    print(f"train+val={len(tv)} ({len(tv_real)} reales, {tv['anio_campana'].nunique()} campañas) | test={len(test)}")

    if args.seguimiento:
        bundle = joblib.load(MODEL_PATH)
        params = {k: v for k, v in bundle["model_params"].items() if k not in ("max_iter", "monotonic_cst")}
        print(f"\n[ML-18] Seguimiento retrospectivo (modelo del {bundle['trained_at']}):")
        bundle["seguimiento"] = seguimiento_retrospectivo(
            bundle["model"], params, int(bundle["model_params"]["max_iter"]), tv, test
        )
        bundle["bundle_version"] = BUNDLE_VERSION
        guardar_bundle(bundle, catalog)
        return 0 if bundle["seguimiento"]["criterio_brier_final_menor_que_inicial"] else 1

    if args.solo_calibrar:
        bundle = joblib.load(MODEL_PATH)
        params = {k: v for k, v in bundle["model_params"].items() if k not in ("max_iter", "monotonic_cst")}
        print(f"\n[ML-16] Calibración de la probabilidad de año malo (modelo del {bundle['trained_at']}):")
        bundle["calibracion_anio_malo"] = calibrar_bundle(
            bundle["model"], params, int(bundle["model_params"]["max_iter"]), tv, test, escenarios
        )
        bundle["bundle_version"] = BUNDLE_VERSION
        guardar_bundle(bundle, catalog)
        return 0

    print("\n[1/5] Búsqueda por validación cruzada dejando una campaña afuera:")
    if args.solo_evaluar:
        previo = joblib.load(MODEL_PATH)
        model = previo["model"]
        params = {k: v for k, v in previo["model_params"].items() if k not in ("max_iter", "monotonic_cst")}
        n_iter = int(previo["model_params"]["max_iter"])
        comparacion = previo["model_comparison_val"]
        cv_base = previo["metrics"]["cv_loso"]["base_anio_normal"]
        trained_at = previo["trained_at"]
        print(f"  (--solo-evaluar) modelo del {trained_at}: {params}, {n_iter} iteraciones")
        print("\n[2/5] Evaluación en test con el modelo guardado:")
    else:
        params, n_iter, comparacion = buscar_loso(tv)
        cv_base = cv_base_anio_normal(tv)
        print(f"  => {params}, {n_iter} iteraciones (CV MAE año normal: {cv_base})")

        print("\n[2/5] Refit con train + val y evaluación en test:")
        X_tv, y_tv, w_tv = to_xyw(tv)
        model = nuevo_modelo(params, n_iter).fit(X_tv, y_tv, sample_weight=w_tv)
        trained_at = datetime.now(timezone.utc).isoformat()
    exp_oni = expandir_ensemble(test, escenarios, ponderar_oni=True)
    exp_uni = exp_oni.assign(_peso=1.0)
    X_exp = np.column_stack([exp_oni[NUMERIC_FEATURES].to_numpy(float), exp_oni["cultivo_id"].to_numpy(float)])
    pred_exp = predict_clipped(model, X_exp)

    metrics = {
        "test_produccion_oni": metricas_completas(test, promedio_por_fila(exp_oni, pred_exp, len(test))),
        "test_produccion_uniforme": metricas_completas(test, promedio_por_fila(exp_uni, pred_exp, len(test))),
        "test_whatif_observado": metricas_completas(test, predict_clipped(model, to_xyw(test)[0])),
        "base_anio_normal_test": metricas_completas(test, base_anio_normal(tv_real, test)),
        "base_fao_mapeado_test": metricas_completas(test, base_fao_ensemble(test, exp_oni, meta["mapeo_fao_a_magyp"])),
    }
    metrics["mae_kg_ha_test_produccion"] = mae_kg_ha_por_cultivo(test, promedio_por_fila(exp_oni, pred_exp, len(test)))
    for k, m in metrics.items():
        if k == "mae_kg_ha_test_produccion":
            continue
        g = m["global"]
        print(f"  - {k:<26} MAE={g['mae']:.3f}  RMSE={g['rmse']:.3f}  R²={g['r2']:.4f}  "
              f"Spearman={m['spearman_cultivos_medio']}  AUC años malos={m['anios_malos']['auc']}")

    def _mejora(k: str, base: str) -> float:
        return round(1.0 - metrics[k]["global"]["mae"] / metrics[base]["global"]["mae"], 4)

    criterios = {
        "produccion_vs_anio_normal": (_mejora("test_produccion_oni", "base_anio_normal_test"), MEJORA_PROD_VS_NORMAL),
        "produccion_vs_fao": (_mejora("test_produccion_oni", "base_fao_mapeado_test"), MEJORA_PROD_VS_FAO),
        "whatif_vs_anio_normal": (_mejora("test_whatif_observado", "base_anio_normal_test"), MEJORA_WHATIF_VS_NORMAL),
    }
    aceptacion: dict[str, Any] = {k: {"mejora": v, "minimo": m, "passed": v >= m} for k, (v, m) in criterios.items()}
    aceptacion["passed"] = all(v["passed"] for v in aceptacion.values())
    for k, v in aceptacion.items():
        if k != "passed":
            print(f"  Aceptación {k}: {v['mejora']:.1%} (mínimo {v['minimo']:.0%}) → {'OK' if v['passed'] else 'FALLA'}")
    print("  MAE en kg/ha (producción vs. tendencia sola):", {
        c: f"{v['modelo']}/{v['tendencia']}" for c, v in metrics["mae_kg_ha_test_produccion"].items()
    })
    print("  Por campaña (real / producción ONI):", {
        a: f"{v['real']}/{metrics['test_produccion_oni']['por_anio'][a]['predicho']}"
        for a, v in metrics["test_produccion_oni"]["por_anio"].items()
    })

    print("\n[3/5] Importancias por permutación (test real, clima observado)...")
    importances = compute_importances(model, test)
    for f, v in sorted(importances["global"].items(), key=lambda kv: -kv[1])[:8]:
        print(f"  - {f:<30} {v:.3f}")

    print("\n[4/5] Chequeos:")
    checks = chequeos(model, catalog, test)
    for k, v in checks.items():
        print(f"  - {k}: {v}")
    checks["aceptacion"] = aceptacion
    checks["all_passed"] = all(v["passed"] for v in checks.values() if isinstance(v, dict) and "passed" in v)

    print("\n[ML-16] Calibración de la probabilidad de año malo (fuera de muestra, 19 campañas):")
    calibracion = calibrar_bundle(model, params, n_iter, tv, test, escenarios)

    print("\n[5/5] Serialización...")
    bundle = {
        "bundle_version": BUNDLE_VERSION,
        "model_version": MODEL_VERSION,
        "trained_at": trained_at,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "sklearn_version": sklearn.__version__,
        "model": model,
        "model_name": "hist_gradient_boosting_monotonic",
        "model_params": {**params, "max_iter": n_iter, "monotonic_cst": MONOTONIC_CST},
        "feature_columns": FEATURE_COLUMNS,
        "crop_feature_encoding": "cultivo_candidato -> crops_catalog.by_name[crop]['id'] (última columna)",
        "target": TARGET_COLUMN,
        "target_semantics": "50 = año normal según la tendencia de largo plazo del departamento (MAGyP); 30 = 20% bajo la tendencia",
        "output_range": [0.0, 100.0],
        "crops_catalog": catalog,
        "cultivos_entrenados": sorted(tv_real["cultivo_candidato"].unique()),
        "feature_importances": importances,
        "feature_baselines": compute_feature_baselines(tv_real),
        "metrics": {**metrics, "cv_loso": {"modelo": comparacion, "base_anio_normal": cv_base}},
        "model_comparison_val": comparacion,
        "sanity_checks": checks,
        "calibracion_anio_malo": calibracion,
    }
    guardar_bundle(bundle, catalog)

    if not checks["all_passed"]:
        print("\nRESULTADO: FALLÓ al menos un chequeo (ver training_metrics.json).")
        return 1
    print("\nRESULTADO: modelo aceptado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
