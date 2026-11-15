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
| `ML-1` | Generación del Dataset con Telemetría Histórica Real NASA POWER (20 años) + SRTM + SoilGrids, Esquema de Doble Ventana (`[-89d, t]` Hídrica / `[t+1, +90d]` Riesgos), Desacople Espacial y Split Temporal (70/15/15) | `backend/ml/generate_dataset.py`, `backend/ml/data/nasa_raw_telemetry.json`, `backend/ml/data/train.csv`, `backend/ml/data/val.csv`, `backend/ml/data/test.csv` | — | `[x]` |
| `ML-2` | Entrenamiento, Selección de Modelo (`HistGradientBoosting` vs `RandomForest`), Importancias por Permutación y Validación Agronómica | `backend/ml/train_baseline.py`, `backend/ml/modelo_agro.joblib`, `backend/ml/data/training_metrics.json` | `ML-1` | `[x]` |
| `ML-3` | Matriz de Rotación Agronómica, Salud del Suelo ($S_{\text{suelo}}$) y Cobertura 12 Meses (*Bare-Field Periods*) | `backend/services/rotation_matrix.py`, `backend/services/test_rotation_matrix.py` | — | `[x]` |
| `ML-4` | Motor de Inferencia Online (`predictor.py`), Fusión Multicriterio (MCDA), Detector de Anomalías y Explicabilidad | `backend/ml/predictor.py`, `backend/ml/test_predictor.py` | `ML-2`, `ML-3` | `[x]` |
| `ML-5` | Ensemble de años análogos para la ventana futura (`predict_ensemble`): promedio, P10/P90, años desfavorables y escalón de riesgo (Tarea C.1, coordinada con `BACK-6`) | `backend/ml/predictor.py`, `backend/ml/test_predictor.py`, `CONTEXT.md` | `ML-4`, `BACK-6` | `[x]` |
| `ML-6` | Dataset con rindes reales MAGyP (179 departamentos pampeanos, 2006/07–2024/25): label = rinde ajustado por abandono vs. tendencia, ventanas por calendario de siembra, `dias_hasta_siembra`, pesos 1/n, fórmulas únicas con el backend (Tareas C.2 y C.3) | `backend/ml/generate_dataset.py`, `backend/ml/magyp.py`, `backend/ml/calendario_siembra.py`, `backend/ml/fao_labels.py`, `backend/ml/test_dataset_magyp.py`, `backend/ml/data/*`, `backend/providers/features.py` | `ML-5`, `BACK-6` | `[x]` |
| `ML-7` | Reentrenamiento con el dataset MAGyP: validación agrupada por campaña, early stopping propio y métricas contra la tendencia y contra FAO | `backend/ml/train_baseline.py`, `backend/ml/escenarios.py`, `backend/ml/modelo_agro.joblib`, `backend/ml/predictor.py`, `backend/providers/enso.py`, `backend/providers/nasa_telemetry.py`, `backend/services/simulation_service.py`, `backend/schemas.py` | `ML-6` | `[x]` (2/3 criterios) |
| `ML-8` | Recalibración de umbrales de riesgo a la escala MAGyP (50 = año normal): cortes por puntaje esperado, escalón por P10, `umbral_desfavorable`, regla de suelo; cultivos fuera de ventana al final del ranking; `visualize_model.py` actualizado | `backend/ml/predictor.py`, `backend/ml/test_predictor.py`, `backend/ml/visualize_model.py`, `backend/routers/test_simulate.py`, `CONTEXT.md` | `ML-10` | `[x]` |
| `ML-9` | Extender el dataset a las campañas 1990/91–2024/25 (más años para aprender la relación clima–rinde y el contraste entre cultivos) | `backend/ml/generate_dataset.py`, `backend/ml/data/*` | `ML-7` | `[ ]` |
| `ML-10` | Cultivos sin rinde MAGyP fuera del modelo (puntaje relativo por `Ky` de FAO-56) y penalización por demanda hídrica con perfil seco | `backend/ml/train_baseline.py`, `backend/ml/predictor.py`, `backend/ml/test_predictor.py`, `backend/services/rotation_matrix.py`, `backend/services/test_rotation_matrix.py`, `backend/ml/modelo_agro.joblib`, `backend/ml/data/training_metrics.json`, `CONTEXT.md` | `ML-7` | `[x]` |
| `ML-11` | Lote ocupado por el antecesor de invierno: en verano, tras trigo, cebada o camelina, solo cultivos de segunda; campo `motivo_no_sembrable`; testigo trigo → soja de segunda | `backend/services/rotation_matrix.py`, `backend/ml/predictor.py`, `backend/schemas.py`, `backend/ml/test_predictor.py`, `backend/routers/test_simulate.py`, `CONTEXT.md` | `ML-8` | `[x]` |
| `ML-12` | Años análogos filtrados por fase ENSO (en lugar del peso gaussiano) y riesgo térmico de verano calculado con esos mismos años | `backend/providers/enso.py`, `backend/ml/escenarios.py`, `backend/ml/predictor.py`, `backend/services/simulation_service.py`, tests, `backend/ml/data/training_metrics.json`, `CONTEXT.md` | `ML-11` | `[x]` |
| `ML-13` | Años análogos desde 1981 (climatología y días de calor siguen en 2006–2025); `train_baseline --solo-evaluar` | `backend/providers/nasa_telemetry.py`, `backend/providers/generar_precache.py`, `backend/providers/data/climatologia_pampa.json`, `backend/ml/generate_dataset.py`, `backend/ml/train_baseline.py`, `backend/ml/data/*`, `backend/ml/modelo_agro.joblib`, tests, `CONTEXT.md` | `ML-12` | `[x]` |
| `ML-14` | Secuencias de rotación que respetan el invierno que ya pasó (antecesor o barbecho) y dejan la del perfil como "próximo ciclo" | `backend/services/rotation_matrix.py`, `backend/services/test_rotation_matrix.py`, `CONTEXT.md` | `ML-11` | `[x]` |

---

## 4. Especificación de Tareas Atómicas

