# TASKS_FRONTEND.md — Tablero y Protocolo de Tareas Atómicas (Track Frontend, GIS & UI/UX)

> **Fuente de la Verdad:** Antes de proponer o programar cualquier tarea, el agente DEBE leer [`../CONTEXT.md`](../CONTEXT.md) (especialmente las **Secciones 3.2, 5, 6 y 8**).

---

## 1. Protocolo Obligatorio para el Agente (Cómo trabajar con el Desarrollador)

Cada vez que el desarrollador te pida crear, detallar o avanzar con una tarea de Frontend, seguí **estrictamente estos 4 pasos en orden**:

1. **Consultar el Contexto General:** Revisá el flujo de usuario (Sección 6), las capas satelitales de NASA GIBS (Sección 3.2) y el contrato JSON (Sección 5) en [`../CONTEXT.md`](../CONTEXT.md).
2. **Hacer Preguntas de Definición (Obligatorio ANTES de cerrar la especificación o programar):**
   - No asumas decisiones de UX/UI o de interacción que estén abiertas (ej. paleta de colores Dark vs. Light, qué lotes demo pre-cargar en el mapa, cómo debe funcionar la herramienta para pintar/dibujar el polígono del campo en Leaflet, qué controles mostrar en los sliders *What-If*, diseño de las tarjetas de telemetría y ranking).
   - **Hacele preguntas claras y concretas al desarrollador** para definir esos detalles antes de cerrar la especificación.
3. **Documentar la Tarea Atómica en este archivo:**
   - Con las respuestas del desarrollador, redactá la especificación de la tarea en la sección **3. Especificación de Tareas Atómicas** de este archivo usando la plantilla estándar y marcala como `[~]` (En progreso).
4. **Implementar y Verificar (Definition of Done):**
   - Escribí el código dentro de `frontend/`, verificá que compile sin errores de tipos (`npx tsc -b` / `npm run build`) y marcá la tarea como `[x]`.

---

## 2. Reglas de Aislamiento (Cero Conflictos en Git)

- **Archivos Permitidos (Scope Exclusivo de Frontend):**
  - Todo archivo dentro de `frontend/` (`frontend/src/*`, `frontend/index.html`, `frontend/TASKS_FRONTEND.md`, etc.).
- **Archivos Prohibidos:** NO modificar ningún archivo dentro de `backend/`.

---

## 3. Tablero de Tareas Atómicas (Frontend)

| ID | Tarea Atómica | Archivos Involucrados | Depende de | Estado |
| :--- | :--- | :--- | :---: | :---: |
| **FRONT-1** | Sistema de Diseño (Paleta AgTech), Contratos TypeScript, Lotes Demo Pampeanos y Cliente API con Simulador Reactivo | `frontend/index.html`, `frontend/src/index.css`, `frontend/src/types/api.ts`, `frontend/src/data/demoFields.ts`, `frontend/src/services/apiClient.ts` | — | `[x]` |
| **FRONT-2** | Visor GIS Satelital con Leaflet, Capas WMTS de NASA GIBS y 3 Modos de Selección/Dibujo de Lote | `frontend/src/components/MapView.tsx`, `frontend/src/utils/geo.ts`, `frontend/src/data/demoFields.ts` | `FRONT-1` | `[x]` |
| **FRONT-3** | Panel de Telemetría NASA/Suelo, Selectores de Campaña/Objetivo y Controles Interactivos *What-If* | `frontend/src/components/TelemetryCards.tsx`, `frontend/src/components/SimulationControls.tsx` | `FRONT-1` | `[x]` |
| **FRONT-4** | Tarjeta de Recomendación Explicada, Gráficos de Ranking de Cultivos y Dashboard Split-Screen Integrado | `frontend/src/components/RecommendationPanel.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css` | `FRONT-2`, `FRONT-3` | `[x]` |

---

## 4. Especificación de Tareas Atómicas

### `[x]` FRONT-1: Sistema de Diseño (Paleta AgTech), Contratos TypeScript, Lotes Demo Pampeanos y Cliente API con Simulador Reactivo
- **Objetivo:** Establecer las variables CSS globales con la paleta definida por la desarrolladora, los contratos estrictos de datos (`SimulateRequest` / `SimulateResponse`), el catálogo de 4 lotes demo con polígonos reales en la Región Pampeana y el motor cliente de simulación local para trabajar sin depender de que el backend esté levantado.
- **Archivos Permitidos:**
  - `frontend/index.html`
  - `frontend/src/index.css`
  - `frontend/src/types/api.ts`
  - `frontend/src/data/demoFields.ts`
  - `frontend/src/services/apiClient.ts`
