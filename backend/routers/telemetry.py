"""Router de ``GET /api/v1/telemetry`` (BACK-20 / BACK-23)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from providers.nasa_power import NasaPowerUnavailable
from providers.soilgrids import SoilGridsUnavailable
from providers.srtm import SrtmUnavailable
from providers.supabase_client import get_authenticated_supabase_client
from schemas import TelemetryResponse
from services.telemetry_service import TelemetryFetcher, obtener_telemetria_campo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["telemetria"])
_optional_bearer = HTTPBearer(auto_error=False)


class FieldStore(Protocol):
    """Acceso mínimo a ``public.fields`` para leer y refrescar datos propios del lote."""

    def get_field(self, field_id: UUID, access_token: str) -> dict[str, Any] | None: ...

    def update_field(self, field_id: UUID, access_token: str, updates: dict[str, Any]) -> None: ...


class SupabaseFieldStore:
    """Implementación sobre Supabase RLS usando el JWT del usuario autenticado."""

    def get_field(self, field_id: UUID, access_token: str) -> dict[str, Any] | None:
        client = get_authenticated_supabase_client(access_token)
        result = (
            client.table("fields")
            .select("*")
            .eq("id", str(field_id))
            .maybe_single()
            .execute()
        )
        return result.data if result else None

    def update_field(self, field_id: UUID, access_token: str, updates: dict[str, Any]) -> None:
        client = get_authenticated_supabase_client(access_token)
        client.table("fields").update(updates).eq("id", str(field_id)).execute()


_default_field_store = SupabaseFieldStore()


def get_telemetry_fetcher() -> TelemetryFetcher:
    """Dependencia sobreescribible en tests (``app.dependency_overrides``)."""
    return obtener_telemetria_campo


def get_field_store() -> FieldStore:
    """Dependencia sobreescribible en tests para lectura/actualización de ``public.fields``."""
    return _default_field_store


def get_hoy() -> date:
    """Fecha de evaluación (UTC). Sobreescribible en tests."""
    return datetime.now(timezone.utc).date()


@router.get("/telemetry", response_model=TelemetryResponse)
async def get_field_telemetry(
    lat: float = Query(..., ge=-90, le=90, description="Latitud del centroide del lote."),
    lon: float = Query(..., ge=-180, le=180, description="Longitud del centroide del lote."),
    field_id: UUID | None = Query(
        default=None,
        description="ID del campo en BD para reutilizar suelo/topografía propios y reintentar si corresponde.",
    ),
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    fetcher: TelemetryFetcher = Depends(get_telemetry_fetcher),
    field_store: FieldStore = Depends(get_field_store),
    hoy: date = Depends(get_hoy),
) -> dict[str, Any]:
    """Devuelve telemetría satelital en vivo y datos edáficos/topográficos del campo."""
    field_row: dict[str, Any] | None = None
    access_token = credentials.credentials if credentials and credentials.credentials else None
    if field_id is not None and access_token:
        try:
            field_row = field_store.get_field(field_id, access_token)
        except Exception:  # noqa: BLE001
            logger.warning("No se pudo leer el campo %s desde Supabase; se consulta por coordenadas.", field_id)

    try:
        if field_row is not None and access_token and field_id is not None:
            return await fetcher(
                lat,
                lon,
                today=hoy,
                field_row=field_row,
                persist_field_updates=lambda updates: field_store.update_field(
                    field_id, access_token, updates
                ),
            )
        return await fetcher(lat, lon, today=hoy)
    except (NasaPowerUnavailable, SoilGridsUnavailable, SrtmUnavailable) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
