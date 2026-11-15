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
| **FRONT-24** | Alineación de Contrato Auth Frontend–Backend (`BACK-3` / Supabase) y Configuración `VITE_API_URL` | `frontend/.env.example`, `frontend/src/types/api.ts`, `frontend/src/services/authClient.ts`, `frontend/src/components/AuthScreen.tsx` | `FRONT-18`, `FRONT-23` | `[x]` |
| **FRONT-25** | Actualización de Credenciales Demo (`demoereia@gmail.com`) para Autenticación Real en Supabase | `frontend/.env.example`, `frontend/src/services/fieldsClient.ts` | `FRONT-24` | `[x]` |
| **FRONT-26** | Envío y Persistencia de Polígono Dibujado en `/api/v1/fields` (`BACK-6`) | `frontend/src/types/api.ts`, `frontend/src/services/fieldsClient.ts`, `frontend/src/App.tsx`, `frontend/TASKS_FRONTEND.md` | `FRONT-21`, `FRONT-24` | `[x]` |
| **FRONT-27** | Header Limpio, Pestañas de Archivero Alineadas a la Izquierda y Barra de Campos en Una Fila con Pill Terracota de Ajustes | `frontend/src/components/BrandBlock.tsx`, `frontend/src/components/FieldsSubheader.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css` | `FRONT-20`, `FRONT-26` | `[x]` |
| **FRONT-28** | Card Flotante Glass con Diseño de Fichero para Ajustes de Usuario (`Usuario`, `Campos`, `Expandir mapa`, `Idioma`) | `frontend/src/components/UserSettingsModal.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css` | `FRONT-27` | `[x]` |
| **FRONT-29** | Sincronización de Colores Vivos (sin Verde) entre Pills de Campos y Polígonos del Mapa con Mayor Opacidad | `frontend/src/theme/mapColors.ts`, `frontend/src/components/FieldsSubheader.tsx`, `frontend/src/components/MapView.tsx`, `frontend/src/App.css` | `FRONT-27` | `[x]` |
| **FRONT-30** | Formulario de Edición de Perfil (`Nombre`, `Correo`, `Contraseña`) y Botón `Cerrar sesión` en Pestaña `Usuario` | `frontend/src/types/api.ts`, `frontend/src/services/authClient.ts`, `frontend/src/components/UserSettingsModal.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css` | `FRONT-28` | `[x]` |
| **FRONT-31** | Listado de Campos del Usuario con Menú Desplegable (`⋮`) para Renombrar y Borrar en Pestaña `Campos` | `frontend/src/types/api.ts`, `frontend/src/services/fieldsClient.ts`, `frontend/src/components/UserSettingsModal.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css` | `FRONT-28`, `FRONT-29` | `[x]` |
| **FRONT-32** | Edición Interactiva de Polígono de un Campo Existente (`Editar superficie`) desde el Menú Desplegable | `frontend/src/components/MapView.tsx`, `frontend/src/components/FieldsSubheader.tsx`, `frontend/src/components/UserSettingsModal.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css` | `FRONT-31` | `[x]` |
| **FRONT-33** | Filtro Previo por Provincias (Región Pampeana), Mapa 3D de Argentina y Optimización de Rendimiento | `frontend/src/data/argentinaProvinces.json`, `frontend/src/utils/geo.ts`, `frontend/src/components/ProvinceSelectorScreen.tsx`, `frontend/src/components/MapView.tsx`, `frontend/src/services/authClient.ts`, `frontend/src/types/api.ts`, `frontend/src/theme/mapColors.ts`, `frontend/src/index.css`, `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/SKILLS_FRONTEND.md` | `FRONT-24`, `FRONT-26` | `[x]` |
| **FRONT-34** | Conexión de `Info general` a `GET /api/v1/telemetry` al Seleccionar Campo, Fallback de Suelo, Fix de Riesgo Térmico y Último Cultivo desde BD (`BACK-20`) | `frontend/src/types/api.ts`, `frontend/src/services/apiClient.ts`, `frontend/src/services/fieldsClient.ts`, `frontend/src/components/TelemetryCards.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/TASKS_FRONTEND.md` | `FRONT-21`, `BACK-20` | `[x]` |
| **FRONT-35** | Datos Propios de Suelo/Topografía por Campo (`UserField`), Materia Orgánica en `%` y Consulta Dinámica de NASA POWER con `field_id` (`BACK-21..23`) | `frontend/src/types/api.ts`, `frontend/src/services/apiClient.ts`, `frontend/src/components/TelemetryCards.tsx`, `frontend/src/App.tsx`, `frontend/TASKS_FRONTEND.md` | `FRONT-34`, `BACK-21`, `BACK-22`, `BACK-23` | `[x]` |
| **FRONT-36** | Solapa Verde de Usuario en Panel Derecho (`Usuario` + `Idioma`) y Separación de `⋮` en Buscador (`Campos` + `Expandir mapa`) | `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/src/components/MapSearchBar.tsx`, `frontend/src/components/FieldsSubheader.tsx`, `frontend/src/components/UserSettingsModal.tsx`, `frontend/TASKS_FRONTEND.md` | `FRONT-31`, `FRONT-33` | `[x]` |
| **FRONT-37** | Encabezado de `Info general` sin Coordenadas ni Hectáreas (Solo Nombre del Campo sin Repetición) | `frontend/src/components/TelemetryCards.tsx`, `frontend/src/App.tsx`, `frontend/TASKS_FRONTEND.md` | `FRONT-35` | `[x]` |
| **FRONT-38** | Botones de Acción Principal en Verde Vivo Claro (`Planificar`, `Guardar campo`, `+ Nuevo campo`, `Iniciar sesión`, `Reproducir serie`) y Estados Deshabilitados Tenues | `frontend/src/index.css`, `frontend/src/App.css`, `frontend/SKILLS_FRONTEND.md`, `frontend/TASKS_FRONTEND.md` | `FRONT-36` | `[x]` |
| **FRONT-39** | Login Acoplado a la Derecha, Modo Demo Exclusivo en Inicio de Sesión y Cuaderno Rayado Izquierdo con Marca y Lema | `frontend/src/components/AuthScreen.tsx`, `frontend/src/App.css`, `frontend/TASKS_FRONTEND.md` | `FRONT-38` | `[x]` |
| **FRONT-40** | Envío de `field_id` y `Authorization` en `POST /api/v1/simulate` + Manejo de `401` / `404` / `422` | `frontend/src/types/api.ts`, `frontend/src/services/apiClient.ts`, `frontend/src/components/AuthScreen.tsx`, `frontend/src/components/RecommendationPanel.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/TASKS_FRONTEND.md` | `FRONT-35` | `[x]` |
| **FRONT-41** | Avisos Discretos de Dato Aproximado (`advertencias`, `suelo_advertencias`, `topo_advertencias`) sin Siglas Técnicas | `frontend/src/utils/formatters.ts`, `frontend/src/components/TelemetryCards.tsx`, `frontend/src/components/RecommendationPanel.tsx`, `frontend/src/App.css`, `frontend/TASKS_FRONTEND.md` | `FRONT-40` | `[x]` |
| **FRONT-42** | Polling de `reintento_en_curso` (`GET /api/v1/fields/{id}` cada 30 s), Spinner Discreto y Refresco + Aviso al Llegar Dato Real | `frontend/src/types/api.ts`, `frontend/src/services/fieldsClient.ts`, `frontend/src/App.tsx`, `frontend/src/components/TelemetryCards.tsx`, `frontend/src/App.css`, `frontend/TASKS_FRONTEND.md` | `FRONT-41` | `[x]` |
| **FRONT-43** | Panel de recomendación en lenguaje de productor: riesgo de año malo como frecuencia ("3 de cada 10 campañas"), rinde en qq/ha contra el normal de la zona, rango año malo / año bueno, detalle técnico desplegable y estados sin backend (último resultado real guardado, nunca datos de ejemplo) | `frontend/src/types/api.ts`, `frontend/src/components/RecommendationPanel.tsx`, `frontend/src/components/RiesgoRindeResumen.tsx` (nuevo), `frontend/src/components/AvisoEstadoDatos.tsx` (nuevo), `frontend/src/utils/formatters.ts`, `frontend/src/utils/lenguajeProductor.ts` (nuevo), `frontend/src/services/apiClient.ts`, `frontend/src/services/ultimoResultado.ts` (nuevo), `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/TASKS_FRONTEND.md` | `BACK-27` | `[x]` |
| **FRONT-44** | Registrar siembra y vista de seguimiento de campaña: avance del período que define el rinde, evolución semanal del riesgo, qué pasó con el clima desde la siembra y rinde esperado actualizado | `frontend/src/types/api.ts`, `frontend/src/services/fieldsClient.ts`, `frontend/src/components/RegistrarSiembraForm.tsx` (nuevo), `frontend/src/components/SeguimientoCampana.tsx` (nuevo), `frontend/src/utils/lenguajeProductor.ts`, `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/TASKS_FRONTEND.md` | `FRONT-36`, `BACK-29` | `[x]` |
| **FRONT-45** | Cerrar la campaña en curso (fecha de cosecha, rinde cosechado en qq/ha y notas) y borrarla con confirmación | `frontend/src/types/api.ts`, `frontend/src/services/fieldsClient.ts`, `frontend/src/components/AccionesCampana.tsx` (nuevo), `frontend/src/components/SeguimientoCampana.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/TASKS_FRONTEND.md` | `FRONT-37`, `BACK-30` | `[x]` |
| **FRONT-46** | *Información histórica* con datos reales (BACK-31): lluvia y agua en raíces por campaña con gráfico contra lo normal, cosechas del lote, rinde de la zona; sin datos inventados; el mapa colorea solo el lote seleccionado | `frontend/src/data/historicalData.ts`, `frontend/src/components/HistoricalPanel.tsx`, `frontend/src/components/MapView.tsx`, `frontend/src/services/apiClient.ts`, `frontend/src/types/api.ts`, `frontend/src/App.tsx`, `frontend/src/App.css` | `BACK-31` | `[x]` |

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

