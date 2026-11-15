"""Tests de BACK-24: política del servicio único de datos del lote (sin red)."""

from __future__ import annotations

import asyncio
from datetime import date

import pytest

from providers.nasa_power import NasaPowerUnavailable
from providers.nasa_telemetry import ReferenciaHistorica
from providers.soilgrids import PerfilSueloSatelital, SoilGridsUnavailable
from providers.srtm import SrtmUnavailable, TopografiaSrtm
from routers.test_telemetry import _serie_reciente
from services import datos_lote
from services.field_enrichment_service import suelo_a_columnas_field, topografia_a_columnas_field

HOY = date(2026, 11, 15)
REF = ReferenciaHistorica(clim_por_doy={d: 200.0 for d in range(1, 367)}, dias_calor_verano_promedio=30.0)
PERFIL_REAL = PerfilSueloSatelital(
    arcilla_pct=23.4, arena_pct=14.2, limo_pct=62.4, carbono_organico_g_kg=17.9, ph=6.4,
    textura_predominante="franco_limoso", fuente="isric_soilgrids_v2", distancia_fuente_km=0.0,
    localidad_fallback=None, advertencias=(),
)
ADV_GRILLA = "Perfil de suelo de ISRIC tomado de un punto de referencia a 46 km."
PERFIL_GRILLA = PerfilSueloSatelital(
    arcilla_pct=29.0, arena_pct=20.0, limo_pct=51.0, carbono_organico_g_kg=12.8, ph=6.1,
    textura_predominante="franco_arcilloso", fuente="grilla_isric", distancia_fuente_km=46.0,
    localidad_fallback=None, advertencias=(ADV_GRILLA,), reintentar_soilgrids=True,
)
TOPO_REAL = TopografiaSrtm(
    elevacion_m=69.0, pendiente_terreno_pct=0.82, fuente="opentopodata_srtm30m", fuente_elevacion="srtm30m",
    distancia_fuente_km=0.0, localidad_fallback=None, advertencias=(),
)


def _campo(perfil=None, topo=None, **extra):
    fila = {"id": "f1", "lat": -33.95, "lon": -60.57}
    if perfil is not None:
        fila.update(suelo_a_columnas_field(perfil))
    if topo is not None:
        fila.update(topografia_a_columnas_field(topo))
    fila.update(extra)
    return fila


@pytest.fixture
def providers(monkeypatch):
    """Providers falsos; cada test ajusta ``estado`` y lee ``llamadas``."""
    estado = {"suelo": PERFIL_REAL, "topo": TOPO_REAL, "reciente": None, "ref": REF}
    llamadas: list[str] = []

    def _resultado(clave):
        valor = estado[clave]
        if isinstance(valor, BaseException):
            raise valor
        return valor

    async def suelo(*_a, **_k):
        llamadas.append("suelo")
        return _resultado("suelo")

    async def topo(*_a, **_k):
        llamadas.append("topo")
        return _resultado("topo")

    async def reciente(*_a, **_k):
        llamadas.append("reciente")
        if isinstance(estado["reciente"], BaseException):
            raise estado["reciente"]
        return _serie_reciente(0.46, 0.35)

    async def ref(*_a, **_k):
        llamadas.append("ref")
        return _resultado("ref")

    monkeypatch.setattr(datos_lote, "fetch_perfil_suelo", suelo)
    monkeypatch.setattr(datos_lote, "fetch_topografia", topo)
    monkeypatch.setattr(datos_lote, "obtener_ventana_reciente", reciente)
    monkeypatch.setattr(datos_lote, "obtener_referencia_historica", ref)
    return estado, llamadas


def _obtener(**kw):
    return asyncio.run(datos_lote.obtener_datos_lote(-33.95, -60.57, today=HOY, client=object(), **kw))


