"""Label real del ML (ML-6): rindes departamentales de MAGyP → puntaje vs. tendencia.

Pipeline puro (sin red salvo ``descargar_csv``):
1. ``filtrar_pampa``: región pampeana, 2006/07+, cultivos del modelo (cebada cervecera
   hasta 2015/16 y cebada total desde 2016/17).
2. ``calcular_labels``: rinde ajustado por abandono → tendencia Theil–Sen sobre los años de
   entrenamiento → ``puntaje = 50 + 100 × (rinde_aj / tendencia − 1)`` recortado a [0, 100].
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

URL_CSV = (
    "https://datos.magyp.gob.ar/dataset/9e1e77ba-267e-4eaa-a59f-3296e86b5f36/resource/"
    "95d066e6-8a0f-4a80-b59d-6f28f88eacd5/download/estimaciones-agricolas-2026-03.csv"
)

PROVINCIAS_PAMPA: dict[str, str] = {
    "06": "Buenos Aires",
    "14": "Córdoba",
    "30": "Entre Ríos",
    "42": "La Pampa",
    "82": "Santa Fe",
}
ANIO_MIN = 2006
ANIO_CEBADA_TOTAL = 2016  # antes de 2016/17 solo existe "cebada cervecera"

# cultivo MAGyP → (cultivo_magyp normalizado, primer año, último año)
MAPEO_CULTIVOS: dict[str, tuple[str, int, int]] = {
    "trigo total": ("trigo", ANIO_MIN, 9999),
    "cebada cervecera": ("cebada", ANIO_MIN, ANIO_CEBADA_TOTAL - 1),
    "cebada total": ("cebada", ANIO_CEBADA_TOTAL, 9999),
    "maíz": ("maiz", ANIO_MIN, 9999),
    "soja 1ra": ("soja_primera", ANIO_MIN, 9999),
    "soja 2da": ("soja_segunda", ANIO_MIN, 9999),
    "girasol": ("girasol", ANIO_MIN, 9999),
    "sorgo": ("sorgo", ANIO_MIN, 9999),
}

# cultivo del modelo → cultivo_magyp (los dos maíces comparten rinde)
CULTIVO_MODELO_A_MAGYP: dict[str, str] = {
    "trigo": "trigo",
    "cebada": "cebada",
    "maiz_temprano": "maiz",
    "maiz_tardio": "maiz",
    "soja_primera": "soja_primera",
    "soja_segunda": "soja_segunda",
    "girasol": "girasol",
    "sorgo": "sorgo",
}

SUPERFICIE_MIN_HA = 1000.0
MIN_ANIOS_TRAIN = 8
PISO_TENDENCIA_REL = 0.30


def descargar_csv(destino: Path, url: str = URL_CSV, timeout_s: float = 120.0) -> Path:
    import httpx

    destino.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, timeout=timeout_s, follow_redirects=True) as resp:
        resp.raise_for_status()
        with destino.open("wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)
    return destino


def filtrar_pampa(crudo: pd.DataFrame) -> pd.DataFrame:
    """Normaliza el CSV consolidado de MAGyP al subconjunto del modelo."""
    df = crudo.copy()
    df["departamento_id"] = df["departamento_id"].astype(str).str.zfill(5)
    df = df[df["departamento_id"].str[:2].isin(PROVINCIAS_PAMPA)]
    df["anio_campana"] = df["campania"].astype(str).str[:4].astype(int)
    df = df[df["cultivo"].isin(MAPEO_CULTIVOS)]

    filas = []
    for cultivo, (normalizado, desde, hasta) in MAPEO_CULTIVOS.items():
        parte = df[(df["cultivo"] == cultivo) & df["anio_campana"].between(max(desde, ANIO_MIN), hasta)]
        filas.append(parte.assign(cultivo_magyp=normalizado))
    out = pd.concat(filas, ignore_index=True)

    numericas = ["superficie_sembrada_ha", "superficie_cosechada_ha", "produccion_tm", "rendimiento_kgxha"]
    for col in numericas:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    columnas = ["departamento_id", "provincia", "departamento", "cultivo_magyp", "anio_campana", *numericas]
    return out[columnas].sort_values(["departamento_id", "cultivo_magyp", "anio_campana"]).reset_index(drop=True)


def tendencia_theil_sen(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """(pendiente, ordenada) Theil–Sen: mediana de pendientes de a pares, robusta a sequías."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 2:
        return 0.0, float(np.median(y)) if len(y) else 0.0
    i, j = np.triu_indices(len(x), k=1)
    dx = x[j] - x[i]
    validos = dx != 0
    pendiente = float(np.median((y[j] - y[i])[validos] / dx[validos])) if validos.any() else 0.0
    ordenada = float(np.median(y - pendiente * x))
    return pendiente, ordenada


