"""Tests de BACK-7: ``POST /api/v1/simulate`` (sin red)."""

from __future__ import annotations

import time
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from main import app
from providers.features import FEATURES_FUTURAS, InsumosML, construir_insumos_ml
from providers.nasa_power import NasaPowerUnavailable
from providers.soilgrids import PerfilSueloSatelital, SoilGridsUnavailable
from providers.srtm import SrtmUnavailable, TopografiaSrtm
from providers.test_features import HOY, _estado_limpio, _handler  # noqa: F401 (fixture autouse)
from routers.simulate import get_constructor_insumos
from schemas import CULTIVO_ANTERIOR_NEUTRO, CULTIVOS_VALIDOS, SimulateResponse, TelemetriaNasa
from services.rotation_matrix import ALL_CROPS, NEUTRAL_PREVIOUS_VALUES

CALOR = [1, 3, 5, 6, 8, 10, 12, 14, 16, 18, 21, 23, 25, 28, 31, 34, 38, 41, 45]
ESCENARIOS = [
    {
        "anio": 2006 + i,
        "frecuencia_tormentas_extremas": i % 3,
        "frecuencia_estres_termico": c,
        "frecuencia_riesgo_helada": 0,
    }
    for i, c in enumerate(CALOR)
]
TELEMETRIA = TelemetriaNasa(
    fecha_ultimo_dato_valido=date(2026, 11, 11),
    indice_humedad_radicular_pct=46.0,
    indice_humedad_superficial_pct=35.0,
    tendencia_humedad_15d_pct=-4.4,
    anomalia_lluvia_90d_pct=-37.38,
    frecuencia_tormentas_extremas_90d=3,
    riesgo_termico_verano="alto",
)
ADV_SUELO = "Suelo tomado de un píxel vecino."
PERFIL = PerfilSueloSatelital(
    arcilla_pct=23.4,
    arena_pct=14.2,
    limo_pct=62.4,
    carbono_organico_g_kg=17.9,
    ph=6.4,
    textura_predominante="franco_limoso",
    fuente="isric_soilgrids_v2_vecino",
    distancia_fuente_km=0.25,
    localidad_fallback=None,
    advertencias=(ADV_SUELO,),
)
TOPO = TopografiaSrtm(
    elevacion_m=69.04,
    pendiente_terreno_pct=9.3,  # por encima del tope del modelo (8.2): la respuesta muestra el real
    fuente="opentopodata_srtm30m",
    fuente_elevacion="srtm30m",
    distancia_fuente_km=0.0,
    localidad_fallback=None,
    advertencias=(ADV_SUELO,),  # duplicada a propósito
)
FEATURES = {
    "gwetroot_saturacion_pct": 46.0,
    "gwettop_saturacion_pct": 35.0,
    "tendencia_humedad_15d_pct": -4.4,
    "anomalia_lluvia_90d_pct": -37.38,
    "indice_aridez_evaporativa": 0.752,
    "pendiente_terreno_pct": 8.2,
    "elevacion_m": 69.0,
    "textura_arcilla_pct": 23.4,
}
BODY = {
    "coordenadas": {"lat": -33.95, "lon": -60.57},
    "campana": "verano",
    "cultivo_anterior": "soja_primera",
    "objetivo_productor": "equilibrio",
}


def _insumos(escenarios=ESCENARIOS) -> InsumosML:
    return InsumosML(
        features_actuales=dict(FEATURES),
        escenarios_historicos=list(escenarios),
        fecha_corte=TELEMETRIA.fecha_ultimo_dato_valido,
        telemetria=TELEMETRIA,
        perfil_suelo=PERFIL,
        topografia=TOPO,
        advertencias=PERFIL.advertencias + TOPO.advertencias,
    )


@pytest.fixture
def cliente():
    llamadas: list[tuple[float, float]] = []
    estado = {"insumos": _insumos(), "error": None}

    async def falso(lat, lon, **_kw):
        llamadas.append((lat, lon))
        if estado["error"] is not None:
            raise estado["error"]
        return estado["insumos"]

    app.dependency_overrides[get_constructor_insumos] = lambda: falso
    with TestClient(app) as c:
        c.llamadas = llamadas
        c.estado = estado
        yield c
    app.dependency_overrides.clear()


def test_paridad_cultivos_con_rotation_matrix():
    assert set(CULTIVOS_VALIDOS) == set(ALL_CROPS)
    assert set(CULTIVO_ANTERIOR_NEUTRO) <= NEUTRAL_PREVIOUS_VALUES


def test_simulate_contrato_completo_con_ensemble(cliente):
    r = cliente.post("/api/v1/simulate", json=BODY)
    assert r.status_code == 200, r.text
    data = r.json()
    SimulateResponse.model_validate(data)
    assert cliente.llamadas == [(-33.95, -60.57)]

    dist = data["recomendacion_principal"]["distribucion_hidroclimatica"]
    assert dist["anios_evaluados"] == len(ESCENARIOS)
    assert dist["umbral_desfavorable"] == 50.0
    assert dist["p10"] <= dist["promedio"] <= dist["p90"]
    for item in data["ranking_cultivos"]:
        assert item["anios_evaluados"] == len(ESCENARIOS)
        assert item["score_hidroclimatico_p10"] is not None
    assert {i["cultivo"] for i in data["ranking_cultivos"]} == {
        "maiz_temprano", "maiz_tardio", "soja_primera", "soja_segunda", "girasol", "sorgo"
    }
    assert "años análogos" in data["recomendacion_principal"]["explicacion"]


