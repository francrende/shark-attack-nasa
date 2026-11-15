# CONTEXTO DEL PROYECTO: Shark Attack

## 1. Visión General (Elevator Pitch)
**Shark Attack** es una plataforma AgTech de soporte a la toma de decisiones agronómicas enfocada en la adaptación climática, eficiencia hídrica y planificación de rotaciones inteligentes. Nace en el **NASA Space Apps Challenge 2026** (*Challenge: Field Shift: Adapting Farms with NASA Data*) con una arquitectura pensada desde el día uno para evolucionar hacia un **producto comercial escalable (SaaS)**.

El sistema asiste al productor y al asesor agronómico para definir **estrategias de rotación y elección de cultivos por campaña (Invierno / Verano)** cruzando cuatro dimensiones:
- **Clima, Hidrología Satelital y Anomalías (NASA POWER + SMAP + GPM + GLDAS):** Índice de saturación hídrica en zona radicular (`GWETROOT`) y superficial (`GWETTOP`), anomalías de precipitación, frecuencia de lluvias extremas, estrés térmico y demanda evaporativa (`EVPTRNS`), detectados automáticamente al seleccionar el lote en el mapa.
- **Topografía y Riesgo de Escorrentía (NASA SRTM):** Elevación y pendiente del terreno a 30 metros de resolución para evaluar pérdida de agua útil por escorrentía superficial, potencial de infiltración y riesgo de erosión hídrica en períodos de suelo desnudo (*bare ground*).
- **Edafología, Aptitud Agroecológica y Salud del Suelo (SoilGrids + FAO GAEZ + MODIS/Sentinel-2):** Propiedades físicas y químicas del lote (textura arcilla/limo/arena, carbono orgánico, pH), curvas ecofisiológicas por cultivo (**FAO GAEZ v4 / FAO-56**), impacto del cultivo antecesor (balance de C/N, cobertura de rastrojo) y vigor vegetativo histórico (`NDVI`).
- **Simulación Interactiva ("What-If"):** Capacidad de evaluar escenarios climáticos futuros (ej. campañas tipo *"La Niña / Seca"* o *"El Niño / Húmeda"*) ajustando prioridades agronómicas y restricciones de mercado.

---

## 2. Arquitectura y Estrategia de Escalabilidad (Hackathon $\rightarrow$ Producto Comercial)

Para no construir código descartable en la hackathon pero tampoco bloquear el entregable de 48 horas, el proyecto adopta **Clean Architecture / Patrón de Adaptadores (Ports & Adapters)** en el Backend y componentes desacoplados en el Frontend.

### 2.1. Tech Stack Base
- **Frontend:** React + TypeScript + Vite (UI/UX enfocada en el productor, mapa interactivo con Leaflet / Mapbox GL superponiendo capas satelitales WMTS/WMS de la NASA).
- **Backend:** Python + FastAPI (Arquitectura modular dividida en `routers/`, `services/`, `providers/` y `ml/`).
- **Data/ML:** `scikit-learn` (`HistGradientBoostingRegressor` / `RandomForestRegressor`) + `Pandas`/`Polars` para series temporales climáticas y motor híbrido de decisión multicriterio (MCDA).
- **Despliegue (Deploy):** Frontend en Vercel | Backend en Render/Railway.
- **Puertos Locales Habituales:** Frontend `:5173` (o `:3000`) | Backend `:8000`.

### 2.2. Matriz de Evolución: MVP Hackathon vs. Producto Comercial (Go-to-Market)

| Módulo / Capa | Fase 1: MVP Hackathon (48 hs) | Fase 2: Producto Comercial Escalable (SaaS) |
| :--- | :--- | :--- |
| **Unidad Espacial** | Punto único por coordenadas (`lat`, `lon`). | Polígonos GeoJSON de lotes reales dibujados por el productor o importados (Shapefile/KML). |
| **Ingesta Climática e Hidrológica** | Consulta síncrona a **NASA POWER API** (asimilación **SMAP + GLDAS + GPM IMERG**, con caché y filtro de `-999`). | Pipeline asíncrono (Celery/Redis + PostGIS) que pre-ingesta **NASA POWER + SMAP L4 + GPM IMERG + ERA5** diariamente. |
| **Topografía y Terreno** | **NASA SRTM (30m)** vía **OpenTopoData API** (con fallback a la elevación embebida en `NASA POWER`) para pendiente y escorrentía. | Modelo Digital de Elevación (DEM) intralote de alta resolución para mapas de flujo de agua y microcuencas de anegamiento. |
| **Datos de Suelo** | **ISRIC SoilGrids API** (o fallback regional pre-cacheado de la Pampa Húmeda) para textura, pH y carbono orgánico. | Integración con cartas de suelo locales (**GeoINTA** en Argentina / **USDA SSURGO & WSS** en EE.UU.) + análisis de laboratorio. |
| **Imágenes Satelitales** | Capas globales **NASA GIBS** (MODIS / VIIRS / SMAP / IMERG) vía WMTS directo en el mapa. | Recorte por lote en alta resolución (10m–30m) usando **NASA HLS (Landsat 8/9 + Copernicus Sentinel-2)** vía STAC/COG para mapeo de suelo desnudo (*bare soil*) y variabilidad intralote. |
| **Entrenamiento del ML** | Modelo entrenado con **rindes reales departamentales de MAGyP** (169 departamentos pampeanos, 2006/07–2024/25) + **NASA POWER**, **SRTM**, **SoilGrids** y el índice **ENSO (ONI de NOAA)**. FAO GAEZ v4 / FAO-56 queda para la sensibilidad del What-If y, vía el factor `Ky`, para puntuar los cultivos sin rinde MAGyP fuera del modelo (ML-10). | Re-entrenamiento continuo con **rindes a escala de lote** (mapas de rinde, seguros), más campañas (1990+), NDVI en la campaña y feedback real de cosecha. |
| **Unidad de Recomendación** | Ranking de cultivos por campaña (`invierno` vs `verano`, fecha temprana/tardía) y comparación de secuencias anuales (incluyendo la rotación actual). | Planificador plurianual (rotación a 3–5 años) con balance acumulado de Carbono, Nitrógeno, Fósforo, huella hídrica y margen de mercado. |

---

## 3. Catálogo de APIs y Fuentes de Datos (NASA, Topografía, Edafología y Agronomía)

### 3.1. APIs Core para el Backend (Datos numéricos en tiempo real por `lat`/`lon`)

