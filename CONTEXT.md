# CONTEXTO DEL PROYECTO: Shark Attack

## 1. Visión General (Elevator Pitch)
**Shark Attack** es una plataforma AgTech de soporte a la toma de decisiones agronómicas enfocada en la adaptación climática, eficiencia hídrica y planificación de rotaciones inteligentes. Nace en el **NASA Space Apps Challenge 2026** (*Challenge: Field Shift: Adapting Farms with NASA Data*) con una arquitectura pensada desde el día uno para evolucionar hacia un **producto comercial escalable (SaaS)**.

El sistema asiste al productor y al asesor agronómico para definir **estrategias de rotación y elección de cultivos por campaña (Invierno / Verano)** cruzando tres dimensiones:
- **Clima e Hidrología Satelital (Datos NASA):** Índice de saturación hídrica en zona radicular (`GWETROOT`) y superficial (`GWETTOP`), anomalías de precipitación, estrés térmico y demanda evaporativa, detectados automáticamente al seleccionar el lote en el mapa.
- **Edafología y Salud del Suelo (NASA + Datos de Suelo):** Propiedades físicas y químicas del lote (textura arcilla/limo/arena, carbono orgánico, retención hídrica), impacto del cultivo antecesor (balance de C/N) y cobertura vegetal histórica (`NDVI`).
- **Simulación Interactiva ("What-If"):** Capacidad de evaluar escenarios futuros (ej. *"¿Qué pasa con mi rotación si la campaña viene un 20% más seca?"*) ajustando prioridades agronómicas.

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
| **Ingesta Climática NASA** | Consulta síncrona a **NASA POWER API** (con caché en memoria/SQLite y filtro de valores `-999`). | Pipeline asíncrono (Celery/Redis + PostGIS) que pre-ingesta **NASA POWER + SMAP L4 + IMERG** diariamente. |
| **Datos de Suelo** | **ISRIC SoilGrids API** (o fallback regional pre-cacheado de la Pampa Húmeda) para textura y carbono. | Integración con cartas de suelo locales (ej. GeoINTA en Argentina / SSURGO) + carga de análisis de laboratorio del productor. |
| **Imágenes Satelitales** | Capas globales **NASA GIBS** (MODIS/SMAP a 250m–9km) vía WMTS directo en el mapa. | Recorte por lote en alta resolución (10m–30m) usando **NASA HLS (Landsat + Sentinel-2)** vía STAC/COG para ver variabilidad intralote (ambientación). |
| **Entrenamiento del ML** | Modelo entrenado sobre curvas agroclimáticas **FAO-56** + series históricas de NASA POWER en puntos testigo. | Re-entrenamiento continuo con **rindes históricos departamentales (SIIA/MAGyP)** y feedback real de cosecha de los usuarios. |
| **Unidad de Recomendación** | Cultivos filtrados por campaña (`invierno` vs `verano`, diferenciando fecha temprana/tardía) o secuencias anuales. | Planificador plurianual (rotación a 3–5 años) con balance acumulado de Carbono, Nitrógeno, Fósforo y huella hídrica. |

---

## 3. Catálogo de APIs y Fuentes de Datos (NASA & Edafología)

### 3.1. APIs Core para el Backend (Datos numéricos por `lat`/`lon`)

#### A. NASA POWER API (Prediction Of Worldwide Energy Resources) — *[Prioridad Alta - Fase 1 y 2]*
API RESTful abierta (no requiere API Key) optimizada para aplicaciones agroclimáticas (`community=AG`). Devuelve JSON directo por coordenadas con series diarias, mensuales y climatologías históricas.
- **Endpoint base:** `https://power.larc.nasa.gov/api/temporal/{daily|monthly|climatology}/point`
- **Parámetros clave:**
  - `PRECTOTCORR`: Precipitación total corregida (mm/día) — cálculo de oferta hídrica acumulada y anomalías.
  - `GWETROOT`: **Fracción de saturación hídrica en la zona radicular (`0.0` a `1.0`, hasta 1m)** asimilada de modelos terrestres y SMAP. *Nota agronómica:* Al ser una fracción de saturación relativa al tipo de suelo y no humedad volumétrica cruda, evita sesgos entre suelos arenosos y arcillosos.
  - `GWETTOP`: Fracción de humedad superficial (0–5 cm) — determina ventana óptima de siembra.
  - `GWETPROF`: Humedad total del perfil del suelo.
  - `T2M`, `T2M_MAX`, `T2M_MIN`: Temperatura a 2 metros (media, máxima y mínima en °C) — detección de golpes de calor en período crítico y riesgo de heladas.
  - `ALLSKY_SFC_SW_DWN` / `EVPTRNS`: Radiación solar incidente y flujo de evapotranspiración.