### `[x]` ML-1: Generación del Dataset con Telemetría Histórica Real NASA POWER (20 años) + SRTM + SoilGrids, Esquema de Doble Ventana (`[-89d, t]` Hídrica / `[t+1, +90d]` Riesgos), Desacople Espacial y Split Temporal (70/15/15)
- **Objetivo:** Construir el dataset de entrenamiento (`train.csv`, 70%), validación (`val.csv`, 15%) y testeo (`test.csv`, 15%) libre de *Domain Shift* y de *Overfitting* (espacial y temporal), extrayendo pares de ventanas históricas reales sobre 20 años (2006–2025) de **NASA POWER API (`SMAP/GLDAS/IMERG`)**, topografía de **NASA SRTM (OpenTopoData)** y textura de **ISRIC SoilGrids** en localidades agrícolas reales, cacheadas localmente en `backend/ml/data/nasa_raw_telemetry.json`.
- **Archivos Permitidos:** `backend/ml/generate_dataset.py`, `backend/ml/data/nasa_raw_telemetry.json`, `backend/ml/data/train.csv`, `backend/ml/data/val.csv`, `backend/ml/data/test.csv`, `backend/ml/data/dataset_metadata.json`, `backend/ml/TASKS_ML.md`
- **Decisiones Acordadas con el Desarrollador:**
  - **Eliminación de *Domain Shift* y Esquema de Doble Ventana Temporal (`[-89d, t]` vs. `[t+1, +90d]`):**
    - Descargar series diarias reales de **20 años (`2006-01-01` a `2025-12-31`)** de `NASA POWER API` (`community=AG`, parámetros: `GWETROOT`, `GWETTOP`, `PRECTOTCORR`, `T2M_MAX`, `T2M_MIN`, `EVPTRNS`), filtrando valores faltantes (`-999.0`), junto con elevación/pendiente real de `OpenTopoData SRTM 30m` (y fallback a `geometry.coordinates[2]` de NASA POWER) y arcilla de `ISRIC SoilGrids` en **15 localidades representativas de la Región Pampeana y agrícola argentina** (Pergamino, Venado Tuerto, Marcos Juárez, Río Cuarto, Trenque Lauquen, Tandil, Balcarce, Tres Arroyos, Chascomús, Paraná, Rafaela, General Pico, Junín, Azul, Victoria).
    - Persistir la telemetría cruda descargada en `backend/ml/data/nasa_raw_telemetry.json` para que futuras ejecuciones de `generate_dataset.py` no requieran red si el caché ya existe.
    - Para cada fecha de decisión/evaluación $t$ (`idx`), separar explícitamente dos ventanas de 90 días (Opción A acordada con el desarrollador):
      1. **Ventana Pasada (`win_past = [t - 89, t]` — Estado Hídrico y Memoria del Suelo al momento de evaluar):**
         - `gwetroot_saturacion_pct`: estado del perfil radicular en el día $t$.
         - `gwettop_saturacion_pct`: humedad superficial (0–5 cm) en el día $t$.
         - `tendencia_humedad_15d_pct`: variación neta de humedad en los últimos 15 días (`[t - 14, t]`).
         - `anomalia_lluvia_90d_pct`: desvío porcentual de `PRECTOTCORR` acumulado en `[t - 89, t]` respecto a la climatología histórica de 20 años.
         - `indice_aridez_evaporativa`: cociente `PRECTOTCORR / EVPTRNS` acumulado en `[t - 89, t]`.
      2. **Ventana Futura (`win_future = [t + 1, t + 90]` — Riesgos Meteorológicos durante el Ciclo del Cultivo):**
         - `frecuencia_tormentas_extremas`: eventos con `PRECTOTCORR > 50 mm/día` en los 90 días posteriores a la decisión (`[t + 1, t + 90]`).
         - `frecuencia_estres_termico`: días con `T2M_MAX > 34°C` en los 90 días posteriores a la decisión (`[t + 1, t + 90]`).
         - `frecuencia_riesgo_helada`: días con `T2M_MIN < 2°C` en los 90 días posteriores a la decisión (`[t + 1, t + 90]`).
      3. **Asignación de Campaña (`season_campana`):** Clasificar la ventana según el centro del ciclo futuro del cultivo (`win_future.iloc[44]["month"]` en `4..9` $\rightarrow$ `"invierno"`, y `10..12` o `1..3` $\rightarrow$ `"verano"`), asegurando que un cultivo evaluado antes de su siembra reciba el estado hídrico previo (`win_past`) y la exposición térmica/pluviométrica de su campaña real (`win_future`).
  - **Eliminación de *Overfitting Espacial* (Desacople de Variables Estáticas):**
    - Como `elevacion_m`, `pendiente_terreno_pct` y `textura_arcilla_pct` son constantes para un punto `(lat, lon)`, al construir cada muestra a partir de una ventana climática real de una localidad, se aplica variabilidad continua intra-zona (*spatial jittering* realista sobre la distribución topográfica/edáfica local y cruce con perfiles de lotes vecinos) para que el árbol nunca pueda memorizar una coordenada fija por su altitud o arcilla exacta.
  - **Eliminación de *Data Leakage Temporal* (Split por Bloques Temporales 70 / 15 / 15 sin solapamiento de `win_future`):**
    - Las ventanas se particionan cronológicamente (*Out-of-Time Split*) garantizando que ni `win_past` ni `win_future` crucen las fronteras entre bloques (`2019 -> 2020` ni `2022 -> 2023`), asegurando proporción `70% Train / 15% Validation / 15% Test` estratificada por los 11 cultivos (`16.500` filas totales: `11.550` Train, `2.475` Val, `2.475` Test):
      - **Train (70%):** Ventanas históricas `2006–2019` (`11.550` filas).
      - **Validation (15%):** Ventanas históricas `2020–2022` (`2.475` filas).
      - **Test (15%):** Ventanas históricas recientes `2023–2025` (`2.475` filas).
  - **Catálogo de Cultivos (11 cultivos oficiales de `CONTEXT.md`):**
    - *Invierno (`invierno`):* `trigo`, `cebada`, `vicia_cobertura`, `avena_cobertura`, `camelina`.
    - *Verano (`verano`):* `maiz_temprano`, `maiz_tardio`, `soja_primera`, `soja_segunda`, `girasol`, `sorgo`.
  - **Etiquetado del Target (`s_hidroclimatico`, 0 a 100):** Curvas ecofisiológicas **FAO GAEZ v4 / FAO-56** ($K_y$, umbrales óptimos/críticos y penalizaciones no lineales por golpe de calor + sequía, escorrentía por pendiente SRTM + tormentas GPM, anegamiento en suelos arcillosos planos, falsa recarga superficial y *flash drought*) + ruido gaussiano leve ($\sigma = 1.5$ pts).
- **Especificación Técnica:**
  1. Implementar en `backend/ml/generate_dataset.py` el descargador con caché (`fetch_or_load_nasa_telemetry`) que consulta **NASA POWER Daily API**, **OpenTopoData SRTM30m** e **ISRIC SoilGrids** para las 15 localidades agrícolas y guarda `backend/ml/data/nasa_raw_telemetry.json`.
  2. Implementar el extractor de doble ventana de 90 días (`extract_real_90d_windows`) que calcula en `win_past = [t - 89, t]` las 5 features de estado hídrico del suelo (`gwetroot_saturacion_pct`, `gwettop_saturacion_pct`, `tendencia_humedad_15d_pct`, `anomalia_lluvia_90d_pct`, `indice_aridez_evaporativa`) y en `win_future = [t + 1, t + 90]` las 3 features de riesgo meteorológico del ciclo (`frecuencia_tormentas_extremas`, `frecuencia_estres_termico`, `frecuencia_riesgo_helada`).
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
- **Resultado de la Verificación (2026-11-14 — Esquema de Doble Ventana y Curvas Calibradas Argentina):**
  - Ganador: `hist_gradient_boosting_v3` (`learning_rate=0.03`, `max_leaf_nodes=31`, `min_samples_leaf=15`, `l2_regularization=0.5`). Random Forest quedó en Val RMSE ≈ 6.10 vs 3.15 del HGB.
  - Test Out-of-Time (2023–2025): `MAE = 1.95`, `RMSE = 2.92`, `R² = 0.9803` (gap R² Train–Test = `0.013`).
  - Importancias globales por permutación: `gwetroot_saturacion_pct (33.6%)` > `cultivo_candidato (27.1%)` > `frecuencia_estres_termico (14.7%)` > `anomalia_lluvia_90d_pct (9.3%)` > `frecuencia_riesgo_helada (8.8%)`.
  - Latencia batch (6 cultivos de verano): `p50 = 6.0 ms`, `p95 = 8.6 ms`.
  - Benchmark de sequía de `CONTEXT.md`: `sorgo 88.4` · `girasol 83.6` · `maiz_tardio 79.0` · `soja_primera 54.0` · `soja_segunda 53.1` · `maiz_temprano 47.7` (margen `29.6` pts).
  - Nota para `predictor.py`: las predicciones crudas pueden salir por debajo de 0 (mín. `-12.0`), así que siempre hay que acotarlas a `[0, 100]`.

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

---

### `[x]` ML-4: Motor de Inferencia Online (`predictor.py`), Fusión Multicriterio (MCDA), Detector de Anomalías y Explicabilidad
- **Objetivo:** Implementar en `backend/ml/predictor.py` el motor de recomendación híbrido (`AgroPredictor` / `RecommendationEngine`) que carga `modelo_agro.joblib` en memoria (Singleton, `< 15 ms`), aplica las transformaciones internas de simulación *What-If*, infiere $S_{\text{hidroclimatico}}$ (`0..100`), lo fusiona con $S_{\text{suelo}}$ de `rotation_matrix.py` según `objetivo_productor`, detecta anomalías físicas basadas en evidencia y construye la explicación agronómica y el contrato completo para `POST /api/v1/simulate`.
- **Archivos Permitidos:** `backend/ml/predictor.py`, `backend/ml/test_predictor.py`, `backend/ml/TASKS_ML.md`
- **Decisiones Acordadas con el Desarrollador:**
  1. **Simulación *What-If* (Controles independientes en UI + Consistencia interna para el modelo):**
     - `override_humedad_radicular_pct` y `variacion_lluvia_esperada_pct` son controles independientes en la UI, pero internamente `predictor.py` recalcula las variables físicas derivadas para que el árbol no reciba vectores contradictorios (ej. `variacion_lluvia_esperada_pct` ajusta `anomalia_lluvia_90d_pct`, reescala proporcionalmente `indice_aridez_evaporativa` y, si no se fijó override manual de humedad, acompaña la recarga/secado físico del perfil; `override_humedad_radicular_pct` actualiza `gwetroot_saturacion_pct` y acompaña suavemente `gwettop_saturacion_pct` y `tendencia_humedad_15d_pct` evitando falsas alarmas de desacople).
  2. **Fórmula del Score Final (Opción B — Lineal + Amortiguador por Factor Limitante Crítico):**
     - Base ponderada según `objetivo_productor` (`resiliencia_hidroclimatica`: `0.75/0.25`, `conservacion_suelo`: `0.30/0.70`, `equilibrio`: `0.50/0.50`) más penalización no lineal tipo *Ley del Mínimo de Liebig* (hasta `6–8 pts`) cuando alguno de los dos pilares cae en zona crítica (`< 35.0`, por monocultivo severo o colapso hídrico).
  3. **Clasificación Bidimensional del `riesgo` (`bajo` | `medio` | `alto` | `critico`):**
     - Basada en la combinación de $S_{\text{hidroclimatico}}$, $S_{\text{suelo}}$ y vulnerabilidad fisiológica al estrés activo: `"critico"` si $S_{\text{hidro}} < 50$ o `score_final < 30`; `"alto"` si $S_{\text{suelo}} < 35$ o $50 \le S_{\text{hidro}} < 62$ o `score_final < 55`; `"medio"` si $62 \le S_{\text{hidro}} < 84$ o $55 \le \text{score\_final} < 75$; `"bajo"` si $S_{\text{hidro}} \ge 84$ y $S_{\text{suelo}} \ge 55$.
  4. **Explicabilidad (`factores_clave_ml` en Top 3 bullets):**
     - Usar `feature_baselines["by_campana"][campana]` + importancias por permutación del cultivo (`per_crop`) + severidad física de anomalías activas en el lote fusionadas con los factores topográficos/edáficos de `rotation_matrix.py`.
  5. **Catálogo de 6 Anomalías Basadas en Evidencia (`anomalias_detectadas`):**
     - `deficit_hidrico_radicular`, `pulso_secado_rapido` (*Flash Drought*), `falsa_recarga_superficial`, `riesgo_escorrentia_erosion`, `exceso_hidrico_anegamiento` y `estres_termico_critico` / `riesgo_helada_tardia`, con `severidad` (`"baja" | "media" | "alta"`) y `evidencia` respaldada por NASA POWER, SRTM y SoilGrids.
  6. **Contrato de Salida Enriquecido:**
     - Devolver todos los campos exactos de la Sección 5 de `CONTEXT.md` (`anomalias_detectadas`, `recomendacion_principal`, `ranking_cultivos`, `validacion_local_requerida`, más clasificadores `riesgo_termico_verano`, `riesgo_erosion_escorrentia`, `condicion_rotacion_previa`) e incluir además `comparacion_estrategias` (con `score_final` híbrido) y `cobertura_12_meses`.
