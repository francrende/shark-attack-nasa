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