---

### `[x]` FRONT-24: Alineación de Contrato Auth Frontend–Backend (`BACK-3` / Supabase) y Configuración `VITE_API_URL`
- **Objetivo:** Dejar configurado el entorno del frontend para conectarse al backend FastAPI + Supabase Auth (`BACK-3`) y alinear los tipos y el flujo de login/registro con el contrato real de `backend/schemas.py`.
- **Archivos Permitidos:**
  - `frontend/.env.example`
  - `frontend/src/types/api.ts`
  - `frontend/src/services/authClient.ts`
  - `frontend/src/components/AuthScreen.tsx`
- **Decisiones Acordadas con el Desarrollador:**
  - **Configuración de API:** Se agrega `frontend/.env.example` (y `frontend/.env.local` para desarrollo local) con `VITE_API_URL=http://localhost:8000`.
  - **Contrato Auth (`BACK-3`):** `AuthResponse` acepta `access_token: string | null` y `requiere_confirmacion_email?: boolean` para manejar cuentas recién registradas que requieren confirmación por email en Supabase.
  - **Persistencia de sesión:** `authClient.ts` almacena y limpia `access_token` y `refresh_token` de forma consistente al iniciar y cerrar sesión.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-25: Actualización de Credenciales Demo (`demoereia@gmail.com`) para Autenticación Real en Supabase
- **Objetivo:** Actualizar las credenciales de fallback y de ejemplo del Modo Demo para usar la cuenta confirmada en Supabase (`demoereia@gmail.com` / `contraseñadedemo`), reemplazando el dominio ficticio `demo@ereia.app` que Supabase rechaza en validación de email.
- **Archivos Permitidos:**
  - `frontend/.env.example`
  - `frontend/src/services/fieldsClient.ts`
- **Decisiones Acordadas con el Desarrollador:**
  - El Modo Demo se autentica contra `/api/v1/auth/login` con `demoereia@gmail.com` / `contraseñadedemo` (sobrescribible vía `VITE_DEMO_EMAIL` y `VITE_DEMO_PASSWORD`).
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-26: Envío y Persistencia de Polígono Dibujado en `/api/v1/fields` (`BACK-6`)
- **Objetivo:** Enviar el polígono dibujado (`polygon: [number, number][]`) al crear un campo en `POST /api/v1/fields` y priorizar el polígono devuelto por el backend al listar los campos en `GET /api/v1/fields`.
- **Archivos Permitidos:**
  - `frontend/src/types/api.ts`
  - `frontend/src/services/fieldsClient.ts`
  - `frontend/src/App.tsx`
  - `frontend/TASKS_FRONTEND.md`
- **Decisiones Acordadas con el Desarrollador:**
  - `FieldCreateRequest` y `UserField` incluyen `polygon?: [number, number][] | null`.
  - `attachCachedPolygons` prioriza el `polygon` proveniente de Supabase y usa `localStorage` solo como respaldo para campos antiguos sin geometría en BD.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-27: Header Limpio, Pestañas de Archivero Alineadas a la Izquierda y Barra de Campos en Una Fila con Pill Terracota de Ajustes
- **Objetivo:** Limpiar el header eliminando el texto `"Soporte para el cultivo"`, el nombre de usuario y el botón de cerrar sesión; alinear las 3 pestañas del panel derecho al margen izquierdo (estilo archivero real) y ubicar la pill de configuración (ícono de engranaje sin texto) en terracota (`--color-terracotta`) manteniendo el alto de las pills de campos en una sola fila sin cortes ni recorte parcial, con flechas para desplazarlos.
- **Archivos Permitidos:**
  - `frontend/src/components/BrandBlock.tsx`
  - `frontend/src/components/FieldsSubheader.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - **Header limpio:** Se elimina `<p className="brand-subtitle">Soporte para el cultivo</p>` en `BrandBlock.tsx` y `.header-session-bar` del header en `App.tsx`.
  - **Pestañas tipo archivero:** `.top-nav-tabs` usa `display: flex` sin `padding` lateral, alineando las 3 pestañas principales al margen izquierdo del panel derecho.
  - **Pill terracota de ajustes y carrusel sin cortes:** Ubicada a la izquierda en `FieldsSubheader.tsx` con ícono `Settings` sin texto (`36×36px`, `border-radius: var(--radius-md)`), usando `--color-terracotta` según `SKILLS_FRONTEND.md §2.1` (reservando `--color-heat-soil` solo para calor y suelo). Las pills de campos se muestran en una sola fila calculando exactamente cuáles entran completas (ocultando las que quedarían cortadas) con flechas izquierda/derecha. Si la sesión es `demo`, al tocarla lleva a iniciar sesión (`AuthScreen`); si es usuario autenticado, abre la card flotante de ajustes (`FRONT-28`).
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-28: Card Flotante Glass con Diseño de Fichero para Ajustes de Usuario (`Usuario`, `Campos`, `Expandir mapa`, `Idioma`)
- **Objetivo:** Implementar una card modal flotante con fondo *glassmorphism* sobre la vista principal siguiendo el diseño de fichero con 4 pestañas (`Usuario`, `Campos`, `Expandir mapa`, `Idioma`), dejando el contenido funcional de cada pestaña para una etapa posterior.
- **Archivos Permitidos:**
  - `frontend/src/components/UserSettingsModal.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - **Estética Glass + Fichero:** Overlay semitransparente con `backdrop-filter: blur(...)` y card con pestañas tipo archivero en la parte superior.
  - **4 pestañas iniciales:** `Usuario`, `Campos`, `Expandir mapa` e `Idioma`, con estado placeholder limpio listo para completar su contenido en la siguiente etapa.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-29: Sincronización de Colores Vivos (sin Verde) entre Pills de Campos y Polígonos del Mapa con Mayor Opacidad
