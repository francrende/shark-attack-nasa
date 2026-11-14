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
| **FRONT-5** | Ajuste de Capas del Mapa ("Mapa satelital") y Separación de Configuración Principal vs. Simulador *What-If* | `frontend/src/data/demoFields.ts`, `frontend/src/components/SimulationControls.tsx` | `FRONT-2`, `FRONT-3` | `[x]` |
| **FRONT-6** | Menú Superior de 4 Pestañas (`Info general`, `Planificación de campaña`, `Información histórica`, `Chat`) | `frontend/src/App.tsx`, `frontend/src/App.css` | `FRONT-4`, `FRONT-5` | `[x]` |
| **FRONT-7** | Refinamiento UX/UI de `"Planificación de campaña"`, Header y Tokens según `SKILLS_FRONTEND.md` | `frontend/src/theme/mapColors.ts`, `frontend/src/components/SimulationControls.tsx`, `frontend/src/components/RecommendationPanel.tsx`, `frontend/src/services/apiClient.ts`, `frontend/src/App.tsx`, `frontend/src/App.css` | `FRONT-6` | `[x]` |
| **FRONT-8** | Refinamiento UX/UI de `"Info general"` y Mapa GIS (Fechas humanas, Glosario, Cero Hex Hardcodeados y Anti-clutter) | `frontend/src/utils/formatters.ts`, `frontend/src/components/TelemetryCards.tsx`, `frontend/src/components/MapView.tsx`, `frontend/src/data/demoFields.ts`, `frontend/src/App.css` | `FRONT-7` | `[x]` |
| **FRONT-9** | Pestaña `"Información histórica"` (Línea de Tiempo de 10 Años Sincronizada en Vivo con el Mapa + Desplegable de Variables) | `frontend/src/data/historicalData.ts`, `frontend/src/components/HistoricalPanel.tsx`, `frontend/src/components/MapView.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css` | `FRONT-8` | `[x]` |
| **FRONT-10** | Rediseño del Header en Marrón/Terracota y Pestañas estilo Carpeta de Archivo Físico con Pestaña Activa Resaltada | `frontend/src/index.css`, `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/SKILLS_FRONTEND.md` | `FRONT-9` | `[x]` |
| **FRONT-11** | Simplificación del Mapa GIS: Eliminación del modo `"Tocar un punto"` | `frontend/src/types/api.ts`, `frontend/src/components/MapView.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css` | `FRONT-10` | `[x]` |
| **FRONT-12** | Reemplazo de Preguntas en Títulos por Títulos de Pestaña y Lenguaje Formal Agronómico | `frontend/src/components/SimulationControls.tsx`, `frontend/src/components/RecommendationPanel.tsx`, `frontend/src/components/TelemetryCards.tsx`, `frontend/src/components/HistoricalPanel.tsx`, `frontend/src/services/apiClient.ts`, `frontend/src/data/demoFields.ts`, `frontend/src/data/historicalData.ts`, `frontend/SKILLS_FRONTEND.md` | `FRONT-10` | `[x]` |
| **FRONT-13** | Diversificación Cromática de Botones y Controles Seleccionados (No Todo Verde) | `frontend/src/index.css`, `frontend/src/App.css`, `frontend/src/components/SimulationControls.tsx`, `frontend/src/components/HistoricalPanel.tsx` | `FRONT-11`, `FRONT-12` | `[x]` |
| **FRONT-14** | Header Sólido `#3A0C00`, Eliminación de Pestaña Chat y Alineación de Pestañas al 40% del Panel Derecho | `frontend/src/index.css`, `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/SKILLS_FRONTEND.md` | `FRONT-10` | `[x]` |
| **FRONT-15** | Integración de las Pestañas de Carpeta al Componente Derecho Superpuestas sobre el Header | `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/SKILLS_FRONTEND.md` | `FRONT-14` | `[x]` |
| **FRONT-16** | Diferir Estrategia de Rotación hasta Seleccionar Campaña y Cultivo Antecesor (Con Estado Vacío y Carga Asíncrona) | `frontend/src/components/SimulationControls.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css` | `FRONT-12` | `[x]` |
| **FRONT-17** | Precarga Automática de Datos Históricos al Completar Campaña/Cultivo y Botón `"Planificar"` | `frontend/src/components/SimulationControls.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css` | `FRONT-16` | `[x]` |
| **FRONT-18** | Pantalla de Inicio de Sesión y Registro Conectada a `BACK-3` (Con Modo Demo) | `frontend/src/types/api.ts`, `frontend/src/services/authClient.ts`, `frontend/src/components/AuthScreen.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css` | `FRONT-15` | `[x]` |
| **FRONT-19** | Rebranding a **Ereia** (Fraunces 600, Ícono PNG sin recuadro), Header `#FFF5E0` y Fondo Salvia `#A8BC82` | `frontend/public/ereia-icon.png`, `frontend/index.html`, `frontend/src/index.css`, `frontend/src/components/BrandBlock.tsx`, `frontend/src/components/AuthScreen.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css` | `FRONT-18` | `[x]` |
| **FRONT-20** | Refinamiento de Panel Derecho, Pestañas tipo Carpeta y Header (Tonos Arena, Márgenes y Sombras sin Bordes) | `frontend/src/index.css`, `frontend/src/App.css` | `FRONT-19` | `[x]` |
| **FRONT-21** | Segundo Header Colapsable de Gestión de Lotes del Usuario y Delimitación de Nuevos Campos (`BACK-4`) | `frontend/src/types/api.ts`, `frontend/src/services/fieldsClient.ts`, `frontend/src/components/FieldsSubheader.tsx`, `frontend/src/components/MapView.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css` | `FRONT-20` | `[x]` |
| **FRONT-22** | Refinamiento UX/UI de Campañas, Objetivo Animado y Listado Interactivo de Estrategia de Rotación | `frontend/src/components/SimulationControls.tsx`, `frontend/src/components/RecommendationPanel.tsx`, `frontend/src/App.css` | `FRONT-21` | `[x]` |
| **FRONT-23** | Estrategia de Rotación Unificada en Listado Expandible, Campaña Actual (`Invierno` Desactivado) y Mapa Limpio sin Capas GIBS | `frontend/src/components/RecommendationPanel.tsx`, `frontend/src/components/SimulationControls.tsx`, `frontend/src/components/MapView.tsx`, `frontend/src/services/apiClient.ts`, `frontend/src/App.tsx`, `frontend/src/App.css` | `FRONT-22` | `[x]` |

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