- **Regla técnica obligatoria (Manejo del lag `-999`):** Los datos satelitales de NASA POWER (especialmente `GWETROOT`) tienen una latencia de procesamiento de **3 a 7 días**. Los últimos días del calendario suelen devolver `-999.0`. El cliente HTTP del backend **siempre debe pedir una ventana de los últimos 30 días** y tomar el último valor válido (`!= -999.0`).

#### B. ISRIC SoilGrids API (Complemento Edáfico para datos NASA) — *[Prioridad Alta - Fase 1 y 2]*
El desafío de la NASA pide cruzar observaciones satelitales con información local del suelo. SoilGrids provee propiedades edáficas globales a 250m de resolución vía REST JSON por `lat`/`lon`.
- **Endpoint base:** `https://rest.isric.org/soilgrids/v2.0/properties/query`
- **Variables clave:** `clay` (arcilla), `sand` (arena), `silt` (limo), `soc` (carbono orgánico del suelo) y `phh2o` (pH). Permite ajustar la retención hídrica real y el score de salud del suelo.

#### C. NASA AppEEARS API (Application for Extracting and Exploring Analysis Ready Samples) — *[Prioridad Media - Fase 2 / Pre-caché]*
API de LP DAAC que extrae series históricas de sensores como **MODIS**, **SMAP**, **ECOSTRESS** y **HLS**.
- **Particularidad técnica:** Requiere token de *NASA Earthdata Login* y opera mediante colas de trabajo asíncronas (`jobs`). En el MVP se usa solo para descargar datasets de entrenamiento offline; en la **Fase 2 (Producto Comercial)** se integra mediante workers en background para monitorear lotes suscriptos.
- **Productos destacados:** `MOD13Q1` (NDVI cada 16 días a 250m), `ECO3ETPTJPL` (Evapotranspiración ECOSTRESS a 70m), `SPL4SMGP` (SMAP Root Zone Soil Moisture a 9km).

---

### 3.2. APIs de Imágenes Satelitales y Capas Visuales para el Frontend (Mapas)

#### D. NASA GIBS (Global Imagery Browse Services) / Worldview — *[Prioridad Alta UI/UX - Fase 1]*
Servicio de teselas (WMTS / WMS / XYZ tiles) que permite superponer capas satelitales de la NASA directamente en **Leaflet** o **Mapbox** en tiempo real, sin procesar rasters en el backend ni requerir API Keys.
- **Endpoint WMTS base:** `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{Layer}/default/{Time}/{TileMatrixSet}/{z}/{y}/{x}.{format}`
- **Capas recomendadas para el Frontend:**
  - `MODIS_Terra_CorrectedReflectance_TrueColor` o `VIIRS_SNPP_CorrectedReflectance_TrueColor`: Imagen satelital real actualizada diariamente.
  - `SMAP_L4_Analyzed_Root_Zone_Soil_Moisture`: Mapa de calor global de humedad en zona radicular.
  - `MODIS_Terra_NDVI_8Day`: Capa visual de índice de vegetación (biomasa activa).
  - `MODIS_Terra_Land_Surface_Temp_Day`: Temperatura superficial terrestre (LST) para visualizar estrés térmico regional.
  - `IMERG_Precipitation_Rate`: Tasa de precipitación derivada de la misión **GPM**.

#### E. NASA Earthdata CMR-STAC / Harmonized Landsat Sentinel-2 (HLS) — *[Fase 2: Escala de Lote]*
API basada en el estándar **STAC** (`https://cmr.earthdata.nasa.gov/stac/LPCLOUD`) para consultar recortes ópticos multiespectrales de **30 metros de resolución** (Landsat 8/9 + Sentinel-2). Base para ofrecer lectura de NDVI/NDWI intralote en la versión comercial.

---

### 3.3. Otras Fuentes del Ecosistema NASA (Referencia y Validación)
- **Crop-CASMA (NASA + USDA):** Referencia metodológica para anomalías de humedad de suelo (SMAP 1 km) y condición vegetativa.
- **NASA GPM (IMERG) & GRACE-FO:** Medición de tormentas en tiempo casi real y variaciones de agua subterránea/acuíferos a largo plazo.
- **NASA Giovanni:** Herramienta de análisis geofísico para validar correlaciones históricas durante el desarrollo.

---

## 4. Arquitectura de Machine Learning y Motor de Decisión

El motor de recomendación está diseñado bajo una interfaz común (`RecommendationEngine`) que combina **Machine Learning basado en Árboles (`scikit-learn`)** con una **Matriz de Transición Agronómica y Scoring Multicriterio (MCDA)**.