def puntaje_vs_tendencia(rinde: np.ndarray | float, tendencia: np.ndarray | float) -> np.ndarray:
    """50 = año normal; 30 = 20% bajo la tendencia; 0 = la mitad o menos."""
    ratio = np.asarray(rinde, dtype=float) / np.asarray(tendencia, dtype=float)
    return np.clip(50.0 + 100.0 * (ratio - 1.0), 0.0, 100.0)


def _rinde_observado(g: pd.DataFrame) -> pd.Series:
    """Rinde cosechado (kg/ha); 0 si se sembró y no se cosechó nada."""
    rinde = g["rendimiento_kgxha"].copy()
    calculado = 1000.0 * g["produccion_tm"] / g["superficie_cosechada_ha"].where(g["superficie_cosechada_ha"] > 0)
    rinde = rinde.where(rinde > 0, calculado)
    sin_cosecha = g["superficie_cosechada_ha"].fillna(0) <= 0
    return rinde.mask(sin_cosecha, 0.0)


def _base_rindes(df: pd.DataFrame) -> pd.DataFrame:
    base = df[df["superficie_sembrada_ha"] >= SUPERFICIE_MIN_HA].copy()
    base["rinde_kgxha"] = _rinde_observado(base)
    base["fraccion_cosechada"] = (
        base["superficie_cosechada_ha"].fillna(0) / base["superficie_sembrada_ha"]
    ).clip(0.0, 1.0)
    return base.dropna(subset=["rinde_kgxha"])


def _ajustar_grupo(g: pd.DataFrame, anios_train: set[int]) -> tuple[pd.DataFrame, dict[str, Any]] | None:
    """Rinde ajustado por abandono y parámetros de la tendencia de un departamento × cultivo.

    ``None`` si hay menos de ``MIN_ANIOS_TRAIN`` campañas o nunca se cosechó.
    """
    train = g[g["anio_campana"].isin(anios_train)]
    if len(train) < MIN_ANIOS_TRAIN:
        return None
    fc_tipica = float(train["fraccion_cosechada"].median())
    if fc_tipica <= 0:
        return None
    g = g.copy()
    g["fraccion_tipica"] = fc_tipica
    g["rinde_ajustado"] = g["rinde_kgxha"] * np.minimum(1.0, g["fraccion_cosechada"] / fc_tipica)

    train_aj = g.loc[g["anio_campana"].isin(anios_train), ["anio_campana", "rinde_ajustado"]]
    pendiente, ordenada = tendencia_theil_sen(train_aj["anio_campana"].to_numpy(), train_aj["rinde_ajustado"].to_numpy())
    piso = max(PISO_TENDENCIA_REL * float(train_aj["rinde_ajustado"].median()), 1.0)
    params = {
        "pendiente": pendiente,
        "ordenada": ordenada,
        "piso": piso,
        "fraccion_tipica": fc_tipica,
        "anio_min": int(train_aj["anio_campana"].min()),
        "anio_max": int(train_aj["anio_campana"].max()),
        "n_campanas": int(len(train_aj)),
    }
    return g, params


def tendencia_en(params: Mapping[str, Any], anios: np.ndarray | int) -> np.ndarray:
    """Rinde normal (kg/ha) según la tendencia en el/los año(s) de campaña ``anios``."""
    valor = float(params["ordenada"]) + float(params["pendiente"]) * np.asarray(anios, dtype=float)
    return np.maximum(valor, float(params["piso"]))


