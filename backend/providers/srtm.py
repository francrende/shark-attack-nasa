"""Provider de topografía NASA SRTM 30 m vía OpenTopoData (BACK-5).

Devuelve la elevación y la pendiente de un punto para el bloque ``topografia_srtm`` del
contrato y las features ``elevacion_m`` / ``pendiente_terreno_pct`` del ML.

Pendiente: grilla 3×3 con 300 m de separación (9 puntos en una sola llamada) y fórmula de
Horn. SRTM viene en metros enteros; con vecinos a ~100 m el redondeo domina en la llanura
pampeana (Pergamino daba 2,2 %, igual que Tandil), mientras que a 300 m queda en el orden
esperable (Pergamino 0,8 %, Tandil 2,1 %, Paraná 1,9 %).

Cascada:
1. OpenTopoData (9 puntos).
2. Si falla / tarda / corte automático / tope diario: elevación de NASA POWER
   (geometry.coordinates[2]) y pendiente de la localidad GeoINTA más cercana (≤ 100 km),
   ``fuente="fallback_regional"``, con advertencia y ``reintentar_srtm=True``.
3. Fuera de 100 km: ``SrtmUnavailable`` (503).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Literal

import httpx

from providers.cache import clave_celda_power, clave_coordenada, obtener_cache
from providers.nasa_power import NasaPowerUnavailable, _validar_coordenadas, fetch_daily_range
from providers.regional import RADIO_FALLBACK_KM, localidad_mas_cercana
from providers.resiliencia import ContadorDiario, CorteAutomatico, EsperaMinima

BASE_URL = "https://api.opentopodata.org/v1/srtm30m"
PASO_M = 300.0
METROS_POR_GRADO_LAT = 111_320.0
TIMEOUT_S = 5.0
TIMEOUT_SEGUNDO_PLANO_S = 30.0  # BACK-32: cola de reintentos
INTERVALO_MIN_S = 1.0  # OpenTopoData público: 1 llamada/segundo
LIMITE_DIARIO = 1000  # OpenTopoData público: 1000 llamadas/día
DURACION_CORTE_S = 300.0

ESPACIO_TOPO = "topografia"
ESPACIO_ELEV_NASA = "nasa_elevacion"
ESPACIO_RECIENTE_NASA = "nasa_reciente"  # ventana reciente cacheada por nasa_telemetry
FECHA_ELEV_NASA = date(2024, 1, 1)  # cualquier día sirve: la elevación viene en geometry
_SIN_DATO = {"sin_dato": True}

FuenteTopo = Literal["opentopodata_srtm30m", "fallback_regional"]
FuenteElevacion = Literal["srtm30m", "nasa_power", "geointa"]


class SrtmUnavailable(Exception):
    """Sin dato de SRTM y sin localidad GeoINTA a menos de 100 km."""


@dataclass(frozen=True)
class TopografiaSrtm:
    elevacion_m: float
    pendiente_terreno_pct: float
    fuente: FuenteTopo
    fuente_elevacion: FuenteElevacion
    distancia_fuente_km: float
    localidad_fallback: str | None
    advertencias: tuple[str, ...]
    # True si es un dato aproximado por una falla transitoria: reintentar SRTM al reabrir el campo.
    reintentar_srtm: bool = False


def topografia_a_dict(topo: TopografiaSrtm) -> dict[str, Any]:
    datos = asdict(topo)
    datos["advertencias"] = list(topo.advertencias)
    return datos


def dict_a_topografia(datos: dict[str, Any]) -> TopografiaSrtm:
    return TopografiaSrtm(**{**datos, "advertencias": tuple(datos.get("advertencias", ()))})


# ---------------------------------------------------------------------------
# Estado del módulo
# ---------------------------------------------------------------------------

_corte = CorteAutomatico(DURACION_CORTE_S)
_espera = EsperaMinima(INTERVALO_MIN_S)
_contador = ContadorDiario(LIMITE_DIARIO)


def reiniciar_estado(
    corte: CorteAutomatico | None = None,
    espera: EsperaMinima | None = None,
    contador: ContadorDiario | None = None,
) -> None:
    """Reinicia corte, espera y contador diario (uso en tests)."""
    global _corte, _espera, _contador
    _corte = corte or CorteAutomatico(DURACION_CORTE_S)
    _espera = espera or EsperaMinima(INTERVALO_MIN_S)
    _contador = contador or ContadorDiario(LIMITE_DIARIO)


# ---------------------------------------------------------------------------
# Funciones puras
# ---------------------------------------------------------------------------


def grilla_3x3(lat: float, lon: float, paso_m: float = PASO_M) -> list[tuple[float, float]]:
    """9 puntos en orden de filas Norte→Sur y columnas Oeste→Este (el centro es el índice 4)."""
    dlat = paso_m / METROS_POR_GRADO_LAT
    dlon = dlat / max(math.cos(math.radians(lat)), 1e-6)
    return [(lat + i * dlat, lon + j * dlon) for i in (1, 0, -1) for j in (-1, 0, 1)]


def pendiente_horn(z: list[float], paso_m: float = PASO_M) -> float:
    """Pendiente (%) con el método de Horn sobre una grilla 3×3 (orden de ``grilla_3x3``).

        a b c
        d e f      dz/dx = ((c + 2f + i) − (a + 2d + g)) / (8·paso)   (hacia el Este)
        g h i      dz/dy = ((a + 2b + c) − (g + 2h + i)) / (8·paso)   (hacia el Norte)
    """
    if len(z) != 9:
        raise ValueError("Se requieren 9 elevaciones")
    a, b, c, d, _e, f, g, h, i = z
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * paso_m)
    dzdy = ((a + 2 * b + c) - (g + 2 * h + i)) / (8 * paso_m)
    return math.hypot(dzdx, dzdy) * 100.0


def _advertencia_fallback(localidad: str, distancia_km: float) -> str:
    return (
        f"Topografía estimada regionalmente: pendiente de {localidad} (a {distancia_km:.0f} km) "
        "y elevación promedio de la zona. El ajuste por pendiente es aproximado."
    )


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


async def _elevacion_respaldo(lat: float, lon: float, client: httpx.AsyncClient) -> float | None:
    """Elevación de la celda de NASA POWER: caché de la ventana reciente → caché propia → request mínimo."""
    cache = obtener_cache()
    clave = clave_celda_power(lat, lon)

    reciente = cache.get(ESPACIO_RECIENTE_NASA, clave)
    if reciente and reciente.get("elevacion_m") is not None:
        return float(reciente["elevacion_m"])
    propia = cache.get(ESPACIO_ELEV_NASA, clave)
    if propia is not None:
        return float(propia["elevacion_m"])

    try:
        serie = await fetch_daily_range(lat, lon, FECHA_ELEV_NASA, FECHA_ELEV_NASA, ["T2M"], client=client)
    except NasaPowerUnavailable:
        return None
    if serie.elevacion_m is None:
        return None
    cache.set(ESPACIO_ELEV_NASA, clave, {"elevacion_m": serie.elevacion_m})
    return serie.elevacion_m


async def _fallback_regional(
    lat: float, lon: float, client: httpx.AsyncClient, motivo: str, *, transitorio: bool
) -> TopografiaSrtm:
    cercana = localidad_mas_cercana(lat, lon, RADIO_FALLBACK_KM)
    if cercana is None:
        raise SrtmUnavailable(
            f"SRTM sin dato ({motivo}) y ninguna localidad GeoINTA a menos de "
            f"{RADIO_FALLBACK_KM:.0f} km de ({lat}, {lon})"
        )
    loc, distancia = cercana

    elevacion = await _elevacion_respaldo(lat, lon, client)
    fuente_elev: FuenteElevacion = "nasa_power"
    if elevacion is None:
        elevacion, fuente_elev = loc["elevacion_m"], "geointa"

    return TopografiaSrtm(
        elevacion_m=round(float(elevacion), 1),
        pendiente_terreno_pct=loc["pendiente_pct"],
        fuente="fallback_regional",
        fuente_elevacion=fuente_elev,
        distancia_fuente_km=round(distancia, 2),
        localidad_fallback=loc["nombre"],
        advertencias=(_advertencia_fallback(loc["nombre"], distancia),),
        reintentar_srtm=transitorio,
    )


async def _cascada(
    client: httpx.AsyncClient, lat: float, lon: float, clave: str, segundo_plano: bool = False
) -> TopografiaSrtm:
    """``segundo_plano`` (BACK-32): ignora el corte, no lo abre ni lo cierra y espera más."""
    cache = obtener_cache()

    if not segundo_plano and not _corte.permite_llamada():
        return await _fallback_regional(lat, lon, client, "corte automático activo", transitorio=True)
    if not _contador.reservar():
        return await _fallback_regional(lat, lon, client, "tope diario de OpenTopoData", transitorio=True)

    await _espera.esperar()
    puntos = grilla_3x3(lat, lon)
    try:
        resp = await client.get(
            BASE_URL,
            params={"locations": "|".join(f"{a:.6f},{b:.6f}" for a, b in puntos)},
            timeout=TIMEOUT_SEGUNDO_PLANO_S if segundo_plano else TIMEOUT_S,
        )
    except httpx.TimeoutException:
        if not segundo_plano:
            _corte.registrar_falla()
        return await _fallback_regional(lat, lon, client, "timeout", transitorio=True)
    except httpx.TransportError as exc:
        return await _fallback_regional(lat, lon, client, f"error de red: {exc}", transitorio=True)

    if resp.status_code == 429:
        if not segundo_plano:
            _corte.registrar_falla()
        return await _fallback_regional(lat, lon, client, "HTTP 429", transitorio=True)
    if resp.status_code != 200:
        return await _fallback_regional(lat, lon, client, f"HTTP {resp.status_code}", transitorio=True)

    try:
        resultados = resp.json()["results"]
        elevaciones = [r.get("elevation") for r in resultados]
        if len(elevaciones) != 9:
            raise ValueError(f"se esperaban 9 resultados, llegaron {len(elevaciones)}")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        return await _fallback_regional(lat, lon, client, f"respuesta inválida: {exc}", transitorio=True)

    if not segundo_plano:
        _corte.registrar_exito()
    if any(e is None for e in elevaciones):
        # Mar o fuera de la cobertura de SRTM: determinístico, se cachea y no se reintenta.
        cache.set(ESPACIO_TOPO, clave, _SIN_DATO)
        return await _fallback_regional(lat, lon, client, "puntos sin dato en SRTM", transitorio=False)

    topo = TopografiaSrtm(
        elevacion_m=round(float(elevaciones[4]), 1),
        pendiente_terreno_pct=round(pendiente_horn([float(e) for e in elevaciones]), 2),
        fuente="opentopodata_srtm30m",
        fuente_elevacion="srtm30m",
        distancia_fuente_km=0.0,
        localidad_fallback=None,
        advertencias=(),
    )
    cache.set(ESPACIO_TOPO, clave, topografia_a_dict(topo))
    return topo


async def fetch_topografia(
    lat: float, lon: float, *, client: httpx.AsyncClient | None = None, segundo_plano: bool = False
) -> TopografiaSrtm:
    """Elevación y pendiente del punto (SRTM 30 m), con caché y cascada de respaldo.

    Raises:
        ValueError: coordenadas fuera de rango.
        SrtmUnavailable: sin dato y sin localidad GeoINTA a menos de 100 km.
    """
    _validar_coordenadas(lat, lon)
    clave = clave_coordenada(lat, lon)
    cacheado = obtener_cache().get(ESPACIO_TOPO, clave)

    if client is None:
        async with httpx.AsyncClient() as propio:
            return await _resolver(propio, lat, lon, clave, cacheado, segundo_plano)
    return await _resolver(client, lat, lon, clave, cacheado, segundo_plano)


async def _resolver(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
    clave: str,
    cacheado: Any,
    segundo_plano: bool = False,
) -> TopografiaSrtm:
    if cacheado == _SIN_DATO:
        return await _fallback_regional(lat, lon, client, "puntos sin dato en SRTM (caché)", transitorio=False)
    if cacheado is not None:
        return dict_a_topografia(cacheado)
    return await _cascada(client, lat, lon, clave, segundo_plano)
