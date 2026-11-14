"""
Entrenamiento, Selección de Modelo y Validación Agronómica (ML-2).

Pipeline:
1. Carga los splits temporales Out-of-Time generados por ML-1:
   - train.csv (2006-2019) | val.csv (2020-2022) | test.csv (2023-2025)
2. Compara candidatos de HistGradientBoostingRegressor (feature categórica nativa para
   `cultivo_candidato`) vs RandomForestRegressor sobre val.csv y elige el mejor (RMSE).
3. Re-evalúa el ganador en train/val/test (global y por cultivo).
4. Precalcula permutation_importance (global y por cultivo) en val.csv + baselines de
   features para explicabilidad (`factores_clave_ml`) en < 1 ms durante la inferencia.
5. Ejecuta Sanity Checks (R² > 0.85 y MAE < 5.0 en Test, gap de generalización,
   latencia < 15 ms, rango [0, 100] y benchmark de sequía de CONTEXT.md).
6. Serializa `backend/ml/modelo_agro.joblib` + `backend/ml/data/training_metrics.json`.

Uso:
    backend\\.venv\\Scripts\\python.exe backend/ml/train_baseline.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import max_error, mean_absolute_error, mean_squared_error, r2_score

SEED = 42

ML_DIR = Path(__file__).resolve().parent
DATA_DIR = ML_DIR / "data"
MODEL_PATH = ML_DIR / "modelo_agro.joblib"
METRICS_PATH = DATA_DIR / "training_metrics.json"

# Las 12 features oficiales de CONTEXT.md (Sección 4.3). La #12 (`cultivo_candidato`)
# ingresa al modelo codificada con el id entero del catálogo (`cultivo_id`).
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
NUMERIC_FEATURES = FEATURE_COLUMNS[:-1]
CROP_FEATURE_INDEX = len(FEATURE_COLUMNS) - 1
TARGET_COLUMN = "s_hidroclimatico"

# Criterios de aceptación (Definition of Done)
MIN_TEST_R2 = 0.85
MAX_TEST_MAE = 5.0
MAX_R2_GAP_TRAIN_TEST = 0.10
MAX_LATENCY_MS = 15.0

# Escenario testigo de sequía de CONTEXT.md (Sección 5) — mismo que ML-1.
DROUGHT_BENCHMARK_FEATURES: dict[str, float] = {
    "gwetroot_saturacion_pct": 34.0,
    "gwettop_saturacion_pct": 28.5,
    "tendencia_humedad_15d_pct": -12.0,
    "anomalia_lluvia_90d_pct": -24.2,
    "frecuencia_tormentas_extremas": 1,
    "frecuencia_estres_termico": 6,
    "frecuencia_riesgo_helada": 0,
    "indice_aridez_evaporativa": 0.52,
    "pendiente_terreno_pct": 1.8,
    "elevacion_m": 78.5,
    "textura_arcilla_pct": 24.5,
}
DROUGHT_WINNERS = ["sorgo", "girasol"]
DROUGHT_LOSERS = ["maiz_temprano", "soja_primera"]
DROUGHT_MIN_MARGIN = 10.0  # puntos de diferencia mínima ("superar ampliamente")


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------
def load_metadata() -> dict[str, Any]:
    with open(DATA_DIR / "dataset_metadata.json", encoding="utf-8") as f:
        return json.load(f)


def build_crops_catalog(metadata: dict[str, Any]) -> dict[str, Any]:
    by_name = {
        name: {"id": int(v["id"]), "campana": v["campana"]}
        for name, v in metadata["crops_catalog"].items()
    }
    by_id = {v["id"]: name for name, v in by_name.items()}
    return {"by_name": by_name, "by_id": by_id}


def to_xy(df: pd.DataFrame, catalog: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """Convierte un DataFrame de ML-1 en la matriz X (12 features) y el vector y."""
    crop_ids = df["cultivo_candidato"].map(lambda c: catalog["by_name"][c]["id"])
    X = np.column_stack([df[NUMERIC_FEATURES].to_numpy(dtype=float), crop_ids.to_numpy(dtype=float)])
    y = df[TARGET_COLUMN].to_numpy(dtype=float)
    return X, y


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
def predict_clipped(model: Any, X: np.ndarray) -> np.ndarray:
    return np.clip(model.predict(X), 0.0, 100.0)


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "n": int(len(y_true)),
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4),
        "r2": round(float(r2_score(y_true, y_pred)), 4),
        "max_error": round(float(max_error(y_true, y_pred)), 4),
    }


def evaluate_split(model: Any, df: pd.DataFrame, catalog: dict[str, Any]) -> dict[str, Any]:
    X, y = to_xy(df, catalog)
    y_pred = predict_clipped(model, X)
    per_crop: dict[str, Any] = {}
    for crop in catalog["by_name"]:
        mask = (df["cultivo_candidato"] == crop).to_numpy()
        if mask.sum() > 1:
            per_crop[crop] = regression_metrics(y[mask], y_pred[mask])
    return {"global": regression_metrics(y, y_pred), "per_crop": per_crop}


# ---------------------------------------------------------------------------
# Candidatos y selección
# ---------------------------------------------------------------------------
def candidate_models() -> dict[str, Any]:
    categorical_mask = [False] * len(NUMERIC_FEATURES) + [True]
    candidates: dict[str, Any] = {}
    hgb_grid = [
        {"learning_rate": 0.05, "max_iter": 800, "max_leaf_nodes": 31, "min_samples_leaf": 20, "l2_regularization": 1.0},
        {"learning_rate": 0.05, "max_iter": 1000, "max_leaf_nodes": 63, "min_samples_leaf": 30, "l2_regularization": 2.0},
        {"learning_rate": 0.03, "max_iter": 1500, "max_leaf_nodes": 31, "min_samples_leaf": 15, "l2_regularization": 0.5},
    ]
    for i, params in enumerate(hgb_grid, start=1):
        candidates[f"hist_gradient_boosting_v{i}"] = HistGradientBoostingRegressor(
            loss="squared_error",
            categorical_features=categorical_mask,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=40,
            random_state=SEED,
            **params,
        )
    rf_grid = [
        {"n_estimators": 300, "max_depth": None, "min_samples_leaf": 3, "max_features": 0.6},
        {"n_estimators": 300, "max_depth": 20, "min_samples_leaf": 5, "max_features": 0.8},
    ]
    for i, params in enumerate(rf_grid, start=1):
        candidates[f"random_forest_v{i}"] = RandomForestRegressor(
            random_state=SEED, n_jobs=-1, **params
        )
    return candidates


def select_best_model(
    X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray
) -> tuple[str, Any, dict[str, Any]]:
    comparison: dict[str, Any] = {}
    best_name, best_model, best_rmse = "", None, float("inf")
    for name, model in candidate_models().items():
        t0 = time.perf_counter()
        model.fit(X_train, y_train)
        fit_s = time.perf_counter() - t0
        val_metrics = regression_metrics(y_val, predict_clipped(model, X_val))
        val_metrics["fit_seconds"] = round(fit_s, 2)
        comparison[name] = val_metrics
        print(
            f"  - {name:<28} Val RMSE={val_metrics['rmse']:.3f}  MAE={val_metrics['mae']:.3f}  "
            f"R²={val_metrics['r2']:.4f}  ({fit_s:.1f}s)"
        )
        if val_metrics["rmse"] < best_rmse:
            best_name, best_model, best_rmse = name, model, val_metrics["rmse"]
    return best_name, best_model, comparison


# ---------------------------------------------------------------------------
# Explicabilidad
# ---------------------------------------------------------------------------
def _normalize_importances(raw: np.ndarray) -> dict[str, float]:
    clipped = np.clip(raw, 0.0, None)
    total = clipped.sum()
    weights = clipped / total if total > 0 else np.full_like(clipped, 1.0 / len(clipped))
    return {feat: round(float(w), 5) for feat, w in zip(FEATURE_COLUMNS, weights)}


def compute_importances(
    model: Any, df_val: pd.DataFrame, catalog: dict[str, Any]
) -> dict[str, Any]:
    X_val, y_val = to_xy(df_val, catalog)
    glob = permutation_importance(
        model, X_val, y_val, n_repeats=8, random_state=SEED, scoring="neg_mean_absolute_error"
    )
    per_crop: dict[str, Any] = {}
    for crop in catalog["by_name"]:
        mask = (df_val["cultivo_candidato"] == crop).to_numpy()
        res = permutation_importance(
            model, X_val[mask], y_val[mask], n_repeats=8, random_state=SEED,
            scoring="neg_mean_absolute_error",
        )
        imp = _normalize_importances(res.importances_mean)
        imp.pop("cultivo_candidato", None)  # constante dentro de un cultivo
        total = sum(imp.values()) or 1.0
        per_crop[crop] = {k: round(v / total, 5) for k, v in imp.items()}
    return {
        "method": "permutation_importance (scoring=neg_mean_absolute_error, n_repeats=8, split=val 2020-2022)",
        "global": _normalize_importances(glob.importances_mean),
        "global_raw_mae_increase": {
            feat: round(float(v), 4) for feat, v in zip(FEATURE_COLUMNS, glob.importances_mean)
        },
        "per_crop": per_crop,
    }


def compute_feature_baselines(df: pd.DataFrame) -> dict[str, Any]:
    baselines: dict[str, Any] = {}
    for feat in NUMERIC_FEATURES:
        s = df[feat].astype(float)
        baselines[feat] = {
            "mean": round(float(s.mean()), 4),
            "std": round(float(s.std()), 4),
            "p05": round(float(s.quantile(0.05)), 4),
            "p50": round(float(s.quantile(0.50)), 4),
            "p95": round(float(s.quantile(0.95)), 4),
        }
    baselines_by_campaign: dict[str, Any] = {}
    for campana, grp in df.groupby("campana"):
        baselines_by_campaign[campana] = {
            feat: {"mean": round(float(grp[feat].mean()), 4), "std": round(float(grp[feat].std()), 4)}
            for feat in NUMERIC_FEATURES
        }
    return {"global": baselines, "by_campana": baselines_by_campaign}


# ---------------------------------------------------------------------------
# Sanity Checks
# ---------------------------------------------------------------------------
def build_scenario_matrix(features: dict[str, float], crops: list[str], catalog: dict[str, Any]) -> np.ndarray:
    rows = [[float(features[f]) for f in NUMERIC_FEATURES] + [float(catalog["by_name"][c]["id"])] for c in crops]
    return np.asarray(rows, dtype=float)


def run_sanity_checks(
    model: Any, metrics: dict[str, Any], catalog: dict[str, Any], X_test: np.ndarray
) -> dict[str, Any]:
    checks: dict[str, Any] = {}

    test_g, train_g = metrics["test"]["global"], metrics["train"]["global"]
    checks["test_r2"] = {"value": test_g["r2"], "threshold": f"> {MIN_TEST_R2}", "passed": test_g["r2"] > MIN_TEST_R2}
    checks["test_mae"] = {"value": test_g["mae"], "threshold": f"< {MAX_TEST_MAE}", "passed": test_g["mae"] < MAX_TEST_MAE}
    gap = round(train_g["r2"] - test_g["r2"], 4)
    checks["generalization_gap_r2"] = {
        "value": gap, "threshold": f"< {MAX_R2_GAP_TRAIN_TEST}", "passed": gap < MAX_R2_GAP_TRAIN_TEST,
    }

    # Rango: predicciones crudas del modelo sobre Test + valores clippeados
    raw = model.predict(X_test)
    clipped = np.clip(raw, 0.0, 100.0)
    checks["prediction_range"] = {
        "raw_min": round(float(raw.min()), 3), "raw_max": round(float(raw.max()), 3),
        "clipped_min": round(float(clipped.min()), 3), "clipped_max": round(float(clipped.max()), 3),
        "passed": bool(clipped.min() >= 0.0 and clipped.max() <= 100.0),
    }

    # Latencia: batch con todos los cultivos de la campaña de verano (peor caso: 6 cultivos)
    summer = [c for c, v in catalog["by_name"].items() if v["campana"] == "verano"]
    X_lote = build_scenario_matrix(DROUGHT_BENCHMARK_FEATURES, summer, catalog)
    if hasattr(model, "n_jobs"):
        model.set_params(n_jobs=1)  # inferencia online: 1 hilo, sin overhead de joblib
    for _ in range(10):
        predict_clipped(model, X_lote)  # warm-up
    timings = []
    for _ in range(200):
        t0 = time.perf_counter()
        predict_clipped(model, X_lote)
        timings.append((time.perf_counter() - t0) * 1000.0)
    p50, p95 = float(np.percentile(timings, 50)), float(np.percentile(timings, 95))
    checks["latency_ms_batch_campana"] = {
        "batch_size": len(summer), "p50": round(p50, 3), "p95": round(p95, 3),
        "threshold": f"p95 < {MAX_LATENCY_MS}", "passed": p95 < MAX_LATENCY_MS,
    }

    # Benchmark agronómico de sequía (CONTEXT.md Sección 5)
    preds = predict_clipped(model, X_lote)
    scores = {c: round(float(p), 2) for c, p in zip(summer, preds)}
    margin = min(scores[w] for w in DROUGHT_WINNERS) - max(scores[l] for l in DROUGHT_LOSERS)
    checks["drought_benchmark_context_md"] = {
        "scenario": DROUGHT_BENCHMARK_FEATURES,
        "predicted_scores": dict(sorted(scores.items(), key=lambda kv: -kv[1])),
        "rule": f"min({DROUGHT_WINNERS}) - max({DROUGHT_LOSERS}) >= {DROUGHT_MIN_MARGIN}",
        "margin": round(float(margin), 2),
        "passed": bool(margin >= DROUGHT_MIN_MARGIN),
    }

    checks["all_passed"] = all(v["passed"] for k, v in checks.items() if isinstance(v, dict))
    return checks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 78)
    print("ML-2 | Entrenamiento del modelo S_hidroclimatico (Shark Attack)")
    print("=" * 78)

    metadata = load_metadata()
    catalog = build_crops_catalog(metadata)
    df_train = pd.read_csv(DATA_DIR / "train.csv")
    df_val = pd.read_csv(DATA_DIR / "val.csv")
    df_test = pd.read_csv(DATA_DIR / "test.csv")
    print(f"Splits: train={len(df_train)} (2006-2019) | val={len(df_val)} (2020-2022) | test={len(df_test)} (2023-2025)")

    X_train, y_train = to_xy(df_train, catalog)
    X_val, y_val = to_xy(df_val, catalog)
    X_test, _ = to_xy(df_test, catalog)

    print("\n[1/5] Comparación de candidatos sobre val.csv:")
    best_name, model, comparison = select_best_model(X_train, y_train, X_val, y_val)
    print(f"  => Ganador: {best_name}")

    print("\n[2/5] Evaluación del ganador (train / val / test):")
    metrics = {
        "train": evaluate_split(model, df_train, catalog),
        "val": evaluate_split(model, df_val, catalog),
        "test": evaluate_split(model, df_test, catalog),
    }
    for split, m in metrics.items():
        g = m["global"]
        print(f"  - {split:<5} MAE={g['mae']:.3f}  RMSE={g['rmse']:.3f}  R²={g['r2']:.4f}  MaxErr={g['max_error']:.2f}")

    print("\n[3/5] Permutation importance (global y por cultivo) sobre val.csv...")
    importances = compute_importances(model, df_val, catalog)
    top = sorted(importances["global"].items(), key=lambda kv: -kv[1])[:6]
    for feat, w in top:
        print(f"  - {feat:<30} {w:.3f}")
    df_all_train_val = pd.concat([df_train, df_val], ignore_index=True)
    feature_baselines = compute_feature_baselines(df_all_train_val)

    print("\n[4/5] Sanity Checks:")
    checks = run_sanity_checks(model, metrics, catalog, X_test)
    for name, c in checks.items():
        if isinstance(c, dict):
            status = "OK  " if c["passed"] else "FAIL"
            detail = {k: v for k, v in c.items() if k not in ("passed", "scenario", "predicted_scores")}
            print(f"  [{status}] {name}: {detail}")
    print(f"  Benchmark sequía (verano): {checks['drought_benchmark_context_md']['predicted_scores']}")

    print("\n[5/5] Serialización...")
    trained_at = datetime.now(timezone.utc).isoformat()
    model_params = {k: (v if isinstance(v, (int, float, str, bool, type(None))) else str(v))
                    for k, v in model.get_params().items()}
    bundle = {
        "bundle_version": "1.0.0",
        "trained_at": trained_at,
        "sklearn_version": sklearn.__version__,
        "model": model,
        "model_name": best_name,
        "model_params": model_params,
        "feature_columns": FEATURE_COLUMNS,
        "crop_feature_encoding": "cultivo_candidato -> crops_catalog.by_name[crop]['id'] (feature índice 11)",
        "target": TARGET_COLUMN,
        "output_range": [0.0, 100.0],
        "crops_catalog": catalog,
        "feature_importances": importances,
        "feature_baselines": feature_baselines,
        "metrics": metrics,
        "model_comparison_val": comparison,
        "sanity_checks": checks,
    }
    joblib.dump(bundle, MODEL_PATH, compress=3)

    report = {k: v for k, v in bundle.items() if k != "model"}
    report["crops_catalog"] = {"by_name": catalog["by_name"], "by_id": {str(k): v for k, v in catalog["by_id"].items()}}
    report["model_file"] = str(MODEL_PATH.relative_to(ML_DIR.parent.parent)).replace("\\", "/")
    report["model_file_size_kb"] = round(MODEL_PATH.stat().st_size / 1024, 1)
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"  - {MODEL_PATH} ({report['model_file_size_kb']} KB)")
    print(f"  - {METRICS_PATH}")

    if not checks["all_passed"]:
        print("\nRESULTADO: FALLÓ al menos un Sanity Check. Revisar training_metrics.json.")
        return 1
    print("\nRESULTADO: Todos los Sanity Checks pasaron. Modelo listo para predictor.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
