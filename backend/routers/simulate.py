"""Endpoint ``POST /api/v1/simulate`` (BACK-7, contrato de CONTEXT.md §5)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from providers.features import construir_insumos_ml
from providers.nasa_power import NasaPowerUnavailable
from providers.soilgrids import SoilGridsUnavailable
from providers.srtm import SrtmUnavailable
from schemas import SimulateRequest, SimulateResponse
from services.simulation_service import ConstructorInsumos, simular

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


@router.post(
    "/simulate",
    response_model=SimulateResponse,
    responses={503: {"description": 'Un servicio externo no respondió: {"detail": str, "fuente": str}'}},
)
async def simulate(
    request: SimulateRequest,
    construir: ConstructorInsumos = Depends(get_constructor_insumos),
    hoy: date = Depends(get_hoy),
) -> Any:
    try:
        return await simular(request, construir=construir, today=hoy)
    except (NasaPowerUnavailable, SoilGridsUnavailable, SrtmUnavailable) as exc:
        fuente = next(f for tipo, f in FUENTE_POR_ERROR.items() if isinstance(exc, tipo))
        return JSONResponse(status_code=503, content={"detail": str(exc), "fuente": fuente})
    except ValueError as exc:
        # Campaña no vigente (CampanaNoVigente) o coordenadas fuera de rango de los providers.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
