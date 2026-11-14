"""
Generador del Dataset de Entrenamiento, Validación y Testeo (ML-1).

Resuelve simultáneamente:
1. Cero Domain Shift: Extrae ventanas reales de 90 días a partir de 20 años de series
   diarias reales (2006-2025) de NASA POWER API (SMAP/GLDAS/GPM IMERG: PRECTOTCORR,
   GWETROOT, GWETTOP, T2M_MAX, T2M_MIN, EVPTRNS), NASA SRTM 30m (OpenTopoData) e
   ISRIC SoilGrids en 15 localidades agrícolas de Argentina, cacheadas localmente en
   `backend/ml/data/nasa_raw_telemetry.json`.
2. Cero Overfitting Espacial: Desacopla las variables estáticas (`elevacion_m`,
   `pendiente_terreno_pct`, `textura_arcilla_pct`) aplicando variabilidad continua
   intra-zona a escala de lote para impedir que los árboles memoricen coordenadas fijas.
3. Cero Data Leakage Temporal: Divide el dataset mediante bloques cronológicos estrictos
   (Out-of-Time Split):
   - Train (70% - 11.550 filas):      Campañas históricas 2006-2019
   - Validation (15% - 2.475 filas):  Campañas 2020-2022
   - Test (15% - 2.475 filas):        Campañas recientes 2023-2025
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pandas as pd

SEED = 42
SAMPLES_PER_CROP_TRAIN = 1050  # 70% de 1500
SAMPLES_PER_CROP_VAL = 225     # 15% de 1500
SAMPLES_PER_CROP_TEST = 225    # 15% de 1500

NASA_POWER_BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
OPENTOPO_BASE_URL = "https://api.opentopodata.org/v1/srtm30m"
SOILGRIDS_BASE_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"

# Las 12 features oficiales de entrada (X) definidas en CONTEXT.md (Sección 4.3)
FEATURE_COLUMNS: list[str] = [
    "gwetroot_saturacion_pct",
    "gwettop_saturacion_pct",
    "tendencia_humedad_15d_pct",
    "anomalia_lluvia_90d_pct",
    "frecuencia_tormentas_extremas",
    "frecuencia_estres_termico",
    "frecuencia_riesgo_helada",
    "indice_aridez_evaporativa",
    "pendiente_terreno_pct",
    "elevacion_m",
    "textura_arcilla_pct",
    "cultivo_candidato",
]

TARGET_COLUMN = "s_hidroclimatico"

# 15 localidades representativas de la región agrícola argentina con valores de respaldo
# (Cartas de Suelo GeoINTA / SRTM 30m) en caso de rate-limit de OpenTopoData o SoilGrids.
AGRO_LOCATIONS: list[dict[str, Any]] = [
    {
        "id": "pergamino_ba",
        "nombre": "Pergamino (Pampa Ondulada)",
        "lat": -33.89,
        "lon": -60.57,
        "fallback_elev_m": 68.0,
        "fallback_slope_pct": 1.15,
        "fallback_clay_pct": 25.4,
        "slope_spread": 0.65,
        "clay_spread": 3.5,
    },
    {
        "id": "venado_tuerto_sf",
        "nombre": "Venado Tuerto (Sur Santa Fe)",
        "lat": -33.75,
        "lon": -61.97,
        "fallback_elev_m": 112.0,
        "fallback_slope_pct": 0.75,
        "fallback_clay_pct": 23.8,
        "slope_spread": 0.45,
        "clay_spread": 3.2,
    },
    {
        "id": "marcos_juarez_cba",
        "nombre": "Marcos Juárez (Sudeste Córdoba)",
        "lat": -32.70,
        "lon": -62.10,
        "fallback_elev_m": 114.0,
        "fallback_slope_pct": 0.85,
        "fallback_clay_pct": 24.5,
        "slope_spread": 0.50,
        "clay_spread": 3.4,
    },
    {
        "id": "rio_cuarto_cba",
        "nombre": "Río Cuarto (Suroeste Córdoba)",
        "lat": -33.12,
        "lon": -64.35,
        "fallback_elev_m": 438.0,
        "fallback_slope_pct": 1.95,
        "fallback_clay_pct": 17.2,
        "slope_spread": 1.10,
        "clay_spread": 3.0,
    },
    {
        "id": "trenque_lauquen_ba",
        "nombre": "Trenque Lauquen (Pampa Arenosa)",
        "lat": -35.97,
        "lon": -62.73,
        "fallback_elev_m": 96.0,
        "fallback_slope_pct": 0.60,
        "fallback_clay_pct": 15.8,
        "slope_spread": 0.40,
        "clay_spread": 2.8,
    },
    {
        "id": "tandil_ba",
        "nombre": "Tandil (Pampa Serrana / Sudeste)",
        "lat": -37.32,
        "lon": -59.13,
        "fallback_elev_m": 188.0,
        "fallback_slope_pct": 2.85,
        "fallback_clay_pct": 27.6,
        "slope_spread": 1.45,
        "clay_spread": 4.0,
    },
    {
        "id": "balcarce_ba",
        "nombre": "Balcarce (Sudeste Bonaerense)",
        "lat": -37.85,
        "lon": -58.26,
        "fallback_elev_m": 118.0,
        "fallback_slope_pct": 2.10,
        "fallback_clay_pct": 26.8,
        "slope_spread": 1.15,
        "clay_spread": 3.8,
    },
    {
        "id": "tres_arroyos_ba",
        "nombre": "Tres Arroyos (Sur Bonaerense / Fina)",
        "lat": -38.37,
        "lon": -60.28,
        "fallback_elev_m": 108.0,
        "fallback_slope_pct": 1.25,
        "fallback_clay_pct": 24.9,
        "slope_spread": 0.70,
        "clay_spread": 3.5,
    },
    {
        "id": "chascomus_ba",
        "nombre": "Chascomús (Cuenca del Salado)",
        "lat": -35.57,
        "lon": -58.01,
        "fallback_elev_m": 18.0,
        "fallback_slope_pct": 0.30,
        "fallback_clay_pct": 33.5,
        "slope_spread": 0.25,
        "clay_spread": 4.8,
    },
    {
        "id": "parana_er",
        "nombre": "Paraná (Lomadas Entrerrianas)",
        "lat": -31.74,
        "lon": -60.51,
        "fallback_elev_m": 78.0,
        "fallback_slope_pct": 2.45,
        "fallback_clay_pct": 37.2,
        "slope_spread": 1.25,
        "clay_spread": 5.0,
    },
    {
        "id": "rafaela_sf",
        "nombre": "Rafaela (Centro Santa Fe)",
        "lat": -31.25,
        "lon": -61.49,
        "fallback_elev_m": 99.0,
        "fallback_slope_pct": 0.70,
        "fallback_clay_pct": 28.4,
        "slope_spread": 0.45,
        "clay_spread": 3.8,
    },
    {
        "id": "general_pico_lp",
        "nombre": "General Pico (Noreste La Pampa)",
        "lat": -35.66,
        "lon": -63.75,
        "fallback_elev_m": 143.0,
        "fallback_slope_pct": 0.65,
        "fallback_clay_pct": 14.9,
        "slope_spread": 0.40,
        "clay_spread": 2.7,
    },
    {
        "id": "junin_ba",
        "nombre": "Junín (Noroeste Bonaerense)",
        "lat": -34.58,
        "lon": -60.95,
        "fallback_elev_m": 81.0,
        "fallback_slope_pct": 0.80,
        "fallback_clay_pct": 21.6,
        "slope_spread": 0.50,
        "clay_spread": 3.2,
    },
    {
        "id": "azul_ba",
        "nombre": "Azul (Centro Bonaerense)",
        "lat": -36.78,
        "lon": -59.86,
        "fallback_elev_m": 136.0,
        "fallback_slope_pct": 1.35,
        "fallback_clay_pct": 29.8,
        "slope_spread": 0.80,
        "clay_spread": 4.2,
    },
    {
        "id": "victoria_er",
        "nombre": "Victoria (Sur Entre Ríos - Vertisoles)",
        "lat": -32.62,
        "lon": -60.15,
        "fallback_elev_m": 54.0,
        "fallback_slope_pct": 2.20,
        "fallback_clay_pct": 38.5,
        "slope_spread": 1.15,
        "clay_spread": 5.2,
    },
]

# Parámetros ecofisiológicos FAO GAEZ v4 / FAO-56 por cultivo
CROP_CATALOG: dict[str, dict[str, Any]] = {
    # ================= CAMPAÑA FINA (INVIERNO) =================
    "trigo": {
        "id": 0,
        "campana": "invierno",
        "gwetroot_opt_min": 48.0,
        "gwetroot_opt_max": 78.0,
        "gwetroot_crit_min": 26.0,
        "gwetroot_waterlog_max": 86.0,
        "ky_drought": 1.05,
        "ky_waterlog": 1.15,
        "heat_tol": 3.0,
        "heat_sens": 2.8,
        "frost_tol": 14.0,
        "frost_sens": 1.1,
        "aridity_opt": 0.85,
        "runoff_sens": 1.0,
        "base_potential": 96.0,
    },
    "cebada": {
        "id": 1,
        "campana": "invierno",
        "gwetroot_opt_min": 45.0,
        "gwetroot_opt_max": 74.0,
        "gwetroot_crit_min": 25.0,
        "gwetroot_waterlog_max": 80.0,
        "ky_drought": 1.00,
        "ky_waterlog": 1.55,
        "heat_tol": 2.5,
        "heat_sens": 3.0,
        "frost_tol": 12.0,
        "frost_sens": 1.3,
        "aridity_opt": 0.80,
        "runoff_sens": 1.05,
        "base_potential": 95.0,
    },
    "vicia_cobertura": {
        "id": 2,
        "campana": "invierno",
        "gwetroot_opt_min": 38.0,
        "gwetroot_opt_max": 76.0,
        "gwetroot_crit_min": 20.0,
        "gwetroot_waterlog_max": 83.0,
        "ky_drought": 0.78,
        "ky_waterlog": 1.25,
        "heat_tol": 4.0,
        "heat_sens": 2.1,
        "frost_tol": 15.0,
        "frost_sens": 0.9,
        "aridity_opt": 0.72,
        "runoff_sens": 0.70,
        "base_potential": 94.0,
    },
    "avena_cobertura": {
        "id": 3,
        "campana": "invierno",
        "gwetroot_opt_min": 36.0,
        "gwetroot_opt_max": 82.0,
        "gwetroot_crit_min": 19.0,
        "gwetroot_waterlog_max": 88.0,
        "ky_drought": 0.75,
        "ky_waterlog": 0.90,
        "heat_tol": 4.0,
        "heat_sens": 2.2,
        "frost_tol": 14.0,
        "frost_sens": 1.0,
        "aridity_opt": 0.75,
        "runoff_sens": 0.65,
        "base_potential": 94.5,
    },
    "camelina": {
        "id": 4,
        "campana": "invierno",
        "gwetroot_opt_min": 30.0,
        "gwetroot_opt_max": 70.0,
        "gwetroot_crit_min": 16.0,
        "gwetroot_waterlog_max": 81.0,
        "ky_drought": 0.65,
        "ky_waterlog": 1.40,
        "heat_tol": 4.5,
        "heat_sens": 2.0,
        "frost_tol": 18.0,
        "frost_sens": 0.7,
        "aridity_opt": 0.62,
        "runoff_sens": 0.85,
        "base_potential": 92.0,
    },
    # ================= CAMPAÑA GRUESA (VERANO) =================
    "maiz_temprano": {
        "id": 5,
        "campana": "verano",
        "gwetroot_opt_min": 56.0,
        "gwetroot_opt_max": 82.0,
        "gwetroot_crit_min": 33.0,
        "gwetroot_waterlog_max": 88.0,
        "ky_drought": 1.38,
        "ky_waterlog": 1.10,
        "heat_tol": 4.0,
        "heat_sens": 3.4,
        "frost_tol": 2.0,
        "frost_sens": 3.5,
        "aridity_opt": 1.05,
        "runoff_sens": 1.15,
        "base_potential": 97.0,
    },
    "maiz_tardio": {
        "id": 6,
        "campana": "verano",
        "gwetroot_opt_min": 45.0,
        "gwetroot_opt_max": 78.0,
        "gwetroot_crit_min": 24.0,
        "gwetroot_waterlog_max": 88.0,
        "ky_drought": 0.85,
        "ky_waterlog": 1.05,
        "heat_tol": 7.0,
        "heat_sens": 1.9,
        "frost_tol": 2.5,
        "frost_sens": 3.2,
        "aridity_opt": 0.78,
        "runoff_sens": 0.90,
        "base_potential": 94.0,
    },
    "soja_primera": {
        "id": 7,
        "campana": "verano",
        "gwetroot_opt_min": 54.0,
        "gwetroot_opt_max": 80.0,
        "gwetroot_crit_min": 31.0,
        "gwetroot_waterlog_max": 87.0,
        "ky_drought": 1.25,
        "ky_waterlog": 1.15,
        "heat_tol": 5.0,
        "heat_sens": 2.7,
        "frost_tol": 1.5,
        "frost_sens": 3.6,
        "aridity_opt": 0.96,
        "runoff_sens": 1.45,
        "base_potential": 95.5,
    },
    "soja_segunda": {
        "id": 8,
        "campana": "verano",
        "gwetroot_opt_min": 50.0,
        "gwetroot_opt_max": 78.0,
        "gwetroot_crit_min": 29.0,
        "gwetroot_waterlog_max": 86.0,
        "ky_drought": 1.28,
        "ky_waterlog": 1.20,
        "heat_tol": 5.5,
        "heat_sens": 2.6,
        "frost_tol": 1.5,
        "frost_sens": 3.8,
        "aridity_opt": 0.94,
        "runoff_sens": 1.30,
        "base_potential": 92.0,
    },
    "girasol": {
        "id": 9,
        "campana": "verano",
        "gwetroot_opt_min": 40.0,
        "gwetroot_opt_max": 70.0,
        "gwetroot_crit_min": 19.0,
        "gwetroot_waterlog_max": 78.0,
        "ky_drought": 0.72,
        "ky_waterlog": 1.65,
        "heat_tol": 8.5,
        "heat_sens": 1.5,
        "frost_tol": 2.5,
        "frost_sens": 2.8,
        "aridity_opt": 0.68,
        "runoff_sens": 1.05,
        "base_potential": 92.5,
    },
    "sorgo": {
        "id": 10,
        "campana": "verano",
        "gwetroot_opt_min": 38.0,
        "gwetroot_opt_max": 76.0,
        "gwetroot_crit_min": 16.0,
        "gwetroot_waterlog_max": 90.0,
        "ky_drought": 0.58,
        "ky_waterlog": 0.85,
        "heat_tol": 10.5,
        "heat_sens": 1.2,
        "frost_tol": 2.0,
        "frost_sens": 3.0,
        "aridity_opt": 0.62,
        "runoff_sens": 0.72,
        "base_potential": 93.5,
    },
}


def _fetch_single_location(loc: dict[str, Any]) -> dict[str, Any]:
    """Descarga 20 años de datos diarios reales de NASA POWER + SRTM + SoilGrids para una localidad."""
    lat = loc["lat"]
    lon = loc["lon"]
    params = {
        "parameters": "PRECTOTCORR,GWETROOT,GWETTOP,T2M_MAX,T2M_MIN,EVPTRNS",
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": "20060101",
        "end": "20251231",
        "format": "JSON",
    }

    with httpx.Client(timeout=45.0) as client:
        resp = client.get(NASA_POWER_BASE_URL, params=params)
        resp.raise_for_status()
        power_json = resp.json()

        # Elevación de respaldo embebida en NASA POWER (geometry.coordinates[2])
        coords = power_json.get("geometry", {}).get("coordinates", [lon, lat, loc["fallback_elev_m"]])
        elev_m = float(coords[2]) if len(coords) >= 3 and coords[2] is not None else loc["fallback_elev_m"]
        slope_pct = float(loc["fallback_slope_pct"])
        srtm_source = "nasa_power_geometry_plus_geointa_slope"

        # Intento de consulta a OpenTopoData SRTM 30m (punto central y desplazado ~100m)
        try:
            lat_offset = round(lat + 0.001, 6)
            topo_resp = client.get(
                OPENTOPO_BASE_URL,
                params={"locations": f"{lat},{lon}|{lat_offset},{lon}"},
                timeout=8.0,
            )
            if topo_resp.status_code == 200:
                results = topo_resp.json().get("results", [])
                if len(results) >= 2 and results[0].get("elevation") is not None and results[1].get("elevation") is not None:
                    e0 = float(results[0]["elevation"])
                    e1 = float(results[1]["elevation"])
                    elev_m = e0
                    calc_slope = abs(e1 - e0) / 111.0 * 100.0
                    # Combinar pendiente puntual 30m con pendiente media de cuenca para evitar ruido de píxel nulo
                    slope_pct = round(max(0.15, 0.5 * calc_slope + 0.5 * loc["fallback_slope_pct"]), 2)
                    srtm_source = "opentopodata_srtm30m"
        except Exception:
            pass

        # Intento de consulta a ISRIC SoilGrids (arcilla 0-30cm)
        clay_pct = float(loc["fallback_clay_pct"])
        soil_source = "geointa_soilgrids_calibrated"
        try:
            sg_resp = client.get(
                SOILGRIDS_BASE_URL,
                params={
                    "lon": lon,
                    "lat": lat,
                    "property": "clay",
                    "depth": "0-5cm",
                    "value": "mean",
                },
                timeout=8.0,
            )
            if sg_resp.status_code == 200:
                layers = sg_resp.json().get("properties", {}).get("layers", [])
                if layers:
                    val = layers[0].get("depths", [{}])[0].get("values", {}).get("mean")
                    if val is not None and val > 0:
                        clay_pct = round(float(val) / 10.0, 2)  # g/kg -> %
                        soil_source = "isric_soilgrids_v2"
        except Exception:
            pass

    daily_params = power_json["properties"]["parameter"]
    return {
        "id": loc["id"],
        "nombre": loc["nombre"],
        "lat": lat,
        "lon": lon,
        "elevacion_m": round(elev_m, 1),
        "pendiente_terreno_pct": round(slope_pct, 2),
        "textura_arcilla_pct": round(clay_pct, 2),
        "slope_spread": loc["slope_spread"],
        "clay_spread": loc["clay_spread"],
        "srtm_source": srtm_source,
        "soil_source": soil_source,
        "daily": daily_params,
    }


def fetch_or_load_nasa_telemetry(cache_path: Path, force_refresh: bool = False) -> list[dict[str, Any]]:
    """Carga el caché local de telemetría NASA o lo descarga desde las APIs reales si no existe."""
    if cache_path.exists() and not force_refresh:
        print(f"[Cache] Cargando telemetría histórica real de la NASA desde {cache_path.name}...")
        return json.loads(cache_path.read_text(encoding="utf-8"))

    print(f"[NASA API] Descargando 20 años (2006-2025) de series diarias reales en {len(AGRO_LOCATIONS)} localidades...")
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_loc = {
            executor.submit(_fetch_single_location, loc): loc for loc in AGRO_LOCATIONS
        }
        for future in as_completed(future_to_loc):
            loc = future_to_loc[future]
            data = future.result()
            results.append(data)
            print(
                f"  ✓ {data['nombre']} ({data['lat']}, {data['lon']}) -> "
                f"{len(data['daily']['GWETROOT'])} días | Elev: {data['elevacion_m']}m | "
                f"Pendiente: {data['pendiente_terreno_pct']}% | Arcilla: {data['textura_arcilla_pct']}%"
            )

    # Ordenar determinísticamente por orden en AGRO_LOCATIONS
    order_map = {loc["id"]: idx for idx, loc in enumerate(AGRO_LOCATIONS)}
    results.sort(key=lambda item: order_map[item["id"]])

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    print(f"[Cache] Telemetría real guardada en {cache_path} ({cache_path.stat().st_size / (1024*1024):.2f} MB)")
    return results


def extract_real_90d_windows(telemetry_list: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Convierte las series diarias crudas de 20 años de NASA POWER en ventanas históricas reales
    de 90 días (con paso de 10 días para evitar solapamiento inmediato excesivo),
    filtrando valores '-999.0' y calculando exactamente las 8 features hidroclimáticas.
    """
    window_records: list[dict[str, Any]] = []

    for loc in telemetry_list:
        daily = loc["daily"]
        dates = sorted(daily["PRECTOTCORR"].keys())

        df_loc = pd.DataFrame(
            {
                "date_str": dates,
                "prectotcorr": [float(daily["PRECTOTCORR"][d]) for d in dates],
                "gwetroot": [float(daily["GWETROOT"][d]) for d in dates],
                "gwettop": [float(daily["GWETTOP"][d]) for d in dates],
                "t2m_max": [float(daily["T2M_MAX"][d]) for d in dates],
                "t2m_min": [float(daily["T2M_MIN"][d]) for d in dates],
                "evptrns": [float(daily.get("EVPTRNS", {}).get(d, -999.0)) for d in dates],
            }
        )
        df_loc["date"] = pd.to_datetime(df_loc["date_str"], format="%Y%m%d")
        df_loc["year"] = df_loc["date"].dt.year
        df_loc["month"] = df_loc["date"].dt.month
        df_loc["doy"] = df_loc["date"].dt.day_of_year

        # Regla técnica obligatoria (CONTEXT.md 3.1.A): Filtrar lags y faltantes (-999 / < -900)
        for col in ["prectotcorr", "gwetroot", "gwettop", "t2m_max", "t2m_min", "evptrns"]:
            df_loc.loc[df_loc[col] < -900.0, col] = np.nan

        # Interpolación/forward-fill suave sobre huecos aislados de satélite
        df_loc[["prectotcorr", "gwetroot", "gwettop", "t2m_max", "t2m_min", "evptrns"]] = (
            df_loc[["prectotcorr", "gwetroot", "gwettop", "t2m_max", "t2m_min", "evptrns"]]
            .ffill()
            .bfill()
        )

        # Suma móvil de 90 días de lluvia para construir la climatología de 20 años por día del año
        df_loc["rain_90d"] = df_loc["prectotcorr"].rolling(window=90, min_periods=75).sum()
        clim_rain_by_doy = df_loc.groupby("doy")["rain_90d"].mean().to_dict()

        # Extraer ventanas reales cada 10 días desde el día 90 en adelante
        for idx in range(90, len(df_loc), 10):
            win = df_loc.iloc[idx - 89 : idx + 1]
            last_row = win.iloc[-1]
            row_15d_ago = win.iloc[-15]

            gwetroot_pct = float(last_row["gwetroot"]) * 100.0
            gwettop_pct = float(last_row["gwettop"]) * 100.0
            gwetroot_15d_ago_pct = float(row_15d_ago["gwetroot"]) * 100.0
            gwettop_15d_ago_pct = float(row_15d_ago["gwettop"]) * 100.0

            # Variación neta combinada (raíz + superficie) en los últimos 15 días válidos
            tendencia_15d_pct = 0.65 * (gwetroot_pct - gwetroot_15d_ago_pct) + 0.35 * (
                gwettop_pct - gwettop_15d_ago_pct
            )

            rain_90d = float(win["prectotcorr"].sum())
            doy = int(last_row["doy"])
            hist_rain_90d = max(25.0, float(clim_rain_by_doy.get(doy, 180.0)))
            anomalia_lluvia_90d_pct = ((rain_90d - hist_rain_90d) / hist_rain_90d) * 100.0

            tormentas_extremas = int((win["prectotcorr"] > 50.0).sum())
            estres_termico = int((win["t2m_max"] > 34.0).sum())
            riesgo_helada = int((win["t2m_min"] < 2.0).sum())

            # Demanda evaporativa acumulada en 90 días (EVPTRNS o aproximación Hargreaves si EVPTRNS<=0)
            evap_90d = float(win["evptrns"].clip(lower=0.1).sum())
            if evap_90d < 45.0:
                t_mean = 0.5 * (win["t2m_max"] + win["t2m_min"])
                evap_90d = float(np.clip(t_mean * 0.16, 1.2, 6.5).sum())

            indice_aridez = rain_90d / max(30.0, evap_90d)

            month = int(last_row["month"])
            # Asignar estación agronómica de la ventana real:
            # Meses 4..9 (Abril a Septiembre) -> ventana de campaña fina (invierno)
            # Meses 10..12 y 1..3 (Octubre a Marzo) -> ventana de campaña gruesa (verano)
            season_campana = "invierno" if 4 <= month <= 9 else "verano"

            window_records.append(
                {
                    "location_id": loc["id"],
                    "date": last_row["date_str"],
                    "year": int(last_row["year"]),
                    "month": month,
                    "season_campana": season_campana,
                    "gwetroot_saturacion_pct": round(float(np.clip(gwetroot_pct, 5.0, 99.0)), 2),
                    "gwettop_saturacion_pct": round(float(np.clip(gwettop_pct, 5.0, 99.0)), 2),
                    "tendencia_humedad_15d_pct": round(float(np.clip(tendencia_15d_pct, -40.0, 40.0)), 2),
                    "anomalia_lluvia_90d_pct": round(float(np.clip(anomalia_lluvia_90d_pct, -80.0, 140.0)), 2),
                    "frecuencia_tormentas_extremas": int(np.clip(tormentas_extremas, 0, 12)),
                    "frecuencia_estres_termico": int(np.clip(estres_termico, 0, 45)),
                    "frecuencia_riesgo_helada": int(np.clip(riesgo_helada, 0, 55)),
                    "indice_aridez_evaporativa": round(float(np.clip(indice_aridez, 0.08, 3.0)), 3),
                    "base_pendiente_pct": float(loc["pendiente_terreno_pct"]),
                    "base_elevacion_m": float(loc["elevacion_m"]),
                    "base_arcilla_pct": float(loc["textura_arcilla_pct"]),
                    "slope_spread": float(loc["slope_spread"]),
                    "clay_spread": float(loc["clay_spread"]),
                }
            )

    return pd.DataFrame(window_records)