### 4.1.Separación por Campaña y Secuencias de Rotación
Para evitar el error agronómico de comparar cultivos de invierno contra cultivos de verano en una misma fecha de siembra, el motor opera sobre **ventanas de campaña explícitas**:
- **Campaña Fina (`invierno`):** `trigo`, `cebada`, `vicia_cobertura` (leguminosa de servicio), `avena_cobertura`, `camelina`.
- **Campaña Gruesa (`verano`):** `maiz_temprano`, `maiz_tardio`, `soja_primera`, `soja_segunda` (post-fina), `girasol`, `sorgo`.
- **Secuencia Recomendada:** Además de puntuar los cultivos de la campaña seleccionada, el sistema sugiere la **secuencia anual óptima (Invierno $\rightarrow$ Verano)** (ej. *Vicia de cobertura $\rightarrow$ Maíz Tardío* para recuperar nitrógeno y escapar al estrés hídrico de enero).

### 4.2. Modelo de Machine Learning (`HistGradientBoostingRegressor` / `RandomForestRegressor`)
- **Qué predice:** El **Puntaje de Aptitud Hidroclimática ($S_{\text{hidroclimatico}}$, de 0 a 100)** de cada cultivo candidato frente a las variables de clima y agua de la NASA (`GWETROOT`, `PRECTOTCORR`, `T2M_MAX`, `T2M_MIN`, `EVPTRNS`) y la textura del suelo.
- **Por qué ensambles de árboles:** Capturan umbrales biológicos no lineales (ej. caída abrupta de rinde cuando `T2M_MAX > 35°C` coincide con `GWETROOT < 0.30`), no requieren GPU, corren en `< 15 ms` en producción y proveen explicabilidad por variable (`feature_importances_` / valores SHAP).
- **Estrategia de Entrenamiento en 2 Fases:**
  1. **Fase 1 (Hackathon — Script `train_baseline.py`):** Generación de un dataset calibrado combinando las curvas oficiales de respuesta al agua y temperatura de la **FAO (FAO-56)** con distribuciones climáticas reales descargadas de **NASA POWER** en puntos representativos de la región pampeana. Garantiza un modelo funcional, coherente y sin cuellos de botella de limpieza de datos en las 48 hs.
  2. **Fase 2 (Producto Comercial — Pipeline de Datos Reales):** Entrenamiento supervisado sobre el dataset histórico de **Estimaciones Agrícolas (SIIA / MAGyP)** cruzado por departamento y campaña con las series diarias de **NASA POWER**, **SMAP** y **MODIS NDVI**, incorporando ajuste fino por lote con datos propios del productor.

### 4.3. Features de Entrada ($X$) del Modelo ML
1. `gwetroot_saturacion_pct`: Índice de humedad radicular actual (`GWETROOT * 100` de NASA POWER, o valor simulado por el usuario en modo *What-If*).
2. `gwettop_saturacion_pct`: Humedad superficial (0–5 cm) para viabilidad de emergencia en siembra.
3. `anomalia_lluvia_90d_pct`: Desvío porcentual de la lluvia acumulada (`PRECTOTCORR`) de los últimos 90 días respecto a la climatología histórica de 20 años de la NASA en esa coordenada.
4. `frecuencia_estres_termico`: Días esperados con `T2M_MAX > 34°C` durante la ventana crítica del cultivo.
5. `frecuencia_riesgo_helada`: Días esperados con `T2M_MIN < 2°C`.
6. `indice_aridez_evaporativa`: Relación entre precipitación y demanda evaporativa (`PRECTOTCORR / EVPTRNS`).
7. `textura_arcilla_pct`: Porcentaje de arcilla del lote (vía SoilGrids / perfil regional) para ajustar retención de agua.
8. `cultivo_candidato`: Cultivo a evaluar dentro de la campaña seleccionada.

### 4.4. Los 2 Pilares del Puntaje y Fórmula Dinámica
Para evitar redundancias, el sistema separa el cálculo en **2 únicos pilares** claramente diferenciados:

1. **$S_{\text{hidroclimatico}}$ (Clima + Agua — Calculado 100% por el Modelo de ML):** Evalúa qué tan viable es el cultivo según la oferta de agua en el perfil (`GWETROOT`), la anomalía de lluvias (`PRECTOTCORR`) y el estrés térmico (`T2M_MAX`/`T2M_MIN`) reportados por la NASA.
2. **$S_{\text{suelo}}$ (Salud del Suelo y Rotación — Calculado por Matriz Agronómica + SoilGrids):** Tabla determinística de reglas agronómicas que evalúa la transición `cultivo_anterior -> cultivo_candidato` (balance de Carbono/Nitrógeno, aporte de rastrojo y corte de ciclo de plagas) ajustada por el nivel actual de Carbono Orgánico (`soc`) del lote. Por ejemplo, penaliza el monocultivo `soja -> soja` (`20 pts`) y premia rotaciones con gramíneas como `soja -> sorgo` o `soja -> maiz` (`90–95 pts`).

