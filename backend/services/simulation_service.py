"""Orquestación de ``POST /api/v1/simulate`` (BACK-7).

Une los insumos del ML (``providers.features.construir_insumos_ml``, BACK-6) con el motor de
recomendación (``ml.predictor.run_recommendation`` con ensemble de años análogos, ML-5) y
reemplaza los bloques descriptivos de la respuesta por el dato real de los providers.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import date, datetime, timedelta, timezone
from typing import Any

from starlette.concurrency import run_in_threadpool

from ml.escenarios import escenarios_por_cultivo
from ml.predictor import run_recommendation
from services.rotation_matrix import get_crops_for_campaign
from providers.enso import fase_enso
from providers.features import InsumosML, construir_insumos_ml
from providers.nasa_power import NasaPowerUnavailable
from providers.nasa_telemetry import ANALOGOS_START
from schemas import Campana, SimulateRequest

ConstructorInsumos = Callable[..., Awaitable[InsumosML]]

MSG_SIN_ESCENARIOS = (
    "No hay años históricos completos de NASA POWER para la ventana futura de esta coordenada."
)


ANTICIPACION_CAMPANA_DIAS = 45
MESES_INVIERNO = range(4, 10)  # abril..septiembre


class CampanaNoVigente(ValueError):
    """La campaña pedida no es la habilitada para la fecha (CONTEXT §4.1)."""


def campana_vigente(hoy: date) -> Campana:
    """Regla de CONTEXT §4.1 (igual que el entrenamiento): mes de hoy + 45 días en abr–sep → invierno."""
    centro = hoy + timedelta(days=ANTICIPACION_CAMPANA_DIAS)
    return "invierno" if centro.month in MESES_INVIERNO else "verano"


def proxima_habilitacion(campana: Campana, hoy: date) -> date:
    """Primer día desde ``hoy`` en que ``campana`` queda habilitada."""
    dia = hoy
    while campana_vigente(dia) != campana:
        dia += timedelta(days=1)
    return dia


def validar_campana(campana: Campana, hoy: date) -> None:
    vigente = campana_vigente(hoy)
    if campana != vigente:
        desde = proxima_habilitacion(campana, hoy)
        raise CampanaNoVigente(
            f"Hoy ({hoy:%d/%m/%Y}) corresponde la campaña de {vigente}. La de {campana} se "
            f"habilita el {desde:%d/%m/%Y}: el estado del suelo de hoy no sirve para evaluarla."
        )


def _sin_duplicados(items: tuple[str, ...]) -> list[str]:
    return list(dict.fromkeys(items))


def armar_respuesta(
    insumos: InsumosML,
    request: SimulateRequest,
    departamento_codigo: str | None = None,
    advertencias_extra: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Corre el motor de recomendación y ajusta la respuesta al contrato §5 (sin E/S).

    ``departamento_codigo`` es el departamento guardado del campo (BACK-28); sin él, el predictor
    usa el más cercano a las coordenadas.
    """
    if not insumos.escenarios_historicos:
        raise NasaPowerUnavailable(MSG_SIN_ESCENARIOS)

    perfil = insumos.perfil_suelo
    topo = insumos.topografia
    what_if = request.simulacion_what_if.model_dump() if request.simulacion_what_if else None
    escenarios: Any = insumos.escenarios_historicos
    if insumos.calendario_eventos and insumos.calendario_lluvia:
        # ML-7: años análogos del período crítico de cada cultivo, ponderados por ONI.
        escenarios = escenarios_por_cultivo(
            insumos.calendario_eventos,
            insumos.calendario_lluvia,
            get_crops_for_campaign(request.campana),
            insumos.fecha_corte,
            oni_actual=insumos.oni_actual,
        )
        if not all(escenarios.values()):
            raise NasaPowerUnavailable(MSG_SIN_ESCENARIOS)

    respuesta = run_recommendation(
        features=insumos.features_actuales,
        escenarios_historicos=escenarios,
        campana=request.campana,
        cultivo_anterior=request.cultivo_anterior,
        objetivo_productor=request.objetivo_productor,
        carbono_organico_g_kg=perfil.carbono_organico_g_kg,
        phh2o=perfil.ph,
        arena_pct=perfil.arena_pct,
        fecha_ultimo_dato_valido=insumos.fecha_corte.isoformat(),
        ubicacion={"lat": request.coordenadas.lat, "lon": request.coordenadas.lon},
        simulacion_what_if=what_if,
        fecha_corte=insumos.fecha_corte,
        oni_actual=insumos.oni_actual,
        departamento_codigo=departamento_codigo,
    )

    # Bloques descriptivos: dato satelital real, sin los topes del modelo ni el What-If.
    riesgo_termico_analogos = respuesta["telemetria_nasa"]["riesgo_termico_verano"]
    respuesta["telemetria_nasa"] = insumos.telemetria.model_dump(mode="json")
    if request.campana == "verano":
        # ML-12: días de calor esperados en los años análogos (misma fase ENSO), no el promedio
        # de todos los años, para que no contradiga el riesgo de los cultivos.
        respuesta["telemetria_nasa"]["riesgo_termico_verano"] = riesgo_termico_analogos
    respuesta["topografia_srtm"].update(
        elevacion_m=round(float(topo.elevacion_m), 1),
        pendiente_terreno_pct=round(float(topo.pendiente_terreno_pct), 1),
    )
    suelo = respuesta["perfil_suelo"]
    if perfil.textura_predominante:
        suelo["textura_predominante"] = perfil.textura_predominante
    if perfil.arcilla_pct is not None:
        suelo["arcilla_pct"] = round(float(perfil.arcilla_pct), 1)
    respuesta["advertencias"] = _sin_duplicados(tuple(advertencias_extra) + tuple(insumos.advertencias))
    # BACK-27: fase ENSO con la que se eligieron los años análogos (el front explica contra qué
    # campañas se compara).
    if insumos.oni_actual is not None:
        respuesta["fase_enso"] = {
            "fase": fase_enso(float(insumos.oni_actual)),
            "oni": round(float(insumos.oni_actual), 2),
            "anios_analogos_desde": ANALOGOS_START.year,
        }
    return respuesta


async def simular(
    request: SimulateRequest,
    *,
    construir: ConstructorInsumos = construir_insumos_ml,
    today: date | None = None,
    campo: dict[str, Any] | None = None,
    persistir_campo: Callable[[dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Pipeline online completo: providers en paralelo → features → ensemble ML → respuesta §5.

    BACK-24: ``campo`` es la fila de ``public.fields`` del usuario (el servicio único de datos del
    lote usa sus datos fijos y guarda lo que falte). BACK-28: su departamento define el rinde normal.

    Raises:
        CampanaNoVigente: la campaña pedida no corresponde a la fecha (se valida antes de consultar).
        NasaPowerUnavailable / SoilGridsUnavailable / SrtmUnavailable: provider sin datos.
    """
    today = today or datetime.now(timezone.utc).date()
    validar_campana(request.campana, today)
    # BACK-24: con campo guardado, el servicio único usa sus datos fijos y guarda lo que falte.
    extra = {"campo": campo, "persistir_campo": persistir_campo} if campo is not None else {}
    insumos = await construir(request.coordenadas.lat, request.coordenadas.lon, today=today, **extra)
    departamento_codigo = campo.get("departamento_codigo") if campo is not None else None
    # El ensemble del modelo es CPU y síncrono: en un hilo aparte, para que el servidor siga
    # atendiendo otros pedidos (login, campos) mientras calcula. Idea de BACK-7 de Dolfina.
    return await run_in_threadpool(armar_respuesta, insumos, request, departamento_codigo)