- **Objetivo:** Eliminar los tonos verdes de las pills de campos y sincronizar cada campo en el mapa (`Polygon` / `CircleMarker`) con el color de su pill usando variantes más claras/vivas de la paleta (`--color-heat-soil-light`, `--color-water-rain-light`, `--color-gold-yellow`, `--color-terracotta`) y mayor opacidad al estar seleccionado.
- **Archivos Permitidos:**
  - `frontend/src/theme/mapColors.ts`
  - `frontend/src/components/FieldsSubheader.tsx`
  - `frontend/src/components/MapView.tsx`
  - `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - **Sin verde:** Se reemplaza `variant-olive` y el relleno verde en el mapa (que se confundía con la imagen satelital) por 4 tonos claros/vivos de la paleta definidos de forma centralizada en `FIELD_PALETTE`.
  - **Pills seleccionadas sin borde en tono oscuro:** Cada pill seleccionada pasa a su variante oscura (`--color-heat-soil-dark`, `--color-water-rain-dark`, `--color-gold-yellow-dark`, `--color-terracotta-dark`) con texto claro `--color-bg-card` (evitando texto negro en el amarillo) y sin borde resaltado.
  - **Relleno en el mapa del mismo color que el borde:** Cada campo mantiene su `fieldColor` como borde y relleno, subiendo `fillOpacity` a `0.65` al seleccionarse (`0.24` en no seleccionados).
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-30: Formulario de Edición de Perfil (`Nombre`, `Correo`, `Contraseña`) y Botón `Cerrar sesión` en Pestaña `Usuario`
- **Objetivo:** Completar el contenido de la pestaña `"Usuario"` dentro de la card flotante `UserSettingsModal` siguiendo `SKILLS_FRONTEND.md`, permitiendo editar nombre completo, correo electrónico y nueva contraseña (vía `PATCH /api/v1/auth/me`) y cerrar sesión.
- **Archivos Permitidos:**
  - `frontend/src/types/api.ts`
  - `frontend/src/services/authClient.ts`
  - `frontend/src/components/UserSettingsModal.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - **Contrato API:** Se agrega `UserUpdateRequest` y `updateCurrentUser` apuntando a `PATCH /api/v1/auth/me` con el Bearer token activo.
  - **UX según `SKILLS_FRONTEND.md`:** Uso exclusivo de tokens de `index.css`, lenguaje formal español sin voseo, validación clara de campos (contraseña opcional ≥ 6 caracteres) y botones diferenciados (`Guardar cambios` en `--color-terracotta` y `Cerrar sesión` con `--color-risk-critical`).
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-31: Listado de Campos del Usuario con Menú Desplegable (`⋮`) para Renombrar y Borrar en Pestaña `Campos`
- **Objetivo:** Completar el contenido de la pestaña `"Campos"` en `UserSettingsModal` listando los lotes del usuario con su color asignado en el mapa, superficie y un menú desplegable de tres puntos (`MoreVertical`) sin íconos internos para `Editar nombre` (hover azul) y `Borrar` con confirmación inline (hover rojo), conectados a `PATCH /api/v1/fields/{id}` y `DELETE /api/v1/fields/{id}`.
- **Archivos Permitidos:**
  - `frontend/src/types/api.ts`
  - `frontend/src/services/fieldsClient.ts`
  - `frontend/src/components/UserSettingsModal.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - **Conexión con backend:** `updateUserField` (`PATCH /api/v1/fields/{id}`) y `deleteUserField` (`DELETE /api/v1/fields/{id}`), limpiando además `localStorage` (`removeCachedFieldPolygon`) y reasignando el campo activo al siguiente disponible cuando se borra el seleccionado.
  - **UI según `SKILLS_FRONTEND.md`:** Título formal `"Campos registrados"`, menú desplegable de tres puntos (`⋮`) sin íconos internos, edición inline del nombre (`Escape` cancela la edición) y confirmación inline previa al borrado con tokens de `--color-risk-critical`.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-32: Edición Interactiva de Polígono de un Campo Existente (`Editar superficie`) desde el Menú Desplegable
- **Objetivo:** Permitir editar el contorno poligonal de un campo guardado desde la opción `"Editar superficie"` (hover naranja) del menú desplegable en `"Campos"`, reutilizando la barra superior de delimitación y habilitando arrastre de vértices, inserción de esquinas desde puntos medios, eliminación con clic derecho y persistencia en `PATCH /api/v1/fields/{id}`.
- **Archivos Permitidos:**
  - `frontend/src/components/MapView.tsx`
  - `frontend/src/components/FieldsSubheader.tsx`
  - `frontend/src/components/UserSettingsModal.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/App.css`
- **Decisiones Acordadas con el Desarrollador:**
  - **Acceso desde `"Campos"`:** Opción `"Editar superficie"` dentro del menú `⋮` (hover naranja con `--color-heat-soil-soft` / `--color-heat-soil-dark`); al seleccionarla cierra el modal, centra el mapa en el campo seleccionado y precarga su polígono actual en `customPolygon`.
  - **Edición en Leaflet:** Marcadores `draggable` en cada vértice (`.poly-vertex-handle`), marcadores `+` en puntos medios (`.poly-midpoint-handle`) y clic derecho para quitar esquinas (mínimo 3). Al guardar recalcula centroide y superficie (`hectareas`) llamando a `updateUserField`.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-33: Filtro Previo por Provincias (Región Pampeana), Mapa 3D de Argentina y Optimización de Rendimiento
- **Objetivo:** Incorporar una pantalla previa de selección de provincias argentinas (Región Pampeana habilitada: Buenos Aires, Córdoba, Entre Ríos, La Pampa y Santa Fe) con mapa SVG 3D interactivo, persistencia en `profiles.provincias` para cuentas registradas (solo en memoria en modo demo), filtrado de lotes y validación de vértices en `MapView`, y optimizaciones de rendimiento sin alterar la estética.
- **Archivos Permitidos:**
  - `frontend/src/data/argentinaProvinces.json`
  - `frontend/src/utils/geo.ts`
  - `frontend/src/components/ProvinceSelectorScreen.tsx`
  - `frontend/src/components/MapView.tsx`
  - `frontend/src/services/authClient.ts`
  - `frontend/src/types/api.ts`
  - `frontend/src/theme/mapColors.ts`
  - `frontend/src/index.css`
  - `frontend/src/App.tsx`
  - `frontend/src/App.css`
  - `frontend/SKILLS_FRONTEND.md`
  - `frontend/TASKS_FRONTEND.md`
- **Decisiones Acordadas con el Desarrollador:**
  - **Mapa 3D de Argentina (`ProvinceSelectorScreen`):** Proyección inclinada de las 24 jurisdicciones oficiales (IGN simplificado con topología compartida), con elevación coplanar en hover/selección para las 5 habilitadas, hover diferenciado en Islas Malvinas (`¡Son argentinas!`) y tooltip `"Próximamente — Región en expansión"` en jurisdicciones bloqueadas.
  - **Sidebar alineado al tablero:** Reutiliza `.right-analysis-pane` y el ritmo/paleta cálida de tarjetas de `Planificación de campaña` (cajas crema/elevadas con borde punteado `--color-border-strong`, chips en `--color-earth-brown-dark`, contador en marrón tierra y botón terracota con texto `--color-bg-card`), además de una línea separadora `border-bottom: 1.5px solid var(--color-border-strong)` en `.top-navbar`.
  - **Flujo Demo vs. BD y GIS:** Usuarios registrados persisten en `PATCH /api/v1/auth/me/provinces` y pueden reeditar desde `.header-province-pill`; en modo demo no se llama al endpoint. `App.tsx` filtra `visibleFields` y `MapView.tsx` ajusta `fitBounds` y valida clics de dibujo contra las provincias elegidas.
  - **Optimización sin cambios visuales:** Tooltip posicionado vía `ref` + `translate3d` sin re-renders de React en `onMouseMove`, blur agrupado en `MapBaseRelief`, menos capas redundantes de extrusión 3D, `key={field.id}` estable en capas Leaflet y `React.lazy` para `MapView` y `HistoricalPanel`.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npm run build && npm run lint`

---

### `[x]` FRONT-34: Conexión de `Info general` a `GET /api/v1/telemetry` al Seleccionar Campo, Fallback de Suelo, Fix de Riesgo Térmico y Último Cultivo desde BD (`BACK-20`)
- **Objetivo:** Mostrar datos satelitales y edáficos reales en la pestaña **Info general** (`Agua en las raíces`, `Humedad para sembrar`, `Riesgo de golpe de calor`, `Materia orgánica del suelo`, textura y rotación previa) apenas el productor selecciona un campo, sin alterar la sección *What-If*.
- **Archivos Permitidos:**
  - `frontend/src/types/api.ts`
  - `frontend/src/services/apiClient.ts`
  - `frontend/src/services/fieldsClient.ts`
  - `frontend/src/components/TelemetryCards.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/App.css`
  - `frontend/TASKS_FRONTEND.md`
- **Decisiones Acordadas con el Desarrollador:**
  1. **Disparo al seleccionar el campo y What-If intacto:** Cada vez que el usuario selecciona un lote (o confirma un polígono nuevo), consultar `GET /api/v1/telemetry?lat=...&lon=...` para poblar `Info general`. No tocar `WhatIfPanel` ni modificar el valor que usa actualmente.
  2. **Fallback honesto cuando falta el dato de suelo:** Si `perfil_suelo.carbono_organico_g_kg` o `perfil_suelo.textura_predominante` vienen en `null` desde el backend (fallback regional de SoilGrids), mostrar el mensaje `"No se puede mostrar en este momento"` en lugar de inventar cifras y renderizar las `advertencias` recibidas.
  3. **Último cultivo desde BD:** Si el campo seleccionado está guardado en Supabase y tiene campañas en `GET /api/v1/fields/{field_id}/campaigns`, usar la más reciente para mostrar *Estado tras el último cultivo* en `Info general` apenas se selecciona el lote (antes incluso de correr `POST /api/v1/simulate`).
- **Especificación Técnica:**
  1. En `frontend/src/types/api.ts`, corregir `RiesgoTermicoVerano` a `'bajo' | 'medio' | 'alto' | 'critico'` (alineado con `backend/schemas.py`) y agregar los tipos `PerfilSueloTelemetria` (con propiedades `null` posibles), `TopografiaTelemetria` y `TelemetryResponse`.
  2. En `frontend/src/services/apiClient.ts`, implementar `fetchFieldTelemetry(lat, lon, signal?)` contra `GET /api/v1/telemetry?lat=...&lon=...`.
  3. En `frontend/src/App.tsx`, disparar la carga de telemetría (con cancelación ante cambios rápidos de campo) y la lectura/uso de la última campaña de `GET /api/v1/fields/{field_id}/campaigns` para usuarios autenticados con lote en BD, combinando prioridad `simulationResult` → `fieldTelemetry` sin tocar `WhatIfPanel`.
  4. En `frontend/src/components/TelemetryCards.tsx`, actualizar `getHeatRiskMeaning` para cubrir `'bajo' | 'medio' | 'alto' | 'critico'`, incorporar estados de carga/error, mostrar `"No se puede mostrar en este momento"` cuando falte materia orgánica o textura, y mostrar el último cultivo de BD o indicador de sin historial previo.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-35: Datos Propios del Campo (`UserField`), Materia Orgánica en `%` y Telemetría Dinámica por `field_id` (`BACK-21`–`BACK-23`)
- **Objetivo:** Mostrar en `Info general` el perfil de suelo, topografía y **materia orgánica del suelo en `%`** propios de cada campo guardado en `public.fields`, mientras **Agua en las raíces**, **Humedad para sembrar**, **Lluvias 90d** y **Riesgo de golpe de calor** se piden en el momento al seleccionar el lote vía `GET /api/v1/telemetry?lat=...&lon=...&field_id=...`.
- **Archivos Permitidos:**
  - `frontend/src/types/api.ts`
  - `frontend/src/services/apiClient.ts`
  - `frontend/src/components/TelemetryCards.tsx`
  - `frontend/src/App.tsx`
  - `frontend/TASKS_FRONTEND.md`
- **Decisiones Acordadas con el Desarrollador:**
  - El backend persiste `materia_organica_g_kg` (`carbono_organico_g_kg × 1.724`) y el frontend la muestra convertida a porcentaje (`materia_organica_g_kg / 10`, ej. `2.2%`).
  - Mientras carga NASA POWER al seleccionar un campo guardado, `Info general` muestra de inmediato los datos propios de suelo y topografía del `UserField` seleccionado (si ya están persistidos) y sincroniza la respuesta actualizada si el backend reintentó SoilGrids/SRTM.
- **Especificación Técnica:**
  1. Ampliar `UserField`, `PerfilSueloTelemetria` (`materia_organica_g_kg`) y `TopografiaTelemetria` (`fuente_elevacion`) en `frontend/src/types/api.ts`.
  2. Actualizar `fetchFieldTelemetry` en `frontend/src/services/apiClient.ts` para enviar `field_id` y el header `Authorization: Bearer ...` cuando estén disponibles.
  3. En `frontend/src/App.tsx`, pasar `fieldId` y `token` al seleccionar un campo, aprovechar los datos propios del `UserField` seleccionado y actualizar `userFields` cuando la respuesta de telemetría traiga datos refrescados.
  4. En `frontend/src/components/TelemetryCards.tsx`, calcular y renderizar **Materia orgánica del suelo** en `%` (`materia_organica_g_kg / 10`, o fallback desde `carbono_organico_g_kg × 1.724 / 10`), con umbrales calibrados en `%` (`< 2.9%`, `2.9%–3.5%`, `≥ 3.5%`) y detalle edáfico (`pH`, textura granulométrica, carbono orgánico) dentro del cajón expandible.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-36: Solapa Verde de Usuario en Panel Derecho (`Usuario` + `Idioma`) y Separación de `⋮` en Buscador (`Campos` + `Expandir mapa`)
