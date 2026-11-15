"""Tests de BACK-1 (sin red): httpx.MockTransport + asyncio.run."""

import asyncio
from datetime import date

import httpx
import pytest

from providers.nasa_power import (
    PARAMETROS,
    NasaPowerUnavailable,
    fetch_daily_window,
)

HOY = date(2026, 11, 14)


def _payload(gwetroot: dict, extra: dict | None = None) -> dict:
    parametros = {"GWETROOT": gwetroot}
    parametros.update(extra or {})
    return {"properties": {"parameter": parametros}}


def _run(handler, **kwargs):
    async def _go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_daily_window(-33.95, -60.57, client=client, today=HOY, **kwargs)

    return asyncio.run(_go())


def test_parseo_correcto():
    payload = _payload(
        {"20261110": 0.34, "20261111": 0.35},
        {"T2M_MAX": {"20261110": 31.2, "20261111": 29.8}},
    )
    serie = _run(lambda req: httpx.Response(200, json=payload))

    assert serie.series["GWETROOT"][date(2026, 11, 10)] == 0.34
    assert serie.series["T2M_MAX"][date(2026, 11, 11)] == 29.8
    assert serie.last_valid("GWETROOT") == (date(2026, 11, 11), 0.35)
    assert serie.start == date(2026, 10, 16)
    assert serie.end == HOY


def test_last_valid_saltea_lag_de_999():
    payload = _payload(
        {"20261108": 0.34, "20261109": -999.0, "20261110": -999, "20261111": -999.0}
    )
    serie = _run(lambda req: httpx.Response(200, json=payload))

    assert serie.series["GWETROOT"][date(2026, 11, 10)] is None
    assert serie.last_valid("GWETROOT") == (date(2026, 11, 8), 0.34)


def test_parametro_todo_999_devuelve_none():
    payload = _payload({"20261110": -999.0, "20261111": -999.0})
    serie = _run(lambda req: httpx.Response(200, json=payload))

    assert serie.last_valid("GWETROOT") is None
    assert serie.last_valid("PARAM_INEXISTENTE") is None


def test_reintento_500_luego_200():
    llamadas = []

    def handler(req):
        llamadas.append(req)
        if len(llamadas) == 1:
            return httpx.Response(500)
        return httpx.Response(200, json=_payload({"20261111": 0.4}))

    serie = _run(handler)
    assert len(llamadas) == 2
    assert serie.last_valid("GWETROOT") == (date(2026, 11, 11), 0.4)


def test_dos_500_lanzan_unavailable():
    llamadas = []

    def handler(req):
        llamadas.append(req)
        return httpx.Response(503)

    with pytest.raises(NasaPowerUnavailable):
        _run(handler)
    assert len(llamadas) == 2


def test_timeout_lanza_unavailable():
    llamadas = []

    def handler(req):
        llamadas.append(req)
        raise httpx.ReadTimeout("timeout", request=req)

    with pytest.raises(NasaPowerUnavailable):
        _run(handler)
    assert len(llamadas) == 2


def test_4xx_no_reintenta():
    llamadas = []

    def handler(req):
        llamadas.append(req)
        return httpx.Response(422, json={"messages": ["bad request"]})

    with pytest.raises(NasaPowerUnavailable):
        _run(handler)
    assert len(llamadas) == 1


def test_json_sin_parameter_lanza_unavailable():
    with pytest.raises(NasaPowerUnavailable):
        _run(lambda req: httpx.Response(200, json={"properties": {}}))


@pytest.mark.parametrize("lat,lon", [(-91, 0), (91, 0), (0, -181), (0, 181)])
def test_coordenadas_invalidas(lat, lon):
    with pytest.raises(ValueError):
        asyncio.run(fetch_daily_window(lat, lon, today=HOY))


def test_query_enviada():
    capturada = {}

    def handler(req):
        capturada["params"] = dict(req.url.params)
        return httpx.Response(200, json=_payload({"20261114": 0.3}))

    _run(handler)
    params = capturada["params"]
    assert params["community"] == "AG"
    assert params["start"] == "20261016"
    assert params["end"] == "20261114"
    assert params["latitude"] == "-33.95"
    assert params["longitude"] == "-60.57"
    assert params["format"] == "JSON"
    assert params["parameters"].split(",") == PARAMETROS
