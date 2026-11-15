"""Servicios de enriquecimiento edáfico y topográfico por campo (BACK-21 / BACK-22 / BACK-23).

Centraliza:
- Cálculo de materia orgánica del suelo en g/kg (``carbono_organico_g_kg × 1.724``).
- Conversión entre ``PerfilSueloSatelital`` / ``TopografiaSrtm`` y las columnas propias
  de ``public.fields``.
- Consulta paralela de SoilGrids + SRTM al crear o actualizar ubicación de un campo.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import httpx

from providers.soilgrids import PerfilSueloSatelital, SoilGridsUnavailable, fetch_perfil_suelo
from providers.srtm import SrtmUnavailable, TopografiaSrtm, fetch_topografia

FACTOR_VAN_BEMMELEN = 1.724

FieldEnricher = Callable[[float, float], Awaitable[dict[str, Any]]]


def redondear_opcional(valor: float | None, decimales: int = 1) -> float | None:
    """Redondea un número opcional preservando ``None``."""
    if valor is None:
        return None
    return round(float(valor), decimales)


def calcular_materia_organica_g_kg(carbono_organico_g_kg: float | None) -> float | None:
    """Convierte carbono orgánico del suelo (g/kg) a materia orgánica (g/kg) vía factor 1.724."""
    if carbono_organico_g_kg is None:
        return None
    return round(float(carbono_organico_g_kg) * FACTOR_VAN_BEMMELEN, 1)


def perfil_suelo_no_disponible() -> dict[str, Any]:
    """Representación de telemetría cuando SoilGrids y su respaldo fallan."""
    return {
        "textura_predominante": None,
        "arcilla_pct": None,
        "arena_pct": None,
        "limo_pct": None,
        "carbono_organico_g_kg": None,
        "materia_organica_g_kg": None,
        "ph": None,
        "fuente": "no_disponible",
        "localidad_fallback": None,
        "distancia_fuente_km": 0.0,
        "reintentar_soilgrids": True,
    }


def serializar_perfil_suelo(perfil: PerfilSueloSatelital) -> dict[str, Any]:
    """Serializa ``PerfilSueloSatelital`` para ``GET /api/v1/telemetry`` incluyendo MO."""
    carbono = redondear_opcional(perfil.carbono_organico_g_kg, 1)
    return {
        "textura_predominante": perfil.textura_predominante,
        "arcilla_pct": redondear_opcional(perfil.arcilla_pct, 1),
        "arena_pct": redondear_opcional(perfil.arena_pct, 1),
        "limo_pct": redondear_opcional(perfil.limo_pct, 1),
        "carbono_organico_g_kg": carbono,
        "materia_organica_g_kg": calcular_materia_organica_g_kg(carbono),
        "ph": redondear_opcional(perfil.ph, 2),
        "fuente": perfil.fuente,
        "localidad_fallback": perfil.localidad_fallback,
        "distancia_fuente_km": round(float(perfil.distancia_fuente_km), 2),
        "reintentar_soilgrids": bool(perfil.reintentar_soilgrids),
    }


def serializar_topografia(topo: TopografiaSrtm) -> dict[str, Any]:
    """Serializa ``TopografiaSrtm`` para ``GET /api/v1/telemetry``."""
    return {
        "elevacion_m": round(float(topo.elevacion_m), 1),
        "pendiente_terreno_pct": round(float(topo.pendiente_terreno_pct), 2),
        "fuente": topo.fuente,
        "fuente_elevacion": topo.fuente_elevacion,
        "localidad_fallback": topo.localidad_fallback,
        "distancia_fuente_km": round(float(topo.distancia_fuente_km), 2),
        "reintentar_srtm": bool(topo.reintentar_srtm),
    }


def suelo_a_columnas_field(perfil: PerfilSueloSatelital) -> dict[str, Any]:
    """Convierte ``PerfilSueloSatelital`` al diccionario de columnas propias de ``public.fields``."""
    carbono = redondear_opcional(perfil.carbono_organico_g_kg, 1)
    return {
        "ph": redondear_opcional(perfil.ph, 2),
        "limo_pct": redondear_opcional(perfil.limo_pct, 1),
        "arena_pct": redondear_opcional(perfil.arena_pct, 1),
        "arcilla_pct": redondear_opcional(perfil.arcilla_pct, 1),
        "textura_predominante": perfil.textura_predominante,
        "carbono_organico_g_kg": carbono,
        "materia_organica_g_kg": calcular_materia_organica_g_kg(carbono),
        "suelo_fuente": perfil.fuente,
        "suelo_advertencias": list(perfil.advertencias),
        "suelo_localidad_fallback": perfil.localidad_fallback,
        "suelo_distancia_fuente_km": round(float(perfil.distancia_fuente_km), 2),
        "reintentar_soilgrids": bool(perfil.reintentar_soilgrids),
    }


def suelo_no_disponible_a_columnas_field(
    advertencia: str = "Propiedades del suelo no disponibles en este momento para esta ubicación.",
) -> dict[str, Any]:
    """Columnas de ``public.fields`` cuando no fue posible obtener suelo al crear/actualizar."""
    return {
        "ph": None,
        "limo_pct": None,
        "arena_pct": None,
        "arcilla_pct": None,
        "textura_predominante": None,
        "carbono_organico_g_kg": None,
        "materia_organica_g_kg": None,
        "suelo_fuente": "no_disponible",
        "suelo_advertencias": [advertencia],
        "suelo_localidad_fallback": None,
        "suelo_distancia_fuente_km": 0.0,
        "reintentar_soilgrids": True,
    }


def topografia_a_columnas_field(topo: TopografiaSrtm) -> dict[str, Any]:
    """Convierte ``TopografiaSrtm`` al diccionario de columnas propias de ``public.fields``."""
    return {
        "elevacion_m": round(float(topo.elevacion_m), 1),
        "pendiente_terreno_pct": round(float(topo.pendiente_terreno_pct), 2),
        "fuente_elevacion": topo.fuente_elevacion,
        "topo_fuente": topo.fuente,
        "topo_advertencias": list(topo.advertencias),
        "topo_localidad_fallback": topo.localidad_fallback,
        "topo_distancia_fuente_km": round(float(topo.distancia_fuente_km), 2),
        "reintentar_srtm": bool(topo.reintentar_srtm),
    }


def topografia_no_disponible_a_columnas_field(
    advertencia: str = "Topografía SRTM no disponible en este momento para esta ubicación.",
) -> dict[str, Any]:
    """Columnas de ``public.fields`` cuando no fue posible obtener topografía."""
    return {
        "elevacion_m": None,
        "pendiente_terreno_pct": None,
        "fuente_elevacion": None,
        "topo_fuente": "no_disponible",
        "topo_advertencias": [advertencia],
        "topo_localidad_fallback": None,
        "topo_distancia_fuente_km": 0.0,
        "reintentar_srtm": True,
    }


def tiene_suelo_propio_valido(row: Mapping[str, Any]) -> bool:
    """Indica si una fila de ``public.fields`` ya tiene suelo definitivo (no requiere reintento)."""
    if row.get("reintentar_soilgrids") is not False:
        return False
    fuente = row.get("suelo_fuente")
    if not fuente or fuente == "no_disponible":
        return False
    return (
        row.get("arcilla_pct") is not None
        or row.get("carbono_organico_g_kg") is not None
        or row.get("textura_predominante") is not None
    )


def tiene_topografia_propia_valida(row: Mapping[str, Any]) -> bool:
    """Indica si una fila de ``public.fields`` ya tiene topografía definitiva (sin reintento)."""
    if row.get("reintentar_srtm") is not False:
        return False
    fuente = row.get("topo_fuente")
    if not fuente or fuente == "no_disponible":
        return False
    return row.get("elevacion_m") is not None and row.get("pendiente_terreno_pct") is not None


def columnas_field_a_perfil_telemetria(
    row: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Convierte las columnas propias de suelo de ``public.fields`` a ``PerfilSueloTelemetriaOut``."""
    carbono = redondear_opcional(row.get("carbono_organico_g_kg"), 1)
    materia_organica = row.get("materia_organica_g_kg")
    if materia_organica is None:
        materia_organica = calcular_materia_organica_g_kg(carbono)
    else:
        materia_organica = redondear_opcional(materia_organica, 1)

    advertencias = [str(a) for a in (row.get("suelo_advertencias") or [])]
    perfil = {
        "textura_predominante": row.get("textura_predominante"),
        "arcilla_pct": redondear_opcional(row.get("arcilla_pct"), 1),
        "arena_pct": redondear_opcional(row.get("arena_pct"), 1),
        "limo_pct": redondear_opcional(row.get("limo_pct"), 1),
        "carbono_organico_g_kg": carbono,
        "materia_organica_g_kg": materia_organica,
        "ph": redondear_opcional(row.get("ph"), 2),
        "fuente": str(row.get("suelo_fuente") or "no_disponible"),
        "localidad_fallback": row.get("suelo_localidad_fallback"),
        "distancia_fuente_km": round(float(row.get("suelo_distancia_fuente_km") or 0.0), 2),
        "reintentar_soilgrids": bool(row.get("reintentar_soilgrids", False)),
    }
    return perfil, advertencias


