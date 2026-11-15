"""Endpoint ``POST /api/v1/simulate`` (BACK-7, contrato de CONTEXT.md §5)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from providers.features import construir_insumos_ml
from providers.nasa_power import NasaPowerUnavailable
from providers.soilgrids import SoilGridsUnavailable
from providers.srtm import SrtmUnavailable
from schemas import SimulateRequest, SimulateResponse
from services.simulation_service import ConstructorInsumos, simular

router = APIRouter(prefix="/api/v1", tags=["simulacion"])


def get_constructor_insumos() -> ConstructorInsumos:
    """Dependencia sobreescribible en tests (``app.dependency_overrides``)."""
    return construir_insumos_ml


@router.post("/simulate", response_model=SimulateResponse)
async def simulate(
    request: SimulateRequest,
    construir: ConstructorInsumos = Depends(get_constructor_insumos),
) -> dict[str, Any]:
    try:
        return await simular(request, construir=construir)
    except (NasaPowerUnavailable, SoilGridsUnavailable, SrtmUnavailable) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ValueError as exc:
        # Coordenadas fuera de rango detectadas por los providers.
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