def compute_fao_hydroclimatic_score(
    features: dict[str, Any],
    crop_name: str,
    rng: np.random.Generator | None = None,
    noise_std: float = 1.5,
) -> float:
    """
    Calcula el Puntaje de Aptitud Hidroclimática y Topográfica (S_hidroclimatico, 0 a 100)
    integrando las curvas de respuesta FAO GAEZ v4 / FAO-56 y las interacciones no lineales
    documentadas en CONTEXT.md (Sección 4.2, 4.3 y 4.4).
    """
    p = CROP_CATALOG[crop_name]

    gwetroot = float(features["gwetroot_saturacion_pct"])
    gwettop = float(features["gwettop_saturacion_pct"])
    tendencia_15d = float(features["tendencia_humedad_15d_pct"])
    anomalia_lluvia = float(features["anomalia_lluvia_90d_pct"])
    tormentas = int(features["frecuencia_tormentas_extremas"])
    estres_termico = int(features["frecuencia_estres_termico"])
    riesgo_helada = int(features["frecuencia_riesgo_helada"])
    aridez = float(features["indice_aridez_evaporativa"])
    pendiente = float(features["pendiente_terreno_pct"])
    elevacion = float(features["elevacion_m"])
    arcilla = float(features["textura_arcilla_pct"])

    # 1. Humedad efectiva en zona radicular ajustada por pérdida de infiltración en pendiente
    # y retención por textura arcillosa (interacción SRTM + SoilGrids + GPM).
    runoff_loss_pct = 0.0
    if pendiente > 1.2:
        infiltration_resistance = 1.0 + max(0.0, (arcilla - 28.0) / 35.0)
        storm_amplifier = 1.0 + 0.22 * tormentas
        runoff_loss_pct = (
            (pendiente - 1.2)
            * 1.65
            * infiltration_resistance
            * storm_amplifier
            * p["runoff_sens"]
        )

    clay_retention_bonus = np.clip((arcilla - 20.0) * 0.14, -1.8, 2.5)
    effective_gwetroot = gwetroot - 0.55 * runoff_loss_pct + clay_retention_bonus

    score = float(p["base_potential"])

    # 2. Respuesta al déficit hídrico radicular (Curva no lineal FAO-56 Ky)
    opt_min = p["gwetroot_opt_min"]
    opt_max = p["gwetroot_opt_max"]
    crit_min = p["gwetroot_crit_min"]
    ky = p["ky_drought"]

    if effective_gwetroot < opt_min:
        deficit_ratio = (opt_min - effective_gwetroot) / max(10.0, (opt_min - crit_min))
        drought_penalty = 24.0 * ky * (deficit_ratio**1.35)
        score -= drought_penalty
    elif effective_gwetroot <= opt_max:
        mid_opt = 0.5 * (opt_min + opt_max)
        half_span = max(8.0, 0.5 * (opt_max - opt_min))
        center_bonus = 2.5 * (1.0 - abs(effective_gwetroot - mid_opt) / half_span)
        score += max(0.0, center_bonus)

    # 3. Respuesta al exceso hídrico / anegamiento (GWETROOT > umbral + arcilla alta + pendiente plana)
    waterlog_max = p["gwetroot_waterlog_max"]
    if gwetroot > waterlog_max:
        excess = gwetroot - waterlog_max
        poor_drainage_factor = 1.0
        if arcilla > 32.0:
            poor_drainage_factor += (arcilla - 32.0) / 25.0
        if pendiente < 0.6:
            poor_drainage_factor += (0.6 - pendiente) * 0.65
        waterlog_penalty = (
            1.45 * p["ky_waterlog"] * (excess**1.25) * poor_drainage_factor
        )
        score -= waterlog_penalty

    # 4. Anomalía de precipitación de 90 días e Índice de Aridez Evaporativa (PRECTOTCORR / EVPTRNS)
    if anomalia_lluvia < -10.0:
        rain_def_scale = abs(anomalia_lluvia + 10.0) / 25.0
        score -= 7.2 * (ky**1.15) * rain_def_scale
    elif anomalia_lluvia > 35.0 and gwetroot > 78.0:
        score -= 4.5 * p["ky_waterlog"] * ((anomalia_lluvia - 35.0) / 30.0)

    if aridez < p["aridity_opt"]:
        aridity_gap = (p["aridity_opt"] - aridez) / max(0.35, p["aridity_opt"])
        score -= 8.0 * ky * (aridity_gap**1.2)

    # 5. Interacción crítica NO LINEAL: Golpes de Calor (T2M_MAX > 34°C) x Sequía Radicular
    if estres_termico > p["heat_tol"]:
        excess_heat_days = estres_termico - p["heat_tol"]
        moisture_stress_multiplier = 1.0
        if effective_gwetroot < 40.0:
            moisture_stress_multiplier += 1.15 * ((40.0 - effective_gwetroot) / 20.0)
        score -= excess_heat_days * p["heat_sens"] * moisture_stress_multiplier

    # 6. Riesgo de Helada (T2M_MIN < 2°C) e interacción con altitud (SRTM elevacion_m)
    effective_frost_days = float(riesgo_helada) + max(0.0, (elevacion - 220.0) / 140.0)
    if effective_frost_days > p["frost_tol"]:
        excess_frost = effective_frost_days - p["frost_tol"]
        score -= excess_frost * p["frost_sens"]

    # 7. Anomalías físicas en curso (CONTEXT.md Sección 4.4):
    # 7a. Pulso de Secado Rápido (Flash Drought Onset: tendencia_15d < -10%)
    if tendencia_15d < -10.0:
        drying_severity = abs(tendencia_15d + 10.0) / 12.0
        evap_multiplier = 1.25 if aridez < 0.65 else 1.0
        score -= 5.8 * ky * drying_severity * evap_multiplier

    # 7b. Trampa de "Falsa Recarga" Superficial (GWETTOP > 58% pero GWETROOT < 36%)
    if gwettop > 58.0 and gwetroot < 36.0:
        decouple_gap = (gwettop - gwetroot) / 25.0
        score -= 6.5 * (ky**1.3) * decouple_gap

    # 7c. Suelo superficial extremadamente seco para emergencia/implantación (GWETTOP < 22%)
    if gwettop < 22.0:
        score -= (22.0 - gwettop) * 0.45 * ky

    # 8. Penalización directa por escorrentía y tormentas torrenciales (> 50 mm/día) en pendiente
    score -= 0.75 * runoff_loss_pct

    # 9. Bonus de rusticidad defensiva en escenarios restrictivos
    if 22.0 <= gwetroot <= 42.0 and anomalia_lluvia < -12.0:
        rusticity_factor = max(0.0, 1.0 - ky)
        score += 4.0 * rusticity_factor

    # 10. Ruido gaussiano leve (±1.5 pts) para evitar sobreajuste determinístico
    if rng is not None and noise_std > 0.0:
        score += float(rng.normal(0.0, noise_std))

    return float(np.clip(round(score, 2), 0.0, 100.0))


