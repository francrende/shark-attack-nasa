"""Endpoint ``POST /api/v1/simulate`` (BACK-7, contrato de CONTEXT.md §5)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from providers.features import construir_insumos_ml
from providers.nasa_power import NasaPowerUnavailable
from providers.soilgrids import SoilGridsUnavailable
from providers.srtm import SrtmUnavailable
from schemas import SimulateRequest, SimulateResponse
from routers.telemetry import FieldStore, get_field_store
from services.field_enrichment_service import departamento_a_columnas_field
from services.simulation_service import ConstructorInsumos, simular

_bearer_opcional = HTTPBearer(auto_error=False)
# BACK-24: diferencia máxima entre las coordenadas pedidas y las del campo (~100 m).
TOLERANCIA_COORDENADAS_GRADOS = 0.001

router = APIRouter(prefix="/api/v1", tags=["simulacion"])

# 503 con el servicio externo que falló, para que el front pueda decir cuál (idea de BACK-7 de
# Dolfina). Respuesta: {"detail": <mensaje>, "fuente": "nasa_power" | "soilgrids" | "srtm"}.
FUENTE_POR_ERROR: dict[type[Exception], str] = {
    NasaPowerUnavailable: "nasa_power",
    SoilGridsUnavailable: "soilgrids",
    SrtmUnavailable: "srtm",
}


def get_constructor_insumos() -> ConstructorInsumos:
    """Dependencia sobreescribible en tests (``app.dependency_overrides``)."""
    return construir_insumos_ml


def get_hoy() -> date:
    """Fecha de evaluación (t = hoy, UTC). Sobreescribible en tests."""
    return datetime.now(timezone.utc).date()


async def _cargar_campo(
    request: SimulateRequest, credentials: HTTPAuthorizationCredentials | None, field_store: FieldStore
) -> tuple[SimulateRequest, dict[str, Any], Any]:
    """BACK-24: lee el campo con el token del usuario (RLS) y valida las coordenadas.

    Devuelve el request con las coordenadas del campo, la fila y la función para guardarle cambios.
    """
    token = credentials.credentials if credentials and credentials.credentials else None
    if not token:
        raise HTTPException(status_code=401, detail="Para simular un campo guardado hace falta iniciar sesión.")
    try:
        campo = await run_in_threadpool(field_store.get_field, request.field_id, token)
    except Exception as exc:  # noqa: BLE001 - token vencido o Supabase sin responder
        raise HTTPException(status_code=401, detail="No se pudo verificar la sesión para leer el campo.") from exc
    if not campo:
        raise HTTPException(status_code=404, detail="El campo no existe o no pertenece al usuario.")
    lat, lon = float(campo["lat"]), float(campo["lon"])
    if (
        abs(lat - request.coordenadas.lat) > TOLERANCIA_COORDENADAS_GRADOS
        or abs(lon - request.coordenadas.lon) > TOLERANCIA_COORDENADAS_GRADOS
    ):
        raise HTTPException(status_code=422, detail="Las coordenadas no coinciden con las del campo guardado.")
    field_id = request.field_id

    def persistir(cambios: dict[str, Any]) -> None:
        field_store.update_field(field_id, token, cambios)

    # BACK-28: campos creados antes de tener departamento MAGyP: se calcula y se guarda una vez.
    if not campo.get("departamento_codigo"):
        columnas = departamento_a_columnas_field(lat, lon)
        campo = {**campo, **columnas}
        if columnas["departamento_codigo"]:
            try:
                await run_in_threadpool(persistir, columnas)
            except Exception:  # noqa: BLE001 - guardar es una optimización: se usa igual
                pass

    request = request.model_copy(update={"coordenadas": request.coordenadas.model_copy(update={"lat": lat, "lon": lon})})
    return request, campo, persistir


@router.post(
    "/simulate",
    response_model=SimulateResponse,
    responses={
        401: {"description": "`field_id` sin sesión válida"},
        404: {"description": "El campo no existe o no es del usuario"},
        503: {"description": 'Un servicio externo no respondió: {"detail": str, "fuente": str}'},
    },
)
async def simulate(
    request: SimulateRequest,
    construir: ConstructorInsumos = Depends(get_constructor_insumos),
    hoy: date = Depends(get_hoy),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_opcional),
    field_store: FieldStore = Depends(get_field_store),
) -> Any:
    campo = persistir = None
    if request.field_id is not None:
        request, campo, persistir = await _cargar_campo(request, credentials, field_store)
    try:
        return await simular(request, construir=construir, today=hoy, campo=campo, persistir_campo=persistir)
    except (NasaPowerUnavailable, SoilGridsUnavailable, SrtmUnavailable) as exc:
        fuente = next(f for tipo, f in FUENTE_POR_ERROR.items() if isinstance(exc, tipo))
        return JSONResponse(status_code=503, content={"detail": str(exc), "fuente": fuente})
    except ValueError as exc:
        # Campaña no vigente (CampanaNoVigente) o coordenadas fuera de rango de los providers.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