def test_bloques_descriptivos_muestran_dato_real(cliente):
    data = cliente.post("/api/v1/simulate", json=BODY).json()
    assert data["telemetria_nasa"] == TELEMETRIA.model_dump(mode="json")
    assert data["topografia_srtm"]["pendiente_terreno_pct"] == 9.3
    assert data["topografia_srtm"]["elevacion_m"] == 69.0
    assert data["perfil_suelo"]["textura_predominante"] == "franco_limoso"
    assert data["perfil_suelo"]["arcilla_pct"] == 23.4
    assert data["perfil_suelo"]["carbono_organico_g_kg"] == 17.9
    assert data["advertencias"] == [ADV_SUELO]
    assert data["ubicacion"] == {"lat": -33.95, "lon": -60.57}


def test_what_if_cambia_scores_pero_no_la_telemetria(cliente):
    base = cliente.post("/api/v1/simulate", json=BODY).json()
    seco = cliente.post(
        "/api/v1/simulate",
        json={**BODY, "simulacion_what_if": {"override_humedad_radicular_pct": 10, "variacion_lluvia_esperada_pct": -50}},
    ).json()
    assert seco["telemetria_nasa"] == base["telemetria_nasa"]
    prom = lambda d: d["recomendacion_principal"]["sub_scores"]["hidroclimatico"]  # noqa: E731
    finales = lambda d: {i["cultivo"]: i["score_final"] for i in d["ranking_cultivos"]}  # noqa: E731
    assert finales(seco) != finales(base) or prom(seco) != prom(base)


def test_campana_invierno(cliente):
    data = cliente.post("/api/v1/simulate", json={**BODY, "campana": "invierno", "cultivo_anterior": "maiz_tardio"}).json()
    assert {i["cultivo"] for i in data["ranking_cultivos"]} == {
        "trigo", "cebada", "vicia_cobertura", "avena_cobertura", "camelina"
    }


@pytest.mark.parametrize("valor", [None, "barbecho", "  Soja_Primera "])
def test_cultivo_anterior_aceptados(cliente, valor):
    assert cliente.post("/api/v1/simulate", json={**BODY, "cultivo_anterior": valor}).status_code == 200


@pytest.mark.parametrize(
    "cambio",
    [
        {"campana": "otono"},
        {"cultivo_anterior": "soja"},
        {"objetivo_productor": "maximo_rinde"},
        {"coordenadas": {"lat": -95, "lon": -60.57}},
        {"simulacion_what_if": {"variacion_lluvia_esperada_pct": 80}},
        {"simulacion_what_if": {"override_humedad_radicular_pct": 120}},
        {"campo_extra": 1},
    ],
)
def test_validaciones_422(cliente, cambio):
    r = cliente.post("/api/v1/simulate", json={**BODY, **cambio})
    assert r.status_code == 422
    assert cliente.llamadas == []


@pytest.mark.parametrize(
    "error", [NasaPowerUnavailable("NASA caída"), SoilGridsUnavailable("ISRIC caído"), SrtmUnavailable("SRTM caído")]
)
def test_provider_caido_503(cliente, error):
    cliente.estado["error"] = error
    r = cliente.post("/api/v1/simulate", json=BODY)
    assert r.status_code == 503
    assert str(error) in r.json()["detail"]


def test_sin_escenarios_503(cliente):
    cliente.estado["insumos"] = _insumos(escenarios=[])
    r = cliente.post("/api/v1/simulate", json=BODY)
    assert r.status_code == 503


def test_latencia_post_insumos(cliente):
    cliente.post("/api/v1/simulate", json=BODY)  # calentamiento
    tiempos = []
    for _ in range(15):
        t0 = time.perf_counter()
        assert cliente.post("/api/v1/simulate", json=BODY).status_code == 200
        tiempos.append(time.perf_counter() - t0)
    tiempos.sort()
    assert tiempos[int(0.95 * (len(tiempos) - 1))] < 0.25


def test_health():
    with TestClient(app) as c:
        assert c.get("/health").json() == {"status": "ok"}


def test_punta_a_punta_con_providers_mockeados():
    """Providers reales (BACK-6) con HTTP mockeado → ensemble ML → contrato §5."""
    registro: list[str] = []

    async def construir(lat, lon, **_kw):
        async with httpx.AsyncClient(transport=httpx.MockTransport(_handler(registro))) as client:
            return await construir_insumos_ml(lat, lon, client=client, today=HOY)

    app.dependency_overrides[get_constructor_insumos] = lambda: construir
    try:
        with TestClient(app) as c:
            r = c.post("/api/v1/simulate", json=BODY)
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    data = r.json()
    SimulateResponse.model_validate(data)
    assert {"nasa_reciente", "nasa_hist", "suelo", "srtm"} <= set(registro)
    dist = data["recomendacion_principal"]["distribucion_hidroclimatica"]
    assert dist["anios_evaluados"] in (19, 20)
    assert set(FEATURES_FUTURAS) <= set(dist["peor_escenario"])