- **Objetivo:** Desacoplar los ajustes de cuenta/idioma de los ajustes geográficos de campos/mapa. Incorporar una nueva solapa con el ícono de usuario alineada a la derecha del panel derecho (como última solapa de `.top-nav-tabs`, resaltada en verde), y limitar el botón `⋮` del buscador (`MapSearchBar`) únicamente a `Campos` y `Expandir mapa` tanto para usuarios autenticados como en modo demo.
- **Archivos Permitidos:**
  - `frontend/src/App.tsx`
  - `frontend/src/App.css`
  - `frontend/src/components/MapSearchBar.tsx`
  - `frontend/src/components/FieldsSubheader.tsx`
  - `frontend/src/components/UserSettingsModal.tsx`
  - `frontend/TASKS_FRONTEND.md`
- **Decisiones Acordadas con el Desarrollador:**
  1. **Nueva solapa con estilo de carpeta alineada a la derecha del panel derecho:** Se ubica al extremo derecho de `.top-nav-tabs` (`margin-left: auto`, después de `Información histórica`), mostrando el ícono de `User`, con color verde destacado respecto de las demás solapas y marcándose como activa (`.active`) mientras el modal de usuario está abierto.
  2. **Separación estricta 2 y 2 en `UserSettingsModal`:** Nunca se muestran las 4 pestañas juntas.
     - Al abrir desde la **solapa de usuario**: el modal solo muestra las pestañas **`Usuario`** e **`Idioma`** (iniciando en `Usuario`).
     - Al abrir desde los **tres puntitos (`⋮`) del buscador**: el modal solo muestra las pestañas **`Campos`** y **`Expandir mapa`** (iniciando en `Campos`).
  3. **Comportamiento en Modo Demo vs. Usuario autenticado:**
     - **Botón `⋮` del buscador:** Funciona igual en modo demo y en modo autenticado: abre `UserSettingsModal` con **`Campos`** y **`Expandir mapa`** (sin cerrar la sesión demo).
     - **Solapa de Usuario:** En usuario autenticado abre `UserSettingsModal` con **`Usuario`** e **`Idioma`**; en **modo demo** lleva al usuario a iniciar sesión / registrarse (`handleLogout()` hacia `AuthScreen`).
- **Especificación Técnica:**
  1. En `frontend/src/components/UserSettingsModal.tsx`, agregar prop `scope: 'user' | 'map'` que filtre `ALL_TABS` a `['usuario', 'idioma']` o `['campos', 'expandir_mapa']` respectivamente y reinicie `activeTab` al primer tab del `scope` cada vez que `isOpen` o `scope` cambie. Permitir abrirse también cuando `authStatus === 'demo'` si `scope === 'map'`.
  2. En `frontend/src/App.tsx`, reemplazar el estado booleano `isSettingsOpen` por `settingsScope: 'user' | 'map' | null` (o equivalente), agregar la solapa verde de usuario a la izquierda en `.top-nav-tabs` (con `aria-label="Cuenta de usuario"` / tooltip acorde al modo), conectar `onUserAction` / `onMapMenuAction` de `FieldsSubheader` -> `MapSearchBar` a `setSettingsScope('map')` para ambos modos (`demo` y `authenticated`).
  3. En `frontend/src/components/MapSearchBar.tsx` y `frontend/src/components/FieldsSubheader.tsx`, actualizar `title`/`aria-label` del botón `⋮` para reflejar `"Campos y mapa"` (ya no `"Iniciar sesión"` en demo) y marcar `.active` solo cuando el modal esté abierto en `scope === 'map'`.
  4. En `frontend/src/App.css`, definir los estilos de la solapa de usuario en verde (`--color-primary` / `--color-primary-light`) integrada a `.top-nav-tabs` y su estado `.active`.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-37: Encabezado de `Info general` sin Coordenadas ni Hectáreas (Solo Nombre del Campo sin Repetición)
- **Objetivo:** Limpiar el encabezado de la pestaña **Info general** eliminando por completo las coordenadas (`lat, lon`) y las hectáreas (`superficieHa`), y mostrando el nombre del campo (`loteLabel`) una sola vez sin duplicación visual.
- **Archivos Permitidos:**
  - `frontend/src/components/TelemetryCards.tsx`
  - `frontend/src/App.tsx`
  - `frontend/TASKS_FRONTEND.md`
- **Decisiones Acordadas con el Desarrollador:**
  1. **Sin coordenadas ni hectáreas:** Quitar tanto el bloque `<code>lat, lon</code>` como el badge de `ha` (`superficieHa`) de `TelemetryCards.tsx` (y remover el texto `"Ubicación del lote:"`).
  2. **Nombre del campo una sola vez:** Eliminar el subtítulo repetido (`p.telemetry-lote-subtitle`) debajo de `h2.section-title` (`Info general`) y mostrar el nombre del campo (`loteLabel`) en la pill del encabezado derecho con el ícono `MapPin`.
- **Especificación Técnica:**
  1. Actualizar `headerNode` en `frontend/src/components/TelemetryCards.tsx` para renderizar `h2.section-title` (`Info general`) a la izquierda y una pill a la derecha con `<MapPin size={13} />` + `{loteLabel}` (limpiando la prop `superficieHa` si no se utiliza en otra parte del componente o dejándola opcional sin renderizar).
  2. Ajustar en `frontend/src/App.css` los estilos de la pill en el encabezado de `Info general` para que el nombre del campo se vea legible y equilibrado sin cortar innecesariamente.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-38: Botones de Acción Principal en Verde Vivo Claro (`Planificar`, `Guardar campo`, `+ Nuevo campo`, `Iniciar sesión`, `Reproducir serie`) y Estados Deshabilitados Tenues
- **Objetivo:** Diferenciar visualmente los botones de acción principal pasándolos del terracota actual a un **verde vivo más claro** dentro de la gama de la paleta, y reducir notablemente la opacidad (con un toque de `grayscale`) en su estado `:disabled` para que nunca se confundan con botones habilitados.
- **Archivos Permitidos:**
  - `frontend/src/index.css`
  - `frontend/src/App.css`
  - `frontend/SKILLS_FRONTEND.md`
  - `frontend/TASKS_FRONTEND.md`
- **Decisiones Acordadas con el Desarrollador:**
  1. **Solo botones de acción principal:** El cambio cromático y de `:disabled` se aplica específicamente a:
     - **`Planificar`** (`.plan-submit-btn`)
     - **`Guardar campo` / `Guardar cambios` en delimitación** (`.poly-action-btn.primary`)
     - **`+` Añadir nuevo campo** (`.fields-new-icon-btn`, `.fields-new-btn`)
     - **`Iniciar sesión` / `Crear cuenta`** (`.auth-submit-btn`)
     - **`Reproducir serie`** (`.play-timeline-btn`)
  2. **Verde vivo más claro dentro de los tonos del proyecto:** Definir tokens dedicados en `index.css` (derivados más vivos y claros que `#4B5B2D`, con buen contraste para texto claro y variante hover oscura) para aplicarlos en esos 5 botones principales sin teñir todos los botones secundarios ni los controles azules/terracota/rojos.
  3. **Estado `:disabled` bien distinguible:** Reducir la opacidad de estos botones cuando están deshabilitados (ej. `opacity: 0.34`) y sumar `filter: grayscale(0.45)` para que el contraste frente al estado habilitado sea inmediato.
  4. **Actualización documental:** Ajustar `SKILLS_FRONTEND.md` para reflejar esta excepción controlada de botones de acción principal en verde vivo.
- **Especificación Técnica:**
  1. Añadir tokens `--color-action-green` y `--color-action-green-hover` en `frontend/src/index.css`.
  2. Actualizar en `frontend/src/App.css` las clases `.plan-submit-btn`, `.poly-action-btn.primary`, `.fields-new-icon-btn`, `.fields-new-btn`, `.auth-submit-btn` y `.play-timeline-btn` (fondo, `border: none`, `:hover:not(:disabled)`, `:focus-visible` y `:disabled` con baja opacidad + `grayscale`).
  3. Actualizar `frontend/SKILLS_FRONTEND.md` con la regla de botones sin borde (`border: none`) y la excepción de `--color-action-green` para las acciones principales.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-39: Login Acoplado a la Derecha, Modo Demo Exclusivo en Inicio de Sesión y Cuaderno Rayado Izquierdo con Marca y Lema
- **Objetivo:** Reorganizar `AuthScreen` en una grilla de dos columnas a pantalla completa con el formulario acoplado como panel derecho (sin tarjeta flotante centrada), restringir el acceso a modo demo únicamente a la pestaña de inicio de sesión (`mode === 'login'`), y mostrar en el sector izquierdo una hoja de cuaderno rayado con el logo, el nombre **Ereia** y el texto **"Soporte para el cultivo"** debajo.
- **Archivos Permitidos:**
  - `frontend/src/components/AuthScreen.tsx`
  - `frontend/src/App.css`
  - `frontend/TASKS_FRONTEND.md`
- **Decisiones Acordadas con el Desarrollador:**
  1. **Panel derecho fijo (no flotante):** el formulario de acceso/registro ocupa el panel derecho a altura completa (`min-height: 100vh` en desktop), acoplado al borde derecho.
  2. **Modo demo solo en Login:** el divisor y el botón `Explorar en modo demo` (sin borde) solo se muestran cuando `mode === 'login'`, ocultándose en `Crear cuenta` (`mode === 'register'`).
  3. **Sector izquierdo tipo cuaderno rayado:** fondo de hoja rayada cálida con margen lateral sutil, mostrando el logo `/ereia-icon.png`, el wordmark **Ereia** y debajo el lema **"Soporte para el cultivo"**.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-40: Envío de `field_id` y `Authorization` en `POST /api/v1/simulate` + Manejo de `401` / `404` / `422`
