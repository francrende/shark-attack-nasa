"""Orquestación de ``POST /api/v1/simulate`` (BACK-7).

Une los insumos del ML (``providers.features.construir_insumos_ml``, BACK-6) con el motor de
recomendación (``ml.predictor.run_recommendation`` con ensemble de años análogos, ML-5) y
reemplaza los bloques descriptivos de la respuesta por el dato real de los providers.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from ml.predictor import run_recommendation
from providers.features import InsumosML, construir_insumos_ml
from providers.nasa_power import NasaPowerUnavailable
from schemas import SimulateRequest

ConstructorInsumos = Callable[..., Awaitable[InsumosML]]

MSG_SIN_ESCENARIOS = (
    "No hay años históricos completos de NASA POWER para la ventana futura de esta coordenada."
)


def _sin_duplicados(items: tuple[str, ...]) -> list[str]:
    return list(dict.fromkeys(items))


def armar_respuesta(insumos: InsumosML, request: SimulateRequest) -> dict[str, Any]:
    """Corre el motor de recomendación y ajusta la respuesta al contrato §5 (sin E/S)."""
    if not insumos.escenarios_historicos:
        raise NasaPowerUnavailable(MSG_SIN_ESCENARIOS)

    perfil = insumos.perfil_suelo
    topo = insumos.topografia
    what_if = request.simulacion_what_if.model_dump() if request.simulacion_what_if else None

    respuesta = run_recommendation(
        features=insumos.features_actuales,
        escenarios_historicos=insumos.escenarios_historicos,
        campana=request.campana,
        cultivo_anterior=request.cultivo_anterior,
        objetivo_productor=request.objetivo_productor,
        carbono_organico_g_kg=perfil.carbono_organico_g_kg,
        phh2o=perfil.ph,
        arena_pct=perfil.arena_pct,
        fecha_ultimo_dato_valido=insumos.fecha_corte.isoformat(),
        ubicacion={"lat": request.coordenadas.lat, "lon": request.coordenadas.lon},
        simulacion_what_if=what_if,
    )

    # Bloques descriptivos: dato satelital real, sin los topes del modelo ni el What-If.
    respuesta["telemetria_nasa"] = insumos.telemetria.model_dump(mode="json")
    respuesta["topografia_srtm"].update(
        elevacion_m=round(float(topo.elevacion_m), 1),
        pendiente_terreno_pct=round(float(topo.pendiente_terreno_pct), 1),
    )
    suelo = respuesta["perfil_suelo"]
    if perfil.textura_predominante:
        suelo["textura_predominante"] = perfil.textura_predominante
    if perfil.arcilla_pct is not None:
        suelo["arcilla_pct"] = round(float(perfil.arcilla_pct), 1)
    respuesta["advertencias"] = _sin_duplicados(insumos.advertencias)
    return respuesta


async def simular(
    request: SimulateRequest,
    *,
    construir: ConstructorInsumos = construir_insumos_ml,
    today: date | None = None,
) -> dict[str, Any]:
    """Pipeline online completo: providers en paralelo → features → ensemble ML → respuesta §5.

    Raises:
        NasaPowerUnavailable / SoilGridsUnavailable / SrtmUnavailable: provider sin datos.
    """
    insumos = await construir(request.coordenadas.lat, request.coordenadas.lon, today=today)
    return armar_respuesta(insumos, request)
