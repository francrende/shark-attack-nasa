"""Tests de BACK-21 / BACK-22: enriquecimiento automático de suelo, MO y topografía en ``/api/v1/fields``."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import app  # noqa: E402
from providers.soilgrids import PerfilSueloSatelital, SoilGridsUnavailable  # noqa: E402
from providers.srtm import SrtmUnavailable, TopografiaSrtm  # noqa: E402
from routers.auth import AuthenticatedUser  # noqa: E402
from routers.fields import get_current_user, get_field_enricher  # noqa: E402
from services.field_enrichment_service import (  # noqa: E402
    calcular_materia_organica_g_kg,
    enriquecer_datos_campo,
)

USER_ID = str(uuid4())
FIELD_ID = str(uuid4())

PERFIL_EJEMPLO = PerfilSueloSatelital(
    arcilla_pct=17.7,
    arena_pct=33.9,
    limo_pct=48.4,
    carbono_organico_g_kg=12.9,
    ph=7.28,
    textura_predominante="franco",
    fuente="isric_soilgrids_v2",
    distancia_fuente_km=0.0,
    localidad_fallback=None,
    advertencias=(),
    reintentar_soilgrids=False,
)

TOPO_EJEMPLO = TopografiaSrtm(
    elevacion_m=113.0,
    pendiente_terreno_pct=0.42,
    fuente="opentopodata_srtm30m",
    fuente_elevacion="srtm30m",
    distancia_fuente_km=0.0,
    localidad_fallback=None,
    advertencias=(),
    reintentar_srtm=False,
)


class _FakeQuery:
    def __init__(self, rows: dict[str, dict]) -> None:
        self._rows = rows
        self._op = "select"
        self._payload: dict | None = None
        self._eq_id: str | None = None

    def select(self, *_args, **_kwargs):
        self._op = "select"
        return self

    def insert(self, payload: dict):
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload: dict):
        self._op = "update"
        self._payload = payload
        return self

    def eq(self, col: str, val: str):
        if col == "id":
            self._eq_id = val
        return self

    def maybe_single(self):
        return self

    def execute(self):
        if self._op == "insert":
            assert self._payload is not None
            row = {
                "id": FIELD_ID,
                "created_at": datetime(2026, 11, 15, 15, 0, tzinfo=timezone.utc).isoformat(),
                **self._payload,
            }
            self._rows[FIELD_ID] = row
            return SimpleNamespace(data=[row])
        if self._op == "update":
            assert self._payload is not None and self._eq_id is not None
            existing = self._rows.get(self._eq_id)
            if not existing:
                return SimpleNamespace(data=[])
            existing.update(self._payload)
            return SimpleNamespace(data=[existing])
        if self._eq_id is not None:
            return SimpleNamespace(data=self._rows.get(self._eq_id))
        return SimpleNamespace(data=list(self._rows.values()))


class _FakeSupabaseClient:
    def __init__(self, rows: dict[str, dict]) -> None:
        self.rows = rows

    def table(self, name: str):
        assert name == "fields"
        return _FakeQuery(self.rows)


class FieldEnrichmentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        app.dependency_overrides.clear()
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            id=USER_ID,
            email="test@ereia.ag",
            nombre="Test",
            access_token="fake-jwt",
        )

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_calcular_materia_organica_g_kg(self) -> None:
        self.assertEqual(calcular_materia_organica_g_kg(12.9), 22.2)
        self.assertEqual(calcular_materia_organica_g_kg(14.7), 25.3)
        self.assertIsNone(calcular_materia_organica_g_kg(None))

    async def test_enriquecer_datos_campo_completo(self) -> None:
        async def _fake_suelo(*_args, **_kwargs):
            return PERFIL_EJEMPLO

        async def _fake_topo(*_args, **_kwargs):
            return TOPO_EJEMPLO

        with (
            patch("services.field_enrichment_service.fetch_perfil_suelo", side_effect=_fake_suelo),
            patch("services.field_enrichment_service.fetch_topografia", side_effect=_fake_topo),
        ):
            cols = await enriquecer_datos_campo(-33.95, -60.57)

        self.assertEqual(cols["ph"], 7.28)
        self.assertEqual(cols["carbono_organico_g_kg"], 12.9)
        self.assertEqual(cols["materia_organica_g_kg"], 22.2)
        self.assertEqual(cols["suelo_fuente"], "isric_soilgrids_v2")
        self.assertFalse(cols["reintentar_soilgrids"])
        self.assertEqual(cols["elevacion_m"], 113.0)
        self.assertEqual(cols["pendiente_terreno_pct"], 0.42)
        self.assertEqual(cols["fuente_elevacion"], "srtm30m")
        self.assertEqual(cols["topo_fuente"], "opentopodata_srtm30m")
        self.assertFalse(cols["reintentar_srtm"])

    async def test_enriquecer_datos_campo_tolera_falla_de_proveedores(self) -> None:
        async def _fail_suelo(*_args, **_kwargs):
            raise SoilGridsUnavailable("sin cobertura")

        async def _fail_topo(*_args, **_kwargs):
            raise SrtmUnavailable("sin cobertura")

        with (
            patch("services.field_enrichment_service.fetch_perfil_suelo", side_effect=_fail_suelo),
            patch("services.field_enrichment_service.fetch_topografia", side_effect=_fail_topo),
        ):
            cols = await enriquecer_datos_campo(-33.95, -60.57)

        self.assertEqual(cols["suelo_fuente"], "no_disponible")
        self.assertTrue(cols["reintentar_soilgrids"])
        self.assertIsNone(cols["materia_organica_g_kg"])
        self.assertEqual(cols["topo_fuente"], "no_disponible")
        self.assertTrue(cols["reintentar_srtm"])

    async def test_create_y_update_field_enriquecen_solo_cuando_corresponde(self) -> None:
        llamadas_enricher: list[tuple[float, float]] = []

        async def _fake_enricher(lat: float, lon: float):
            llamadas_enricher.append((lat, lon))
            return {
                "ph": 6.65,
                "limo_pct": 65.1,
                "arena_pct": 3.1,
                "arcilla_pct": 31.8,
                "textura_predominante": "franco_arcillo_limoso",
                "carbono_organico_g_kg": 14.7,
                "materia_organica_g_kg": 25.3,
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

        rows: dict[str, dict] = {}
        fake_client = _FakeSupabaseClient(rows)
        app.dependency_overrides[get_field_enricher] = lambda: _fake_enricher

        with patch("routers.fields.get_authenticated_supabase_client", return_value=fake_client):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                resp = await client.post(
                    "/api/v1/fields",
                    json={"nombre": "Lote Norte", "lat": -32.4793, "lon": -61.3548},
                )
                self.assertEqual(resp.status_code, 201)
                creado = resp.json()
                self.assertEqual(creado["materia_organica_g_kg"], 25.3)
                self.assertEqual(creado["suelo_fuente"], "isric_soilgrids_v2")
                self.assertEqual(creado["topo_fuente"], "opentopodata_srtm30m")
                self.assertEqual(len(llamadas_enricher), 1)

                # Renombrar no debe disparar enriquecimiento
                resp_rename = await client.patch(
                    f"/api/v1/fields/{FIELD_ID}",
                    json={"nombre": "Lote Renombrado"},
                )
                self.assertEqual(resp_rename.status_code, 200)
                self.assertEqual(len(llamadas_enricher), 1)

                # Cambiar polígono sí re-enriquece usando lat/lon guardados si no vienen en PATCH
                resp_poly = await client.patch(
                    f"/api/v1/fields/{FIELD_ID}",
                    json={"polygon": [[-32.47, -61.35], [-32.48, -61.35], [-32.48, -61.36]]},
                )
                self.assertEqual(resp_poly.status_code, 200)
                self.assertEqual(len(llamadas_enricher), 2)


if __name__ == "__main__":
    unittest.main()