#### A. NASA POWER API (Prediction Of Worldwide Energy Resources — Integración SMAP, GLDAS y GPM) — *[Prioridad Alta - Fase 1 y 2]*
API RESTful abierta (no requiere API Key) optimizada para aplicaciones agroclimáticas (`community=AG`). Devuelve JSON directo por coordenadas con series diarias, mensuales y climatologías históricas, integrando observaciones de **SMAP**, modelos de asimilación terrestre **GLDAS**, precipitación satelital **GPM/IMERG** y reanálisis **MERRA-2**.
- **Endpoint base:** `https://power.larc.nasa.gov/api/temporal/{daily|monthly|climatology}/point`
- **Parámetros clave:**
  - `PRECTOTCORR`: Precipitación total corregida (mm/día, derivada de **GPM/IMERG** y estaciones) — cálculo de oferta hídrica acumulada, anomalías de 90 días y frecuencia de tormentas extremas (`> 50 mm/día`).
  - `GWETROOT`: **Fracción de saturación hídrica en la zona radicular (`0.0` a `1.0`, hasta 1m)** asimilada de **GLDAS y SMAP**. *Nota agronómica:* Al ser una fracción de saturación relativa al tipo de suelo y no humedad volumétrica cruda, evita sesgos entre suelos arenosos y arcillosos.
  - `GWETTOP`: Fracción de humedad superficial (0–5 cm) — determina ventana óptima de siembra y permite medir la velocidad de secado superficial.
  - `GWETPROF`: Humedad total del perfil profundo del suelo.
  - `T2M`, `T2M_MAX`, `T2M_MIN`: Temperatura a 2 metros (media, máxima y mínima en °C) — detección de golpes de calor en período crítico y riesgo de heladas / estado de congelamiento (*freeze/thaw*).
  - `ALLSKY_SFC_SW_DWN` / `EVPTRNS`: Radiación solar incidente y flujo de evapotranspiración / demanda evaporativa.
- **Dato topográfico incluido:** El bloque `geometry.coordinates` de la respuesta de NASA POWER devuelve `[lon, lat, elevacion_msnm]`, sirviendo como fallback instantáneo de altimetría.
- **Regla técnica obligatoria (Manejo del lag `-999`):** Los datos satelitales de NASA POWER (especialmente `GWETROOT`) tienen una latencia de procesamiento de **3 a 7 días**. Los últimos días del calendario suelen devolver `-999.0`. El cliente HTTP del backend **siempre debe pedir una ventana de los últimos 30 a 90 días** y tomar el último valor válido (`!= -999.0`).

#### B. NASA SRTM (Shuttle Radar Topography Mission - 30m) vía OpenTopoData API — *[Prioridad Alta - Fase 1 y 2]*
El recurso oficial **NASA SRTM** provee el modelo digital de elevación global a 30 metros de resolución para analizar pendiente (*slope*), escorrentía superficial (*runoff*), potencial de infiltración y riesgo de erosión hídrica.
- **Endpoint REST (sin API Key):** `https://api.opentopodata.org/v1/srtm30m?locations={lat},{lon}|{lat_offset},{lon}`
- **Variables calculadas en el Backend:**
  - `elevacion_m`: Altitud del lote en metros sobre el nivel del mar (con fallback automático a `geometry.coordinates[2]` de NASA POWER si el servicio externo demora).
  - `pendiente_terreno_pct`: Pendiente topográfica local (%) estimada comparando la cota del lote con puntos adyacentes a ~100 m (`±0.001°`). Permite cuantificar la pérdida de agua de lluvia por escorrentía y el peligro de erosión en lotes con pendiente y baja cobertura vegetal.

#### C. ISRIC SoilGrids API (Complemento Edáfico Global — Equivalente a USDA SSURGO / WSS) — *[Prioridad Alta - Fase 1 y 2]*
Cruza las observaciones satelitales de la NASA con las propiedades físicas y químicas locales del suelo a 250m de resolución vía REST JSON por `lat`/`lon`.
- **Endpoint base:** `https://rest.isric.org/soilgrids/v2.0/properties/query`
- **Variables clave:** `clay` (arcilla), `sand` (arena), `silt` (limo), `soc` (carbono orgánico del suelo) y `phh2o` (pH). Permite ajustar la retención hídrica real, el riesgo de erodabilidad y el score de salud del suelo.

#### D. FAO GAEZ v4 (Global Agro-Ecological Zones) & FAO-56 — *[Base de Conocimiento Ecofisiológico Offline - Fase 1 y 2]*
Recurso oficial del challenge que define las curvas de aptitud agroclimática, requerimientos térmicos/hídricos, restricciones edáficas/topográficas y factores de reducción de rinde ($K_y$) para decenas de cultivos a escala global.
- **Modo de consumo (Latencia 0 ms):** Para no penalizar el tiempo de respuesta con descargas raster pesadas en vivo, los umbrales fenológicos y curvas de respuesta de **FAO GAEZ v4 y FAO-56** se integran de forma tabulada en `backend/ml/fao_labels.py` y en el motor agronómico (`backend/services/rotation_matrix.py`). Desde ML-6 el modelo se entrena con rindes reales. Las curvas FAO dan la sensibilidad de las filas What-If y sirven de línea base de comparación. Desde ML-10 los cultivos sin dato MAGyP (coberturas y camelina) ya no entran al modelo: se puntúan con el factor `Ky` de FAO-56 relativo a los cultivos con rinde real (§4.5).

#### E. NASA AppEEARS API (MODIS, SMAP, ECOSTRESS y HLS) — *[Prioridad Media - Fase 2 / Pre-caché Offline]*
API de LP DAAC que extrae series históricas de sensores como **MODIS/VIIRS**, **SMAP**, **ECOSTRESS** (temperatura superficial LST y evapotranspiración a 70m) y **HLS**.
- **Particularidad técnica:** Requiere token de *NASA Earthdata Login* y opera mediante colas de trabajo asíncronas (`jobs`). En el MVP se utiliza para validación y descarga offline; en la **Fase 2 (Producto Comercial)** se integra mediante workers en background.

---

### 3.2. APIs de Imágenes Satelitales y Capas Visuales para el Frontend (Mapas)

#### F. NASA GIBS (Global Imagery Browse Services) / Worldview — *[Prioridad Alta UI/UX - Fase 1]*
Servicio de teselas (WMTS / WMS / XYZ tiles) que permite superponer capas satelitales de la NASA directamente en **Leaflet** o **Mapbox** en tiempo real, sin procesar rasters en el backend ni requerir API Keys.
- **Endpoint WMTS base:** `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{Layer}/default/{Time}/{TileMatrixSet}/{z}/{y}/{x}.{format}`
- **Capas recomendadas para el Frontend:**
  - `MODIS_Terra_CorrectedReflectance_TrueColor` o `VIIRS_SNPP_CorrectedReflectance_TrueColor`: Imagen satelital diaria para inspección visual y detección de suelo desnudo (*bare ground*).
  - `SMAP_L4_Analyzed_Root_Zone_Soil_Moisture`: Mapa de calor global de humedad en zona radicular.
  - `MODIS_Terra_NDVI_8Day`: Capa visual de índice de vegetación (vigor y biomasa activa).
  - `MODIS_Terra_Land_Surface_Temp_Day`: Temperatura superficial terrestre (LST, proxy de **ECOSTRESS/MODIS**) para visualizar focos de estrés térmico.
  - `IMERG_Precipitation_Rate`: Tasa de precipitación derivada de la misión **GPM**.

#### G. NASA Earthdata CMR-STAC / Harmonized Landsat & Copernicus Sentinel-2 (HLS) — *[Fase 2: Escala de Lote]*
API basada en el estándar **STAC** (`https://cmr.earthdata.nasa.gov/stac/LPCLOUD`) que combina **Landsat 8/9 (NASA/USGS)** y **Sentinel-2 (ESA Copernicus)** a 10m–30m de resolución para lectura de NDVI/NDWI intralote y mapeo fino de períodos de suelo desnudo.

---

