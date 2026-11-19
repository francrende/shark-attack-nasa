# BACK-15: `PATCH /api/v1/auth/me` para editar el perfil

- **Issue:** EREIA-3 (Multica)
- **Módulos:** BACK
- **Depende de:** —

## Objetivo

Que el usuario autenticado pueda cambiar su `nombre`, `email` y/o `password` desde la pestaña **Usuario** del modal de ajustes. Hoy el frontend ya envía el request y el backend no tiene la ruta, así que la edición de perfil falla.

## Contexto

- El frontend ya llama a `PATCH /api/v1/auth/me` desde [`frontend/src/services/authClient.ts`](../frontend/src/services/authClient.ts) (formulario de FRONT-30 en `UserSettingsModal.tsx`).
- [`backend/routers/auth.py`](../backend/routers/auth.py) tiene `GET /me` y `PATCH /me/provinces`, pero no `PATCH /me`. La dependencia `get_current_user` ya existe.
- `UserProfileResponse` ya existe en [`backend/schemas.py`](../backend/schemas.py): `{ id, email, nombre, provincias, created_at }`.
- El nombre vive en `public.profiles.nombre` y el email y la contraseña en Supabase Auth.

## Alcance por módulo

### BACK

- Archivos: `backend/schemas.py`, `backend/routers/auth.py`, `backend/routers/test_auth.py` (nuevo).
- Cambios:
  1. Schema `UserUpdateRequest`, con todos los campos opcionales: `nombre: str | None`, `email: EmailStr | None` y `password: str | None` (mínimo 6 caracteres). Rechaza campos extra.
  2. `@router.patch("/me", response_model=UserProfileResponse)` con `Depends(get_current_user)`.
  3. Payload vacío → `400`. Errores de Supabase Auth (`AuthApiError`) → respuestas HTTP con mensaje en español (email en uso → `409`, password débil → `422`).
  4. Si cambia `nombre` o `email`, se actualiza también `public.profiles`, en la misma petición.

## Criterios de aceptación

- [ ] `PATCH /api/v1/auth/me` con `nombre` devuelve `200` con el perfil actualizado, y `GET /me` refleja el cambio.
- [ ] Cambiar `email` o `password` funciona sin bloquear al usuario en espera de confirmación por mail (ver Preguntas abiertas).
- [ ] Sin token → `401`. Body vacío → `400`. Password de menos de 6 caracteres → `422`.
- [ ] El formulario del frontend (FRONT-30) funciona contra el backend local sin cambios en `frontend/`.

## Cómo verificar

```bash
cd backend && python -m pytest routers/test_auth.py -q && python -m pytest -q
```

Manual: con `uvicorn` levantado y el frontend en `localhost:5173`, editar el nombre desde Ajustes → Usuario y recargar.

## Fuera de alcance

- Cambios en la UI de FRONT-30.
- Borrar la cuenta.

## Preguntas abiertas

- ¿El email y la contraseña se actualizan con el cliente del usuario (`update_user` con su JWT, que puede pedir confirmación por mail) o con `auth.admin.update_user_by_id` usando la secret key, para evitar la confirmación? "Confirm email" está desactivado desde BACK-5.
