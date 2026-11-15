"""Generación offline de los datos precargados (BACK-4).

Uso (desde backend/):
    python -m providers.generar_precache nasa    # climatología + días de calor por celda pampeana
    python -m providers.generar_precache suelo   # perfil SoilGrids de los lotes de ejemplo
    python -m providers.generar_precache grilla  # BACK-19: grilla de suelo ISRIC (~100 km) -> Supabase
    python -m providers.generar_precache subir-clima [--forzar]  # BACK-26: JSON de celdas -> Supabase

Ambos son secuenciales (las consultas en paralelo a NASA POWER se colgaban y ISRIC limita a
5 llamadas/minuto), reanudables (saltean lo ya generado con la versión vigente) y guardan
el progreso a medida que avanzan.
"""

from __future__ import annotations

import asyncio
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from providers.cache import PASO_LAT_POWER, PASO_LON_POWER, clave_celda_power
from providers.nasa_power import fetch_daily_range
from providers.nasa_telemetry import (
    ANALOGOS_START,
    HIST_END,
    HIST_PARAMETROS,
    HIST_START,
    RUTA_PRECALCULO,
    VERSION_CALCULO,
    calcular_referencia,
    referencia_a_dict,
)
from providers.cache import clave_coordenada
from providers.soilgrids import (
    ESPACIO_GRILLA,
    RUTA_LOTES_EJEMPLO,
    _armar_perfil,
    _consultar,
    _haversine_km,
    _vecinos,
    fetch_perfil_suelo,
    perfil_a_dict,
)

# Región pampeana (centros de celda de la grilla de NASA POWER)
LAT_MIN, LAT_MAX = -39.0, -28.0
LON_MIN, LON_MAX = -65.0, -57.5
TIMEOUT_CELDA_S = 90.0
GUARDAR_CADA = 10

# Lotes de ejemplo que ofrece el frontend en el mapa (a confirmar con el track de frontend)
LOTES_EJEMPLO = [
    ("Pergamino (Pampa Ondulada)", -33.95, -60.57),
    ("Marcos Juárez (Sudeste Córdoba)", -32.70, -62.10),
    ("Balcarce (Sudeste Bonaerense)", -37.85, -58.26),
    ("Rafaela (Centro Santa Fe)", -31.25, -61.49),
]
FUENTES_REALES = {"isric_soilgrids_v2", "isric_soilgrids_v2_vecino"}


def _rango(desde: float, hasta: float, paso: float) -> list[float]:
    n = round((hasta - desde) / paso)
    return [round(desde + i * paso, 4) for i in range(n + 1)]


def celdas_pampeanas() -> list[tuple[float, float]]:
    return [(la, lo) for la in _rango(LAT_MIN, LAT_MAX, PASO_LAT_POWER) for lo in _rango(LON_MIN, LON_MAX, PASO_LON_POWER)]


def _leer(ruta: Path, clave_raiz: str, vacio: Any) -> dict[str, Any]:
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {clave_raiz: vacio}


