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
- **Base de Datos y Auth:** Supabase (PostgreSQL + Supabase Auth + Row Level Security) conectado desde FastAPI mediante `supabase-py` (`backend/sql/schema.sql`).
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
| **Entrenamiento del ML** | Modelo entrenado sobre curvas agroecológicas **FAO GAEZ v4 / FAO-56** + series históricas de **NASA POWER** y topografía **SRTM** en puntos testigo. | Re-entrenamiento continuo con **rindes históricos departamentales (SIIA/MAGyP o USDA NASS QuickStats)** y feedback real de cosecha. |
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
- **Modo de consumo (Latencia 0 ms):** Para no penalizar el tiempo de respuesta con descargas raster pesadas en vivo, los umbrales fenológicos y curvas de respuesta de **FAO GAEZ v4 y FAO-56** se integran de forma tabulada en el script de entrenamiento (`backend/ml/train_baseline.py`) y en el motor agronómico (`backend/services/rotation_matrix.py`).

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
- **Ambas campañas están soportadas con la misma lógica** (backend, ML y matriz de rotación). Lo que cambia según la fecha es **cuál está habilitada en la interfaz**: el frontend **bloquea el botón de la campaña que no corresponde a la fecha actual**, porque el modelo evalúa con los datos satelitales y climáticos del día de hoy ($t \approx$ hoy) y con la climatología de los 90 días siguientes. Cuando sea efectivamente época de invierno, se habilita `invierno` y se bloquea `verano`, sin ningún cambio de lógica.
- **Regla de campaña vigente:** es la misma que se usa en el entrenamiento (`generate_dataset.py`): se mira el **mes central de la ventana futura** (hoy + 45 días). Si cae entre **abril y septiembre**, la campaña habilitada es `invierno`; si no, `verano`. En la práctica, `invierno` queda habilitada aproximadamente entre mediados de febrero y mediados de agosto. Frontend y ML deben usar exactamente esta regla.
- **Alcance de la Recomendación (`secuencia_sugerida`):** El sistema recomienda el cultivo (o terna alternativa) para la **campaña habilitada en curso**, contrastándolo contra alternativas defensivas y contra la **estrategia testigo (repetir el cultivo anterior / monocultivo)** según el estado hídrico y edáfico actual.

### 4.2. Modelo de Machine Learning (`HistGradientBoostingRegressor` / `RandomForestRegressor`) y Datos de Entrenamiento
- **Qué predice:** El **Puntaje de Aptitud Hidroclimática y Topográfica ($S_{\text{hidroclimatico}}$, de 0 a 100)** de cada cultivo candidato frente a la telemetría satelital de la NASA (`GWETROOT`, `GWETTOP`, `PRECTOTCORR`, `T2M_MAX`, `T2M_MIN`, `EVPTRNS`), la pendiente del terreno (`SRTM`) y la textura del suelo (`SoilGrids`).
- **Por qué ensambles de árboles:** Capturan interacciones no lineales críticas (ej. caída abrupta de aptitud cuando `T2M_MAX > 34°C` coincide con `GWETROOT < 0.30`, o pérdida de eficiencia de lluvia cuando `pendiente_terreno_pct > 2.0%` en suelos con baja infiltración), no requieren GPU, corren en `< 15 ms` en producción y proveen explicabilidad (`feature_importances_`).
- **Con qué datos se entrena (Estrategia en 2 Fases):**
  1. **Fase 1 (Hackathon — Script `train_baseline.py`):** Se construye un dataset de entrenamiento combinando:
     - **Distribuciones climáticas e hidrológicas reales** extraídas de series históricas diarias de 20 años de **NASA POWER (SMAP/GLDAS/IMERG)**, perfiles de pendiente de **NASA SRTM** y texturas de **SoilGrids** en puntos representativos de la región agrícola.
     - **Funciones de respuesta ecofisiológica de FAO GAEZ v4 y FAO-56:** Los umbrales térmicos (óptimos, corte por calor y helada), coeficientes de cultivo ($K_c$), sensibilidad al déficit hídrico ($K_y$) y penalizaciones por pendiente/drenaje de la FAO se utilizan para etiquetar el target ($S_{\text{hidroclimatico}}$) sobre los escenarios históricos reales. Esto garantiza un modelo físicamente consistente, sin sobreajuste y listo en las 48 hs.
  2. **Fase 2 (Producto Comercial — Pipeline de Datos Reales):** Entrenamiento supervisado cruzando la serie histórica de **rindes departamentales reales (SIIA / MAGyP en Argentina o USDA NASS QuickStats en EE.UU.)** con las anomalías de **NASA POWER**, **ERA5**, **SMAP**, **SRTM** y **MODIS/Sentinel-2 NDVI** de cada campaña.

