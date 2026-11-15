"""Router CRUD para campos/lotes del usuario autenticado."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

try:
    from backend.providers.supabase_client import get_authenticated_supabase_client
    from backend.routers.auth import AuthenticatedUser, get_current_user
    from backend.schemas import FieldCreate, FieldResponse, FieldUpdate
except ImportError:
    from providers.supabase_client import get_authenticated_supabase_client
    from routers.auth import AuthenticatedUser, get_current_user
    from schemas import FieldCreate, FieldResponse, FieldUpdate

router = APIRouter(prefix="/api/v1/fields", tags=["Fields"])


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
def create_field(
    payload: FieldCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> FieldResponse:
    """Crea un nuevo campo para el usuario autenticado."""
    client = get_authenticated_supabase_client(current_user.access_token)
    data = {
        "user_id": current_user.id,
        **payload.model_dump(mode="json", exclude_none=True),
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
def update_field(
    field_id: UUID,
    payload: FieldUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> FieldResponse:
    """Actualiza los datos de un campo existente."""
    updates = payload.model_dump(exclude_unset=True, mode="json")
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se enviaron campos para actualizar.",
        )

    client = get_authenticated_supabase_client(current_user.access_token)
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
