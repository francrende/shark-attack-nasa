"""Tests de BACK-20: ``GET /api/v1/telemetry`` (sin red)."""

from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import app  # noqa: E402
from providers.nasa_power import NasaPowerDailySeries, NasaPowerUnavailable  # noqa: E402
from providers.nasa_telemetry import ReferenciaHistorica  # noqa: E402
from providers.soilgrids import PerfilSueloSatelital, SoilGridsUnavailable  # noqa: E402
from providers.srtm import SrtmUnavailable, TopografiaSrtm  # noqa: E402
from routers.telemetry import get_field_store, get_hoy, get_telemetry_fetcher  # noqa: E402
from schemas import TelemetryResponse  # noqa: E402
from services.telemetry_service import obtener_telemetria_campo  # noqa: E402

HOY = date(2026, 11, 15)

TELEMETRIA_OK = {
    "fecha_ultimo_dato_valido": "2026-11-11",
    "indice_humedad_radicular_pct": 46.0,
    "indice_humedad_superficial_pct": 35.0,
    "tendencia_humedad_15d_pct": -4.4,
    "anomalia_lluvia_90d_pct": -37.38,
    "frecuencia_tormentas_extremas_90d": 3,
    "riesgo_termico_verano": "alto",
}

PERFIL_OK = PerfilSueloSatelital(
    arcilla_pct=23.4,
    arena_pct=14.2,
    limo_pct=62.4,
    carbono_organico_g_kg=17.9,
    ph=6.4,
    textura_predominante="franco_limoso",
    fuente="isric_soilgrids_v2",
    distancia_fuente_km=0.0,
    localidad_fallback=None,
    advertencias=(),
)

ADV_SUELO = "SoilGrids no disponible; se usó referencia regional GeoINTA (Pergamino)."
PERFIL_FALLBACK = PerfilSueloSatelital(
    arcilla_pct=29.5,
    arena_pct=None,
    limo_pct=None,
    carbono_organico_g_kg=None,
    ph=None,
    textura_predominante=None,
    fuente="fallback_regional",
    distancia_fuente_km=12.34,
    localidad_fallback="Pergamino",
    advertencias=(ADV_SUELO,),
    reintentar_soilgrids=True,
)

TOPO_OK = TopografiaSrtm(
    elevacion_m=69.04,
    pendiente_terreno_pct=1.45,
    fuente="opentopodata_srtm30m",
    fuente_elevacion="srtm30m",
    distancia_fuente_km=0.0,
    localidad_fallback=None,
    advertencias=(ADV_SUELO, "Pendiente tomada del modelo SRTM 30 m."),
)


def _serie_reciente_dummy() -> NasaPowerDailySeries:
    dias = [HOY - timedelta(days=i) for i in range(95, -1, -1)]
    return NasaPowerDailySeries(
        lat=-36.93,
        lon=-64.05,
        start=dias[0],
        end=dias[-1],
        series={
            "GWETROOT": {d: 0.44 for d in dias},
            "GWETTOP": {d: 0.31 for d in dias},
            "PRECTOTCORR": {d: 2.0 for d in dias},
        },
        elevacion_m=175.0,
    )


# BACK-24: los indicadores se calculan con la función única (``indicadores_telemetria``) a
# partir de la ventana reciente y la referencia histórica. Estos datos sintéticos dan los
# mismos valores que antes devolvía el fake de la telemetría "ligera" (46 %, 35 %, "alto").
REF_OK = ReferenciaHistorica(clim_por_doy={d: 200.0 for d in range(1, 367)}, dias_calor_verano_promedio=30.0)


def _serie_reciente(gwetroot: float, gwettop: float) -> NasaPowerDailySeries:
    serie = _serie_reciente_dummy()
    dias = sorted(serie.series["GWETROOT"])
    return NasaPowerDailySeries(
        lat=serie.lat,
        lon=serie.lon,
        start=serie.start,
        end=serie.end,
        series={
            "GWETROOT": {d: gwetroot for d in dias},
            "GWETTOP": {d: gwettop for d in dias},
            "PRECTOTCORR": dict(serie.series["PRECTOTCORR"]),
        },
        elevacion_m=serie.elevacion_m,
    )


