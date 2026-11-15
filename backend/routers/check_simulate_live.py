"""Simulación de punta a punta con las APIs reales y el modelo real (requiere red).

Adaptado de ``check_simulate_live.py`` de BACK-7 (rama ``dolfi``, Dolfina) al ensemble de años
análogos por fase ENSO. Usa el mismo servicio que el endpoint, sin levantar el servidor.

Uso (desde ``backend/``)::

    python -m routers.check_simulate_live                         # Pergamino, antecesor soja_primera
    python -m routers.check_simulate_live -33.935 -60.579 trigo   # lat lon cultivo_anterior
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime, timezone

from schemas import SimulateRequest
from services.simulation_service import campana_vigente, simular


def main(lat: float, lon: float, cultivo_anterior: str) -> None:
    hoy = datetime.now(timezone.utc).date()
    pedido = SimulateRequest(
        coordenadas={"lat": lat, "lon": lon},
        campana=campana_vigente(hoy),
        cultivo_anterior=cultivo_anterior,
        objetivo_productor="equilibrio",
    )
    for intento in ("primera consulta", "segunda consulta (caché)"):
        t0 = time.perf_counter()
        r = asyncio.run(simular(pedido, today=hoy))
        print(f"== {intento}: {time.perf_counter() - t0:.2f} s")

    tel, topo, suelo = r["telemetria_nasa"], r["topografia_srtm"], r["perfil_suelo"]
    print(
        f"\nLote ({lat}, {lon}) · campaña {pedido.campana} · antecesor {cultivo_anterior}\n"
        f"  agua en las raíces {tel['indice_humedad_radicular_pct']}% · lluvia 90 días "
        f"{tel['anomalia_lluvia_90d_pct']:+.1f}% · riesgo de calor {tel['riesgo_termico_verano']}\n"
        f"  pendiente {topo['pendiente_terreno_pct']}% · suelo {suelo['textura_predominante']} "
        f"({suelo['arcilla_pct']}% arcilla)"
    )
    rec = r["recomendacion_principal"]
    dist = rec.get("distribucion_hidroclimatica") or {}
    print(
        f"\nRecomendación: {rec['cultivo']} ({rec['score_final']}) · {rec['secuencia_sugerida']}\n"
        f"  años análogos: {dist.get('anios_evaluados')} · desfavorables: {dist.get('anios_desfavorables')} · "
        f"P10 {dist.get('p10')} · P90 {dist.get('p90')}"
    )
    print("\nRanking:")
    for item in r["ranking_cultivos"]:
        motivo = f"  [no sembrable: {item['motivo_no_sembrable']}]" if item.get("motivo_no_sembrable") else ""
        print(f"  {item['cultivo']:<16} {item['score_final']:>6}  riesgo={item['riesgo']}{motivo}")
    print(f"\nExplicación: {rec['explicacion']}")
    if r.get("advertencias"):
        print("\nAdvertencias:", *r["advertencias"], sep="\n  - ")


if __name__ == "__main__":
    if len(sys.argv) == 4:
        main(float(sys.argv[1]), float(sys.argv[2]), sys.argv[3])
    else:
        main(-33.95, -60.57, "soja_primera")