def tendencias_por_departamento(df: pd.DataFrame, anios: Iterable[int]) -> dict[str, Any]:
    """Parámetros de la tendencia por departamento × cultivo_magyp (ML-17).

    Mismo ajuste que ``calcular_labels``: la tendencia proyectada a un año reproduce
    ``tendencia_kgxha`` y, con ella, el puntaje se puede convertir de vuelta a kg/ha.
    """
    anios = set(anios)
    out: dict[str, Any] = {}
    for (dep, cultivo), g in _base_rindes(df).groupby(["departamento_id", "cultivo_magyp"], sort=True):
        ajuste = _ajustar_grupo(g, anios)
        if ajuste is None:
            continue
        _, params = ajuste
        dep_out = out.setdefault(str(dep), {
            "nombre": str(g["departamento"].iloc[0]),
            "provincia": str(g["provincia"].iloc[0]),
            "cultivos": {},
        })
        dep_out["cultivos"][str(cultivo)] = {
            k: (round(v, 6) if isinstance(v, float) else v) for k, v in params.items()
        }
    return out


def calcular_labels(df: pd.DataFrame, anios_train: Iterable[int]) -> pd.DataFrame:
    """Puntaje por departamento × cultivo_magyp × campaña.

    Devuelve columnas ``departamento_id, cultivo_magyp, anio_campana, rinde_kgxha,
    fraccion_cosechada, fraccion_tipica, rinde_ajustado, tendencia_kgxha, puntaje``.
    Los parámetros (fracción típica y tendencia) se ajustan solo con ``anios_train``.
    """
    anios_train = set(anios_train)
    salida = []
    for (_, _), g in _base_rindes(df).groupby(["departamento_id", "cultivo_magyp"], sort=False):
        ajuste = _ajustar_grupo(g, anios_train)
        if ajuste is None:
            continue
        g, params = ajuste
        g["tendencia_kgxha"] = tendencia_en(params, g["anio_campana"].to_numpy())
        g["puntaje"] = puntaje_vs_tendencia(g["rinde_ajustado"], g["tendencia_kgxha"]).round(2)
        salida.append(g)

    columnas = [
        "departamento_id", "cultivo_magyp", "anio_campana", "rinde_kgxha", "fraccion_cosechada",
        "fraccion_tipica", "rinde_ajustado", "tendencia_kgxha", "puntaje",
    ]
    if not salida:
        return pd.DataFrame(columns=columnas)
    return pd.concat(salida, ignore_index=True)[columnas]


# ---------------------------------------------------------------------------
# CLI (ML-17): python -m ml.magyp --tendencias
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent / "data"
MAGYP_CSV = DATA_DIR / "magyp_pampa.csv"
TENDENCIAS_JSON = DATA_DIR / "tendencias_magyp.json"
VERSION_TENDENCIAS = 1


def exportar_tendencias(destino: Path = TENDENCIAS_JSON) -> dict[str, Any]:
    """Escribe ``tendencias_magyp.json`` a partir de ``magyp_pampa.csv`` (sin red)."""
    from ml.generate_dataset import ANIOS_TENDENCIA  # import tardío: generate_dataset importa este módulo

    df = pd.read_csv(MAGYP_CSV, dtype={"departamento_id": str})
    departamentos = tendencias_por_departamento(df, ANIOS_TENDENCIA)
    salida = {
        "version": VERSION_TENDENCIAS,
        "fuente": "MAGyP Estimaciones Agrícolas, rinde ajustado por abandono (ml/magyp.py)",
        "metodo": "Theil–Sen por departamento × cultivo, mismo ajuste que el label del modelo (calcular_labels)",
        "anios": [ANIOS_TENDENCIA.start, ANIOS_TENDENCIA.stop - 1],
        "cultivo_modelo_a_magyp": CULTIVO_MODELO_A_MAGYP,
        "departamentos": departamentos,
    }
    destino.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    return salida


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Utilidades MAGyP del modelo")
    parser.add_argument("--tendencias", action="store_true", help=f"escribe {TENDENCIAS_JSON.name}")
    args = parser.parse_args(argv)
    if not args.tendencias:
        parser.print_help()
        return 1
    salida = exportar_tendencias()
    n = sum(len(d["cultivos"]) for d in salida["departamentos"].values())
    print(f"{TENDENCIAS_JSON}: {len(salida['departamentos'])} departamentos, {n} pares departamento × cultivo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
