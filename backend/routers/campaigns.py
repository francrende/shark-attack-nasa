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


# Tolerancia por husos horarios: Argentina está en UTC−3 y el servidor en UTC.
TOLERANCIA_FUTURO_DIAS = 1


def _validar_fechas_campana(client, field_id: UUID, campaign_id: UUID, updates: dict) -> None:
    """BACK-30: al cerrar o editar una campaña, la cosecha va después de la siembra y no es futura."""
    from datetime import date as _date, datetime as _datetime, timedelta as _timedelta, timezone as _timezone

    actual = (
        client.table("campaigns")
        .select("fecha_inicio, fecha_fin")
        .eq("id", str(campaign_id))
        .eq("field_id", str(field_id))
        .maybe_single()
        .execute()
    )
    if not actual or not actual.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaña no encontrada.")
    inicio = updates.get("fecha_inicio", actual.data.get("fecha_inicio"))
    fin = updates.get("fecha_fin", actual.data.get("fecha_fin"))
    if fin is None:
        return
    inicio_d, fin_d = _date.fromisoformat(str(inicio)[:10]), _date.fromisoformat(str(fin)[:10])
    if fin_d < inicio_d:
        raise HTTPException(status_code=422, detail="La fecha de cosecha no puede ser anterior a la de siembra.")
    hoy = _datetime.now(_timezone.utc).date()
    if fin_d > hoy + _timedelta(days=TOLERANCIA_FUTURO_DIAS):
        raise HTTPException(status_code=422, detail="La fecha de cosecha no puede ser futura.")


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
    if "fecha_inicio" in updates or "fecha_fin" in updates:
        _validar_fechas_campana(client, field_id, campaign_id, updates)

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


# ---------------------------------------------------------------------------
# BACK-29: seguimiento de una campaña sembrada (ML-18)
# ---------------------------------------------------------------------------

from datetime import date, datetime, timezone  # noqa: E402
from typing import Any, Protocol  # noqa: E402

from fastapi.responses import JSONResponse  # noqa: E402

from providers.nasa_power import NasaPowerUnavailable  # noqa: E402
from providers.soilgrids import SoilGridsUnavailable  # noqa: E402
from providers.srtm import SrtmUnavailable  # noqa: E402
from schemas import SeguimientoResponse  # noqa: E402
from services.seguimiento_service import (  # noqa: E402
    ConstructorSeguimiento,
    SeguimientoInvalido,
    calcular_seguimiento,
    construir_insumos_seguimiento,
)

FUENTE_POR_ERROR: dict[type[Exception], str] = {
    NasaPowerUnavailable: "nasa_power",
    SoilGridsUnavailable: "soilgrids",
    SrtmUnavailable: "srtm",
}


class CampaignStore(Protocol):
    """Acceso mínimo a ``campaigns`` y ``fields`` para el seguimiento (sobreescribible en tests)."""

    def get_field(self, field_id: UUID, access_token: str) -> dict[str, Any] | None: ...

    def get_campaign(self, field_id: UUID, campaign_id: UUID, access_token: str) -> dict[str, Any] | None: ...

    def save_simulacion_json(self, campaign_id: UUID, access_token: str, simulacion_json: dict[str, Any]) -> None: ...


class SupabaseCampaignStore:
    def get_field(self, field_id: UUID, access_token: str) -> dict[str, Any] | None:
        client = get_authenticated_supabase_client(access_token)
        result = client.table("fields").select("*").eq("id", str(field_id)).maybe_single().execute()
        return result.data if result else None

    def get_campaign(self, field_id: UUID, campaign_id: UUID, access_token: str) -> dict[str, Any] | None:
        client = get_authenticated_supabase_client(access_token)
        result = (
            client.table("campaigns")
            .select("*")
            .eq("id", str(campaign_id))
            .eq("field_id", str(field_id))
            .maybe_single()
            .execute()
        )
        return result.data if result else None

    def save_simulacion_json(self, campaign_id: UUID, access_token: str, simulacion_json: dict[str, Any]) -> None:
        client = get_authenticated_supabase_client(access_token)
        client.table("campaigns").update({"simulacion_json": simulacion_json}).eq("id", str(campaign_id)).execute()


_default_campaign_store = SupabaseCampaignStore()


def get_campaign_store() -> CampaignStore:
    return _default_campaign_store


def get_constructor_seguimiento() -> ConstructorSeguimiento:
    return construir_insumos_seguimiento


def get_hoy() -> date:
    return datetime.now(timezone.utc).date()


@router.get(
    "/{campaign_id}/seguimiento",
    response_model=SeguimientoResponse,
    responses={503: {"description": 'Un servicio externo no respondió: {"detail": str, "fuente": str}'}},
)
async def seguimiento_campaign(
    field_id: UUID,
    campaign_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    store: CampaignStore = Depends(get_campaign_store),
    construir: ConstructorSeguimiento = Depends(get_constructor_seguimiento),
    hoy: date = Depends(get_hoy),
) -> Any:
    """Cómo viene la campaña: riesgo de año malo y rinde semana a semana desde la siembra (ML-18)."""
    campo = store.get_field(field_id, current_user.access_token)
    campana = store.get_campaign(field_id, campaign_id, current_user.access_token) if campo else None
    if not campo or not campana:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaña no encontrada.")
    try:
        respuesta, es_nueva = await calcular_seguimiento(campana, campo, hoy, construir)
    except SeguimientoInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (NasaPowerUnavailable, SoilGridsUnavailable, SrtmUnavailable) as exc:
        fuente = next(f for tipo, f in FUENTE_POR_ERROR.items() if isinstance(exc, tipo))
        return JSONResponse(status_code=503, content={"detail": str(exc), "fuente": fuente})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    salida = SeguimientoResponse.model_validate(respuesta).model_dump(mode="json")
    if es_nueva:
        try:
            simulacion = dict(campana.get("simulacion_json") or {})
            simulacion["seguimiento"] = salida
            store.save_simulacion_json(campaign_id, current_user.access_token, simulacion)
        except Exception:  # noqa: BLE001 - guardar es una optimización: el resultado se devuelve igual
            pass
    return salida
