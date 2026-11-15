"""Tests de BACK-3 (sin red): httpx.MockTransport + asyncio.run."""

import asyncio

import httpx
import pytest

from providers import soilgrids
from providers.cache import CacheEnCapas, CacheMemoria, clave_coordenada, configurar_cache
from providers.soilgrids import (
    ADV_FALLBACK,
    ADV_SIN_PH,
    ADV_SIN_SOC,
    ADV_VECINO,
    CorteAutomatico,
    LimitadorTasa,
    PerfilSueloSatelital,
    SoilGridsUnavailable,
    _parsear,
    clasificar_textura_usda,
    fetch_perfil_suelo,
    perfil_a_dict,
)

PERGAMINO = (-33.95, -60.57)
MADRID = (40.42, -3.70)

# Valores reales de Pergamino (14/11/2026), en unidades mapeadas (g/kg, dg/kg, pH*10)
PERGAMINO_RAW = {
    "clay": (220, 227, 243),
    "sand": (143, 142, 142),
    "silt": (637, 632, 615),
    "soc": (273, 188, 142),
    "phh2o": (63, 63, 65),
}
NULOS = {p: (None, None, None) for p in PERGAMINO_RAW}


class Reloj:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


class Secundaria(CacheMemoria):
    """Simula la capa persistente (Supabase) para verificar qué llega a ella."""


@pytest.fixture(autouse=True)
def _estado_limpio():
    reloj = Reloj()
    soilgrids.reiniciar_estado(LimitadorTasa(reloj=reloj), CorteAutomatico(reloj=reloj), lotes_ejemplo=[])
    configurar_cache(CacheEnCapas(CacheMemoria(reloj=reloj), secundaria=Secundaria(reloj=reloj)))
    yield reloj
    soilgrids.reiniciar_estado()
    configurar_cache(CacheEnCapas(CacheMemoria()))


def _en_cache(lat_lon=PERGAMINO):
    from providers.cache import obtener_cache

    return obtener_cache().get(soilgrids.ESPACIO_SUELO, clave_coordenada(*lat_lon))


def _en_secundaria(lat_lon=PERGAMINO):
    from providers.cache import obtener_cache

    return obtener_cache().secundaria.get(soilgrids.ESPACIO_SUELO, clave_coordenada(*lat_lon))


def _payload(raw: dict) -> dict:
    etiquetas = ("0-5cm", "5-15cm", "15-30cm")
    return {
        "properties": {
            "layers": [
                {
                    "name": prop,
                    "unit_measure": {"d_factor": 10},
                    "depths": [{"label": e, "values": {"mean": v}} for e, v in zip(etiquetas, vals)],
                }
                for prop, vals in raw.items()
            ]
        }
    }


def _run(handler, lat_lon=PERGAMINO):
    llamadas = []

    def wrapped(req):
        llamadas.append((float(req.url.params["lat"]), float(req.url.params["lon"])))
        return handler(req)

    async def _go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(wrapped)) as client:
            return await fetch_perfil_suelo(*lat_lon, client=client)

    return asyncio.run(_go()), llamadas


def _es_punto(req, lat_lon=PERGAMINO) -> bool:
    return (float(req.url.params["lat"]), float(req.url.params["lon"])) == lat_lon


# ---------- parseo y textura ----------


def test_parseo_pondera_0_30cm_y_aplica_d_factor():
    v = _parsear(_payload(PERGAMINO_RAW))
    # (220*5 + 227*10 + 243*15) / 30 / 10
    assert v["clay"] == pytest.approx((220 * 5 + 227 * 10 + 243 * 15) / 300)
    assert v["soc"] == pytest.approx((273 * 5 + 188 * 10 + 142 * 15) / 300)  # ≈ 17,9 g/kg
    assert v["phh2o"] == pytest.approx(6.4)


def test_parseo_con_profundidad_faltante_pondera_las_disponibles():
    raw = dict(PERGAMINO_RAW, clay=(200, None, 300))
    assert _parsear(_payload(raw))["clay"] == pytest.approx((200 * 5 + 300 * 15) / 200)


def test_parseo_json_invalido_lanza_value_error():
    with pytest.raises(ValueError):
        _parsear({"properties": {}})


