"""Rinde en kg/ha a partir del puntaje (ML-17).

El label del modelo es ``puntaje = 50 + 100 × (rinde / tendencia − 1)``, con la tendencia
Theil–Sen del departamento y cultivo (``magyp.calcular_labels``). Acá se invierte:

    rinde_kg_ha = tendencia(departamento, cultivo, año) × (1 + (puntaje − 50) / 100)

Es el rinde **del departamento**, no del lote. Los valores se redondean a 50 kg/ha.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

TENDENCIAS_JSON = Path(__file__).resolve().parent / "data" / "tendencias_magyp.json"
REDONDEO_KG = 50.0
PUNTAJE_NORMAL = 50.0

MOTIVO_SIN_MAGYP = "No hay rindes históricos de MAGyP para este cultivo."
MOTIVO_FUERA_DE_COBERTURA = "Tu lote está fuera de la zona con datos de rinde (región pampeana)."
MOTIVO_SIN_UBICACION = "No se indicó la ubicación del lote."


@lru_cache(maxsize=1)
def tendencias() -> dict[str, Any]:
    return json.loads(TENDENCIAS_JSON.read_text(encoding="utf-8"))


def _redondear(kg: float) -> float:
    return float(round(kg / REDONDEO_KG) * REDONDEO_KG)


def rinde_desde_puntaje(puntaje: float, normal_kg: float) -> float:
    return max(0.0, float(normal_kg) * (1.0 + (float(puntaje) - PUNTAJE_NORMAL) / 100.0))


def rinde_normal_kg_ha(cultivo: str, departamento: str, anio_campana: int) -> float | None:
    """Rinde normal (tendencia) del cultivo en el departamento, o ``None`` si no hay dato."""
    datos = tendencias()
    magyp = datos["cultivo_modelo_a_magyp"].get(cultivo)
    params = datos["departamentos"].get(departamento, {}).get("cultivos", {}).get(magyp) if magyp else None
    if params is None:
        return None
    valor = float(params["ordenada"]) + float(params["pendiente"]) * float(anio_campana)
    return float(np.maximum(valor, float(params["piso"])))


def vacio(motivo: str) -> dict[str, Any]:
    return {"esperado": None, "anio_malo": None, "anio_bueno": None, "normal": None, "motivo_sin_dato": motivo}


def rinde_kg_ha(
    cultivo: str,
    departamento: str,
    nombre_departamento: str,
    anio_campana: int,
    puntaje_esperado: float | None,
    puntaje_anio_malo: float | None,
    puntaje_anio_bueno: float | None,
) -> dict[str, Any]:
    """``{"esperado", "anio_malo", "anio_bueno", "normal", "motivo_sin_dato"}`` en kg/ha."""
    if cultivo not in tendencias()["cultivo_modelo_a_magyp"] or puntaje_esperado is None:
        return vacio(MOTIVO_SIN_MAGYP)
    normal = rinde_normal_kg_ha(cultivo, departamento, anio_campana)
    if normal is None:
        return vacio(f"No hay suficientes campañas de este cultivo en {nombre_departamento} para estimar lo normal.")

    def conv(p: float | None) -> float | None:
        return None if p is None else _redondear(rinde_desde_puntaje(p, normal))

    return {
        "esperado": conv(puntaje_esperado),
        "anio_malo": conv(puntaje_anio_malo),
        "anio_bueno": conv(puntaje_anio_bueno),
        "normal": _redondear(normal),
        "motivo_sin_dato": None,
    }


# ---------------------------------------------------------------------------
# BACK-31: rinde de la zona por campaña (pestaña de información histórica)
# ---------------------------------------------------------------------------

MAGYP_CSV = Path(__file__).resolve().parent / "data" / "magyp_pampa.csv"


@lru_cache(maxsize=1)
def _rindes_magyp() -> dict[str, list[tuple[str, int, float]]]:
    """``{departamento: [(cultivo_magyp, año de campaña, rinde observado kg/ha)]}``.

    Mismo filtro que el label (``magyp._base_rindes``): superficie sembrada ≥ 1000 ha; 0 kg/ha si
    se sembró y no se cosechó nada.
    """
    import pandas as pd

    from ml.magyp import _base_rindes

    base = _base_rindes(pd.read_csv(MAGYP_CSV, dtype={"departamento_id": str}))
    salida: dict[str, list[tuple[str, int, float]]] = {}
    for fila in base[["departamento_id", "cultivo_magyp", "anio_campana", "rinde_kgxha"]].itertuples(index=False):
        salida.setdefault(str(fila.departamento_id), []).append(
            (str(fila.cultivo_magyp), int(fila.anio_campana), float(fila.rinde_kgxha))
        )
    return salida


def rinde_zona_por_campana(departamento: str) -> dict[int, list[dict[str, Any]]]:
    """Rinde MAGyP del departamento por campaña y cultivo, contra su rinde normal (tendencia).

    ``{año: [{"cultivo", "rinde_kg_ha", "normal_kg_ha", "vs_normal_pct"}]}``. ``cultivo`` es el
    nombre MAGyP (``trigo``, ``cebada``, ``maiz``, ``soja_primera``, ``soja_segunda``, ``girasol``,
    ``sorgo``). Sin tendencia para ese cultivo en el departamento, ``normal`` y el desvío son None.
    """
    params_dep = tendencias()["departamentos"].get(departamento, {}).get("cultivos", {})
    salida: dict[int, list[dict[str, Any]]] = {}
    for cultivo, anio, rinde in sorted(_rindes_magyp().get(departamento, [])):
        params = params_dep.get(cultivo)
        normal = None
        if params is not None:
            normal = max(float(params["ordenada"]) + float(params["pendiente"]) * anio, float(params["piso"]))
        salida.setdefault(anio, []).append({
            "cultivo": cultivo,
            "rinde_kg_ha": _redondear(rinde),
            "normal_kg_ha": _redondear(normal) if normal is not None else None,
            "vs_normal_pct": round((rinde / normal - 1.0) * 100.0) if normal else None,
        })
    return salida
