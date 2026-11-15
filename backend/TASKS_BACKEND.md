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

| ID | Tarea Atómica | Archivos Involucrados | Depende de | Estado |
| :--- | :--- | :--- | :---: | :---: |
| `BACK-1` | Estructura base FastAPI, config y cliente Supabase | `backend/main.py`, `backend/config.py`, `backend/providers/supabase_client.py`, `backend/requirements.txt`, `backend/.env.example` | — | `[x]` |
| `BACK-2` | Esquema SQL en Supabase (`profiles`, `fields`, `campaigns` + RLS) | `backend/sql/schema.sql` | `BACK-1` | `[x]` |
| `BACK-3` | Endpoints de Auth y dependencia JWT (Supabase Auth) | `backend/routers/auth.py`, `backend/schemas.py`, `backend/main.py` | `BACK-1`, `BACK-2` | `[x]` |
| `BACK-4` | CRUD de Campos y Campañas/Resultados por Campo | `backend/routers/fields.py`, `backend/routers/campaigns.py`, `backend/schemas.py`, `backend/main.py` | `BACK-2`, `BACK-3` | `[x]` |
| `BACK-5` | Verificación Live de Auth Supabase, Usuario Demo (`demoereia@gmail.com`) y Nota de Rate Limit Email | `backend/TASKS_BACKEND.md` | `BACK-3` | `[x]` |

---

## 4. Especificación de Tareas Atómicas

### `[x]` BACK-1: Estructura base FastAPI, configuración y cliente Supabase
- **Objetivo:** Dejar levantado el esqueleto modular de FastAPI con lectura de variables de entorno (`pydantic-settings`), CORS habilitado para el frontend y el cliente oficial `supabase-py` listo para usar, más un endpoint `/health` que verifique la app y la configuración de Supabase.
- **Archivos Permitidos:** `backend/main.py`, `backend/config.py`, `backend/providers/supabase_client.py`, `backend/requirements.txt`, `backend/.env.example`
- **Decisiones Acordadas con el Desarrollador:**
  - Conexión a Supabase mediante el SDK oficial `supabase-py` usando `SUPABASE_URL` y `SUPABASE_KEY` (y opcionalmente `SUPABASE_SERVICE_ROLE_KEY` si se requiere en backend).
- **Especificación Técnica:**
  1. Agregar `supabase` a `backend/requirements.txt` e instalarlo en `.venv`.
  2. Crear `backend/.env.example` con `SUPABASE_URL`, `SUPABASE_KEY` (anon/publishable) y `CORS_ORIGINS`.
  3. Crear `backend/config.py` con `Settings(BaseSettings)` cargando `.env`.
  4. Crear `backend/providers/supabase_client.py` con `get_supabase_client()` y `get_authenticated_supabase_client(access_token)` (para respetar RLS con el JWT del usuario).
  5. Crear `backend/main.py` con la instancia `FastAPI(title="Shark Attack API")`, middleware CORS y `GET /health`.
- **Definition of Done (Comando de Verificación):**
  - `python -c "from backend.main import app; print(app.title)"` y `GET http://localhost:8000/health` devuelve `200 OK`.

### `[x]` BACK-2: Esquema SQL en Supabase (`profiles`, `fields`, `campaigns` + RLS)
- **Objetivo:** Definir el modelo relacional en PostgreSQL/Supabase para usuarios, sus campos/lotes y el historial de campañas (fechas, cultivo, resultados y JSON de simulación), con seguridad Row Level Security (RLS) activada.
- **Archivos Permitidos:** `backend/sql/schema.sql`
- **Decisiones Acordadas con el Desarrollador:**
  - Autenticación con **Supabase Auth** nativo (`auth.users`) enlazado a una tabla `public.profiles`.
  - Guardar tanto los datos estructurados de cada campaña (tipo `invierno`/`verano`, fechas, cultivo, rinde/resultado) como el JSON completo de la recomendación/simulación (`/api/v1/simulate`) en una columna `simulacion_json` (`jsonb`).
