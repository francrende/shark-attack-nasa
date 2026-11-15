"""Verificación opcional de construir_insumos_ml contra las APIs reales (requiere red).

Uso (desde backend/):  python -m providers.check_features_live [lat lon]
"""

import asyncio
import statistics
import sys
import time

from providers.features import FEATURES_FUTURAS, construir_insumos_ml


async def main(lat: float, lon: float) -> None:
    t0 = time.perf_counter()
    ins = await construir_insumos_ml(lat, lon)
    print(f"Insumos ML @ ({lat}, {lon}) | corte {ins.fecha_corte} | {time.perf_counter() - t0:.2f} s\n")
    print("features_actuales:")
    for k, v in ins.features_actuales.items():
        print(f"  {k:<28} {v}")
    print(f"\nescenarios_historicos: {len(ins.escenarios_historicos)} años")
    for feat in FEATURES_FUTURAS:
        vals = [e[feat] for e in ins.escenarios_historicos]
        print(f"  {feat:<30} min={min(vals):>3} mediana={statistics.median(vals):>5} max={max(vals):>3}")
    print("\nfuentes:", ins.perfil_suelo.fuente, "|", ins.topografia.fuente)
    for adv in ins.advertencias:
        print("  ⚠", adv)


if __name__ == "__main__":
    lat, lon = (float(sys.argv[1]), float(sys.argv[2])) if len(sys.argv) == 3 else (-33.95, -60.57)
    asyncio.run(main(lat, lon))