### 3.3. Equivalencia de Recursos del Challenge (Estándar EE.UU. vs. Implementación Global / Argentina)

El listado oficial de recursos del challenge incluye bases de datos gubernamentales de EE.UU. (USDA/USGS). Para que **Shark Attack** opere en la **Región Pampeana (Argentina)** y sea escalable globalmente, la arquitectura implementa sus equivalentes exactos:

| Recurso Oficial del Challenge (EE.UU.) | Función en el Challenge | Implementación en **Shark Attack** (Global / Argentina) |
| :--- | :--- | :--- |
| **USDA SSURGO / Web Soil Survey (WSS)** | Textura, materia orgánica, drenaje y retención hídrica del suelo. | **ISRIC SoilGrids API** (Global 250m) + **Cartas de Suelo GeoINTA**. |
| **USDA NASS QuickStats & CDL (CropScape)** | Rindes históricos por condado y secuencias de cultivos previas. | **SIIA / MAGyP (Estimaciones Agrícolas)** por departamento y campaña. |
| **USDA AMS Market News** | Precios de commodities, liquidez y viabilidad comercial de la rotación. | **Indicador de Aptitud de Mercado / Riesgo Financiero** en la matriz de cultivos (liquidez comercial vs. inversión en cultivo de servicio). |
| **PRISM Climate Data & CoCoRaHS** | Normales climáticas de 30 años y validación de lluvias extremas. | Climatología histórica de 20–30 años de **NASA POWER** y reanálisis **ERA5 (ECMWF/ESA)**. |
| **OpenET** | Evapotranspiración a escala de lote para manejo del agua. | Flujo de evapotranspiración `EVPTRNS` (**NASA POWER / GLDAS**) + **NASA ECOSTRESS**. |

---

## 4. Arquitectura de Machine Learning, Detección de Anomalías y Motor de Decisión

El motor de recomendación está diseñado bajo una interfaz común (`RecommendationEngine`) que combina **Machine Learning basado en Árboles (`scikit-learn`)** con una **Matriz de Transición Agronómica, Topográfica y Scoring Multicriterio (MCDA)**.

### 4.1. Separación por Campaña y Recomendación de Campaña Actual
Para evitar el error agronómico de comparar cultivos de invierno contra cultivos de verano en una misma fecha de siembra, el motor opera sobre **ventanas de campaña explícitas**:
- **Campaña Gruesa (`verano`):** `maiz_temprano`, `maiz_tardio`, `soja_primera`, `soja_segunda` (post-fina), `girasol`, `sorgo`.
- **Campaña Fina (`invierno`):** `trigo`, `cebada`, `vicia_cobertura` (leguminosa fijadora de N), `avena_cobertura` (gramínea de cobertura contra erosión), `camelina`.
- **Ambas campañas están soportadas con la misma lógica** (backend, ML y matriz de rotación). Lo que cambia según la fecha es **cuál está habilitada en la interfaz**: el frontend **bloquea el botón de la campaña que no corresponde a la fecha actual**, porque el modelo evalúa con los datos satelitales y climáticos del día de hoy ($t \approx$ hoy) y con los años análogos del **período crítico** de cada cultivo en esa campaña (ensemble ponderado por ENSO, ver §4.3 B). Cuando sea efectivamente época de invierno, se habilita `invierno` y se bloquea `verano`, sin ningún cambio de lógica.
- **Regla de campaña vigente:** es la misma que se usa en el entrenamiento (`generate_dataset.py`): se mira el **mes central de la ventana futura** (hoy + 45 días). Si cae entre **abril y septiembre**, la campaña habilitada es `invierno`; si no, `verano`. En la práctica, `invierno` queda habilitada aproximadamente entre mediados de febrero y mediados de agosto. Frontend y ML deben usar exactamente esta regla.
- **Alcance de la Recomendación (`secuencia_sugerida`):** El sistema recomienda el cultivo (o terna alternativa) para la **campaña habilitada en curso**, contrastándolo contra alternativas defensivas y contra la **estrategia testigo (repetir el cultivo anterior / monocultivo)** según el estado hídrico y edáfico actual.

### 4.2. Modelo de Machine Learning (`HistGradientBoostingRegressor` / `RandomForestRegressor`) y Datos de Entrenamiento
- **Qué predice:** El **Puntaje de Aptitud Hidroclimática ($S_{\text{hidroclimatico}}$, de 0 a 100)** de cada cultivo candidato: el **rinde esperado respecto de la tendencia normal del lugar** (50 = año normal, 30 = 20% menos, 70 = 20% más), aprendido de rindes reales de MAGyP. Las entradas son la telemetría satelital de la NASA (`GWETROOT`, `GWETTOP`, `PRECTOTCORR`, `T2M_MAX`, `T2M_MIN`, `EVPTRNS`), la pendiente (`SRTM`), la textura del suelo (`SoilGrids`), el clima del período crítico del cultivo y el ENSO.
- **Por qué ensambles de árboles:** Capturan interacciones no lineales críticas (ej. caída abrupta de aptitud cuando `T2M_MAX > 34°C` coincide con `GWETROOT < 0.30`, o pérdida de eficiencia de lluvia cuando `pendiente_terreno_pct > 2.0%` en suelos con baja infiltración), no requieren GPU, corren en `< 15 ms` en producción y proveen explicabilidad (`feature_importances_`).
- **Con qué datos se entrena (Estrategia en 2 Fases):**
  1. **Fase 1 (ML-1/ML-2, reemplazada en ML-6/ML-7):** el target salía de las curvas FAO GAEZ v4 / FAO-56 aplicadas a 15 localidades. El modelo solo imitaba la fórmula (R² 0,99 contra ella), y contra rindes reales predecía peor que decir "año normal". La fórmula queda en `ml/fao_labels.py`, solo para las filas What-If y como línea base.
  2. **Fase 2 (implementada en ML-6/ML-7, `generate_dataset.py` + `train_baseline.py`):**
     - **Cultivos que entran al modelo (ML-10):** solo los 8 con rinde MAGyP (`trigo`, `cebada`, `maiz_temprano`, `maiz_tardio`, `soja_primera`, `soja_segunda`, `girasol`, `sorgo`). `vicia_cobertura`, `avena_cobertura` y `camelina` se puntúan fuera del modelo (§4.5).
     - **Label:** rinde real departamental de **MAGyP** en 169 departamentos pampeanos, campañas 2006/07–2024/25. El rinde se ajusta por la superficie abandonada respecto de la típica del departamento y se compara contra su tendencia de largo plazo (Theil–Sen): `puntaje = 50 + 100 × (rinde/tendencia − 1)`. **50 es un año normal** y 30 es un rinde 20% bajo la tendencia.
     - **Features:** las mismas fórmulas que producción (`providers/features.py`). El suelo sale de SoilGrids y la topografía de SRTM, por departamento.
     - **Elección del modelo:** HistGradientBoosting con monotonía en calor y heladas, elegido por validación cruzada dejando una campaña afuera.
     - **Resultado en test 2022–2024 (MAE):**
       - Producción con años análogos ponderados por ONI: 17.9 (17.7 en ML-7, con las coberturas dentro del modelo).
       - What-If con el clima del período crítico observado: 14.9.
       - Línea base "año normal": 18.4. Línea base FAO: 23.5.
     - **Detección de años malos:** AUC 0.76, contra 0.52 de "año normal".
     - **Límite conocido:** antes de sembrar, la predictibilidad está acotada por el clima del período crítico, que todavía no ocurrió. El ranking entre cultivos de un mismo año es débil (ver ML-8 y ML-9).
     - **Fase comercial siguiente:** rindes a escala de lote, NDVI en la campaña (MODIS/Sentinel-2) y ERA5.