---

### `[x]` FRONT-17: Precarga Automática de Datos Históricos al Completar Campaña/Cultivo y Botón `"Planificar"`
- **Objetivo:** Separar la carga de datos históricos (automática apenas el usuario completa campaña y cultivo antecesor) de la visualización de la recomendación de cultivo, la cual se muestra al presionar el botón **`"Planificar"`** según el objetivo seleccionado.
- **Archivos Permitidos:** `frontend/src/components/SimulationControls.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - Al completarse `campana` y `cultivoAnterior`, se dispara automáticamente el pedido/precarga de los datos históricos del lote.
  - La tarjeta `RecommendationPanel` (y `WhatIfPanel`) permanece oculta hasta que el usuario presione el botón **`"Planificar"`** en `CampaignConfigPanel`.
  - Si el usuario cambia el objetivo o los sliders *What-If* luego de planificar, la recomendación se actualiza automáticamente.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-5: Ajuste de Capas del Mapa ("Mapa satelital") y Separación de Configuración Principal vs. Simulador *What-If*
- **Objetivo:** Eliminar la capa `"Vista Real del cielo"`, renombrar `"Solo lotes y caminos"` a `"Mapa satelital"` como opción por defecto, y desacoplar los controles de planificación en dos componentes independientes: `CampaignConfigPanel` (Tipo de campaña, Último cultivo y Objetivo) y `WhatIfPanel` (Simulador interactivo separado).
- **Archivos Permitidos:** `frontend/src/data/demoFields.ts`, `frontend/src/components/SimulationControls.tsx`
- **Decisiones Acordadas con el Desarrollador:**
  - Sacar `"Vista Real del cielo"` (`modis_true_color`) y dejar la capa limpia renombrada a **`"Mapa satelital"`**.
  - Separar la configuración principal (Tipo de campaña, Último cultivo y Objetivo) del bloque *What-If* para que en la pestaña `"Planificación de campaña"` se muestre primero la Configuración Principal, luego la Recomendación y Ranking, y debajo en una tarjeta independiente el Simulador *What-If*.
- **Especificación Técnica:**
  1. En `frontend/src/data/demoFields.ts`, configurar el ítem `'none'` con `shortLabel: 'Mapa satelital'` y `name: 'Mapa satelital'`.
  2. En `frontend/src/components/SimulationControls.tsx`, exportar dos componentes separados: `CampaignConfigPanel` (Paso 2 principal) y `WhatIfPanel` (Tarjeta independiente para simular escenarios de agua y lluvia).
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b`

---

### `[x]` FRONT-6: Menú Superior de 4 Pestañas (`Info general`, `Planificación de campaña`, `Información histórica`, `Chat`)
- **Objetivo:** Incorporar en el Header superior un menú de navegación con 4 pestañas que controle qué módulos se visualizan en el panel derecho y cuándo se muestra u oculta el mapa satelital.
- **Archivos Permitidos:** `frontend/src/App.tsx`, `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - **Pestaña 1 — `Info general`:** Muestra el Mapa Satelital a la izquierda y el Paso 1 (`TelemetryCards`: estado hídrico, lluvias, calor y suelo del lote) a la derecha.
  - **Pestaña 2 — `Planificación de campaña`:** Muestra el Mapa Satelital a la izquierda y en el panel derecho, en este orden exacto:
    1. Tarjeta 1: Configuración Principal (`CampaignConfigPanel`: Tipo de campaña, Último cultivo, Objetivo).
    2. Tarjeta 2: Recomendación y Ranking (`RecommendationPanel`: Paso 3).
    3. Tarjeta 3 (separada): Simulador *What-If* (`WhatIfPanel`).
  - **Pestaña 3 — `Información histórica`:** Mantiene el **Mapa Satelital visible a la izquierda** (para permitir visualizar la evolución histórica de temperatura de la tierra o tipos de cultivo en el mapa) y deja el panel derecho con un contenedor vacío preparado para los gráficos históricos.
  - **Pestaña 4 — `Chat`:** Única pestaña donde **no se muestra el mapa**, dejando el área principal vacía lista para integrar el asistente conversacional.
- **Especificación Técnica:**
  1. Agregar el estado `activeTab: 'info_general' | 'planificacion' | 'historico' | 'chat'` en `frontend/src/App.tsx` y renderizar la barra de pestañas en el Header superior.
  2. Mantener montado o visible el panel izquierdo del mapa en `info_general`, `planificacion` e `historico`, y ocultarlo cuando `activeTab === 'chat'`.
  3. Estilizar las pestañas del menú superior y los contenedores vacíos de `Información histórica` y `Chat` en `frontend/src/App.css` respetando la paleta `#4B5B2D`, `#FFF5E0` y `#22181C` y las fuentes `Newsreader` / `Plus Jakarta Sans`.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-17: Precarga Automática de Datos Históricos al Completar Campaña/Cultivo y Botón `"Planificar"`