- **Objetivo:** Aprovechar `field_id` (opcional) en `POST /api/v1/simulate` cuando se simula sobre un campo guardado (tanto en sesión autenticada como en modo demo), enviando `field_id`, las coordenadas del campo y el header `Authorization: Bearer <access_token>` para reutilizar suelo y topografía persistidos sin reconsultar APIs externas, y manejar explícitamente `401`, `404` y `422` (manteniendo intacta la simulación sobre puntos sueltos sin `field_id`).
- **Archivos Permitidos:**
  - `frontend/src/types/api.ts`
  - `frontend/src/services/apiClient.ts`
  - `frontend/src/components/AuthScreen.tsx`
  - `frontend/src/components/RecommendationPanel.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/App.css`
  - `frontend/TASKS_FRONTEND.md`
- **Decisiones Acordadas con el Desarrollador:**
  1. **Modo demo igual que usuarios autenticados:** cuando haya un campo guardado seleccionado (`selectedUserField`) y no se esté dibujando o consultando un punto suelto en el mapa, enviar `field_id: selectedUserField.id`, las coordenadas del campo y el header `Authorization: Bearer <token>` tanto en modo demo como en cuentas autenticadas. Si es un punto suelto en el mapa sin `field_id`, omitir `field_id`.
  2. **Respuesta `401` (sesión inválida o expirada):** mostrar un aviso claro de sesión expirada/inválida, cerrar la sesión actual y redireccionar a `AuthScreen` (inicio de sesión).
  3. **Respuestas `404` y `422` (campo ajeno/inexistente o coordenadas con desfase > 100 m):** NO caer silenciosamente al simulador local; mostrar en el panel el mensaje `"Ocurrió un error inesperado"` acompañado de un botón **`Reintentar`** que vuelva a disparar la simulación.
- **Especificación Técnica:**
  1. En `frontend/src/types/api.ts`, agregar `field_id?: string | null;` a `SimulateRequest`.
  2. En `frontend/src/services/apiClient.ts`, crear una clase de error tipada (ej. `SimulateApiError` con `status: number`) y actualizar `simulateCropRotation(request: SimulateRequest, token?: string | null)` para incluir `Authorization: Bearer <token>` cuando exista token y enviar `field_id` en el JSON body si está definido. Ante `!response.ok`, lanzar `SimulateApiError` con el código HTTP (`401`, `404`, `422`, etc.) sin ocultar dichos errores bajo un fallback local silencioso cuando la respuesta del backend sea `401`/`404`/`422`.
  3. En `frontend/src/App.tsx` y `frontend/src/components/RecommendationPanel.tsx`:
     - Al planificar campaña sobre un campo guardado (`selectedUserField`), pasar `field_id: selectedUserField.id` y las coordenadas del campo (`lat`, `lon`), junto con `activeToken`. En punto suelto en el mapa, omitir `field_id`.
     - Si `simulateCropRotation` falla con `401`: ejecutar cierre de sesión limpiando estado de sesión, pasar un aviso inicial a `AuthScreen` (ej. `"Su sesión expiró o dejó de ser válida. Inicie sesión nuevamente."`) y redirigir al inicio de sesión.
     - Si falla con `404` o `422`: mostrar en `RecommendationPanel` un estado de error con el texto `"Ocurrió un error inesperado"` y el botón **`Reintentar`** (verde sin borde según `SKILLS_FRONTEND.md`).
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-41: Avisos Discretos de Dato Aproximado (`advertencias`, `suelo_advertencias`, `topo_advertencias`) sin Siglas Técnicas
- **Objetivo:** Mostrar de forma visible pero discreta los avisos de dato aproximado provenientes de `advertencias` (`/simulate` y `/telemetry`), así como de `suelo_advertencias` y `topo_advertencias` (`UserField`), cerca de los bloques de suelo/topografía en `Info general` y `Planificación de campaña`, traduciendo siglas técnicas al lenguaje comprensible del productor según `SKILLS_FRONTEND.md`.
- **Archivos Permitidos:**
  - `frontend/src/utils/formatters.ts`
  - `frontend/src/components/TelemetryCards.tsx`
  - `frontend/src/components/RecommendationPanel.tsx`
  - `frontend/src/App.css`
  - `frontend/TASKS_FRONTEND.md`
- **Decisiones Acordadas con el Desarrollador:**
  1. **Estilo y ubicación:** mantener el banner de advertencia amarillo (`.telemetry-warning-banner`) tal como está diseñado actualmente en `Info general` (`TelemetryCards.tsx`), y replicar el mismo estilo discreto en `RecommendationPanel.tsx` si `/simulate` devuelve `advertencias`.
  2. **Lenguaje sin siglas técnicas:** NO mostrar `"ISRIC"`, `"SRTM"`, `"SoilGrids"`, `"grilla_isric"` ni siglas técnicas crudas en la UI. Traducir y redactar los avisos en español formal (sin voseo) para que el productor comprenda qué dato aproximado está viendo (por ejemplo, perfil de suelo de referencia a X km o topografía aproximada de la zona) sin mencionar nombres de proveedores o siglas internas.
- **Especificación Técnica:**
  1. En `frontend/src/utils/formatters.ts`, crear un helper reutilizable `humanizeAgronomicWarnings(...)` (para evitar lógica duplicada entre `TelemetryCards` y `RecommendationPanel`) que:
     - Combine y deduplique avisos de `suelo_advertencias`, `topo_advertencias` y `advertencias` de `/telemetry` o `/simulate`.
     - Elimine o traduzca siglas y términos técnicos (`ISRIC`, `SoilGrids`, `SRTM`, `NASA POWER`, `grilla_isric`, `isric_soilgrids_v2`, `srtm_90m`, etc.) a redacción agronómica clara y breve para el productor (conservando distancias en km o magnitudes útiles cuando vengan en el texto).
  2. En `frontend/src/components/TelemetryCards.tsx`, ubicar el banner amarillo `.telemetry-warning-banner` cerca del bloque de suelo/topografía cuando existan advertencias sanitizadas de suelo, topografía o telemetría (sin repetir textos equivalentes).
  3. En `frontend/src/components/RecommendationPanel.tsx`, mostrar el mismo formato discreto de banner amarillo cuando `simulateData.advertencias` contenga avisos sanitizados.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`

---

### `[x]` FRONT-42: Polling de `reintento_en_curso` (`GET /api/v1/fields/{id}` cada 30 s), Spinner Discreto y Refresco + Aviso al Llegar Dato Real
- **Objetivo:** Incorporar `reintento_en_curso` en el contrato `UserField`, agregar `getUserField` (`GET /api/v1/fields/{id}`) en `src/services/fieldsClient.ts`, consultar cada 30 s mientras el campo seleccionado tenga `reintento_en_curso = true`, detectar cambios en `suelo_fuente` o `topo_fuente`, actualizar la UI con un aviso claro al llegar el dato real y detener el polling cuando `reintento_en_curso` pase a `false` o cambie el campo seleccionado.
- **Archivos Permitidos:**
  - `frontend/src/types/api.ts`
  - `frontend/src/services/fieldsClient.ts`
  - `frontend/src/App.tsx`
  - `frontend/src/components/TelemetryCards.tsx`
  - `frontend/src/App.css`
  - `frontend/TASKS_FRONTEND.md`
- **Decisiones Acordadas con el Desarrollador:**
  1. **Indicador durante `reintento_en_curso = true`:** mostrar solo una ruedita de carga pequeña (spinner discreto con `aria-label` / `title` accesible, sin bloques extensos de texto) junto al bloque de suelo/topografía en `Info general`.
  2. **Al cambiar `suelo_fuente` o `topo_fuente` (llegada de dato real):** mostrar una notificación clara y breve en español formal (ej. `"Llegó el dato real del suelo de su lote"` / `"Llegó el dato real de topografía de su lote"`, sin siglas técnicas) **y refrescar automáticamente** la UI (estado del campo seleccionado en `userFields`, telemetría en `Info general` y re-simulación si el usuario ya había planificado campaña).
  3. **Corte del polling:** detener inmediatamente el intervalo de 30 s si `reintento_en_curso` pasa a `false`, si el usuario selecciona otro campo, cierra sesión o se desmonta el componente.
- **Especificación Técnica:**
  1. En `frontend/src/types/api.ts`, agregar `reintento_en_curso?: boolean;` al tipo `UserField`.
  2. En `frontend/src/services/fieldsClient.ts`, implementar `getUserField(token: string, fieldId: string, signal?: AbortSignal): Promise<UserField>` llamando a `GET /api/v1/fields/${encodeURIComponent(fieldId)}` con `Authorization: Bearer ${token}`.
  3. En `frontend/src/App.tsx`, mediante `useEffect` ligado a `selectedUserField?.id`, `selectedUserField?.reintento_en_curso` y `activeToken`:
     - Si `reintento_en_curso === true`, programar `setInterval` cada `30_000` ms llamando a `getUserField` con `AbortController`.
     - Comparar `suelo_fuente` y `topo_fuente` previos vs. los nuevos recibidos: si alguno cambió respecto a la instantánea anterior (ej. dejó de ser aproximado/grilla o cambió de fuente), mostrar un toast/aviso discreto de llegada de dato real y actualizar el campo en `userFields`, disparar refresco de `/api/v1/telemetry` y re-ejecutar `POST /api/v1/simulate` si `hasPlanned` está activo para ese campo.
     - Limpiar intervalo y abortar requests pendientes al cambiar de campo o pasar `reintento_en_curso` a `false`.
  4. En `frontend/src/components/TelemetryCards.tsx` + `frontend/src/App.css`, renderizar el spinner compacto (`Loader2` animado con `aria-label`) junto al bloque de suelo/topografía cuando `reintento_en_curso === true`, sin sobrecargar visualmente con párrafos de texto.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build`