### 4.3. Features de Entrada ($X$) del Modelo ML: Estado Actual (`[-89d, t]`) vs. Período Crítico del Cultivo
Todas las features se calculan de forma determinística a partir de las respuestas de **NASA POWER**, **NASA SRTM (OpenTopoData)**, **ISRIC SoilGrids** y el **ONI de NOAA**, con las mismas funciones en entrenamiento y producción (`providers/features.py`). Se separa rigurosamente el **estado hídrico heredado en el suelo** (ventana pasada `[t - 89, t]`, conocido al decidir) de los **riesgos meteorológicos del período crítico del cultivo** (desconocidos al decidir: en producción llegan como años análogos):

- **A. Ventana Pasada `[t - 89, t]` (Estado Hídrico y Memoria del Suelo al día de evaluación $t$):**
  1. `gwetroot_saturacion_pct`: Índice de humedad en zona radicular en el día $t$ (`GWETROOT * 100`, de NASA POWER / SMAP-GLDAS, o valor simulado en modo *What-If*).
  2. `gwettop_saturacion_pct`: Humedad superficial (0–5 cm, `GWETTOP * 100`) en el día $t$ para viabilidad de emergencia en siembra y detección de desacople con la raíz.
  3. `tendencia_humedad_15d_pct`: Variación neta de humedad superficial/radicular en los últimos 15 días válidos (`[t - 14, t]`, mide la velocidad de secado o recarga reciente del perfil).
  4. `anomalia_lluvia_90d_pct`: Desvío porcentual de la lluvia acumulada (`PRECTOTCORR`) de los últimos 90 días (`[t - 89, t]`) respecto a la climatología histórica de 20 años de NASA POWER en esa coordenada.
  8. `indice_aridez_evaporativa`: Relación entre precipitación acumulada y demanda evaporativa (`PRECTOTCORR / EVPTRNS`) en los 90 días previos (`[t - 89, t]`) que explica cómo llegó el perfil hídrico al día $t$.

- **B. Período Crítico del Cultivo (Riesgos Meteorológicos durante el Ciclo; desde ML-7 reemplaza a la ventana `[t + 1, t + 90]`):**
  *(ML-7: las features se miden en una ventana de 90 días que empieza `OFFSET` días después del inicio de siembra de cada cultivo (`ml/calendario_siembra.py`). Cubre la floración y el llenado en verano, y la espigazón y el llenado en los cereales de invierno, que es la etapa que define el rinde. En el entrenamiento se usa la ventana observada de esa campaña. En producción se usan los **años análogos** de esa misma ventana (`ml/escenarios.py`), **ponderados por ENSO**: el peso es gaussiano en la diferencia entre el ONI de NOAA publicado hoy y el publicado en la misma fecha de cada año (`providers/enso.py`). Se agregan tres features: `lluvia_periodo_critico_mm` (lluvia acumulada en el período crítico), `dias_hasta_siembra` (desde t hasta el inicio de siembra) y `oni_actual`. El modelo pasa a tener 15 features.)*
  *(Distribución, no un número: el ML (`predict_ensemble`) corre el modelo una vez por año análogo y cultivo y devuelve el **promedio ponderado** (score principal), el **P10** ("año malo"), el **P90** ("año bueno"), la cantidad de años bajo el umbral desfavorable y el peor año análogo. Es la lógica del "Ensemble Streamflow Prediction" hidrológico: no se pronostica el clima, se usa lo que ya ocurrió en esa coordenada y en esas fechas, dando más peso a los años con la misma fase ENSO.)*
  5. `frecuencia_tormentas_extremas`: Cantidad de eventos de lluvia torrencial (`PRECTOTCORR > 50 mm/día`, derivado de GPM/IMERG/POWER) en el período crítico del cultivo — indicador de riesgo de escorrentía y erosión durante el ciclo.
  6. `frecuencia_estres_termico`: Días con `T2M_MAX > 34°C` en el período crítico (golpes de calor en floración y llenado). El modelo es **monótono**: más días de calor nunca suben el puntaje.
  7. `frecuencia_riesgo_helada`: Días con `T2M_MIN < 2°C` en el período crítico (también monótono).

- **C. Variables Topográficas, Edáficas y de Cultivo:**
  9. `pendiente_terreno_pct`: Pendiente topográfica local (%) obtenida de **NASA SRTM (30m)** (modifica la infiltración efectiva del agua de lluvia y el riesgo de erosión).
  10. `elevacion_m`: Altitud sobre el nivel del mar (msnm) vía **NASA SRTM / NASA POWER**.
  11. `textura_arcilla_pct`: Porcentaje de arcilla del lote vía **ISRIC SoilGrids** (regula la capacidad de retención hídrica y el drenaje).
  12. `cultivo_candidato`: Identificador/codificación del cultivo a evaluar dentro de la campaña seleccionada.
  13. `lluvia_periodo_critico_mm`, 14. `dias_hasta_siembra`, 15. `oni_actual` (ML-7, ver B).

### 4.4. Detección Basada en Evidencia de Fenómenos Meteorológicos Inusuales (Sin Predicciones Forzadas)
> **Principio de Rigor Técnico:** Los datasets satelitales de observación de la Tierra (**SMAP, GPM, MODIS, SRTM, NASA POWER**) miden el **estado físico actual y la climatología histórica**, no son modelos meteorológicos de pronóstico a 6 meses ni modelos oceánicos del Pacífico. Por lo tanto, **el sistema NO fuerza predicciones meteorológicas futuras que los datos no pueden sostener**.

En su lugar, el backend combina la telemetría de los últimos 90 días con la estadística histórica de 20 años de la NASA para **detectar anomalías físicas ya en curso** y **cuantificar riesgos empíricos reales** en el lote:

1. **Pulso de Secado Rápido (*Flash Drought Onset*):**
   - *Qué sí podemos saber con los datos:* Si en los últimos 15 días `tendencia_humedad_15d_pct` muestra una caída brusca (ej. `< -15%`) coincidiendo con temperaturas altas (`T2M_MAX`) y alta demanda evaporativa (`EVPTRNS`). Se informa una alerta temprana de **secado acelerado en curso**, sin inventar si lloverá el mes próximo.
2. **Trampa de "Falsa Recarga" Superficial (`GWETTOP` vs. `GWETROOT`):**
   - *Qué sí podemos saber con los datos:* Si una lluvia reciente humedeció los primeros 5 cm (`GWETTOP > 60%`, dando falsa sensación de humedad para sembrar), pero el metro profundo sigue seco (`GWETROOT < 35%`). El sistema advierte que el lote **no tiene reserva profunda** para sostener un cultivo demandante si se cortan las lluvias en verano.