def _build_split_from_real_windows(
    windows_df: pd.DataFrame,
    samples_per_crop: int,
    split_name: str,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Construye un split (Train, Val o Test) tomando exclusivamente ventanas reales
    del bloque de años correspondiente:
    - 85% ventanas reales de NASA POWER con desacople espacial continuo de lote (SRTM/SoilGrids)
    - 15% ventanas reales de ese mismo bloque perturbadas con escenarios What-If
      (para cubrir los extremos de los sliders de simulación y pendientes/anomalías severas).
    """
    rows: list[dict[str, Any]] = []
    n_pure_real = int(round(samples_per_crop * 0.85))
    n_what_if = samples_per_crop - n_pure_real

    for crop_name, crop_meta in CROP_CATALOG.items():
        campana = crop_meta["campana"]
        crop_id = crop_meta["id"]

        season_pool = windows_df[windows_df["season_campana"] == campana].reset_index(drop=True)
        if len(season_pool) == 0:
            season_pool = windows_df.reset_index(drop=True)

        # Estratificar selección de ventanas reales cubriendo cuartiles de humedad (secas, normales, húmedas)
        q_labels = pd.qcut(
            season_pool["gwetroot_saturacion_pct"].rank(method="first"),
            q=4,
            labels=False,
        )
        sampled_indices: list[int] = []
        per_quartile = n_pure_real // 4
        remainder = n_pure_real - (per_quartile * 4)

        for q_idx in range(4):
            q_pool = season_pool.index[q_labels == q_idx].to_numpy()
            count_q = per_quartile + (1 if q_idx < remainder else 0)
            chosen = rng.choice(q_pool, size=count_q, replace=len(q_pool) < count_q)
            sampled_indices.extend(int(i) for i in chosen)

        # 1. 85% Ventanas Reales de NASA POWER + Desacople Espacial Intra-Zona (Anti-Overfitting Espacial)
        for idx in sampled_indices:
            w = season_pool.iloc[idx]

            # Desacople espacial: mezcla entre el perfil topográfico/edáfico local y variabilidad continua de lote
            if rng.random() < 0.75:
                elev = float(np.clip(w["base_elevacion_m"] + rng.normal(0.0, 18.0), 6.0, 580.0))
                slope = float(
                    np.clip(
                        w["base_pendiente_pct"] + rng.normal(0.0, w["slope_spread"]),
                        0.05,
                        7.5,
                    )
                )
                clay = float(
                    np.clip(
                        w["base_arcilla_pct"] + rng.normal(0.0, w["clay_spread"]),
                        9.0,
                        52.0,
                    )
                )
            else:
                # Cruce con otro perfil edáfico/topográfico regional para que clima y suelo generalicen libremente
                other = AGRO_LOCATIONS[int(rng.integers(0, len(AGRO_LOCATIONS)))]
                elev = float(np.clip(other["fallback_elev_m"] + rng.normal(0.0, 22.0), 6.0, 580.0))
                slope = float(
                    np.clip(
                        rng.gamma(shape=1.6, scale=max(0.35, other["fallback_slope_pct"] * 0.75)),
                        0.05,
                        8.0,
                    )
                )
                clay = float(
                    np.clip(
                        other["fallback_clay_pct"] + rng.normal(0.0, other["clay_spread"]),
                        9.0,
                        52.0,
                    )
                )

            # Jitter mínimo de sub-celda satelital (~9km SMAP -> escala de lote)
            gwetroot = float(np.clip(w["gwetroot_saturacion_pct"] + rng.normal(0.0, 1.2), 8.0, 99.0))
            gwettop = float(np.clip(w["gwettop_saturacion_pct"] + rng.normal(0.0, 1.5), 6.0, 99.0))
            tendencia = float(np.clip(w["tendencia_humedad_15d_pct"] + rng.normal(0.0, 0.8), -38.0, 38.0))
            anomalia = float(np.clip(w["anomalia_lluvia_90d_pct"] + rng.normal(0.0, 1.5), -75.0, 130.0))
            aridez = float(np.clip(w["indice_aridez_evaporativa"] + rng.normal(0.0, 0.03), 0.08, 2.8))

            feat: dict[str, Any] = {
                "gwetroot_saturacion_pct": round(gwetroot, 2),
                "gwettop_saturacion_pct": round(gwettop, 2),
                "tendencia_humedad_15d_pct": round(tendencia, 2),
                "anomalia_lluvia_90d_pct": round(anomalia, 2),
                "frecuencia_tormentas_extremas": int(w["frecuencia_tormentas_extremas"]),
                "frecuencia_estres_termico": int(w["frecuencia_estres_termico"]),
                "frecuencia_riesgo_helada": int(w["frecuencia_riesgo_helada"]),
                "indice_aridez_evaporativa": round(aridez, 3),
                "pendiente_terreno_pct": round(slope, 2),
                "elevacion_m": round(elev, 1),
                "textura_arcilla_pct": round(clay, 2),
                "cultivo_candidato": crop_name,
                "cultivo_id": crop_id,
                "campana": campana,
                "origen_muestra": f"nasa_real_{w['year']}",
            }
            feat[TARGET_COLUMN] = compute_fao_hydroclimatic_score(
                feat, crop_name=crop_name, rng=rng, noise_std=1.5
            )
            rows.append(feat)

        # 2. 15% Ventanas Reales perturbadas con escenarios What-If (extremos de sliders y anomalías)
        what_if_indices = rng.choice(season_pool.index.to_numpy(), size=n_what_if, replace=True)
        for idx in what_if_indices:
            w = season_pool.iloc[int(idx)]
            mode = int(rng.integers(0, 4))

            gwetroot = float(w["gwetroot_saturacion_pct"])
            gwettop = float(w["gwettop_saturacion_pct"])
            tendencia = float(w["tendencia_humedad_15d_pct"])
            anomalia = float(w["anomalia_lluvia_90d_pct"])
            tormentas = int(w["frecuencia_tormentas_extremas"])
            estres = int(w["frecuencia_estres_termico"])
            helada = int(w["frecuencia_riesgo_helada"])
            aridez = float(w["indice_aridez_evaporativa"])

            if mode == 0:
                # Escenario What-If Slider Seco / La Niña Severa
                gwetroot = float(rng.uniform(12.0, 34.0))
                gwettop = float(np.clip(gwetroot + rng.normal(-4.0, 6.0), 8.0, 48.0))
                anomalia = float(np.clip(anomalia - rng.uniform(18.0, 45.0), -70.0, -15.0))
                aridez = float(np.clip(aridez * rng.uniform(0.45, 0.75), 0.12, 0.70))
                if campana == "verano":
                    estres = int(np.clip(estres + rng.integers(3, 10), 4, 22))
            elif mode == 1:
                # Escenario What-If Slider Húmedo / El Niño / Anegamiento
                gwetroot = float(rng.uniform(80.0, 97.0))
                gwettop = float(np.clip(gwetroot + rng.normal(3.0, 4.0), 75.0, 99.0))
                anomalia = float(np.clip(anomalia + rng.uniform(20.0, 50.0), 15.0, 120.0))
                tormentas = int(np.clip(tormentas + rng.integers(1, 5), 1, 9))
                aridez = float(np.clip(aridez * rng.uniform(1.25, 1.80), 1.10, 2.60))
            elif mode == 2:
                # Trampa de Falsa Recarga Superficial (GWETTOP > 60% con GWETROOT < 35%)
                gwetroot = float(rng.uniform(16.0, 34.5))
                gwettop = float(rng.uniform(60.0, 86.0))
                tendencia = float(rng.normal(3.0, 5.0))
            else:
                # Pulso de Secado Rápido (Flash Drought) en lote con pendiente elevada
                gwetroot = float(rng.uniform(22.0, 42.0))
                tendencia = float(rng.uniform(-28.0, -14.0))

            elev = float(np.clip(w["base_elevacion_m"] + rng.normal(0.0, 25.0), 8.0, 560.0))
            slope = float(np.clip(rng.gamma(shape=1.8, scale=1.35), 0.10, 8.2))
            clay = float(np.clip(w["base_arcilla_pct"] + rng.normal(0.0, 6.5), 10.0, 52.0))

            feat = {
                "gwetroot_saturacion_pct": round(gwetroot, 2),
                "gwettop_saturacion_pct": round(gwettop, 2),
                "tendencia_humedad_15d_pct": round(tendencia, 2),
                "anomalia_lluvia_90d_pct": round(anomalia, 2),
                "frecuencia_tormentas_extremas": tormentas,
                "frecuencia_estres_termico": estres,
                "frecuencia_riesgo_helada": helada,
                "indice_aridez_evaporativa": round(aridez, 3),
                "pendiente_terreno_pct": round(slope, 2),
                "elevacion_m": round(elev, 1),
                "textura_arcilla_pct": round(clay, 2),
                "cultivo_candidato": crop_name,
                "cultivo_id": crop_id,
                "campana": campana,
                "origen_muestra": f"nasa_whatif_{w['year']}",
            }
            feat[TARGET_COLUMN] = compute_fao_hydroclimatic_score(
                feat, crop_name=crop_name, rng=rng, noise_std=1.5
            )
            rows.append(feat)

    df_split = pd.DataFrame(rows)
    ordered_cols = FEATURE_COLUMNS + ["cultivo_id", "campana", "origen_muestra", TARGET_COLUMN]
    return df_split[ordered_cols].sample(frac=1.0, random_state=SEED).reset_index(drop=True)


def build_and_save_all_splits(
    windows_df: pd.DataFrame,
    output_dir: Path,
    telemetry_list: list[dict[str, Any]],
    seed: int = SEED,
) -> dict[str, Any]:
    """
    Realiza el corte Out-of-Time (por bloques de años reales de la NASA) para evitar
    Data Leakage temporal y guarda train.csv (70%), val.csv (15%) y test.csv (15%).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    # Bloques temporales estrictamente disjuntos:
    # - Train: 2006 a 2019 (14 años de historia real)
    # - Val:   2020 a 2022 (3 años de validación real, incluye La Niña 2020-2022)
    # - Test:  2023 a 2025 (3 años de testeo futuro real, incluye fin de sequía 2023 y transición 2024-2025)
    win_train = windows_df[windows_df["year"] <= 2019].copy()
    win_val = windows_df[(windows_df["year"] >= 2020) & (windows_df["year"] <= 2022)].copy()
    win_test = windows_df[windows_df["year"] >= 2023].copy()

    df_train = _build_split_from_real_windows(win_train, SAMPLES_PER_CROP_TRAIN, "train", rng)
    df_val = _build_split_from_real_windows(win_val, SAMPLES_PER_CROP_VAL, "val", rng)
    df_test = _build_split_from_real_windows(win_test, SAMPLES_PER_CROP_TEST, "test", rng)

    train_path = output_dir / "train.csv"
    val_path = output_dir / "val.csv"
    test_path = output_dir / "test.csv"

    df_train.to_csv(train_path, index=False)
    df_val.to_csv(val_path, index=False)
    df_test.to_csv(test_path, index=False)

    df_all = pd.concat([df_train, df_val, df_test], ignore_index=True)

    # Benchmark del caso testigo de CONTEXT.md (Sección 5)
    benchmark_features = {
        "gwetroot_saturacion_pct": 34.0,
        "gwettop_saturacion_pct": 28.5,
        "tendencia_humedad_15d_pct": -12.0,
        "anomalia_lluvia_90d_pct": -24.2,
        "frecuencia_tormentas_extremas": 1,
        "frecuencia_estres_termico": 6,
        "frecuencia_riesgo_helada": 0,
        "indice_aridez_evaporativa": 0.52,
        "pendiente_terreno_pct": 1.8,
        "elevacion_m": 78.5,
        "textura_arcilla_pct": 24.5,
    }
    summer_benchmark = {
        crop: compute_fao_hydroclimatic_score(
            benchmark_features, crop_name=crop, rng=None, noise_std=0.0
        )
        for crop, meta in CROP_CATALOG.items()
        if meta["campana"] == "verano"
    }

    metadata = {
        "seed": seed,
        "data_source": "NASA POWER API (2006-2025 daily SMAP/GLDAS/GPM IMERG) + NASA SRTM 30m + ISRIC SoilGrids / GeoINTA",
        "anti_overfitting_strategy": {
            "domain_shift_mitigation": "85% real 90-day NASA POWER windows (2006-2025) + 15% What-If slider perturbations over real windows",
            "spatial_overfitting_mitigation": "Continuous intra-zone & cross-zone spatial jittering on elevacion_m, pendiente_terreno_pct, and textura_arcilla_pct",
            "temporal_leakage_mitigation": "Strict Out-of-Time Temporal Block Split: Train (2006-2019), Val (2020-2022), Test (2023-2025)",
        },
        "real_nasa_windows_extracted": {
            "total_90d_windows": len(windows_df),
            "train_pool_2006_2019": len(win_train),
            "val_pool_2020_2022": len(win_val),
            "test_pool_2023_2025": len(win_test),
        },
        "locations_count": len(telemetry_list),
        "locations": [
            {
                "id": loc["id"],
                "nombre": loc["nombre"],
                "lat": loc["lat"],
                "lon": loc["lon"],
                "elevacion_m": loc["elevacion_m"],
                "pendiente_terreno_pct": loc["pendiente_terreno_pct"],
                "textura_arcilla_pct": loc["textura_arcilla_pct"],
            }
            for loc in telemetry_list
        ],
        "total_rows": len(df_all),
        "splits": {
            "train": {
                "rows": len(df_train),
                "ratio": round(len(df_train) / len(df_all), 4),
                "years": "2006-2019",
                "file": train_path.name,
            },
            "val": {
                "rows": len(df_val),
                "ratio": round(len(df_val) / len(df_all), 4),
                "years": "2020-2022",
                "file": val_path.name,
            },
            "test": {
                "rows": len(df_test),
                "ratio": round(len(df_test) / len(df_all), 4),
                "years": "2023-2025",
                "file": test_path.name,
            },
        },
        "features_12": FEATURE_COLUMNS,
        "target": TARGET_COLUMN,
        "crops_catalog": {
            k: {"id": v["id"], "campana": v["campana"]} for k, v in CROP_CATALOG.items()
        },
        "target_stats_by_crop": (
            df_all.groupby("cultivo_candidato")[TARGET_COLUMN]
            .agg(["count", "mean", "std", "min", "median", "max"])
            .round(2)
            .to_dict(orient="index")
        ),
        "context_md_drought_benchmark_summer": summer_benchmark,
    }

    metadata_path = output_dir / "dataset_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Generador de Dataset ML con Telemetría Real NASA POWER")
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Fuerza la descarga desde NASA POWER API incluso si existe nasa_raw_telemetry.json",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"
    cache_path = data_dir / "nasa_raw_telemetry.json"

    telemetry_list = fetch_or_load_nasa_telemetry(cache_path, force_refresh=args.refresh_cache)
    windows_df = extract_real_90d_windows(telemetry_list)
    metadata = build_and_save_all_splits(
        windows_df=windows_df,
        output_dir=data_dir,
        telemetry_list=telemetry_list,
        seed=SEED,
    )

    print("\n=== Dataset ML Basado en Telemetría Real NASA Generado Exitosamente ===")
    print(
        f"Ventanas reales de 90 días extraídas (2006-2025): {metadata['real_nasa_windows_extracted']['total_90d_windows']}"
    )
    print(f"Total de filas generadas: {metadata['total_rows']}")
    for split_name, info in metadata["splits"].items():
        print(
            f"  - {split_name.upper():<5} ({info['years']}): {info['rows']:>6} filas "
            f"({info['ratio']*100:.1f}%) -> {info['file']}"
        )


if __name__ == "__main__":
    main()
