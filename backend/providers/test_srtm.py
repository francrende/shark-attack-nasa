"""Tests de BACK-5 (sin red): httpx.MockTransport + asyncio.run."""

import asyncio
import math
from datetime import date

import httpx
import pytest

from providers import srtm
from providers.cache import CacheEnCapas, CacheMemoria, clave_celda_power, clave_coordenada, configurar_cache, obtener_cache
from providers.nasa_power import dict_a_serie, fetch_daily_range, serie_a_dict
from providers.regional import haversine_km
from providers.resiliencia import ContadorDiario, CorteAutomatico, EsperaMinima
from providers.srtm import (
    SrtmUnavailable,
    TopografiaSrtm,
    fetch_topografia,
    grilla_3x3,
    pendiente_horn,
)

PERGAMINO = (-33.95, -60.57)
MADRID = (40.42, -3.70)
ELEV_NASA = 71.5


class Reloj:
    def __init__(self) -> None:
        self.t = 0.0
        self.dormido: list[float] = []

    def __call__(self) -> float:
        return self.t

    async def dormir(self, s: float) -> None:
        self.dormido.append(s)
        self.t += s


@pytest.fixture(autouse=True)
def _estado_limpio():
    reloj = Reloj()
    srtm.reiniciar_estado(
        CorteAutomatico(reloj=reloj),
        EsperaMinima(reloj=reloj, dormir=reloj.dormir),
        ContadorDiario(limite=1000, hoy=lambda: date(2026, 11, 14)),
    )
    configurar_cache(CacheEnCapas(CacheMemoria(reloj=reloj)))
    yield reloj
    srtm.reiniciar_estado()
    configurar_cache(CacheEnCapas(CacheMemoria()))


def _respuesta_topo(elevaciones):
    return {"status": "OK", "results": [{"elevation": e, "location": {}} for e in elevaciones]}


def _respuesta_nasa(elev=ELEV_NASA):
    return {
        "geometry": {"coordinates": [-60.57, -33.95, elev]},
        "properties": {"parameter": {"T2M": {"20240101": 25.0}}},
    }


def _handler(topo, nasa=None, registro=None):
    """Enruta por host: OpenTopoData -> ``topo`` ; NASA POWER -> ``nasa``."""

    def h(req):
        es_topo = "opentopodata" in req.url.host
        if registro is not None:
            registro.append("topo" if es_topo else "nasa")
        destino = topo if es_topo else (nasa or (lambda r: httpx.Response(200, json=_respuesta_nasa())))
        return destino(req)

    return h


def _run(handler, lat_lon=PERGAMINO):
    async def _go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_topografia(*lat_lon, client=client)

    return asyncio.run(_go())


PLANO = [69.0] * 9
LLANO_REAL = [70.0, 71.0, 71.0, 69.0, 69.0, 71.0, 67.0, 66.0, 68.0]


# ---------- funciones puras ----------


def test_horn_plano_horizontal_da_cero():
    assert pendiente_horn(PLANO) == 0.0


@pytest.mark.parametrize("orientacion", ["este", "norte", "oeste", "sur"])
def test_horn_plano_inclinado_1pct_en_cualquier_orientacion(orientacion):
    # 1 m cada 100 m -> 3 m por paso de 300 m
    def z(fila, col):  # fila 0 = Norte, col 0 = Oeste
        este, norte = (col - 1) * 300, (1 - fila) * 300
        return {"este": este, "oeste": -este, "norte": norte, "sur": -norte}[orientacion] / 100

    grilla = [z(f, c) for f in range(3) for c in range(3)]
    assert pendiente_horn(grilla) == pytest.approx(1.0)


def test_horn_diagonal():
    grilla = [((c - 1) * 300 + (1 - f) * 300) / 100 for f in range(3) for c in range(3)]
    assert pendiente_horn(grilla) == pytest.approx(math.sqrt(2))


def test_horn_requiere_9_valores():
    with pytest.raises(ValueError):
        pendiente_horn([1.0] * 8)


def test_grilla_3x3_orden_y_distancias():
    pts = grilla_3x3(*PERGAMINO)
    assert len(pts) == 9
    assert pts[4] == PERGAMINO
    lat0, lon0 = PERGAMINO
    assert pts[1][0] > lat0 and pts[7][0] < lat0  # N arriba, S abajo
    assert pts[3][1] < lon0 and pts[5][1] > lon0  # O izquierda, E derecha
    for idx in (1, 3, 5, 7):
        assert haversine_km(lat0, lon0, *pts[idx]) == pytest.approx(0.3, abs=0.005)