3. **Peligro de Escorrentía y Erosión por Lluvias Torrenciales (`GPM/PRECTOTCORR` + `SRTM`):**
   - *Qué sí podemos saber con los datos:* Cruzando la frecuencia de tormentas intensas (`> 50 mm/día`) con la pendiente real de **SRTM (`pendiente_terreno_pct`)** y la textura de **SoilGrids**, el sistema identifica si el lote es propenso a perder agua por escorrentía y sufrir lavado de suelo cuando queda desnudo (*bare ground*).
4. **Exposición Histórica a Extremos Térmicos (Climatología NASA POWER) y Simulación de Escenarios (ENSO):**
   - El sistema reporta la frecuencia estadística histórica de golpes de calor y heladas en esa coordenada.
   - **No se genera un pronóstico estacional propio.** Se usa el **estado ENSO ya observado y publicado por NOAA** (ONI): los años análogos con la misma fase (La Niña / Neutro / El Niño) pesan más en el ensemble. Es evidencia, no adivinación: las sequías 2008/09, 2017/18 y 2022/23 fueron años La Niña.
   - Para evaluar qué pasaría si la campaña resulta atípicamente seca o húmeda, se proveen **Presets Climáticos en el simulador *What-If***, para que el productor o su agrónomo evalúen la sensibilidad de cada rotación bajo cada escenario.
   - **Límite honesto (ML-7):** antes de sembrar, el rinde es poco predecible, porque depende del clima del período crítico. El modelo mejora un 2–3% sobre "año normal" en producción y un 19% con el clima conocido (What-If) (ver §4.7). Por eso la respuesta muestra un **rango** (P10–P90, años desfavorables) y no un número único.

### 4.5. Los 2 Pilares del Puntaje, Viabilidad de Mercado y Fórmula Dinámica
Para mantener la transparencia matemática, el sistema separa el cálculo en **2 pilares cuantitativos** complementados con metadatos de riesgo, mercado y validación local:

1. **$S_{\text{hidroclimatico}}$ (Clima + Agua + Topografía Hídrica — Modelo de ML + dos reglas agronómicas explícitas, ver abajo):** Evalúa qué tan viable es el cultivo según la reserva radicular (`GWETROOT`), el secado reciente, la anomalía de lluvias (`PRECTOTCORR`), el estrés térmico (`T2M_MAX`/`T2M_MIN`), la demanda evaporativa (`EVPTRNS`) y la eficiencia de infiltración según pendiente (`SRTM`) y arcilla (`SoilGrids`).
2. **$S_{\text{suelo}}$ (Salud del Suelo, Cobertura y Control de Erosión — Calculado por Matriz Agronómica + SoilGrids + SRTM):** Evalúa la transición `cultivo_anterior -> cultivo_candidato` (balance de Carbono/Nitrógeno, aporte de rastrojo, reducción de meses de suelo desnudo y corte de ciclo de plagas) ajustada por el nivel actual de Carbono Orgánico (`soc`) y penalizando doblemente los cultivos de baja cobertura en lotes con pendiente elevada (`pendiente_terreno_pct` de SRTM).

**Reglas agronómicas sobre $S_{\text{hidroclimatico}}$ (ML-10).** El modelo aprende cuánto se desvía cada cultivo de **su propio** rinde normal. No sabe cuánta agua consume un cultivo ni puede puntuar cultivos sin rinde histórico. Dos reglas determinísticas y explicables cubren eso:

- **Cultivos sin rinde MAGyP (`vicia_cobertura`, `avena_cobertura`, `camelina`):** no pasan por el modelo. Su puntaje parte del promedio de los cultivos con rinde real de la misma campaña (trigo y cebada) y escala el desvío respecto de un año normal por el factor de respuesta del rinde de FAO-56: $S = 50 + \frac{K_{y,\text{cultivo}}}{K_{y,\text{referencia}}} \cdot (S_{\text{referencia}} - 50)$. Con $K_y$ menor (0,62–0,76 contra 1,05), una cobertura se aleja menos de 50 que el trigo, para bien y para mal. Se calcula año análogo por año análogo, así que también tiene P10, P90 y años desfavorables.
- **Demanda hídrica con perfil seco (`penalizacion_demanda_hidrica` en `services/rotation_matrix.py`):** si el agua en las raíces (`GWETROOT`) está por debajo de 45%, a cada cultivo se le restan hasta 10 puntos según su consumo de agua del ciclo (`CONSUMO_AGUA_CICLO_MM`, de 220 mm en vicia a 550 mm en maíz temprano): `10 × severidad × demanda_relativa`, con severidad 0 en 45% y 1 en 25% o menos. Representa el agua que el cultivo le saca al perfil y no le deja al siguiente, algo que el rinde del propio cultivo no mide. Cuando aplica, la `explicacion` lo dice. Los consumos son orientativos (rangos FAO ajustados al ciclo pampeano) y requieren validación local.

$$\text{Score Final} = w_{\text{clima}} \cdot S_{\text{hidroclimatico}} + w_{\text{suelo}} \cdot S_{\text{suelo}}$$

| `objetivo_productor` | Peso Hidroclimático ($w_{\text{clima}}$) | Peso Suelo ($w_{\text{suelo}}$) | Enfoque de la Recomendación |
| :--- | :---: | :---: | :--- |
| `resiliencia_hidroclimatica` | **`0.75`** | `0.25` | Prioriza asegurar el cultivo frente a sequías, baja humedad radicular o golpes de calor. |
| `conservacion_suelo` | `0.30` | **`0.70`** | Prioriza regenerar carbono, proteger pendientes contra la erosión, aportar rastrojo y cortar el monocultivo. |
| `equilibrio` | `0.50` | `0.50` | Balance 50/50 entre seguridad hídrica/climática y sustentabilidad del suelo. |

### 4.6. Flujo de Ejecución: Offline (Entrenamiento) vs. Online (Inferencia en Producción)
- **Fase Offline (Pre-deploy):** `python -m ml.generate_dataset` (rindes MAGyP + NASA POWER + SRTM + SoilGrids + ONI) y `python -m ml.train_baseline` (validación cruzada dejando una campaña afuera) generan `modelo_agro.joblib`, que se incluye en el repositorio del backend.
- **Fase Online (`POST /api/v1/simulate` en `< 1.5s`):**
  1. FastAPI recibe `coordenadas`, `campana`, `cultivo_anterior`, `objetivo_productor` y (opcionalmente) `simulacion_what_if`.
  2. Consulta en paralelo **NASA POWER API** (filtrando lags `-999.0`), **OpenTopoData SRTM API** (con fallback a la elevación de NASA POWER) e **ISRIC SoilGrids API**.
  3. Calcula las 8 features actuales (`BACK-6`), el ONI publicado y, para cada cultivo de la campaña, los **años análogos de su período crítico ponderados por ENSO** (`ml/escenarios.py`), más `dias_hasta_siembra`.
     - Evalúa las alertas de anomalías físicas en curso, sin forzar predicciones sin sustento.
     - Ejecuta en memoria el ensemble `predict_ensemble` (`ML-5`/`ML-7`) en un único batch de `años × cultivos`. Así obtiene $S_{\text{hidroclimatico}}$ (promedio ponderado) y su distribución (P10, P90 y años desfavorables).
     - Puntúa los cultivos sin rinde MAGyP relativo a los que sí tienen, y descuenta la demanda hídrica si el perfil está seco (ML-10, §4.5).
     - El riesgo se clasifica con el promedio y sube un nivel si el P10 cae en zona crítica (umbrales de ML-8, abajo).
     - Los cultivos cuya siembra ya terminó se marcan con `fuera_de_ventana_siembra` y van al final del ranking: nunca son el cultivo recomendado ni la alternativa.