### `[x]` FRONT-36: Panel de recomendación en lenguaje de productor (riesgo de año malo y rinde en qq/ha)
- **Objetivo:** Mostrar lo que el modelo sabe de una forma que el productor argentino, su asesor o una empresa (aseguradora, acopio, financiera) entiendan sin explicación: **cuántas campañas de cada 10 salen mal, cuántos quintales se esperan contra lo normal de la zona y cuánto se cae en un año malo**. Hoy el panel muestra un anillo "/100" que se lee como nota de examen (53/100 parece malo, pero significa "un poco mejor que un año normal"), y no muestra ni el rango ni los años malos que la API ya devuelve.
- **Archivos Permitidos:** `frontend/src/types/api.ts`, `frontend/src/components/RecommendationPanel.tsx`, `frontend/src/components/RiesgoRindeResumen.tsx` (nuevo), `frontend/src/utils/formatters.ts`, `frontend/src/utils/lenguajeProductor.ts` (nuevo), `frontend/src/services/apiClient.ts`, `frontend/src/services/ultimoResultado.ts` (nuevo), `frontend/src/components/AvisoEstadoDatos.tsx` (nuevo), `frontend/src/App.tsx` (solo el flujo de carga y error de la simulación), `frontend/src/App.css`, `frontend/TASKS_FRONTEND.md`.
- **Decisiones Acordadas con el Desarrollador (2026-11-15):**
  1. **No se muestra jerga técnica en la vista principal.** Ningún texto visible dice "P10", "P90", "puntaje", "score", "ensemble", "análogos", "ONI", "calibración" ni "/100". Todo pasa por la tabla de traducción de abajo, implementada en `utils/lenguajeProductor.ts` como funciones puras.
  2. **Rinde en quintales por hectárea (qq/ha)**, la unidad de uso en Argentina (1 qq = 100 kg), redondeado a entero. Los kg/ha quedan solo en el detalle técnico.
  3. **Probabilidad como frecuencia**, no como porcentaje: "3 de cada 10 campañas como esta". Siempre va acompañada de la referencia habitual.
     - **Solo cuando `anticipa_diferencias` es `true`** (hoy maíz y soja). Para el resto de los cultivos (hoy trigo, cebada, girasol y sorgo) se muestra **solo la frecuencia habitual** y se dice que el sistema todavía no anticipa diferencias entre años para ese cultivo (ML-16: medido fuera de muestra, no le gana a la frecuencia habitual). Nunca se inventa una comparación.
  4. **Lo que el sistema no sabe se dice, no se inventa:**
     - Si un campo viene `null`, se muestra el motivo en palabras y no un número.
     - **Nunca se muestra una recomendación inventada como si fuera del lote.** Hoy, si `/simulate` falla, el bloque `catch` de `App.tsx` cae en silencio a `generateSimulatedResponse`. Ese reemplazo se elimina. Cuando el backend falla, el front sigue la tabla de *Estados cuando el backend no responde* (abajo): muestra el último resultado real guardado o un error claro, pero nunca datos de ejemplo.
     - **El modo demo sigue existiendo, pero solo si se activa a propósito.** `generateSimulatedResponse` se usa solo cuando `USE_SIMULATED_MODE` está activado (por ejemplo, para una presentación sin backend), nunca como respuesta a un error.
       - En ese modo hay un aviso fijo arriba del panel: **"Modo demostración: datos de ejemplo, no corresponden a tu lote."**
       - En ese modo no se generan probabilidades ni kg/ha.
       - La respuesta se marca con `es_ejemplo: true`, un campo solo del front.
  5. **Vista para empresas:** un desplegable **"Ver detalle técnico"** al pie de cada cultivo con los valores exactos. La vista principal no cambia.
- **Tabla de traducción (fuente única: `utils/lenguajeProductor.ts`):**

  | Dato de la API | Texto para el productor | Regla |
  | :--- | :--- | :--- |
  | `prob_anio_malo` (con `anticipa_diferencias = true`) | "**3 de cada 10** campañas como esta terminan con un rinde bajo" | **Una sola escala para todas las frecuencias** (corregido el 2026-11-15 tras la revisión visual): por debajo de 0,35, "1 de cada N" con N = `round(1 / p)`; desde 0,35, "N de cada 10"; hasta 0,05, "menos de 1 de cada 20". Antes se mezclaba "2 de cada 10" con "1 de cada 4" y, redondeando a décimos, 0,18 y 0,24 se leían iguales. "Rinde bajo" = 15% o más bajo lo normal de la zona; se explica en un ícono (i). El valor nunca supera el tope del modelo (hoy 0,35 → "4 de cada 10" como máximo). |
  | `anticipa_diferencias = false` | "En esta zona, **1 de cada 4** campañas de trigo termina con rinde bajo. Para este cultivo todavía no podemos anticipar si este año viene mejor o peor que lo habitual." | La frecuencia sale de `prob_anio_malo_tipica`, con la misma escala que la fila anterior (`frecuencia(p)` en `lenguajeProductor.ts`). Sin flecha ni color de alerta. |
  | `prob_anio_malo` vs `prob_anio_malo_tipica` | "**Más riesgo que lo habitual** (normalmente son 2 de cada 10)" | Cociente ≥ 1,3 → "Más riesgo que lo habitual"; ≤ 0,77 → "Menos riesgo que lo habitual"; en el medio → "Riesgo parecido a lo habitual". |
  | `rinde_kg_ha.esperado` y `.normal` | "Rinde esperado: **34 qq/ha** (lo normal en la zona es 32 qq/ha, **+6%**)" | Porcentaje = `esperado / normal − 1`, redondeado a entero. Entre −2% y +2%: "similar a lo normal". |
  | `rinde_kg_ha.anio_malo` / `.anio_bueno` | "En un año malo: **~24 qq/ha** · En un año bueno: **~38 qq/ha**" | Barra horizontal con el rango, una marca en el esperado y una línea en lo normal. El "~" indica que es aproximado. |
  | `anios_evaluados` + `fase_enso` | "Comparamos con **12 campañas con El Niño** desde 1981 en esta zona" | `nina` → "La Niña (años más secos)", `nino` → "El Niño (años más húmedos)", `neutro` → "años neutros (ni Niño ni Niña)". |
  | `departamento_referencia` | "Lo normal de la zona es el promedio de **Pergamino (Buenos Aires)** según el Ministerio de Agricultura (MAGyP). Tu lote puede rendir distinto." | Si `distancia_km > 30`: agregar "(el departamento más cercano, a 42 km)". |
  | `sub_scores.hidroclimatico` | El anillo "/100" se elimina. Si hay `rinde_kg_ha`, manda el "+6%" de la fila de rinde. Si no hay (coberturas, fuera de cobertura), se muestra "**+3% sobre un año normal**" | Desvío % = `hidroclimatico − 50` (por la definición de la escala MAGyP). Entre −2 y +2: "en línea con un año normal". No se muestran dos porcentajes distintos para el mismo cultivo: `hidroclimatico` incluye la penalización por demanda hídrica y el kg/ha no (ML-17). |
  | `sub_scores.suelo` | "Aporte al suelo: **Muy bueno / Bueno / Regular / Malo**" | ≥ 75 / ≥ 55 / ≥ 35 / < 35. El número queda en el detalle técnico. |
  | `rinde_kg_ha = null` en coberturas | "Cultivo de servicio: no se cosecha, su valor está en el suelo y el agua que deja." | — |
  | `rinde_kg_ha.motivo_sin_dato` (otros casos) | El motivo tal cual viene, por ejemplo "Tu lote está fuera de la zona con datos de rinde (región pampeana)." | — |
  | Todos los campos de ML-16 en `null` en un cultivo MAGyP | Se muestra solo la categoría actual ("Riesgo medio") | Bundle sin distribución predictiva. No se muestra ninguna frecuencia. |

- **Estados cuando el backend no responde (fuente única: `components/AvisoEstadoDatos.tsx`):**

  | Qué pasó | Cómo se detecta | Qué muestra el panel |
  | :--- | :--- | :--- |
  | **Servidor despertando** (Render Free duerme tras 15 min sin uso; la primera consulta tarda 30–60 s) | El pedido sigue abierto después de 5 s | Indicador de carga con "**Despertando el servidor, puede tardar hasta un minuto…**". El pedido no se corta antes de **75 s** (`AbortController`). Si hay un resultado guardado, se muestra mientras tanto con el aviso de la última fila. |
  | **Falla un servicio externo** | `503` con `{"detail", "fuente"}` (BACK-7) | "**No pudimos consultar {fuente} en este momento.** Probá de nuevo en unos minutos." + botón **Reintentar**. Nombres para `fuente`: `nasa_power` → "los datos satelitales de NASA", `soilgrids` → "el mapa de suelos", `srtm` → "el relieve del terreno". |
  | **Pedido inválido** | `422` | El mensaje del backend tal cual (por ejemplo, la campaña que no corresponde a la fecha), sin botón de reintentar. |
  | **Backend caído o sin red** | Error de red, timeout de 75 s o `5xx` sin `fuente` | Si hay un resultado guardado para ese lote y esa configuración: se muestra completo con el aviso "**Sin conexión con el servidor. Te mostramos el último resultado de este lote, del 12/11 a las 10:40.**" + **Reintentar**. Si no hay: "**No pudimos conectarnos con el servidor.** Revisá tu conexión o probá de nuevo en unos minutos." + **Reintentar**. Nunca datos de ejemplo. |

  - **Qué se guarda (`services/ultimoResultado.ts`):**
    - Cada respuesta **real** y exitosa de `/simulate` sin What-If se guarda en `localStorage` con la fecha de consulta. Las de ejemplo nunca se guardan.
    - La clave es el `field_id` (o, sin campo guardado, la coordenada redondeada a 3 decimales) + `campana` + `cultivo_anterior` + `objetivo_productor`.
    - Se guarda una entrada por clave, hasta 20 en total, y se descartan primero las más viejas.
    - Un resultado de otra campaña (invierno o verano) no se reutiliza.
    - Todas las lecturas y escrituras van en `try/catch`, porque `localStorage` puede estar bloqueado. Sin `localStorage`, el panel muestra el error sin resultado guardado.
  - **What-If sin conexión:** los controles quedan deshabilitados con "Necesitás conexión para simular escenarios". No se simula en el navegador.
  - **Antigüedad:** si el resultado guardado tiene más de 7 días, el aviso agrega "**puede estar desactualizado: la humedad del suelo cambia de una semana a otra**".

