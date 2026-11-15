"""Datos regionales de respaldo compartidos por los providers (BACK-5).

Tabla de 15 localidades agrícolas calibradas con Cartas de Suelo GeoINTA / SRTM. Es una
copia de ``AGRO_LOCATIONS`` (backend/ml/generate_dataset.py): se copia en lugar de importarla
para no acoplarse a un archivo de otro track.
"""

from __future__ import annotations

import math
from typing import Any

RADIO_FALLBACK_KM = 100.0

LOCALIDADES_GEOINTA: tuple[dict[str, Any], ...] = (
    {"id": "pergamino_ba", "nombre": "Pergamino (Pampa Ondulada)", "lat": -33.89, "lon": -60.57, "arcilla_pct": 25.4, "pendiente_pct": 1.15, "elevacion_m": 68.0},
    {"id": "venado_tuerto_sf", "nombre": "Venado Tuerto (Sur Santa Fe)", "lat": -33.75, "lon": -61.97, "arcilla_pct": 23.8, "pendiente_pct": 0.75, "elevacion_m": 112.0},
    {"id": "marcos_juarez_cba", "nombre": "Marcos Juárez (Sudeste Córdoba)", "lat": -32.70, "lon": -62.10, "arcilla_pct": 24.5, "pendiente_pct": 0.85, "elevacion_m": 114.0},
    {"id": "rio_cuarto_cba", "nombre": "Río Cuarto (Suroeste Córdoba)", "lat": -33.12, "lon": -64.35, "arcilla_pct": 17.2, "pendiente_pct": 1.95, "elevacion_m": 438.0},
    {"id": "trenque_lauquen_ba", "nombre": "Trenque Lauquen (Pampa Arenosa)", "lat": -35.97, "lon": -62.73, "arcilla_pct": 15.8, "pendiente_pct": 0.60, "elevacion_m": 96.0},
    {"id": "tandil_ba", "nombre": "Tandil (Pampa Serrana / Sudeste)", "lat": -37.32, "lon": -59.13, "arcilla_pct": 27.6, "pendiente_pct": 2.85, "elevacion_m": 188.0},
    {"id": "balcarce_ba", "nombre": "Balcarce (Sudeste Bonaerense)", "lat": -37.85, "lon": -58.26, "arcilla_pct": 26.8, "pendiente_pct": 2.10, "elevacion_m": 118.0},
    {"id": "tres_arroyos_ba", "nombre": "Tres Arroyos (Sur Bonaerense / Fina)", "lat": -38.37, "lon": -60.28, "arcilla_pct": 24.9, "pendiente_pct": 1.25, "elevacion_m": 108.0},
    {"id": "chascomus_ba", "nombre": "Chascomús (Cuenca del Salado)", "lat": -35.57, "lon": -58.01, "arcilla_pct": 33.5, "pendiente_pct": 0.30, "elevacion_m": 18.0},
    {"id": "parana_er", "nombre": "Paraná (Lomadas Entrerrianas)", "lat": -31.74, "lon": -60.51, "arcilla_pct": 37.2, "pendiente_pct": 2.45, "elevacion_m": 78.0},
    {"id": "rafaela_sf", "nombre": "Rafaela (Centro Santa Fe)", "lat": -31.25, "lon": -61.49, "arcilla_pct": 28.4, "pendiente_pct": 0.70, "elevacion_m": 99.0},
    {"id": "general_pico_lp", "nombre": "General Pico (Noreste La Pampa)", "lat": -35.66, "lon": -63.75, "arcilla_pct": 14.9, "pendiente_pct": 0.65, "elevacion_m": 143.0},
    {"id": "junin_ba", "nombre": "Junín (Noroeste Bonaerense)", "lat": -34.58, "lon": -60.95, "arcilla_pct": 21.6, "pendiente_pct": 0.80, "elevacion_m": 81.0},
    {"id": "azul_ba", "nombre": "Azul (Centro Bonaerense)", "lat": -36.78, "lon": -59.86, "arcilla_pct": 29.8, "pendiente_pct": 1.35, "elevacion_m": 136.0},
    {"id": "victoria_er", "nombre": "Victoria (Sur Entre Ríos - Vertisoles)", "lat": -32.62, "lon": -60.15, "arcilla_pct": 38.5, "pendiente_pct": 2.20, "elevacion_m": 54.0},
)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def localidad_mas_cercana(
    lat: float, lon: float, radio_km: float = RADIO_FALLBACK_KM
) -> tuple[dict[str, Any], float] | None:
    """Localidad GeoINTA más cercana y su distancia en km, o ``None`` si está a más de ``radio_km``."""
    mejor = min(
        ((loc, haversine_km(lat, lon, loc["lat"], loc["lon"])) for loc in LOCALIDADES_GEOINTA),
        key=lambda par: par[1],
    )
    return mejor if mejor[1] <= radio_km else None
