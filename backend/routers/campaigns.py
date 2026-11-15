"""Router CRUD para campañas e historial de cultivos por campo."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

try:
    from backend.providers.supabase_client import get_authenticated_supabase_client
    from backend.routers.auth import AuthenticatedUser, get_current_user
    from backend.schemas import CampaignCreate, CampaignResponse, CampaignUpdate
except ImportError:
    from providers.supabase_client import get_authenticated_supabase_client
    from routers.auth import AuthenticatedUser, get_current_user
    from schemas import CampaignCreate, CampaignResponse, CampaignUpdate

router = APIRouter(prefix="/api/v1/fields/{field_id}/campaigns", tags=["Campaigns"])


def _ensure_field_accessible(client, field_id: UUID) -> None:
    """Verifica que el campo exista y pertenezca al usuario (RLS)."""
    result = (
        client.table("fields")
        .select("id")
        .eq("id", str(field_id))
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campo no encontrado.",
        )


@router.get("", response_model=list[CampaignResponse])
def list_campaigns(
    field_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[CampaignResponse]:
    """Lista el historial de campañas de un campo ordenado por fecha_inicio descendente."""
    client = get_authenticated_supabase_client(current_user.access_token)
    _ensure_field_accessible(client, field_id)

    result = (
        client.table("campaigns")
        .select("*")
        .eq("field_id", str(field_id))
        .order("fecha_inicio", desc=True)
        .execute()
    )
    return [CampaignResponse(**row) for row in (result.data or [])]


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(
    field_id: UUID,
    payload: CampaignCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CampaignResponse:
    """Registra una nueva campaña con cultivo, fechas y resultados/simulación."""
    client = get_authenticated_supabase_client(current_user.access_token)
    _ensure_field_accessible(client, field_id)

    data = {
        "field_id": str(field_id),
        "user_id": current_user.id,
        **payload.model_dump(mode="json"),
    }
    result = client.table("campaigns").insert(data).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar la campaña.",
        )
    return CampaignResponse(**result.data[0])


@router.patch("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    field_id: UUID,
    campaign_id: UUID,
    payload: CampaignUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CampaignResponse:
    """Actualiza fechas, cultivo o resultados de una campaña existente."""
    updates = payload.model_dump(exclude_unset=True, mode="json")
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se enviaron datos para actualizar.",
        )

    client = get_authenticated_supabase_client(current_user.access_token)
    _ensure_field_accessible(client, field_id)

    result = (
        client.table("campaigns")
        .update(updates)
        .eq("id", str(campaign_id))
        .eq("field_id", str(field_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaña no encontrada.",
        )
    return CampaignResponse(**result.data[0])


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(
    field_id: UUID,
    campaign_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    """Elimina una campaña del historial del campo."""
    client = get_authenticated_supabase_client(current_user.access_token)
    _ensure_field_accessible(client, field_id)

    result = (
        client.table("campaigns")
        .delete()
        .eq("id", str(campaign_id))
        .eq("field_id", str(field_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaña no encontrada.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
