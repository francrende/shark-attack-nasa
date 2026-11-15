"""Router de ``GET /api/v1/historial`` (BACK-31): historial real del lote por campaña agrícola."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from providers.nasa_power import NasaPowerUnavailable
from providers.supabase_client import get_authenticated_supabase_client
from schemas import HistorialResponse
from services.historial_service import obtener_historial

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["historial"])
_optional_bearer = HTTPBearer(auto_error=False)


class HistorialStore(Protocol):
    """Lectura del campo y sus campañas (RLS con el JWT del usuario)."""

    def get_field(self, field_id: UUID, access_token: str) -> dict[str, Any] | None: ...

    def list_campaigns(self, field_id: UUID, access_token: str) -> list[dict[str, Any]]: ...


class SupabaseHistorialStore:
    def get_field(self, field_id: UUID, access_token: str) -> dict[str, Any] | None:
        client = get_authenticated_supabase_client(access_token)
        result = client.table("fields").select("*").eq("id", str(field_id)).maybe_single().execute()
        return result.data if result else None

    def list_campaigns(self, field_id: UUID, access_token: str) -> list[dict[str, Any]]:
        client = get_authenticated_supabase_client(access_token)
        result = (
            client.table("campaigns")
            .select("id, cultivo, fecha_inicio, fecha_fin, rinde_kg_ha")
            .eq("field_id", str(field_id))
            .order("fecha_inicio", desc=True)
            .execute()
        )
        return list(result.data or [])


_default_store = SupabaseHistorialStore()


def get_historial_store() -> HistorialStore:
    return _default_store


def get_hoy() -> date:
    return datetime.now(timezone.utc).date()


@router.get(
    "/historial",
    response_model=HistorialResponse,
    responses={503: {"description": 'NASA POWER no respondió: {"detail": str, "fuente": "nasa_power"}'}},
)
async def get_historial(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    field_id: UUID | None = Query(default=None, description="Campo guardado: suma sus cosechas y su departamento."),
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    store: HistorialStore = Depends(get_historial_store),
    hoy: date = Depends(get_hoy),
) -> Any:
    """Lluvia, agua en raíces, rinde de la zona y cosechas del lote por campaña, desde 2006/07."""
    token = credentials.credentials if credentials and credentials.credentials else None
    campo: dict[str, Any] | None = None
    campanas: list[dict[str, Any]] | None = None
    if field_id is not None and token:
        try:
            campo = store.get_field(field_id, token)
            campanas = store.list_campaigns(field_id, token) if campo else None
        except Exception:  # noqa: BLE001 - sin Supabase se muestra igual el clima y la zona
            logger.warning("No se pudo leer el campo %s para el historial.", field_id)
    try:
        return await obtener_historial(lat, lon, hoy=hoy, campo=campo, campanas_lote=campanas)
    except NasaPowerUnavailable as exc:
        return JSONResponse(status_code=503, content={"detail": str(exc), "fuente": "nasa_power"})
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
