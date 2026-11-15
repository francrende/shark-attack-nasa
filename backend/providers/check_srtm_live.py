"""Verificación opcional contra OpenTopoData real (requiere red).

Uso (desde backend/):  python -m providers.check_srtm_live [lat lon]
Sin argumentos: Pergamino (llano), Tandil (serrano) y Paraná (lomadas).
"""

import asyncio
import sys
import time

from providers.srtm import fetch_topografia

PUNTOS_DEFAULT = [
    ("Pergamino (llano)", -33.95, -60.57),
    ("Tandil (serrano)", -37.32, -59.13),
    ("Paraná (lomadas)", -31.74, -60.51),
]


async def main(puntos: list[tuple[str, float, float]]) -> None:
    for nombre, lat, lon in puntos:
        t0 = time.perf_counter()
        topo = await fetch_topografia(lat, lon)
        print(
            f"{nombre:<20} elev={topo.elevacion_m:>6} m  pendiente={topo.pendiente_terreno_pct:>5} %  "
            f"fuente={topo.fuente} ({topo.fuente_elevacion})  {time.perf_counter() - t0:.2f}s"
        )
        for adv in topo.advertencias:
            print(f"   ⚠ {adv}")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        puntos = [("Punto", float(sys.argv[1]), float(sys.argv[2]))]
    else:
        puntos = PUNTOS_DEFAULT
    asyncio.run(main(puntos))
