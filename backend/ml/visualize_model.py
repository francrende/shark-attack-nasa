"""
Visualización del modelo entrenado (`modelo_agro.joblib`) — Herramienta de desarrollo ML.

Genera en `backend/ml/reports/`:
  01_importancia_global.png        Permutation importance global (test 2022-2024, clima observado)
  02_importancia_por_cultivo.png   Heatmap de importancias normalizadas por cultivo
  03_predicho_vs_real_test.png     Predicho vs rinde real MAGyP en test (clima del período crítico observado)
  04_error_por_cultivo.png         MAE por cultivo: producción, What-If y línea base "año normal"
  05_curvas_respuesta_verano.png   Curvas de respuesta (PDP manual) de cultivos de verano
  06_curvas_respuesta_invierno.png Curvas de respuesta de cultivos de invierno
  07_arbol_ilustrativo.png         Primer árbol del ensamble HGB (profundidad limitada)
  08_calibracion_anio_malo.png     ML-16: calibración de la probabilidad de año malo (fuera de muestra)
  09_seguimiento_retrospectivo.png ML-18: mejora de la predicción según el avance del período crítico

Uso:
    backend\\.venv\\Scripts\\pip.exe install -r backend/ml/requirements-dev.txt
    backend\\.venv\\Scripts\\python.exe backend/ml/visualize_model.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ML_DIR = Path(__file__).resolve().parent
DATA_DIR = ML_DIR / "data"
REPORTS_DIR = ML_DIR / "reports"
MODEL_PATH = ML_DIR / "modelo_agro.joblib"

# Escenario base (benchmark de sequía de CONTEXT.md) sobre el cual se varía 1 feature a la vez.
BASE_SCENARIO: dict[str, float] = {
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
    "lluvia_periodo_critico_mm": 340.0,
    "dias_hasta_siembra": 15,
    "oni_actual": 0.0,
}

# Features a barrer en las curvas de respuesta: (nombre, min, max, etiqueta)
RESPONSE_SWEEPS: list[tuple[str, float, float, str]] = [
    ("gwetroot_saturacion_pct", 5, 100, "Humedad radicular GWETROOT (%)"),
    ("anomalia_lluvia_90d_pct", -70, 80, "Anomalía de lluvia 90d (%)"),
    ("frecuencia_estres_termico", 0, 40, "Días con T2M_MAX > 34°C"),
    ("frecuencia_riesgo_helada", 0, 50, "Días con T2M_MIN < 2°C"),
    ("lluvia_periodo_critico_mm", 80, 700, "Lluvia del período crítico (mm)"),
    ("oni_actual", -2, 2, "ONI (ENSO) publicado al decidir"),
]

LABELS_ES: dict[str, str] = {
    "gwetroot_saturacion_pct": "Humedad radicular",
    "gwettop_saturacion_pct": "Humedad superficial",
    "tendencia_humedad_15d_pct": "Tendencia humedad 15d",
    "anomalia_lluvia_90d_pct": "Anomalía lluvia 90d",
    "frecuencia_tormentas_extremas": "Tormentas extremas",
    "frecuencia_estres_termico": "Estrés térmico",
    "frecuencia_riesgo_helada": "Riesgo de helada",
    "indice_aridez_evaporativa": "Índice aridez",
    "pendiente_terreno_pct": "Pendiente",
    "elevacion_m": "Elevación",
    "textura_arcilla_pct": "Arcilla",
    "lluvia_periodo_critico_mm": "Lluvia período crítico",
    "dias_hasta_siembra": "Días hasta siembra",
    "oni_actual": "ONI (ENSO)",
    "cultivo_candidato": "Cultivo candidato",
}


def _save(fig: plt.Figure, name: str) -> None:
    path = REPORTS_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    print(f"  - {path.relative_to(ML_DIR.parent.parent)}")


def _to_x(df: pd.DataFrame, bundle: dict[str, Any]) -> np.ndarray:
    feats = bundle["feature_columns"]
    by_name = bundle["crops_catalog"]["by_name"]
    num = df[feats[:-1]].to_numpy(dtype=float)
    crop = df["cultivo_candidato"].map(lambda c: by_name[c]["id"]).to_numpy(dtype=float)
    return np.column_stack([num, crop])


def _predict(bundle: dict[str, Any], X: np.ndarray) -> np.ndarray:
    return np.clip(bundle["model"].predict(X), 0.0, 100.0)


def _crops(bundle: dict[str, Any], campana: str) -> list[str]:
    """Cultivos de la campaña que puntúa el modelo (ML-10: solo los que tienen rinde MAGyP)."""
    entrenados = set(bundle.get("cultivos_entrenados") or bundle["crops_catalog"]["by_name"])
    return [c for c, v in bundle["crops_catalog"]["by_name"].items() if v["campana"] == campana and c in entrenados]


# ---------------------------------------------------------------------------
def plot_global_importance(bundle: dict[str, Any]) -> None:
    imp = bundle["feature_importances"]["global"]
    items = sorted(imp.items(), key=lambda kv: kv[1])
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.barh([LABELS_ES.get(k, k) for k, _ in items], [v * 100 for _, v in items], color="#2e7d32")
    for i, (_, v) in enumerate(items):
        ax.text(v * 100 + 0.4, i, f"{v * 100:.1f}%", va="center", fontsize=8)
    ax.set_xlabel("Importancia relativa (%) — aumento de MAE al permutar")
    ax.set_title(f"Importancia global de variables ({bundle['model_name']})")
    _save(fig, "01_importancia_global.png")


def plot_importance_by_crop(bundle: dict[str, Any]) -> None:
    per_crop = bundle["feature_importances"]["per_crop"]
    crops = _crops(bundle, "invierno") + _crops(bundle, "verano")
    feats = [f for f in bundle["feature_columns"] if f != "cultivo_candidato"]
    mat = np.array([[per_crop[c].get(f, 0.0) * 100 for f in feats] for c in crops])
    fig, ax = plt.subplots(figsize=(12, 6))
    im = ax.imshow(mat, cmap="YlGn", aspect="auto")
    ax.set_xticks(range(len(feats)), [LABELS_ES[f] for f in feats], rotation=35, ha="right")
    ax.set_yticks(range(len(crops)), crops)
    for i in range(len(crops)):
        for j in range(len(feats)):
            ax.text(j, i, f"{mat[i, j]:.0f}", ha="center", va="center", fontsize=7,
                    color="white" if mat[i, j] > mat.max() * 0.6 else "black")
    ax.axhline(len(_crops(bundle, "invierno")) - 0.5, color="black", lw=1.5)
    fig.colorbar(im, ax=ax, label="Importancia relativa (%)")
    ax.set_title("Importancia de variables por cultivo (arriba: invierno | abajo: verano)")
    _save(fig, "02_importancia_por_cultivo.png")


def plot_pred_vs_real(bundle: dict[str, Any], df_test: pd.DataFrame) -> None:
    y = df_test["s_hidroclimatico"].to_numpy()
    y_hat = _predict(bundle, _to_x(df_test, bundle))
    m = bundle["metrics"]["test_whatif_observado"]["global"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    for campana, color in (("invierno", "#1565c0"), ("verano", "#ef6c00")):
        mask = (df_test["campana"] == campana).to_numpy()
        axes[0].scatter(y[mask], y_hat[mask], s=6, alpha=0.35, color=color, label=campana)
    axes[0].plot([0, 100], [0, 100], "k--", lw=1)
    axes[0].set_xlabel("Puntaje real (rinde MAGyP vs. tendencia, 50 = año normal)")
    axes[0].set_ylabel("S_hidroclimatico predicho")
    axes[0].set_title(f"Test 2022-2024, clima observado | MAE={m['mae']:.2f}  RMSE={m['rmse']:.2f}  R²={m['r2']:.3f}")
    axes[0].legend()
    axes[0].set_xlim(-2, 102)
    axes[0].set_ylim(-2, 102)

    resid = y_hat - y
    axes[1].hist(resid, bins=60, color="#6a1b9a", alpha=0.8)
    axes[1].axvline(0, color="black", lw=1)
    axes[1].set_xlabel("Residuo (predicho − real) [pts]")
    axes[1].set_ylabel("Frecuencia")
    axes[1].set_title(f"Distribución de residuos | p95 |error| = {np.percentile(np.abs(resid), 95):.2f} pts")
    _save(fig, "03_predicho_vs_real_test.png")


def plot_error_by_crop(bundle: dict[str, Any]) -> None:
    crops = _crops(bundle, "invierno") + _crops(bundle, "verano")
    splits = [
        ("test_produccion_oni", "Producción (años análogos)", "#ef5350"),
        ("test_whatif_observado", "What-If (clima observado)", "#42a5f5"),
        ("base_anio_normal_test", 'Línea base "año normal"', "#9e9e9e"),
    ]
    x = np.arange(len(crops))
    w = 0.27
    fig, ax = plt.subplots(figsize=(12, 5))
    for k, (clave, etiqueta, color) in enumerate(splits):
        vals = [bundle["metrics"][clave]["por_cultivo"][c] for c in crops]
        ax.bar(x + (k - 1) * w, vals, w, label=etiqueta, color=color)
    ax.set_xticks(x, crops, rotation=30, ha="right")
    ax.set_ylabel("MAE (pts)")
    ax.set_title("Error absoluto medio por cultivo en test 2022-2024")
    ax.legend()
    _save(fig, "04_error_por_cultivo.png")


def plot_response_curves(bundle: dict[str, Any], campana: str, filename: str) -> None:
    feats = bundle["feature_columns"]
    by_name = bundle["crops_catalog"]["by_name"]
    crops = _crops(bundle, campana)
    base = dict(BASE_SCENARIO)
    if campana == "invierno":
        base.update({"frecuencia_estres_termico": 0, "frecuencia_riesgo_helada": 8, "lluvia_periodo_critico_mm": 250.0})
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5))
    for ax, (feat, lo, hi, label) in zip(axes.ravel(), RESPONSE_SWEEPS):
        grid = np.linspace(lo, hi, 60)
        for crop in crops:
            rows = []
            for v in grid:
                s = dict(base)
                s[feat] = v
                rows.append([s[f] for f in feats[:-1]] + [by_name[crop]["id"]])
            ax.plot(grid, _predict(bundle, np.asarray(rows, dtype=float)), lw=1.8, label=crop)
        ax.axvline(base[feat], color="grey", ls=":", lw=1)
        ax.set_xlabel(label)
        ax.set_ylabel("S_hidroclimatico")
        ax.set_ylim(-2, 102)
        ax.grid(alpha=0.25)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle(
        f"Curvas de respuesta — campaña {campana} (se varía 1 variable; resto fijo en el escenario base, línea gris)",
        fontsize=11,
    )
    _save(fig, filename)


def plot_tree(bundle: dict[str, Any], max_depth: int = 3) -> None:
    model = bundle["model"]
    if not hasattr(model, "_predictors"):
        print("  - (árbol omitido: el modelo no es HistGradientBoosting)")
        return
    predictor = model._predictors[0][0]
    nodes = predictor.nodes
    feats = bundle["feature_columns"]
    # El ColumnTransformer interno de HGB reordena: primero categóricas, luego numéricas.
    is_cat = np.asarray(model.is_categorical_)
    internal_order = [feats[i] for i in np.where(is_cat)[0]] + [feats[i] for i in np.where(~is_cat)[0]]
    by_id = bundle["crops_catalog"]["by_id"]
    bitsets = predictor.raw_left_cat_bitsets

    def left_crops(node: Any) -> list[str]:
        bits = bitsets[node["bitset_idx"]]
        return [by_id[i] for i in sorted(by_id) if (int(bits[i // 32]) >> (i % 32)) & 1]

    fig, ax = plt.subplots(figsize=(18, 8))
    ax.axis("off")

    def draw(idx: int, depth: int, x: float, span: float) -> None:
        n = nodes[idx]
        y = 1.0 - depth * 0.25
        if n["is_leaf"] or depth == max_depth:
            txt = f"hoja\nΔ={n['value']:+.2f}\nn={n['count']}" if n["is_leaf"] else f"…\nn={n['count']}"
            color = "#c8e6c9"
        else:
            raw_name = internal_order[int(n["feature_idx"])]
            fname = LABELS_ES.get(raw_name, raw_name)
            if n["is_categorical"]:
                crops_left = left_crops(n)
                cond = "∈ {" + ",\n".join(", ".join(crops_left[i:i + 2]) for i in range(0, len(crops_left), 2)) + "}"
            else:
                cond = f"≤ {n['num_threshold']:.2f}"
            txt = f"{fname}\n{cond}\nn={n['count']}"
            color = "#bbdefb"
            for child, dx in ((int(n["left"]), -span), (int(n["right"]), span)):
                ax.plot([x, x + dx], [y - 0.03, 1.0 - (depth + 1) * 0.25 + 0.04], color="grey", lw=0.8)
                draw(child, depth + 1, x + dx, span / 2)
        ax.text(x, y, txt, ha="center", va="center", fontsize=8,
                bbox={"boxstyle": "round", "fc": color, "ec": "grey"})

    draw(0, 0, 0.5, 0.25)
    ax.set_xlim(0, 1)
    ax.set_ylim(1.0 - (max_depth + 0.5) * 0.25, 1.08)
    ax.set_title(
        f"Árbol #1 de {model.n_iter_} del ensamble (profundidad ≤ {max_depth}). "
        "Ilustrativo: la predicción final suma las correcciones Δ de todos los árboles. "
        "(rama izquierda = condición verdadera)",
        fontsize=10,
    )
    _save(fig, "07_arbol_ilustrativo.png")


def plot_calibracion_anio_malo(bundle: dict[str, Any]) -> None:
    """ML-16: diagrama de calibración, mejora por cultivo y probabilidad por campaña (fuera de muestra)."""
    cal = bundle.get("calibracion_anio_malo")
    if not cal:
        print("  - (sin calibracion_anio_malo en el bundle: se omite 08)")
        return
    met = cal["metricas"]
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))

    ax = axes[0]
    tramos = met["diagrama"]
    pred = [t["prob_media"] for t in tramos]
    real = [t["frecuencia_real"] for t in tramos]
    tam = [max(20.0, 600.0 * t["fraccion_peso"]) for t in tramos]
    ax.plot([0, 0.5], [0, 0.5], "--", color="#9e9e9e", label="Calibración perfecta")
    ax.scatter(pred, real, s=tam, color="#2e7d32", zorder=3, label="Tramos (tamaño = casos)")
    ax.axhline(met["tasa_anios_malos"], color="#ef5350", lw=1, label=f"Tasa media ({met['tasa_anios_malos']:.0%})")
    ax.set_xlim(0, 0.5)
    ax.set_ylim(0, 0.5)
    ax.set_xlabel("Probabilidad predicha de año malo")
    ax.set_ylabel("Frecuencia real de año malo")
    ax.set_title(f"Calibración fuera de muestra ({len(cal['campanas'])} campañas)")
    ax.legend(fontsize=8, loc="upper left")

    ax = axes[1]
    por_cultivo = met["por_cultivo"]
    crops = sorted(por_cultivo, key=lambda c: por_cultivo[c]["brier_skill"])
    skill = [por_cultivo[c]["brier_skill"] * 100 for c in crops]
    colores = ["#2e7d32" if cal["prob_valida_por_cultivo"][c] else "#bdbdbd" for c in crops]
    ax.barh(crops, skill, color=colores)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("Mejora del Brier contra la probabilidad típica (%)")
    ax.set_title("Por cultivo (gris: se muestra solo la frecuencia habitual)")

    ax = axes[2]
    camp = met["por_campana"]
    anios = sorted(camp, key=int)
    x = np.arange(len(anios))
    ax.bar(x - 0.2, [camp[a]["tasa_real"] for a in anios], 0.4, label="Tasa real de años malos", color="#ef5350")
    ax.bar(x + 0.2, [camp[a]["prob_media"] for a in anios], 0.4, label="Probabilidad media predicha", color="#42a5f5")
    ax.set_xticks(x, [f"{a[2:]}/{(int(a) + 1) % 100:02d}" for a in anios], rotation=60, fontsize=7)
    ax.set_title("Por campaña: lo que pasó vs. lo que se anticipaba")
    ax.legend(fontsize=8)
    _save(fig, "08_calibracion_anio_malo.png")


def plot_seguimiento(bundle: dict[str, Any]) -> None:
    """ML-18: cómo mejora la predicción a medida que se observa el período crítico."""
    seg = bundle.get("seguimiento")
    if not seg:
        print("  - (sin seguimiento en el bundle: se omite 09)")
        return
    res = seg["resumen"]
    niveles = seg["niveles"]
    x = [float(n) * 100 for n in niveles]
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))

    ax = axes[0]
    ax.plot(x, [res[n]["brier_skill"] * 100 for n in niveles], "o-", color="#2e7d32", label="Mejora del Brier vs. típica")
    ax.plot(x, [(res[n]["auc_anios_malos"] - 0.5) * 100 for n in niveles], "s--", color="#42a5f5", label="AUC − 0,5 (×100)")
    ax.set_xlabel("Avance del período crítico (%)")
    ax.set_ylabel("%")
    ax.set_title("Detección de años malos")
    ax.legend(fontsize=8)

    ax = axes[1]
    ax.plot(x, [res[n]["mae"] for n in niveles], "o-", color="#ef5350", label="MAE")
    ax.plot(x, [res[n]["ancho_rango_medio"] / 2 for n in niveles], "s--", color="#8d6e63", label="Medio ancho del rango")
    ax.set_xlabel("Avance del período crítico (%)")
    ax.set_ylabel("Puntos (50 = año normal)")
    ax.set_title("Error y rango")
    ax.legend(fontsize=8)

    ax = axes[2]
    ax.plot(x, [res[n]["sequia_2022_prob_media"] for n in niveles], "o-", color="#b8292f", label="Probabilidad media 2022/23")
    ax.axhline(res[niveles[0]]["sequia_2022_prob_tipica"], color="#9e9e9e", ls="--", label="Probabilidad típica")
    ax.set_xlabel("Avance del período crítico (%)")
    ax.set_ylabel("Probabilidad de año malo")
    ax.set_title("Sequía 2022/23: cuándo la anticipa")
    ax.legend(fontsize=8)
    _save(fig, "09_seguimiento_retrospectivo.png")


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    bundle = joblib.load(MODEL_PATH)
    df_test = pd.read_csv(DATA_DIR / "dataset_magyp_test.csv.gz", dtype={"departamento_id": str})
    df_test = df_test[df_test["origen_muestra"] == "magyp_real"].reset_index(drop=True)
    print(f"Modelo: {bundle['model_name']} | entrenado: {bundle['trained_at']}")
    print("Generando gráficos en backend/ml/reports/ ...")
    plot_global_importance(bundle)
    plot_importance_by_crop(bundle)
    plot_pred_vs_real(bundle, df_test)
    plot_error_by_crop(bundle)
    plot_response_curves(bundle, "verano", "05_curvas_respuesta_verano.png")
    plot_response_curves(bundle, "invierno", "06_curvas_respuesta_invierno.png")
    plot_tree(bundle)
    plot_calibracion_anio_malo(bundle)
    plot_seguimiento(bundle)
    print("Listo.")


if __name__ == "__main__":
    main()