@pytest.mark.parametrize(
    "arena,limo,arcilla,esperado",
    [
        (90, 5, 5, "arenoso"),
        (82, 10, 8, "arenoso_franco"),
        (75, 15, 10, "franco_arenoso"),
        (40, 40, 20, "franco"),
        (14, 62, 24, "franco_limoso"),
        (5, 85, 10, "limoso"),
        (60, 15, 25, "franco_arcillo_arenoso"),
        (30, 35, 35, "franco_arcilloso"),
        (10, 55, 35, "franco_arcillo_limoso"),
        (50, 5, 45, "arcillo_arenoso"),
        (10, 50, 40, "arcillo_limoso"),
        (20, 20, 60, "arcilloso"),
    ],
)
def test_triangulo_usda(arena, limo, arcilla, esperado):
    assert clasificar_textura_usda(arena, limo, arcilla) == esperado


def test_textura_normaliza_a_100():
    # Mismas proporciones que (14, 62, 24) pero sumando 50
    assert clasificar_textura_usda(7, 31, 12) == "franco_limoso"


# ---------- camino feliz y caché ----------


def test_pergamino_dato_real():
    perfil, llamadas = _run(lambda req: httpx.Response(200, json=_payload(PERGAMINO_RAW)))
    assert isinstance(perfil, PerfilSueloSatelital)
    assert perfil.fuente == "isric_soilgrids_v2"
    assert perfil.textura_predominante == "franco_limoso"
    assert perfil.arcilla_pct == 23.4
    assert perfil.carbono_organico_g_kg == 17.9
    assert perfil.ph == 6.4
    assert perfil.distancia_fuente_km == 0.0
    assert perfil.advertencias == ()
    assert len(llamadas) == 1


def test_query_una_sola_llamada_con_todo():
    capturado = {}

    def handler(req):
        capturado["props"] = req.url.params.get_list("property")
        capturado["depths"] = req.url.params.get_list("depth")
        capturado["value"] = req.url.params["value"]
        return httpx.Response(200, json=_payload(PERGAMINO_RAW))

    _run(handler)
    assert capturado["props"] == ["clay", "sand", "silt", "soc", "phh2o"]
    assert capturado["depths"] == ["0-5cm", "5-15cm", "15-30cm"]
    assert capturado["value"] == "mean"


def test_cache_por_coordenada_redondeada():
    handler = lambda req: httpx.Response(200, json=_payload(PERGAMINO_RAW))  # noqa: E731
    _, llamadas1 = _run(handler, (-33.9501, -60.5702))
    perfil2, llamadas2 = _run(handler, (-33.9504, -60.5698))  # misma celda de ~100 m
    assert len(llamadas1) == 1
    assert llamadas2 == []
    assert perfil2.fuente == "isric_soilgrids_v2"


# ---------- cascada: vecinos ----------


def test_null_usa_primer_vecino_con_dato():
    def handler(req):
        lat = float(req.url.params["lat"])
        if _es_punto(req):
            return httpx.Response(200, json=_payload(NULOS))
        if lat < PERGAMINO[0]:  # vecino Sur con dato; Norte sin dato
            return httpx.Response(200, json=_payload(PERGAMINO_RAW))
        return httpx.Response(200, json=_payload(NULOS))

    perfil, llamadas = _run(handler)
    assert perfil.fuente == "isric_soilgrids_v2_vecino"
    assert perfil.distancia_fuente_km == pytest.approx(0.5, abs=0.05)
    assert ADV_VECINO in perfil.advertencias
    assert len(llamadas) == 5  # punto + 4 vecinos en paralelo


def test_vecinos_a_500m_en_las_4_direcciones():
    def handler(req):
        return httpx.Response(200, json=_payload(NULOS))

    _, llamadas = _run(handler)
    vecinos = llamadas[1:]
    assert len(vecinos) == 4
    lat0, lon0 = PERGAMINO
    from providers.soilgrids import _haversine_km

    for vlat, vlon in vecinos:
        assert _haversine_km(lat0, lon0, vlat, vlon) == pytest.approx(0.5, abs=0.02)
    assert {(vlat > lat0, vlat < lat0, vlon > lon0, vlon < lon0) for vlat, vlon in vecinos} == {
        (True, False, False, False),
        (False, True, False, False),
        (False, False, True, False),
        (False, False, False, True),
    }


def test_todo_null_cae_a_fallback_y_se_cachea():
    perfil, llamadas = _run(lambda req: httpx.Response(200, json=_payload(NULOS)))
    assert perfil.fuente == "fallback_regional"
    assert perfil.localidad_fallback == "Pergamino (Pampa Ondulada)"
    assert len(llamadas) == 5

    # Segunda consulta: va directo al fallback desde la caché, sin requests
    perfil2, llamadas2 = _run(lambda req: httpx.Response(200, json=_payload(PERGAMINO_RAW)))
    assert perfil2.fuente == "fallback_regional"
    assert llamadas2 == []


