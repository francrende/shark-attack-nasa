"""Router CRUD para campos/lotes del usuario autenticado."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

try:
    from backend.providers.supabase_client import get_authenticated_supabase_client
    from backend.routers.auth import AuthenticatedUser, get_current_user
    from backend.schemas import FieldCreate, FieldResponse, FieldUpdate
    from backend.services.field_enrichment_service import FieldEnricher, enriquecer_datos_campo
except ImportError:
    from providers.supabase_client import get_authenticated_supabase_client
    from routers.auth import AuthenticatedUser, get_current_user
    from schemas import FieldCreate, FieldResponse, FieldUpdate
    from services.field_enrichment_service import FieldEnricher, enriquecer_datos_campo

router = APIRouter(prefix="/api/v1/fields", tags=["Fields"])


def get_field_enricher() -> FieldEnricher:
    """Dependencia sobreescribible en tests para poblar suelo y topografía al crear/mover un campo."""
    return enriquecer_datos_campo


@router.get("", response_model=list[FieldResponse])
def list_fields(current_user: AuthenticatedUser = Depends(get_current_user)) -> list[FieldResponse]:
    """Lista todos los campos pertenecientes al usuario autenticado."""
    client = get_authenticated_supabase_client(current_user.access_token)
    result = (
        client.table("fields")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return [FieldResponse(**row) for row in (result.data or [])]


@router.post("", response_model=FieldResponse, status_code=status.HTTP_201_CREATED)
async def create_field(
    payload: FieldCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    enricher: FieldEnricher = Depends(get_field_enricher),
) -> FieldResponse:
    """Crea un nuevo campo para el usuario autenticado con sus datos propios de suelo y topografía."""
    enrichment = await enricher(payload.lat, payload.lon)
    client = get_authenticated_supabase_client(current_user.access_token)
    data = {
        "user_id": current_user.id,
        **payload.model_dump(mode="json", exclude_none=True),
        **enrichment,
    }
    result = client.table("fields").insert(data).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo crear el campo.",
        )
    return FieldResponse(**result.data[0])


@router.get("/{field_id}", response_model=FieldResponse)
def get_field(
    field_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> FieldResponse:
    """Obtiene el detalle de un campo del usuario autenticado."""
    client = get_authenticated_supabase_client(current_user.access_token)
    result = (
        client.table("fields")
        .select("*")
        .eq("id", str(field_id))
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campo no encontrado.",
        )
    return FieldResponse(**result.data)


@router.patch("/{field_id}", response_model=FieldResponse)
async def update_field(
    field_id: UUID,
    payload: FieldUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    enricher: FieldEnricher = Depends(get_field_enricher),
) -> FieldResponse:
    """Actualiza los datos de un campo existente y refresca suelo/topografía si cambió la ubicación."""
    updates = payload.model_dump(exclude_unset=True, mode="json")
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se enviaron campos para actualizar.",
        )

    client = get_authenticated_supabase_client(current_user.access_token)
    if any(k in updates for k in ("lat", "lon", "polygon")):
        target_lat = updates.get("lat")
        target_lon = updates.get("lon")
        if target_lat is None or target_lon is None:
            existing = (
                client.table("fields")
                .select("lat, lon")
                .eq("id", str(field_id))
                .maybe_single()
                .execute()
            )
            if not existing.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Campo no encontrado.",
                )
            if target_lat is None:
                target_lat = existing.data["lat"]
            if target_lon is None:
                target_lon = existing.data["lon"]
        enrichment = await enricher(float(target_lat), float(target_lon))
        updates.update(enrichment)

    result = (
        client.table("fields")
        .update(updates)
        .eq("id", str(field_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campo no encontrado.",
        )
    return FieldResponse(**result.data[0])


@router.delete("/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_field(
    field_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    """Elimina un campo y su historial asociado."""
    client = get_authenticated_supabase_client(current_user.access_token)
    result = (
        client.table("fields")
        .delete()
        .eq("id", str(field_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campo no encontrado.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
