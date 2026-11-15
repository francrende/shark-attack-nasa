"""Tests de la capa de caché persistente en Supabase (BACK-18). Sin red: cliente falso."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any

import pytest

from providers.cache import CacheEnCapas, CacheMemoria
from providers.cache_supabase import CacheSupabase, crear_cache_supabase


class _Consulta:
    """Imita el builder encadenado de supabase-py (`table().select().in_()...execute()`)."""

    def __init__(self, cliente: "ClienteFalso") -> None:
        self.c = cliente
        self.op = None
        self.payload: Any = None
        self.espacios: list[str] | None = None
        self.rango: tuple[int, int] | None = None

    def select(self, _cols):
        self.op = "select"
        return self

    def in_(self, _col, valores):
        self.espacios = list(valores)
        return self

    def order(self, _col):
        return self

    def range(self, desde, hasta):
        self.rango = (desde, hasta)
        return self

    def upsert(self, filas):
        self.op = "upsert"
        self.payload = filas
        return self

    def execute(self):
        if self.c.error is not None:
            raise self.c.error
        if self.op == "select":
            self.c.selects.append(self.rango)
            filas = [f for f in self.c.filas if self.espacios is None or f["espacio"] in self.espacios]
            desde, hasta = self.rango
            return SimpleNamespace(data=filas[desde : hasta + 1])
        self.c.upserts.append(self.payload)
        self.c.escrito.set()
        return SimpleNamespace(data=self.payload)


class ClienteFalso:
    def __init__(self, filas=None, error: Exception | None = None) -> None:
        self.filas = list(filas or [])
        self.error = error
        self.selects: list = []
        self.upserts: list = []
        self.escrito = threading.Event()

    def table(self, nombre):
        assert nombre == "provider_cache"
        return _Consulta(self)


def _fila(espacio, clave, valor=None):
    return {"espacio": espacio, "clave": clave, "valor": valor if valor is not None else {"v": clave}}


def test_hidratar_pagina_y_carga_solo_espacios_persistidos():
    filas = [_fila("suelo", f"k{i:03d}") for i in range(5)] + [_fila("nasa_reciente", "x")]
    cliente = ClienteFalso(filas)
    cache = CacheSupabase(cliente, tam_pagina=2)
    assert cache.hidratar() == 5
    assert cliente.selects == [(0, 1), (2, 3), (4, 5)]  # 2 + 2 + 1 (< página → corta)
    assert cache.get("suelo", "k003") == {"v": "k003"}
    assert cache.get("nasa_reciente", "x") is None


def test_get_no_llama_al_cliente_y_devuelve_copias():
    cliente = ClienteFalso([_fila("suelo", "a", {"lista": [1]})])
    cache = CacheSupabase(cliente)
    cache.hidratar()
    cliente.selects.clear()
    leido = cache.get("suelo", "a")
    leido["lista"].append(2)
    assert cache.get("suelo", "a") == {"lista": [1]}
    assert cache.get("suelo", "no_existe") is None
    assert cliente.selects == []


def test_set_encola_solo_persistidos_sin_ttl_y_escribe_en_segundo_plano():
    cliente = ClienteFalso()
    cache = CacheSupabase(cliente)
    cache.set("nasa_reciente", "c", {"x": 1})  # no persistido
    cache.set("suelo", "ttl", {"x": 1}, ttl_s=60)  # con TTL
    cache.set("topografia", "t1", {"elev": 69.0})
    cache.cerrar()
    filas = [f for lote in cliente.upserts for f in lote]
    assert filas == [{"espacio": "topografia", "clave": "t1", "valor": {"elev": 69.0}}]
    assert cache.get("topografia", "t1") == {"elev": 69.0}
    assert cache.get("nasa_reciente", "c") is None


def test_lote_deduplica_misma_clave():
    cliente = ClienteFalso()
    cache = CacheSupabase(cliente)
    bloqueo = threading.Event()
    original = cache._escribir

    def escribir_lento(lote):
        bloqueo.wait(2)
        original(lote)

    cache._escribir = escribir_lento  # type: ignore[method-assign]
    cache.set("suelo", "a", {"v": 1})  # el hilo toma este y se bloquea
    cache.set("suelo", "b", {"v": 1})
    cache.set("suelo", "b", {"v": 2})  # misma PK en el mismo lote
    bloqueo.set()
    cache.cerrar()
    for lote in cliente.upserts:
        claves = [(f["espacio"], f["clave"]) for f in lote]
        assert len(claves) == len(set(claves))
    ultimo_b = [f["valor"] for lote in cliente.upserts for f in lote if f["clave"] == "b"][-1]
    assert ultimo_b == {"v": 2}


def test_filtro_de_escritura():
    cliente = ClienteFalso()
    cache = CacheSupabase(cliente, filtro_escritura=lambda e, c: c != "precalculada")
    cache.set("nasa_hist", "precalculada", {"x": 1})
    cache.set("nasa_hist", "nueva", {"x": 2})
    cache.cerrar()
    assert [f["clave"] for lote in cliente.upserts for f in lote] == ["nueva"]


@pytest.mark.parametrize("error", [RuntimeError("relation provider_cache does not exist"), TimeoutError()])
def test_precarga_fallida_no_lanza(error):
    cache = CacheSupabase(ClienteFalso(error=error))
    assert cache.hidratar() == 0
    assert cache.get("suelo", "a") is None


def test_precarga_cortada_por_tiempo_conserva_lo_bajado():
    t = {"ahora": 0.0}
    cliente = ClienteFalso([_fila("suelo", f"k{i}") for i in range(10)])
    cache = CacheSupabase(cliente, tam_pagina=2, reloj=lambda: t["ahora"])
    original = cliente.table

    def tabla_lenta(nombre):
        t["ahora"] += 4.0  # cada página tarda 4 s
        return original(nombre)

    cliente.table = tabla_lenta  # type: ignore[method-assign]
    assert cache.hidratar(timeout_s=10) == 6  # páginas a t=4, 8 y 12 (la 3.ª arranca a t=8)
    assert cache.get("suelo", "k0") is not None


def test_error_al_escribir_no_se_propaga():
    cliente = ClienteFalso(error=RuntimeError("401 invalid api key"))
    cache = CacheSupabase(cliente)
    cache.set("suelo", "a", {"v": 1})
    cache.cerrar()
    assert cache.escrituras_fallidas == 1
    assert cache.get("suelo", "a") == {"v": 1}  # la copia en memoria sigue sirviendo


def test_entradas_de_un_espacio():
    cache = CacheSupabase(ClienteFalso([_fila("suelo_grilla", "g1"), _fila("suelo_grilla", "g2"), _fila("suelo", "s")]))
    cache.hidratar()
    assert cache.entradas("suelo_grilla") == {"g1": {"v": "g1"}, "g2": {"v": "g2"}}


def test_en_capas_completa_la_primaria_desde_supabase():
    cache = CacheSupabase(ClienteFalso([_fila("suelo", "a")]))
    cache.hidratar()
    capas = CacheEnCapas(CacheMemoria(), secundaria=cache)
    assert capas.get("suelo", "a") == {"v": "a"}
    assert capas.primaria.get("suelo", "a") == {"v": "a"}


def test_cerrar_sin_hilo_no_falla():
    CacheSupabase(ClienteFalso()).cerrar()


@pytest.mark.parametrize(
    "ajustes",
    [
        {"supabase_url": "https://x.supabase.co", "supabase_secret_key": "", "cache_persistente": True},
        {"supabase_url": "", "supabase_secret_key": "sb_secret_x", "cache_persistente": True},
        {"supabase_url": "https://x.supabase.co", "supabase_secret_key": "sb_secret_x", "cache_persistente": False},
    ],
)
def test_crear_devuelve_none_sin_credenciales_o_desactivada(ajustes):
    assert crear_cache_supabase(SimpleNamespace(**ajustes)) is None