$$\text{Score Final} = w_{\text{clima}} \cdot S_{\text{hidroclimatico}} + w_{\text{suelo}} \cdot S_{\text{suelo}}$$

| `objetivo_productor` | Peso Hidroclimático ($w_{\text{clima}}$) | Peso Suelo ($w_{\text{suelo}}$) | Enfoque de la Recomendación |
| :--- | :---: | :---: | :--- |
| `resiliencia_hidroclimatica` | **`0.75`** | `0.25` | Prioriza asegurar el cultivo frente a sequías, baja humedad radicular o golpes de calor. |
| `conservacion_suelo` | `0.30` | **`0.70`** | Prioriza regenerar carbono, aportar cobertura de rastrojo y cortar el monocultivo. |
| `equilibrio` | `0.50` | `0.50` | Balance 50/50 entre seguridad hídrica/climática y sustentabilidad del suelo. |

### 4.5. Flujo de Ejecución: Offline (Entrenamiento) vs. Online (Inferencia en Producción)
- **Fase Offline (Pre-deploy):** Se ejecuta el script de entrenamiento con series históricas de NASA POWER + curvas FAO/SIIA $\rightarrow$ genera el archivo `modelo_agro.joblib` que queda incluido en el repositorio del backend.
- **Fase Online (`POST /api/v1/simulate` en `< 1.5s`):**
  1. FastAPI recibe `coordenadas`, `campana`, `cultivo_anterior` y `objetivo_productor`.
  2. Consulta en paralelo **NASA POWER API** (filtrando lags `-999.0`) y **SoilGrids API**.
  3. Construye las features $X$ y ejecuta `modelo_agro.predict(X)` en memoria para obtener $S_{\text{hidroclimatico}}$ de cada cultivo de la campaña.
  4. Cruza cada cultivo con la **Matriz de Rotación** para obtener $S_{\text{suelo}}$, aplica los pesos ($w_{\text{clima}}, w_{\text{suelo}}$) y devuelve el JSON.

---

## 5. Contratos de Datos (API JSON)
Formato estándar de comunicación entre el Frontend y el Backend.

### Request: `POST /api/v1/simulate`
> **Nota de UX:** El usuario **no necesita ingresar la humedad del suelo manualmente**; el backend la detecta automáticamente vía satélite (`GWETROOT` de NASA POWER). El campo `simulacion_what_if` es **opcional** y solo se envía cuando el usuario mueve los sliders en la UI para simular escenarios hipotéticos.

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
    "variacion_lluvia_esperada_pct": 0 // opcional (-50 a +50): para simular años más secos o húmedos
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
    "anomalia_lluvia_90d_pct": -24.2,
    "riesgo_termico_verano": "alto"
  },
  "perfil_suelo": {
    "textura_predominante": "franco_limoso",
    "carbono_organico_g_kg": 18.4,
    "condicion_rotacion_previa": "deficit_rastrojo_por_soja"
  },
  "recomendacion_principal": {
    "cultivo": "sorgo",
    "secuencia_sugerida": "vicia_cobertura (invierno) -> sorgo / maiz_tardio (verano)",
    "score_final": 90.5,
    "sub_scores": {
      "hidroclimatico": 86.0,
      "suelo": 95.0
    },
    "factores_clave_ml": [
      "Baja saturación hídrica en zona radicular detectada por NASA (34%)",
      "Alta necesidad de aportar rastrojo de gramínea tras cultivo de Soja",
      "Anomalía de lluvias de -24.2% en los últimos 90 días"
    ],
    "explicacion": "Recomendación: Sembrar Sorgo (o Maíz Tardío precedido por Vicia). Detectamos vía satélite una reserva hídrica ajustada (34% de saturación radicular) y un déficit de lluvias del 24%. A diferencia del Maíz Temprano (riesgo crítico en floración) o repetir Soja (degradación de carbono del suelo), el Sorgo ofrece un 86% de aptitud hidroclimática y un 95% de beneficio edáfico para recomponer la estructura del lote."
  },
  "ranking_cultivos": [
    { "cultivo": "sorgo", "score_final": 90.5, "riesgo": "bajo" },
    { "cultivo": "maiz_tardio", "score_final": 82.5, "riesgo": "medio" },
    { "cultivo": "girasol", "score_final": 72.0, "riesgo": "bajo" },
    { "cultivo": "maiz_temprano", "score_final": 64.0, "riesgo": "critico" },
    { "cultivo": "soja_primera", "score_final": 31.0, "riesgo": "alto" }
  ]
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
