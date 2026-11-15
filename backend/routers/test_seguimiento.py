"""Tests de BACK-29: ``GET /api/v1/fields/{field_id}/campaigns/{campaign_id}/seguimiento`` (sin red)."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest
from fastapi.testclient import TestClient

from main import app
from ml.escenarios import inicio_periodo_critico_real
from providers.features import codificar_lluvia
from providers.nasa_power import NasaPowerUnavailable
from routers.campaigns import (
    AuthenticatedUser,
    get_campaign_store,
    get_constructor_seguimiento,
    get_current_user,
    get_hoy,
)
from schemas import SeguimientoResponse
from services.seguimiento_service import ADVERTENCIAS_FIJAS, InsumosSeguimiento, calendarios_observados

FIELD_ID = "11111111-1111-1111-1111-111111111111"
CAMPAIGN_ID = "33333333-3333-3333-3333-333333333333"
SIEMBRA = date(2026, 11, 10)
INICIO = inicio_periodo_critico_real("soja_primera", SIEMBRA)
URL = f"/api/v1/fields/{FIELD_ID}/campaigns/{CAMPAIGN_ID}/seguimiento"

CAMPO = {"id": FIELD_ID, "lat": -33.95, "lon": -60.57, "departamento_codigo": None}
FEATURES = {
    "gwetroot_saturacion_pct": 46.0, "gwettop_saturacion_pct": 40.0, "tendencia_humedad_15d_pct": -3.0,
    "anomalia_lluvia_90d_pct": -10.0, "indice_aridez_evaporativa": 0.6, "pendiente_terreno_pct": 0.8,
    "elevacion_m": 80.0, "textura_arcilla_pct": 25.0,
}


def _calendarios(calor: float, anios, seed: int):
    rng = np.random.default_rng(seed)
    ev, ll = {}, {}
    for a in anios:
        n = 366 if a % 4 == 0 else 365
        ev[a] = "".join(rng.choice(["0", "2"], p=[1 - calor, calor]) for _ in range(n))
        ll[a] = "".join(codificar_lluvia(float(x)) for x in rng.gamma(0.6, 5.0, n))
    return ev, ll


HIST_EV, HIST_LL = _calendarios(0.10, range(1981, 2026), seed=1)
OBS_EV, OBS_LL = _calendarios(0.40, (2026, 2027), seed=2)


def _insumos(ultimo: date) -> InsumosSeguimiento:
    return InsumosSeguimiento(
        features_siembra=dict(FEATURES),
        calendario_eventos=HIST_EV,
        calendario_lluvia=HIST_LL,
        observado_eventos={**HIST_EV, **OBS_EV},
        observado_lluvia={**HIST_LL, **OBS_LL},
        ultimo_dato=ultimo,
        oni_siembra=0.1,
    )


class _StoreFalso:
    def __init__(self, campana):
        self.campana = campana
        self.guardado = None

    def get_field(self, field_id, token):
        return dict(CAMPO) if str(field_id) == FIELD_ID else None

    def get_campaign(self, field_id, campaign_id, token):
        return dict(self.campana) if str(campaign_id) == CAMPAIGN_ID else None

    def save_simulacion_json(self, campaign_id, token, simulacion_json):
        self.guardado = simulacion_json
        self.campana["simulacion_json"] = simulacion_json


def _campana(**cambios):
    c = {"id": CAMPAIGN_ID, "field_id": FIELD_ID, "campana": "verano", "cultivo": "soja_primera",
         "fecha_inicio": SIEMBRA.isoformat(), "fecha_fin": None, "simulacion_json": None}
    c.update(cambios)
    return c


@pytest.fixture
def cliente():
    estado = {"hoy": INICIO + timedelta(days=40), "ultimo": INICIO + timedelta(days=35), "error": None, "llamadas": 0}
    store = _StoreFalso(_campana())

    async def construir(lat, lon, fecha_siembra, *, today, **kw):
        estado["llamadas"] += 1
        if estado["error"] is not None:
            raise estado["error"]
        return _insumos(estado["ultimo"])

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id="u1", email="test@ereia.ag", nombre="Test", access_token="jwt"
    )
    app.dependency_overrides[get_campaign_store] = lambda: store
    app.dependency_overrides[get_constructor_seguimiento] = lambda: construir
    app.dependency_overrides[get_hoy] = lambda: estado["hoy"]
    with TestClient(app) as c:
        c.estado = estado
        c.store = store
        yield c
    app.dependency_overrides.clear()


def test_en_curso_contrato_y_guardado(cliente):
    r = cliente.get(URL)
    assert r.status_code == 200, r.text
    data = r.json()
    SeguimientoResponse.model_validate(data)
    assert data["etapa"] == "en_curso"
    assert data["dias_observados"] == 36
    assert data["serie"][0]["dias_observados"] == 0
    assert data["serie"][-1]["dias_observados"] == 36
    assert data["observado"]["dias"] == 36
    assert data["departamento_referencia"]["nombre"] == "Pergamino"
    assert data["serie"][-1]["rinde_kg_ha"]["normal"] is not None
    for adv in ADVERTENCIAS_FIJAS:
        assert adv in data["advertencias"]
    assert cliente.store.guardado["seguimiento"]["etapa"] == "en_curso"


def test_reutiliza_lo_calculado_el_mismo_dia(cliente):
    primero = cliente.get(URL).json()
    segundo = cliente.get(URL).json()
    assert cliente.estado["llamadas"] == 1
    assert segundo == primero
    cliente.estado["hoy"] += timedelta(days=1)
    cliente.get(URL)
    assert cliente.estado["llamadas"] == 2


def test_etapas_previa_y_terminado(cliente):
    cliente.estado["ultimo"] = INICIO - timedelta(days=3)
    previa = cliente.get(URL).json()
    assert previa["etapa"] == "previa" and len(previa["serie"]) == 1 and previa["observado"] is None
    cliente.store.campana["simulacion_json"] = None
    cliente.estado["ultimo"] = INICIO + timedelta(days=120)
    fin = cliente.get(URL).json()
    assert fin["etapa"] == "terminado" and fin["dias_observados"] == 90


@pytest.mark.parametrize(
    "cambio, mensaje",
    [
        ({"cultivo": "vicia_cobertura"}, "cultivos de servicio"),
        ({"fecha_inicio": "2027-06-01"}, "todavía no ocurrió"),
    ],
)
def test_validaciones_422(cliente, cambio, mensaje):
    cliente.store.campana = _campana(**cambio)
    r = cliente.get(URL)
    assert r.status_code == 422
    assert mensaje in r.json()["detail"]


def test_campana_ajena_404(cliente):
    r = cliente.get(f"/api/v1/fields/{FIELD_ID}/campaigns/44444444-4444-4444-4444-444444444444/seguimiento")
    assert r.status_code == 404


def test_nasa_caida_503(cliente):
    cliente.estado["error"] = NasaPowerUnavailable("timeout")
    r = cliente.get(URL)
    assert r.status_code == 503
    assert r.json()["fuente"] == "nasa_power"


def test_calendarios_observados_indexan_desde_el_1_de_enero():
    """La serie de la campaña arranca el 1/1: el índice de cada día coincide con el del histórico."""
    from providers.nasa_power import NasaPowerDailySeries

    desde, hasta = date(2026, 1, 1), date(2026, 12, 31)
    fechas = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]
    serie = NasaPowerDailySeries(
        lat=-33.95, lon=-60.57, start=desde, end=hasta,
        series={
            "PRECTOTCORR": {d: (60.0 if d == date(2026, 11, 20) else 1.0) for d in fechas},
            "T2M_MAX": {d: 30.0 for d in fechas},
            "T2M_MIN": {d: 10.0 for d in fechas},
        },
        elevacion_m=80.0,
    )
    ev, _ = calendarios_observados(serie, hasta)
    assert ev[2026][(date(2026, 11, 20) - desde).days] == "1"  # tormenta ese día exacto