- **Objetivo:** Separar la carga de datos históricos (automática apenas el usuario completa campaña y cultivo antecesor) de la visualización de la recomendación de cultivo, la cual se muestra al presionar el botón **`"Planificar"`** según el objetivo seleccionado.
- **Archivos Permitidos:** `frontend/src/components/SimulationControls.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - Al completarse `campana` y `cultivoAnterior`, se dispara automáticamente el pedido/precarga de los datos históricos del lote.
  - La tarjeta `RecommendationPanel` (y `WhatIfPanel`) permanece oculta hasta que el usuario presione el botón **`"Planificar"`** en `CampaignConfigPanel`.
  - Si el usuario cambia el objetivo o los sliders *What-If* luego de planificar, la recomendación se actualiza automáticamente.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-7: Refinamiento UX/UI de `"Planificación de campaña"`, Header y Tokens según `SKILLS_FRONTEND.md`
- **Objetivo:** Alinear la experiencia de `"Planificación de campaña"`, el menú superior y el uso de tokens de color con las reglas de diseño de [`SKILLS_FRONTEND.md`](./SKILLS_FRONTEND.md) (claridad en `< 5s`, divulgación progresiva, glosario sin tecnicismos, formato entero de puntajes y cero hex hardcodeados).
- **Archivos Permitidos:**
  - `frontend/src/theme/mapColors.ts`
  - `frontend/src/data/demoFields.ts`
  - `frontend/src/services/apiClient.ts`
  - `frontend/src/components/SimulationControls.tsx`
  - `frontend/src/components/RecommendationPanel.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - **Pestaña inicial por defecto:** Iniciar directamente en **`Planificación de campaña`** (`activeTab = 'planificacion'`) y ordenar las pestañas con `Planificación de campaña` primero.
  - **Pestaña Chat:** Mantener el botón **`Chat`** visible en el menú superior pero deshabilitado (`disabled`) con una etiqueta discreta **`Próximamente`**.
  - **Configuración principal (`CampaignConfigPanel`):**
    - Etiquetas en español rioplatense claro: `Campaña gruesa (verano)` / `Campaña fina (invierno)`, `Último cultivo`, `¿Qué querés priorizar?`.
    - Tarjetas de objetivo (`Seguridad frente a sequía`, `Equilibrio`, `Cuidar el suelo`) con título claro, descripción breve de 1 línea y barra visual mínima (azul agua / naranja suelo) sin porcentajes técnicos como titular.
  - **Tarjeta de Recomendación (`RecommendationPanel`):**
    - **Conclusión primero, evidencia después:** Nombre del cultivo recomendado en `Newsreader`, anillo de **Puntaje general** entero sobre 100 (`91 / 100`) y una frase corta de 1 línea explicando el porqué antes de las barras.
    - **2 barras de pilares:** `Aptitud frente al agua y el clima` (azul `--color-water-rain`) y `Aporte al suelo y la rotación` (naranja `--color-heat-soil`) con valores enteros.
    - **Rotación sugerida para el año:** Nombres legibles (`Vicia de cobertura (invierno) → Sorgo o Maíz tardío (verano)`) en vez de códigos `snake_case`.
    - **Divulgación progresiva ("Ver detalle"):** Los motivos detallados y la explicación extendida se despliegan bajo un botón `"Ver detalle"`, manteniendo la vista inicial limpia (≤ 4 elementos clave).
    - **Ranking anti-clutter:** Mostrar el **Top 3** por defecto con un botón `"Ver todos los cultivos (N)"`, usando `"Riesgo muy alto"` en lugar de `"Riesgo crítico"` y `aria-live="polite"`.
  - **Tarjeta `¿Qué pasa si...?` (`WhatIfPanel`):**
    - Visualmente secundaria, con insignia `"Escenario simulado"` cuando está activa, controles en palabras simples (`Agua en las raíces al sembrar`, `Lluvias de la campaña`) y botón `"Volver al dato real"`.
  - **Tokens de color (`src/theme/mapColors.ts`):** Centralizar constantes de color para SVG/Leaflet eliminando códigos hexadecimales sueltos en componentes y reglas de `App.css`.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-17: Precarga Automática de Datos Históricos al Completar Campaña/Cultivo y Botón `"Planificar"`
- **Objetivo:** Separar la carga de datos históricos (automática apenas el usuario completa campaña y cultivo antecesor) de la visualización de la recomendación de cultivo, la cual se muestra al presionar el botón **`"Planificar"`** según el objetivo seleccionado.
- **Archivos Permitidos:** `frontend/src/components/SimulationControls.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - Al completarse `campana` y `cultivoAnterior`, se dispara automáticamente el pedido/precarga de los datos históricos del lote.
  - La tarjeta `RecommendationPanel` (y `WhatIfPanel`) permanece oculta hasta que el usuario presione el botón **`"Planificar"`** en `CampaignConfigPanel`.
  - Si el usuario cambia el objetivo o los sliders *What-If* luego de planificar, la recomendación se actualiza automáticamente.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-8: Refinamiento UX/UI de `"Info general"` y Mapa GIS (Fechas humanas, Glosario, Cero Hex Hardcodeados y Anti-clutter)
- **Objetivo:** Refinar `"Info general"` (`TelemetryCards.tsx`) y el visor satelital (`MapView.tsx`) para cumplir el 100% de [`SKILLS_FRONTEND.md`](./SKILLS_FRONTEND.md) (fechas en formato humano `"8 nov. 2026"`, glosario obligatorio §3.3, aviso de resolución zonal en capas SMAP/IMERG al hacer zoom, ocultamiento automático de pistas tras el primer clic y colores desde `mapColors.ts`).
- **Archivos Permitidos:** `frontend/src/utils/formatters.ts`, `frontend/src/components/TelemetryCards.tsx`, `frontend/src/components/MapView.tsx`, `frontend/src/data/demoFields.ts`, `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - **Pregunta guía de `"Info general"` (§1):** Responder `"¿Cómo está mi lote hoy?"` en `< 5s` con un resumen claro y las 2 tarjetas semánticas (Agua/Lluvias en azul `#4A7B9D` y Calor/Suelo en naranja `#F05D23`).
  - **Glosario obligatorio (§3.3) y formato de datos (§3.4):**
    - `Agua en las raíces`, `Humedad para sembrar`, `Lluvias de los últimos 3 meses`, `Riesgo de golpe de calor`, `Materia orgánica del suelo` y `Tipo de suelo`, cada uno con su tooltip explicativo corto.
    - Porcentajes enteros emparejados con su interpretación cualitativa (`"34% · Reserva ajustada"`), anomalías con signo (`"−24%"`, `"+7%"`), coordenadas con máximo 3 decimales y fechas en formato humano (`"8 nov. 2026"`).
  - **Pautas de Mapa GIS (§4.1 y §5):**
    - Botones de modo en lenguaje natural: `Lotes de ejemplo`, `Dibujar mi lote`, `Tocar un punto`.
    - Ocultar el mensaje de ayuda de `"Tocar un punto"` automáticamente después del primer clic en el mapa.
    - Mostrar aviso sutil de resolución zonal (`"Esta capa muestra la tendencia de la zona, no el detalle del lote."`) cuando una capa de baja resolución nativa (`Agua en el suelo` o `Lluvias recientes`) se visualiza con zoom cercano.
    - Reemplazar todos los colores hexadecimales inline de `MapView.tsx` y `demoFields.ts` por `THEME_COLORS` (`src/theme/mapColors.ts`) y clases CSS.