# ---------- cascada: fallas -> fallback ----------


def test_timeout_va_directo_a_fallback_sin_vecinos():
    def handler(req):
        raise httpx.ReadTimeout("timeout", request=req)

    perfil, llamadas = _run(handler)
    assert perfil.fuente == "fallback_regional"
    assert len(llamadas) == 1


def test_429_va_directo_a_fallback():
    perfil, llamadas = _run(lambda req: httpx.Response(429))
    assert perfil.fuente == "fallback_regional"
    assert len(llamadas) == 1


def test_fallback_por_timeout_no_se_cachea(_estado_limpio):
    def timeout(req):
        raise httpx.ReadTimeout("timeout", request=req)

    _run(timeout)
    _estado_limpio.t = 300.0  # fin del corte automático (BACK-4)
    perfil, llamadas = _run(lambda req: httpx.Response(200, json=_payload(PERGAMINO_RAW)))
    assert perfil.fuente == "isric_soilgrids_v2"
    assert len(llamadas) == 1


def test_fallback_contenido_y_advertencia():
    perfil, _ = _run(lambda req: httpx.Response(503))
    assert perfil.arcilla_pct == 25.4
    assert perfil.arena_pct is None and perfil.limo_pct is None
    assert perfil.carbono_organico_g_kg is None and perfil.ph is None
    assert perfil.textura_predominante is None
    assert perfil.advertencias == (ADV_FALLBACK,)
    assert perfil.distancia_fuente_km == pytest.approx(6.7, abs=0.2)  # Pergamino pedido vs. tabla


def test_fuera_de_100km_lanza_unavailable():
    with pytest.raises(SoilGridsUnavailable):
        _run(lambda req: httpx.Response(503), MADRID)


def test_dato_parcial_sin_soc_ni_ph():
    raw = dict(PERGAMINO_RAW, soc=(None, None, None), phh2o=(None, None, None))
    perfil, _ = _run(lambda req: httpx.Response(200, json=_payload(raw)))
    assert perfil.fuente == "isric_soilgrids_v2"
    assert perfil.carbono_organico_g_kg is None
    assert perfil.textura_predominante == "franco_limoso"
    assert ADV_SIN_SOC in perfil.advertencias
    assert ADV_SIN_PH in perfil.advertencias


# ---------- limitador de tasa ----------


def test_sin_cupo_va_directo_a_fallback(_estado_limpio):
    handler = lambda req: httpx.Response(200, json=_payload(PERGAMINO_RAW))  # noqa: E731
    puntos = [(-33.95 + i * 0.01, -60.57) for i in range(6)]
    fuentes, total = [], 0
    for p in puntos:
        perfil, llamadas = _run(handler, p)
        fuentes.append(perfil.fuente)
        total += len(llamadas)
    assert fuentes[:5] == ["isric_soilgrids_v2"] * 5
    assert fuentes[5] == "fallback_regional"
    assert total == 5

    # Pasados 60 s se libera el cupo
    _estado_limpio.t = 60.0
    perfil, llamadas = _run(handler, (-33.80, -60.57))
    assert perfil.fuente == "isric_soilgrids_v2"
    assert len(llamadas) == 1


def test_cupo_parcial_consulta_solo_los_vecinos_que_entran():
    ok = lambda req: httpx.Response(200, json=_payload(PERGAMINO_RAW))  # noqa: E731
    _run(ok, (-33.90, -60.57))
    _run(ok, (-33.85, -60.57))  # quedan 3 llamadas de cupo

    perfil, llamadas = _run(lambda req: httpx.Response(200, json=_payload(NULOS)))
    assert len(llamadas) == 3  # punto + 2 vecinos
    assert perfil.fuente == "fallback_regional"
    # No se probaron los 4 vecinos -> el "sin dato" NO se cachea y queda para reintentar
    assert _en_cache() is None
    assert perfil.reintentar_soilgrids is True


def test_limitador_ventana_deslizante():
    reloj = Reloj()
    lim = LimitadorTasa(max_llamadas=5, ventana_s=60, reloj=reloj)
    assert lim.reservar_hasta(4) == 4
    reloj.t = 30
    assert lim.reservar_hasta(4) == 1
    reloj.t = 60  # vencen las 4 del t=0
    assert lim.reservar_hasta(4) == 4


