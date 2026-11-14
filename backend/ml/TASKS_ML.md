# TASKS_ML.md — Tablero y Protocolo de Tareas Atómicas (Track ML, FAO-56 & Agronomía)

> **Fuente de la Verdad:** Antes de proponer o programar cualquier tarea, el agente DEBE leer [`../../CONTEXT.md`](../../CONTEXT.md) (especialmente las **Secciones 4, 5 y 8**).

---

## 1. Protocolo Obligatorio para el Agente (Cómo trabajar con el Desarrollador)

Cada vez que el desarrollador te pida crear, detallar o avanzar con una tarea de Machine Learning o Agronomía, seguí **estrictamente estos 4 pasos en orden**:

1. **Consultar el Contexto General:** Revisá la arquitectura de ML y la matriz agronómica en la **Sección 4** y el contrato JSON en la **Sección 5** de [`../../CONTEXT.md`](../../CONTEXT.md).
2. **Hacer Preguntas de Definición (Obligatorio ANTES de cerrar la especificación o programar):**
   - No asumas decisiones agronómicas o de modelado que estén abiertas (ej. catálogo final de cultivos por campaña, puntajes exactos de penalización por monocultivo, comportamiento de las curvas FAO-56 ante sequía o exceso hídrico, hiperparámetros del modelo, umbrales para clasificar el riesgo como bajo/medio/alto/crítico, idioma y formato de `factores_clave_ml` y `explicacion`).
   - **Hacele preguntas claras y concretas al desarrollador** para alinear esos criterios antes de escribir la especificación final.
3. **Documentar la Tarea Atómica en este archivo:**
   - Con las respuestas del desarrollador, redactá la especificación de la tarea en la sección **3. Especificación de Tareas Atómicas** de este archivo usando la plantilla estándar y marcala como `[~]` (En progreso).
4. **Implementar y Verificar (Definition of Done):**
   - Escribí el código respetando el **Scope Exclusivo de Carpetas**, ejecutá las pruebas/entrenamiento de verificación y, cuando pasen sin errores, marcá la tarea como `[x]`.

---

## 2. Reglas de Aislamiento (Cero Conflictos en Git)

- **Archivos Permitidos (Scope Exclusivo de ML & Agronomía):**
  - `backend/ml/*` (`train_baseline.py`, `predictor.py`, `modelo_agro.joblib`, etc.)
  - `backend/services/rotation_matrix.py`
  - `backend/ml/TASKS_ML.md`
- **Archivos Prohibidos:** NO modificar `backend/schemas.py`, `backend/providers/*`, `backend/routers/*`, `backend/services/simulation_service.py`, `backend/main.py` ni `frontend/*` (pertenecen a otros miembros del equipo).

---

## 3. Tablero de Tareas Atómicas (ML & Agronomía)

*(Vacío inicialmente — El agente irá agregando aquí cada tarea junto con el desarrollador luego de la etapa de preguntas).*

| ID | Tarea Atómica | Archivos Involucrados | Depende de | Estado |
| :--- | :--- | :--- | :---: | :---: |
| `ML-1` | Generación del Dataset con Telemetría Histórica Real NASA POWER (20 años) + SRTM + SoilGrids, Desacople Espacial y Split Temporal (70/15/15) | `backend/ml/generate_dataset.py`, `backend/ml/data/nasa_raw_telemetry.json`, `backend/ml/data/train.csv`, `backend/ml/data/val.csv`, `backend/ml/data/test.csv` | — | `[x]` |

---

## 4. Especificación de Tareas Atómicas

