"""Tests de BACK-31: ``GET /api/v1/historial`` y su agregado por campaña agrícola (sin red)."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from main import app
from ml.rinde import rinde_zona_por_campana
from providers.nasa_power import NasaPowerDailySeries, NasaPowerUnavailable
from routers.historial import get_historial_store, get_hoy
from schemas import HistorialResponse
from services import historial_service as hs

HOY = date(2008, 11, 15)  # campañas 2006/07 y 2007/08 completas; 2008/09 en curso


def _meses(lluvia_por_mes: float = 75.0) -> hs.Mensual:
    """Jul-2006 → Oct-2008 con 75 mm y 65% de agua por mes; enero de 2008 seco; noviembre 2008 parcial."""
    meses: hs.Mensual = {}
    for anio in (2006, 2007, 2008):
        for mes in range(1, 13):
            if (anio, mes) < (2006, 7) or (anio, mes) > (2008, 11):
                continue
            agua = 0.40 if (anio, mes) == (2008, 1) else 0.65
            meses[(anio, mes)] = {"lluvia_mm": lluvia_por_mes, "lluvia_completa": True, "agua_raices": agua}
    meses[(2008, 11)] = {"lluvia_mm": 10.0, "lluvia_completa": False, "agua_raices": None}
    # Campaña en curso más seca: julio a octubre de 2008 con la mitad de la lluvia.
    for mes in (7, 8, 9, 10):
        meses[(2008, mes)]["lluvia_mm"] = lluvia_por_mes / 2
    return meses


def test_campanas_completas_normales_y_mes_mas_seco():
    filas, normales = hs.campanas_desde_mensual(_meses(), HOY)
    por_anio = {f["anio"]: f for f in filas}
    assert [f["etiqueta"] for f in filas] == ["2006/07", "2007/08", "2008/09"]
    assert por_anio[2006]["completa"] and por_anio[2007]["completa"] and not por_anio[2008]["completa"]
    assert por_anio[2006]["lluvia_mm"] == 900
    assert normales == {"lluvia_mm": 900, "agua_raices_pct": 64, "campanas_completas": 2}
    assert por_anio[2007]["mes_mas_seco"] == "2008-01"
    assert por_anio[2007]["agua_raices_mes_mas_seco_pct"] == 40
    assert por_anio[2006]["lluvia_vs_normal_pct"] == 0


def test_campana_en_curso_se_compara_con_los_mismos_meses():
    filas, _ = hs.campanas_desde_mensual(_meses(), HOY)
    actual = filas[-1]
    assert actual["lluvia_comparada_hasta"] == "2008-10"
    assert actual["lluvia_vs_normal_pct"] == -50
    assert actual["meses_con_dato"] == 4  # noviembre parcial no cuenta como completo


def test_agregar_diario_suma_lluvia_y_promedia_agua():
    dias = [date(2026, 1, d) for d in range(1, 32)]
    serie = NasaPowerDailySeries(
        lat=-37.0, lon=-59.0, start=dias[0], end=dias[-1],
        series={"PRECTOTCORR": {d: 2.0 for d in dias}, "GWETROOT": {d: 0.5 for d in dias[:9]}},
    )
    mes = hs.agregar_diario(serie)[(2026, 1)]
    assert mes["lluvia_mm"] == 62.0 and mes["lluvia_completa"]
    assert mes["agua_raices"] is None  # solo 9 días con dato: no alcanza para promediar


def test_mes_en_curso_no_cuenta_como_completo():
    dias = [date(2026, 11, d) for d in range(1, 16)]  # 15 de 30 días de noviembre
    serie = NasaPowerDailySeries(
        lat=-37.0, lon=-59.0, start=dias[0], end=dias[-1],
        series={"PRECTOTCORR": {d: 1.0 for d in dias}, "GWETROOT": {d: 0.5 for d in dias}},
    )
    mes = hs.agregar_diario(serie)[(2026, 11)]
    assert mes["lluvia_mm"] == 15.0 and not mes["lluvia_completa"]
    assert mes["agua_raices"] == 0.5  # 15 días alcanzan para promediar el agua del mes en curso


def test_cosechas_por_campana_agricola():
    campanas = [
        {"id": "a", "cultivo": "trigo", "fecha_inicio": "2026-06-10", "fecha_fin": "2026-12-05", "rinde_kg_ha": 4200},
        {"id": "b", "cultivo": "soja_segunda", "fecha_inicio": "2027-01-05", "fecha_fin": None, "rinde_kg_ha": None},
        {"id": "c", "cultivo": "soja_primera", "fecha_inicio": "2025-11-13", "fecha_fin": "2026-04-20", "rinde_kg_ha": 3100},
    ]
    por = hs.cosechas_por_campana(campanas)
    assert [c["cultivo"] for c in por[2026]] == ["trigo", "soja_segunda"]  # doble cultivo 2026/27
    assert por[2026][1]["en_curso"] is True
    assert [c["cultivo"] for c in por[2025]] == ["soja_primera"]


def test_rinde_zona_sequia_2008_en_pergamino():
    zona = rinde_zona_por_campana("06623")
    soja = next(r for r in zona[2008] if r["cultivo"] == "soja_primera")
    assert soja["vs_normal_pct"] is not None and soja["vs_normal_pct"] < -20
    assert soja["normal_kg_ha"] % 50 == 0


@pytest.fixture
def cliente(monkeypatch):
    async def mensual_falso(lat, lon, hoy, client):
        return _meses()

    class Store:
        def get_field(self, field_id, token):
            return {"id": str(field_id), "lat": -33.95, "lon": -60.57, "departamento_codigo": "06623"}

        def list_campaigns(self, field_id, token):
            return [{"id": "x", "cultivo": "soja_primera", "fecha_inicio": "2007-11-10", "fecha_fin": "2008-04-20", "rinde_kg_ha": 3000}]

    monkeypatch.setattr(hs, "obtener_mensual", mensual_falso)
    app.dependency_overrides[get_historial_store] = lambda: Store()
    app.dependency_overrides[get_hoy] = lambda: HOY
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_endpoint_con_campo_y_sesion(cliente):
    r = cliente.get(
        "/api/v1/historial",
        params={"lat": -33.95, "lon": -60.57, "field_id": "11111111-1111-1111-1111-111111111111"},
        headers={"Authorization": "Bearer jwt"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    HistorialResponse.model_validate(data)
    assert data["departamento_referencia"]["nombre"] == "Pergamino"
    c2007 = next(c for c in data["campanas"] if c["anio"] == 2007)
    assert c2007["cosechas_lote"][0]["rinde_kg_ha"] == 3000
    assert any(r["cultivo"] == "soja_primera" for r in c2007["rinde_zona"])


def test_endpoint_sin_sesion_avisa_que_faltan_las_cosechas(cliente):
    data = cliente.get("/api/v1/historial", params={"lat": -33.95, "lon": -60.57}).json()
    assert all(c["cosechas_lote"] == [] for c in data["campanas"])
    assert any("guardá el lote" in a for a in data["advertencias"])


def test_nasa_caida_503(cliente, monkeypatch):
    async def caida(*_a, **_k):
        raise NasaPowerUnavailable("timeout")

    monkeypatch.setattr(hs, "obtener_mensual", caida)
    r = cliente.get("/api/v1/historial", params={"lat": -33.95, "lon": -60.57})
    assert r.status_code == 503 and r.json()["fuente"] == "nasa_power"