- **Especificación Técnica:**
  1. Implementar `AgroPredictor` con carga lazy/singleton de `backend/ml/modelo_agro.joblib` y configuración `n_jobs=1` para latencia `< 15 ms`.
  2. Implementar `apply_what_if_simulation(...)` para recalcular internamente las features afectadas sin romper la consistencia física del árbol.
  3. Implementar `detect_physical_anomalies(...)` con las 6 reglas basadas en evidencia.
  4. Implementar el motor MCDA (`predict_and_recommend(...)`) combinando $S_{\text{hidroclimatico}}$ clippeado a `[0, 100]` con `evaluate_campaign_soil(...)` y `compare_rotation_strategies(...)` de `rotation_matrix.py`, penalización por factor limitante `< 35`, clasificación bidimensional de `riesgo`, Top 3 `factores_clave_ml` y redacción dinámica de `explicacion`.
  5. Crear `backend/ml/test_predictor.py` validando el caso testigo de `CONTEXT.md`, escenarios *What-If* (Seco/Húmedo/Override), detección de las 6 anomalías, campañas de invierno y verano, objetivos del productor y latencia `< 15 ms`.
- **Definition of Done (Comando de Verificación):**
  - `.\backend\.venv\Scripts\python.exe -m unittest backend/ml/test_predictor.py -v`
- **Resultado de la Verificación (2026-11-14):**
  - 14/14 tests unitarios y de integración (`test_predictor.py` + `test_rotation_matrix.py`) en verde (`OK`).
  - Caso testigo de `CONTEXT.md` reproducido con ranking exacto (`sorgo` ganador con `s_suelo = 95.0`, `maiz_tardio` segundo, `soja_primera` última con `score_final = 31.0` tras penalización Opción B) y niveles de riesgo bidimensionales idénticos (`sorgo: bajo`, `maiz_tardio: medio`, `girasol: bajo`, `maiz_temprano: critico`, `soja_primera: alto`).
  - Latencia p95 del pipeline completo (inferencia ML + matriz agronómica + detector de anomalías + explicabilidad) `< 15 ms`.

---

### `[x]` ML-5: Ensemble de años análogos para la ventana futura (`predict_ensemble`)
- **Objetivo:** Dejar de resumir la ventana futura `[corte+1, corte+90]` en un único valor. El backend (`BACK-6`, `construir_insumos_ml`) entrega las 8 features actuales y la lista de **escenarios históricos por año** (los valores reales de `frecuencia_tormentas_extremas`, `frecuencia_estres_termico` y `frecuencia_riesgo_helada` de cada año 2006–2025 con la ventana completa, normalmente 19 o 20). El ML corre el modelo una vez por escenario y por cultivo de la campaña, y agrega los resultados en una **distribución** del score hidroclimático por cultivo: el promedio es el score principal, P10 representa un "año malo" y P90 un "año bueno".
- **Por qué:** en entrenamiento el modelo aprende con el futuro **observado** de cada ventana. En producción el futuro no se conoce. Pasarle un promedio climatológico le daría valores suavizados que nunca vio. Pasarle los futuros que realmente ocurrieron en esa coordenada y en esas fechas mantiene la misma distribución que en entrenamiento, y además cuantifica el riesgo sin inventar pronósticos (CONTEXT.md §4.4).
- **Archivos Permitidos:** `backend/ml/predictor.py`, `backend/ml/test_predictor.py`, `backend/ml/TASKS_ML.md`, `CONTEXT.md` (§4.1, §4.3, §4.6 y §5).
- **Independiente del label:** funciona con el modelo actual (label FAO) y con el reentrenamiento con rindes MAGyP, sin cambiar la interfaz. Solo cambia el valor por defecto del umbral (ver abajo).
- **Decisiones Acordadas con el Desarrollador:**
  1. **Umbral de "año desfavorable":** parámetro `umbral_desfavorable` configurable, con valor por defecto `50.0`, que coincide con el corte `critico` de `classify_crop_risk`. Se recalibra al reentrenar con MAGyP, donde 50 = año normal, sin cambiar el contrato.
  2. **Agregados por cultivo:** promedio (score principal), P10, P90, cantidad de años desfavorables (`score < umbral`), cantidad de años evaluados y el **peor escenario** (año análogo, score y sus 3 features futuras), para que la explicación pueda citarlo.
  3. **Riesgo:** se clasifica con el promedio, como hoy (`classify_crop_risk`), y **se sube un nivel** (`bajo → medio → alto → critico`) si el P10 cae en la zona crítica (`P10 < 50.0`, el mismo corte `critico` de S_hidro). Así, un cultivo con buen promedio pero años muy malos no queda como `bajo`.
  4. **Ponderación de años:** todos pesan lo mismo. La función acepta `pesos` opcionales para sumar más adelante la ponderación por fase ENSO sin cambiar el contrato (tarea futura).
- **Decisiones por defecto del agente (corregir si no aplican):**
  - **Interfaz:**
    - `AgroPredictor.predict_ensemble(features_actuales, escenarios_historicos, campana, *, pesos=None, umbral_desfavorable=50.0, simulacion_what_if=None) -> dict[cultivo, dict]`.
    - `features_actuales`: las 8 features de `FEATURES_ACTUALES` de `backend/providers/features.py`, ya con topes.
    - `escenarios_historicos`: lista de `{anio, frecuencia_tormentas_extremas, frecuencia_estres_termico, frecuencia_riesgo_helada}`, el formato exacto de `InsumosML.escenarios_historicos`.
    - Parámetros que se sumen más adelante, como `fecha_corte` y `lat` para `dias_hasta_siembra` con el reentrenamiento MAGyP, van **solo por nombre y opcionales**, para no romper a quien ya la llame.
  - **Cálculo:** se arma una matriz de `N_escenarios × N_cultivos` filas y se predice en **un único batch** (unas 114 filas en verano), igual que `predict_hydroclimatic_batch`. Cada predicción se acota a `[0, 100]` antes de agregar.
  - **Percentiles:** sin pesos, `numpy.percentile` (método `linear`). Con pesos, percentil ponderado. Todo redondeado a 1 decimal.
  - **What-If dentro del ensemble:** si viene `simulacion_what_if`, se aplica `apply_what_if_simulation` al vector completo de **cada escenario**, porque la variación de lluvia también ajusta las tormentas. Así el What-If modifica el presente y el futuro sigue siendo incierto. Pasar un solo escenario, como decidió `BACK-6` para el What-If, sigue funcionando: es una lista de un elemento.
  - **Validaciones:** se lanza `ValueError` si la lista de escenarios está vacía, si a un escenario le falta alguna de las 3 features futuras, si a `features_actuales` le falta alguna de las 8, o si los `pesos` no tienen el largo correcto o suman 0. El ML no vuelve a aplicar topes, porque los aplica el backend.
  - **Integración en `predict_and_recommend` / `run_recommendation`:** nuevo parámetro opcional `escenarios_historicos`.
    - **Si viene:** `features` aporta las 8 actuales, `S_hidro` de cada cultivo es el **promedio** del ensemble y alimenta la fusión MCDA, el ranking y las estrategias como hoy. El riesgo aplica el escalón por P10.
    - **Si no viene:** comportamiento actual con un único vector de 12 features, sin cambios, por compatibilidad con los tests, el What-If de un escenario y los llamadores existentes.
    - **Escenario representativo** (para `detect_physical_anomalies`, `build_key_ml_factors`, `riesgo_termico_verano` y `riesgo_erosion_escorrentia`): la **mediana por feature** de los escenarios, redondeada a entero.
  - **Contrato §5 (campos nuevos, sin quitar ni renombrar ninguno):**
    - `recomendacion_principal.distribucion_hidroclimatica`: `{promedio, p10, p90, anios_desfavorables, anios_evaluados, umbral_desfavorable, peor_escenario: {anio, score, frecuencia_tormentas_extremas, frecuencia_estres_termico, frecuencia_riesgo_helada}}`.
    - En cada elemento de `ranking_cultivos`: `score_hidroclimatico_p10`, `anios_desfavorables` y `anios_evaluados`.
    - Sin `escenarios_historicos`, esos campos **no se incluyen**, así el contrato actual queda idéntico.
  - **Explicación:** si hay ensemble, `explicacion` agrega una oración con el riesgo del ganador, por ejemplo: *"En 3 de 19 años análogos el puntaje hidroclimático quedó por debajo de 50; el peor escenario (calor como en 2008) lo lleva a 24."*