- **Especificación Técnica:**
  1. Crear `frontend/src/utils/formatters.ts` con funciones para formatear fechas ISO a formato humano (`formatHumanDate`, `formatShortHumanDate`), porcentajes enteros y anomalías con signo (`−`).
  2. Actualizar `frontend/src/components/TelemetryCards.tsx` aplicando el glosario §3.3, valores enteros + etiquetas cualitativas, fecha humana y gaveta opcional `"Ver detalle del suelo"`.
  3. Actualizar `frontend/src/components/MapView.tsx` y `frontend/src/data/demoFields.ts` para usar `THEME_COLORS`, detectar el nivel de zoom para la nota de resolución zonal y ocultar la pista interactiva tras el primer clic.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-17: Precarga Automática de Datos Históricos al Completar Campaña/Cultivo y Botón `"Planificar"`
- **Objetivo:** Separar la carga de datos históricos (automática apenas el usuario completa campaña y cultivo antecesor) de la visualización de la recomendación de cultivo, la cual se muestra al presionar el botón **`"Planificar"`** según el objetivo seleccionado.
- **Archivos Permitidos:** `frontend/src/components/SimulationControls.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - Al completarse `campana` y `cultivoAnterior`, se dispara automáticamente el pedido/precarga de los datos históricos del lote.
  - La tarjeta `RecommendationPanel` (y `WhatIfPanel`) permanece oculta hasta que el usuario presione el botón **`"Planificar"`** en `CampaignConfigPanel`.
  - Si el usuario cambia el objetivo o los sliders *What-If* luego de planificar, la recomendación se actualiza automáticamente.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-9: Pestaña `"Información histórica"` (Línea de Tiempo de 10 Años Sincronizada en Vivo con el Mapa + Desplegable de Variables)
- **Objetivo:** Implementar la experiencia de `"Información histórica"` donde el productor desliza el año en una ventana de 10 años (`2017–2026`) y ve cambiar en tiempo real el lote en el mapa y la fecha de la capa satelital de la NASA, mostrando por defecto la evolución de los cultivos sembrados y permitiendo cambiar de variable histórica mediante un menú desplegable.
- **Archivos Permitidos:**
  - `frontend/src/data/historicalData.ts`
  - `frontend/src/components/HistoricalPanel.tsx`
  - `frontend/src/components/MapView.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - **Sincronización en tiempo real con el Mapa (2017–2026):** Al mover el año, el polígono del lote cambia de color y etiqueta en el mapa según el año y la variable elegida, y la fecha de la capa satelital de NASA GIBS se actualiza al año correspondiente.
  - **Vista por defecto + Menú desplegable de variables históricas:**
    - Por defecto muestra la **Evolución de los cultivos sembrados** (rotación año por año, familia del cultivo y rinde/resultado).
    - Incluye un selector desplegable para cambiar el dato histórico visualizado a:
      1. `Cultivos sembrados en el lote` *(por defecto)*
      2. `Lluvias acumuladas y agua en el suelo` (`--color-water-rain`)
      3. `Evaporación y demanda de agua del ambiente` (`--color-water-rain` / `--color-gold-yellow`)
      4. `Temperatura y días de golpe de calor` (`--color-heat-soil`)
      5. `Materia orgánica del suelo` (`--color-heat-soil` / `--color-earth-brown`)
  - **Cumplimiento estricto de `SKILLS_FRONTEND.md`:** Cero siglas técnicas, máximo 3–4 métricas por tarjeta, colores semánticos (azul = agua, naranja = calor/suelo, verde = cultivos/decisión) y controles accesibles.
- **Especificación Técnica:**
  1. Crear `frontend/src/data/historicalData.ts` con series históricas de 10 años (`2017–2026`) por lote/coordenada y metadatos de las 5 variables históricas (incluyendo color de lote en el mapa y capa NASA GIBS sugerida).
  2. Crear `frontend/src/components/HistoricalPanel.tsx` con el control deslizante de año (`2017–2026`) + botón Reproducir/Pausar, el desplegable de variable histórica, el resumen del año seleccionado y la visualización limpia de los 10 años (línea de cultivos por defecto o barras interactivas de la variable elegida).
  3. Actualizar `frontend/src/components/MapView.tsx` y `frontend/src/App.tsx` para que, cuando la pestaña `"Información histórica"` esté activa, el mapa reciba el año histórico seleccionado (`historicalYear`), la fecha satelital histórica y el estilo/etiqueta dinámica de cada lote en ese año.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-17: Precarga Automática de Datos Históricos al Completar Campaña/Cultivo y Botón `"Planificar"`
- **Objetivo:** Separar la carga de datos históricos (automática apenas el usuario completa campaña y cultivo antecesor) de la visualización de la recomendación de cultivo, la cual se muestra al presionar el botón **`"Planificar"`** según el objetivo seleccionado.
- **Archivos Permitidos:** `frontend/src/components/SimulationControls.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - Al completarse `campana` y `cultivoAnterior`, se dispara automáticamente el pedido/precarga de los datos históricos del lote.
  - La tarjeta `RecommendationPanel` (y `WhatIfPanel`) permanece oculta hasta que el usuario presione el botón **`"Planificar"`** en `CampaignConfigPanel`.
  - Si el usuario cambia el objetivo o los sliders *What-If* luego de planificar, la recomendación se actualiza automáticamente.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-10: Rediseño del Header en Marrón/Terracota y Pestañas estilo Carpeta de Archivo Físico con Pestaña Activa Resaltada
- **Objetivo:** Reemplazar el fondo verde del Header por una paleta cálida marrón/terracota y transformar la barra de navegación en pestañas de carpeta de archivo físico ancladas al borde inferior del Header (no botones flotantes), resaltando claramente la pestaña activa conectada con el lienzo crema inferior.
- **Archivos Permitidos:** `frontend/src/index.css`, `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/SKILLS_FRONTEND.md`
- **Decisiones Acordadas con el Desarrollador:**
  - **Header marrón/terracota:** Usar tonos tierra/terracota (`--color-header-bg: #7A442A` / `--color-earth-brown: #8C5A3C` y `--color-earth-brown-dark: #633D26`) en lugar del verde.
  - **Pestañas de carpeta física (File Folder Tabs):** Las pestañas se apoyan directamente sobre la línea inferior del Header (`border-radius` superior redondeado y base recta `10px 10px 0 0`, sin flotar en el aire). La pestaña activa se funde con el fondo crema (`--color-bg: #FFF5E0`), sobresale ligeramente en altura, lleva un borde superior de acento terracota (`--color-heat-soil`) y tipografía destacada.