async def _fake_reciente_ok(*_args, **_kwargs):
    return _serie_reciente(0.46, 0.35)


async def _fake_ref_ok(*_args, **_kwargs):
    return REF_OK


class TelemetryRouterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        app.dependency_overrides.clear()
        app.dependency_overrides[get_hoy] = lambda: HOY

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_openapi_incluye_telemetry(self) -> None:
        paths = app.openapi()["paths"]
        self.assertIn("/api/v1/telemetry", paths)
        self.assertIn("get", paths["/api/v1/telemetry"])

    async def test_telemetry_happy_path(self) -> None:
        async def _fake_telemetria(*_args, **_kwargs):
            return TELEMETRIA_OK, []

        async def _fake_suelo(*_args, **_kwargs):
            return PERFIL_OK

        async def _fake_topo(*_args, **_kwargs):
            return TOPO_OK

        with (
            patch("services.datos_lote.obtener_ventana_reciente", side_effect=_fake_reciente_ok),
            patch("services.datos_lote.obtener_referencia_historica", side_effect=_fake_ref_ok),
            patch("services.datos_lote.fetch_perfil_suelo", side_effect=_fake_suelo),
            patch("services.datos_lote.fetch_topografia", side_effect=_fake_topo),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.get("/api/v1/telemetry", params={"lat": -33.95, "lon": -60.57})

        self.assertEqual(resp.status_code, 200)
        parsed = TelemetryResponse.model_validate(resp.json())
        self.assertEqual(parsed.ubicacion.lat, -33.95)
        assert parsed.telemetria_nasa is not None
        assert parsed.topografia_srtm is not None
        self.assertEqual(parsed.telemetria_nasa.indice_humedad_radicular_pct, 46.0)
        self.assertEqual(parsed.telemetria_nasa.riesgo_termico_verano, "alto")
        self.assertEqual(parsed.perfil_suelo.carbono_organico_g_kg, 17.9)
        self.assertEqual(parsed.perfil_suelo.materia_organica_g_kg, 30.9)
        self.assertEqual(parsed.perfil_suelo.textura_predominante, "franco_limoso")
        self.assertEqual(parsed.topografia_srtm.elevacion_m, 69.0)
        self.assertEqual(parsed.topografia_srtm.pendiente_terreno_pct, 1.45)
        self.assertEqual(parsed.topografia_srtm.fuente_elevacion, "srtm30m")

    async def test_telemetry_preserva_null_en_fallback_y_deduplica_advertencias(self) -> None:
        async def _fake_telemetria(*_args, **_kwargs):
            return TELEMETRIA_OK, []

        async def _fake_suelo(*_args, **_kwargs):
            return PERFIL_FALLBACK

        async def _fake_topo(*_args, **_kwargs):
            return TOPO_OK

        with (
            patch("services.datos_lote.obtener_ventana_reciente", side_effect=_fake_reciente_ok),
            patch("services.datos_lote.obtener_referencia_historica", side_effect=_fake_ref_ok),
            patch("services.datos_lote.fetch_perfil_suelo", side_effect=_fake_suelo),
            patch("services.datos_lote.fetch_topografia", side_effect=_fake_topo),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.get("/api/v1/telemetry", params={"lat": -33.95, "lon": -60.57})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIsNone(body["perfil_suelo"]["carbono_organico_g_kg"])
        self.assertIsNone(body["perfil_suelo"]["textura_predominante"])
        self.assertEqual(body["perfil_suelo"]["fuente"], "fallback_regional")
        self.assertEqual(body["perfil_suelo"]["localidad_fallback"], "Pergamino")
        self.assertTrue(body["perfil_suelo"]["reintentar_soilgrids"])
        self.assertEqual(
            body["advertencias"],
            [ADV_SUELO, "Pendiente tomada del modelo SRTM 30 m."],
        )

    async def test_soilgrids_unavailable_devuelve_200_con_nasa_disponible(self) -> None:
        async def _fake_suelo(*_args, **_kwargs):
            raise SoilGridsUnavailable("fuera de 100 km GeoINTA")

        async def _fake_topo(*_args, **_kwargs):
            raise SrtmUnavailable("fuera de 100 km GeoINTA")

        async def _fake_reciente(*_args, **_kwargs):
            return _serie_reciente_dummy()

        async def _fake_clim(*_args, **_kwargs):
            raise NasaPowerUnavailable("timeout histórico")

        with (
            patch("services.datos_lote.obtener_ventana_reciente", side_effect=_fake_reciente),
            patch("services.datos_lote.obtener_referencia_historica", side_effect=_fake_clim),
            patch("services.datos_lote.fetch_perfil_suelo", side_effect=_fake_suelo),
            patch("services.datos_lote.fetch_topografia", side_effect=_fake_topo),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.get("/api/v1/telemetry", params={"lat": -36.93, "lon": -64.05})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["telemetria_nasa"]["indice_humedad_radicular_pct"], 44.0)
        self.assertEqual(body["telemetria_nasa"]["indice_humedad_superficial_pct"], 31.0)
        self.assertIsNone(body["telemetria_nasa"]["anomalia_lluvia_90d_pct"])
        self.assertIsNone(body["telemetria_nasa"]["riesgo_termico_verano"])
        self.assertIsNone(body["topografia_srtm"])
        self.assertEqual(body["perfil_suelo"]["fuente"], "no_disponible")
        self.assertIsNone(body["perfil_suelo"]["carbono_organico_g_kg"])
        self.assertIsNone(body["perfil_suelo"]["textura_predominante"])
        self.assertGreaterEqual(len(body["advertencias"]), 3)

    async def test_todos_los_providers_caidos_devuelven_503(self) -> None:
        async def _nasa_fail(*_args, **_kwargs):
            raise NasaPowerUnavailable("nasa caída")

        async def _suelo_fail(*_args, **_kwargs):
            raise SoilGridsUnavailable("soilgrids caído")

        async def _topo_fail(*_args, **_kwargs):
            raise SrtmUnavailable("srtm caído")

        with (
            patch("services.datos_lote.obtener_ventana_reciente", side_effect=_nasa_fail),
            patch("services.datos_lote.obtener_referencia_historica", side_effect=_nasa_fail),
            patch("services.datos_lote.fetch_perfil_suelo", side_effect=_suelo_fail),
            patch("services.datos_lote.fetch_topografia", side_effect=_topo_fail),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.get("/api/v1/telemetry", params={"lat": -33.95, "lon": -60.57})
        self.assertEqual(resp.status_code, 503)

    async def test_coordenadas_fuera_de_rango_devuelven_422(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/v1/telemetry", params={"lat": 95.0, "lon": -60.57})
        self.assertEqual(resp.status_code, 422)

    async def test_value_error_en_servicio_devuelve_422(self) -> None:
        with self.assertRaises(ValueError):
            await obtener_telemetria_campo(120.0, -60.57)

        async def _invalido(*_args, **_kwargs):
            raise ValueError("Coordenadas inválidas")

        app.dependency_overrides[get_telemetry_fetcher] = lambda: _invalido
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/v1/telemetry", params={"lat": -33.95, "lon": -60.57})
        self.assertEqual(resp.status_code, 422)

    async def test_telemetry_reutiliza_datos_propios_del_campo_sin_llamar_isric_ni_srtm(self) -> None:
        field_id = "11111111-1111-1111-1111-111111111111"
        saved_row = {
            "id": field_id,
            "lat": -32.4793,
            "lon": -61.3548,
            "ph": 6.65,
            "limo_pct": 65.1,
            "arena_pct": 3.1,
            "arcilla_pct": 31.8,
            "textura_predominante": "franco_arcillo_limoso",
            "carbono_organico_g_kg": 14.7,
            "materia_organica_g_kg": None,  # valida cálculo automático 14.7 * 1.724 = 25.3
            "suelo_fuente": "isric_soilgrids_v2",
            "suelo_advertencias": [],
            "suelo_localidad_fallback": None,
            "suelo_distancia_fuente_km": 0.0,
            "reintentar_soilgrids": False,
            "elevacion_m": 113.0,
            "pendiente_terreno_pct": 0.42,
            "fuente_elevacion": "srtm30m",
            "topo_fuente": "opentopodata_srtm30m",
            "topo_advertencias": [],
            "topo_localidad_fallback": None,
            "topo_distancia_fuente_km": 0.0,
            "reintentar_srtm": False,
        }
        updated_calls: list[dict] = []

        class _FakeStore:
            def get_field(self, fid, _token):
                return saved_row if str(fid) == field_id else None

            def update_field(self, _fid, _token, updates):
                updated_calls.append(updates)

        async def _fake_telemetria(*_args, **_kwargs):
            return TELEMETRIA_OK, []

        async def _no_debe_llamarse(*_args, **_kwargs):
            raise AssertionError("No debía consultar ISRIC/SRTM cuando el campo ya tiene datos válidos")

        app.dependency_overrides[get_field_store] = lambda: _FakeStore()
        with (
            patch("services.datos_lote.obtener_ventana_reciente", side_effect=_fake_reciente_ok),
            patch("services.datos_lote.obtener_referencia_historica", side_effect=_fake_ref_ok),
            patch("services.datos_lote.fetch_perfil_suelo", side_effect=_no_debe_llamarse),
            patch("services.datos_lote.fetch_topografia", side_effect=_no_debe_llamarse),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.get(
                    "/api/v1/telemetry",
                    params={"lat": -32.4793, "lon": -61.3548, "field_id": field_id},
                    headers={"Authorization": "Bearer fake-token"},
                )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["perfil_suelo"]["carbono_organico_g_kg"], 14.7)
        self.assertEqual(body["perfil_suelo"]["materia_organica_g_kg"], 25.3)
        self.assertEqual(body["perfil_suelo"]["textura_predominante"], "franco_arcillo_limoso")
        self.assertEqual(body["topografia_srtm"]["elevacion_m"], 113.0)
        self.assertEqual(body["topografia_srtm"]["fuente_elevacion"], "srtm30m")
        self.assertEqual(updated_calls, [])

    async def test_telemetry_reintenta_suelo_si_reintentar_soilgrids_es_true_y_persiste(self) -> None:
        field_id = "22222222-2222-2222-2222-222222222222"
        saved_row = {
            "id": field_id,
            "lat": -33.95,
            "lon": -60.57,
            "suelo_fuente": "fallback_regional",
            "reintentar_soilgrids": True,
            "elevacion_m": 69.0,
            "pendiente_terreno_pct": 1.45,
            "fuente_elevacion": "srtm30m",
            "topo_fuente": "opentopodata_srtm30m",
            "topo_advertencias": [],
            "topo_localidad_fallback": None,
            "topo_distancia_fuente_km": 0.0,
            "reintentar_srtm": False,
        }
        updated_calls: list[dict] = []

        class _FakeStore:
            def get_field(self, fid, _token):
                return saved_row if str(fid) == field_id else None

            def update_field(self, _fid, _token, updates):
                updated_calls.append(updates)

        async def _fake_telemetria(*_args, **_kwargs):
            return TELEMETRIA_OK, []

        async def _fake_suelo(*_args, **_kwargs):
            return PERFIL_OK

        async def _no_topo(*_args, **_kwargs):
            raise AssertionError("SRTM no debía reintentarse porque reintentar_srtm=False")

        app.dependency_overrides[get_field_store] = lambda: _FakeStore()
        with (
            patch("services.datos_lote.obtener_ventana_reciente", side_effect=_fake_reciente_ok),
            patch("services.datos_lote.obtener_referencia_historica", side_effect=_fake_ref_ok),
            patch("services.datos_lote.fetch_perfil_suelo", side_effect=_fake_suelo),
            patch("services.datos_lote.fetch_topografia", side_effect=_no_topo),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.get(
                    "/api/v1/telemetry",
                    params={"lat": -33.95, "lon": -60.57, "field_id": field_id},
                    headers={"Authorization": "Bearer fake-token"},
                )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(updated_calls), 1)
        self.assertEqual(updated_calls[0]["materia_organica_g_kg"], 30.9)
        self.assertFalse(updated_calls[0]["reintentar_soilgrids"])
        self.assertNotIn("elevacion_m", updated_calls[0])


if __name__ == "__main__":
    unittest.main()
