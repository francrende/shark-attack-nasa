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
| `ML-2` | Entrenamiento, Selección de Modelo (`HistGradientBoosting` vs `RandomForest`), Importancias por Permutación y Validación Agronómica | `backend/ml/train_baseline.py`, `backend/ml/modelo_agro.joblib`, `backend/ml/data/training_metrics.json` | `ML-1` | `[x]` |
| `ML-3` | Matriz de Rotación Agronómica, Salud del Suelo ($S_{\text{suelo}}$) y Cobertura 12 Meses (*Bare-Field Periods*) | `backend/services/rotation_matrix.py`, `backend/services/test_rotation_matrix.py` | — | `[x]` |

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

---

### `[x]` ML-2: Entrenamiento, Selección de Modelo (`HistGradientBoosting` vs `RandomForest`), Importancias por Permutación y Validación Agronómica
- **Objetivo:** Entrenar y evaluar el modelo regresor que predice el puntaje de aptitud hidroclimática y topográfica (`s_hidroclimatico`, de `0` a `100`) sobre los splits temporales `train.csv` (2006–2019), `val.csv` (2020–2022) y `test.csv` (2023–2025), seleccionando el mejor estimador y empaquetando el modelo junto con sus metadatos e importancias precalculadas en `backend/ml/modelo_agro.joblib`.
- **Archivos Permitidos:** `backend/ml/train_baseline.py`, `backend/ml/modelo_agro.joblib`, `backend/ml/data/training_metrics.json`, `backend/ml/TASKS_ML.md`
- **Decisiones Acordadas con el Desarrollador:**
  - **Estrategia de Modelado y Selección:**
    - Entrenar y comparar `HistGradientBoostingRegressor` (con soporte nativo de feature categórica para `cultivo_candidato` y regularización `l2_regularization` / `min_samples_leaf` para evitar sobreajuste) contra `RandomForestRegressor` evaluando sobre `val.csv` (`2020–2022`), y seleccionar el mejor según RMSE/MAE en validación.
  - **Estructura del Artefacto (`backend/ml/modelo_agro.joblib`):**
    - Serializar un diccionario/bundle autocontenido con:
      - `model`: estimador entrenado ganador (`scikit-learn`).
      - `model_name`: nombre del modelo ganador y sus hiperparámetros.
      - `feature_columns`: lista ordenada de las 12 features oficiales de `CONTEXT.md`.
      - `crops_catalog`: mapeo oficial `crop_name -> {id, campana}` e inverso `id -> crop_name`.
      - `feature_importances`: importancias globales y por cultivo precalculadas mediante `permutation_importance` sobre `val.csv`, más estadísticas de referencia (`feature_baselines`: media y desvío de cada feature en el dataset) para calcular sensibilidad local en `< 1 ms` durante la inferencia.
      - `metrics`: reporte completo de métricas en `train`, `val` y `test` (global y desglosado por los 11 cultivos).
    - Guardar además el reporte legible en `backend/ml/data/training_metrics.json`.
  - **Explicabilidad (`factores_clave_ml`):**
    - Precalcular `permutation_importance` en `val.csv` tanto a nivel global como condicionado por cada uno de los 11 cultivos, normalizando los pesos para que `predictor.py` pueda combinar importancia intrínseca del cultivo + desvío físico de la telemetría del lote sin costo computacional en producción.
  - **Sanity Checks Automáticos y Criterios de Aceptación (DoD):**
    - Verificar automáticamente al finalizar `train_baseline.py`:
      1. `R² > 0.85` y `MAE < 5.0` en el conjunto de **Test Out-of-Time (`2023–2025`)**.
      2. Control de generalización sin overfitting severo (diferencia acotada entre Train y Test).
      3. Latencia de inferencia para un lote (evaluando todos los cultivos de una campaña en batch) `< 15 ms`.
      4. Coherencia agronómica en el escenario benchmark de sequía de `CONTEXT.md` (`GWETROOT = 34%`, anomalía de lluvia `-24.2%`, pendiente `1.8%`): `sorgo` y `girasol` deben superar ampliamente a `soja_primera` y `maiz_temprano`, con predicciones acotadas en `[0.0, 100.0]`.
- **Especificación Técnica:**
  1. Implementar `backend/ml/train_baseline.py` cargando `train.csv`, `val.csv`, `test.csv` y `dataset_metadata.json`.
  2. Ejecutar búsqueda de hiperparámetros / comparación entre candidatos de `HistGradientBoostingRegressor` (`categorical_features=[11]`) y `RandomForestRegressor` usando `val.csv`.
  3. Evaluar el modelo ganador en `train.csv`, `val.csv` y `test.csv` (métricas globales `MAE`, `RMSE`, `R²`, `MaxError` y métricas por cultivo).
  4. Calcular `permutation_importance` global y por cultivo sobre `val.csv` y estadísticas base de features.
  5. Ejecutar la suite de *Sanity Checks* (umbrales en Test, latencia `< 15 ms` y benchmark de sequía de `CONTEXT.md`) y serializar `backend/ml/modelo_agro.joblib` y `backend/ml/data/training_metrics.json`.
