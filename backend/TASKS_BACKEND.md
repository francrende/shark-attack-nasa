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
| BACK-3 | Provider ISRIC SoilGrids (0–30 cm ponderado, vecinos ante `null`, fallback GeoINTA, caché) | `backend/providers/soilgrids.py`, `backend/providers/test_soilgrids.py`, `backend/providers/check_soilgrids_live.py` | — | `[x]` |
| BACK-4 | Resiliencia y latencia: caché en capas, caché de NASA por celda de grilla, climatología pampeana precalculada, corte automático de SoilGrids, lotes de ejemplo | `backend/providers/cache.py`, `backend/providers/nasa_telemetry.py`, `backend/providers/soilgrids.py`, `backend/providers/generar_precache.py`, `backend/providers/data/*.json`, `backend/providers/test_cache.py`, `backend/providers/test_nasa_telemetry.py`, `backend/providers/test_soilgrids.py` | BACK-2, BACK-3 | `[x]` |

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
> **Recalibración post-verificación (acordada con el desarrollador):** los umbrales originales 5/12/20 dejaban 11 de 12 puntos de la región en `alto` o `critico`, porque NASA POWER (MERRA-2) da al menos unos 11 días por verano en toda la región. Se midieron 12 puntos (2006–2025) y se pasó a **15/25/40**, manteniendo `T2M_MAX > 34 °C` por coherencia con la feature `frecuencia_estres_termico` del ML. El ML no usa este campo, que es solo informativo.
>
> | Nivel | Días/verano | Puntos de calibración (promedio) |
> | :--- | :--- | :--- |
> | `bajo` | < 15 | Balcarce 11,5 · Tres Arroyos 13,7 · 9 de Julio 14,1 |
> | `medio` | 15 – < 25 | Río Cuarto 23,7 · Pergamino 23,8 |
> | `alto` | 25 – 40 | Gral. Pico 26,2 · Gualeguaychú 30,3 · Marcos Juárez 31,5 · Paraná 34,5 · Rafaela 35,8 |
> | `critico` | > 40 | Reconquista 44,7 · Charata 55,8 |
>
> **Nota operativa:** 4 consultas históricas de 20 años en paralelo contra NASA POWER se colgaron más de 5 minutos. De a una tardan entre 0,3 y 1,7 s. Hay que tenerlo en cuenta en la tarea de caché y si se arman pre-cálculos en lote.
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
    - `bajo`: menos de 15 días.
    - `medio`: de 15 a menos de 25 días.
    - `alto`: de 25 a 40 días.
    - `critico`: más de 40 días.
    - Recalibrados desde 5/12/20; ver la nota al inicio de la tarea.
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
     - Bordes de umbral 15, 25 y 40, más los puntos de calibración.
     - `build_telemetria_nasa` de punta a punta con `MockTransport`.
     - Sin `GWETROOT` válido lanza `NasaPowerUnavailable`.
- **Definition of Done (Comando de Verificación):**
  - `cd backend && python -m pytest providers/ -v`: todos en verde, incluidos los tests de BACK-1.
  - (Opcional, con red) `cd backend && python -m providers.check_nasa_power_live`: imprime el bloque `telemetria_nasa` real de Pergamino.

### `[x]` BACK-3: Provider ISRIC SoilGrids
> **Verificación (14/11/2026):** pasan los 80 tests de `providers/`. En la prueba en vivo, ISRIC no respondió: Pergamino y Tres Arroyos cayeron al fallback por timeout (unos 8,9 s cada uno), y una consulta suelta con timeout de 60 s tampoco respondió. Más temprano respondía en unos 5 s. **El camino con dato real no se pudo verificar en vivo.** Está cubierto por tests con los valores reales de Pergamino capturados antes. La cascada de fallback sí quedó verificada en vivo.
>
> **Riesgo abierto:** con ISRIC caído, cada consulta nueva espera los 8 s antes de caer al fallback, porque esos fallbacks no se cachean. Ver la propuesta de circuit breaker o pre-caché en la conversación.
- **Objetivo:** Cliente async que devuelve el perfil edáfico de un `lat`/`lon`: arcilla, arena, limo, carbono orgánico, pH y clase textural. Si SoilGrids no tiene dato o no responde, sigue una cascada de respaldo y avisa qué no se pudo obtener. Sin endpoint y sin `condicion_rotacion_previa`, que depende del cultivo anterior y es de `/simulate`.
- **Archivos Permitidos:**
  - `backend/providers/soilgrids.py`: el cliente, la cascada, la caché y la tabla de fallback.
  - `backend/providers/test_soilgrids.py`: los tests con mocks.
  - `backend/providers/check_soilgrids_live.py`: el script opcional contra la API real.
