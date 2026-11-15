"""Verificación opcional contra la API real de ISRIC SoilGrids (requiere red).

Uso (desde backend/):  python -m providers.check_soilgrids_live [lat lon]
Sin argumentos consulta Pergamino (dato real) y Tres Arroyos (píxel sin dato -> vecinos/fallback).
Ojo: ISRIC permite 5 llamadas/minuto; no correrlo dos veces seguidas.
"""

import asyncio
import sys
import time

from providers.soilgrids import fetch_perfil_suelo

PUNTOS_DEFAULT = [("Pergamino", -33.95, -60.57), ("Tres Arroyos", -38.38, -60.28)]


async def main(puntos: list[tuple[str, float, float]]) -> None:
    for nombre, lat, lon in puntos:
        t0 = time.perf_counter()
        perfil = await fetch_perfil_suelo(lat, lon)
        print(f"{nombre} ({lat}, {lon}) | {time.perf_counter() - t0:.2f} s")
        for campo, valor in perfil.__dict__.items():
            print(f"  {campo:<24} {valor}")
        print()


if __name__ == "__main__":
    if len(sys.argv) == 3:
        puntos = [("Punto", float(sys.argv[1]), float(sys.argv[2]))]
    else:
        puntos = PUNTOS_DEFAULT
    asyncio.run(main(puntos))
