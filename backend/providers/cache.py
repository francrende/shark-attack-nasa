"""Caché enchufable para los providers (BACK-4).

Interfaz mínima ``get(espacio, clave)`` / ``set(espacio, clave, valor, ttl_s)`` con valores
serializables a JSON, para poder sumar más adelante una segunda capa persistente
(p. ej. Supabase) debajo de la caché en memoria sin tocar los providers:

    configurar_cache(CacheEnCapas(CacheMemoria(), secundaria=MiCacheSupabase()))

Claves:
- ``clave_coordenada(lat, lon)``: coordenada redondeada a 3 decimales (~100 m). Suelo.
- ``clave_celda_power(lat, lon)``: centro de la celda de la grilla de NASA POWER
  (0,5° × 0,625°). Verificado: todos los puntos de una celda devuelven la misma serie.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any, Protocol

PASO_LAT_POWER = 0.5
PASO_LON_POWER = 0.625


class Cache(Protocol):
    def get(self, espacio: str, clave: str) -> Any | None: ...

    def set(self, espacio: str, clave: str, valor: Any, ttl_s: float | None = None) -> None: ...


def _copia_json(valor: Any) -> Any:
    """Valida que el valor sea serializable a JSON y devuelve una copia independiente."""
    return json.loads(json.dumps(valor, allow_nan=False))


class CacheMemoria:
    """Caché en memoria del proceso, con TTL opcional por entrada."""

    def __init__(self, reloj: Callable[[], float] = time.monotonic) -> None:
        self._reloj = reloj
        self._datos: dict[tuple[str, str], tuple[Any, float | None]] = {}

    def get(self, espacio: str, clave: str) -> Any | None:
        entrada = self._datos.get((espacio, clave))
        if entrada is None:
            return None
        valor, expira = entrada
        if expira is not None and self._reloj() >= expira:
            del self._datos[(espacio, clave)]
            return None
        return _copia_json(valor)

    def set(self, espacio: str, clave: str, valor: Any, ttl_s: float | None = None) -> None:
        expira = None if ttl_s is None else self._reloj() + ttl_s
        self._datos[(espacio, clave)] = (_copia_json(valor), expira)

    def limpiar(self) -> None:
        self._datos.clear()


class CacheEnCapas:
    """Lee de la primaria; si no está, de la secundaria (y rellena la primaria). Escribe en ambas.

    ``ttl_por_espacio`` define el TTL con que se rellena la primaria al leer de la secundaria
    (la secundaria gestiona su propio vencimiento).
    """

    def __init__(
        self,
        primaria: Cache,
        secundaria: Cache | None = None,
        ttl_por_espacio: dict[str, float] | None = None,
    ) -> None:
        self.primaria = primaria
        self.secundaria = secundaria
        self.ttl_por_espacio = dict(ttl_por_espacio or {})

    def get(self, espacio: str, clave: str) -> Any | None:
        valor = self.primaria.get(espacio, clave)
        if valor is not None or self.secundaria is None:
            return valor
        valor = self.secundaria.get(espacio, clave)
        if valor is not None:
            self.primaria.set(espacio, clave, valor, self.ttl_por_espacio.get(espacio))
        return valor

    def set(self, espacio: str, clave: str, valor: Any, ttl_s: float | None = None) -> None:
        self.primaria.set(espacio, clave, valor, ttl_s)
        if self.secundaria is not None:
            self.secundaria.set(espacio, clave, valor, ttl_s)


def _fmt(x: float) -> str:
    return f"{x + 0.0:.3f}"  # + 0.0 normaliza -0.0


def clave_coordenada(lat: float, lon: float) -> str:
    return f"{_fmt(round(lat, 3))},{_fmt(round(lon, 3))}"


def centro_celda_power(lat: float, lon: float) -> tuple[float, float]:
    return round(lat / PASO_LAT_POWER) * PASO_LAT_POWER, round(lon / PASO_LON_POWER) * PASO_LON_POWER


def clave_celda_power(lat: float, lon: float) -> str:
    clat, clon = centro_celda_power(lat, lon)
    return f"{_fmt(clat)},{_fmt(clon)}"


TTL_POR_ESPACIO_DEFAULT = {"nasa_reciente": 6 * 3600.0}

_cache_global: Cache = CacheEnCapas(CacheMemoria(), ttl_por_espacio=TTL_POR_ESPACIO_DEFAULT)


def obtener_cache() -> Cache:
    return _cache_global


def configurar_cache(cache: Cache) -> None:
    """Reemplaza la caché global (para enchufar Supabase o aislar tests)."""
    global _cache_global
    _cache_global = cache