- **Definition of Done (Comando de Verificación):**
  - `backend\.venv\Scripts\python.exe backend/ml/train_baseline.py`
- **Resultado de la Verificación (2026-11-14):**
  - Ganador: `hist_gradient_boosting_v3` (`learning_rate=0.03`, `max_leaf_nodes=31`, `min_samples_leaf=15`, `l2_regularization=0.5`). Random Forest quedó en Val RMSE ≈ 6.3 vs 3.24 del HGB.
  - Test Out-of-Time (2023–2025): `MAE = 2.22`, `RMSE = 3.30`, `R² = 0.9887` (gap R² Train–Test = `0.008`).
  - Latencia batch (6 cultivos de verano): `p50 = 8.4 ms`, `p95 = 10.8 ms`.
  - Benchmark de sequía de `CONTEXT.md`: `sorgo 91.9` · `girasol 86.9` · `maiz_tardio 80.4` · `soja_segunda 58.2` · `soja_primera 56.2` · `maiz_temprano 45.6` (margen `30.7` pts).
  - Nota para `predictor.py`: las predicciones crudas pueden salir por debajo de 0 (mín. `-28.8`), así que siempre hay que acotarlas a `[0, 100]`.

---

### `[x]` ML-3: Matriz de Rotación Agronómica, Salud del Suelo ($S_{\text{suelo}}$) y Cobertura 12 Meses
- **Objetivo:** Implementar el motor determinístico del Pilar 2 ($S_{\text{suelo}}$, 0–100) en `backend/services/rotation_matrix.py`, evaluando la transición `cultivo_anterior -> cultivo_candidato`, el balance de carbono orgánico (`soc` de SoilGrids), el riesgo erosivo por pendiente (`pendiente_terreno_pct` de SRTM), la textura (`arcilla_pct`), la cobertura mensual de 12 meses (*bare-field periods*) y la comparación de 3 estrategias de rotación para ser consumidos directamente por `ML-4` (`predictor.py`).
- **Archivos Permitidos:** `backend/services/rotation_matrix.py`, `backend/services/test_rotation_matrix.py`, `backend/ml/TASKS_ML.md`
- **Decisiones Acordadas con el Desarrollador:**
  - **Catálogo oficial y sincronización `0..10`:** Mismos 11 cultivos de `CONTEXT.md` y `ML-1`, exponiendo `numeric_id` (`0..10`) sincronizado 1:1 con `CROP_CATALOG` de `generate_dataset.py`.
  - **Monocultivo, barbecho y `soja_segunda`:** Penalización fuerte en monocultivo (`soja -> soja` 25 pts, `girasol -> girasol` 30 pts), penalización específica a `soja_segunda` si viene de cultivo de verano sin fina intermedia (52 pts vs. 88–89 pts en doble cultivo tras trigo/cebada), calibración exacta con el caso testigo de `CONTEXT.md` (`soja_primera -> sorgo` con `soc=18.4` y `pendiente=1.8%` $\rightarrow$ `s_suelo = 95.0`) y base neutra si `cultivo_anterior` es `None`/`"ninguno"`/`"barbecho"`.
  - **Umbrales SoilGrids (`soc`, `arcilla_pct`, `phh2o`) y SRTM (`pendiente_terreno_pct`):** `soc < 15.0 g/kg` bajo carbono; `pendiente >= 1.0%` moderada y `>= 2.0%` alta; ajuste por suelos arenosos (`< 16%` arcilla) o vertisoles pesados (`> 34%` arcilla); tolerancia total a valores `None`.
  - **Cobertura 12 meses y comparador de 3 estrategias:** `calendario_12m` distingue `cultivo_candidato`, `cultivo_antecesor`, `rastrojo_protector` y `suelo_desnudo`, y `compare_rotation_strategies(...)` contrasta la Estrategia Testigo (monocultivo), Defensiva Hídrica y Regenerativa de Suelo.
- **Especificación Técnica:**
  1. Definir `CROP_PROFILES` para los 11 cultivos con `numeric_id`, familia botánica, aporte de rastrojo, balance de carbono, fijación de N, cobertura inicial, meses activos/rastrojo, secuencia sugerida y perfil de mercado.
  2. Implementar `evaluate_soil_and_rotation(...)`, `evaluate_campaign_soil(...)` y `compare_rotation_strategies(...)`.
  3. Validar en `backend/services/test_rotation_matrix.py` sincronización 1:1 con `ML-1`, caso de referencia de `CONTEXT.md`, penalización de `soja_segunda` post-verano, ajustes de textura, calendario 12m y comparador de 3 estrategias.
- **Definition of Done (Comando de Verificación):**
  - `.\backend\.venv\Scripts\python.exe -m unittest backend/services/test_rotation_matrix.py -v`