# ---------- BACK-4: corte automático ----------


def test_timeout_activa_corte_y_no_se_llama_por_5_min(_estado_limpio):
    def timeout(req):
        raise httpx.ReadTimeout("timeout", request=req)

    ok = lambda req: httpx.Response(200, json=_payload(PERGAMINO_RAW))  # noqa: E731

    _run(timeout)
    # Durante el corte: fallback directo sin requests, aunque ISRIC ya respondería
    _estado_limpio.t = 299.0
    perfil, llamadas = _run(ok, (-33.90, -60.57))
    assert llamadas == []
    assert perfil.fuente == "fallback_regional"
    assert perfil.reintentar_soilgrids is True

    # A los 5 min: 1 llamada de prueba; responde -> se reabre
    _estado_limpio.t = 300.0
    perfil, llamadas = _run(ok, (-33.85, -60.57))
    assert len(llamadas) == 1
    assert perfil.fuente == "isric_soilgrids_v2"
    assert not soilgrids._corte.cortado


def test_429_activa_corte():
    _run(lambda req: httpx.Response(429))
    assert soilgrids._corte.cortado


def test_503_no_activa_corte():
    _run(lambda req: httpx.Response(503))
    assert not soilgrids._corte.cortado


def test_prueba_fallida_corta_otros_5_min(_estado_limpio):
    def timeout(req):
        raise httpx.ReadTimeout("timeout", request=req)

    _run(timeout)
    _estado_limpio.t = 300.0
    _, llamadas = _run(timeout, (-33.90, -60.57))
    assert len(llamadas) == 1  # la llamada de prueba
    _estado_limpio.t = 599.0
    _, llamadas = _run(timeout, (-33.85, -60.57))
    assert llamadas == []  # sigue cortado hasta t=600
    _estado_limpio.t = 600.0
    _, llamadas = _run(timeout, (-33.80, -60.57))
    assert len(llamadas) == 1


def test_corte_permite_una_sola_prueba():
    reloj = Reloj()
    corte = CorteAutomatico(duracion_s=300, reloj=reloj)
    corte.registrar_falla()
    assert not corte.permite_llamada()
    reloj.t = 300
    assert corte.permite_llamada()
    assert not corte.permite_llamada()  # segunda llamada mientras la prueba está en curso
    corte.registrar_exito()
    assert corte.permite_llamada() and corte.permite_llamada()


# ---------- BACK-4: marca de reintento y caché en capas ----------


def test_fallback_transitorio_marcado_y_fuera_de_todas_las_capas():
    perfil, _ = _run(lambda req: httpx.Response(503))
    assert perfil.reintentar_soilgrids is True
    assert _en_cache() is None
    assert _en_secundaria() is None


def test_sin_dato_deterministico_no_se_marca_y_se_cachea():
    perfil, _ = _run(lambda req: httpx.Response(200, json=_payload(NULOS)))
    assert perfil.reintentar_soilgrids is False
    assert _en_secundaria() == {"sin_dato": True}


def test_dato_real_llega_a_la_capa_secundaria():
    perfil, _ = _run(lambda req: httpx.Response(200, json=_payload(PERGAMINO_RAW)))
    assert perfil.reintentar_soilgrids is False
    assert _en_secundaria() == perfil_a_dict(perfil)


def test_dato_desde_secundaria_sin_request():
    from providers.cache import obtener_cache

    perfil, _ = _run(lambda req: httpx.Response(200, json=_payload(PERGAMINO_RAW)))
    obtener_cache().primaria.limpiar()  # simula reinicio del servidor: memoria vacía, Supabase no
    perfil2, llamadas = _run(lambda req: httpx.Response(500))
    assert llamadas == []
    assert perfil2 == perfil


# ---------- BACK-4: lotes de ejemplo ----------


def test_lote_ejemplo_a_menos_de_100m_sin_request():
    perfil_real, _ = _run(lambda req: httpx.Response(200, json=_payload(PERGAMINO_RAW)))
    soilgrids.reiniciar_estado(
        lotes_ejemplo=[{"nombre": "Pergamino", "lat": -33.95, "lon": -60.57, "perfil": perfil_a_dict(perfil_real)}]
    )
    perfil, llamadas = _run(lambda req: httpx.Response(500), (-33.9505, -60.5705))  # ~70 m
    assert llamadas == []
    assert perfil.fuente == "precache"
    assert perfil.textura_predominante == "franco_limoso"
    assert perfil.distancia_fuente_km < 0.1


