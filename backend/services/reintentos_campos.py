"""Reintento en segundo plano de ISRIC/SRTM para campos con dato aproximado (BACK-25).

Cuando un campo queda con suelo o topografía aproximados (grilla, GeoINTA o
``no_disponible``, con ``reintentar_* = true``), se encola. Cada ``INTERVALO_S`` (5 min,
alineado con el corte automático de los providers) se reintenta, hasta ``MAX_INTENTOS``
(12, una hora). Solo se escribe dato real, con los mismos mappers de BACK-22, y suelo y
topografía por separado.

- La cola vive en memoria con un solo worker. Si Render reinicia, se reconstruye al arrancar
  con los campos pendientes creados en las últimas 24 h (``cargar_pendientes``).
- Escribe con la secret key (saltea RLS) filtrando por ``id``: el worker no tiene el token
  del usuario.
- El frontend consulta ``GET /fields/{id}`` cada 30 s mientras ``reintento_en_curso`` sea
  ``true`` (``en_curso``).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from providers.soilgrids import fetch_perfil_suelo
from providers.srtm import fetch_topografia
from services.field_enrichment_service import suelo_a_columnas_field, topografia_a_columnas_field

logger = logging.getLogger(__name__)

INTERVALO_S = 300.0
MAX_INTENTOS = 12
VENTANA_ARRANQUE = timedelta(hours=24)

EscritorCampo = Callable[[str, dict[str, Any]], None]  # (field_id, cambios) -> None, sincrónico
Proveedor = Callable[..., Awaitable[Any]]


async def suelo_segundo_plano(lat: float, lon: float) -> Any:
    """BACK-27: ISRIC con timeout largo, esperando cupo y sin tocar el corte automático."""
    return await fetch_perfil_suelo(lat, lon, segundo_plano=True)


async def topografia_segundo_plano(lat: float, lon: float) -> Any:
    """BACK-27: OpenTopoData con timeout largo y sin tocar el corte automático."""
    return await fetch_topografia(lat, lon, segundo_plano=True)


@dataclass
class Pendiente:
    lat: float
    lon: float
    suelo: bool
    topo: bool
    intentos: int = 0


class ColaReintentos:
    def __init__(
        self,
        escritor: EscritorCampo,
        *,
        proveedor_suelo: Proveedor = suelo_segundo_plano,
        proveedor_topo: Proveedor = topografia_segundo_plano,
        intervalo_s: float = INTERVALO_S,
        max_intentos: int = MAX_INTENTOS,
        dormir: Callable[[float], Awaitable[Any]] = asyncio.sleep,
    ) -> None:
        self._escritor = escritor
        self._suelo = proveedor_suelo
        self._topo = proveedor_topo
        self._intervalo_s = intervalo_s
        self._max_intentos = max_intentos
        self._dormir = dormir
        self._pendientes: dict[str, Pendiente] = {}
        self._tarea: asyncio.Task | None = None

    # --- estado -------------------------------------------------------------------------

    def encolar(self, field_id: Any, lat: float, lon: float, *, suelo: bool, topo: bool) -> None:
        """Agrega o actualiza un campo. Sin nada pendiente, lo saca. No reinicia el contador."""
        clave = str(field_id)
        if not suelo and not topo:
            self._pendientes.pop(clave, None)
            return
        actual = self._pendientes.get(clave)
        if actual is None or (actual.lat, actual.lon) != (lat, lon):
            self._pendientes[clave] = Pendiente(lat=lat, lon=lon, suelo=suelo, topo=topo)
        else:
            actual.suelo, actual.topo = suelo, topo

    def en_curso(self, field_id: Any) -> bool:
        return str(field_id) in self._pendientes

    def encolar_desde_fila(self, fila: dict[str, Any]) -> None:
        """Encola según las marcas ``reintentar_*`` de una fila de ``public.fields``."""
        if fila.get("id") is None or fila.get("lat") is None or fila.get("lon") is None:
            return
        self.encolar(
            fila["id"],
            float(fila["lat"]),
            float(fila["lon"]),
            suelo=fila.get("reintentar_soilgrids") is not False,
            topo=fila.get("reintentar_srtm") is not False,
        )

    # --- trabajo ------------------------------------------------------------------------

    async def ciclo(self) -> None:
        """Una ronda: un intento por cada campo pendiente, de a uno (respeta límites y cortes)."""
        for clave, p in list(self._pendientes.items()):
            p.intentos += 1
            cambios: dict[str, Any] = {}
            if p.suelo:
                try:
                    perfil = await self._suelo(p.lat, p.lon)
                    if not perfil.reintentar_soilgrids:
                        cambios.update(suelo_a_columnas_field(perfil))
                except Exception as exc:  # noqa: BLE001 - se reintenta en la próxima ronda
                    logger.info("reintentos: suelo de %s sigue sin responder (%s)", clave, exc)
            if p.topo:
                try:
                    topo = await self._topo(p.lat, p.lon)
                    if not topo.reintentar_srtm:
                        cambios.update(topografia_a_columnas_field(topo))
                except Exception as exc:  # noqa: BLE001
                    logger.info("reintentos: topografía de %s sigue sin responder (%s)", clave, exc)
            if cambios:
                try:
                    await asyncio.to_thread(self._escritor, clave, cambios)
                    p.suelo = p.suelo and "suelo_fuente" not in cambios
                    p.topo = p.topo and "topo_fuente" not in cambios
                    logger.info("reintentos: campo %s actualizado con dato real (%s)", clave, sorted(cambios))
                except Exception:  # noqa: BLE001 - se vuelve a intentar escribir en la próxima ronda
                    logger.warning("reintentos: no se pudo guardar el campo %s", clave, exc_info=True)
            if (not p.suelo and not p.topo) or p.intentos >= self._max_intentos:
                self._pendientes.pop(clave, None)

    async def _bucle(self) -> None:
        while True:
            await self._dormir(self._intervalo_s)
            try:
                await self.ciclo()
            except Exception:  # noqa: BLE001 - el worker nunca muere
                logger.warning("reintentos: error en la ronda", exc_info=True)

    def iniciar(self) -> None:
        if self._tarea is None or self._tarea.done():
            self._tarea = asyncio.create_task(self._bucle(), name="reintentos_campos")

    async def detener(self) -> None:
        if self._tarea is not None:
            self._tarea.cancel()
            try:
                await self._tarea
            except asyncio.CancelledError:
                pass
            self._tarea = None


# ---------------------------------------------------------------------------
# Instancia global y Supabase
# ---------------------------------------------------------------------------

_cola: ColaReintentos | None = None


def configurar_cola(cola: ColaReintentos | None) -> None:
    global _cola
    _cola = cola


def obtener_cola() -> ColaReintentos | None:
    return _cola


def en_curso(field_id: Any) -> bool:
    """``reintento_en_curso`` de ``FieldResponse``: ``False`` si no hay cola."""
    return _cola is not None and _cola.en_curso(field_id)


def crear_cliente_servicio(settings: Any) -> Any | None:
    """Cliente de Supabase con la secret key, o ``None`` si la persistencia está desactivada."""
    if not getattr(settings, "cache_persistente", True):
        return None
    url = (settings.supabase_url or "").strip()
    clave = (settings.supabase_secret_key or "").strip()
    if not url or not clave:
        return None
    from supabase import create_client

    return create_client(url, clave)


def escritor_supabase(cliente: Any) -> EscritorCampo:
    def escribir(field_id: str, cambios: dict[str, Any]) -> None:
        cliente.table("fields").update(cambios).eq("id", field_id).execute()

    return escribir


def cargar_pendientes(cliente: Any, *, ahora: datetime | None = None) -> list[dict[str, Any]]:
    """Campos de cualquier usuario creados en las últimas 24 h con algún ``reintentar_*`` en true.

    ``public.fields`` no tiene ``updated_at``: un campo movido hace más de 24 h no se retoma
    al arrancar (le queda el reintento al volver a elegirlo, BACK-23).
    """
    desde = (ahora or datetime.now(timezone.utc)) - VENTANA_ARRANQUE
    resp = (
        cliente.table("fields")
        .select("id,lat,lon,reintentar_soilgrids,reintentar_srtm")
        .or_("reintentar_soilgrids.eq.true,reintentar_srtm.eq.true")
        .gte("created_at", desde.isoformat())
        .execute()
    )
    return list(resp.data or [])


async def iniciar_reintentos(settings: Any) -> ColaReintentos | None:
    """Crea la cola, retoma los pendientes y arranca el worker (desde el ``lifespan``)."""
    cliente = crear_cliente_servicio(settings)
    if cliente is None:
        configurar_cola(None)
        return None
    cola = ColaReintentos(escritor_supabase(cliente))
    try:
        filas = await asyncio.wait_for(asyncio.to_thread(cargar_pendientes, cliente), 10.0)
        for fila in filas:
            cola.encolar_desde_fila(fila)
        logger.info("reintentos: %d campos pendientes retomados al arrancar", len(cola._pendientes))
    except Exception:  # noqa: BLE001 - sin pendientes previos no se rompe el arranque
        logger.warning("reintentos: no se pudieron cargar los pendientes", exc_info=True)
    configurar_cola(cola)
    cola.iniciar()
    return cola


async def detener_reintentos() -> None:
    cola = obtener_cola()
    if cola is not None:
        await cola.detener()
    configurar_cola(None)