- **Hallazgos de la API real (14/11/2026):**
  - La latencia es de unos 5 s por consulta.
  - Tres Arroyos (-38.38, -60.28) devuelve HTTP 200 con todos los valores en `null`.
  - Las unidades vienen escaladas por `d_factor = 10`: `clay`, `sand` y `silt` en g/kg (÷10 da %), `soc` en dg/kg (÷10 da g/kg) y `phh2o` en pH×10.
- **Decisiones Acordadas con el Desarrollador:**
  - **Profundidad:** todas las propiedades se ponderan en **0–30 cm**, con pesos de 5, 10 y 15 cm para `0-5cm`, `5-15cm` y `15-30cm`.
    - ⚠️ **Avisar al track de ML:** el modelo entrenó con la arcilla de **0–5 cm** ([generate_dataset.py:479](ml/generate_dataset.py#L479)). En Pergamino da 23,4 % (0–30 cm) contra 22,0 % (0–5 cm).
  - **Una sola llamada:** `property` = `clay`, `sand`, `silt`, `soc` y `phh2o`; `depth` = `0-5cm`, `5-15cm` y `15-30cm`; `value=mean`.
  - **Timeout:** 8 s, **sin reintento**. El provider es async para que `/simulate` lo consulte en paralelo con NASA POWER.
  - **Cascada:**
    1. **Punto pedido.** Si responde con dato, se usa.
    2. **Si responde `null`** (píxel urbano o de agua): se consultan **4 vecinos a unos 500 m (N, S, E, O) en paralelo**, con el mismo timeout de 8 s, y se usa el primero con dato real, en ese orden.
    3. **Si hay timeout, error de red, HTTP 429/5xx, o los vecinos también dan `null`:** se usa la **localidad GeoINTA más cercana, hasta 100 km**, y solo para la arcilla. `fuente = "fallback_regional"`. Ante 429 o timeout se pasa directo a este paso, sin consultar vecinos.
    4. **Si no hay localidad a menos de 100 km:** se lanza `SoilGridsUnavailable`, que el router convertirá en 503.
  - **Advertencia visible:** con el fallback regional, el resultado lleva en `advertencias` el texto *"Textura estimada regionalmente, carbono orgánico no disponible: el ajuste de rotación por carbono no se aplicó."*
  - **Caché:** en memoria, por coordenada redondeada a 3 decimales (unos 100 m), **sin vencimiento**.
    - **Se cachean** los resultados reales (del punto o de un vecino) y el caso **"punto y 4 vecinos en `null`"**, que es determinístico: esas celdas siempre dan `null`. Las consultas siguientes a esa coordenada van directo al fallback, sin llamar a ISRIC.
    - **No se cachean** los fallbacks por timeout, 429, 5xx o error de red, porque son fallas transitorias.
  - **Límite de ISRIC (5 llamadas por minuto, por IP):** el proceso lleva un contador de ventana deslizante de 60 s.
    - Si no queda cupo para la llamada principal, se va directo al fallback regional.
    - Si hay que consultar vecinos y queda cupo para menos de 4, se consultan solo los que entran (en orden N, S, E, O). En ese caso el "todo `null`" no se cachea, porque no se probaron los 4.
    - Peor caso por campo: 1 + 4 = 5 llamadas.
- **Decisiones por defecto del agente (corregir si no aplican):**
  - **"Con dato" = arcilla presente:** un punto se considera con dato si la arcilla 0–30 cm no es `null`, porque es la feature que necesita el ML. Si falta la arcilla, se trata como `null` y se consultan los vecinos.
  - **Advertencia por vecino:** si el perfil sale de un vecino, se agrega *"Perfil de suelo tomado a ~500 m del punto marcado (sin dato en SoilGrids: zona urbana o espejo de agua)."*
  - **Vecinos:** se desplazan unos 500 m en latitud (0,0045°) y en longitud (0,0045° / cos(lat)).
  - **Dato parcial:** si alguna propiedad viene `null` y otras no, se usan las que vinieron. Se agrega una advertencia por cada propiedad faltante (por ejemplo, sin `soc`: *"carbono orgánico no disponible: el ajuste de rotación por carbono no se aplicó"*). Si falta alguna profundidad, se pondera con las que haya.
  - **Clase textural:** se usa el triángulo USDA, con nombres en español `snake_case` (por ejemplo `franco_limoso`, como en el contrato) y arena+limo+arcilla normalizados a 100. Si falta alguna de las tres, `textura_predominante = None`, lo que pasa siempre con el fallback.
  - **Tabla GeoINTA:** se **copia** a `soilgrids.py` (id, nombre, lat, lon y `fallback_clay_pct` de las 15 localidades de `AGRO_LOCATIONS`), en lugar de importarla desde `ml/`, para no acoplarse a un archivo de otro track. Distancia por haversine.
  - **No se toca `schemas.py`:** el provider devuelve una `dataclass` de dominio. El modelo Pydantic de `perfil_suelo` y la ubicación de `advertencias` en la respuesta son de la tarea de `/simulate`, porque el contrato §5 no tiene un campo para eso. Opciones: `validacion_local_requerida.brechas_informacion` o un campo nuevo.
- **Especificación Técnica:**
  1. Constantes:
     - `BASE_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"`
     - `PROPIEDADES = ["clay", "sand", "silt", "soc", "phh2o"]`
     - `PROFUNDIDADES = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}`
     - `TIMEOUT_S = 8.0`
     - `OFFSET_VECINO_GRADOS = 0.0045`
     - `RADIO_FALLBACK_KM = 100`
  2. `dataclass` congelada `PerfilSueloSatelital`:
     - `arcilla_pct`, `arena_pct`, `limo_pct`, `carbono_organico_g_kg`, `ph`: `float | None`
     - `textura_predominante: str | None`
     - `fuente: Literal["isric_soilgrids_v2", "isric_soilgrids_v2_vecino", "fallback_regional"]`
     - `distancia_fuente_km: float`: 0 si es el punto pedido, unos 0,5 si es un vecino, y la distancia a la localidad si es fallback.
     - `localidad_fallback: str | None`
     - `advertencias: tuple[str, ...]`
  3. Funciones puras:
     - `_parsear(payload) -> dict[str, float | None]`: pondera 0–30 cm y aplica el `d_factor`.
     - `clasificar_textura_usda(arena, limo, arcilla) -> str`
     - `_localidad_mas_cercana(lat, lon) -> tuple[dict, float] | None`
  4. Función pública: `async def fetch_perfil_suelo(lat, lon, *, client=None) -> PerfilSueloSatelital`. Valida las coordenadas (`ValueError`), consulta la caché y aplica la cascada.
  5. Excepción `SoilGridsUnavailable(Exception)`.
  6. Tests mínimos:
     - Parseo y ponderación 0–30 cm con `d_factor`.
     - Ponderación con una profundidad faltante.
     - Bordes del triángulo USDA, y que Pergamino da `franco_limoso`.
     - Respuesta `null` → vecino con dato → `fuente="isric_soilgrids_v2_vecino"`.
     - Vecinos también en `null` → fallback regional.
     - Timeout → fallback directo, sin consultar vecinos.
     - 429 → fallback directo.
     - Fallback con la advertencia exacta y `textura_predominante=None`.
     - Fuera de 100 km (por ejemplo Madrid) → `SoilGridsUnavailable`.
     - Dato parcial (sin `soc`) → advertencia de carbono.
     - La segunda llamada a la misma coordenada redondeada no hace request (caché).
     - El fallback por timeout no se cachea, y el "punto y 4 vecinos en `null`" sí.
     - Sin cupo en el limitador → fallback directo sin request. Con cupo parcial, se consultan solo los vecinos que entran.
     - Coordenadas inválidas → `ValueError`.
- **Definition of Done (Comando de Verificación):**
  - `cd backend && python -m pytest providers/ -v`: todos en verde, incluidos los de BACK-1 y BACK-2.
  - (Opcional, con red) `cd backend && python -m providers.check_soilgrids_live`: imprime el perfil de Pergamino (dato real) y de Tres Arroyos (vecino o fallback).

### `[x]` BACK-4: Resiliencia y latencia (caché, precálculo y corte automático)
> **Verificación (14/11/2026):**
> - **Tests:** pasan los 107 de `providers/`.
> - **Precálculo:** `generar_precache nasa` generó **299/299 celdas sin fallas** (786 KB). Distribución del riesgo: bajo 41, medio 74, alto 119, crítico 65. Coincide con la calibración: Balcarce 11,5 (bajo), Pergamino 23,8 (medio), Rafaela 35,8 (alto).
> - **En vivo:** el primer lote de una celda tarda 1,57 s (solo la ventana reciente) y otro lote de la misma celda 0,22 s, contra 1,72 s antes. La anomalía no cambió (−37,38 %).
>
> **Pendiente:** `generar_precache suelo` no se pudo correr porque ISRIC sigue sin responder. Correrlo cuando vuelva, y confirmar los 4 lotes de ejemplo con el frontend.
>
> **Para coordinar tras el pull de `main` (ML-4):**
> - `predictor.py` trae su propio `classify_summer_thermal_risk` (días en una ventana de 90 días, cortes 3,5/7, sin `critico`) y `classify_soil_texture` (solo arcilla). Se superponen con `riesgo_termico_verano` (dic–feb, 15/25/40) y con la clasificación USDA de este track. Hay que acordar cuál llena el contrato.
> - En el ML, las tormentas, el estrés térmico y las heladas pasaron a la **ventana futura** `[t+1, t+90]`. En producción hay que calcularlas como el promedio histórico de esos 90 días. `frecuencia_tormentas_extremas_90d` de la telemetría (90 días pasados) **no** es esa feature.
- **Objetivo:** Que cualquier jurado, en cualquier punto y en cualquier momento, reciba respuesta rápida, y que una caída de ISRIC no deje datos aproximados guardados para siempre. Sin Supabase (lo implementa otro compañero), pero con la caché lista para enchufarlo.
- **Contexto:** los jurados prueban la app **solos, sin guía y en puntos arbitrarios**. Por eso una pre-caché de puntos fijos sirve poco, y el foco pasa a la **caché por celda de grilla** y al **precálculo regional**.
- **Hallazgo verificado (14/11/2026):** NASA POWER devuelve **valores idénticos** (`PRECTOTCORR`, `T2M_MAX`, `GWETROOT`, todo 2020) para puntos distintos dentro de la misma celda de 0,5° × 0,625°, y valores distintos en la celda vecina. Caveat: `ALLSKY_SFC_SW_DWN` usa otra grilla (1° × 1°); hoy no se usa en ningún cálculo.
- **Archivos Permitidos:**
  - `backend/providers/cache.py` (nuevo): la interfaz de caché, la capa en memoria y la composición en capas.
  - `backend/providers/nasa_telemetry.py`: usa la caché por celda y el precálculo.
  - `backend/providers/soilgrids.py`: corte automático, caché vía la interfaz, lotes de ejemplo y marca de reintento.
  - `backend/providers/generar_precache.py` (nuevo): script offline.
  - `backend/providers/data/climatologia_pampa.json` y `backend/providers/data/suelo_lotes_ejemplo.json` (nuevos, generados por el script).
  - Tests: `backend/providers/test_cache.py` (nuevo), `test_nasa_telemetry.py` y `test_soilgrids.py`.
- **Decisiones Acordadas con el Desarrollador:**
  - **Interfaz de caché enchufable:** `get(espacio, clave)` y `set(espacio, clave, valor, ttl_s=None)`, con valores **serializables a JSON**.
    - Implementación inicial: `CacheMemoria`.
    - `CacheEnCapas(primaria, secundaria=None)` lee de la memoria. Si no encuentra, lee de la secundaria (Supabase, a futuro) y completa la memoria. `set` escribe en ambas.
    - **No se implementa Supabase.**
  - **Caché de NASA, clave = celda de la grilla POWER** (centro: `round(lat/0,5)·0,5`, `round(lon/0,625)·0,625`):
    - **Histórico (`nasa_hist`):** se guarda lo **calculado**, no la serie cruda de 20 años: `{climatologia_lluvia_90d_por_doy, dias_calor_verano_promedio, riesgo_termico_verano, version_calculo}`. **Sin vencimiento.** Si `version_calculo` no coincide con la actual, se trata como no encontrado.
    - **Ventana reciente (`nasa_reciente`):** la serie de 100 días serializada, con **TTL de 6 h**, en memoria.
    - Si NASA falla en la ventana reciente: `NasaPowerUnavailable` con un **mensaje claro** (503). **No hay foto precargada** de la ventana reciente.
  - **Climatología pampeana precalculada:** `generar_precache.py nasa` calcula el histórico de **todas las celdas de la región pampeana**, **de a una consulta** (las consultas en paralelo se colgaban), y lo guarda en `data/climatologia_pampa.json`.
    - Se carga en la caché **la primera vez que se usa**, para no depender de `main.py`.
    - Una celda fuera del JSON se calcula en vivo y se cachea.
  - **Suelo precargado solo para 3–4 lotes de ejemplo** que el frontend ofrezca en el mapa:
    - Coincidencia exacta (a menos de 100 m), sin vencimiento, `fuente = "precache"`.
    - `generar_precache.py suelo` los genera cuando ISRIC esté disponible, y se guardan en `data/suelo_lotes_ejemplo.json`.
  - **Corte automático de SoilGrids:**
    - **1 timeout o un 429** corta las llamadas por **5 minutos**. Mientras dura, se va directo al fallback regional, sin llamar a ISRIC.
    - Pasados los 5 minutos se hace **1 llamada de prueba**: si responde, se reabre, y si falla, se corta otros 5 minutos.
  - **Datos aproximados no permanentes:** `PerfilSueloSatelital` gana `reintentar_soilgrids: bool`, en `True` cuando el resultado es un fallback por falla transitoria (corte, timeout, 429, 5xx, red o límite de llamadas).
    - Quien persista campos (Supabase) debe reintentar SoilGrids al reabrirlos si la marca está en `True`.
    - Esos resultados **nunca se escriben en la caché**, en ninguna de las capas.
- **Decisiones por defecto del agente (corregir si no aplican):**
  - **Clave de la caché:** es un `str`. Hay helpers para las dos formas: `clave_coordenada(lat, lon)` (3 decimales, para el suelo) y `clave_celda_power(lat, lon)` (para NASA). Así la misma interfaz sirve para los dos casos y para Supabase.
  - **Región pampeana precalculada:** lat de -39,0 a -28,0 y lon de -65,0 a -57,5 (centros de celda), unas 300 celdas. Se guardan con un decimal (unos 800 KB), y el script tarda unos 10 minutos.
  - **Qué se usa del histórico cacheado:** se guarda `dias_calor_verano_promedio` y la categoría se **reclasifica al leer**, con los umbrales vigentes. Así una recalibración no invalida la caché. `riesgo_termico_verano` se guarda solo como referencia.
  - **El "punto y 4 vecinos sin dato" de BACK-3** pasa a la interfaz como `{"sin_dato": true}`. Es determinístico, así que `reintentar_soilgrids = False`.
  - **Descarto el "perfil de lote de referencia a hasta 30 km"** de la ronda anterior de preguntas: con solo 3–4 lotes precargados casi nunca aplicaría.
  - **Lotes de ejemplo propuestos:** Pergamino (-33,95, -60,57), Marcos Juárez (-32,70, -62,10), Balcarce (-37,85, -58,26) y Rafaela (-31,25, -61,49). **A confirmar con el frontend.**
  - **Coordenadas justo en el borde de una celda:** se asignan con `round()` de Python. No se verificó qué celda asigna NASA en esos casos.
- **Especificación Técnica:**
  1. `cache.py`:
     - `class Cache(Protocol)` con `get` y `set`.
     - `CacheMemoria(reloj=time.monotonic)` con TTL.
     - `CacheEnCapas`.
     - Las funciones `clave_coordenada` y `clave_celda_power`.
     - La instancia por defecto `cache_global` y `configurar_cache(cache)` para enchufar Supabase o tests.
  2. `nasa_telemetry.py`:
     - `VERSION_CALCULO = "telemetria-v1"`.
     - `obtener_referencia_historica(lat, lon, client)`: caché, luego JSON precalculado, luego cálculo en vivo.
     - `obtener_ventana_reciente(...)`: caché con TTL de 6 h o NASA en vivo.
     - `build_telemetria_nasa` las usa, y la firma no cambia.
     - `cargar_climatologia_precalculada()`, de carga única y perezosa.
  3. `soilgrids.py`:
     - `CorteAutomatico(duracion_s=300, reloj)`, con los estados cerrado, abierto y en prueba.
     - La caché pasa por la interfaz (espacio `suelo`).
     - `cargar_lotes_ejemplo()`, perezosa.
     - El campo `reintentar_soilgrids` y la `Fuente` gana `"precache"`.
  4. `generar_precache.py`, con dos subcomandos:
     - `nasa`: secuencial, reanudable (saltea las celdas ya presentes) e imprime el avance.
     - `suelo`: secuencial, respeta las 5 llamadas por minuto y no guarda los fallbacks.
  5. Tests mínimos:
     - Caché: TTL que vence, capa secundaria que completa la primaria, `set` que escribe en ambas capas.
     - Claves: la celda agrupa puntos de la misma celda y separa los de la vecina.
     - NASA: una segunda llamada en la misma celda no hace requests. La ventana reciente vence a las 6 h. Una `version_calculo` distinta se recalcula. Se usa el JSON precalculado sin hacer la request histórica.
     - Corte automático: un timeout abre el corte, durante el corte no hay requests, a los 5 minutos hay 1 llamada de prueba, con éxito se reabre y con falla se corta otros 5 minutos.
     - Marca de reintento: es `True` en los fallbacks transitorios y `False` en los de "sin dato". Los transitorios no llegan a ninguna capa de caché.
     - Lote de ejemplo: a menos de 100 m da `fuente="precache"` sin request.
- **Definition of Done (Comando de Verificación):**
  - `cd backend && python -m pytest providers/ -v`: todos en verde.
  - `cd backend && python -m providers.generar_precache nasa`: genera `data/climatologia_pampa.json` con unas 300 celdas.
  - (Cuando ISRIC esté disponible) `cd backend && python -m providers.generar_precache suelo`.
- **Riesgo anotado (fuera de alcance de BACK-4):** el plan gratuito de Render **duerme el servicio** tras 15 minutos sin tráfico, y el primer jurado espera unos 30–60 s. Hace falta un **ping cada 10 minutos** (por ejemplo, un cron externo o UptimeRobot a un `/health`). Tarea de deploy, coordinar con quien tenga `main.py`.

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