### 4.3. Features de Entrada ($X$) del Modelo ML y Esquema de Doble Ventana Temporal (`[-89d, t]` vs. `[t+1, +90d]`)
Todas las features se calculan de forma determinística a partir de las respuestas de **NASA POWER**, **NASA SRTM (OpenTopoData)** e **ISRIC SoilGrids**, separando rigurosamente el **estado hídrico heredado en el suelo** (ventana pasada `[t - 89, t]`) de los **riesgos meteorológicos a los que se expondrá el cultivo tras la siembra** (ventana futura `[t + 1, t + 90]`):

- **A. Ventana Pasada `[t - 89, t]` (Estado Hídrico y Memoria del Suelo al día de evaluación $t$):**
  1. `gwetroot_saturacion_pct`: Índice de humedad en zona radicular en el día $t$ (`GWETROOT * 100`, de NASA POWER / SMAP-GLDAS, o valor simulado en modo *What-If*).
  2. `gwettop_saturacion_pct`: Humedad superficial (0–5 cm, `GWETTOP * 100`) en el día $t$ para viabilidad de emergencia en siembra y detección de desacople con la raíz.
  3. `tendencia_humedad_15d_pct`: Variación neta de humedad superficial/radicular en los últimos 15 días válidos (`[t - 14, t]`, mide la velocidad de secado o recarga reciente del perfil).
  4. `anomalia_lluvia_90d_pct`: Desvío porcentual de la lluvia acumulada (`PRECTOTCORR`) de los últimos 90 días (`[t - 89, t]`) respecto a la climatología histórica de 20 años de NASA POWER en esa coordenada.
  8. `indice_aridez_evaporativa`: Relación entre precipitación acumulada y demanda evaporativa (`PRECTOTCORR / EVPTRNS`) en los 90 días previos (`[t - 89, t]`) que explica cómo llegó el perfil hídrico al día $t$.

- **B. Ventana Futura `[t + 1, t + 90]` (Riesgos Meteorológicos durante el Ciclo del Cultivo):**
  *(En el dataset histórico `generate_dataset.py` se extraen de los 90 días posteriores a la fecha de decisión `[t + 1, t + 90]`; en inferencia online en vivo se estiman mediante la climatología histórica de esos próximos 90 días del calendario `[doy + 1 .. doy + 90]` en la coordenada).*
  5. `frecuencia_tormentas_extremas`: Cantidad de eventos de lluvia torrencial (`PRECTOTCORR > 50 mm/día`, derivado de GPM/IMERG/POWER) en la ventana futura de 90 días (`[t + 1, t + 90]`) — indicador de riesgo de escorrentía y erosión durante el ciclo.
  6. `frecuencia_estres_termico`: Días con `T2M_MAX > 34°C` durante la ventana futura de 90 días (`[t + 1, t + 90]`, golpes de calor en el ciclo del cultivo).
  7. `frecuencia_riesgo_helada`: Días con `T2M_MIN < 2°C` durante la ventana futura de 90 días (`[t + 1, t + 90]`, riesgo de helada en el ciclo del cultivo).

- **C. Variables Topográficas, Edáficas y de Cultivo:**
  9. `pendiente_terreno_pct`: Pendiente topográfica local (%) obtenida de **NASA SRTM (30m)** (modifica la infiltración efectiva del agua de lluvia y el riesgo de erosión).
  10. `elevacion_m`: Altitud sobre el nivel del mar (msnm) vía **NASA SRTM / NASA POWER**.
  11. `textura_arcilla_pct`: Porcentaje de arcilla del lote vía **ISRIC SoilGrids** (regula la capacidad de retención hídrica y el drenaje).
  12. `cultivo_candidato`: Identificador/codificación del cultivo a evaluar dentro de la campaña seleccionada.

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
   - El sistema reporta la frecuencia estadística histórica de golpes de calor y heladas en esa coordenada. Para evaluar qué pasaría si la campaña entrante resulta atípicamente seca (*tipo La Niña*) o húmeda (*tipo El Niño*), **no se adivina el pronóstico estacional**, sino que se proveen **Presets Climáticos en el simulador *What-If*** para que el productor o su agrónomo evalúen la sensibilidad de cada rotación bajo cada escenario.

### 4.5. Los 2 Pilares del Puntaje, Viabilidad de Mercado y Fórmula Dinámica
Para mantener la transparencia matemática, el sistema separa el cálculo en **2 pilares cuantitativos** complementados con metadatos de riesgo, mercado y validación local:

1. **$S_{\text{hidroclimatico}}$ (Clima + Agua + Topografía Hídrica — Calculado 100% por el Modelo de ML):** Evalúa qué tan viable es el cultivo según la reserva radicular (`GWETROOT`), el secado reciente, la anomalía de lluvias (`PRECTOTCORR`), el estrés térmico (`T2M_MAX`/`T2M_MIN`), la demanda evaporativa (`EVPTRNS`) y la eficiencia de infiltración según pendiente (`SRTM`) y arcilla (`SoilGrids`).
2. **$S_{\text{suelo}}$ (Salud del Suelo, Cobertura y Control de Erosión — Calculado por Matriz Agronómica + SoilGrids + SRTM):** Evalúa la transición `cultivo_anterior -> cultivo_candidato` (balance de Carbono/Nitrógeno, aporte de rastrojo, reducción de meses de suelo desnudo y corte de ciclo de plagas) ajustada por el nivel actual de Carbono Orgánico (`soc`) y penalizando doblemente los cultivos de baja cobertura en lotes con pendiente elevada (`pendiente_terreno_pct` de SRTM).

$$\text{Score Final} = w_{\text{clima}} \cdot S_{\text{hidroclimatico}} + w_{\text{suelo}} \cdot S_{\text{suelo}}$$

| `objetivo_productor` | Peso Hidroclimático ($w_{\text{clima}}$) | Peso Suelo ($w_{\text{suelo}}$) | Enfoque de la Recomendación |
| :--- | :---: | :---: | :--- |
| `resiliencia_hidroclimatica` | **`0.75`** | `0.25` | Prioriza asegurar el cultivo frente a sequías, baja humedad radicular o golpes de calor. |
| `conservacion_suelo` | `0.30` | **`0.70`** | Prioriza regenerar carbono, proteger pendientes contra la erosión, aportar rastrojo y cortar el monocultivo. |
| `equilibrio` | `0.50` | `0.50` | Balance 50/50 entre seguridad hídrica/climática y sustentabilidad del suelo. |