# ---------- camino feliz, query y caché ----------


def test_dato_real_y_query_de_una_llamada():
    capturado = {}

    def topo(req):
        capturado["locations"] = req.url.params["locations"]
        return httpx.Response(200, json=_respuesta_topo(LLANO_REAL))

    registro = []
    t = _run(_handler(topo, registro=registro))
    assert isinstance(t, TopografiaSrtm)
    assert t.fuente == "opentopodata_srtm30m"
    assert t.fuente_elevacion == "srtm30m"
    assert t.elevacion_m == 69.0  # centro de la grilla
    assert t.pendiente_terreno_pct == round(pendiente_horn(LLANO_REAL), 2)
    assert t.reintentar_srtm is False and t.advertencias == ()
    assert registro == ["topo"]
    assert len(capturado["locations"].split("|")) == 9


def test_cache_por_coordenada():
    registro = []
    h = _handler(lambda r: httpx.Response(200, json=_respuesta_topo(LLANO_REAL)), registro=registro)
    t1 = _run(h, (-33.9501, -60.5702))
    t2 = _run(h, (-33.9504, -60.5698))
    assert registro == ["topo"]
    assert t1 == t2


def test_espera_minima_entre_llamadas(_estado_limpio):
    h = _handler(lambda r: httpx.Response(200, json=_respuesta_topo(PLANO)))
    _run(h, (-33.90, -60.57))
    _estado_limpio.t += 0.3
    _run(h, (-33.80, -60.57))
    assert _estado_limpio.dormido == [pytest.approx(0.7)]


# ---------- fallbacks ----------


def test_timeout_fallback_con_elevacion_nasa_y_corte():
    def topo(req):
        raise httpx.ReadTimeout("timeout", request=req)

    registro = []
    t = _run(_handler(topo, registro=registro))
    assert t.fuente == "fallback_regional"
    assert t.fuente_elevacion == "nasa_power"
    assert t.elevacion_m == ELEV_NASA
    assert t.pendiente_terreno_pct == 1.15  # Pergamino GeoINTA
    assert t.localidad_fallback == "Pergamino (Pampa Ondulada)"
    assert t.reintentar_srtm is True
    assert "Topografía estimada regionalmente" in t.advertencias[0]
    assert registro == ["topo", "nasa"]
    assert srtm._corte.cortado
    assert obtener_cache().get(srtm.ESPACIO_TOPO, clave_coordenada(*PERGAMINO)) is None  # no se cachea


def test_durante_el_corte_no_se_llama_a_opentopodata(_estado_limpio):
    def timeout(req):
        raise httpx.ReadTimeout("timeout", request=req)

    _run(_handler(timeout))
    registro = []
    _estado_limpio.t += 100
    t = _run(_handler(lambda r: httpx.Response(200, json=_respuesta_topo(PLANO)), registro=registro), (-33.90, -60.57))
    assert "topo" not in registro
    assert t.fuente == "fallback_regional"


def test_429_activa_corte():
    _run(_handler(lambda r: httpx.Response(429)))
    assert srtm._corte.cortado


def test_elevacion_respaldo_usa_cache_de_ventana_reciente():
    obtener_cache().set("nasa_reciente", clave_celda_power(*PERGAMINO), {"elevacion_m": 80.0, "series": {}})
    registro = []
    t = _run(_handler(lambda r: httpx.Response(503), registro=registro))
    assert t.elevacion_m == 80.0
    assert registro == ["topo"]  # no hizo falta pedir a NASA


def test_elevacion_respaldo_se_cachea_por_celda():
    registro = []
    falla = lambda r: httpx.Response(503)  # noqa: E731
    _run(_handler(falla, registro=registro), (-33.95, -60.57))
    _run(_handler(falla, registro=registro), (-34.20, -60.90))  # misma celda de NASA
    assert registro.count("nasa") == 1


def test_nasa_tambien_falla_usa_elevacion_geointa():
    t = _run(_handler(lambda r: httpx.Response(503), nasa=lambda r: httpx.Response(503)))
    assert t.fuente_elevacion == "geointa"
    assert t.elevacion_m == 68.0