def test_lote_ejemplo_a_mas_de_100m_no_aplica():
    soilgrids.reiniciar_estado(
        lotes_ejemplo=[
            {
                "nombre": "Pergamino",
                "lat": -33.95,
                "lon": -60.57,
                "perfil": perfil_a_dict(
                    PerfilSueloSatelital(23.4, 14.2, 62.4, 17.9, 6.4, "franco_limoso", "isric_soilgrids_v2", 0.0, None, ())
                ),
            }
        ]
    )
    perfil, llamadas = _run(lambda req: httpx.Response(200, json=_payload(PERGAMINO_RAW)), (-33.952, -60.57))  # ~220 m
    assert len(llamadas) == 1
    assert perfil.fuente == "isric_soilgrids_v2"


# ---------- validación ----------


@pytest.mark.parametrize("lat,lon", [(-91, 0), (91, 0), (0, -181), (0, 181)])
def test_coordenadas_invalidas(lat, lon):
    with pytest.raises(ValueError):
        asyncio.run(fetch_perfil_suelo(lat, lon))


# ---------- BACK-19: grilla de suelo ISRIC (respaldo antes de GeoINTA) ----------

from providers.soilgrids import ADV_GRILLA, _armar_perfil, registrar_grilla  # noqa: E402

NORTE_SANTA_FE = (-29.0, -60.0)  # sin localidad GeoINTA a 100 km


def _entrada_grilla(lat, lon, raw=PERGAMINO_RAW, fuente="isric_soilgrids_v2"):
    perfil = _armar_perfil(_parsear(_payload(raw)), fuente, 0.0)
    return {clave_coordenada(lat, lon): {"lat": lat, "lon": lon, "perfil": perfil_a_dict(perfil)}}


def _timeout(req):
    raise httpx.ReadTimeout("timeout", request=req)


def test_grilla_por_timeout_perfil_completo_y_no_se_cachea():
    registrar_grilla(_entrada_grilla(-29.2, -60.3))
    perfil, llamadas = _run(_timeout, NORTE_SANTA_FE)
    assert len(llamadas) == 1
    assert perfil.fuente == "grilla_isric"
    assert perfil.textura_predominante == "franco_limoso" and perfil.carbono_organico_g_kg is not None
    assert perfil.distancia_fuente_km == pytest.approx(36.3, abs=1.0)
    assert perfil.advertencias[0] == ADV_GRILLA.format(distancia=perfil.distancia_fuente_km)
    assert perfil.reintentar_soilgrids is True
    assert _en_cache(NORTE_SANTA_FE) is None and _en_secundaria(NORTE_SANTA_FE) is None


def test_grilla_con_corte_activo_sin_request():
    registrar_grilla(_entrada_grilla(-29.2, -60.3))
    _run(_timeout, NORTE_SANTA_FE)  # abre el corte
    perfil, llamadas = _run(lambda req: httpx.Response(200, json=_payload(PERGAMINO_RAW)), NORTE_SANTA_FE)
    assert llamadas == []
    assert perfil.fuente == "grilla_isric"


def test_grilla_tiene_prioridad_sobre_geointa():
    registrar_grilla(_entrada_grilla(-34.3, -60.9))  # ~50 km; GeoINTA Pergamino está a ~7 km
    perfil, _ = _run(lambda req: httpx.Response(503))
    assert perfil.fuente == "grilla_isric"
    assert perfil.localidad_fallback is None


def test_sin_grilla_cerca_cae_a_geointa():
    registrar_grilla(_entrada_grilla(-38.0, -58.0))  # Balcarce: a más de 120 km de Pergamino
    perfil, _ = _run(lambda req: httpx.Response(503))
    assert perfil.fuente == "fallback_regional"


def test_sin_grilla_ni_geointa_lanza_unavailable():
    registrar_grilla(_entrada_grilla(-33.95, -60.57))
    with pytest.raises(SoilGridsUnavailable):
        _run(lambda req: httpx.Response(503), NORTE_SANTA_FE)


def test_grilla_radio_120km():
    registrar_grilla(_entrada_grilla(-30.0, -60.0))  # ~111 km al norte del punto pedido
    perfil, _ = _run(_timeout, NORTE_SANTA_FE)
    assert perfil.fuente == "grilla_isric"


def test_grilla_en_pixel_sin_dato_no_se_marca_para_reintentar():
    registrar_grilla(_entrada_grilla(-29.2, -60.3))
    perfil, llamadas = _run(lambda req: httpx.Response(200, json=_payload(NULOS)), NORTE_SANTA_FE)
    assert len(llamadas) == 5
    assert perfil.fuente == "grilla_isric"
    assert perfil.reintentar_soilgrids is False