### 4.6. Flujo de Ejecución: Offline (Entrenamiento) vs. Online (Inferencia en Producción)
- **Fase Offline (Pre-deploy):** Se ejecuta el script `train_baseline.py` con series históricas de NASA POWER + topografía SRTM + curvas FAO GAEZ/FAO-56 $\rightarrow$ genera el archivo `modelo_agro.joblib` incluido en el repositorio del backend.
- **Fase Online (`POST /api/v1/simulate` en `< 1.5s`):**
  1. FastAPI recibe `coordenadas`, `campana`, `cultivo_anterior`, `objetivo_productor` y (opcionalmente) `simulacion_what_if`.
  2. Consulta en paralelo **NASA POWER API** (filtrando lags `-999.0`), **OpenTopoData SRTM API** (con fallback a la elevación de NASA POWER) e **ISRIC SoilGrids API**.
  3. Calcula las 12 features $X$, evalúa las alertas de anomalías físicas en curso (sin forzar predicciones sin sustento) y ejecuta `modelo_agro.predict(X)` en memoria para obtener $S_{\text{hidroclimatico}}$.
  4. Cruza cada cultivo con la **Matriz de Rotación y Pendiente** para obtener $S_{\text{suelo}}$, aplica los pesos ($w_{\text{clima}}, w_{\text{suelo}}$) e incluye las notas de incertidumbre y validación agronómica local requeridas por el challenge.

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
    "variacion_lluvia_esperada_pct": 0 // opcional (-50 a +50): ej. -25 para simular escenario seco, +25 para húmedo
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
    "perfil_mercado": "Bajo costo de implantación y alta estabilidad defensiva; grano comercializable como forraje o exportación.",
    "factores_clave_ml": [
      "Baja saturación hídrica en zona radicular detectada por NASA (34%)",
      "Pendiente de 1.8% (SRTM) requiere rastrojo de gramínea tras Soja para frenar escorrentía",
      "Anomalía de lluvias de -24.2% en los últimos 90 días"
    ],
    "explicacion": "Recomendación: Sembrar Sorgo (o Maíz Tardío precedido por Vicia). Detectamos vía satélite una reserva hídrica ajustada (34% de saturación radicular), un déficit de lluvias del 24% y una pendiente del 1.8% (SRTM). A diferencia del Maíz Temprano (riesgo crítico en floración) o repetir Soja (degradación de carbono y riesgo de erosión por suelo desnudo), el Sorgo ofrece un 86% de aptitud hidroclimática y un 95% de beneficio edáfico para proteger y recomponer la estructura del lote."
  },
  "ranking_cultivos": [
    { "cultivo": "sorgo", "score_final": 90.5, "riesgo": "bajo" },
    { "cultivo": "maiz_tardio", "score_final": 82.5, "riesgo": "medio" },
    { "cultivo": "girasol", "score_final": 72.0, "riesgo": "bajo" },
    { "cultivo": "maiz_temprano", "score_final": 64.0, "riesgo": "critico" },
    { "cultivo": "soja_primera", "score_final": 31.0, "riesgo": "alto" }
  ],
  "validacion_local_requerida": {
    "nota_resolucion_satelital": "Humedad satelital (NASA POWER/SMAP) estimada a escala regional (~9 km), topografía SRTM a 30 m y suelo a 250 m.",
    "brechas_informacion": [
      "No mide profundidad de napa freática local ni compactación subsuperficial (piso de arado)",
      "No reemplaza el pronóstico meteorológico estacional ni el análisis químico de laboratorio (Fósforo/Nitrógeno)"
    ],
    "recomendacion_experto": "Validar agua útil real con muestreo de barreno a 1 metro y consultar al ingeniero agrónomo local antes de definir la densidad de siembra."
  }
}
```

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

Pasos para dejar el entorno local listo después de clonar o hacer `git pull` del repositorio. El backend se conecta a **Supabase** (PostgreSQL + Auth) mediante variables de entorno.

### 7.1. Estructura del Repositorio
```text
shark-attack-nasa/
├── backend/
│   ├── ml/                # Entrenamiento (train_baseline.py), predictor y TASKS_ML.md
│   ├── providers/         # Clientes externos (supabase_client.py, NASA POWER, SRTM, SoilGrids)
│   ├── routers/           # Endpoints FastAPI (auth.py, fields.py, campaigns.py, simulación)
│   ├── services/          # Lógica de negocio y matriz de rotación agronómica
│   ├── sql/               # Esquema PostgreSQL y políticas RLS para Supabase (schema.sql)
│   ├── config.py          # Configuración con pydantic-settings (.env)
│   ├── main.py            # Entrypoint FastAPI, CORS, /health y registro de routers
│   ├── schemas.py         # Modelos Pydantic de request/response
│   ├── .env.example       # Plantilla de variables de entorno (SUPABASE_URL, SUPABASE_KEY)
│   ├── requirements.txt   # Dependencias de Python
│   └── TASKS_BACKEND.md   # Tablero y protocolo de tareas atómicas de Backend
├── frontend/              # Aplicación React + TypeScript + Vite + Leaflet
│   ├── SKILLS_FRONTEND.md # Skill y guía de diseño UX/UI agrario, glosario y convenciones de Frontend
│   └── TASKS_FRONTEND.md  # Tablero y protocolo de tareas atómicas de Frontend
└── CONTEXT.md             # Documentación de arquitectura, contratos y metodología
```

### 7.2. Configurar Base de Datos y Auth en Supabase
1. Crear un proyecto en **Supabase** (categoría *B2B SaaS application*) y copiar `SUPABASE_URL` (URL base del proyecto, sin `/rest/v1/`) y `SUPABASE_KEY` (anon/publishable key).
2. Copiar `backend/.env.example` a `backend/.env` y completar las credenciales.
   - *Estado actual del entorno:* Proyecto Supabase creado (`https://kjiddadksvosdaoyapfu.supabase.co`) y archivo local `backend/.env` configurado con `SUPABASE_URL`, `SUPABASE_KEY` y `CORS_ORIGINS`.
3. Ejecutar el script [`backend/sql/schema.sql`](./backend/sql/schema.sql) en el **SQL Editor** de Supabase para crear las tablas `profiles`, `fields` y `campaigns` (incluye trigger de alta automática de perfil y políticas **RLS** por usuario).
4. **Endpoints disponibles en Backend (`/docs`):**
   - **Auth (`/api/v1/auth`):** `POST /register`, `POST /login`, `GET /me` (Bearer JWT).
   - **Campos (`/api/v1/fields`):** `GET /`, `POST /`, `GET /{field_id}`, `PATCH /{field_id}`, `DELETE /{field_id}`.
   - **Campañas e Historial (`/api/v1/fields/{field_id}/campaigns`):** `GET /`, `POST /`, `PATCH /{campaign_id}`, `DELETE /{campaign_id}` (guarda `campana`, `cultivo`, `fecha_inicio`, `fecha_fin`, `rinde_kg_ha`, `resultado_notas` y `simulacion_json`).
   - **Healthcheck:** `GET /health`.

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

# 4. Iniciar el servidor FastAPI (una vez creado main.py)
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



