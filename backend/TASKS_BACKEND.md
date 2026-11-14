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
| BACK-2 | Bloque `telemetria_nasa` (humedad, tendencia de 15 días, anomalía de lluvia de 90 días, tormentas extremas, riesgo térmico de verano) | `backend/schemas.py`, `backend/providers/nasa_power.py`, `backend/providers/nasa_telemetry.py`, `backend/providers/test_nasa_telemetry.py`, `backend/providers/check_nasa_power_live.py` | BACK-1 | `[x]` |

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

### `[x]` BACK-2: Bloque `telemetria_nasa`
> **Observación post-verificación (pendiente de decisión):** contra la API real, Pergamino da un promedio de **23,8 días/verano con `T2M_MAX > 34 °C`** (2006–2025, MERRA-2), así que sale `critico`. Los umbrales 5/12/20 dejan casi toda la zona núcleo en `critico`. Hay que recalibrarlos (ver la conversación con el desarrollador) antes de la demo.
- **Objetivo:** Construir el bloque `telemetria_nasa` del contrato (CONTEXT §5) a partir de NASA POWER, con el dato satelital real y sus 7 campos. Quedan fuera el What-If, las features exclusivas de ML, `anomalias_detectadas`, la elevación y el endpoint.
- **Archivos Permitidos:**
  - `backend/schemas.py`: modelo Pydantic `TelemetriaNasa`.
  - `backend/providers/nasa_power.py`: refactor chico, se agrega un fetch por rango de fechas.
  - `backend/providers/nasa_telemetry.py`: los cálculos y el armado del bloque.
  - `backend/providers/test_nasa_telemetry.py`: los tests.
  - `backend/providers/check_nasa_power_live.py`: se le agrega la impresión de la telemetría.
- **Decisiones Acordadas con el Desarrollador:**
  - **Fuente histórica:** request diario 2006-01-01 → 2025-12-31 (`PRECTOTCORR`, `T2M_MAX`), en paralelo con el request reciente.
  - **`anomalia_lluvia_90d_pct`:** se calcula **igual que `extract_real_90d_windows` en `backend/ml/generate_dataset.py`**, para que no haya diferencias entre entrenamiento e inferencia:
    - Referencia: climatología por día del año (`doy`). Se rellenan los `-999` con `ffill` y luego `bfill`, se hace la suma móvil de 90 días con `min_periods=75` y se promedia por `doy`.
    - `hist = max(25, clim[doy_fin])`, con 180 por defecto si falta ese `doy`.
    - Actual: suma de los 90 días que terminan en la **fecha de corte** (ver más abajo).
    - `anomalía = (actual − hist) / hist × 100`, recortada a [−80, +140] y redondeada a 2 decimales.
  - **`tendencia_humedad_15d_pct`:** igual que el script de ML.
    - `0.65 × (GWETROOT%[corte] − GWETROOT%[corte−14d]) + 0.35 × (GWETTOP%[corte] − GWETTOP%[corte−14d])`. Equivale a `iloc[-15]` en el script.
    - Recortada a [−40, 40] y redondeada a 2 decimales.
  - **`frecuencia_tormentas_extremas_90d`:** días con `PRECTOTCORR > 50 mm` en la ventana de 90 días, recortado a [0, 12]. Igual que el script de ML.
  - **Ventana reciente de 100 días:** la regla "30 a 90 días" de CONTEXT §3.1.A se interpreta como un **mínimo**. Se piden 100 días para que, con un lag de hasta 10 días, entren 90 días válidos.
  - **Fecha de corte:** es el último día en que `PRECTOTCORR`, `GWETROOT` y `GWETTOP` son válidos a la vez. Todos los cálculos recientes terminan ahí, igual que la `last_row` del script de ML.
  - **`riesgo_termico_verano`:** promedio histórico de días con `T2M_MAX > 34 °C` entre el 1/12 y el 28-29/2. Se usan solo temporadas completas (dic 2006–feb 2007 … dic 2024–feb 2025, 19 en total). Umbrales:
    - `bajo`: menos de 5 días.
    - `medio`: de 5 a menos de 12 días.
    - `alto`: de 12 a 20 días.
    - `critico`: más de 20 días.
  - **What-If:** **no** modifica `telemetria_nasa`, que siempre muestra el dato real. Se aplica sobre las features en la tarea de `/simulate`.
  - **Features de ML:** `frecuencia_estres_termico`, `frecuencia_riesgo_helada` e `indice_aridez_evaporativa` quedan **fuera** de esta tarea, hasta que el track de ML confirme las ventanas.
  - **Fuera de alcance:** `anomalias_detectadas` (tarea aparte) y la elevación de `geometry.coordinates` (va en la tarea de SRTM).