- **Especificación Técnica:**
  1. `types/api.ts`: agregar `RindeKgHa`, `DepartamentoReferencia`, `FaseEnso` y los campos opcionales de BACK-27 en `RankingCultivoItem`, `RecomendacionPrincipal`, `DistribucionHidroclimatica` y `SimulateResponse`.
  2. `utils/lenguajeProductor.ts` (nuevo):
     - `frecuenciaAnioMalo(p)`, `comparacionHabitual(p, pTipica)`, `frecuenciaHabitual(pTipica, cultivo)`, `rindeVsNormal(esperado, normal)`, `textoFaseEnso(fase)`, `textoAporteSuelo(s)`, `textoDesvioNormal(hidro)`.
     - Todas devuelven texto y, cuando aplica, un nivel (`bueno | neutro | malo`) para el color. Sin dependencias de React.
  3. `utils/formatters.ts`: `kgHaAQq(kg)` y `formatQq(kg)` → `"34 qq/ha"`.
  4. `components/RiesgoRindeResumen.tsx` (nuevo): bloque reutilizable (también lo usa FRONT-37) con tres filas:
     - (a) Riesgo de año malo: frecuencia grande más la comparación con lo habitual si `anticipa_diferencias`; si no, la frecuencia habitual con la aclaración de que todavía no se anticipan diferencias.
     - (b) Rinde esperado frente a lo normal.
     - (c) Barra año malo / año bueno.
     - Al pie, la línea de "Comparamos con…" y la fuente.
     - El color nunca va solo: siempre acompaña un texto o un ícono (accesibilidad).
  5. `components/RecommendationPanel.tsx`:
     - En la tarjeta expandida de cada cultivo y en la recomendación principal, reemplazar el anillo "/100" por `RiesgoRindeResumen`.
     - En la fila compacta del ranking, mostrar al lado del nombre "34 qq/ha · 3 de cada 10 con rinde bajo" (o "34 qq/ha · riesgo habitual" si `anticipa_diferencias` es `false`).
     - Desplegable "Ver detalle técnico" con una tabla: probabilidad (%), probabilidad típica (%), si anticipa diferencias, rinde esperado, año malo y año bueno en kg/ha, puntajes (promedio, año malo y año bueno con el error real, P10 y P90 del clima de los años análogos, suelo), años evaluados, código y distancia del departamento.
  6. `services/apiClient.ts`:
     - `simulateCropRotation` recibe un `signal` y usa un timeout de 75 s.
     - Ante una respuesta no exitosa, lanza un error tipado `SimulacionError { tipo: 'servicio_externo' | 'invalido' | 'sin_conexion', fuente?, mensaje }` en lugar de un `Error` genérico. Lee `fuente` del cuerpo del `503`.
     - `generateSimulatedResponse` devuelve los campos nuevos en `null` y `es_ejemplo: true`.
  7. `services/ultimoResultado.ts` (nuevo): `guardarUltimoResultado(clave, respuesta)` y `leerUltimoResultado(clave) -> { respuesta, consultadoEn } | null`, con las reglas de la sección de estados.
  8. `components/AvisoEstadoDatos.tsx` (nuevo): los avisos de la tabla de estados (despertando, servicio externo, inválido, sin conexión con o sin resultado guardado, modo demostración) con su botón **Reintentar**.
  9. `App.tsx` (solo el flujo de la simulación):
     - Eliminar el `generateSimulatedResponse` del bloque `catch`.
     - Guardar las respuestas reales, y ante un error, decidir el estado con `SimulacionError` y `leerUltimoResultado`.
     - Disparar el aviso de "despertando" a los 5 s y conectar el botón **Reintentar**.
     - No se toca nada más de `App.tsx`, para no chocar con quien trabaja en el panel histórico.
- **Pendiente detectado, fuera de esta tarea:** `baselineResult` en `App.tsx` (alrededor de la línea 464) también usa `generateSimulatedResponse` para la línea base de Info general y el valor de humedad del What-If. Hay que coordinarlo con quien está sacando los datos demo: debería salir de `GET /api/v1/telemetry` (FRONT-34).
- **Ejemplo para un cultivo sin anticipación (Trigo, Pergamino):**
  > **Trigo**
  > En esta zona, **1 de cada 4** campañas de trigo termina con rinde bajo. Para este cultivo todavía no podemos anticipar si este año viene mejor o peor que lo habitual.
  > Rinde esperado: **38 qq/ha** (similar a lo normal en la zona) · En un año malo: ~25 qq/ha · En un año bueno: ~48 qq/ha
- **Ejemplo de cómo debe leerse (Soja de 2da tras trigo, Marcos Juárez):**
  > **Soja de 2da** · Recomendado
  > **2 de cada 10** campañas como esta terminan con rinde bajo · *Menos riesgo que lo habitual (normalmente 3 de cada 10)*
  > Rinde esperado: **29 qq/ha** (lo normal en la zona es 28 qq/ha, +4%)
  > En un año malo: ~22 qq/ha ━━━━━●━━━ En un año bueno: ~34 qq/ha
  > Comparamos con 12 campañas con El Niño (años más húmedos) desde 1981 en esta zona. Lo normal es el promedio de Marcos Juárez (Córdoba), MAGyP. Tu lote puede rendir distinto.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build && npm run lint`
  - Revisión visual con estos casos:
    - Un cultivo MAGyP con todos los datos.
    - Una cobertura (`rinde_kg_ha = null`).
    - Backend apagado **con** un resultado guardado: se ve el último resultado real con su fecha y **Reintentar**.
    - Backend apagado **sin** resultado guardado: mensaje de error y **Reintentar**, sin datos de ejemplo.
    - `503` simulado de NASA POWER: "No pudimos consultar los datos satelitales de NASA…".
    - Respuesta demorada más de 5 s (por ejemplo, con *throttling* en DevTools): aparece "Despertando el servidor…".
    - `USE_SIMULATED_MODE` activado: aviso fijo de modo demostración, sin frecuencias ni qq/ha.
- **Resultado de la Verificación (2026-11-15):** revisado visualmente por el desarrollador.
  - `npx tsc -b`, `npm run build` y `npm run lint` sin errores (el lint solo tiene las advertencias `set-state-in-effect` que ya existían en el proyecto).
  - Implementado: `utils/lenguajeProductor.ts` (tabla de traducción), `formatQq` / `kgHaAQq`, `RiesgoRindeResumen.tsx` (riesgo, rinde, barra de rango, "Comparamos con…" y fuente), `RecommendationPanel.tsx` (sin anillo "/100"; fila compacta "80 qq/ha · 2 de cada 10 con rinde bajo"; aporte al suelo en palabras; "Ver detalle técnico"), `ultimoResultado.ts`, `AvisoEstadoDatos.tsx`, `SimulacionError` y timeout de 75 s en `apiClient.ts`, y en `App.tsx` solo el flujo de la simulación (sin datos de ejemplo por error, aviso de "despertando" a los 5 s, último resultado guardado, Reintentar, What-If deshabilitado sin conexión).
  - **Agregado respecto de la especificación:** `/simulate` ahora manda `field_id` y el token cuando el usuario tiene sesión, para usar el suelo, la topografía (servicio único de datos del lote, BACK-24) y el departamento guardados (BACK-28). Los 401/404/422 de ese `field_id` se muestran con el mensaje del backend, no como "sin conexión".
  - Datos reales verificados contra el backend (Pergamino, 15/11/2026, El Niño ONI +2,46): maíz tardío 2 de cada 10 contra 1 de cada 4 habitual, 79,5 qq/ha contra 77 normal; girasol y sorgo solo con la frecuencia habitual y el rinde normal.
  - **Decisión de presentación:** cuando hay frecuencia de año malo, la fila compacta no muestra el badge de categoría ("Riesgo alto"), que mezcla clima y suelo. El problema de suelo se sigue viendo en "Aporte al suelo: Malo" (rojo). Sin frecuencia (respuestas viejas), el badge queda como antes.
  - **Revisión visual del desarrollador (2026-11-15): OK.**

---

### `[x]` FRONT-37: Registrar siembra y seguimiento de la campaña
- **Objetivo:** Que el productor registre qué sembró y cuándo, y que después, cada vez que entra, vea **cómo viene la campaña**: en qué parte del período que define el rinde está, si el riesgo subió o bajó desde que sembró y por qué (cuánto llovió, cuántos días de calor hubo), y el rinde esperado actualizado. Para una empresa, es la misma vista en el lote de cada cliente.
- **Archivos Permitidos:** `frontend/src/types/api.ts`, `frontend/src/services/fieldsClient.ts`, `frontend/src/components/RegistrarSiembraForm.tsx` (nuevo), `frontend/src/components/SeguimientoCampana.tsx` (nuevo), `frontend/src/components/RiesgoRindeResumen.tsx`, `frontend/src/utils/lenguajeProductor.ts`, `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/TASKS_FRONTEND.md`.
- **Decisiones Acordadas con el Desarrollador (2026-11-15):**
  1. **Solo para usuarios registrados con el campo guardado.** En modo demo se muestra la sección deshabilitada con "Registrate y guardá tu lote para seguir la campaña".
  2. **La fecha de siembra es `fecha_inicio`.** El formulario dice "Fecha de siembra", nunca "fecha de inicio".
  3. **Sin librerías nuevas de gráficos:** el gráfico semanal es un SVG propio (el proyecto hoy no tiene librería de gráficos).
  4. **El mismo lenguaje y la misma tabla de traducción de FRONT-36.** Se reusa `RiesgoRindeResumen` para el estado actual.
- **Textos por etapa (fuente: `utils/lenguajeProductor.ts`):**

  | Situación | Texto |
  | :--- | :--- |
  | `etapa = previa` | "Sembraste **Soja de 1ra** el 12/11. El período que define el rinde (floración y llenado de granos) arranca alrededor del **6/1**. Hasta entonces, el riesgo es el mismo que al sembrar." |
  | `etapa = en_curso` | "**Semana 6 de 13** del período que define el rinde (floración y llenado)." + barra de avance |
  | `etapa = terminado` | "El período que define el rinde terminó el 5/4. Lo que queda depende de la cosecha." |
  | Evolución del riesgo | "Riesgo de año malo: **5 de cada 10** (al sembrar era 3 de cada 10) ▲ **subió**" (▲ subió / ▼ bajó / = se mantiene, con una diferencia mínima de 1 de cada 10). |
  | Por qué (de `observado`) | "Desde el 6/1 llovieron **85 mm**, **la mitad de lo normal** para estas fechas, y hubo **9 días de más de 34 °C**." Lluvia: cociente < 0,7 "bastante menos que lo normal" / < 0,9 "algo menos" / ≤ 1,1 "parecido a lo normal" / ≤ 1,3 "algo más" / mayor "bastante más". Calor, heladas y tormentas fuertes se mencionan solo si son más de 0. |
  | Rinde | Bloque de FRONT-36: "Rinde esperado hoy: **27 qq/ha** (lo normal es 31 qq/ha, −13%) · En un año malo: ~22 · En un año bueno: ~31". Se agrega: "El rango se achica a medida que avanza la campaña." |
  | Atraso del dato | "Último dato satelital: 10/1 (los datos llegan con 3 a 7 días de atraso)." |
  | Lo que no ve | "Usa clima regional: no ve tormentas locales, plagas, enfermedades ni el manejo del lote." |
  | Cultivo de servicio | "Para cultivos de servicio no hay seguimiento de rinde." (422 del backend) |

- **Especificación Técnica:**
  1. `types/api.ts`: `CampaignCreate`, `SeguimientoResponse`, `PuntoSeguimiento` y `ClimaObservado` (BACK-29).
  2. `services/fieldsClient.ts`: `createCampaign(fieldId, data, token)` (el `POST` ya existe en el backend) y `fetchSeguimiento(fieldId, campaignId, token, signal?)`.
  3. `components/RegistrarSiembraForm.tsx`:
     - Campos: cultivo (solo los de la campaña vigente, con nombres legibles de `CULTIVOS_CATALOGO`) y fecha de siembra (no puede ser futura ni de hace más de 9 meses).
     - La campaña se completa sola según el cultivo.
     - Botón "Registrar siembra".
  4. `components/SeguimientoCampana.tsx`:
     - Encabezado con cultivo y fecha de siembra.
     - Texto de etapa y barra de avance.
     - Evolución del riesgo con flecha.
     - "Por qué" a partir de `observado`.
     - `RiesgoRindeResumen` con el último punto de la serie.
     - **Gráfico SVG semanal:** eje X con las fechas (dd/mm), línea de "cuántas de cada 10" y banda año malo / año bueno en qq/ha en un segundo panel, con una línea punteada en lo habitual. Cada punto con tooltip en el mismo lenguaje ("Semana del 20/1: 4 de cada 10").
     - Letra chica con el atraso del dato y lo que no ve.
     - "Ver detalle técnico" con la tabla semanal (fecha, días observados, probabilidad %, rinde esperado, año malo y año bueno en kg/ha).
  5. `App.tsx`: con el campo seleccionado, si tiene una campaña sin `fecha_fin` y sembrada hace menos de 9 meses, mostrar `SeguimientoCampana` arriba de la recomendación. Si no tiene, mostrar el botón "Registrar siembra". Cancelar la consulta cuando se cambia de campo.
  6. Estados: cargando ("Consultando datos satelitales…"), error 503 ("No pudimos consultar NASA POWER en este momento. Probá de nuevo en unos minutos.") y 422 con el mensaje del backend.
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b && npm run build && npm run lint`
  - Revisión visual de las tres etapas con datos reales de una campaña de prueba.