**Umbrales de riesgo (ML-8, escala MAGyP).** Calibrados con el ensemble de producción en 2019–2024, donde en promedio 1 de cada 4 años es malo (rinde real 15% o más bajo la tendencia):

| `riesgo` | Puntaje hidroclimático esperado | % de casos | Años malos reales |
| :--- | :---: | :---: | :---: |
| `critico` | < 40 | 15% | 1 de cada 2 |
| `alto` | 40–45 | 17% | 1 de cada 3 |
| `medio` | 45–50 | 22% | 1 de cada 4 |
| `bajo` | ≥ 50 | 46% | 1 de cada 7 |

- **Escalón por P10:** si el peor 10% de los años análogos queda debajo de 30, el riesgo sube un nivel (pasa en el 18% de los casos, y en ellos 4 de cada 10 años son malos).
- **Suelo:** con $S_{\text{suelo}} < 35$ (por ejemplo, repetir soja en pendiente) el riesgo es al menos `alto`.
- **Año análogo desfavorable** (`anios_desfavorables`): puntaje menor a 40. El modelo achata hacia la media, así que 40 en sus predicciones equivale a un año malo real.
  4. Cruza cada cultivo con la **Matriz de Rotación y Pendiente** para obtener $S_{\text{suelo}}$, aplica los pesos ($w_{\text{clima}}, w_{\text{suelo}}$) e incluye las notas de incertidumbre y validación agronómica local requeridas por el challenge.

### 4.7. Límites Conocidos del Modelo y Hoja de Ruta
Esta sección registra qué hace bien el modelo, qué no, y qué se puede mejorar. El challenge no pide predecir rinde: pide una herramienta de apoyo que compare estrategias de rotación, explique la evidencia y muestre la incertidumbre. El modelo es un insumo de esa comparación, no el producto.

**Qué quedó validado (test 2022/23–2024/25 y validación cruzada por campaña):**
- **Campaña correcta:** el predictor solo evalúa los cultivos de la campaña pedida y el backend rechaza la campaña que no corresponde a la fecha. No depende del modelo.
- **Reacción al estado del suelo:** con perfil seco bajan todos los cultivos y más los sensibles. En verano el orden es agronómicamente razonable (girasol y sorgo arriba, sojas abajo).
- **Detección de años malos:** AUC 0,76 en producción, contra 0,52 de la línea base "año normal".
- **Contra la fórmula FAO:** el modelo es un 24% mejor. La fórmula sola predice peor que decir "año normal".

**Problemas conocidos:**

| Problema | Evidencia | Consecuencia |
| :--- | :--- | :--- |
| Antes de sembrar, el rinde es poco predecible | En producción el MAE es 17,9 contra 18,4 de "año normal" (2,3%). Con el clima del período crítico conocido baja a 14,9 | La respuesta muestra un rango (P10–P90), no un número. No se debe prometer "predicción de rinde" |
| Pocas campañas independientes | El rinde de un año está muy correlacionado entre departamentos: son 16 campañas, no 200 mil filas. Las 4 configuraciones probadas dan el mismo MAE | Cambiar hiperparámetros no ayuda; hacen falta más años |
| El test depende de un solo año | Casi toda la ganancia viene de la sequía 2022/23. En validación cruzada, con clima observado, la mejora es 6% | Con 3 años de test no se distingue 3% de 5% |
| En producción la predicción se achata | En 2022/23 el puntaje real fue 22 y el predicho 44 | Anticipa la dirección, no la magnitud |
| Ranking débil entre cultivos del mismo año | Spearman 0,05. `maiz_temprano` y `maiz_tardio` comparten el rinde "maíz" | El orden fino entre cultivos lo deciden el pilar suelo y las reglas de §4.5 |
| Features gruesas del período crítico | `indice_aridez_evaporativa` usa `EVPTRNS` (evapotranspiración real, no demanda) y casi no aporta; calendario único para toda la región; un solo umbral de calor (34 °C) | El techo con clima conocido es bajo (R² 0,30) |
| El ONI funciona en parte como "identificador de año" | La curva de respuesta al ONI (`ml/reports/05_curvas_respuesta_verano.png`) es irregular, con saltos entre −1,5 y 0: con 16 campañas, cada valor de ONI corresponde casi a un año puntual | Sobreajuste posible en la ponderación por ENSO. Con más campañas (hoja de ruta 4) o con el ONI agrupado en fases (Niña / Neutro / Niño) se suaviza |
| Filas What-If con fórmula FAO | Cerca del 4% del peso de entrenamiento todavía sale de la fórmula | Falta medir si conviene quitarlas (ablación) |

**Qué se corrigió en ML-10:** las coberturas tenían label de fórmula FAO y en sequía caían a 6–8 puntos, lo que dejaba al trigo primero aunque fuera el más demandante. Ahora se puntúan relativo a los cultivos reales (FAO-56 `Ky`) y se descuenta la demanda hídrica con perfil seco (§4.5).

**Hoja de ruta, en orden de costo/beneficio:**
1. **Medir en el régimen correcto:** validación cruzada dejando una campaña afuera sobre las 19 campañas y con años análogos (producción), con el resultado por año. Hoy la selección usa clima observado.
2. **Modelo directo para producción:** un segundo modelo entrenado solo con lo conocido al decidir (estado actual, ONI, cultivo, días a siembra). El actual queda para el What-If.
3. **Más años análogos:** NASA POWER llega a 1981. Pasar de 19 a unos 44 años análogos mejora el P10 y la ponderación por ENSO, sin depender de MAGyP.
4. **Más campañas con rinde (ML-9, 1990+):** con tendencia flexible en lugar de lineal (siembra directa, soja RR), asignando el rinde "maíz" anterior a 2010 solo a `maiz_temprano`, y verificando desde cuándo MAGyP separa soja de primera y de segunda.
5. **Mejores features del período crítico:** lluvia menos demanda (ET0 por Hargreaves), `GWETROOT` y temperatura máxima media dentro del período, sub-ventanas de 30 días, umbral de calor por cultivo y calendario corrido por latitud.
6. **Ponderar por superficie sembrada:** hoy un departamento con 1.000 ha pesa igual que uno con 200.000 ha.
7. **Escala de lote (fase comercial):** rindes de mapas de cosecha, NDVI en la campaña (MODIS / HLS) y consumo de agua medido (ECOSTRESS) en lugar de la tabla orientativa.

---

## 5. Contratos de Datos (API JSON)
Formato estándar de comunicación entre el Frontend y el Backend.

### Request: `POST /api/v1/simulate`
> **Nota de UX:** El usuario **no necesita ingresar la humedad del suelo ni la pendiente manualmente**; el backend las detecta automáticamente vía satélite (`GWETROOT` de NASA POWER y pendiente de NASA SRTM). El campo `simulacion_what_if` es **opcional** y permite simular escenarios hipotéticos (ej. botones rápidos de escenario *"Seco / La Niña"*, *"Neutro"* o *"Húmedo / El Niño"*, o sliders manuales).

