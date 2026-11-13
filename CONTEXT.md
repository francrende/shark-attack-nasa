# CONTEXTO DEL PROYECTO: Shark Attack

## 1. Visión General (Elevator Pitch)
**Shark Attack** es una herramienta web de soporte a la toma de decisiones agronómicas enfocada en la adaptación de cultivos y rotación inteligente. Desarrollada para el **NASA Space Apps Challenge 2026** (*Challenge: Field Shift: Adapting Farms with NASA Data*).

El sistema asiste al productor agrícola para definir qué cultivar y cómo planificar su rotación cruzando dimensiones clave respaldadas por observaciones de la Tierra de la NASA:
- **Clima e Hidrología (Datos NASA):** Humedad superficial y en zona radicular, régimen de precipitaciones histórico, anomalías térmicas y estrés evaporativo.
- **Salud del Suelo y Estado Vegetativo:** Impacto del cultivo antecesor (balance de nutrientes/agua), cobertura vegetal (NDVI) y resiliencia agronómica frente a sequías o eventos extremos.
- **Monitoreo Satelital Visual:** Capas interactivas de imágenes satelitales y mapas térmicos/hídricos para explorar el estado del lote y la región.

---

## 2. Arquitectura y Tech Stack
- **Frontend:** React + TypeScript (UI/UX enfocada en el productor, mapa interactivo con Leaflet / Mapbox GL superponiendo capas satelitales WMTS/WMS de la NASA).
- **Backend:** Python + FastAPI (Microservicio que consulta APIs agroclimáticas de la NASA y procesa reglas agronómicas / modelos de recomendación).
- **Data/ML:** Pandas/Polars para manejo de series temporales climáticas. Lógica de scoring multicriterio / Árboles de decisión para recomendar rotaciones.
- **Despliegue (Deploy):** Frontend en Vercel | Backend en Render/Railway.
- **Puertos Locales Habituales:** Frontend `:3000` (o `:5173` con Vite) | Backend `:8000`.

---

## 3. Catálogo de APIs y Fuentes de Datos de la NASA
A continuación se detallan las principales APIs y servicios de datos de la NASA relevantes para el desafío, divididos según su rol en la arquitectura (Backend de datos puntuales vs. Frontend de visualización satelital y fuentes complementarias).

### 3.1. APIs Core para el Backend (Datos numéricos por `lat`/`lon`)

#### A. NASA POWER API (Prediction Of Worldwide Energy Resources) — *[Prioridad Alta]*
API RESTful abierta (no requiere API Key) optimizada para aplicaciones agroclimáticas (`community=AG`). Devuelve JSON/CSV directo por coordenadas con series diarias, mensuales y climatologías históricas.
- **Documentación / Endpoint base:** `https://power.larc.nasa.gov/api/temporal/{daily|monthly|climatology}/point`
- **Parámetros clave para el proyecto:**
  - `PRECTOTCORR`: Precipitación total corregida (mm/día) — cálculo de oferta hídrica acumulada.
  - `GWETROOT`: Humedad del suelo en la zona radicular (0.0 a 1.0, hasta 1 metro de profundidad, asimilado de SMAP/GLDAS) — clave para decidir cultivos de alta demanda hídrica.
  - `GWETTOP`: Humedad en la capa superficial del suelo (0–5 cm) — determina ventana óptima de siembra.
  - `GWETPROF`: Humedad total del perfil del suelo.
  - `T2M`, `T2M_MAX`, `T2M_MIN`: Temperatura a 2 metros (media, máxima y mínima en °C) — detección de golpes de calor en floración y riesgo de heladas.
  - `ALLSKY_SFC_SW_DWN`: Radiación solar incidente — cálculo de tasa fotosintética potencial y evapotranspiración.
  - `EVPTRNS` / `RH2M`: Flujo de transpiración / Humedad relativa a 2m.

#### B. NASA AppEEARS API (Application for Extracting and Exploring Analysis Ready Samples) — *[Prioridad Media / Datos Pre-cacheados]*
API de LP DAAC que permite extraer valores puntuales o regionales de sensores como **MODIS**, **SMAP**, **ECOSTRESS** y **Landsat/Sentinel (HLS)** en formato JSON/CSV sin descargar rasters gigantes.
- **Particularidad técnica:** Requiere token de *NASA Earthdata Login* y funciona de forma asíncrona (basada en tareas/jobs), por lo que conviene usarla para **pre-poblar datos históricos del lote** o cachear curvas de NDVI/evapotranspiración, más que en llamadas síncronas en vivo.
- **Endpoint base:** `https://appeears.earthdatacloud.nasa.gov/api/`
- **Productos destacados:**
  - `MOD13Q1` (MODIS NDVI / EVI cada 16 días a 250m): Índice de vegetación para medir salud histórica del lote.
  - `ECO2LSTE` / `ECO3ETPTJPL` (ECOSTRESS): Temperatura de superficie terrestre (LST) y Evapotranspiración (estrés hídrico de las plantas).
  - `SPL3SMP_E` / `SPL4SMGP` (SMAP): Humedad del suelo con resolución mejorada (9 km).

---

### 3.2. APIs de Imágenes Satelitales y Capas Visuales para el Frontend (Mapas)