- **Resultado de la Verificación (2026-11-15):** revisado visualmente por el desarrollador.
  - `npx tsc -b`, `npm run build` y `npm run lint` sin errores (solo las advertencias `set-state-in-effect` que ya tenía el proyecto).
  - Implementado: tipos de BACK-29 y `CampaignCreateRequest`; `createCampaign`, `fetchSeguimiento` y `SeguimientoError` en `fieldsClient.ts`; `RegistrarSiembraForm.tsx`; `SeguimientoCampana.tsx` (encabezado, etapa y semana, barra de avance, evolución del riesgo con flecha, "por qué" desde `observado`, `RiesgoRindeResumen` con el último punto, gráfico SVG semanal con banda de qq/ha y líneas de lo habitual, letra chica, detalle técnico); textos en `lenguajeProductor.ts` (`textoEtapa`, `textoEvolucion`, `textoPorQue`, `comparacionLluvia`, `textoUltimoDato`); en `App.tsx` la campaña en curso (sin fecha de fin, sembrada hace menos de 9 meses, cultivo con rinde), su consulta y el formulario, arriba de la planificación.
  - **Cambio respecto de la especificación:** el formulario ofrece **los 8 cultivos con rinde**, agrupados por campaña, y no solo los de la campaña vigente: en noviembre (verano vigente) un trigo sembrado en junio está justo en su período crítico. La campaña sale del cultivo.
  - Estados: cargando ("Consultando datos satelitales…"), `503` con el nombre de la fuente y Reintentar, `422` con el mensaje del backend, sin conexión con Reintentar. En modo demo: "Registrate y guardá tu lote para seguir la campaña semana a semana."
  - **Revisión visual del desarrollador (2026-11-15): OK.**
  - **Correcciones tras la primera revisión visual (2026-11-15):**
    - *Info general* tomaba la siembra en curso como "último cultivo" (antecesor). Ahora `App.tsx` guarda todas las campañas del lote: la más reciente sin fecha de fin y con seguimiento es la **campaña en curso**, y el "último cultivo" es la más reciente que no es esa.
    - Las frecuencias se escriben en una sola escala (ver FRONT-36) y la flecha de evolución sigue a lo que se lee: si las dos frecuencias se escriben igual, "se mantiene".
    - En la etapa `previa` ya no se muestra la línea de evolución (un solo punto, repetía el recuadro de riesgo).

---

### `[x]` FRONT-38: Cerrar y borrar la campaña en curso
- **Objetivo:** Sin esto, una siembra seguía apareciendo como campaña en curso hasta 9 meses después aunque ya se hubiera cosechado, y no había forma de corregir una carga errónea.
- **Archivos:** `frontend/src/types/api.ts`, `frontend/src/services/fieldsClient.ts`, `frontend/src/components/AccionesCampana.tsx` (nuevo), `frontend/src/components/SeguimientoCampana.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css`.
- **Decisiones (2026-11-15, pedido del desarrollador):**
  - Las acciones van al pie de "Cómo viene la campaña" y se muestran siempre, aunque el seguimiento haya fallado (por ejemplo, NASA caída).
  - **Cerrar campaña (ya cosechada):** fecha de cosecha (entre la siembra y hoy), rinde cosechado en **qq/ha** opcional (se guarda en kg/ha × 100) con la aclaración "Con el rinde real de tu lote el sistema puede comparar lo que esperaba con lo que pasó y aprender de tu campo", y notas opcionales. Al cerrar, la campaña deja de estar en curso, pasa a ser el "último cultivo" de Info general y vuelve a aparecer "Registrar siembra".
  - **Borrar siembra:** confirmación en línea ("¿Borrar la siembra de Soja de 1ra del 13/11? Se borra también su seguimiento. No se puede deshacer."), con botón en rojo.
  - Los errores del backend (fechas inválidas) se muestran tal cual, en el idioma del productor.
- **Verificación (2026-11-15):** `npx tsc -b`, `npm run build` y `npm run lint` sin errores. Revisión visual del desarrollador (2026-11-15): OK.

---

### `[x]` FRONT-39: Información histórica con datos reales
- **Objetivo:** La pestaña mostraba rotaciones y clima inventados (copiados del lote demo más cercano). Ahora muestra solo datos reales de BACK-31.
- **Decisiones (2026-11-15, con el desarrollador):** campaña agrícola desde 2006/07; tres datos: *Cosechas del lote y rinde de la zona*, *Lluvia por campaña*, *Agua en las raíces*; se quitan temperatura, evaporación y materia orgánica por año.
- **Implementación:**
  - `data/historicalData.ts`: sin serie inventada; métricas, `visualHistorico` (color y textos del lote en el mapa), `fechaGibsCampana` (15 de enero de cada campaña; en la en curso, hasta 7 días atrás), `campanaInicial`, textos de desvío y nivel de lluvia.
  - `HistoricalPanel.tsx`: control de campaña y reproducción, resumen de la campaña (lluvia contra lo normal, agua en raíces con el mes más seco, cosechas del lote), tabla "Cómo le fue a la zona" en qq/ha contra lo normal, gráfico SVG por campaña (lluvia o agua en raíces) con la línea de lo normal, lista de cosechas por campaña y fuentes al pie.
  - `MapView.tsx`: el color histórico es el del **lote seleccionado** (con datos reales); los demás campos quedan con su color normal.
  - `App.tsx`: pide el historial al abrir la pestaña o cambiar de lote (y al cerrar o registrar una campaña), con los avisos de FRONT-36 si falla.
- **Verificación (2026-11-15):** `npx tsc -b`, `npm run build` y `npm run lint` sin errores. Revisión visual del desarrollador (2026-11-15): OK.
