"""Seguimiento de una campaña ya sembrada (BACK-29, sobre ML-18).

Arma las entradas de ``AgroPredictor.predict_seguimiento`` a partir de la campaña guardada
(``campaigns.fecha_inicio`` = fecha de siembra) y del campo (coordenadas, suelo, topografía y
departamento guardados), y decide si alcanza con el resultado guardado en
``campaigns.simulacion_json["seguimiento"]``.

Se calcula cuando el usuario lo pide (Render Free duerme y no hay procesos programados) y como
mucho una vez por día: NASA POWER publica a diario y con 3 a 7 días de atraso.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import httpx
from starlette.concurrency import run_in_threadpool

from ml.departamentos import departamento_mas_cercano, departamento_por_codigo
from ml.predictor import get_predictor
from providers.cache import clave_celda_power, obtener_cache
from providers.enso import oni_al
from providers.features import calendario_eventos, calendario_lluvia, features_actuales_desde_series
from providers.nasa_power import PARAMETROS, NasaPowerUnavailable, dict_a_serie, fetch_daily_range, serie_a_dict
from providers.nasa_telemetry import fecha_de_corte, obtener_referencia_historica, recortar_serie
from providers.soilgrids import fetch_perfil_suelo
from providers.srtm import fetch_topografia
from services.field_enrichment_service import columnas_field_a_perfil_suelo, columnas_field_a_topografia

ESPACIO_SEGUIMIENTO = "nasa_seguimiento"
TTL_SEGUIMIENTO_S = 6 * 3600.0
# Días previos a la siembra para el estado del suelo (la ventana de 90 días + margen por -999).
DIAS_PREVIOS_SIEMBRA = 110
PARAMS_EVENTOS = ("PRECTOTCORR", "T2M_MAX", "T2M_MIN")

ADVERTENCIAS_FIJAS: tuple[str, ...] = (
    "Los datos satelitales de NASA POWER llegan con 3 a 7 días de atraso.",
    "Usa clima regional (~50 km): no ve tormentas locales, plagas, enfermedades ni el manejo del lote.",
)
ADV_FUERA_DE_COBERTURA = (
    "El lote está fuera de la zona con datos de rinde (región pampeana): se muestra el riesgo sin rinde en kg/ha."
)


class SeguimientoInvalido(ValueError):
    """La campaña no se puede seguir (422 con mensaje para el usuario)."""


@dataclass(frozen=True)
class InsumosSeguimiento:
    features_siembra: dict[str, Any]
    calendario_eventos: dict[int, str]
    calendario_lluvia: dict[int, str]
    observado_eventos: dict[int, str]
    observado_lluvia: dict[int, str]
    ultimo_dato: date
    oni_siembra: float | None
    advertencias: tuple[str, ...] = field(default_factory=tuple)


ConstructorSeguimiento = Callable[..., Awaitable[InsumosSeguimiento]]


def ultimo_dia_con_eventos(serie: Any) -> date:
    """Último día con lluvia, máxima y mínima válidas a la vez (no se inventan días con -999)."""
    columnas = [serie.series.get(p, {}) for p in PARAMS_EVENTOS]
    for dia in sorted(set(columnas[0]).intersection(*columnas[1:]), reverse=True):
        if all(col.get(dia) is not None for col in columnas):
            return dia
    raise NasaPowerUnavailable("NASA POWER no tiene días con lluvia y temperaturas válidas desde la siembra")


def calendarios_observados(serie: Any, hasta: date) -> tuple[dict[int, str], dict[int, str]]:
    """Calendarios diarios de la campaña hasta ``hasta``. La serie arranca el 1/1 (índices por año)."""
    recorte = recortar_serie(serie, serie.start, hasta)
    fechas = [serie.start + timedelta(days=i) for i in range((hasta - serie.start).days + 1)]
    p = [recorte.series["PRECTOTCORR"].get(d) for d in fechas]
    tx = [recorte.series["T2M_MAX"].get(d) for d in fechas]
    tn = [recorte.series["T2M_MIN"].get(d) for d in fechas]
    return calendario_eventos(fechas, p, tx, tn), calendario_lluvia(fechas, p)


async def _serie_campana(lat: float, lon: float, desde: date, hasta: date, client: httpx.AsyncClient) -> Any:
    cache = obtener_cache()
    clave = f"{clave_celda_power(lat, lon)}|{desde.isoformat()}|{hasta.isoformat()}"
    cacheado = cache.get(ESPACIO_SEGUIMIENTO, clave)
    if cacheado is not None:
        return dict_a_serie(cacheado)
    serie = await fetch_daily_range(lat, lon, desde, hasta, PARAMETROS, client=client)
    cache.set(ESPACIO_SEGUIMIENTO, clave, serie_a_dict(serie), TTL_SEGUIMIENTO_S)
    return serie


async def construir_insumos_seguimiento(
    lat: float,
    lon: float,
    fecha_siembra: date,
    *,
    today: date,
    client: httpx.AsyncClient | None = None,
    perfil_guardado: Any | None = None,
    topografia_guardada: Any | None = None,
) -> InsumosSeguimiento:
    """Una sola consulta a NASA POWER desde el 1/1 del año de ``siembra − 110 días`` hasta hoy.

    Cubre el estado del suelo al sembrar y todo el período crítico observado, sin depender de la
    ventana de 90 días de ``nasa_reciente``.
    """
    desde = date((fecha_siembra - timedelta(days=DIAS_PREVIOS_SIEMBRA)).year, 1, 1)

    async def _armar(c: httpx.AsyncClient) -> InsumosSeguimiento:
        async def _guardado(v: Any) -> Any:
            return v

        serie, ref, perfil, topo = await asyncio.gather(
            _serie_campana(lat, lon, desde, today, c),
            obtener_referencia_historica(lat, lon, c),
            _guardado(perfil_guardado) if perfil_guardado is not None else fetch_perfil_suelo(lat, lon, client=c),
            _guardado(topografia_guardada) if topografia_guardada is not None else fetch_topografia(lat, lon, client=c),
        )
        corte_siembra = fecha_de_corte(recortar_serie(serie, serie.start, fecha_siembra))
        features = features_actuales_desde_series(
            recortar_serie(serie, corte_siembra - timedelta(days=DIAS_PREVIOS_SIEMBRA - 1), corte_siembra),
            corte_siembra,
            ref.clim_por_doy,
            pendiente_terreno_pct=topo.pendiente_terreno_pct,
            elevacion_m=topo.elevacion_m,
            textura_arcilla_pct=perfil.arcilla_pct,
        )
        ultimo = ultimo_dia_con_eventos(serie)
        obs_ev, obs_ll = calendarios_observados(serie, ultimo)
        return InsumosSeguimiento(
            features_siembra=features,
            calendario_eventos=ref.calendario_eventos,
            calendario_lluvia=ref.calendario_lluvia,
            observado_eventos=obs_ev,
            observado_lluvia=obs_ll,
            ultimo_dato=ultimo,
            oni_siembra=oni_al(fecha_siembra),
            advertencias=tuple(perfil.advertencias) + tuple(topo.advertencias),
        )

    if client is None:
        async with httpx.AsyncClient() as propio:
            return await _armar(propio)
    return await _armar(client)


def validar_campana(campana: Mapping[str, Any], hoy: date) -> tuple[str, date]:
    cultivo = str(campana.get("cultivo") or "")
    if cultivo not in get_predictor().cultivos_entrenados:
        raise SeguimientoInvalido("Para cultivos de servicio (o sin rinde histórico) no hay seguimiento de rinde.")
    fecha_siembra = date.fromisoformat(str(campana["fecha_inicio"])[:10])
    if fecha_siembra > hoy:
        raise SeguimientoInvalido("La siembra todavía no ocurrió.")
    return cultivo, fecha_siembra


def resultado_guardado_vigente(campana: Mapping[str, Any], hoy: date) -> dict[str, Any] | None:
    """El seguimiento guardado si se calculó hoy o si el período crítico ya terminó."""
    previo = (campana.get("simulacion_json") or {}).get("seguimiento")
    if not isinstance(previo, Mapping):
        return None
    if str(previo.get("fecha_siembra")) != str(campana.get("fecha_inicio"))[:10] or previo.get("cultivo") != campana.get("cultivo"):
        return None  # la campaña se editó después del cálculo
    if previo.get("calculado_el") == hoy.isoformat() or previo.get("etapa") == "terminado":
        return dict(previo)
    return None


def _departamento(campo: Mapping[str, Any]) -> dict[str, Any] | None:
    codigo = campo.get("departamento_codigo")
    if codigo:
        dep = departamento_por_codigo(str(codigo), float(campo["lat"]), float(campo["lon"]))
        if dep is not None:
            return dep
    return departamento_mas_cercano(float(campo["lat"]), float(campo["lon"]))


def armar_respuesta(
    campana: Mapping[str, Any], campo: Mapping[str, Any], insumos: InsumosSeguimiento, hoy: date
) -> dict[str, Any]:
    """Corre el predictor y arma ``SeguimientoResponse`` (sin E/S)."""
    cultivo, fecha_siembra = validar_campana(campana, hoy)
    dep = _departamento(campo)
    resultado = get_predictor().predict_seguimiento(
        insumos.features_siembra,
        insumos.calendario_eventos,
        insumos.calendario_lluvia,
        insumos.observado_eventos,
        insumos.observado_lluvia,
        cultivo,
        fecha_siembra,
        insumos.ultimo_dato,
        oni_siembra=insumos.oni_siembra,
        departamento=dep,
    )
    advertencias = list(dict.fromkeys(ADVERTENCIAS_FIJAS + insumos.advertencias))
    if dep is None:
        advertencias.append(ADV_FUERA_DE_COBERTURA)
    return {
        **resultado,
        "campana_id": str(campana["id"]),
        "departamento_referencia": dep,
        "calculado_el": hoy,
        "advertencias": advertencias,
    }


async def calcular_seguimiento(
    campana: Mapping[str, Any],
    campo: Mapping[str, Any],
    hoy: date,
    construir: ConstructorSeguimiento = construir_insumos_seguimiento,
) -> tuple[dict[str, Any], bool]:
    """``(respuesta, es_nueva)``. Reutiliza lo guardado si sigue vigente (``es_nueva = False``)."""
    _, fecha_siembra = validar_campana(campana, hoy)
    guardado = resultado_guardado_vigente(campana, hoy)
    if guardado is not None:
        return guardado, False
    guardados: dict[str, Any] = {}
    perfil = columnas_field_a_perfil_suelo(campo)
    topo = columnas_field_a_topografia(campo)
    if perfil is not None:
        guardados["perfil_guardado"] = perfil
    if topo is not None:
        guardados["topografia_guardada"] = topo
    insumos = await construir(float(campo["lat"]), float(campo["lon"]), fecha_siembra, today=hoy, **guardados)
    return await run_in_threadpool(armar_respuesta, campana, campo, insumos, hoy), True