def test_puntos_null_sin_dato_cacheado_y_sin_reintento():
    elev = list(PLANO)
    elev[2] = None
    registro = []
    t = _run(_handler(lambda r: httpx.Response(200, json=_respuesta_topo(elev)), registro=registro))
    assert t.fuente == "fallback_regional"
    assert t.reintentar_srtm is False
    assert obtener_cache().get(srtm.ESPACIO_TOPO, clave_coordenada(*PERGAMINO)) == {"sin_dato": True}
    registro.clear()
    _run(_handler(lambda r: httpx.Response(200, json=_respuesta_topo(PLANO)), registro=registro))
    assert "topo" not in registro  # va directo al fallback desde la caché


def test_respuesta_incompleta_va_a_fallback():
    t = _run(_handler(lambda r: httpx.Response(200, json=_respuesta_topo([69.0] * 4))))
    assert t.fuente == "fallback_regional" and t.reintentar_srtm is True


def test_tope_diario_va_a_fallback():
    srtm.reiniciar_estado(contador=ContadorDiario(limite=1, hoy=lambda: date(2026, 11, 14)))
    ok = lambda r: httpx.Response(200, json=_respuesta_topo(PLANO))  # noqa: E731
    assert _run(_handler(ok), (-33.90, -60.57)).fuente == "opentopodata_srtm30m"
    registro = []
    t = _run(_handler(ok, registro=registro), (-33.80, -60.57))
    assert t.fuente == "fallback_regional" and "topo" not in registro


def test_contador_diario_se_reinicia_al_cambiar_el_dia():
    dia = {"d": date(2026, 11, 14)}
    c = ContadorDiario(limite=1, hoy=lambda: dia["d"])
    assert c.reservar() and not c.reservar()
    dia["d"] = date(2026, 11, 15)
    assert c.reservar()


def test_fuera_de_100km_lanza_unavailable():
    with pytest.raises(SrtmUnavailable):
        _run(_handler(lambda r: httpx.Response(503)), MADRID)


@pytest.mark.parametrize("lat,lon", [(-91, 0), (0, 181)])
def test_coordenadas_invalidas(lat, lon):
    with pytest.raises(ValueError):
        asyncio.run(fetch_topografia(lat, lon))


# ---------- elevación capturada en NASA POWER ----------


def test_nasa_power_captura_elevacion_y_la_serializa():
    async def _go():
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json=_respuesta_nasa(55.0)))
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_daily_range(-33.95, -60.57, date(2024, 1, 1), date(2024, 1, 1), ["T2M"], client=client)

    serie = asyncio.run(_go())
    assert serie.elevacion_m == 55.0
    assert dict_a_serie(serie_a_dict(serie)).elevacion_m == 55.0


def test_nasa_power_sin_geometry_da_none():
    async def _go():
        payload = {"properties": {"parameter": {"T2M": {"20240101": 25.0}}}}
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json=payload))
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_daily_range(-33.95, -60.57, date(2024, 1, 1), date(2024, 1, 1), ["T2M"], client=client)

    assert asyncio.run(_go()).elevacion_m is None


# ---------- BACK-32: modo segundo plano (cola de reintentos) ----------


def _run_fondo(handler, lat_lon=PERGAMINO):
    async def _go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_topografia(*lat_lon, client=client, segundo_plano=True)

    return asyncio.run(_go())


def _timeout(req):
    raise httpx.ReadTimeout("timeout", request=req)


def test_srtm_segundo_plano_consulta_con_corte_activo_y_no_lo_toca():
    _run(_handler(_timeout))  # el tráfico en vivo abre el corte
    registro = []
    topo = _run_fondo(_handler(lambda r: httpx.Response(200, json=_respuesta_topo(LLANO_REAL)), registro=registro))
    assert topo.fuente == "opentopodata_srtm30m" and "topo" in registro
    assert srtm._corte.cortado  # el éxito en segundo plano no lo cierra


def test_srtm_segundo_plano_timeout_largo_y_no_abre_corte():
    timeouts = []

    def topo(req):
        timeouts.append(req.extensions["timeout"]["read"])
        raise httpx.ReadTimeout("timeout", request=req)

    resultado = _run_fondo(_handler(topo))
    assert resultado.reintentar_srtm is True
    assert timeouts == [srtm.TIMEOUT_SEGUNDO_PLANO_S]
    assert not srtm._corte.cortado
