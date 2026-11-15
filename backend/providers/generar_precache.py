"""Generación offline de los datos precargados (BACK-4).

Uso (desde backend/):
    python -m providers.generar_precache nasa    # climatología + días de calor por celda pampeana
    python -m providers.generar_precache suelo   # perfil SoilGrids de los lotes de ejemplo

Ambos son secuenciales (las consultas en paralelo a NASA POWER se colgaban y ISRIC limita a
5 llamadas/minuto), reanudables (saltean lo ya generado con la versión vigente) y guardan
el progreso a medida que avanzan.
"""

from __future__ import annotations

import asyncio
import json
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
from providers.soilgrids import RUTA_LOTES_EJEMPLO, fetch_perfil_suelo, perfil_a_dict

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


if __name__ == "__main__":
    comando = sys.argv[1] if len(sys.argv) > 1 else ""
    if comando == "nasa":
        asyncio.run(generar_nasa())
    elif comando == "suelo":
        asyncio.run(generar_suelo())
    else:
        print(__doc__)
        sys.exit(1)