def test_sin_campo_consulta_todo(providers):
    _, llamadas = providers
    datos = _obtener()
    assert sorted(llamadas) == ["reciente", "ref", "suelo", "topo"]
    assert datos.perfil_suelo == PERFIL_REAL and datos.topografia == TOPO_REAL
    assert not datos.suelo_desde_campo and datos.cambios_campo == {}


def test_campo_con_datos_reales_no_llama_isric_ni_srtm(providers):
    _, llamadas = providers
    guardados = []
    datos = _obtener(campo=_campo(PERFIL_REAL, TOPO_REAL), persistir_campo=guardados.append)
    assert "suelo" not in llamadas and "topo" not in llamadas
    assert datos.suelo_desde_campo and datos.topo_desde_campo
    assert datos.perfil_suelo.arcilla_pct == 23.4 and datos.topografia.pendiente_terreno_pct == 0.82
    assert guardados == []


def test_campo_con_grilla_e_isric_real_usa_y_persiste(providers):
    _, llamadas = providers
    guardados = []
    datos = _obtener(campo=_campo(PERFIL_GRILLA, TOPO_REAL), persistir_campo=guardados.append)
    assert "suelo" in llamadas and "topo" not in llamadas
    assert datos.perfil_suelo == PERFIL_REAL
    assert len(guardados) == 1 and guardados[0]["suelo_fuente"] == "isric_soilgrids_v2"
    assert guardados[0]["reintentar_soilgrids"] is False


def test_campo_con_grilla_e_isric_caido_usa_lo_guardado(providers):
    estado, _ = providers
    estado["suelo"] = SoilGridsUnavailable("caído")
    guardados = []
    datos = _obtener(campo=_campo(PERFIL_GRILLA, TOPO_REAL), persistir_campo=guardados.append)
    assert datos.perfil_suelo.fuente == "grilla_isric"
    assert datos.perfil_suelo.advertencias == (ADV_GRILLA,)
    assert datos.suelo_desde_campo and "suelo" not in datos.errores
    assert guardados == []


def test_campo_vacio_y_provider_caido_marca_no_disponible(providers):
    estado, _ = providers
    estado["topo"] = SrtmUnavailable("caído")
    guardados = []
    datos = _obtener(campo=_campo(PERFIL_REAL), persistir_campo=guardados.append, exigir_todo=False)
    assert datos.topografia is None and isinstance(datos.errores["topo"], SrtmUnavailable)
    assert guardados[0]["topo_fuente"] == "no_disponible"


def test_estricto_lanza_en_orden_de_prioridad(providers):
    estado, _ = providers
    estado["suelo"] = SoilGridsUnavailable("suelo caído")
    estado["topo"] = SrtmUnavailable("srtm caído")
    with pytest.raises(SoilGridsUnavailable):
        _obtener()
    estado["ref"] = NasaPowerUnavailable("histórico caído")
    with pytest.raises(NasaPowerUnavailable, match="NASA POWER no está respondiendo"):
        _obtener()


def test_tolerante_sin_historico_no_lanza(providers):
    estado, _ = providers
    estado["ref"] = NasaPowerUnavailable("timeout")
    datos = _obtener(exigir_todo=False)
    assert datos.referencia is None and datos.reciente is not None
    assert "historico" in datos.errores


def test_persistir_async_y_error_al_persistir_no_rompe(providers):
    guardados = []

    async def persistir_async(cambios):
        guardados.append(cambios)

    _obtener(campo=_campo(PERFIL_GRILLA, TOPO_REAL), persistir_campo=persistir_async)
    assert len(guardados) == 1

    def persistir_roto(_cambios):
        raise RuntimeError("Supabase caído")

    datos = _obtener(campo=_campo(PERFIL_GRILLA, TOPO_REAL), persistir_campo=persistir_roto)
    assert datos.perfil_suelo == PERFIL_REAL


def test_coordenadas_invalidas(providers):
    with pytest.raises(ValueError):
        asyncio.run(datos_lote.obtener_datos_lote(95.0, -60.0, today=HOY))