#### C. NASA GIBS (Global Imagery Browse Services) / Worldview — *[Prioridad Alta para UI/UX]*
Servicio de teselas (WMTS / WMS / XYZ tiles) que permite superponer capas satelitales de la NASA directamente en **Leaflet** o **Mapbox** en tiempo real, sin necesidad de procesar imágenes en el backend ni usar API Keys.
- **Endpoint WMTS base:** `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{Layer}/default/{Time}/{TileMatrixSet}/{z}/{y}/{x}.{format}`
- **Capas recomendadas para el Frontend:**
  - `MODIS_Terra_CorrectedReflectance_TrueColor` o `VIIRS_SNPP_CorrectedReflectance_TrueColor`: Imagen satelital real (color verdadero) actualizada diariamente.
  - `SMAP_L4_Analyzed_Root_Zone_Soil_Moisture`: Mapa de calor global de humedad en zona radicular.
  - `MODIS_Terra_NDVI_8Day`: Capa visual de índice de vegetación (verdor / biomasa activa).
  - `MODIS_Terra_Land_Surface_Temp_Day`: Temperatura superficial del suelo para visualizar islas de calor o estrés térmico regional.
  - `IMERG_Precipitation_Rate`: Tasa de precipitación derivada de la misión **GPM (Global Precipitation Measurement)**.

#### D. NASA Earthdata CMR-STAC / Harmonized Landsat Sentinel-2 (HLS) — *[Opcional / Alta Resolución Visual]*
API basada en el estándar **STAC (SpatioTemporal Asset Catalog)** para buscar y renderizar recortes satelitales ópticos de alta resolución (30 metros) del proyecto **HLS** (que combina Landsat 8/9 de NASA/USGS y Sentinel-2 de ESA).
- **Endpoint STAC:** `https://cmr.earthdata.nasa.gov/stac/LPCLOUD`
- **Uso potencial:** Mostrar la evolución visual del lote específico (a nivel de parcela) o calcular índices espectrales finos (NDVI, NDWI para agua en hojas) mediante Cloud Optimized GeoTIFFs (COGs).

---

### 3.3. Otras Fuentes y Herramientas del Ecosistema NASA / Agro (Opcionales o de Referencia)

#### E. Crop-CASMA (Crop Condition and Soil Moisture Analytics) / USDA-NASA
Plataforma y servicios web (WMS/WCS) desarrollados por la NASA y el USDA basados en datos **SMAP** (humedad del suelo a 1 km de resolución) y **MODIS** (NDVI).
- **Uso potencial:** Referencia metodológica para anomalías de humedad del suelo y condición de cultivos en zonas agrícolas.

#### F. NASA GPM (Global Precipitation Measurement - IMERG) & GRACE-FO
- **GPM:** Medición satelital avanzada de lluvias y tormentas cada 30 minutos. (Accesible vía GIBS para mapas o integrada en modelos diarios).
- **GRACE-FO (Gravity Recovery and Climate Experiment Follow-On):** Mide variaciones en el almacenamiento de agua subterránea (acuíferos) y sequías prolongadas a escala regional. Útil como indicador de resiliencia hídrica a largo plazo.

#### G. NASA Giovanni / GES DISC
Herramienta web de análisis geofísico de la NASA útil durante el desarrollo para explorar correlaciones históricas (ej. anomalías de lluvia vs. humedad de suelo durante años de *El Niño* / *La Niña*) y definir umbrales agronómicos en el backend.

---

## 4. Contratos de Datos (API JSON)
Formato estándar de comunicación entre el Frontend y el Backend. Todas las herramientas de IA (Cursor/Claude/Antigravity) deben respetar o extender esta estructura al generar componentes o endpoints.

### Request: `POST /api/v1/simulate`
```json
{
  "coordenadas": {
    "lat": -33.95,
    "lon": -60.57
  },
  "cultivo_anterior": "soja",
  "humedad_suelo_actual_pct": 22.5,
  "objetivo_productor": "equilibrio" // opciones: "conservacion_suelo", "eficiencia_hidrica", "resiliencia_climatica", "equilibrio"
}
```

### Flujo esperado del Backend en `/api/v1/simulate`
1. Recibe las `coordenadas`, el `cultivo_anterior` y el `objetivo_productor`.
2. Consulta **NASA POWER API** (`PRECTOTCORR`, `GWETROOT`, `GWETTOP`, `T2M_MAX`, `T2M_MIN`) para obtener el perfil hidroclimático de la ubicación (y usar `GWETROOT` si `humedad_suelo_actual_pct` no fue provisto manualmente).
3. Evalúa cada cultivo candidato de rotación cruzando:
   - **Adecuación hídrica y térmica** (según datos NASA).
   - **Impacto en la salud del suelo** (rotación gramínea/leguminosa respecto a `cultivo_anterior`, cobertura de rastrojo y consumo de agua).
4. Devuelve un ranking de cultivos recomendados con métricas agroclimáticas e indicadores de riesgo.

```

### Flujo esperado del Backend en `/api/v1/simulate`
1. Recibe las `coordenadas`, el `cultivo_anterior` y el `objetivo_productor`.
2. Consulta **NASA POWER API** (`PRECTOTCORR`, `GWETROOT`, `GWETTOP`, `T2M_MAX`, `T2M_MIN`) para obtener el perfil hidroclimático de la ubicación (y usar `GWETROOT` si `humedad_suelo_actual_pct` no fue provisto manualmente).
3. Evalúa cada cultivo candidato de rotación cruzando:
   - **Adecuación hídrica y térmica** (según datos NASA).
   - **Impacto en la salud del suelo** (rotación gramínea/leguminosa respecto a `cultivo_anterior`, cobertura de rastrojo y consumo de agua).
4. Devuelve un ranking de cultivos recomendados con métricas agroclimáticas e indicadores de riesgo.