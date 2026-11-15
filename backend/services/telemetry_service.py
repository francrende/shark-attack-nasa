"""Orquestación asíncrona e independiente de ``GET /api/v1/telemetry`` (BACK-20 / BACK-23).

Consulta en paralelo NASA POWER (ventana reciente liviana + climatología si está
disponible), y reutiliza el perfil de suelo / materia orgánica / topografía guardados en
``public.fields`` cuando ``field_id`` está disponible y ``reintentar_* == False``. Si
faltan datos propios o ``reintentar_* == True``, consulta ISRIC SoilGrids y/o SRTM y
actualiza la fila del campo en ``public.fields``.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import math
from collections.abc import Awaitable, Callable, Mapping
from datetime import date, datetime, timezone
from typing import Any

import httpx

from providers.cache import clave_celda_power, obtener_cache
from providers.nasa_power import NasaPowerUnavailable, fetch_daily_range
from providers.nasa_telemetry import (
    ESPACIO_HIST,
    HIST_END,
    HIST_PARAMETROS,
    HIST_START,
    anomalia_lluvia_90d_pct,
    cargar_climatologia_precalculada,
    clasificar_riesgo_termico,
    climatologia_lluvia_90d_por_doy,
    dias_calor_verano_promedio,
    dict_a_referencia,
    fecha_de_corte,
    obtener_ventana_reciente,
    tendencia_humedad_15d_pct,
    tormentas_extremas_90d,
    ventana_90d_rellena,
)
from providers.soilgrids import PerfilSueloSatelital, SoilGridsUnavailable, fetch_perfil_suelo
from providers.srtm import TopografiaSrtm, SrtmUnavailable, fetch_topografia
from services.field_enrichment_service import (
    columnas_field_a_perfil_telemetria,
    columnas_field_a_topografia_telemetria,
    perfil_suelo_no_disponible,
    serializar_perfil_suelo,
    serializar_topografia,
    suelo_a_columnas_field,
    suelo_no_disponible_a_columnas_field,
    tiene_suelo_propio_valido,
    tiene_topografia_propia_valida,
    topografia_a_columnas_field,
    topografia_no_disponible_a_columnas_field,
)

logger = logging.getLogger(__name__)

TelemetryFetcher = Callable[..., Awaitable[dict[str, Any]]]
FieldUpdater = Callable[[dict[str, Any]], Awaitable[None] | None]
HIST_INFO_TIMEOUT_S = 10.0


def _validar_coordenadas(lat: float, lon: float) -> None:
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise ValueError(f"Coordenadas inválidas: ({lat!r}, {lon!r})")
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError(f"Coordenadas fuera de rango: lat={lat}, lon={lon}")


def _perfil_suelo_no_disponible() -> dict[str, Any]:
    return perfil_suelo_no_disponible()


def _serializar_perfil_suelo(perfil: PerfilSueloSatelital) -> dict[str, Any]:
    return serializar_perfil_suelo(perfil)


def _serializar_topografia(topo: TopografiaSrtm) -> dict[str, Any]:
    return serializar_topografia(topo)


async def _obtener_referencia_climatica_rapida(
    lat: float, lon: float, client: httpx.AsyncClient
) -> tuple[dict[int, float] | None, float | None]:
    """Obtiene climatología 2006–2025 desde caché/precálculo o consulta rápida (sin 1981–2005 del ML)."""
    cache = obtener_cache()
    clave = clave_celda_power(lat, lon)

    ref = dict_a_referencia(cache.get(ESPACIO_HIST, clave))
    if ref is not None:
        return ref.clim_por_doy, ref.dias_calor_verano_promedio

    entrada_pre = cargar_climatologia_precalculada().get(clave)
    ref = dict_a_referencia(entrada_pre) if entrada_pre is not None else None
    if ref is not None:
        return ref.clim_por_doy, ref.dias_calor_verano_promedio

    serie = await asyncio.wait_for(
        fetch_daily_range(lat, lon, HIST_START, HIST_END, HIST_PARAMETROS, client=client),
        timeout=HIST_INFO_TIMEOUT_S,
    )
    return climatologia_lluvia_90d_por_doy(serie), dias_calor_verano_promedio(serie)


async def obtener_telemetria_nasa_ligera(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient,
    today: date,
) -> tuple[dict[str, Any], list[str]]:
    """Consulta asíncrona liviana de NASA POWER para ``Info general`` (desacoplada del ML)."""
    reciente_task = obtener_ventana_reciente(lat, lon, client, today)
    ref_task = _obtener_referencia_climatica_rapida(lat, lon, client)
    reciente_res, ref_res = await asyncio.gather(reciente_task, ref_task, return_exceptions=True)

    if isinstance(reciente_res, BaseException):
        if isinstance(reciente_res, ValueError):
            raise reciente_res
        raise NasaPowerUnavailable(str(reciente_res)) from reciente_res

    corte = fecha_de_corte(reciente_res)
    ventana = ventana_90d_rellena(reciente_res, corte)
    advertencias: list[str] = []

    anomalia: float | None = None
    riesgo_termico: str | None = None
    if isinstance(ref_res, BaseException):
        advertencias.append(
            "Referencia climática histórica no disponible en este momento; se muestran las métricas recientes."
        )
    else:
        clim_por_doy, dias_calor = ref_res
        if clim_por_doy is not None:
            anomalia = anomalia_lluvia_90d_pct(ventana, clim_por_doy, corte)
        if dias_calor is not None:
            riesgo_termico = clasificar_riesgo_termico(dias_calor)

    return (
        {
            "fecha_ultimo_dato_valido": corte.isoformat(),
            "indice_humedad_radicular_pct": round(reciente_res.series["GWETROOT"][corte] * 100.0, 1),
            "indice_humedad_superficial_pct": round(reciente_res.series["GWETTOP"][corte] * 100.0, 1),
            "tendencia_humedad_15d_pct": tendencia_humedad_15d_pct(ventana),
            "anomalia_lluvia_90d_pct": anomalia,
            "frecuencia_tormentas_extremas_90d": tormentas_extremas_90d(ventana),
            "riesgo_termico_verano": riesgo_termico,
        },
        advertencias,
    )


async def obtener_telemetria_campo(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
    today: date | None = None,
    field_row: Mapping[str, Any] | None = None,
    persist_field_updates: FieldUpdater | None = None,
) -> dict[str, Any]:
    """Obtiene NASA POWER liviano + SoilGrids + SRTM (o reutiliza datos propios de ``public.fields``)."""
    _validar_coordenadas(lat, lon)
    hoy = today or datetime.now(timezone.utc).date()

    usar_suelo_guardado = field_row is not None and tiene_suelo_propio_valido(field_row)
    usar_topo_guardada = field_row is not None and tiene_topografia_propia_valida(field_row)

    async def _consultar(shared_client: httpx.AsyncClient):
        nasa_coro = obtener_telemetria_nasa_ligera(lat, lon, client=shared_client, today=hoy)
        suelo_coro = (
            asyncio.sleep(0, result=None)
            if usar_suelo_guardado
            else fetch_perfil_suelo(lat, lon, client=shared_client)
        )
        topo_coro = (
            asyncio.sleep(0, result=None)
            if usar_topo_guardada
            else fetch_topografia(lat, lon, client=shared_client)
        )
        return await asyncio.gather(
            nasa_coro,
            suelo_coro,
            topo_coro,
            return_exceptions=True,
        )

    if client is None:
        async with httpx.AsyncClient() as propio:
            nasa_res, suelo_res, topo_res = await _consultar(propio)
    else:
        nasa_res, suelo_res, topo_res = await _consultar(client)

    advertencias: list[str] = []
    for res in (nasa_res, suelo_res, topo_res):
        if isinstance(res, ValueError):
            raise res

    telemetria_nasa: dict[str, Any] | None = None
    if isinstance(nasa_res, BaseException):
        advertencias.append("Telemetría satelital NASA POWER no disponible en este momento.")
    else:
        telemetria_nasa, adv_nasa = nasa_res
        advertencias.extend(adv_nasa)

    field_updates: dict[str, Any] = {}
    suelo_disponible = False
    if usar_suelo_guardado and field_row is not None:
        suelo_disponible = True
        perfil_suelo, adv_suelo = columnas_field_a_perfil_telemetria(field_row)
        advertencias.extend(adv_suelo)
    elif isinstance(suelo_res, SoilGridsUnavailable) or isinstance(suelo_res, BaseException) or suelo_res is None:
        perfil_suelo = _perfil_suelo_no_disponible()
        advertencias.append("Propiedades del suelo no disponibles en este momento para esta ubicación.")
        if field_row is not None and field_row.get("suelo_fuente") is None:
            field_updates.update(suelo_no_disponible_a_columnas_field())
    else:
        suelo_disponible = True
        perfil_suelo = _serializar_perfil_suelo(suelo_res)
        advertencias.extend(suelo_res.advertencias)
        if field_row is not None:
            field_updates.update(suelo_a_columnas_field(suelo_res))

    topografia_srtm: dict[str, Any] | None = None
    if usar_topo_guardada and field_row is not None:
        topografia_srtm, adv_topo = columnas_field_a_topografia_telemetria(field_row)
        advertencias.extend(adv_topo)
    elif isinstance(topo_res, SrtmUnavailable) or isinstance(topo_res, BaseException) or topo_res is None:
        advertencias.append("Topografía SRTM no disponible en este momento para esta ubicación.")
        if field_row is not None and field_row.get("topo_fuente") is None:
            field_updates.update(topografia_no_disponible_a_columnas_field())
    else:
        topografia_srtm = _serializar_topografia(topo_res)
        advertencias.extend(topo_res.advertencias)
        if field_row is not None:
            field_updates.update(topografia_a_columnas_field(topo_res))

    if field_updates and persist_field_updates is not None:
        try:
            maybe_awaitable = persist_field_updates(field_updates)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable
        except Exception:  # noqa: BLE001
            logger.warning("No se pudieron persistir los datos actualizados del campo en BD.", exc_info=True)

    if telemetria_nasa is None and topografia_srtm is None and not suelo_disponible:
        if isinstance(nasa_res, NasaPowerUnavailable):
            raise nasa_res
        if isinstance(suelo_res, SoilGridsUnavailable):
            raise suelo_res
        if isinstance(topo_res, SrtmUnavailable):
            raise topo_res
        raise NasaPowerUnavailable("Ningún proveedor satelital o edáfico pudo responder.")

    return {
        "ubicacion": {"lat": lat, "lon": lon},
        "telemetria_nasa": telemetria_nasa,
        "topografia_srtm": topografia_srtm,
        "perfil_suelo": perfil_suelo,
        "advertencias": list(dict.fromkeys(advertencias)),
    }
