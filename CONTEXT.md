# CONTEXTO DEL PROYECTO: Shark Attack

## 1. Visión General (Elevator Pitch)
**Shark Attack** es una herramienta web de soporte a la toma de decisiones agronómicas para la región de la Pampa Húmeda (Argentina). Desarrollado para el NASA Space Apps Challenge 2026 (Challenge: *Field Shift: Adapting Farms with NASA Data*).
El sistema asiste al productor agrícola para definir qué cultivar cruzando tres dimensiones:
- **Clima y Suelo (Datos NASA):** Humedad actual, clima pasado y proyecciones futuras.
- **Salud del Suelo:** Impacto del cultivo antecesor y resiliencia agronómica.
- **Contexto Económico Local:** Precios de exportación, retenciones impositivas y márgenes brutos estimados.

## 2. Arquitectura y Tech Stack
- **Frontend:** React + TypeScript (UI/UX enfocada en el productor, mapa interactivo con Leaflet/Mapbox).
- **Backend:** Python + FastAPI (Microservicio que procesa reglas agronómicas y consume APIs).
- **Data/ML:** Pandas/Polars para manejo de series temporales. Lógica de scoring / Árboles de decisión.
- **Despliegue (Deploy):** Frontend en Vercel | Backend en Render/Railway.
- **Puertos Locales Habituales:** Frontend `:3000` (o `:5173` si es Vite) | Backend `:8000`.

## 3. Fuentes de Datos
- **NASA POWER API:** Meteorología histórica y proyecciones climáticas (Precipitaciones, Temperatura).
- **NASA SMAP:** Humedad del suelo (Soil Moisture).
- **Economía Local (`economia_argentina.json`):** Datos estáticos o cacheados de precios pizarra (MATba Rofex), alícuotas de derechos de exportación (retenciones) y costos por hectárea.

## 4. Contratos de Datos (API JSON)
Este es el formato estándar de comunicación entre el Frontend y el Backend. Todas las herramientas de IA (Cursor/Claude) deben respetar esta estructura al generar componentes o endpoints.

### Request: `POST /api/v1/simulate`
```json
{
  "coordenadas": { "lat": -33.95, "lon": -60.57 },
  "cultivo_anterior": "soja",
  "humedad_suelo_actual_pct": 22.5,
  "objetivo_productor": "rentabilidad_maxima" // opciones: "rentabilidad_maxima", "conservacion_suelo", "equilibrio"
}