- **Especificación Técnica:**
  1. En `backend/ml/predictor.py`:
     - Constantes `FUTURE_FEATURES` y `CURRENT_FEATURES`, alineadas con `FEATURES_FUTURAS` y `FEATURES_ACTUALES` de `providers/features.py`. Un test verifica la paridad.
     - Helper de percentil ponderado y helper `escalate_risk_level(riesgo, p10)`.
     - Método `AgroPredictor.predict_ensemble(...)` según la interfaz de arriba.
  2. Integrar el ensemble en `predict_and_recommend(...)` y `run_recommendation(...)` mediante el parámetro opcional `escenarios_historicos`, con los campos nuevos del contrato y la oración de riesgo en `explicacion`.
  3. Actualizar `CONTEXT.md`:
     - §4.1 y §4.3 B: la ventana futura en producción es un ensemble de años análogos, no la climatología promedio.
     - §4.6: paso 3 del flujo online.
     - §5: campos nuevos en el ejemplo de respuesta.
  4. Tests en `backend/ml/test_predictor.py`:
     - Con 1 escenario, el ensemble coincide con `predict_hydroclimatic_batch`.
     - El promedio, P10 y P90 coinciden con `numpy` sobre las predicciones individuales.
     - El conteo de años desfavorables respeta `umbral_desfavorable`.
     - El peor escenario es el de menor score.
     - El escalón de riesgo se aplica solo cuando `P10 < 50`.
     - Pesos uniformes dan el mismo resultado que sin pesos.
     - Las validaciones lanzan `ValueError`.
     - `predict_and_recommend` sin escenarios devuelve exactamente el contrato actual, y con escenarios agrega los campos nuevos.
     - Paridad de nombres de features con `providers/features.py`.
     - Latencia del ensemble (6 cultivos × 20 escenarios) con p95 `< 15 ms`.
- **Definition of Done (Comando de Verificación):**
  - `cd backend && .venv\Scripts\python.exe -m pytest -q ml/test_predictor.py services/test_rotation_matrix.py providers/test_features.py`
- **Resultado de la Verificación (2026-11-14):**
  - DoD: `48 passed`. La suite completa del backend (`cd backend && pytest -q`) da `181 passed`. El comando de ML-4 (`python -m unittest backend/ml/test_predictor.py`) da `19 tests OK`: los 7 de ML-4 pasan sin cambios.
  - Sin `escenarios_historicos`, la respuesta es idéntica al contrato de ML-4, con las mismas claves y en el mismo orden (test 08).
  - Ejemplo (caso testigo de sequía + 19 escenarios con calor de 1 a 45 días, como Pergamino al 11/11/2026): `sorgo` gana con promedio `74.1`, P10 `49.7`, P90 `88.3` y `3/19` años desfavorables. El peor escenario es de 45 días de calor (score `45.5`). `maiz_temprano` tiene `17/19` años desfavorables y P10 `0.0`.
  - **Observación para ML-8:** con el modelo FAO actual, los años de mucho calor bajan fuerte el score. Con el escalón por P10 < 50, en ese ejemplo **todos** los cultivos de verano quedan en `alto` o `critico`, incluido el ganador (`sorgo`, que por promedio sería `medio`). No es un error: refleja la fórmula FAO frente a veranos de 30 a 45 días de calor. Hay que revisar el corte del escalón y `umbral_desfavorable` cuando se reentrene con MAGyP.

---

### `[x]` ML-6: Dataset con rindes reales MAGyP
- **Objetivo:** Reemplazar el label `s_hidroclimatico`, que hoy calcula la fórmula FAO (el modelo solo la imitaba), por el **rinde real de MAGyP por departamento y campaña**. Usar las mismas fórmulas de features que producción (`providers/features.py`, Tarea C.2) y el mismo suelo y la misma topografía (arcilla 0–30 cm y pendiente Horn 3×3, Tarea C.3).
- **Archivos Permitidos:**
  - `backend/ml/generate_dataset.py` (reescrito).
  - `backend/ml/magyp.py`, `backend/ml/calendario_siembra.py` y `backend/ml/fao_labels.py` (nuevos; `fao_labels.py` recibe `CROP_CATALOG` y `compute_fao_hydroclimatic_score`, que se siguen re-exportando desde `generate_dataset.py`).
  - `backend/ml/test_dataset_magyp.py` (nuevo).
  - `backend/ml/data/*`.
  - `backend/providers/features.py`: refactor sin cambio de comportamiento, para exponer el cálculo puro de las features actuales.
  - `.gitignore`.
- **Decisiones Acordadas con el Desarrollador:**
  - **Alcance:** región pampeana (Buenos Aires, Córdoba, Santa Fe, Entre Ríos y La Pampa), campañas 2006/07–2024/25.
  - **Fuente del label:** CSV consolidado `estimaciones-agricolas` de datos.magyp.gob.ar.
  - **Cultivos:**
    - `trigo` ← trigo total.
    - `cebada` ← cebada total desde 2016/17 y **cebada cervecera hasta 2015/16**.
    - `maiz_temprano` y `maiz_tardio` ← maíz: el mismo rinde, cada uno con su fecha de siembra.
    - `soja_primera` ← soja 1ra; `soja_segunda` ← soja 2da.
    - `girasol` y `sorgo`.
  - **Rinde ajustado por abandono:** `rinde_aj = rendimiento × min(1, fc / fc_típica)`.
    - `fc` es la superficie cosechada sobre la sembrada de esa campaña.
    - `fc_típica` es la mediana de `fc` del departamento y cultivo en los años de entrenamiento.
    - Así el silo y el pastoreo habituales (22% del maíz y 26% del sorgo no se cosechan para grano) no penalizan, pero el abandono extra de una sequía sí.
  - **Puntaje:** `50 + 100 × (rinde_aj / tendencia − 1)`, recortado a [0, 100]. 50 es un año normal y 30 es un rinde 20% debajo de la tendencia.
  - **Calendario de siembra único** para la región pampeana (inicio–fin):
    - Verano: `maiz_temprano` 15/09–31/10, `maiz_tardio` 01/12–10/01, `soja_primera` 25/10–10/12, `soja_segunda` 10/12–15/01, `girasol` 15/09–15/11, `sorgo` 01/11–20/12.
    - Invierno: `trigo` 20/05–31/07, `cebada` 01/06–20/07, `camelina` 15/05–30/06, `vicia_cobertura` 01/03–30/04, `avena_cobertura` 15/02–30/04.
  - **Filas:** se mantienen las ventanas de 10 días.
    - Cada ventana de una campaña lleva el mismo label MAGyP, con `sample_weight = 1/n_ventanas` de ese departamento, campaña y cultivo.
    - Las ventanas van desde la habilitación de la campaña (regla §4.1: mes de t + 45 días) hasta el fin de siembra del cultivo.
  - **Feature nueva `dias_hasta_siembra`** = inicio de siembra − t, en días. Es negativa dentro de la ventana de siembra. Con ella el modelo pasa a tener 13 features.
  - **Ventana futura:** en el entrenamiento se usa la observada en ese año. En producción se usa el ensemble de años análogos (ML-5).
  - **Split por campaña:**
    - train: 2006/07–2018/19
    - val: 2019/20–2021/22
    - test: 2022/23–2024/25
  - **Híbrido FAO, solo en train:**
    - Cultivos de cobertura sin dato MAGyP (`vicia_cobertura`, `avena_cobertura`, `camelina`): peso 0,5.
    - Filas What-If extremas: peso 0,25.
