"""Tests de la caché enchufable (BACK-4)."""

import pytest

from providers.cache import CacheEnCapas, CacheMemoria, centro_celda_power, clave_coordenada


class Reloj:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_memoria_get_set_y_ttl():
    reloj = Reloj()
    c = CacheMemoria(reloj=reloj)
    c.set("e", "k", {"a": 1}, ttl_s=10)
    c.set("e", "sin_ttl", [1, 2])
    assert c.get("e", "k") == {"a": 1}
    reloj.t = 9.99
    assert c.get("e", "k") == {"a": 1}
    reloj.t = 10
    assert c.get("e", "k") is None
    assert c.get("e", "sin_ttl") == [1, 2]
    assert c.get("otro_espacio", "k") is None


def test_memoria_exige_json_y_devuelve_copias():
    c = CacheMemoria()
    with pytest.raises(TypeError):
        c.set("e", "k", {"fecha": object()})
    original = {"lista": [1]}
    c.set("e", "k", original)
    original["lista"].append(2)
    leido = c.get("e", "k")
    leido["lista"].append(3)
    assert c.get("e", "k") == {"lista": [1]}


def test_capas_rellena_primaria_desde_secundaria_con_ttl_del_espacio():
    reloj = Reloj()
    primaria, secundaria = CacheMemoria(reloj=reloj), CacheMemoria(reloj=reloj)
    capas = CacheEnCapas(primaria, secundaria, ttl_por_espacio={"reciente": 100})
    secundaria.set("reciente", "k", {"v": 1})
    secundaria.set("hist", "k", {"v": 2})

    assert capas.get("reciente", "k") == {"v": 1}
    assert capas.get("hist", "k") == {"v": 2}
    assert primaria.get("reciente", "k") == {"v": 1}

    reloj.t = 100
    secundaria.set("reciente", "k", {"v": 9})
    assert primaria.get("reciente", "k") is None  # venció en la primaria
    assert primaria.get("hist", "k") == {"v": 2}  # sin TTL
    assert capas.get("reciente", "k") == {"v": 9}


def test_capas_set_escribe_en_ambas():
    primaria, secundaria = CacheMemoria(), CacheMemoria()
    CacheEnCapas(primaria, secundaria).set("e", "k", 1)
    assert primaria.get("e", "k") == 1 and secundaria.get("e", "k") == 1


def test_capas_sin_secundaria():
    capas = CacheEnCapas(CacheMemoria())
    assert capas.get("e", "k") is None
    capas.set("e", "k", 1)
    assert capas.get("e", "k") == 1


def test_clave_coordenada_redondea_a_3_decimales():
    assert clave_coordenada(-33.95041, -60.56968) == "-33.950,-60.570"
    assert clave_coordenada(-0.0001, 0.0) == "0.000,0.000"  # sin "-0.000"


def test_centro_celda_power():
    assert centro_celda_power(-33.95, -60.57) == (-34.0, -60.625)
    assert centro_celda_power(-33.70, -60.57) == (-33.5, -60.625)