```json
{
  "coordenadas": {
    "lat": -33.95,
    "lon": -60.57
  },
  "campana": "verano", // opciones: "invierno", "verano"
  "cultivo_anterior": "soja_primera",
  "objetivo_productor": "equilibrio", // opciones: "resiliencia_hidroclimatica", "conservacion_suelo", "equilibrio"
  "simulacion_what_if": {
    "override_humedad_radicular_pct": null, // opcional (0-100): si es null, usa el dato real de NASA POWER
    "variacion_lluvia_esperada_pct": 0 // opcional (-50 a +50): "llueve X% más/menos" que lo observado (multiplica la lluvia: con anomalía -37% y -40 queda -62%). Ej. -25 seco, +25 húmedo
  }
}
```

### Response Esperada: `200 OK`
```json
{
  "ubicacion": { "lat": -33.95, "lon": -60.57 },
  "telemetria_nasa": {
    "fecha_ultimo_dato_valido": "2026-11-08",
    "indice_humedad_radicular_pct": 34.0,
    "indice_humedad_superficial_pct": 28.5,
    "tendencia_humedad_15d_pct": -12.0,
    "anomalia_lluvia_90d_pct": -24.2,
    "frecuencia_tormentas_extremas_90d": 1,
    "riesgo_termico_verano": "alto"
  },
  "topografia_srtm": {
    "elevacion_m": 78.5,
    "pendiente_terreno_pct": 1.8,
    "riesgo_erosion_escorrentia": "medio"
  },
  "perfil_suelo": {
    "textura_predominante": "franco_limoso",
    "arcilla_pct": 24.5,
    "carbono_organico_g_kg": 18.4,
    "condicion_rotacion_previa": "deficit_rastrojo_por_soja"
  },
  "anomalias_detectadas": [
    {
      "tipo": "deficit_hidrico_radicular",
      "severidad": "alta",
      "evidencia": "Reserva radicular en 34% con anomalía de lluvias de -24.2% en los últimos 90 días (NASA POWER / SMAP)."
    }
  ],
  "recomendacion_principal": {
    "cultivo": "sorgo",
    "secuencia_sugerida": "sorgo / maiz_tardio (verano)",
    "score_final": 90.5,
    "sub_scores": {
      "hidroclimatico": 86.0,
      "suelo": 95.0
    },
    "distribucion_hidroclimatica": { // ML-5: ensemble de años análogos (solo si hay escenarios_historicos)
      "promedio": 86.0,
      "p10": 71.5,
      "p90": 94.0,
      "anios_desfavorables": 1, // años con score < umbral_desfavorable
      "anios_evaluados": 19,
      "umbral_desfavorable": 40.0,
      "peor_escenario": {
        "anio": 2008,
        "score": 44.0,
        "frecuencia_tormentas_extremas": 0,
        "frecuencia_estres_termico": 18,
        "frecuencia_riesgo_helada": 0
      }
    },
    "perfil_mercado": "Bajo costo de implantación y alta estabilidad defensiva; grano comercializable como forraje o exportación.",
    "factores_clave_ml": [
      "Baja saturación hídrica en zona radicular detectada por NASA (34%)",
      "Pendiente de 1.8% (SRTM) requiere rastrojo de gramínea tras Soja para frenar escorrentía",
      "Anomalía de lluvias de -24.2% en los últimos 90 días"
    ],
    "explicacion": "Recomendación: Sembrar Sorgo (o Maíz Tardío precedido por Vicia). Detectamos vía satélite una reserva hídrica ajustada (34% de saturación radicular), un déficit de lluvias del 24% y una pendiente del 1.8% (SRTM). A diferencia del Maíz Temprano (riesgo crítico en floración) o repetir Soja (degradación de carbono y riesgo de erosión por suelo desnudo), el Sorgo ofrece un 86% de aptitud hidroclimática y un 95% de beneficio edáfico para proteger y recomponer la estructura del lote."
  },
  "ranking_cultivos": [
    // ML-5: score_hidroclimatico_p10, anios_desfavorables y anios_evaluados solo vienen si hay escenarios_historicos
    // ML-7: "fuera_de_ventana_siembra": true si la siembra de ese cultivo ya terminó (se marca y va al final del ranking; no se excluye)
    { "cultivo": "sorgo", "score_final": 90.5, "riesgo": "bajo", "fuera_de_ventana_siembra": false, "score_hidroclimatico_p10": 71.5, "anios_desfavorables": 1, "anios_evaluados": 19 },
    { "cultivo": "maiz_tardio", "score_final": 82.5, "riesgo": "medio", "score_hidroclimatico_p10": 58.0, "anios_desfavorables": 2, "anios_evaluados": 19 },
    { "cultivo": "girasol", "score_final": 72.0, "riesgo": "bajo", "score_hidroclimatico_p10": 66.0, "anios_desfavorables": 1, "anios_evaluados": 19 },
    { "cultivo": "maiz_temprano", "score_final": 64.0, "riesgo": "critico", "score_hidroclimatico_p10": 22.0, "anios_desfavorables": 9, "anios_evaluados": 19 },
    { "cultivo": "soja_primera", "score_final": 31.0, "riesgo": "alto", "score_hidroclimatico_p10": 30.5, "anios_desfavorables": 7, "anios_evaluados": 19 }
  ],
  "validacion_local_requerida": {
    "nota_resolucion_satelital": "Humedad satelital (NASA POWER/SMAP) estimada a escala regional (~9 km), topografía SRTM a 30 m y suelo a 250 m.",
    "brechas_informacion": [
      "No mide profundidad de napa freática local ni compactación subsuperficial (piso de arado)",
      "No reemplaza el pronóstico meteorológico estacional ni el análisis químico de laboratorio (Fósforo/Nitrógeno)"
    ],
    "recomendacion_experto": "Validar agua útil real con muestreo de barreno a 1 metro y consultar al ingeniero agrónomo local antes de definir la densidad de siembra."
  },
  // BACK-7: además vienen "cobertura_12_meses" y "comparacion_estrategias" (ML-3; ver Swagger en /docs)
  "advertencias": [] // avisos de calidad de dato (fallback regional de SoilGrids/SRTM, propiedades faltantes)
}
```

> **Notas de implementación (BACK-7):**
> - `telemetria_nasa`, `topografia_srtm` y `perfil_suelo` muestran el **dato satelital real**, sin los topes del modelo ni el What-If. El What-If solo cambia los scores, el ranking, las anomalías y la explicación.
> - **ML-10:** el contrato no cambia. `sub_scores.hidroclimatico`, la distribución y el ranking ya incluyen el descuento por demanda hídrica; cuando aplica, `explicacion` termina con una oración que lo dice.
> - **Errores:** `422` para un request inválido (campaña u objetivo desconocidos, `cultivo_anterior` fuera de los 11 cultivos o de `ninguno`/`barbecho`/`sin_cultivo`/`null`, rangos del What-If, campos extra, o **campaña que no corresponde a la fecha** según la regla de §4.1: el backend también la rechaza, además del bloqueo del frontend). `503` si un provider no tiene datos.

---