- **Decisiones por defecto del agente (corregir si no aplican):**
  - **Punto por departamento:** el centroide de georef (apis.datos.gob.ar), deduplicando las celdas de NASA POWER que se comparten.
    - Suelo y topografía salen de los providers del backend (`fetch_perfil_suelo`, `fetch_topografia`) en el centroide. Ya implementan C.3 (arcilla 0–30 cm ponderada y Horn 3×3 a 300 m).
    - **Sin ruido artificial**: no hay jitter de pendiente, arcilla ni elevación, porque ahora la variación espacial es real.
  - **Features idénticas a producción:**
    - Las actuales salen de una función pura extraída de `construir_insumos_ml`, que recibe la serie de los 100 días previos al corte, la climatología 2006–2025 y los datos estáticos.
    - Las futuras salen de `escenarios_ventana_futura(calendario, t)`, tomando el escenario del año de t.
    - Los topes son los de `aplicar_topes`.
  - **Tendencia:** Theil–Sen (mediana de pendientes, robusta a años de sequía) sobre los años de entrenamiento de cada departamento y cultivo. La tendencia tiene un piso del 30% de la mediana.
  - **Filtros:**
    - Superficie sembrada ≥ 1.000 ha.
    - ≥ 8 campañas de entrenamiento con dato por departamento y cultivo (si no, se descarta).
  - **Escala FAO → MAGyP:** las filas FAO usan un mapeo por cuantiles por campaña, ajustado con las filas MAGyP de train, para que 50 signifique lo mismo en ambas fuentes.
  - **Filas What-If con label delta:** `label = label_MAGyP + (FAO_mapeado(perturbada) − FAO_mapeado(original))`. El nivel real se conserva y FAO solo aporta la dirección de la sensibilidad. Son el 15% de las filas reales de train, con las perturbaciones de ML-1.
  - **Archivos de salida:**
    - Commiteados: `data/magyp_pampa.csv` (filtrado), `data/departamentos_pampa.json` (centroide, suelo y topografía), `data/dataset_magyp_{train,val,test}.csv.gz` y `data/dataset_magyp_metadata.json`, además de `data/dataset_magyp_escenarios.csv.gz`: los años análogos (sin el año evaluado) de cada departamento y fecha t de val y test, para la evaluación de ML-7.
    - Sin commitear (`.gitignore`): el CSV crudo de MAGyP y la caché de NASA por celda (`data/cache/`).
    - Los CSV del modelo FAO actual quedan hasta ML-7, que los reemplaza al reentrenar.
  - **Sin modelo nuevo en ML-6:** el predictor y el backend no cambian; `dias_hasta_siembra` se cablea en ML-7.
- **Especificación Técnica:**
  1. `calendario_siembra.py`: `CALENDARIO`, `campana_de(t)`, `inicio_siembra(cultivo, anio_campana)`, `dias_hasta_siembra(cultivo, t)` y `fechas_ventana(campana, anio_campana)`.
  2. `magyp.py`: descarga y filtrado, mapeo de cultivos, `rinde_ajustado`, `tendencia_theil_sen` y `puntaje_vs_tendencia`.
  3. `providers/features.py`: `features_actuales_desde_series(...)` (puro), usado por `construir_insumos_ml` sin cambiar su salida.
  4. `generate_dataset.py`: centroides → estáticos por departamento → NASA por celda (secuencial, reanudable) → filas → split → archivos + metadata.
  5. Tests:
     - Calendario: campaña, `dias_hasta_siembra` y cruce de año.
     - MAGyP: ajuste por abandono, Theil–Sen contra un caso conocido, puntaje, cebada cervecera/total y filtros.
     - Paridad: una fila del dataset coincide con `construir_insumos_ml` para la misma celda y el mismo corte.
     - Pesos: la suma por departamento, campaña y cultivo es 1.
- **Definition of Done (Comando de Verificación):**
  - `cd backend && .venv\Scripts\python.exe -m pytest -q`: todos en verde.
  - `cd backend && .venv\Scripts\python.exe -m ml.generate_dataset`: genera los archivos.
  - La metadata muestra filas por split y por fuente, y la distribución del label.
  - **Sanidad:** las campañas de sequía 2008/09 y 2022/23 dan puntaje medio de maíz y soja < 40.

- **Cambios durante la implementación (acordados con el desarrollador):**
  - **Tendencia del label:** se ajusta con **todo el período 2006–2024** y no solo con train. Con train solamente, la tendencia proyectaba rindes más altos que los reales de 2019–2024 y corría la escala del label entre los splits (MAE 25 en lugar de 17). La tendencia solo usa rindes, nunca clima.
  - **Features futuras en el período crítico de cada cultivo** (ver ML-7), con lluvia acumulada y ONI. Antes eran los 90 días posteriores a t.
  - **Calendario de lluvia diaria en el backend** (`telemetria-v3`): se regeneró el precálculo de las 299 celdas.
  - **`dataset_magyp_escenarios.csv.gz`:** features críticas por departamento × cultivo × año. ML-7 las usa para evaluar con años análogos.
  - **Chascomús:** georef usa el código nuevo `06218` y MAGyP el viejo `06217`; se mapean.
  - **Generador offline:** usa un timeout de 90 s para SoilGrids, porque ISRIC llegó a tardar 30 s por consulta. Hace hasta 4 consultas en vuelo para respetar el límite de 5/min y reintenta más allá del corte automático. Producción no cambia.
- **Resultado de la Verificación (2026-11-15):**
  - **Departamentos:** 169 de 170.
    - Suelo: 166 con dato de SoilGrids, 1 de un píxel vecino y 2 con el valor regional.
    - Topografía: 169 con SRTM.
    - A un departamento le falta el dato estático; se reintenta en la próxima corrida.
  - **Filas:**
    - train: 176587 reales, 65910 de cobertura FAO y 26488 What-If con label delta
    - val: 42135
    - test: 42034
  - **Sanidad:** puntaje medio de maíz y soja en las sequías: {'2008/2009': 11.0, '2017/2018': 30.6, '2022/2023': 17.4} (las tres < 40 ✅).
  - **Tests:** `cd backend && pytest -q` da 234 en verde.

---

### `[x]` ML-7: Reentrenamiento con el dataset MAGyP (aceptación parcial: 2 de 3 criterios)
- **Objetivo:** Entrenar `modelo_agro.joblib` sobre el dataset de ML-6 (13 features, label = rinde real vs. tendencia) y medirlo de forma honesta, igual que funciona en producción. Además, conectar `dias_hasta_siembra` en el predictor y el backend.
- **Archivos Permitidos:**
  - `backend/ml/train_baseline.py` (reescrito).
  - `backend/ml/modelo_agro.joblib`.
  - `backend/ml/data/training_metrics.json`.
  - `backend/ml/predictor.py` y `backend/ml/test_predictor.py`.
  - `backend/ml/visualize_model.py`.
  - `backend/services/simulation_service.py` (pasa `fecha_corte`), `backend/schemas.py` (flag `fuera_de_ventana_siembra`), `backend/routers/test_simulate.py` y `CONTEXT.md` (§4.2, §4.3, §5).
- **Decisiones Acordadas con el Desarrollador:**
  - **Evaluación igual que producción:**
    - En val y test, cada fila se predice con el **ensemble de años análogos** (`escenarios_ventana_futura` de la celda, **sin el año evaluado**), promediado como en `predict_ensemble`. Esa métrica decide.
    - También se informa la métrica con el futuro observado, como techo teórico.
  - **Criterio de aceptación en test:** el MAE ponderado (`sample_weight`, solo filas `magyp_real`) tiene que ser **≥ 10% menor** que el de las dos líneas base, en el mismo régimen de ensemble:
    1. **Año normal:** la media ponderada de train por cultivo.
    2. **FAO mapeado:** `compute_fao_hydroclimatic_score` llevado a la escala MAGyP con el mapeo por cuantiles de ML-6.
  - **Monotonía agronómica:** HistGradientBoosting con `monotonic_cst = −1` en `frecuencia_estres_termico` y `frecuencia_riesgo_helada` (el puntaje no sube con más calor ni con más heladas). El resto de las features queda libre, porque el exceso de agua también daña.
  - **Chequeo de sequía de ML-2 (CONTEXT §5): informativo.** Se calcula y se informa, pero no bloquea.
