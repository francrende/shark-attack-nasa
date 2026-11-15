"""Router y dependencias de autenticación con Supabase Auth."""

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase_auth.errors import AuthApiError

try:
    from backend.providers.supabase_client import (
        get_authenticated_supabase_client,
        get_supabase_client,
    )
    from backend.schemas import (
        AuthLoginRequest,
        AuthRegisterRequest,
        AuthResponse,
        UserProfileResponse,
    )
except ImportError:
    from providers.supabase_client import (
        get_authenticated_supabase_client,
        get_supabase_client,
    )
    from schemas import (
        AuthLoginRequest,
        AuthRegisterRequest,
        AuthResponse,
        UserProfileResponse,
    )

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedUser:
    """Usuario autenticado extraído del JWT de Supabase."""

    id: str
    email: str | None
    nombre: str | None
    access_token: str


def _extract_user_profile(user_obj: Any) -> UserProfileResponse:
    metadata = getattr(user_obj, "user_metadata", None) or {}
    return UserProfileResponse(
        id=user_obj.id,
        email=getattr(user_obj, "email", None),
        nombre=metadata.get("nombre") or None,
        created_at=getattr(user_obj, "created_at", None),
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthenticatedUser:
    """Valida el Bearer token con Supabase Auth y devuelve el usuario actual."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token de autenticación Bearer.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    client = get_supabase_client()
    try:
        user_response = client.auth.get_user(token)
    except AuthApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido o expirado: {exc.message}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo validar el token de autenticación.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_obj = getattr(user_response, "user", None)
    if user_obj is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o usuario inexistente.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    metadata = getattr(user_obj, "user_metadata", None) or {}
    return AuthenticatedUser(
        id=str(user_obj.id),
        email=getattr(user_obj, "email", None),
        nombre=metadata.get("nombre") or None,
        access_token=token,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: AuthRegisterRequest) -> AuthResponse:
    """Registra un usuario nuevo en Supabase Auth."""
    client = get_supabase_client()
    try:
        response = client.auth.sign_up(
            {
                "email": payload.email,
                "password": payload.password,
                "options": {"data": {"nombre": payload.nombre}},
            }
        )
    except AuthApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc

    if response.user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo completar el registro.",
        )

    session = response.session
    return AuthResponse(
        access_token=session.access_token if session else None,
        refresh_token=session.refresh_token if session else None,
        user=_extract_user_profile(response.user),
        requiere_confirmacion_email=session is None,
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: AuthLoginRequest) -> AuthResponse:
    """Inicia sesión con email y contraseña en Supabase Auth."""
    client = get_supabase_client()
    try:
        response = client.auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
    except AuthApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
        ) from exc

    if response.user is None or response.session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas.",
        )

    return AuthResponse(
        access_token=response.session.access_token,
        refresh_token=response.session.refresh_token,
        user=_extract_user_profile(response.user),
        requiere_confirmacion_email=False,
    )


@router.get("/me", response_model=UserProfileResponse)
def get_me(current_user: AuthenticatedUser = Depends(get_current_user)) -> UserProfileResponse:
    """Devuelve el perfil del usuario autenticado."""
    client = get_authenticated_supabase_client(current_user.access_token)
    result = (
        client.table("profiles")
        .select("id, email, nombre, created_at")
        .eq("id", current_user.id)
        .maybe_single()
        .execute()
    )
    if result.data:
        return UserProfileResponse(**result.data)

    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        nombre=current_user.nombre,
    )