- **Especificación Técnica:**
  1. Tabla `public.profiles`: `id` (`uuid PK references auth.users on delete cascade`), `email` (`text`), `nombre` (`text`), `created_at` (`timestamptz`). Trigger automático `on_auth_user_created` para insertar el perfil al registrarse.
  2. Tabla `public.fields`: `id` (`uuid PK default gen_random_uuid()`), `user_id` (`uuid not null references public.profiles(id) on delete cascade`), `nombre` (`text not null`), `lat` (`double precision not null`), `lon` (`double precision not null`), `hectareas` (`double precision`), `created_at` (`timestamptz`).
  3. Tabla `public.campaigns`: `id` (`uuid PK default gen_random_uuid()`), `field_id` (`uuid not null references public.fields(id) on delete cascade`), `user_id` (`uuid not null references public.profiles(id) on delete cascade`), `campana` (`text not null check (campana in ('invierno', 'verano'))`), `cultivo` (`text not null`), `fecha_inicio` (`date not null`), `fecha_fin` (`date`), `rinde_kg_ha` (`double precision`), `resultado_notas` (`text`), `simulacion_json` (`jsonb`), `created_at` (`timestamptz`).
  4. Habilitar RLS en las 3 tablas con políticas para que cada usuario (`auth.uid()`) solo vea, cree, edite y elimine sus propios registros.
- **Definition of Done (Comando de Verificación):**
  - Ejecutar el script `backend/sql/schema.sql` en el SQL Editor de Supabase sin errores y verificar que las 3 tablas y políticas RLS queden creadas.

### `[x]` BACK-3: Endpoints de Auth y dependencia JWT (Supabase Auth)
- **Objetivo:** Exponer endpoints de registro, login y perfil actual usando Supabase Auth, y proveer una dependencia reutilizable `get_current_user` para proteger el resto de los endpoints.
- **Archivos Permitidos:** `backend/routers/auth.py`, `backend/schemas.py`, `backend/main.py`
- **Decisiones Acordadas con el Desarrollador:**
  - Se utiliza Supabase Auth nativo para registro/login con email y contraseña, devolviendo el `access_token` (JWT) y `refresh_token` de Supabase.
- **Especificación Técnica:**
  1. Definir en `backend/schemas.py` los modelos Pydantic: `AuthRegisterRequest`, `AuthLoginRequest`, `AuthResponse`, `UserProfileResponse`.
  2. Crear `backend/routers/auth.py` con prefijo `/api/v1/auth`:
     - `POST /register`: registra el usuario en Supabase Auth (`supabase.auth.sign_up`).
     - `POST /login`: autentica con email y contraseña (`supabase.auth.sign_in_with_password`) y retorna tokens + datos básicos del usuario.
     - `GET /me`: valida el Bearer token vía `get_current_user` (`supabase.auth.get_user(token)`) y retorna el perfil.
  3. Registrar el router en `backend/main.py`.
- **Definition of Done (Comando de Verificación):**
  - Probar `POST /api/v1/auth/register`, `POST /api/v1/auth/login` y `GET /api/v1/auth/me` contra Swagger UI (`/docs`) o `curl` con respuesta `200`/`201`.

### `[x]` BACK-4: CRUD de Campos y Campañas/Resultados por Campo
- **Objetivo:** Permitir que cada usuario autenticado cree, liste, consulte, actualice y elimine sus campos, y registre/consulte el historial de campañas (cultivos, fechas, resultados y `simulacion_json`) de cada campo.
- **Archivos Permitidos:** `backend/routers/fields.py`, `backend/routers/campaigns.py`, `backend/schemas.py`, `backend/main.py`
- **Decisiones Acordadas con el Desarrollador:**
  - Todas las consultas se ejecutan con el cliente autenticado del usuario para respetar las políticas RLS de Supabase.
  - Cada campaña pertenece a un `field_id` y puede almacenar opcionalmente `simulacion_json` completo.