- **Decisiones por defecto del agente (corregir si no aplican):**
  - **Features:** las 13 de ML-6. `cultivo_candidato` es categórica. **Sin** `departamento_id`, lat ni lon, para que el modelo no memorice lugares y sirva para cualquier lote.
  - **Entrenamiento:** `fit(..., sample_weight=...)`.
    - Early stopping **propio**: se entrena con un `max_iter` alto, se elige la iteración con `staged_predict` según el MAE de val en régimen ensemble, y se reentrena con esa cantidad de iteraciones.
    - Nada de `validation_fraction` aleatorio: mezclaría ventanas de la misma campaña entre train y val.
  - **Búsqueda chica de hiperparámetros** (4 a 6 combinaciones de `learning_rate`, `max_leaf_nodes`, `min_samples_leaf` y `l2_regularization`) elegida por el MAE de val en ensemble. Se descarta RandomForest, porque no admite restricciones de monotonía en sklearn.
  - **Modelo final:** se reentrena con train + val usando los hiperparámetros y la cantidad de iteraciones elegidos. Test queda solo para informar.
  - **Métricas informadas** (val y test, ensemble y observado):
    - MAE, RMSE y R² ponderados.
    - MAE por cultivo.
    - Spearman entre cultivos por departamento y campaña (calidad del ranking).
    - Recall de años malos (label < 35).
  - **Predictor:**
    - `predict_ensemble`, `predict_and_recommend` y `run_recommendation` reciben `fecha_corte` (keyword).
    - `dias_hasta_siembra` se calcula por cultivo con `ml/calendario_siembra.py`. Si no viene `fecha_corte`, se usa la fecha UTC de hoy.
    - Los cultivos con la siembra ya terminada no se sacan del ranking: llevan `fuera_de_ventana_siembra: true`.
  - **Backend:** `simulation_service` pasa `fecha_corte = insumos.fecha_corte`. `ItemRanking` gana `fuera_de_ventana_siembra: bool = false`.
  - **Tests que fijaban valores de la fórmula FAO:** se pasan a chequeos estructurales y direccionales (por ejemplo, que la sequía baje el puntaje). Los umbrales de riesgo se recalibran en ML-8.
  - **Bundle:**
    - Se mantienen las claves actuales (`model`, `feature_columns`, `crops_catalog`, `feature_importances`, `feature_baselines`).
    - Se suma `model_version = "ml7-magyp"` y el resumen de métricas.
- **Especificación Técnica:**
  1. `train_baseline.py`: carga de `dataset_magyp_*.csv.gz` y de los escenarios de val/test → búsqueda con early stopping propio → refit con train + val → métricas y líneas base → importancias por permutación sobre test → bundle.
  2. `predictor.py`: 13 features, `fecha_corte` y `fuera_de_ventana_siembra`.
  3. `simulation_service.py` y `schemas.py`: pasar `fecha_corte` y agregar el flag.
  4. Tests: el predictor con el modelo nuevo (estructura, monotonía y latencia), el flag de siembra y el endpoint.
- **Definition of Done (Comando de Verificación):**
  - `cd backend && .venv\Scripts\python.exe -m ml.train_baseline`: imprime las métricas y el criterio de aceptación da `passed`.
  - `cd backend && .venv\Scripts\python.exe -m pytest -q`: todos en verde.
  - Latencia p95 del ensemble (6 cultivos × 20 escenarios) `< 15 ms`.

- **Cambios durante la implementación (acordados con el desarrollador):**
  - **Diagnóstico:** con los 90 días posteriores a t, el modelo no le ganaba a "año normal" **ni siquiera con el clima observado**. El rinde se define en el período crítico (floración y llenado), que esa ventana no cubría.
  - **Período crítico + ENSO:**
    - Las features futuras se miden en la ventana crítica de cada cultivo (`calendario_siembra.OFFSET_PERIODO_CRITICO`), más la lluvia acumulada.
    - El ONI publicado al decidir es una feature, y además pondera los años análogos (`providers/enso.py`, `ml/escenarios.py`).
  - **Selección por validación cruzada dejando una campaña afuera** (16 campañas) en lugar del early stopping por val. Val (2019–2021) son 3 campañas sin sequías fuertes: cortaba a 1–7 iteraciones, mientras test mejoraba hasta las 100–200.
  - **Criterio de aceptación nuevo:** el 10% en producción no es alcanzable antes de sembrar. Quedan tres criterios:
    - producción contra "año normal": ≥ 5%
    - producción contra FAO: ≥ 10%
    - What-If contra "año normal": ≥ 15%
  - **`MAX_ITER` subió a 1500**, porque la validación cruzada con 500 quedaba en el tope. Se usa la cantidad de iteraciones que elige la validación cruzada, **no** la que mejor rinde en test.
- **Resultado de la Verificación (2026-11-15):**
  - **Modelo:** `{'learning_rate': 0.03, 'max_leaf_nodes': 7, 'min_samples_leaf': 1500, 'l2_regularization': 20.0, 'max_iter': 827, 'monotonic_cst': [0, 0, 0, 0, 0, 0, 0, 0, 0, -1, -1, 0, 0, 0, 0]}`.
  - **Validación cruzada:** MAE 17.755, contra 18.918 de "año normal".
  - **Test 2022–2024:**

    | Régimen | MAE | R² | AUC años malos |
    | :--- | :---: | :---: | :---: |
    | Producción, años análogos ponderados por ONI | 17.74 | 0.043 | 0.76 |
    | Producción, años análogos uniformes | 17.80 | 0.025 | 0.74 |
    | What-If, clima observado | 14.76 | 0.315 | 0.80 |
    | Línea base "año normal" | 18.35 | -0.115 | 0.52 |
    | Línea base FAO mapeado | 23.47 | -0.557 | 0.64 |

  - **Aceptación:**
    - producción contra "año normal": 3.3% ❌ (mínimo 5%)
    - producción contra FAO: 24.4% ✅
    - What-If: 19.6% ✅
  - **Por campaña** (puntaje real / predicho en producción): {a: (v['real'], m['test_produccion_oni']['por_anio'][a]['predicho']) for a, v in m['test_produccion_oni']['por_anio'].items()}. En la sequía de 2022/23 el modelo anticipa la dirección, pero no la magnitud.
  - **Importancias:** lluvia del período crítico 0,33, calor del período crítico 0,23, ONI 0,19, cultivo 0,12, humedad radicular 0,06.
  - **Chequeos:**
    - Monotonía: OK.
    - Latencia p95 del ensemble 6×20: 5.228 ms.
    - Benchmark de sequía de CONTEXT §5 (informativo): no se cumple, con margen 3.15.
  - **Debilidad para ML-8 y ML-9:** el ranking **entre cultivos** del mismo año es débil (Spearman ~0,04–0,10). En una sequía extrema todos los cultivos dan bajo y decide el pilar suelo. Causas: `maiz_temprano` y `maiz_tardio` comparten el label "maíz", y 16 campañas no alcanzan para aprender cómo afecta el clima a cada cultivo.
  - **Tests:** los que fijaban valores de la fórmula FAO pasaron a chequeos estructurales y direccionales. `cd backend && pytest -q` da 234 en verde; `python -m unittest backend/ml/test_predictor.py` da OK.
  - **Pendiente:** `ml/visualize_model.py` todavía lee el `test.csv` del modelo FAO (borrado). Resuelto en ML-8.

---

### `[x]` ML-10: Cultivos sin rinde MAGyP fuera del modelo y penalización por demanda hídrica
- **Objetivo:** Que el ranking respete el estado del agua del lote también en invierno. Con ML-7, en sequía el trigo quedaba primero en el pilar hidroclimático porque las coberturas caían a 6–8 puntos. Ese desplome venía de su label (fórmula FAO mapeada), no de datos reales.
- **Archivos Permitidos:** `backend/ml/train_baseline.py`, `backend/ml/predictor.py`, `backend/ml/test_predictor.py`, `backend/services/rotation_matrix.py`, `backend/services/test_rotation_matrix.py`, `backend/ml/modelo_agro.joblib`, `backend/ml/data/training_metrics.json`, `backend/ml/TASKS_ML.md`, `CONTEXT.md`.
- **Decisiones (propuestas por el agente y aprobadas por el desarrollador el 2026-11-15; los valores numéricos los eligió el agente y quedan abiertos a revisión):**
  - **Coberturas fuera del entrenamiento:** `train_baseline.py` descarta las filas `fao_cobertura`. El dataset no se regenera. El bundle suma `cultivos_entrenados` (los 8 con rinde MAGyP).
  - **Puntaje relativo:** para `vicia_cobertura`, `avena_cobertura` y `camelina`, `S = 50 + (Ky_cultivo / Ky_referencia) × (S_referencia − 50)`. La referencia es el promedio de los cultivos entrenados de la misma campaña (trigo y cebada), año análogo por año análogo. `Ky` sale de `ky_drought` en `ml/fao_labels.py`.
  - **Penalización por demanda hídrica:** `penalizacion_demanda_hidrica(cultivo, gwetroot)` en `rotation_matrix.py`. Resta hasta 10 puntos a `S_hidroclimatico`: severidad lineal entre 45% y 25% de agua en las raíces, por demanda relativa entre 200 y 550 mm (`CONSUMO_AGUA_CICLO_MM`). Se aplica a todos los cultivos, en `predict_hydroclimatic_batch` y en `predict_ensemble` (con el `GWETROOT` del What-If si hay override).
  - **Explicación:** si la mayor penalización es de 2 puntos o más, `explicacion` agrega una oración que lo dice.
  - **Contrato:** sin cambios en `schemas.py` ni en el JSON de §5.
  - **Las filas What-If (fórmula FAO) siguen en el entrenamiento.** Medir si conviene sacarlas queda en la hoja de ruta (CONTEXT §4.7).
