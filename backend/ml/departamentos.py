"""Departamento MAGyP de referencia para una coordenada (ML-17).

Se usa el departamento pampeano con centroide más cercano (``data/departamentos_pampa.json``).
Más allá de ``DISTANCIA_MAXIMA_KM`` la coordenada queda fuera de cobertura. Cerca de los límites
entre departamentos el centroide puede elegir el vecino; resolverlo bien requiere los polígonos
del IGN (pendiente).

Sin dependencias fuera de ``ml/``: lo usa también el backend (BACK-28).
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

DEPARTAMENTOS_JSON = Path(__file__).resolve().parent / "data" / "departamentos_pampa.json"
DISTANCIA_MAXIMA_KM = 75.0
RADIO_TIERRA_KM = 6371.0


@lru_cache(maxsize=1)
def _centroides() -> tuple[tuple[str, str, str, float, float], ...]:
    datos = json.loads(DEPARTAMENTOS_JSON.read_text(encoding="utf-8"))
    return tuple(
        (codigo, str(d["nombre"]), str(d["provincia"]), float(d["lat"]), float(d["lon"]))
        for codigo, d in sorted(datos.items())
    )


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia haversine en km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(a))


def departamento_mas_cercano(lat: float, lon: float, max_km: float = DISTANCIA_MAXIMA_KM) -> dict[str, Any] | None:
    """``{"codigo", "nombre", "provincia", "distancia_km"}`` o ``None`` si está fuera de cobertura."""
    mejor = min(_centroides(), key=lambda c: distancia_km(lat, lon, c[3], c[4]))
    dist = distancia_km(lat, lon, mejor[3], mejor[4])
    if dist > max_km:
        return None
    return {"codigo": mejor[0], "nombre": mejor[1], "provincia": mejor[2], "distancia_km": round(dist, 1)}


def departamento_por_codigo(
    codigo: str, lat: float | None = None, lon: float | None = None
) -> dict[str, Any] | None:
    """Datos del departamento por código MAGyP.

    Con ``lat``/``lon`` (el lote), ``distancia_km`` es la distancia real al centroide; sin ellas, 0.
    """
    for c in _centroides():
        if c[0] == codigo:
            dist = round(distancia_km(lat, lon, c[3], c[4]), 1) if lat is not None and lon is not None else 0.0
            return {"codigo": c[0], "nombre": c[1], "provincia": c[2], "distancia_km": dist}
    return None