- **Especificación Técnica:**
  1. Definir en `frontend/src/index.css` los tokens de terracota/marrón para el Header y pestañas de carpeta (`--color-terracotta`, `--color-terracotta-dark`, `--color-folder-tab-inactive`).
  2. Ajustar la estructura y estilos de `.top-navbar` y `.top-nav-tabs` en `frontend/src/App.tsx` y `frontend/src/App.css` para que las pestañas queden alineadas al borde inferior (`align-self: flex-end`) emulando solapas de carpeta de archivo físico.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b`

---

### `[x]` FRONT-11: Simplificación del Mapa GIS: Eliminación del modo `"Tocar un punto"`
- **Objetivo:** Remover por completo la opción `"Tocar un punto"` (`point`) del mapa interactivo, dejando únicamente `"Lotes de ejemplo"` (`demo`) y `"Dibujar lote"` (`polygon`).
- **Archivos Permitidos:** `frontend/src/types/api.ts`, `frontend/src/components/MapView.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - En el mapa no es necesario el botón ni el modo `"Tocar un punto"`.
  - Mantener la selección sobre los lotes de ejemplo y la herramienta para dibujar el polígono del lote.
- **Especificación Técnica:**
  1. Actualizar `SelectionMode` en `frontend/src/types/api.ts` a `'demo' | 'polygon'`.
  2. Eliminar el botón `"Tocar un punto"`, el estado `hasClickedPointOnce`, el mensaje `.map-point-hint` y el handler `onSelectPoint` de `frontend/src/components/MapView.tsx` y `frontend/src/App.tsx`.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b`

---

### `[x]` FRONT-12: Reemplazo de Preguntas en Títulos por Títulos de Pestaña y Lenguaje Formal Agronómico
- **Objetivo:** Eliminar todas las preguntas de los títulos y subtítulos (como `¿Cómo venís y qué vas a sembrar?`, `¿Cómo está mi lote hoy?`, `¿Cómo evolucionó tu campo?`, `¿Qué te conviene sembrar?`, `¿Qué pasa si...?`), colocando en su lugar el título correspondiente de cada pestaña/sección conservando la tipografía `Newsreader` (`--font-heading`) y el color `--color-primary`, y reemplazando el lenguaje informal/voseo por un español técnico-profesional claro y formal en toda la aplicación.
- **Archivos Permitidos:**
  - `frontend/src/components/SimulationControls.tsx`
  - `frontend/src/components/RecommendationPanel.tsx`
  - `frontend/src/components/TelemetryCards.tsx`
  - `frontend/src/components/HistoricalPanel.tsx`
  - `frontend/src/services/apiClient.ts`
  - `frontend/src/data/demoFields.ts`
  - `frontend/src/data/historicalData.ts`
  - `frontend/SKILLS_FRONTEND.md`
- **Decisiones Acordadas con el Desarrollador:**
  - **Cero preguntas en títulos:**
    - En la pestaña `Planificación de campaña`: el título principal es **`Planificación de campaña`**; las sub-secciones usan títulos formales afirmativos (**`Recomendación de cultivo`** y **`Simulación de escenarios climáticos`**), y el selector de objetivo se titula **`Prioridad de manejo`** (en lugar de `¿Qué querés priorizar?`).
    - En la pestaña `Info general`: el título principal es **`Info general`**.
    - En la pestaña `Información histórica`: el título principal es **`Información histórica`** y el selector de métrica se titula **`Variable histórica a visualizar`** (en lugar de `¿Qué dato histórico querés ver?`).
  - **Tipografía y color:** Conservar `var(--font-heading)` (`Newsreader`) y `var(--color-primary)` (`#4B5B2D`) en todos los `.section-title`.
  - **Lenguaje formal:** Reemplazar todas las expresiones informales o en voseo (`venís`, `querés`, `sembrá`, `probá`, `mové`, `tocá`, `banque`, `tu lote`) por redacción profesional, objetiva y clara (` Cultivo recomendado: ...`, `Seleccione...`, `Deslice el selector...`, `soporte el déficit hídrico`, `el lote`).
- **Especificación Técnica:**
  1. Actualizar los encabezados `h2.section-title` y etiquetas en `SimulationControls.tsx`, `RecommendationPanel.tsx`, `TelemetryCards.tsx` y `HistoricalPanel.tsx`.
  2. Revisar y formalizar los textos generados en `apiClient.ts`, `demoFields.ts`, `historicalData.ts` y `MapView.tsx`.
  3. Actualizar `SKILLS_FRONTEND.md` para reflejar la regla de títulos sin preguntas y tono formal.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b`

---

### `[x]` FRONT-13: Diversificación Cromática de Botones y Controles Seleccionados (No Todo Verde)
- **Objetivo:** Evitar que todos los botones y estados de selección sean verdes, distribuyendo la paleta terrosa, terracota, ocre y azul agua en los controles interactivos y reservando el verde (`--color-primary`) para los títulos y el indicador del cultivo recomendado.
- **Archivos Permitidos:** `frontend/src/index.css`, `frontend/src/App.css`, `frontend/src/components/SimulationControls.tsx`, `frontend/src/components/HistoricalPanel.tsx`
- **Decisiones Acordadas con el Desarrollador:**
  - Los botones y selecciones no deben ser todos verdes.
  - Utilizar tonos marrón tierra (`--color-earth-brown` / `--color-earth-brown-dark`), terracota (`--color-heat-soil-dark` / `--color-terracotta`), ocre dorado (`--color-gold-yellow-dark`) y azul hidrológico (`--color-water-rain-dark`) según el contexto del botón:
    - Selector de modo y lotes en el mapa: marrón tierra / terracota.
    - Botones de campaña: `Campaña gruesa (verano)` en tono terracota/ocre cálido y `Campaña fina (invierno)` en azul pizarra (`--color-water-rain-dark`).
    - Tarjetas de prioridad de manejo (`objetivo_productor`): borde y acento según su naturaleza (`Seguridad hídrica` en azul `--color-water-rain`, `Equilibrio` en marrón tierra `--color-earth-brown`, `Conservación del suelo` en terracota `--color-heat-soil-dark`).
    - Botones de línea de tiempo histórica (`Recorrer años`, píldoras de año `2017–2026`, `Volver al dato real`): tonos marrón tierra y terracota.
- **Especificación Técnica:**
  1. Ajustar las clases de botones activos y tarjetas seleccionadas en `frontend/src/App.css` y `frontend/src/components/SimulationControls.tsx`.
  2. Verificar contraste WCAG AA en todos los estados activos y seleccionados.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-17: Precarga Automática de Datos Históricos al Completar Campaña/Cultivo y Botón `"Planificar"`
- **Objetivo:** Separar la carga de datos históricos (automática apenas el usuario completa campaña y cultivo antecesor) de la visualización de la recomendación de cultivo, la cual se muestra al presionar el botón **`"Planificar"`** según el objetivo seleccionado.
- **Archivos Permitidos:** `frontend/src/components/SimulationControls.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - Al completarse `campana` y `cultivoAnterior`, se dispara automáticamente el pedido/precarga de los datos históricos del lote.
  - La tarjeta `RecommendationPanel` (y `WhatIfPanel`) permanece oculta hasta que el usuario presione el botón **`"Planificar"`** en `CampaignConfigPanel`.
  - Si el usuario cambia el objetivo o los sliders *What-If* luego de planificar, la recomendación se actualiza automáticamente.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-14: Header Sólido `#3A0C00`, Eliminación de Pestaña Chat y Alineación de Pestañas al 40% del Panel Derecho