def _guardar(ruta: Path, datos: dict[str, Any]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(ruta)


async def generar_nasa(ruta: Path = RUTA_PRECALCULO) -> None:
    datos = _leer(ruta, "celdas", {})
    celdas: dict[str, Any] = {
        k: v for k, v in datos.get("celdas", {}).items() if v.get("version_calculo") == VERSION_CALCULO
    }
    pendientes = [(la, lo) for la, lo in celdas_pampeanas() if clave_celda_power(la, lo) not in celdas]
    total = len(celdas) + len(pendientes)
    print(f"Celdas: {total} | ya generadas: {len(celdas)} | pendientes: {len(pendientes)}", flush=True)

    def _persistir() -> None:
        _guardar(
            ruta,
            {
                "version_calculo": VERSION_CALCULO,
                "generado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "fuente": (
                    f"NASA POWER daily {ANALOGOS_START}..{HIST_END} ({', '.join(HIST_PARAMETROS)}); "
                    f"climatología y días de calor {HIST_START}..{HIST_END}"
                ),
                "region": {"lat": [LAT_MIN, LAT_MAX], "lon": [LON_MIN, LON_MAX]},
                "celdas": celdas,
            },
        )

    fallidas: list[str] = []
    async with httpx.AsyncClient() as client:
        for i, (la, lo) in enumerate(pendientes, start=1):
            clave = clave_celda_power(la, lo)
            t0 = time.perf_counter()
            try:
                serie = await asyncio.wait_for(
                    fetch_daily_range(la, lo, ANALOGOS_START, HIST_END, HIST_PARAMETROS, client=client),
                    timeout=TIMEOUT_CELDA_S,
                )
                entrada = referencia_a_dict(calcular_referencia(serie))
                celdas[clave] = entrada
                print(
                    f"[{len(celdas)}/{total}] {clave}  días>34°C={entrada['dias_calor_verano_promedio']:>5}  "
                    f"{entrada['riesgo_termico_verano']:<8} {time.perf_counter() - t0:.1f}s",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001 - se informa y se sigue
                fallidas.append(clave)
                print(f"[ERROR] {clave}: {type(exc).__name__}: {exc}", flush=True)
            if i % GUARDAR_CADA == 0:
                _persistir()
    _persistir()
    print(f"Listo: {len(celdas)} celdas en {ruta}. Fallidas: {len(fallidas)} {fallidas}", flush=True)
    if fallidas:
        print("Volvé a correr el comando para reintentar solo las fallidas.", flush=True)


async def generar_suelo(ruta: Path = RUTA_LOTES_EJEMPLO) -> None:
    datos = _leer(ruta, "lotes", [])
    existentes = {(l["lat"], l["lon"]): l for l in datos.get("lotes", [])}
    lotes = list(existentes.values())

    async with httpx.AsyncClient() as client:
        for nombre, lat, lon in LOTES_EJEMPLO:
            if (lat, lon) in existentes:
                print(f"{nombre}: ya generado", flush=True)
                continue
            t0 = time.perf_counter()
            perfil = await fetch_perfil_suelo(lat, lon, client=client)
            if perfil.fuente not in FUENTES_REALES:
                print(
                    f"{nombre}: SIN DATO REAL ({perfil.fuente}, {time.perf_counter() - t0:.1f}s) -> no se guarda. "
                    "Reintentar cuando ISRIC responda (esperá 5 min si se activó el corte automático).",
                    flush=True,
                )
                continue
            lotes.append({"nombre": nombre, "lat": lat, "lon": lon, "perfil": perfil_a_dict(perfil)})
            _guardar(ruta, {"generado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "lotes": lotes})
            print(
                f"{nombre}: OK {perfil.textura_predominante}, arcilla {perfil.arcilla_pct}%, "
                f"soc {perfil.carbono_organico_g_kg} g/kg ({time.perf_counter() - t0:.1f}s)",
                flush=True,
            )
            await asyncio.sleep(13)  # holgura para el límite de 5 llamadas/minuto de ISRIC
    print(f"Lotes guardados: {len(lotes)}/{len(LOTES_EJEMPLO)} en {ruta}", flush=True)


# ---------------------------------------------------------------------------
# BACK-19: grilla de suelo ISRIC cada ~100 km, guardada solo en Supabase (provider_cache)
# ---------------------------------------------------------------------------

# Mismos polígonos que usa el selector de provincias del frontend (solo lectura).
RUTA_PROVINCIAS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "data" / "argentinaProvinces.json"
PASO_GRILLA_KM = 100.0
KM_POR_GRADO_LAT = 111.0
TIMEOUT_GRILLA_S = 60.0  # offline: se puede esperar a ISRIC
SEPARACION_LLAMADAS_S = 13.0  # holgura para el límite de 5 llamadas/minuto de ISRIC


def _punto_en_anillo(lon: float, lat: float, anillo: list[list[float]]) -> bool:
    dentro = False
    j = len(anillo) - 1
    for i in range(len(anillo)):
        xi, yi = anillo[i][0], anillo[i][1]
        xj, yj = anillo[j][0], anillo[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def _poligonos_habilitados(ruta: Path) -> list[list[list[list[float]]]]:
    """Polígonos (anillos GeoJSON [lon, lat]) de las provincias con ``enabled = true``."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    poligonos = []
    for feature in datos["features"]:
        if not feature["properties"].get("enabled"):
            continue
        geom = feature["geometry"]
        poligonos += [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    return poligonos


def _en_poligono(lon: float, lat: float, anillos: list[list[list[float]]]) -> bool:
    if not anillos or not _punto_en_anillo(lon, lat, anillos[0]):
        return False
    return not any(_punto_en_anillo(lon, lat, hueco) for hueco in anillos[1:])


def puntos_grilla(ruta: Path = RUTA_PROVINCIAS, paso_km: float = PASO_GRILLA_KM) -> list[tuple[float, float]]:
    """Puntos (lat, lon) cada ``paso_km`` dentro de las provincias habilitadas en el frontend.

    En latitud el paso es fijo; en longitud se ajusta por cos(lat) para que la separación
    real sea ~``paso_km`` en todas las filas.
    """
    poligonos = _poligonos_habilitados(ruta)
    todos = [c for p in poligonos for c in p[0]]
    lat_min, lat_max = min(c[1] for c in todos), max(c[1] for c in todos)
    lon_min, lon_max = min(c[0] for c in todos), max(c[0] for c in todos)
    paso_lat = paso_km / KM_POR_GRADO_LAT
    puntos = []
    lat = lat_min + paso_lat / 2
    while lat < lat_max:
        paso_lon = paso_km / (KM_POR_GRADO_LAT * math.cos(math.radians(lat)))
        lon = lon_min + paso_lon / 2
        while lon < lon_max:
            if any(_en_poligono(lon, lat, p) for p in poligonos):
                puntos.append((round(lat, 4), round(lon, 4)))
            lon += paso_lon
        lat += paso_lat
    return puntos


async def _perfil_isric_offline(client: httpx.AsyncClient, lat: float, lon: float) -> tuple[dict | None, str]:
    """Perfil real del punto (o de un vecino a 500 m si el píxel es urbano o agua).

    Devuelve (perfil_dict o None, detalle). Respeta el límite de 5 llamadas/minuto de ISRIC.
    """
    for i, (qlat, qlon) in enumerate([(lat, lon)] + _vecinos(lat, lon)):
        if i:
            await asyncio.sleep(SEPARACION_LLAMADAS_S)
        estado, valores, detalle = await _consultar(client, qlat, qlon, timeout_s=TIMEOUT_GRILLA_S)
        if estado == "error":
            return None, detalle
        if estado == "ok":
            fuente = "isric_soilgrids_v2" if i == 0 else "isric_soilgrids_v2_vecino"
            perfil = _armar_perfil(valores, fuente, _haversine_km(lat, lon, qlat, qlon))  # type: ignore[arg-type]
            return perfil_a_dict(perfil), fuente
    return None, "píxel y vecinos sin dato"


async def generar_grilla() -> None:
    from config import get_settings
    from providers.cache_supabase import crear_cache_supabase

    cache = crear_cache_supabase(get_settings())
    if cache is None:
        print("Falta SUPABASE_SECRET_KEY (o SUPABASE_URL) en backend/.env: la grilla vive solo en Supabase.")
        sys.exit(1)
    cache.hidratar(timeout_s=30)
    existentes = cache.entradas(ESPACIO_GRILLA)
    puntos = puntos_grilla()
    pendientes = [(la, lo) for la, lo in puntos if clave_coordenada(la, lo) not in existentes]
    print(
        f"Puntos de grilla: {len(puntos)} | ya en Supabase: {len(puntos) - len(pendientes)} | "
        f"pendientes: {len(pendientes)} (~{len(pendientes) * SEPARACION_LLAMADAS_S / 60:.0f} min)",
        flush=True,
    )

    fallidos: list[str] = []
    async with httpx.AsyncClient() as client:
        for i, (lat, lon) in enumerate(pendientes, start=1):
            t0 = time.perf_counter()
            perfil, detalle = await _perfil_isric_offline(client, lat, lon)
            clave = clave_coordenada(lat, lon)
            if perfil is None:
                fallidos.append(clave)
                print(f"[{i}/{len(pendientes)}] {clave}: SIN DATO ({detalle}, {time.perf_counter() - t0:.1f}s)", flush=True)
            else:
                cache.set(ESPACIO_GRILLA, clave, {"lat": lat, "lon": lon, "perfil": perfil})
                print(
                    f"[{i}/{len(pendientes)}] {clave}: {perfil['textura_predominante']}, "
                    f"arcilla {perfil['arcilla_pct']}%, soc {perfil['carbono_organico_g_kg']} g/kg "
                    f"({detalle}, {time.perf_counter() - t0:.1f}s)",
                    flush=True,
                )
            if i < len(pendientes):
                await asyncio.sleep(max(0.0, SEPARACION_LLAMADAS_S - (time.perf_counter() - t0)))
    cache.cerrar(timeout_s=30)
    print(
        f"Listo. Guardados: {len(pendientes) - len(fallidos)} | sin dato: {len(fallidos)} | "
        f"escrituras fallidas en Supabase: {cache.escrituras_fallidas}",
        flush=True,
    )
    if fallidos:
        print("Volvé a correr el comando para reintentar solo los que faltan.", flush=True)


# ---------------------------------------------------------------------------
# BACK-26: clima histórico por celda (climatologia_pampa.json) -> Supabase (provider_cache)
# ---------------------------------------------------------------------------


def subir_clima(forzar: bool = False, ruta: Path = RUTA_PRECALCULO) -> None:
    """Sube las celdas vigentes del JSON a ``provider_cache`` (espacio ``nasa_hist``).

    Reanudable: saltea las claves que ya están, salvo con ``--forzar`` (por ejemplo, después de
    regenerar el JSON con otra ``version_calculo``).
    """
    from config import get_settings
    from providers.cache_supabase import crear_cache_supabase
    from providers.nasa_telemetry import ESPACIO_HIST

    cache = crear_cache_supabase(get_settings())
    if cache is None:
        print("Falta SUPABASE_SECRET_KEY (o SUPABASE_URL) en backend/.env.")
        sys.exit(1)
    datos = _leer(ruta, "celdas", {})
    celdas = {k: v for k, v in datos.get("celdas", {}).items() if v.get("version_calculo") == VERSION_CALCULO}
    existentes = set() if forzar else cache.claves(ESPACIO_HIST)
    pendientes = {k: v for k, v in celdas.items() if k not in existentes}
    print(
        f"Celdas vigentes ({VERSION_CALCULO}): {len(celdas)} | ya en Supabase: {len(celdas) - len(pendientes)} | "
        f"a subir: {len(pendientes)}",
        flush=True,
    )
    claves = sorted(pendientes)
    lote = 10
    for i in range(0, len(claves), lote):
        cache.escribir_directo(ESPACIO_HIST, {k: pendientes[k] for k in claves[i : i + lote]}, tam_lote=lote)
        print(f"  {min(i + lote, len(claves))}/{len(claves)}", flush=True)
    total = len(cache.claves(ESPACIO_HIST))
    print(f"Listo. Filas nasa_hist en Supabase: {total}", flush=True)


if __name__ == "__main__":
    comando = sys.argv[1] if len(sys.argv) > 1 else ""
    if comando == "nasa":
        asyncio.run(generar_nasa())
    elif comando == "suelo":
        asyncio.run(generar_suelo())
    elif comando == "grilla":
        asyncio.run(generar_grilla())
    elif comando == "subir-clima":
        subir_clima(forzar="--forzar" in sys.argv[2:])
    else:
        print(__doc__)
        sys.exit(1)
