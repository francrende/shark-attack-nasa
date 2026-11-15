"""Cliente de conexión a Supabase para el backend FastAPI."""

from fastapi import HTTPException, status
from supabase import Client, ClientOptions, create_client

try:
    from backend.config import get_settings
except ImportError:
    from config import get_settings


def _ensure_supabase_configured() -> tuple[str, str]:
    settings = get_settings()
    if not settings.is_supabase_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase no está configurado. Definí SUPABASE_URL y SUPABASE_KEY en backend/.env.",
        )
    return settings.supabase_url, settings.supabase_key


def get_supabase_client() -> Client:
    """Crea un cliente Supabase con la clave pública/anon del proyecto."""
    url, key = _ensure_supabase_configured()
    return create_client(url, key)


def get_authenticated_supabase_client(access_token: str) -> Client:
    """Crea un cliente Supabase autenticado con el JWT del usuario para respetar RLS."""
    url, key = _ensure_supabase_configured()
    options = ClientOptions(headers={"Authorization": f"Bearer {access_token}"})
    return create_client(url, key, options=options)
