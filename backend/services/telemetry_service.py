"""Orquestación de ``GET /api/v1/telemetry`` (BACK-20 / BACK-23, unificada en BACK-24).

Desde BACK-24, los datos del lote salen del servicio único ``services.datos_lote`` (el mismo
que usa ``/simulate``), en modo tolerante:

- Suelo y topografía del campo (``public.fields``) si son reales; si no, ISRIC/SRTM, y lo
  obtenido se guarda en el campo.
- Clima histórico de la celda: la misma búsqueda que el modelo (memoria → Supabase → JSON →
  NASA en vivo). Si falta, se muestran las métricas recientes con un aviso.
- Indicadores (``indicadores_telemetria``): el mismo cálculo que ``telemetria_nasa`` de
  ``/simulate``, así Info general y la simulación muestran los mismos números.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Awaitable, Callable, Mapping
from datetime import date, datetime, timezone
from typing import Any

import httpx

from providers.nasa_power import NasaPowerUnavailable
from providers.nasa_telemetry import indicadores_telemetria
from providers.soilgrids import SoilGridsUnavailable
from providers.srtm import SrtmUnavailable
from services.datos_lote import obtener_datos_lote
from services.field_enrichment_service import (
    perfil_suelo_no_disponible,
    serializar_perfil_suelo,
    serializar_topografia,
)

logger = logging.getLogger(__name__)

TelemetryFetcher = Callable[..., Awaitable[dict[str, Any]]]
FieldUpdater = Callable[[dict[str, Any]], Awaitable[None] | None]

ADV_NASA_NO_DISPONIBLE = "Telemetría satelital NASA POWER no disponible en este momento."
ADV_HISTORICO_NO_DISPONIBLE = (
    "Referencia climática histórica no disponible en este momento; se muestran las métricas recientes."
)
ADV_SUELO_NO_DISPONIBLE = "Propiedades del suelo no disponibles en este momento para esta ubicación."
ADV_TOPO_NO_DISPONIBLE = "Topografía SRTM no disponible en este momento para esta ubicación."


def _validar_coordenadas(lat: float, lon: float) -> None:
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise ValueError(f"Coordenadas inválidas: ({lat!r}, {lon!r})")
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError(f"Coordenadas fuera de rango: lat={lat}, lon={lon}")


async def obtener_telemetria_campo(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
    today: date | None = None,
    field_row: Mapping[str, Any] | None = None,
    persist_field_updates: FieldUpdater | None = None,
) -> dict[str, Any]:
    """Info general del lote: NASA en vivo + suelo y topografía (del campo o de los providers)."""
    _validar_coordenadas(lat, lon)
    hoy = today or datetime.now(timezone.utc).date()

    datos = await obtener_datos_lote(
        lat,
        lon,
        campo=field_row,
        persistir_campo=persist_field_updates,
        client=client,
        today=hoy,
        exigir_todo=False,
    )

    advertencias: list[str] = []
    telemetria_nasa: dict[str, Any] | None = None
    if datos.reciente is None:
        advertencias.append(ADV_NASA_NO_DISPONIBLE)
    else:
        if datos.referencia is None:
            advertencias.append(ADV_HISTORICO_NO_DISPONIBLE)
        indicadores = indicadores_telemetria(datos.reciente, datos.referencia)
        telemetria_nasa = {**indicadores, "fecha_ultimo_dato_valido": indicadores["fecha_ultimo_dato_valido"].isoformat()}

    if datos.perfil_suelo is None:
        perfil_suelo = perfil_suelo_no_disponible()
        advertencias.append(ADV_SUELO_NO_DISPONIBLE)
    else:
        perfil_suelo = serializar_perfil_suelo(datos.perfil_suelo)
        advertencias.extend(datos.perfil_suelo.advertencias)

    topografia_srtm: dict[str, Any] | None = None
    if datos.topografia is None:
        advertencias.append(ADV_TOPO_NO_DISPONIBLE)
    else:
        topografia_srtm = serializar_topografia(datos.topografia)
        advertencias.extend(datos.topografia.advertencias)

    if telemetria_nasa is None and topografia_srtm is None and datos.perfil_suelo is None:
        for clave, tipo in (("nasa", NasaPowerUnavailable), ("suelo", SoilGridsUnavailable), ("topo", SrtmUnavailable)):
            if isinstance(datos.errores.get(clave), tipo):
                raise datos.errores[clave]
        raise NasaPowerUnavailable("Ningún proveedor satelital o edáfico pudo responder.")

    return {
        "ubicacion": {"lat": lat, "lon": lon},
        "telemetria_nasa": telemetria_nasa,
        "topografia_srtm": topografia_srtm,
        "perfil_suelo": perfil_suelo,
        "advertencias": list(dict.fromkeys(advertencias)),
    }