- **Definition of Done (Comando de Verificación):**
  - `cd backend && .venv\Scripts\python.exe -m ml.train_baseline` (con `PYTHONIOENCODING=utf-8` si se redirige la salida).
  - `cd backend && .venv\Scripts\python.exe -m pytest -q`.
- **Resultado de la Verificación (2026-11-15):**
  - **Reentrenamiento (solo cultivos con rinde MAGyP):** el mismo modelo gana la validación cruzada (`hgb_v1`, 708 iteraciones). MAE de validación cruzada 17.794, contra 17.755 en ML-7 y 18.918 de "año normal".
  - **Test 2022–2024:**

    | Régimen | MAE ML-10 | MAE ML-7 | AUC años malos |
    | :--- | :---: | :---: | :---: |
    | Producción, años análogos ponderados por ONI | 17.93 | 17.74 | 0.76 |
    | What-If, clima observado | 14.95 | 14.76 | 0.80 |
    | Línea base "año normal" | 18.35 | 18.35 | 0.52 |

  - **Lectura:** sacar las coberturas empeora 0,2 puntos el MAE de los cultivos reales, dentro del ruido de la validación cruzada. Las filas de la fórmula FAO funcionaban como regularización leve, no como información. Se acepta a cambio de no mezclar dos escalas en el ranking.
  - **Aceptación:** sigue fallando el mismo criterio que en ML-7 (producción contra "año normal": 2.3%, mínimo 5%), por eso `train_baseline` termina con código 1. Contra FAO 23.6% ✅, What-If 18.6% ✅. Monotonía OK, latencia p95 4.3 ms.
  - **Efecto en el ranking (lote sintético con perfil seco, 30% de agua en las raíces, ONI −1):**
    - Invierno, pilar hidroclimático: camelina 32.9, vicia 31.2, avena 31.0, trigo 22.1, cebada 18.3. En ML-7 era trigo 28.0 primero y coberturas 6–9. Con objetivo `equilibrio`, gana avena de cobertura.
    - Verano: girasol 29.2, sorgo 23.2, maíz temprano 16.0, soja de primera 15.2, maíz tardío 8.7, soja de segunda 7.9. Con `equilibrio`, gana sorgo.
    - Con perfil normal o húmedo no hay penalización y las coberturas quedan a menos de 2 puntos de trigo y cebada.
  - **Tests:** `pytest -q` da 240 en verde (6 nuevos: 1 en `test_rotation_matrix.py`, 5 en `test_predictor.py`).

---

### `[x]` ML-8: Umbrales de riesgo en la escala MAGyP y cultivos fuera de ventana
- **Objetivo:** Que el `riesgo` que ve el productor tenga sentido con el modelo de rindes reales. Con los cortes heredados de la escala FAO (`critico` si $S_{\text{hidro}} < 50$), la mitad de los casos salía `critico`, incluido el cultivo recomendado.
- **Cambio de alcance:** la parte de "ranking híbrido con contraste FAO (λ por CV)" de la definición original no se hizo. La reemplazan las reglas explícitas de ML-10 (coberturas por `Ky` y demanda hídrica), más simples de explicar. Si hiciera falta, queda en la hoja de ruta de CONTEXT §4.7.
- **Archivos Permitidos:** `backend/ml/predictor.py`, `backend/ml/test_predictor.py`, `backend/ml/visualize_model.py`, `backend/routers/test_simulate.py` (un valor esperado), `backend/ml/TASKS_ML.md`, `CONTEXT.md`.
- **Decisiones Acordadas con el Desarrollador (2026-11-15):** a partir de la calibración del ensemble de producción en val + test (2019–2024; tasa base de años malos 25%):
  - **Cortes:** `critico` < 40, `alto` 40–45, `medio` 45–50, `bajo` ≥ 50 sobre el promedio del ensemble (`HYDRO_RISK_THRESHOLDS`). Años malos reales por tramo: 52%, 33%, 23% y 13–16%.
  - **Escalón por P10:** sube un nivel si P10 < 30 (`CRITICAL_HYDRO_THRESHOLD`).
  - **`umbral_desfavorable`:** 40 (`DEFAULT_UMBRAL_DESFAVORABLE`).
  - **Suelo:** $S_{\text{suelo}} < 35$ → al menos `alto`. Se eliminan los cortes sobre `score_final`, que mezclaban escalas; `classify_crop_risk(s_hidroclimatico, s_suelo)` ya no recibe `score_final`.
- **Hallazgo en la prueba de punta a punta y corrección (propuesta por el agente):** el 15/11 el endpoint recomendaba Maíz Temprano en Pergamino y Tres Arroyos aunque su siembra terminó el 31/10. Ahora los cultivos con `fuera_de_ventana_siembra` van al final del ranking (siguen apareciendo, no se excluyen) y no pueden ser el ganador ni la alternativa. También se corrigió la frase "a diferencia del Maíz Temprano (riesgo crítico en floración)", que salía aunque su riesgo fuera `bajo`: ahora requiere riesgo `alto` o `critico`.
- **`visualize_model.py`:** lee `dataset_magyp_test.csv.gz`, usa las 15 features y las métricas nuevas (producción, What-If y "año normal" por cultivo) y solo grafica los cultivos entrenados. Regenera los 7 gráficos en `backend/ml/reports/`.
- **Resultado de la Verificación (2026-11-15):**
  - `cd backend && .venv\Scripts\python.exe -m pytest -q`: 244 en verde.
  - `POST /api/v1/simulate` con datos reales el 15/11 (verano, viniendo de soja de primera, objetivo `equilibrio`):

    | Lugar | Agua en las raíces | Lluvia 90 días | Recomendado | Riesgo |
    | :--- | :---: | :---: | :--- | :---: |
    | Pergamino | 46% | −39% | Maíz Tardío (alternativa Sorgo) | `medio` |
    | Río Cuarto | 42% | +27% | Maíz Tardío (alternativa Sorgo) | `bajo` |
    | Tres Arroyos | 59% | −27% | Maíz Tardío (alternativa Sorgo) | `bajo` |

    Repetir soja queda `alto` en los tres por el pilar suelo. Latencia: 9 s en frío, 1,5 s con caché.

---

### `[x]` ML-11: Lote ocupado por el antecesor de invierno (solo cultivos de segunda)
- **Objetivo:** No recomendar cultivos imposibles. Al probar Marcos Juárez con antecesor trigo (15/11), el ranking ponía Soja de Primera segunda y como alternativa, y la estrategia testigo era "trigo → soja de primera". Esa secuencia no existe: el trigo se cosecha en noviembre-diciembre y la soja que va después es, por definición, de segunda. Lo mismo vale para girasol y maíz temprano.
- **Decisión Acordada con el Desarrollador (2026-11-15):** marcar y mandar al final, no excluir. Campo nuevo y opcional `motivo_no_sembrable` en `ranking_cultivos` (texto o `null`), que también cubre la siembra terminada. `fuera_de_ventana_siembra` se mantiene con su significado (solo fecha).
- **Regla (`services/rotation_matrix.motivo_lote_ocupado`):** campaña `verano` y antecesor en `CULTIVOS_INVIERNO_COSECHA` (`trigo`, `cebada`, `camelina`) → solo se pueden sembrar `CULTIVOS_DE_SEGUNDA` (`soja_segunda`, `maiz_tardio`, `sorgo`). Las coberturas, el barbecho o un antecesor de verano no restringen.
- **Testigo:** con antecesor de invierno de cosecha, `compare_rotation_strategies("verano", ...)` usa `soja_segunda` (doble cultivo) en lugar de `soja_primera`.
- **Archivos:** `backend/services/rotation_matrix.py`, `backend/ml/predictor.py`, `backend/schemas.py` (campo opcional, compatible), `backend/ml/test_predictor.py`, `backend/routers/test_simulate.py`, `CONTEXT.md`.
- **También en este cambio:** el contraste "menor adaptación al escenario actual" de la explicación se toma del peor cultivo **sembrable**. Antes podía nombrar a uno que quedó último solo por fecha.
- **Pendiente detectado (no resuelto):** las estrategias "defensiva" y "regenerativa" siguen proponiendo `vicia_cobertura (invierno)` antes del cultivo de verano aunque ese invierno ya fue trigo. Se lee como sugerencia para el año siguiente; conviene aclarar la redacción.
- **Resultado de la Verificación (2026-11-15):** `pytest -q` da 247 en verde. Marcos Juárez, verano, antecesor trigo: Soja de Segunda (alternativa Maíz Tardío), riesgo bajo; Soja de Primera, Girasol y Maíz Temprano al final con "El lote está ocupado por Trigo hasta la cosecha (noviembre-diciembre): solo se pueden sembrar cultivos de segunda."