def columnas_field_a_topografia_telemetria(
    row: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Convierte las columnas topográficas de ``public.fields`` a ``TopografiaTelemetriaOut``."""
    advertencias = [str(a) for a in (row.get("topo_advertencias") or [])]
    topo = {
        "elevacion_m": round(float(row["elevacion_m"]), 1),
        "pendiente_terreno_pct": round(float(row["pendiente_terreno_pct"]), 2),
        "fuente": str(row.get("topo_fuente") or "no_disponible"),
        "fuente_elevacion": row.get("fuente_elevacion"),
        "localidad_fallback": row.get("topo_localidad_fallback"),
        "distancia_fuente_km": round(float(row.get("topo_distancia_fuente_km") or 0.0), 2),
        "reintentar_srtm": bool(row.get("reintentar_srtm", False)),
    }
    return topo, advertencias


async def enriquecer_datos_campo(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Consulta SoilGrids y SRTM en paralelo y devuelve las columnas listas para ``public.fields``.

    Nunca lanza excepción por caída de proveedores: si alguno falla, deja sus valores
    en ``None`` con ``reintentar_* = True`` para reintentar al seleccionar el campo.
    """

    async def _consultar(shared_client: httpx.AsyncClient):
        return await asyncio.gather(
            fetch_perfil_suelo(lat, lon, client=shared_client),
            fetch_topografia(lat, lon, client=shared_client),
            return_exceptions=True,
        )

    if client is None:
        async with httpx.AsyncClient() as propio:
            suelo_res, topo_res = await _consultar(propio)
    else:
        suelo_res, topo_res = await _consultar(client)

    for res in (suelo_res, topo_res):
        if isinstance(res, ValueError):
            raise res

    if isinstance(suelo_res, (SoilGridsUnavailable, BaseException)):
        columnas_suelo = suelo_no_disponible_a_columnas_field()
    else:
        columnas_suelo = suelo_a_columnas_field(suelo_res)

    if isinstance(topo_res, (SrtmUnavailable, BaseException)):
        columnas_topo = topografia_no_disponible_a_columnas_field()
    else:
        columnas_topo = topografia_a_columnas_field(topo_res)

    return {**columnas_suelo, **columnas_topo}
