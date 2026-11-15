"""Tests de BACK-25: reintento en segundo plano de ISRIC/SRTM por campo (sin red)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from main import app
from providers.soilgrids import PerfilSueloSatelital, SoilGridsUnavailable
from providers.srtm import TopografiaSrtm
from routers.auth import AuthenticatedUser
from routers.fields import get_current_user, get_field_enricher
from routers.test_fields_enrichment import FIELD_ID, USER_ID, _FakeSupabaseClient
from services import reintentos_campos
from services.field_enrichment_service import (
    suelo_a_columnas_field,
    suelo_no_disponible_a_columnas_field,
    topografia_a_columnas_field,
)
from services.reintentos_campos import ColaReintentos, cargar_pendientes

PERFIL_REAL = PerfilSueloSatelital(
    arcilla_pct=23.4, arena_pct=14.2, limo_pct=62.4, carbono_organico_g_kg=17.9, ph=6.4,
    textura_predominante="franco_limoso", fuente="isric_soilgrids_v2", distancia_fuente_km=0.0,
    localidad_fallback=None, advertencias=(),
)
PERFIL_GRILLA = PerfilSueloSatelital(
    arcilla_pct=29.0, arena_pct=20.0, limo_pct=51.0, carbono_organico_g_kg=12.8, ph=6.1,
    textura_predominante="franco_arcilloso", fuente="grilla_isric", distancia_fuente_km=46.0,
    localidad_fallback=None, advertencias=("a 46 km",), reintentar_soilgrids=True,
)
TOPO_REAL = TopografiaSrtm(
    elevacion_m=69.0, pendiente_terreno_pct=0.82, fuente="opentopodata_srtm30m", fuente_elevacion="srtm30m",
    distancia_fuente_km=0.0, localidad_fallback=None, advertencias=(),
)
TOPO_APROX = TopografiaSrtm(
    elevacion_m=70.0, pendiente_terreno_pct=1.15, fuente="fallback_regional", fuente_elevacion="nasa_power",
    distancia_fuente_km=6.7, localidad_fallback="Pergamino", advertencias=("aprox",), reintentar_srtm=True,
)


class _Providers:
    """Respuestas programables por ronda; registra las llamadas."""

    def __init__(self, suelo=(), topo=()):
        self.suelo = list(suelo)
        self.topo = list(topo)
        self.llamadas: list[str] = []

    async def fetch_suelo(self, *_a, **_k):
        self.llamadas.append("suelo")
        r = self.suelo.pop(0)
        if isinstance(r, BaseException):
            raise r
        return r

    async def fetch_topo(self, *_a, **_k):
        self.llamadas.append("topo")
        r = self.topo.pop(0)
        if isinstance(r, BaseException):
            raise r
        return r


def _cola(prov: _Providers, escritas: list, **kw) -> ColaReintentos:
    return ColaReintentos(
        lambda fid, cambios: escritas.append((fid, cambios)),
        proveedor_suelo=prov.fetch_suelo,
        proveedor_topo=prov.fetch_topo,
        **kw,
    )


def test_encolar_solo_si_hay_pendientes():
    cola = _cola(_Providers(), [])
    cola.encolar("f1", -33.9, -60.5, suelo=False, topo=False)
    assert not cola.en_curso("f1")
    cola.encolar("f1", -33.9, -60.5, suelo=True, topo=False)
    assert cola.en_curso("f1")
    cola.encolar("f1", -33.9, -60.5, suelo=False, topo=False)
    assert not cola.en_curso("f1")


def test_persiste_solo_dato_real_y_por_separado():
    prov = _Providers(suelo=[PERFIL_REAL], topo=[TOPO_APROX, TOPO_REAL])
    escritas: list = []
    cola = _cola(prov, escritas)
    cola.encolar("f1", -33.9, -60.5, suelo=True, topo=True)

    asyncio.run(cola.ciclo())  # suelo real, topografía todavía aproximada
    assert escritas == [("f1", suelo_a_columnas_field(PERFIL_REAL))]
    assert cola.en_curso("f1")

    asyncio.run(cola.ciclo())  # solo se reintenta la topografía
    assert prov.llamadas == ["suelo", "topo", "topo"]
    assert escritas[1] == ("f1", topografia_a_columnas_field(TOPO_REAL))
    assert not cola.en_curso("f1")


def test_aproximado_o_corte_cuenta_el_intento_sin_escribir_y_corta_a_los_12():
    prov = _Providers(suelo=[PERFIL_GRILLA] * 5 + [SoilGridsUnavailable("caído")] * 7)
    escritas: list = []
    cola = _cola(prov, escritas)
    cola.encolar("f1", -33.9, -60.5, suelo=True, topo=False)
    for _ in range(11):
        asyncio.run(cola.ciclo())
    assert cola.en_curso("f1")
    asyncio.run(cola.ciclo())
    assert not cola.en_curso("f1")
    assert escritas == [] and prov.llamadas.count("suelo") == 12


def test_error_al_escribir_sigue_pendiente():
    prov = _Providers(suelo=[PERFIL_REAL, PERFIL_REAL])
    llamadas = []

    def escritor_roto(fid, cambios):
        llamadas.append(fid)
        if len(llamadas) == 1:
            raise RuntimeError("Supabase caído")

    cola = ColaReintentos(escritor_roto, proveedor_suelo=prov.fetch_suelo, proveedor_topo=prov.fetch_topo)
    cola.encolar("f1", -33.9, -60.5, suelo=True, topo=False)
    asyncio.run(cola.ciclo())
    assert cola.en_curso("f1")
    asyncio.run(cola.ciclo())
    assert not cola.en_curso("f1") and len(llamadas) == 2


def test_reencolar_no_reinicia_el_contador():
    prov = _Providers(suelo=[PERFIL_GRILLA] * 12)
    cola = _cola(prov, [], max_intentos=3)
    cola.encolar("f1", -33.9, -60.5, suelo=True, topo=False)
    asyncio.run(cola.ciclo())
    asyncio.run(cola.ciclo())
    cola.encolar("f1", -33.9, -60.5, suelo=True, topo=False)  # p. ej., desde /telemetry
    asyncio.run(cola.ciclo())
    assert not cola.en_curso("f1")


def test_encolar_desde_fila_lee_las_marcas():
    cola = _cola(_Providers(), [])
    fila = {"id": "f1", "lat": -33.9, "lon": -60.5, **suelo_a_columnas_field(PERFIL_REAL), **topografia_a_columnas_field(TOPO_REAL)}
    cola.encolar_desde_fila(fila)
    assert not cola.en_curso("f1")
    cola.encolar_desde_fila({**fila, **suelo_no_disponible_a_columnas_field()})
    assert cola.en_curso("f1")


def test_bucle_espera_el_intervalo_y_se_detiene():
    async def _go():
        esperas: list[float] = []
        ronda = asyncio.Event()

        async def dormir(s):
            esperas.append(s)
            if len(esperas) > 1:
                ronda.set()
                await asyncio.sleep(3600)

        prov = _Providers(suelo=[PERFIL_REAL])
        escritas: list = []
        cola = _cola(prov, escritas, dormir=dormir)
        cola.encolar("f1", -33.9, -60.5, suelo=True, topo=False)
        cola.iniciar()
        await asyncio.wait_for(ronda.wait(), 2)
        await cola.detener()
        return esperas, escritas

    esperas, escritas = asyncio.run(_go())
    assert esperas[:2] == [300.0, 300.0]  # primero espera 5 min: el alta ya intentó
    assert len(escritas) == 1


def test_cargar_pendientes_filtra_por_marcas_y_24h():
    registro = {}

    class _Q:
        def select(self, cols):
            registro["select"] = cols
            return self

        def or_(self, filtro):
            registro["or"] = filtro
            return self

        def gte(self, col, valor):
            registro["gte"] = (col, valor)
            return self

        def execute(self):
            return SimpleNamespace(data=[{"id": "f1"}])

    cliente = SimpleNamespace(table=lambda nombre: _Q())
    filas = cargar_pendientes(cliente, ahora=datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc))
    assert filas == [{"id": "f1"}]
    assert registro["or"] == "reintentar_soilgrids.eq.true,reintentar_srtm.eq.true"
    assert registro["gte"] == ("created_at", "2026-11-14T12:00:00+00:00")


def test_sin_secret_key_no_hay_cola():
    settings = SimpleNamespace(cache_persistente=True, supabase_url="https://x.supabase.co", supabase_secret_key="")
    assert asyncio.run(reintentos_campos.iniciar_reintentos(settings)) is None
    assert reintentos_campos.obtener_cola() is None
    assert reintentos_campos.en_curso("f1") is False


@pytest.fixture
def cola_global():
    cola = _cola(_Providers(), [])
    reintentos_campos.configurar_cola(cola)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=USER_ID, email="test@ereia.ag", nombre="Test", access_token="fake-jwt"
    )
    yield cola
    reintentos_campos.configurar_cola(None)
    app.dependency_overrides.clear()


def _crear_campo(enriquecimiento: dict):
    async def enricher(_lat, _lon):
        return enriquecimiento

    app.dependency_overrides[get_field_enricher] = lambda: enricher
    rows: dict = {}

    async def _go():
        with patch("routers.fields.get_authenticated_supabase_client", return_value=_FakeSupabaseClient(rows)):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
                creado = await c.post("/api/v1/fields", json={"nombre": "Lote", "lat": -33.9, "lon": -60.5})
                leido = await c.get(f"/api/v1/fields/{FIELD_ID}")
                return creado, leido

    return asyncio.run(_go())


def test_alta_con_dato_aproximado_encola_y_lo_muestra(cola_global):
    creado, leido = _crear_campo({**suelo_a_columnas_field(PERFIL_GRILLA), **topografia_a_columnas_field(TOPO_REAL)})
    assert creado.status_code == 201
    assert creado.json()["reintento_en_curso"] is True
    assert leido.json()["reintento_en_curso"] is True
    assert cola_global.en_curso(FIELD_ID)


def test_alta_con_dato_real_no_encola(cola_global):
    creado, leido = _crear_campo({**suelo_a_columnas_field(PERFIL_REAL), **topografia_a_columnas_field(TOPO_REAL)})
    assert creado.json()["reintento_en_curso"] is False
    assert not cola_global.en_curso(FIELD_ID)