### `[x]` ML-1: Generación del Dataset con Telemetría Histórica Real NASA POWER (20 años) + SRTM + SoilGrids, Desacople Espacial y Split Temporal (70/15/15)
- **Objetivo:** Construir el dataset de entrenamiento (`train.csv`, 70%), validación (`val.csv`, 15%) y testeo (`test.csv`, 15%) libre de *Domain Shift* y de *Overfitting* (espacial y temporal), extrayendo ventanas históricas reales de 20 años (2006–2025) de **NASA POWER API (`SMAP/GLDAS/IMERG`)**, topografía de **NASA SRTM (OpenTopoData)** y textura de **ISRIC SoilGrids** en localidades agrícolas reales, cacheadas localmente en `backend/ml/data/nasa_raw_telemetry.json`.
- **Archivos Permitidos:** `backend/ml/generate_dataset.py`, `backend/ml/data/nasa_raw_telemetry.json`, `backend/ml/data/train.csv`, `backend/ml/data/val.csv`, `backend/ml/data/test.csv`, `backend/ml/data/dataset_metadata.json`, `backend/ml/TASKS_ML.md`
- **Decisiones Acordadas con el Desarrollador:**
  - **Eliminación de *Domain Shift* (Datos Reales de APIs NASA):**
    - Descargar series diarias reales de **20 años (`2006-01-01` a `2025-12-31`)** de `NASA POWER API` (`community=AG`, parámetros: `GWETROOT`, `GWETTOP`, `PRECTOTCORR`, `T2M_MAX`, `T2M_MIN`, `EVPTRNS`), filtrando valores faltantes (`-999.0`), junto con elevación/pendiente real de `OpenTopoData SRTM 30m` (y fallback a `geometry.coordinates[2]` de NASA POWER) y arcilla de `ISRIC SoilGrids` en **15 localidades representativas de la Región Pampeana y agrícola argentina** (Pergamino, Venado Tuerto, Marcos Juárez, Río Cuarto, Trenque Lauquen, Tandil, Balcarce, Tres Arroyos, Chascomús, Paraná, Rafaela, General Pico, Junín, Azul, Victoria).
    - Persistir la telemetría cruda descargada en `backend/ml/data/nasa_raw_telemetry.json` para que futuras ejecuciones de `generate_dataset.py` no requieran red si el caché ya existe.
    - Calcular las 8 features hidroclimáticas sobre ventanas reales de 90 días usando exactamente las mismas fórmulas determinísticas que ejecutará el backend en producción (`POST /api/v1/simulate`), más un 15% de perturbaciones tipo *What-If* sobre ventanas reales para cubrir los extremos de los sliders del simulador.
  - **Eliminación de *Overfitting Espacial* (Desacople de Variables Estáticas):**
    - Como `elevacion_m`, `pendiente_terreno_pct` y `textura_arcilla_pct` son constantes para un punto `(lat, lon)`, al construir cada muestra a partir de una ventana climática real de una localidad, se aplica variabilidad continua intra-zona (*spatial jittering* realista sobre la distribución topográfica/edáfica local y cruce con perfiles de lotes vecinos) para que el árbol nunca pueda memorizar una coordenada fija por su altitud o arcilla exacta.
  - **Eliminación de *Data Leakage Temporal* (Split por Bloques Temporales 70 / 15 / 15):**
    - En lugar de mezclar fechas cercanas aleatoriamente, las ventanas históricas reales se particionan cronológicamente (*Out-of-Time Split*) asegurando proporción `70% Train / 15% Validation / 15% Test` estratificada por los 11 cultivos (`16.500` filas totales: `11.550` Train, `2.475` Val, `2.475` Test):
      - **Train (70%):** Ventanas históricas de campañas `2006–2019` (`11.550` filas).
      - **Validation (15%):** Ventanas históricas de campañas `2020–2022` (`2.475` filas).
      - **Test (15%):** Ventanas históricas recientes `2023–2025` (`2.475` filas — evalúa generalización sobre campañas futuras nunca vistas en Train ni Val).
  - **Catálogo de Cultivos (11 cultivos oficiales de `CONTEXT.md`):**
    - *Invierno (`invierno`):* `trigo`, `cebada`, `vicia_cobertura`, `avena_cobertura`, `camelina` (ventanas extraídas en meses de otoño/invierno/primavera).
    - *Verano (`verano`):* `maiz_temprano`, `maiz_tardio`, `soja_primera`, `soja_segunda`, `girasol`, `sorgo` (ventanas extraídas en meses de primavera/verano/otoño temprano).
  - **Etiquetado del Target (`s_hidroclimatico`, 0 a 100):** Curvas ecofisiológicas **FAO GAEZ v4 / FAO-56** ($K_y$, umbrales óptimos/críticos y penalizaciones no lineales por golpe de calor + sequía, escorrentía por pendiente SRTM + tormentas GPM, anegamiento en suelos arcillosos planos, falsa recarga superficial y *flash drought*) + ruido gaussiano leve ($\sigma = 1.5$ pts).
- **Especificación Técnica:**
  1. Implementar en `backend/ml/generate_dataset.py` el descargador con caché (`fetch_or_load_nasa_telemetry`) que consulta **NASA POWER Daily API**, **OpenTopoData SRTM30m** e **ISRIC SoilGrids** para las 15 localidades agrícolas y guarda `backend/ml/data/nasa_raw_telemetry.json`.
  2. Implementar el extractor de ventanas reales de 90 días (`extract_real_90d_windows`) que calcula climatología histórica de 20 años por localidad/época del año, filtra `-999.0` y computa exactamente las features `1..8` de `CONTEXT.md`.
  3. Aplicar desacople espacial continuo en `pendiente_terreno_pct`, `elevacion_m` y `textura_arcilla_pct` + 15% de aumentación *What-If* dentro de cada bloque temporal (`2006–2019` Train, `2020–2022` Val, `2023–2025` Test).
  4. Etiquetar `s_hidroclimatico` con las curvas FAO GAEZ v4 / FAO-56 y exportar `train.csv` (11.550 filas), `val.csv` (2.475 filas), `test.csv` (2.475 filas) y `dataset_metadata.json`.
- **Definition of Done (Comando de Verificación):**
  - `backend\.venv\Scripts\python.exe backend/ml/generate_dataset.py`