## 6. Flujo del Usuario (User Journey)
El proceso que cumple el productor o asesor al utilizar la herramienta sigue cuatro pasos ágiles y accionables:

1. **Selección del lote y detección satelital automática:** Entra a la web, activa las capas visuales de la NASA (Humedad SMAP o Verdor NDVI) y marca su lote en el mapa. El sistema consulta automáticamente a la NASA y al mapa edáfico, mostrándole en pantalla el estado hídrico y térmico actual de su campo sin que tenga que tipear datos complejos.
2. **Configuración de contexto y objetivo:** Indica de qué cultivo viene el lote (ej. *"Vengo de Soja de 1ra"*), qué campaña va a planificar (*"Campaña de Verano"*) y cuál es su prioridad (*"Resiliencia hidroclimática"*, *"Conservación del suelo"* o *"Equilibrio"*).
3. **Recepción de la decisión explicada:** El dashboard ejecuta el modelo híbrido y le devuelve el ranking de cultivos y la secuencia de rotación sugerida con una explicación transparente:
   > *"Recomendación: Sembrar Sorgo o Girasol (y evitar repetir Soja o Maíz Temprano). La telemetría de la NASA muestra una saturación radicular del 34% y una anomalía de lluvias de -24%. El Sorgo presenta un 87% de aptitud integral: resiste el estrés hídrico proyectado y aporta el carbono y rastrojo que tu lote necesita después de la Soja."*
4. **Simulación "What-If" (Opcional):** El productor puede mover un control deslizante (ej. *"¿Qué cambia si llueven 80 mm antes de la siembra?"*) para ver en tiempo real cómo se reacomoda el ranking y planificar su compra de insumos con anticipación.

---

## 7. Guía Rápida de Instalación (Setup del Equipo)

Pasos para dejar el entorno local listo después de clonar o hacer `git pull` del repositorio. No se requiere ningún motor de base de datos externo.

### 7.1. Estructura del Repositorio
```text
shark-attack-nasa/
├── backend/
│   ├── ml/                # Entrenamiento (train_baseline.py), predictor y TASKS_ML.md
│   ├── providers/         # Clientes HTTP (NASA POWER API, NASA SRTM / OpenTopoData, ISRIC SoilGrids API)
│   ├── routers/           # Endpoints FastAPI (/api/v1/simulate)
│   ├── services/          # Lógica de negocio y matriz de rotación agronómica
│   ├── requirements.txt   # Dependencias de Python
│   └── TASKS_BACKEND.md   # Tablero y protocolo de tareas atómicas de Backend
├── frontend/              # Aplicación React + TypeScript + Vite + Leaflet
│   ├── SKILLS_FRONTEND.md # Skill y guía de diseño UX/UI agrario, glosario y convenciones de Frontend
│   └── TASKS_FRONTEND.md  # Tablero y protocolo de tareas atómicas de Frontend
└── CONTEXT.md             # Documentación de arquitectura, contratos y metodología
```

### 7.2. Levantar el Frontend (`React + TypeScript + Vite`)
```bash
cd frontend
npm install
npm run dev
```
- El servidor de desarrollo quedará corriendo en `http://localhost:5173`.

### 7.3. Configurar y Levantar el Backend (`Python + FastAPI`)
```bash
cd backend

# 1. Crear el entorno virtual
python -m venv .venv

# 2. Activar el entorno virtual
# En Windows (PowerShell):
.venv\Scripts\Activate.ps1
# En Windows (CMD):
.venv\Scripts\activate.bat
# En Linux / macOS:
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Iniciar el servidor FastAPI
uvicorn main:app --reload --port 8000
```
- El backend responderá en `http://localhost:8000` (y la documentación interactiva Swagger UI en `http://localhost:8000/docs`).

---

## 8. Metodología de Desarrollo con Agentes

El proyecto se desarrolla en equipo utilizando **Spec-Driven Development (SDD) con Tareas Atómicas** divididas en **3 tracks independientes** para evitar conflictos en Git (`merge conflicts`):
- **Track Backend:** [`backend/TASKS_BACKEND.md`](./backend/TASKS_BACKEND.md)
- **Track ML & Agronomía:** [`backend/ml/TASKS_ML.md`](./backend/ml/TASKS_ML.md)
- **Track Frontend & GIS UI:** [`frontend/TASKS_FRONTEND.md`](./frontend/TASKS_FRONTEND.md) y [`frontend/SKILLS_FRONTEND.md`](./frontend/SKILLS_FRONTEND.md)

### 8.1. Flujo de Trabajo de cada Desarrollador con su Agente
Cada archivo `TASKS_*.md` comienza vacío, sin tareas ni bocetos pre-impuestos. Al iniciar cada bloque de trabajo:
1. **Propuesta Inicial:** El desarrollador conversa con su agente sobre qué funcionalidad o componente de su área quiere construir a partir de la arquitectura y contratos de este documento.
2. **Entrevista de Definición (Obligatoria):** Antes de terminar de especificar la tarea o escribir código, el agente **debe hacerle preguntas al desarrollador** para definir todas las decisiones que hayan quedado en el aire (casos borde, umbrales, UX, validaciones, fallbacks).
3. **Especificación Atómica:** Con las respuestas del desarrollador, el agente redacta la especificación de la **Tarea Atómica** en su archivo `TASKS_*.md` correspondiente.
4. **Implementación y Verificación (*Definition of Done*):** Una vez aprobada la especificación por el desarrollador, el agente implementa el código respetando su **Scope Exclusivo de Carpetas** y ejecuta el comando de verificación antes de marcar la tarea como completada (`[x]`).

### 8.2. Skill de Frontend y Guía de UX Agraria (`frontend/SKILLS_FRONTEND.md`)
Para garantizar una interfaz limpia, intuitiva y pensada para el productor rural (sin saturación visual ni siglas científicas crudas), el Track de Frontend cuenta con la skill dedicada [`frontend/SKILLS_FRONTEND.md`](./frontend/SKILLS_FRONTEND.md). Todo agente que trabaje en `frontend/` debe leerla y cumplir sus reglas:
- **Estética *Analogue-Modern Field Journal*:** Uso exclusivo de variables CSS (`src/index.css` y `src/theme/mapColors.ts`), tipografía editorial `Newsreader` para títulos y `Plus Jakarta Sans` para lectura ágil, con semántica fija de colores (azul `#4A7B9D` = agua/lluvia, naranja `#F05D23` = calor/suelo, verde `#4B5B2D` = decisión/acción, sobre fondo cálido `#FFF5E0`).
- **Principio *Producer-First* (Cero Jerga Técnica):** Traducción obligatoria de todos los acrónimos de la NASA y edafología al lenguaje cotidiano del productor (ej. `GWETROOT` $\rightarrow$ *"Agua en las raíces"*, `MODIS NDVI` $\rightarrow$ *"Verdor del cultivo"*, `S_hidroclimatico` $\rightarrow$ *"Aptitud frente al agua y el clima"*).
- **Divulgación Progresiva y Anti-Clutter:** Una pregunta respondida en `< 5 segundos` por pestaña (`Planificación de campaña`, `Info general`, `Información histórica` con línea de tiempo de 10 años sincronizada en vivo con el mapa, y `Chat`), mostrando primero la conclusión y dejando el desglose técnico bajo controles *"Ver detalle"*.



