"""Servicio único de datos del lote (BACK-24).

Lo usan ``GET /api/v1/telemetry`` (Info general) y ``POST /api/v1/simulate`` (insumos del
modelo), con la misma política (TASKS_BACKEND §4.5):

- **Datos fijos del lote** (suelo y topografía):
  - Si el campo guardado (``public.fields``) tiene dato real (``reintentar_* = false``), se
    usa sin llamar a ISRIC ni a SRTM.
  - Si no, se consulta el provider (con su cascada: vecinos, grilla BACK-19, GeoINTA). Lo
    obtenido se guarda en el campo, igual que BACK-23.
  - Si el provider falla del todo y el campo tiene un dato aproximado guardado, se usa ese.
- **Clima histórico de la celda:** ``obtener_referencia_historica`` (memoria → Supabase →
  JSON → NASA en vivo, 1981–2025, con los calendarios de los años análogos). Es la única
  búsqueda: la versión "ligera" 2006–2025 de BACK-20 se eliminó.
- **Datos diarios:** ventana reciente de NASA POWER (caché de 6 h), siempre en vivo.

Modo estricto (``/simulate``): cualquier dato faltante lanza la excepción del provider
(503). Modo tolerante (``/telemetry``): devuelve lo que haya y el que llama arma los avisos.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import httpx

from providers.nasa_power import NasaPowerDailySeries, NasaPowerUnavailable, _validar_coordenadas
from providers.nasa_telemetry import (
    MSG_NASA_CAIDA,
    ReferenciaHistorica,
    obtener_referencia_historica,
    obtener_ventana_reciente,
)
from providers.soilgrids import PerfilSueloSatelital, fetch_perfil_suelo
from providers.srtm import TopografiaSrtm, fetch_topografia
from services.field_enrichment_service import (
    suelo_a_columnas_field,
    suelo_no_disponible_a_columnas_field,
    tiene_suelo_propio_valido,
    tiene_topografia_propia_valida,
    topografia_a_columnas_field,
    topografia_no_disponible_a_columnas_field,
)

logger = logging.getLogger(__name__)

PersistirCampo = Callable[[dict[str, Any]], Awaitable[None] | None]
TIMEOUT_HISTORICO_TOLERANTE_S = 15.0  # /telemetry: no esperar de más a NASA fuera de la región


@dataclass
class DatosLote:
    """Lo que se sabe del lote. En modo tolerante, lo que falte queda en ``None`` y su
    excepción en ``errores`` (claves ``"nasa"``, ``"historico"``, ``"suelo"`` y ``"topo"``)."""

    lat: float
    lon: float
    reciente: NasaPowerDailySeries | None
    referencia: ReferenciaHistorica | None
    perfil_suelo: PerfilSueloSatelital | None
    topografia: TopografiaSrtm | None
    suelo_desde_campo: bool = False
    topo_desde_campo: bool = False
    cambios_campo: dict[str, Any] = field(default_factory=dict)
    errores: dict[str, BaseException] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Columnas de public.fields -> objetos de los providers
# ---------------------------------------------------------------------------


def _hay_fuente(fuente: Any) -> bool:
    return bool(fuente) and fuente != "no_disponible"


def campo_tiene_suelo(row: Mapping[str, Any]) -> bool:
    """El campo tiene algún perfil de suelo guardado (real o aproximado) con arcilla."""
    return _hay_fuente(row.get("suelo_fuente")) and row.get("arcilla_pct") is not None


def campo_tiene_topografia(row: Mapping[str, Any]) -> bool:
    """El campo tiene alguna topografía guardada (real o aproximada)."""
    return (
        _hay_fuente(row.get("topo_fuente"))
        and row.get("elevacion_m") is not None
        and row.get("pendiente_terreno_pct") is not None
    )


def perfil_desde_campo(row: Mapping[str, Any]) -> PerfilSueloSatelital:
    return PerfilSueloSatelital(
        arcilla_pct=row.get("arcilla_pct"),
        arena_pct=row.get("arena_pct"),
        limo_pct=row.get("limo_pct"),
        carbono_organico_g_kg=row.get("carbono_organico_g_kg"),
        ph=row.get("ph"),
        textura_predominante=row.get("textura_predominante"),
        fuente=row.get("suelo_fuente"),  # type: ignore[arg-type]
        distancia_fuente_km=float(row.get("suelo_distancia_fuente_km") or 0.0),
        localidad_fallback=row.get("suelo_localidad_fallback"),
        advertencias=tuple(str(a) for a in (row.get("suelo_advertencias") or ())),
        reintentar_soilgrids=bool(row.get("reintentar_soilgrids", True)),
    )


def topografia_desde_campo(row: Mapping[str, Any]) -> TopografiaSrtm:
    return TopografiaSrtm(
        elevacion_m=float(row["elevacion_m"]),
        pendiente_terreno_pct=float(row["pendiente_terreno_pct"]),
        fuente=row.get("topo_fuente"),  # type: ignore[arg-type]
        fuente_elevacion=row.get("fuente_elevacion"),  # type: ignore[arg-type]
        distancia_fuente_km=float(row.get("topo_distancia_fuente_km") or 0.0),
        localidad_fallback=row.get("topo_localidad_fallback"),
        advertencias=tuple(str(a) for a in (row.get("topo_advertencias") or ())),
        reintentar_srtm=bool(row.get("reintentar_srtm", True)),
    )


# ---------------------------------------------------------------------------
# Resolución de cada dato fijo con la política del campo
# ---------------------------------------------------------------------------


async def _resolver_suelo(lat, lon, campo, client) -> tuple[PerfilSueloSatelital | None, bool, dict, BaseException | None]:
    """(perfil, desde_campo, cambios_para_el_campo, error)."""
    if campo is not None and tiene_suelo_propio_valido(campo):
        return perfil_desde_campo(campo), True, {}, None
    try:
        perfil = await fetch_perfil_suelo(lat, lon, client=client)
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 - SoilGridsUnavailable u otra falla del provider
        if campo is not None and campo_tiene_suelo(campo):
            return perfil_desde_campo(campo), True, {}, None
        cambios = suelo_no_disponible_a_columnas_field() if campo is not None and campo.get("suelo_fuente") is None else {}
        return None, False, cambios, exc
    return perfil, False, (suelo_a_columnas_field(perfil) if campo is not None else {}), None


async def _resolver_topografia(lat, lon, campo, client) -> tuple[TopografiaSrtm | None, bool, dict, BaseException | None]:
    """(topografía, desde_campo, cambios_para_el_campo, error)."""
    if campo is not None and tiene_topografia_propia_valida(campo):
        return topografia_desde_campo(campo), True, {}, None
    try:
        topo = await fetch_topografia(lat, lon, client=client)
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 - SrtmUnavailable u otra falla del provider
        if campo is not None and campo_tiene_topografia(campo):
            return topografia_desde_campo(campo), True, {}, None
        cambios = (
            topografia_no_disponible_a_columnas_field() if campo is not None and campo.get("topo_fuente") is None else {}
        )
        return None, False, cambios, exc
    return topo, False, (topografia_a_columnas_field(topo) if campo is not None else {}), None


def _error_nasa(exc: BaseException) -> BaseException:
    """Mismo mensaje apto para el usuario que ``build_telemetria_nasa``."""
    if isinstance(exc, NasaPowerUnavailable):
        return NasaPowerUnavailable(f"{MSG_NASA_CAIDA} (detalle: {exc})")
    return exc


async def _persistir(persistir_campo: PersistirCampo, cambios: dict[str, Any]) -> None:
    try:
        if inspect.iscoroutinefunction(persistir_campo):
            await persistir_campo(cambios)
        else:
            resultado = await asyncio.to_thread(persistir_campo, cambios)  # Supabase es sincrónico
            if inspect.isawaitable(resultado):
                await resultado
    except Exception:  # noqa: BLE001 - no guardar el campo no rompe la respuesta
        logger.warning("No se pudieron persistir los datos actualizados del campo en BD.", exc_info=True)


def _avisar_reintento(campo, lat, lon, perfil, topo) -> None:
    """BACK-25: si el campo sigue con algún dato aproximado, que lo reintente la cola."""
    from services.reintentos_campos import obtener_cola  # diferido: evita el ciclo de imports

    cola = obtener_cola()
    if cola is None:
        return
    cola.encolar(
        campo["id"],
        lat,
        lon,
        suelo=perfil is None or bool(perfil.reintentar_soilgrids),
        topo=topo is None or bool(topo.reintentar_srtm),
    )


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


async def obtener_datos_lote(
    lat: float,
    lon: float,
    *,
    campo: Mapping[str, Any] | None = None,
    persistir_campo: PersistirCampo | None = None,
    client: httpx.AsyncClient | None = None,
    today: date | None = None,
    exigir_todo: bool = True,
) -> DatosLote:
    """Datos fijos, clima histórico y datos diarios del lote, con la política de §4.5.

    Raises:
        ValueError: coordenadas fuera de rango.
        NasaPowerUnavailable / SoilGridsUnavailable / SrtmUnavailable: solo con
            ``exigir_todo=True``, si falta un dato (en ese orden de prioridad).
    """
    _validar_coordenadas(lat, lon)
    hoy = today or datetime.now(timezone.utc).date()

    async def _consultar(c: httpx.AsyncClient):
        historico = obtener_referencia_historica(lat, lon, c)
        if not exigir_todo:
            historico = asyncio.wait_for(historico, TIMEOUT_HISTORICO_TOLERANTE_S)
        return await asyncio.gather(
            obtener_ventana_reciente(lat, lon, c, hoy),
            historico,
            _resolver_suelo(lat, lon, campo, c),
            _resolver_topografia(lat, lon, campo, c),
            return_exceptions=True,
        )

    if client is None:
        async with httpx.AsyncClient() as propio:
            reciente, referencia, suelo_res, topo_res = await _consultar(propio)
    else:
        reciente, referencia, suelo_res, topo_res = await _consultar(client)

    for res in (reciente, referencia, suelo_res, topo_res):
        if isinstance(res, ValueError):
            raise res
    for res in (suelo_res, topo_res):  # _resolver_* solo lanza ValueError; otra cosa es un bug
        if isinstance(res, BaseException):
            raise res

    errores: dict[str, BaseException] = {}
    if isinstance(reciente, BaseException):
        errores["nasa"] = _error_nasa(reciente)
        reciente = None
    if isinstance(referencia, BaseException):
        errores["historico"] = _error_nasa(referencia)
        referencia = None
    perfil, suelo_desde_campo, cambios_suelo, error_suelo = suelo_res
    topo, topo_desde_campo, cambios_topo, error_topo = topo_res
    if error_suelo is not None:
        errores["suelo"] = error_suelo
    if error_topo is not None:
        errores["topo"] = error_topo

    cambios = {**cambios_suelo, **cambios_topo}
    if cambios and persistir_campo is not None:
        await _persistir(persistir_campo, cambios)
    if campo is not None and campo.get("id") is not None:
        _avisar_reintento(campo, lat, lon, perfil, topo)

    if exigir_todo:
        for clave in ("nasa", "historico", "suelo", "topo"):
            if clave in errores:
                raise errores[clave]

    return DatosLote(
        lat=lat,
        lon=lon,
        reciente=reciente,
        referencia=referencia,
        perfil_suelo=perfil,
        topografia=topo,
        suelo_desde_campo=suelo_desde_campo,
        topo_desde_campo=topo_desde_campo,
        cambios_campo=cambios,
        errores=errores,
    )
