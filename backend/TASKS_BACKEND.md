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
| BACK-1 | Provider crudo NASA POWER (ventana 30 días + filtro `-999`) | `backend/providers/nasa_power.py`, `backend/providers/test_nasa_power.py`, `backend/providers/check_nasa_power_live.py` | — | `[x]` |

---

## 3.1. Especificación de Tareas

### `[x]` BACK-1: Provider crudo de NASA POWER API
- **Objetivo:** Cliente HTTP aislado que trae la serie diaria de los últimos 30 días de NASA POWER para un `lat`/`lon`, limpia los valores `-999` y expone el último valor válido de cada parámetro. No calcula métricas derivadas ni expone endpoints.
- **Archivos Permitidos:**
  - `backend/providers/nasa_power.py`: el cliente.
  - `backend/providers/test_nasa_power.py`: los tests con mocks.
  - `backend/providers/check_nasa_power_live.py`: el script opcional contra la API real.
- **Decisiones Acordadas con el Desarrollador:**
  - **Alcance:** solo el provider crudo. La anomalía de lluvia de 90 días, el riesgo térmico y el armado de `telemetria_nasa` quedan para **BACK-2**.
  - **Fallas:** timeout de 10 s y 1 reintento ante timeout, error de red o HTTP 5xx. Si igual falla, se lanza `NasaPowerUnavailable`. El mapeo a **HTTP 503** lo hace el router cuando exista, no en esta tarea.
  - **Caché:** no hay en esta tarea (va en una tarea posterior).
  - **Verificación:** pytest con respuestas mockeadas (sin red) y un script opcional contra la API real.
- **Decisiones por defecto del agente (corregir si no aplican):**
  - Cliente **async** con `httpx.AsyncClient`, para poder consultarlo en paralelo con SoilGrids en BACK-2.
  - Si un parámetro tiene los 30 días en `-999`, su último valor válido es `None` y **no se lanza error**. Qué hacer en ese caso lo decide BACK-2.
  - Las coordenadas fuera de rango (`lat ∉ [-90, 90]`, `lon ∉ [-180, 180]`) lanzan `ValueError` antes de llamar a la API.
  - Los tests usan `httpx.MockTransport` y `asyncio.run`, para no sumar `respx` ni `pytest-asyncio`. Solo hay que agregar `pytest` a `requirements.txt`.
- **Especificación Técnica:**
  1. Constantes:
     - `BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"`
     - `PARAMETROS = ["GWETROOT", "GWETTOP", "GWETPROF", "PRECTOTCORR", "T2M", "T2M_MAX", "T2M_MIN", "EVPTRNS", "ALLSKY_SFC_SW_DWN"]`
     - `VENTANA_DIAS = 30`
     - `FILL_VALUE = -999.0`
  2. Query: `parameters=<csv>&community=AG&longitude=<lon>&latitude=<lat>&start=YYYYMMDD&end=YYYYMMDD&format=JSON`, con `end = hoy (UTC)` y `start = end - 29 días`.
  3. Parseo de `properties.parameter.{PARAM}.{YYYYMMDD}`. Cualquier valor `<= -999` (o `-999.0` exacto) pasa a `None`.
  4. Modelo de retorno (`dataclass` congelada) `NasaPowerDailySeries`:
     - `lat`, `lon`, `start: date`, `end: date`
     - `series: dict[str, dict[date, float | None]]`
     - `last_valid(param) -> tuple[date, float] | None`: recorre de la fecha más reciente hacia atrás.
  5. Función pública: `async def fetch_daily_window(lat, lon, *, client: httpx.AsyncClient | None = None, today: date | None = None) -> NasaPowerDailySeries`. Los parámetros `client` y `today` son inyectables para los tests.
  6. Excepción `NasaPowerUnavailable(Exception)` para timeouts, errores de red, HTTP no-2xx y JSON malformado o sin `properties.parameter`.
  7. Tests mínimos:
     - Parseo correcto.
     - Las últimas fechas en `-999` se saltean en `last_valid`.
     - Un parámetro todo en `-999` devuelve `None`.
     - Un 500 seguido de un 200 funciona (reintento).
     - Dos 500 seguidos lanzan `NasaPowerUnavailable`.
     - Un timeout lanza `NasaPowerUnavailable`.
     - Coordenadas inválidas lanzan `ValueError`.
     - La query enviada tiene `community=AG` y la ventana de 30 días.
- **Definition of Done (Comando de Verificación):**
  - `cd backend && python -m pytest providers/test_nasa_power.py -v`: todos los tests en verde.
  - (Opcional, con red) `cd backend && python -m providers.check_nasa_power_live`: imprime el último valor válido de cada parámetro para Pergamino (-33.95, -60.57).

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