- **Especificación Técnica:**
  1. Definir en `backend/schemas.py` los modelos Pydantic: `FieldCreate`, `FieldUpdate`, `FieldResponse`, `CampaignCreate`, `CampaignUpdate`, `CampaignResponse`.
  2. Crear `backend/routers/fields.py` con prefijo `/api/v1/fields`:
     - `GET /`: lista los campos del usuario autenticado.
     - `POST /`: crea un nuevo campo (`nombre`, `lat`, `lon`, `hectareas`).
     - `GET /{field_id}`: obtiene el detalle de un campo.
     - `PATCH /{field_id}` y `DELETE /{field_id}`.
  3. Crear `backend/routers/campaigns.py` con prefijo `/api/v1/fields/{field_id}/campaigns`:
     - `GET /`: lista el historial de campañas/cultivos del campo ordenado por `fecha_inicio` descendente.
     - `POST /`: registra una nueva campaña (`campana`, `cultivo`, `fecha_inicio`, `fecha_fin`, `rinde_kg_ha`, `resultado_notas`, `simulacion_json`).
     - `PATCH /{campaign_id}` y `DELETE /{campaign_id}`: actualiza resultados/fechas o elimina un registro.
  4. Registrar ambos routers en `backend/main.py`.
- **Definition of Done (Comando de Verificación):**
  - Crear un campo, agregar una campaña con fechas/cultivo/resultado y listar el historial del campo autenticado vía `/docs` o `pytest`/script de prueba.

### `[x]` BACK-5: Verificación Live de Auth Supabase, Usuario Demo (`demoereia@gmail.com`) y Nota de Rate Limit Email
- **Objetivo:** Verificar en vivo el servidor FastAPI conectado a Supabase Auth (`/health`, `/api/v1/auth/register`, `/api/v1/auth/login`), validar el usuario demo confirmado en Supabase y documentar la mitigación del `email rate limit exceeded` del SMTP gratuito de Supabase.
- **Archivos Permitidos:** `backend/TASKS_BACKEND.md`
- **Decisiones Acordadas con el Desarrollador:**
  - Usuario demo oficial en Supabase: `demoereia@gmail.com` (creado y confirmado manualmente en Supabase Auth).
  - Para evitar el límite de ~2 correos/hora del SMTP gratuito de Supabase (`email rate limit exceeded`) durante pruebas y demo, se recomienda desactivar **Confirm email** en **Authentication → Providers → Email** del Dashboard de Supabase.
- **Especificación Técnica:**
  1. Levantar FastAPI con `uvicorn` en `http://127.0.0.1:8000` y verificar `GET /health` (`supabase_configured: True`).
  2. Probar `POST /api/v1/auth/register` y `POST /api/v1/auth/login` con `demoereia@gmail.com` obteniendo `200 OK` y `access_token` JWT válido.
- **Definition of Done (Comando de Verificación):**
  - `GET http://127.0.0.1:8000/health` devuelve `{"status":"ok","supabase_configured":true}` y `POST /api/v1/auth/login` con `demoereia@gmail.com` devuelve `200 OK` con `access_token`.

---

## 4.1. Registro de Entorno y Despliegue en Supabase
- **Proyecto Supabase:** Creado bajo categoría *B2B SaaS application* (`https://kjiddadksvosdaoyapfu.supabase.co`).
- **Variables de entorno locales (`backend/.env`):** Archivo creado a partir de `backend/.env.example` con `SUPABASE_URL` (URL base sin `/rest/v1/`, requerida por `supabase-py`), `SUPABASE_KEY` (publishable key) y `CORS_ORIGINS=http://localhost:5173,http://localhost:3000`.
- **Esquema SQL (`backend/sql/schema.sql`):** Listo para ejecutar en el **SQL Editor** de Supabase para crear `public.profiles`, `public.fields`, `public.campaigns`, trigger `on_auth_user_created` y políticas RLS.

---

## 5. Plantilla para Especificar cada Nueva Tarea

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