- **Decisiones por defecto del agente (corregir si no aplican):**
  - `fetch_daily_window` gana un parámetro `dias`. Por defecto sigue en 30, así que BACK-1 no cambia.
  - Si en la ventana de 90 días hay huecos internos en `-999`, se rellenan con `ffill` y `bfill`, igual que en el script de ML. Si hay **menos de 75 días válidos** de `PRECTOTCORR`, se lanza `NasaPowerUnavailable`.
  - Si no existe una fecha de corte (ningún día con los 3 parámetros válidos en la ventana de 100 días), se lanza `NasaPowerUnavailable`, que el router convertirá en 503. Nunca se inventan datos.
  - `fecha_ultimo_dato_valido` es la fecha de corte.
  - Los porcentajes de humedad son `GWET* × 100`, redondeados a 1 decimal y sin recortar, porque es el dato a mostrar.
  - Los cálculos se hacen en Python puro, sin pandas en el camino online. Un test de paridad contra pandas valida la climatología, y se saltea si pandas no está instalado.
- **Especificación Técnica:**
  1. `nasa_power.py`:
     - Se agrega `fetch_daily_range(lat, lon, start, end, parametros, *, client=None) -> NasaPowerDailySeries`.
     - `fetch_daily_window(..., dias=30)` pasa a delegar en esa función.
  2. `schemas.py`: `TelemetriaNasa(BaseModel)` con estos campos:
     - `fecha_ultimo_dato_valido: date`
     - `indice_humedad_radicular_pct: float`
     - `indice_humedad_superficial_pct: float`
     - `tendencia_humedad_15d_pct: float`
     - `anomalia_lluvia_90d_pct: float`
     - `frecuencia_tormentas_extremas_90d: int`
     - `riesgo_termico_verano: Literal["bajo", "medio", "alto", "critico"]`
  3. `nasa_telemetry.py`, funciones puras testeables:
     - `fecha_de_corte(serie_reciente)`
     - `ventana_90d_rellena(serie_reciente, corte)`
     - `climatologia_lluvia_90d_por_doy(serie_hist)`
     - `anomalia_lluvia_90d_pct(ventana, clim, corte)`
     - `tendencia_humedad_15d_pct(ventana)`
     - `tormentas_extremas_90d(ventana)`
     - `dias_calor_verano_promedio(serie_hist)`
     - `clasificar_riesgo_termico(dias)`
  4. `nasa_telemetry.py`, orquestador: `async def build_telemetria_nasa(lat, lon, *, client=None, today=None) -> TelemetriaNasa`. Hace los 2 requests con `asyncio.gather`.
  5. Tests mínimos:
     - Climatología con huecos `-999` y `min_periods`.
     - Paridad con pandas.
     - Anomalía positiva, negativa y en los topes −80 y +140.
     - La fecha de corte es el último día con los 3 parámetros válidos, y la ventana termina ahí.
     - Tendencia (signo, pesos y topes ±40).
     - Tormentas (umbral > 50 mm y tope 12).
     - Menos de 75 días válidos lanza `NasaPowerUnavailable`.
     - Conteo de días de calor solo con temporadas completas.
     - Bordes de umbral 5, 12 y 20.
     - `build_telemetria_nasa` de punta a punta con `MockTransport`.
     - Sin `GWETROOT` válido lanza `NasaPowerUnavailable`.
- **Definition of Done (Comando de Verificación):**
  - `cd backend && python -m pytest providers/ -v`: todos en verde, incluidos los tests de BACK-1.
  - (Opcional, con red) `cd backend && python -m providers.check_nasa_power_live`: imprime el bloque `telemetria_nasa` real de Pergamino.

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