- **Decisiones Acordadas con el Desarrollador:**
  - **Paleta de colores oficial:**
    - Letras destacadas, acentos y botones principales: `#4B5B2D` (con tonos derivados oscuros `#35421E` y claros `#687D40` / `#E9EFE0`).
    - Fondo principal: `#FFF5E0` (con variantes crema/arena `#FFFBF2` y `#F4E5C5` para tarjetas y contenedores).
    - Texto general: `#22181C` (con marrones tierra `#5E4B43` y `#8C5A3C` para subtítulos y bordes).
    - Gráficos e indicadores de calor / estrés térmico / suelo: `#F05D23` (más ocre/amarillo `#D99B26` para alertas medias).
    - Gráficos e indicadores de humedad de suelo y lluvias: `#4A7B9D` (con variantes `#2E5670` y `#DCEBF2`).
  - **Lotes Demo:** 4 lotes representativos en la Región Pampeana (Pergamino, Venado Tuerto, Marcos Juárez y Tres Arroyos) con polígonos reales y distintos escenarios hidroclimáticos y edáficos.
  - **Modo del Cliente API:** Utilizar datos simulados reactivos en el frontend por ahora (respetando el contrato JSON exacto de la Sección 5 de `CONTEXT.md` y respondiendo en vivo a cambios de lote, campaña, cultivo antecesor, objetivo del productor y sliders *What-If*), dejando listo el `fetch` a `POST /api/v1/simulate` para activarlo apenas el equipo de Backend finalice su rama.
- **Especificación Técnica:**
  1. Configurar en `frontend/index.html` el título de la plataforma, tipografías limpias y hojas de estilo de Leaflet.
  2. Definir en `frontend/src/index.css` los tokens de color CSS (`--color-primary: #4B5B2D`, `--color-bg: #FFF5E0`, `--color-text: #22181C`, `--color-heat-soil: #F05D23`, `--color-water-rain: #4A7B9D`, más amarillos/marrones complementarios) y estilos base para layout split-screen.
  3. Crear `frontend/src/types/api.ts` reflejando 1:1 el contrato JSON de `POST /api/v1/simulate` (`SimulateRequest`, `SimulateResponse`, `TelemetriaNasa`, `PerfilSuelo`, `RecomendacionPrincipal`, `RankingCultivoItem`) y tipos de soporte GIS (`DemoField`, `GibsLayerConfig`, `SelectionMode`).
  4. Crear `frontend/src/data/demoFields.ts` con los 4 lotes pampeanos, metadatos de cultivos de invierno y verano, objetivos del productor y configuración de capas WMTS de NASA GIBS.
  5. Crear `frontend/src/services/apiClient.ts` con el motor de simulación reactivo local que calcula los dos pilares ($S_{\text{hidroclimatico}}$ y $S_{\text{suelo}}$) y los pondera según `objetivo_productor` ($0.75/0.25$, $0.30/0.70$, $0.50/0.50$).
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b`

---

### `[x]` FRONT-2: Visor GIS Satelital con Leaflet, Capas WMTS de NASA GIBS y 3 Modos de Selección/Dibujo de Lote
- **Objetivo:** Construir el mapa interactivo con imagen satelital base, superposición de capas científicas de NASA GIBS y soporte para los 3 modos de selección de lote (Lote Demo, Dibujo de polígono clic por clic con cálculo de área/centroide, y Clic rápido en un punto).
- **Archivos Permitidos:** `frontend/src/components/MapView.tsx`, `frontend/src/utils/geo.ts`, `frontend/src/data/demoFields.ts`
- **Decisiones Acordadas con el Desarrollador:**
  - **Capa inicial por defecto:** Iniciar con la capa **NASA MODIS True Color** (`MODIS_Terra_CorrectedReflectance_TrueColor`, `'modis_true_color'`) activa por defecto sobre la base satelital Esri WorldImagery + etiquetas híbridas, permitiendo cambiar en un clic a **SMAP Humedad Radicular**, **MODIS NDVI (Verdor)**, **MODIS Temp. Superficial (LST)**, **IMERG Lluvias (GPM)** o **Solo Satélite Base**.
  - **Modos de selección y herramienta de dibujo:** Incluir los 3 modos (`demo`, `polygon`, `point`). En el modo `polygon`, proveer una barra de herramientas sobre el mapa con acciones para **Agregar vértices por clic**, **Deshacer último punto**, **Cerrar lote** y **Limpiar**, mostrando en vivo la superficie calculada en hectáreas (`ha`) y el centroide (`lat, lon`) que se envía al motor de simulación.
  - **Estética del Mapa:** Controles flotantes y leyendas estilizados con la paleta `#FFF5E0` (superficies), `#4B5B2D` (botones activos y polígonos seleccionados), `#4A7B9D` (capas de agua) y `#F05D23` (capas de calor/polígono en edición).