---

### `[x]` ML-12: Años análogos por fase ENSO y riesgo térmico coherente
- **Origen:** revisión externa de la respuesta de Marcos Juárez (15/11/2026, ONI publicado +2,46, El Niño fuerte). Dos observaciones, ambas confirmadas:
  1. **"Los 19 años análogos no son análogos".** El promedio sí estaba ponderado por ONI, pero con el peso gaussiano (σ = 0,5) y un ONI tan alto, el 81% del peso caía en 2015 y el 19% en 2023 (N efectivo 1,45). Mientras tanto, `anios_desfavorables`, `anios_evaluados` y `peor_escenario` se calculaban **sin pesos** sobre los 19 años. Por eso la explicación citaba como peor caso a 2022 (La Niña, 40 días de más de 34 °C), un año con peso cero.
  2. **"Riesgo térmico alto" contra riesgo bajo en los cultivos.** `telemetria_nasa.riesgo_termico_verano` era el promedio histórico de días de calor de la celda (31,5 en Marcos Juárez → `alto`), sin mirar el ENSO. En los años El Niño esa zona tuvo 10,8 días de calor en el período crítico de la soja de segunda, contra 18,3 en los años La Niña.
- **Decisión (propuesta por el agente a partir de la sugerencia del revisor; el desarrollador pidió continuar):**
  - `providers/enso.py`: `fase_enso` y `pesos_por_fase`. Son análogos los años de la misma fase que hoy (umbral NOAA ±0,5), con peso 1; el resto, peso 0. Si la fase tiene menos de `MIN_ANIOS_ANALOGOS = 5` años, se completa con los de ONI más cercano. `pesos_por_oni` (gaussiano) queda sin uso en producción.
  - `ml/escenarios.py`: `pesos_analogos` usa `pesos_por_fase`; `escenarios_por_cultivo` devuelve solo los años análogos. Así promedio, P10, P90, conteo, peor escenario y el escenario representativo de las anomalías salen del mismo conjunto. `train_baseline` evalúa con la misma función.
  - `ml/predictor.py`: la oración de riesgo empieza con "Hoy rige El Niño (ONI +2.5); se comparó con los años de esa misma fase."
  - `services/simulation_service.py`: en verano, `riesgo_termico_verano` es el que calcula el predictor con los días de calor de los años análogos. En invierno queda el climatológico.
- **Resultado de la Verificación (2026-11-15):**
  - `pytest -q`: 248 en verde.
  - Marcos Juárez, verano, antecesor trigo: Soja de Segunda 72,7, riesgo bajo; 0 de 5 años análogos desfavorables; peor escenario 2023 (El Niño, 19 días de calor) con 51; riesgo térmico `bajo`.
  - Test 2022–2024 en producción con el filtro por fase: MAE 17.9 (mejora 2,4% sobre "año normal"; con peso gaussiano era 17.93 y 2.3%), AUC de años malos 0,77. Sequía 2022/23: real 22.2, predicho 43.6 (antes 43.9). El modelo es el mismo de ML-10: solo cambia cómo se eligen los años análogos.
- **Límite que queda:** entre 5 y 8 años por fase son pocos; el P10 es casi el peor año. No se verificó el pronóstico del SMN que cita el revisor: el sistema no usa pronósticos, solo la fase ENSO ya observada.

---

### `[x]` ML-13: Años análogos desde 1981
- **Objetivo:** Con 19 años de histórico, cada fase ENSO tenía 5 a 8 años análogos y el P10 era casi el peor año. NASA POWER tiene clima diario desde 1981.
- **Decisión (propuesta por el agente, aprobada por el desarrollador el 2026-11-15):** solo el calendario de años análogos se extiende a 1981–2025. La climatología de lluvia (feature `anomalia_lluvia_90d_pct`) y el promedio de días de calor siguen en 2006–2025: así ninguna feature del modelo cambia y no hace falta reentrenar por este motivo.
- **Implementación:**
  - `providers/nasa_telemetry.py`: `ANALOGOS_START = 1981-01-01`; `calcular_referencia` calcula la climatología y los días de calor sobre 2006–2025 (`recortar_serie`) y los calendarios sobre toda la serie. `VERSION_CALCULO = "telemetria-v4"` invalida las cachés viejas. El cálculo en vivo pide 1981–2025.
  - `providers/generar_precache.py` regenera las 299 celdas de `climatologia_pampa.json` desde 1981 (7,5 → 15,8 MB; carga en 0,4 s).
  - `ml/generate_dataset.py`: descarga aparte 1981 → 2005-09 de las 140 celdas de departamentos (`data/cache/nasa_analogos_1981/`, solo lluvia y temperaturas) y la antepone a la serie de cada celda.
  - `ml/train_baseline.py --solo-evaluar`: reevalúa el modelo guardado en ~40 s, sin la búsqueda por CV ni el reentrenamiento (útil cuando cambia la evaluación y no el modelo).
- **Verificación de que las features no cambian:** el dataset regenerado tiene las 284.500 filas anteriores con features y label idénticos (comparación numérica fila por fila). Test nuevo `test_referencia_desde_1981_no_cambia_climatologia_ni_dias_de_calor`. Marcos Juárez: 31,5 días de calor, igual que antes.
- **Cambio no buscado:** al regenerar, San Vicente (06778) entró al dataset: estaba excluido porque SoilGrids no había respondido, y la corrida de descargas reintentó con éxito. 170 departamentos, 575 filas más en train y 46 en test. Por eso se reentrenó completo en lugar de usar `--solo-evaluar`: mismos hiperparámetros, 735 iteraciones (antes 708).
- **Resultado de la Verificación (2026-11-15):**
  - Años análogos para noviembre: El Niño 5 → 12 (se suman 1982, 1986, 1987, 1991, 1997, 2002, 2004), La Niña 6 → 10, neutro 8 → 22.
  - Test 2022–2024:

    | Producción | MAE | AUC años malos |
    | :--- | :---: | :---: |
    | Misma fase ENSO, 2006–2024 (ML-12) | 17.91 | 0.766 |
    | **Misma fase ENSO, 1981–2024 (ML-13)** | **17.85** | **0.784** |
    | Todos los años 1981–2024 sin filtrar | 18.18 | 0.748 |
    | Línea base "año normal" | 18.36 | 0.516 |

    Con más años, filtrar por fase ENSO ayuda de forma clara (17,85 contra 18,18 sin filtrar). Aceptación: producción contra "año normal" 2,8% (sigue debajo del 5%); FAO 23,0% ✅; What-If 19,1% ✅.
  - Marcos Juárez (verano, tras trigo, 15/11): Soja de Segunda 72,1, riesgo bajo, 0 de 12 años El Niño desfavorables; riesgo térmico `medio` (antes `bajo` con 5 años).
  - `pytest -q`: 250 en verde.
- **Límite:** los veranos de los 80 y 90 tuvieron menos días de calor y la lluvia anterior a 2000 no tiene GPM; documentado en CONTEXT §4.7.

---

### `[x]` ML-14: Secuencias que respetan el invierno que ya pasó
- **Objetivo:** La secuencia sugerida salía fija del perfil de cada cultivo. Tras trigo, la estrategia defensiva decía "vicia_cobertura (invierno) -> sorgo (verano)" aunque ese invierno ya había sido trigo.
- **Implementación:** `rotation_matrix.secuencia_real(campana, cultivo_anterior, candidato)`. En verano la secuencia empieza por el invierno real: el antecesor si es de invierno, o `barbecho` si no lo es o no hay antecesor. Si el perfil propone otro invierno, se agrega `; próximo ciclo: <secuencia del perfil>`. En invierno la secuencia del perfil empieza por el propio candidato y se usa tal cual. La usan `secuencia_sugerida` y las estrategias defensiva y regenerativa.
- **Ejemplo:** tras trigo, defensiva = "trigo (invierno) -> sorgo (verano); próximo ciclo: vicia_cobertura (invierno) -> sorgo / maiz_tardio (verano)".
- **Verificación:** test nuevo `test_secuencia_real_respeta_el_invierno_que_ya_paso`; `pytest -q` 250 en verde.