- **Objetivo:** Aplicar el color sólido `#3A0C00` (sin gradiente) al Header, remover por completo la pestaña `Chat` y restringir el contenedor de las 3 pestañas de carpeta física para que no supere el 40% de ancho correspondiente al panel derecho.
- **Archivos Permitidos:** `frontend/src/index.css`, `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/SKILLS_FRONTEND.md`
- **Decisiones Acordadas con el Desarrollador:**
  - **Header sólido `#3A0C00`:** Sin gradiente, usando el token `--color-header-bg: #3A0C00`.
  - **Sin pestaña Chat:** Eliminar el botón `Chat` y su tipo asociado, dejando únicamente las 3 pestañas operativas (`Planificación de campaña`, `Info general`, `Información histórica`).
  - **Ancho máximo del 40%:** Alinear la grilla del Header (`60% 40%`) con el layout inferior para que las pestañas se ubiquen exactamente sobre el 40% del panel derecho y nunca excedan ese ancho.
- **Especificación Técnica:**
  1. Definir `--color-header-bg: #3A0C00` en `frontend/src/index.css`.
  2. Remover la pestaña `Chat` y el ícono `MessageSquare` de `frontend/src/App.tsx`.
  3. Configurar `.top-navbar` con `grid-template-columns: 60% 40%` y `.top-nav-tabs` con `grid-template-columns: repeat(3, minmax(0, 1fr))` dentro del 40% derecho en `frontend/src/App.css`.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-17: Precarga Automática de Datos Históricos al Completar Campaña/Cultivo y Botón `"Planificar"`
- **Objetivo:** Separar la carga de datos históricos (automática apenas el usuario completa campaña y cultivo antecesor) de la visualización de la recomendación de cultivo, la cual se muestra al presionar el botón **`"Planificar"`** según el objetivo seleccionado.
- **Archivos Permitidos:** `frontend/src/components/SimulationControls.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - Al completarse `campana` y `cultivoAnterior`, se dispara automáticamente el pedido/precarga de los datos históricos del lote.
  - La tarjeta `RecommendationPanel` (y `WhatIfPanel`) permanece oculta hasta que el usuario presione el botón **`"Planificar"`** en `CampaignConfigPanel`.
  - Si el usuario cambia el objetivo o los sliders *What-If* luego de planificar, la recomendación se actualiza automáticamente.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-15: Integración de las Pestañas de Carpeta al Componente Derecho Superpuestas sobre el Header
- **Objetivo:** Mover las 3 pestañas de carpeta física dentro del componente derecho (`aside.right-analysis-pane`) de modo que nazcan desde la tarjeta/panel derecho y se proyecten hacia arriba superponiéndose directamente sobre el Header `#3A0C00`.
- **Archivos Permitidos:** `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/SKILLS_FRONTEND.md`
- **Decisiones Acordadas con el Desarrollador:**
  - Las pestañas forman parte estructural del componente derecho (40% de ancho) y no del `<header>`.
  - Se superponen visualmente sobre la franja inferior del Header `#3A0C00` (`margin-top` negativo y `z-index` superior al Header), fundiendo la pestaña activa sin costura con el cuerpo del panel derecho (`.right-folder-body`).
- **Especificación Técnica:**
  1. En `frontend/src/App.tsx`, trasladar `<nav className="top-nav-tabs">` desde `<header className="top-navbar">` hacia el interior de `<aside className="right-analysis-pane">`, envolviendo el contenido desplazable en `<div className="right-folder-body">`.
  2. En `frontend/src/App.css`, configurar `.right-analysis-pane` con `overflow: visible` y `z-index: 25`, aplicar `margin-top: -42px` a `.top-nav-tabs` para superponer las solapas sobre `.top-navbar`, y delegar el `overflow-y: auto` a `.right-folder-body`.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-17: Precarga Automática de Datos Históricos al Completar Campaña/Cultivo y Botón `"Planificar"`
