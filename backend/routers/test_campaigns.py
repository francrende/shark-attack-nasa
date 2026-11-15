"""Tests de BACK-30: cerrar (fecha de cosecha y rinde) y borrar campañas (sin red ni Supabase)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from routers.campaigns import AuthenticatedUser, get_current_user

FIELD_ID = "11111111-1111-1111-1111-111111111111"
CAMPAIGN_ID = "33333333-3333-3333-3333-333333333333"
URL = f"/api/v1/fields/{FIELD_ID}/campaigns"


class _Query:
    def __init__(self, db, tabla):
        self.db, self.tabla = db, tabla
        self.filtros: dict[str, str] = {}
        self.op, self.payload, self.unico = "select", None, False

    def select(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self.filtros[col] = str(val)
        return self

    def maybe_single(self):
        self.unico = True
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def delete(self):
        self.op = "delete"
        return self

    def insert(self, payload):
        self.op, self.payload = "insert", payload
        return self

    def execute(self):
        filas = self.db[self.tabla]
        match = [f for f in filas if all(str(f.get(k)) == v for k, v in self.filtros.items())]
        if self.op == "update":
            for f in match:
                f.update(self.payload)
        elif self.op == "delete":
            self.db[self.tabla] = [f for f in filas if f not in match]
        elif self.op == "insert":
            fila = {"id": CAMPAIGN_ID, "created_at": datetime.now(timezone.utc).isoformat(), **self.payload}
            filas.append(fila)
            match = [fila]
        if self.unico:
            return SimpleNamespace(data=match[0] if match else None)
        return SimpleNamespace(data=[dict(f) for f in match])


class _Cliente:
    def __init__(self, db):
        self.db = db

    def table(self, nombre):
        return _Query(self.db, nombre)


def _campana(**cambios):
    c = {
        "id": CAMPAIGN_ID, "field_id": FIELD_ID, "user_id": "22222222-2222-2222-2222-222222222222", "campana": "verano", "cultivo": "soja_primera",
        "fecha_inicio": "2025-11-13", "fecha_fin": None, "rinde_kg_ha": None, "resultado_notas": None,
        "simulacion_json": {"seguimiento": {"etapa": "terminado"}}, "created_at": "2025-11-13T00:00:00+00:00",
    }
    c.update(cambios)
    return c


@pytest.fixture
def cliente():
    db = {"fields": [{"id": FIELD_ID}], "campaigns": [_campana()]}
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id="u1", email="test@ereia.ag", nombre="Test", access_token="jwt"
    )
    with patch("routers.campaigns.get_authenticated_supabase_client", lambda _t: _Cliente(db)):
        with TestClient(app) as c:
            c.db = db
            yield c
    app.dependency_overrides.clear()


def test_cerrar_campana_con_rinde(cliente):
    r = cliente.patch(f"{URL}/{CAMPAIGN_ID}", json={"fecha_fin": "2026-04-20", "rinde_kg_ha": 3400, "resultado_notas": "Buen año"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["fecha_fin"] == "2026-04-20"
    assert data["rinde_kg_ha"] == 3400
    # El seguimiento guardado no se pierde al cerrar.
    assert data["simulacion_json"]["seguimiento"]["etapa"] == "terminado"


def test_cosecha_antes_de_la_siembra_422(cliente):
    r = cliente.patch(f"{URL}/{CAMPAIGN_ID}", json={"fecha_fin": "2025-11-01"})
    assert r.status_code == 422
    assert "anterior a la de siembra" in r.json()["detail"]
    assert cliente.db["campaigns"][0]["fecha_fin"] is None


def test_cosecha_futura_422(cliente):
    futura = (datetime.now(timezone.utc).date() + timedelta(days=10)).isoformat()
    r = cliente.patch(f"{URL}/{CAMPAIGN_ID}", json={"fecha_fin": futura})
    assert r.status_code == 422
    assert "futura" in r.json()["detail"]


def test_rinde_negativo_422(cliente):
    assert cliente.patch(f"{URL}/{CAMPAIGN_ID}", json={"rinde_kg_ha": -5}).status_code == 422


def test_crear_con_cosecha_anterior_422(cliente):
    r = cliente.post(URL, json={"campana": "verano", "cultivo": "soja_primera", "fecha_inicio": "2025-11-13", "fecha_fin": "2025-10-01"})
    assert r.status_code == 422


def test_borrar_campana(cliente):
    r = cliente.delete(f"{URL}/{CAMPAIGN_ID}")
    assert r.status_code == 204
    assert cliente.db["campaigns"] == []
    assert cliente.delete(f"{URL}/{CAMPAIGN_ID}").status_code == 404


def test_hoy_es_valido_como_cosecha(cliente):
    hoy = date.today().isoformat()
    assert cliente.patch(f"{URL}/{CAMPAIGN_ID}", json={"fecha_fin": hoy}).status_code == 200
