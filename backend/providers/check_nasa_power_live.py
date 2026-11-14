"""Verificación opcional contra la API real de NASA POWER (requiere red).

Uso (desde backend/):  python -m providers.check_nasa_power_live [lat lon]
"""

import asyncio
import sys

from providers.nasa_power import PARAMETROS, fetch_daily_window


async def main(lat: float, lon: float) -> None:
    serie = await fetch_daily_window(lat, lon)
    print(f"NASA POWER @ ({lat}, {lon}) | ventana {serie.start} -> {serie.end}")
    for param in PARAMETROS:
        valores = serie.series.get(param, {})
        invalidos = sum(1 for v in valores.values() if v is None)
        ultimo = serie.last_valid(param)
        texto = f"{ultimo[1]:>8.3f} ({ultimo[0]})" if ultimo else "     sin datos válidos"
        print(f"  {param:<18} {texto} | -999 en ventana: {invalidos}/{len(valores)}")


if __name__ == "__main__":
    lat, lon = (float(sys.argv[1]), float(sys.argv[2])) if len(sys.argv) == 3 else (-33.95, -60.57)
    asyncio.run(main(lat, lon))
