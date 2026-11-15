"""Provider crudo de NASA POWER API (BACK-1).

Trae la serie diaria de los últimos 30 días para un punto (lat, lon), limpia los
valores de relleno ``-999`` (lag de procesamiento satelital de 3 a 7 días) y expone
el último valor válido de cada parámetro.

No calcula métricas derivadas (anomalías, riesgo térmico): eso es BACK-2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETROS: list[str] = [
    "GWETROOT",
    "GWETTOP",
    "GWETPROF",
    "PRECTOTCORR",
    "T2M",
    "T2M_MAX",
    "T2M_MIN",
    "EVPTRNS",
    "ALLSKY_SFC_SW_DWN",
]
VENTANA_DIAS = 30
FILL_VALUE = -999.0
TIMEOUT_S = 10.0
MAX_INTENTOS = 2  # 1 intento + 1 reintento


class NasaPowerUnavailable(Exception):
    """NASA POWER no respondió correctamente (timeout, red, HTTP no-2xx o JSON inválido)."""


@dataclass(frozen=True)
class NasaPowerDailySeries:
    lat: float
    lon: float
    start: date
    end: date
    series: dict[str, dict[date, float | None]] = field(default_factory=dict)
    # Elevación de la celda (geometry.coordinates[2]); respaldo del provider SRTM (BACK-5).
    elevacion_m: float | None = None

    def last_valid(self, param: str) -> tuple[date, float] | None:
        """Último valor válido (no ``-999``) del parámetro, recorriendo desde la fecha más reciente."""
        valores = self.series.get(param, {})
        for dia in sorted(valores, reverse=True):
            valor = valores[dia]
            if valor is not None:
                return dia, valor
        return None


def serie_a_dict(serie: NasaPowerDailySeries) -> dict[str, Any]:
    """Serializa a JSON-compatible (para la caché)."""
    return {
        "lat": serie.lat,
        "lon": serie.lon,
        "start": serie.start.isoformat(),
        "end": serie.end.isoformat(),
        "elevacion_m": serie.elevacion_m,
        "series": {
            p: {d.strftime("%Y%m%d"): v for d, v in valores.items()} for p, valores in serie.series.items()
        },
    }


def dict_a_serie(datos: dict[str, Any]) -> NasaPowerDailySeries:
    return NasaPowerDailySeries(
        lat=datos["lat"],
        lon=datos["lon"],
        start=date.fromisoformat(datos["start"]),
        end=date.fromisoformat(datos["end"]),
        series={
            p: {datetime.strptime(k, "%Y%m%d").date(): v for k, v in valores.items()}
            for p, valores in datos["series"].items()
        },
        elevacion_m=datos.get("elevacion_m"),
    )


def _elevacion(payload: Any) -> float | None:
    """``geometry.coordinates[2]`` de la respuesta de NASA POWER (``None`` si falta o es -999)."""
    try:
        valor = payload["geometry"]["coordinates"][2]
    except (KeyError, IndexError, TypeError):
        return None
    return _limpiar(valor)


def _validar_coordenadas(lat: float, lon: float) -> None:
    if not -90.0 <= lat <= 90.0:
        raise ValueError(f"Latitud fuera de rango [-90, 90]: {lat}")
    if not -180.0 <= lon <= 180.0:
        raise ValueError(f"Longitud fuera de rango [-180, 180]: {lon}")


def _limpiar(valor: Any) -> float | None:
    if valor is None:
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return None if numero <= FILL_VALUE else numero


def _parsear(payload: Any) -> dict[str, dict[date, float | None]]:
    try:
        parametros = payload["properties"]["parameter"]
    except (KeyError, TypeError) as exc:
        raise NasaPowerUnavailable("Respuesta de NASA POWER sin 'properties.parameter'") from exc
    if not isinstance(parametros, dict):
        raise NasaPowerUnavailable("'properties.parameter' no es un objeto")

    series: dict[str, dict[date, float | None]] = {}
    for param, por_fecha in parametros.items():
        if not isinstance(por_fecha, dict):
            raise NasaPowerUnavailable(f"Serie inválida para el parámetro {param}")
        serie: dict[date, float | None] = {}
        for clave, valor in por_fecha.items():
            try:
                dia = datetime.strptime(clave, "%Y%m%d").date()
            except ValueError as exc:
                raise NasaPowerUnavailable(f"Fecha inválida '{clave}' en {param}") from exc
            serie[dia] = _limpiar(valor)
        series[param] = serie
    return series


async def _get_con_reintento(client: httpx.AsyncClient, params: dict[str, str]) -> Any:
    ultimo_error: Exception | None = None
    for _ in range(MAX_INTENTOS):
        try:
            respuesta = await client.get(BASE_URL, params=params, timeout=TIMEOUT_S)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            ultimo_error = exc
            continue

        if respuesta.status_code >= 500:
            ultimo_error = NasaPowerUnavailable(f"NASA POWER respondió HTTP {respuesta.status_code}")
            continue
        if respuesta.status_code != 200:
            raise NasaPowerUnavailable(
                f"NASA POWER respondió HTTP {respuesta.status_code}: {respuesta.text[:300]}"
            )
        try:
            return respuesta.json()
        except ValueError as exc:
            raise NasaPowerUnavailable("NASA POWER devolvió un JSON malformado") from exc

    raise NasaPowerUnavailable(
        f"NASA POWER no disponible tras {MAX_INTENTOS} intentos: {ultimo_error}"
    ) from ultimo_error


async def fetch_daily_window(
    lat: float,
    lon: float,
    *,
    dias: int = VENTANA_DIAS,
    client: httpx.AsyncClient | None = None,
    today: date | None = None,
) -> NasaPowerDailySeries:
    """Descarga la ventana diaria de los últimos ``dias`` días (default 30) y limpia los ``-999``.

    Raises:
        ValueError: coordenadas fuera de rango o ``dias`` < 1.
        NasaPowerUnavailable: falla de red, timeout, HTTP no-2xx o JSON inválido.
    """
    if dias < 1:
        raise ValueError(f"'dias' debe ser >= 1: {dias}")
    end = today or datetime.now(timezone.utc).date()
    start = end - timedelta(days=dias - 1)
    return await fetch_daily_range(lat, lon, start, end, PARAMETROS, client=client)


async def fetch_daily_range(
    lat: float,
    lon: float,
    start: date,
    end: date,
    parametros: list[str],
    *,
    client: httpx.AsyncClient | None = None,
) -> NasaPowerDailySeries:
    """Descarga la serie diaria [start, end] de los ``parametros`` pedidos y limpia los ``-999``.

    Raises:
        ValueError: coordenadas fuera de rango, rango de fechas invertido o sin parámetros.
        NasaPowerUnavailable: falla de red, timeout, HTTP no-2xx o JSON inválido.
    """
    _validar_coordenadas(lat, lon)
    if start > end:
        raise ValueError(f"Rango de fechas invertido: {start} > {end}")
    if not parametros:
        raise ValueError("Se requiere al menos un parámetro")

    params = {
        "parameters": ",".join(parametros),
        "community": "AG",
        "longitude": str(lon),
        "latitude": str(lat),
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }

    if client is None:
        async with httpx.AsyncClient() as propio:
            payload = await _get_con_reintento(propio, params)
    else:
        payload = await _get_con_reintento(client, params)

    return NasaPowerDailySeries(
        lat=lat, lon=lon, start=start, end=end, series=_parsear(payload), elevacion_m=_elevacion(payload)
    )