- **Objetivo:** Separar la carga de datos históricos (automática apenas el usuario completa campaña y cultivo antecesor) de la visualización de la recomendación de cultivo, la cual se muestra al presionar el botón **`"Planificar"`** según el objetivo seleccionado.
- **Archivos Permitidos:** `frontend/src/components/SimulationControls.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - Al completarse `campana` y `cultivoAnterior`, se dispara automáticamente el pedido/precarga de los datos históricos del lote.
  - La tarjeta `RecommendationPanel` (y `WhatIfPanel`) permanece oculta hasta que el usuario presione el botón **`"Planificar"`** en `CampaignConfigPanel`.
  - Si el usuario cambia el objetivo o los sliders *What-If* luego de planificar, la recomendación se actualiza automáticamente.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-16: Diferir Estrategia de Rotación hasta Seleccionar Campaña y Cultivo Antecesor (Con Estado Vacío y Carga Asíncrona)
- **Objetivo:** No mostrar la tarjeta de estrategia de rotación (`RecommendationPanel`) ni el simulador `WhatIfPanel` hasta que el usuario seleccione explícitamente tanto el **tipo de campaña** como el **cultivo antecesor**, dando tiempo a la API para ejecutar las requests asíncronas.
- **Archivos Permitidos:** `frontend/src/components/SimulationControls.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - `campana` y `cultivoAnterior` inician sin selección (`null`) al cargar la aplicación.
  - Al seleccionar un lote en el mapa, se actualizan las coordenadas y telemetría de `Info general`, pero no se pre-completan automáticamente campaña ni cultivo antecesor.
  - Mientras falte alguno de los dos campos, se muestra únicamente `CampaignConfigPanel` junto a un aviso limpio indicando que debe completar ambos campos para generar la estrategia de rotación.
  - Una vez completados ambos campos, se invoca `simulateCropRotation` de forma asíncrona (con estado de carga tipo skeleton y debounce en sliders).
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-17: Precarga Automática de Datos Históricos al Completar Campaña/Cultivo y Botón `"Planificar"`
- **Objetivo:** Separar la carga de datos históricos (automática apenas el usuario completa campaña y cultivo antecesor) de la visualización de la recomendación de cultivo, la cual se muestra al presionar el botón **`"Planificar"`** según el objetivo seleccionado.
- **Archivos Permitidos:** `frontend/src/components/SimulationControls.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - Al completarse `campana` y `cultivoAnterior`, se dispara automáticamente el pedido/precarga de los datos históricos del lote.
  - La tarjeta `RecommendationPanel` (y `WhatIfPanel`) permanece oculta hasta que el usuario presione el botón **`"Planificar"`** en `CampaignConfigPanel`.
  - Si el usuario cambia el objetivo o los sliders *What-If* luego de planificar, la recomendación se actualiza automáticamente.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`


---

### `[x]` FRONT-18: Pantalla de Inicio de Sesión y Registro Conectada a `BACK-3` (Con Modo Demo)
- **Objetivo:** Implementar la vista inicial de autenticación (Iniciar sesión / Crear cuenta) alineada con el sistema de diseño *Analogue-Modern Field Journal* (`SKILLS_FRONTEND.md`) y conectada a los endpoints de Supabase Auth en FastAPI (`BACK-3`), permitiendo también ingresar en modo demostración.
- **Archivos Permitidos:**
  - `frontend/src/types/api.ts`
  - `frontend/src/services/authClient.ts`
  - `frontend/src/components/AuthScreen.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - **Flujo de entrada:** Pantalla de acceso al abrir la aplicación con opción de alternar entre **Iniciar sesión** y **Crear cuenta**, más un botón secundario **"Explorar en modo demo"** para acceder al mapa y planificación sin autenticarse.
  - **Campos del formulario:**
    - *Iniciar sesión:* Email y Contraseña (con botón para mostrar/ocultar contraseña).
    - *Crear cuenta:* Nombre completo, Email y Contraseña (con botón para mostrar/ocultar contraseña).
  - **Persistencia de sesión:** Guardar el `access_token` (JWT) en `localStorage` y validarlo al iniciar la app mediante `GET /api/v1/auth/me`. Mostrar en el header el usuario conectado con acción **"Cerrar sesión"** (o **"Iniciar sesión"** si ingresó en modo demo).
  - **Conexión y manejo de errores:** Conectar directo a FastAPI (`POST /api/v1/auth/login`, `POST /api/v1/auth/register`, `GET /api/v1/auth/me` usando `VITE_API_URL` o `http://localhost:8000` por defecto). Si el backend no responde, mostrar un aviso claro y respetuoso sugiriendo verificar el servidor o usar el modo demo.