def test_grilla_reemplaza_advertencia_de_vecino_y_conserva_las_propias():
    raw = dict(PERGAMINO_RAW, soc=(None, None, None))
    registrar_grilla(_entrada_grilla(-29.2, -60.3, raw, fuente="isric_soilgrids_v2_vecino"))
    perfil, _ = _run(_timeout, NORTE_SANTA_FE)
    assert ADV_VECINO not in perfil.advertencias
    assert ADV_SIN_SOC in perfil.advertencias


def test_registrar_grilla_descarta_entradas_mal_formadas():
    entradas = {**_entrada_grilla(-29.2, -60.3), "rota": {"lat": -30}, "otra": "texto"}
    assert registrar_grilla(entradas) == 1


def test_puntos_grilla_dentro_de_las_provincias():
    from providers.generar_precache import puntos_grilla
    from providers.regional import haversine_km

    puntos = puntos_grilla()
    assert 75 <= len(puntos) <= 95
    assert all(-41.5 < la < -27.5 and -68.5 < lo < -56.5 for la, lo in puntos)
    assert min(haversine_km(*NORTE_SANTA_FE, la, lo) for la, lo in puntos) < 71


# ---------- BACK-27: modo segundo plano (cola de reintentos) ----------


def _run_fondo(handler, lat_lon=PERGAMINO):
    llamadas = []

    def wrapped(req):
        llamadas.append(req)
        return handler(req)

    async def _go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(wrapped)) as client:
            return await fetch_perfil_suelo(*lat_lon, client=client, segundo_plano=True)

    return asyncio.run(_go()), llamadas


def _timeout_live(req):
    raise httpx.ReadTimeout("timeout", request=req)


def test_segundo_plano_consulta_aunque_el_corte_este_activo():
    _run(_timeout_live)  # el tráfico en vivo abre el corte
    perfil, llamadas = _run_fondo(lambda req: httpx.Response(200, json=_payload(PERGAMINO_RAW)))
    assert perfil.fuente == "isric_soilgrids_v2" and len(llamadas) == 1
    # el éxito en segundo plano no cierra el corte: el tráfico en vivo sigue sin llamar
    perfil_vivo, llamadas_vivo = _run(lambda req: httpx.Response(200, json=_payload(PERGAMINO_RAW)), (-34.5, -60.9))
    assert llamadas_vivo == [] and perfil_vivo.reintentar_soilgrids is True


def test_segundo_plano_timeout_no_abre_el_corte_y_usa_timeout_largo():
    timeouts = []

    def handler(req):
        timeouts.append(req.extensions["timeout"]["read"])
        raise httpx.ReadTimeout("timeout", request=req)

    perfil, _ = _run_fondo(handler)
    assert perfil.reintentar_soilgrids is True
    assert timeouts == [soilgrids.TIMEOUT_SEGUNDO_PLANO_S]
    _, llamadas_vivo = _run(lambda req: httpx.Response(200, json=_payload(PERGAMINO_RAW)), (-34.5, -60.9))
    assert len(llamadas_vivo) == 1  # el corte sigue cerrado


def test_segundo_plano_sin_cupo_espera_y_despues_consulta(_estado_limpio, monkeypatch):
    reloj = _estado_limpio
    esperas = []

    async def dormir(s):
        esperas.append(s)
        reloj.t += s

    monkeypatch.setattr(soilgrids, "_dormir", dormir)
    assert soilgrids._limitador.reservar_hasta(5) == 5  # cupo agotado por el tráfico en vivo
    perfil, llamadas = _run_fondo(lambda req: httpx.Response(200, json=_payload(PERGAMINO_RAW)))
    assert perfil.fuente == "isric_soilgrids_v2" and len(llamadas) == 1
    assert sum(esperas) >= 60  # esperó a que se liberara la ventana de 60 s


def test_segundo_plano_vecinos_de_a_uno():
    def handler(req):
        es_punto = (float(req.url.params["lat"]), float(req.url.params["lon"])) == PERGAMINO
        return httpx.Response(200, json=_payload(NULOS if es_punto else PERGAMINO_RAW))

    perfil, llamadas = _run_fondo(handler)
    assert perfil.fuente == "isric_soilgrids_v2_vecino"
    assert len(llamadas) == 2  # el punto y el primer vecino con dato