- **Especificación Técnica:**
  1. Agregar la configuración de `modis_true_color` (`MODIS_Terra_CorrectedReflectance_TrueColor`) en `frontend/src/data/demoFields.ts`.
  2. Crear `frontend/src/utils/geo.ts` con funciones geodésicas para calcular el centroide (`calculateCentroid`) y el área aproximada en hectáreas (`calculatePolygonAreaHa`) a partir de un arreglo de vértices `[lat, lon][]`.
  3. Crear `frontend/src/components/MapView.tsx` integrando `react-leaflet` (`MapContainer`, `TileLayer`, `Polygon`, `Polyline`, `CircleMarker`, `Tooltip`, `useMap`, `useMapEvents`), transición suave (`flyTo`) al cambiar de lote demo, selector flotante de capas NASA GIBS con slider de opacidad y leyenda, y barra interactiva para dibujo de polígonos.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b`

---

### `[x]` FRONT-3: Panel de Telemetría NASA/Suelo, Selectores de Campaña/Objetivo y Controles Interactivos *What-If*
- **Objetivo:** Crear los componentes visuales para mostrar la telemetría satelital detectada (`GWETROOT`, `GWETTOP`, anomalía de lluvia 90d, riesgo térmico y perfil de suelo de SoilGrids) y los controles reactivos de configuración y simulación *What-If*.
- **Archivos Permitidos:** `frontend/src/components/TelemetryCards.tsx`, `frontend/src/components/SimulationControls.tsx`
- **Decisiones Acordadas con el Desarrollador:**
  - **Actualización reactiva en tiempo real:** Al mover los sliders *What-If* o cambiar campaña, cultivo antecesor u objetivo del productor, el motor actualiza las tarjetas y el ranking instantáneamente sin requerir clic en un botón "Recalcular".
  - **Codificación cromática:**
    - `#4A7B9D` para gráficos/barras de humedad radicular (`GWETROOT`), humedad superficial (`GWETTOP`) y anomalías de lluvia (`PRECTOTCORR`).
    - `#F05D23` y tonos tierra/amarillo para riesgo térmico estival, textura edáfica y carbono orgánico del suelo (`soc`).
  - **Controles *What-If*:** Sliders para `override_humedad_radicular_pct` (0 a 100%) y `variacion_lluvia_esperada_pct` (-50% a +50%) con indicador visual cuando el usuario está simulando un escenario hipotético y botón rápido para restaurar los valores satelitales reales de NASA POWER.
- **Especificación Técnica:**
  1. Crear `frontend/src/components/TelemetryCards.tsx` con medidores visuales de saturación hídrica en `#4A7B9D` y salud/estrés térmico/suelo en `#F05D23`.
  2. Crear `frontend/src/components/SimulationControls.tsx` con selector de campaña (`invierno` / `verano`), selector de `cultivo_anterior`, tarjetas interactivas de `objetivo_productor` mostrando los pesos ($w_{\text{clima}}, w_{\text{suelo}}$) y sliders *What-If*.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b`

---

### `[x]` FRONT-4: Tarjeta de Recomendación Explicada, Gráficos de Ranking de Cultivos y Dashboard Split-Screen Integrado
- **Objetivo:** Construir la visualización de la recomendación principal (cultivo ganador, secuencia anual sugerida Invierno -> Verano, sub-scores hidroclimático vs. suelo, factores clave ML y explicación agronómica), el gráfico de barras del ranking de cultivos y ensamblar el Dashboard Split-Screen (~60% Mapa / ~40% Panel lateral).
- **Archivos Permitidos:** `frontend/src/components/RecommendationPanel.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - **Layout Split-screen:** ~60% Mapa interactivo a la izquierda + ~40% Panel derecho sobre fondo `#FFF5E0` con botones y acentos en `#4B5B2D` y textos en `#22181C`.
  - **Visualización de Recomendación y Ranking:** Tarjeta destacada del Cultivo Ganador con anillo/medidor circular de Score Final, barras desglosadas de Pilar Hidroclimático (`#4A7B9D`) vs. Pilar Suelo (`#F05D23`), secuencia anual sugerida (`Invierno -> Verano`), chips de factores clave ML y gráfico horizontal comparativo de todos los cultivos candidatos con insignias de riesgo (`bajo`, `medio`, `alto`, `critico`).
- **Especificación Técnica:**
  1. Crear `frontend/src/components/RecommendationPanel.tsx` con el medidor SVG circular del Score Final, barras comparativas de los dos pilares, flujo visual de la secuencia de rotación y barras horizontales del ranking.
  2. Crear `frontend/src/App.tsx` integrando `MapView`, `TelemetryCards`, `SimulationControls` y `RecommendationPanel` con estado reactivo sincronizado.
  3. Crear `frontend/src/App.css` implementando todos los estilos del dashboard split-screen, tarjetas, barras de progreso, controles del mapa y diseño responsivo aplicando la paleta oficial.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`