- **Especificación Técnica:**
  1. Agregar en `frontend/src/types/api.ts` los contratos `AuthRegisterRequest`, `AuthLoginRequest`, `UserProfile` y `AuthResponse`.
  2. Crear `frontend/src/services/authClient.ts` con `loginUser`, `registerUser`, `fetchCurrentUser`, y manejo de almacenamiento seguro del token en `localStorage`.
  3. Crear `frontend/src/components/AuthScreen.tsx` respetando los tokens CSS (`--color-header-bg`, `--color-bg`, `--color-bg-card`, `--color-primary`, `--color-terracotta`, `--color-text`), tipografía `Newsreader` + `Plus Jakarta Sans`, lenguaje formal sin voseo y contraste WCAG AA.
  4. Integrar el estado de sesión en `frontend/src/App.tsx` y los estilos en `frontend/src/App.css` (incluyendo el indicador de usuario y botón de sesión en `.top-navbar`).
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`


---

### `[x]` FRONT-19: Rebranding a **Ereia** (Fraunces 600, Ícono PNG sin recuadro), Header `#FFF5E0` y Fondo Salvia `#A8BC82`
- **Objetivo:** Reemplazar la marca *Shark Attack* por **Ereia** en tipografía **Fraunces SemiBold (600)** bicolor (`Ere` en `#9E472A` e `ia` en `#4B5B2D`), incorporar el nuevo ícono PNG de brote sin recuadro junto al título, mover *"Soporte para el cultivo"* al costado de **Ereia**, y actualizar el header a `#FFF5E0`, el fondo principal a `#A8BC82` (variante más clara de `#8AA15B`) y la tarjeta de inicio de sesión al mismo color del header (`#FFF5E0`).
- **Archivos Permitidos:**
  - `frontend/public/ereia-icon.png`
  - `frontend/index.html`
  - `frontend/src/index.css`
  - `frontend/src/components/BrandBlock.tsx`
  - `frontend/src/components/AuthScreen.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - **Marca:** Wordmark **Ereia** en `Fraunces` peso `600` (`40px`), con `"Ere"` en `#9E472A` (`--color-terracotta`) e `"ia"` en `#4B5B2D` (`--color-primary`), sin fondo ni caja alrededor del texto ni del ícono PNG.
  - **Subtítulo en línea:** *"Soporte para el cultivo"* ubicado al costado de **Ereia** para permitir mayor tamaño del título principal.
  - **Paleta actualizada:** Header superior y tarjeta `.auth-card` en `#FFF5E0` (`--color-header-bg`), y fondo general de la aplicación en `#A8BC82` (`--color-bg`, tono más claro que `#8AA15B`).
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`


---

### `[x]` FRONT-20: Refinamiento de Panel Derecho, Pestañas tipo Carpeta y Header (Tonos Arena, Márgenes y Sombras sin Bordes)
- **Objetivo:** Unificar cromáticamente la pestaña activa y el panel derecho en tono arena claro (`#EAD9C0`), oscurecer las pestañas inactivas (`#C5A882`), alinear los márgenes laterales de las pestañas con el contenido interno y reemplazar los bordes de separación por sombras sutiles.
- **Archivos Permitidos:**
  - `frontend/src/index.css`
  - `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - **Jerarquía de tonos en carpeta derecha:** `--color-folder-pane: #EAD9C0` para `.right-analysis-pane`, `.right-folder-body` y `.nav-tab-btn.active`; `--color-folder-tab-inactive: #C5A882` (y `--color-folder-tab-hover: #D6BE9E`) para pestañas desactivadas.
  - **Alineación de márgenes:** `.top-nav-tabs` con `padding: 0 24px` para coincidir con el `padding` horizontal de `24px` en `.right-folder-body`.
  - **Sin bordes, con sombras:** Eliminación de bordes en `.left-map-pane`, `.nav-tab-btn`, `.nav-tab-btn.active`, `.right-folder-body` y `.top-navbar`, usando sombras sutiles en el panel derecho y pestaña activa, y `var(--shadow-md)` en `.top-navbar`.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`


---

### `[x]` FRONT-21: Segundo Header Colapsable de Gestión de Lotes del Usuario y Delimitación de Nuevos Campos (`BACK-4`)
- **Objetivo:** Reemplazar el selector flotante de `"Lotes de ejemplo"` por una barra superior colapsable ubicada debajo del header principal en el sector del mapa, que liste los campos reales del usuario desde la base de datos (`GET /api/v1/fields`) y permita delimitar y guardar nuevos campos con nombre (`POST /api/v1/fields`).
- **Archivos Permitidos:**
  - `frontend/src/types/api.ts`
  - `frontend/src/services/fieldsClient.ts`
  - `frontend/src/components/FieldsSubheader.tsx`
  - `frontend/src/components/MapView.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - **Sin lotes estáticos de ejemplo:** En usuario autenticado se consultan sus campos en `GET /api/v1/fields`; en **Modo demo** se autentica contra el backend con un usuario demo fijo (`VITE_DEMO_EMAIL` / `VITE_DEMO_PASSWORD`) para cargar los lotes demo desde la base de datos.
  - **Barra flotante colapsable en el sector del mapa:** En estado colapsado muestra **`Mis campos (N)`** y **`Nuevo campo`**; al desplegar, **`Mis campos`** pasa a **`X`**, aparecen las pills de los campos del usuario hacia la derecha sin barra de fondo (alternando 5 colores de la paleta) y **`Nuevo campo`** se compacta a un botón con solo ícono de lápiz.
  - **Persistencia de polígono y centroide:** Al guardar un nuevo campo se envía `nombre`, `lat`, `lon` y `hectareas` a `POST /api/v1/fields`, y los vértices del polígono se cachean en `localStorage` por `field_id` para dibujarlo en el mapa.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`


---

### `[x]` FRONT-22: Refinamiento UX/UI de Campañas, Objetivo Animado y Listado Interactivo de Estrategia de Rotación
- **Objetivo:** Simplificar las etiquetas y controles de planificación (`Verano`/`Invierno`, `Cultivo`, `Objetivo` con expansión animada al pasar el mouse) y convertir el listado de estrategia de rotación en filas expandibles al hacer clic, con enlace discreto `+ Mas...` sin contenedor.
- **Archivos Permitidos:**
  - `frontend/src/components/SimulationControls.tsx`
  - `frontend/src/components/RecommendationPanel.tsx`
  - `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - **Campañas y cultivo antecesor:** Botones **`Verano`** (tooltip `"Campaña gruesa"`, amarillo) e **`Invierno`** (tooltip `"Campaña fina"`, azul) sin borde, con cambio de tono en `:hover` y color más oscuro al seleccionar; selector con placeholder `"Cultivo"` y exactamente la misma altura (`40px`).
  - **Objetivo:** Renombrado de `"Prioridad de manejo"` a `"Objetivo"`, con las 3 pills del mismo tono tierra sin borde, altura uniforme (`min-height: 56px`) y animación de expansión al hacer `:hover` para mostrar la descripción.
  - **Estrategia de rotación:** Eliminado el encabezado `"Comparativa de cultivos para esta campaña"`, filas del listado expandibles al tocarlas para ver el detalle de cada cultivo, y botón de fundamentos **`+ Mas...`** sin contenedor en la esquina inferior derecha.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`


---

### `[x]` FRONT-23: Estrategia de Rotación Unificada en Listado Expandible, Campaña Actual (`Invierno` Desactivado) y Mapa Limpio sin Capas GIBS
- **Objetivo:** Unificar la recomendación dentro del listado de cultivos (cada ítem expande su tarjeta completa al tocarlo), enfocar la recomendación exclusivamente en la campaña actual (`verano`), desactivar `Invierno` con tooltip `"A futuro"` y eliminar el panel flotante de capas satelitales sobre el mapa.
- **Archivos Permitidos:**
  - `frontend/src/components/RecommendationPanel.tsx`
  - `frontend/src/components/SimulationControls.tsx`
  - `frontend/src/components/MapView.tsx`
  - `frontend/src/services/apiClient.ts`
  - `frontend/src/App.tsx`
  - `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - **Listado único expandible:** Se elimina la tarjeta fija superior y el bloque `"Rotación sugerida para el año"`; al tocar cualquier cultivo del listado se expande su tarjeta completa con anillo de puntaje, barras de pilares y enlace `+ Mas...`.
  - **Campaña actual (`verano`):** `Invierno` queda desactivado (`disabled`) con ícono de información y tooltip `"A futuro"`, alineado con `CONTEXT.md`.
  - **Mapa limpio:** Se elimina el panel flotante inferior de capas temáticas NASA GIBS sobre el mapa, conservando el visor satelital base y etiquetas.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`
