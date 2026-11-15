# TASKS_BACKEND.md — Tablero y Protocolo de Tareas Atómicas (Track Backend & APIs NASA)

> **Fuente de la Verdad:** Antes de proponer o programar cualquier tarea, el agente DEBE leer [`../CONTEXT.md`](../CONTEXT.md) (especialmente las **Secciones 3, 5 y 8**).

---

## 1. Protocolo Obligatorio para el Agente (Cómo trabajar con el Desarrollador)

Cada vez que el desarrollador te pida crear, detallar o avanzar con una tarea de Backend, seguí **estrictamente estos 4 pasos en orden**:

1. **Consultar el Contexto General:** Revisá las fuentes de datos de la NASA y SoilGrids en la **Sección 3** y el contrato JSON inmutable de la **Sección 5** de [`../CONTEXT.md`](../CONTEXT.md).
2. **Hacer Preguntas de Definición (Obligatorio ANTES de cerrar la especificación o programar):**
   - No asumas decisiones que quedaron en el aire (ej. tiempos de timeout, cómo calcular anomalías históricas en NASA POWER, qué zonas cubrir en el fallback de SoilGrids, si los overrides *What-If* modifican el bloque `telemetria_nasa`, validaciones extras en Pydantic, etc.).
   - **Hacele preguntas claras y concretas al desarrollador** para terminar de definir el alcance exacto de la tarea.
3. **Documentar la Tarea Atómica en este archivo:**
   - Una vez que el desarrollador responda tus preguntas, agregá la tarea especificada en la sección **3. Especificación de Tareas Atómicas** de este archivo usando la plantilla estándar y marcala como `[~]` (En progreso).
4. **Implementar y Verificar (Definition of Done):**
   - Escribí el código respetando el **Scope Exclusivo de Carpetas**, ejecutá el comando de verificación y, cuando pase sin errores, marcá la tarea como `[x]`.

---

## 2. Reglas de Aislamiento (Cero Conflictos en Git)

- **Archivos Permitidos (Scope Exclusivo de Backend):**
  - `backend/schemas.py`
  - `backend/providers/*`
  - `backend/routers/*`
  - `backend/services/simulation_service.py`
  - `backend/main.py`
  - `backend/TASKS_BACKEND.md`
- **Archivos Prohibidos:** NO modificar `backend/ml/*`, `backend/services/rotation_matrix.py` ni `frontend/*` (pertenecen a otros miembros del equipo).

---

## 3. Tablero de Tareas Atómicas (Backend)

*(Vacío inicialmente — El agente irá agregando aquí cada tarea junto con el desarrollador luego de la etapa de preguntas).*

| ID | Tarea Atómica | Archivos Involucrados | Depende de | Estado |
| :--- | :--- | :--- | :---: | :---: |
| *Ej: BACK-1* | *(A definir con el agente)* | `backend/...` | — | `[ ]` |
| `BACK-7` | Endpoint `PATCH /api/v1/auth/me` para actualizar `nombre`, `email` y `password` del usuario autenticado | `backend/routers/auth.py`, `backend/schemas.py` | `BACK-3` | `[ ]` |

---

## 4. Plantilla para Especificar cada Nueva Tarea

Cuando el agente y el desarrollador terminen de responder las preguntas de definición de una tarea, el agente debe agregarla aquí abajo siguiendo este formato:

```markdown
### `[ ]` BACK-X: <Título corto de la tarea>
- **Objetivo:** <Qué resuelve exactamente esta unidad atómica>
- **Archivos Permitidos:** `<lista de archivos exclusivos>`
- **Decisiones Acordadas con el Desarrollador:**
  - <Decisión 1 respondida en las preguntas previas>
  - <Decisión 2 respondida en las preguntas previas>
- **Especificación Técnica:**
  1. <Paso técnico 1>
  2. <Paso técnico 2>
- **Definition of Done (Comando de Verificación):**
  - `<comando ejecutable para comprobar que funciona>`
```

---

## 5. Tareas Pendientes Registradas desde Frontend

### `[ ]` BACK-7: Endpoint `PATCH /api/v1/auth/me` para Edición de Perfil de Usuario (`FRONT-30`)
- **Objetivo:** Permitir que el usuario autenticado actualice su `nombre`, `email` y/o `password` desde la pestaña **Usuario** del modal de ajustes en el frontend, persistiendo los cambios en Supabase Auth y en la tabla `profiles`.
- **Archivos Permitidos:** `backend/schemas.py`, `backend/routers/auth.py`, `backend/TASKS_BACKEND.md`
- **Contrato ya conectado desde Frontend (`FRONT-30`):**
  - Método y ruta: `PATCH /api/v1/auth/me`
  - Header requerido: `Authorization: Bearer <access_token>` (dependencia `get_current_user`)
  - Body JSON opcional por campo (`UserUpdateRequest`):
    - `nombre?: string`
    - `email?: string`
    - `password?: string` (mínimo 6 caracteres cuando se envía)
  - Respuesta esperada (`200 OK`, `UserProfileResponse`): `{ "id": string, "email": string, "nombre": string, "created_at": string | null }`
- **Pendiente a definir antes de programar (Protocolo Paso 2):**
  1. Confirmar si para actualizar `email` o `password` se utilizará el cliente autenticado del usuario (`update_user` con JWT) o `service_role` admin (`auth.admin.update_user_by_id`) para evitar bloqueos por confirmación de correo en demo/hackatón.
  2. Confirmar si al cambiar `nombre` o `email` se debe actualizar también `public.profiles` en la misma petición.
- **Especificación Técnica Preliminar:**
  1. Agregar el schema `UserUpdateRequest` en `backend/schemas.py` con validaciones opcionales (`nombre`, `email: EmailStr | None`, `password` mínimo 6 caracteres).
  2. Implementar `@router.patch("/me", response_model=UserProfileResponse)` en `backend/routers/auth.py` recibiendo `current_user: AuthenticatedUser = Depends(get_current_user)`.
  3. Rechazar payloads vacíos (`400 Bad Request`) y mapear errores de Supabase Auth (`AuthApiError`) a respuestas HTTP claras en español.
- **Definition of Done (Comando de Verificación):**
  - Verificar con `uvicorn` levantado que `PATCH /api/v1/auth/me` responde `200` con el perfil actualizado y que `GET /api/v1/auth/me` refleja los nuevos valores.
