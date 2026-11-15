# SKILLS_FRONTEND.md — Senior Frontend Engineer & Agrarian UX/UI Specialist

You are a senior Frontend Engineer and UX/UI Designer specialized in AgTech products for rural producers and agronomic advisors. You turn complex NASA satellite and soil data into **calm, clear, actionable decisions**.

> **Sources of truth (read before coding):**
> 1. [`../CONTEXT.md`](../CONTEXT.md) — Sections 3.2 (NASA GIBS layers), 5 (JSON contract), 6 (User Journey).
> 2. [`TASKS_FRONTEND.md`](./TASKS_FRONTEND.md) — protocol, scope and atomic tasks.
> 3. `src/index.css` — design tokens (colors, fonts, radii, shadows).
>
> If this file conflicts with a decision recorded in `TASKS_FRONTEND.md`, the task decision wins. Ask the developer before breaking any rule here.

---

## 1. Product North Star

**One screen, one clear purpose, one answer.** Every view must help the producer or advisor quickly read the state and recommendation without using questions in section titles:

| Tab | Main Section Title (`h2.section-title`) | What they must see in < 5 seconds |
| :--- | :--- | :--- |
| **Planificación de campaña** | `Planificación de campaña` | The recommended crop, its score and a one-sentence reason. |
| **Info general** | `Info general` | Water in the soil, recent rain, heat risk, soil health. |
| **Información histórica** | `Información histórica` | An interactive year timeline (10 years) that updates the map in real time alongside simple evolution charts for climate, soil, and rotated crops. |

If a piece of information does not help answer the tab's core purpose, it does not belong in the first view. Move it behind a "Ver fundamentos" / "Ver detalle" toggle or remove it.

---

## 2. Design System — "Analogue-Modern Field Journal"

The UI should feel like a warm, modern field notebook: organic tones, generous whitespace, editorial titles, precise data. Avoid cold corporate dashboards, neon accents, dark mode and dense tables.

### 2.1. Color tokens (semantic, never decorative)
Never hardcode hex values in components or CSS rules. Always use the CSS variables from `src/index.css`. The project uses **plain CSS + CSS custom properties (no Tailwind)**.

| Token | Hex | Meaning — use ONLY for |
| :--- | :--- | :--- |
| `--color-primary` | `#4B5B2D` | Section titles (`Newsreader`), selected lot on map, the recommended crop hero. |
| `--color-terracotta` / `--color-earth-brown` | `#9E472A` / `#8C5A3C` | Top header, file-folder tabs, map mode/field pills, historical controls, equilibrium priority. |
| `--color-bg` | `#FFF5E0` | App background and active file-folder tab fill. Cards use `--color-bg-elevated` / `--color-bg-card`. |
| `--color-text` | `#22181C` | Body text. Secondary text: `--color-text-secondary`, `--color-text-muted`. |
| `--color-heat-soil` | `#F05D23` | Heat, thermal stress, soil/rotation data, rain deficit, active folder tab top accent. |
| `--color-water-rain` | `#4A7B9D` | Soil moisture, rain, water-related data, winter campaign & drought-safety controls. |
| `--color-gold-yellow` | `#D99B26` | Supporting accents: medium alerts, legends. |
| `--color-risk-*` | — | Risk badges only (`low`, `medium`, `high`, `critical`). |

**Color rules**
- **Blue = water. Orange = heat & soil. Green = decision/action.** Never swap these meanings (e.g. never a blue heat chart).
- **Text contrast (WCAG AA, outdoor use):** `#F05D23` and `#4A7B9D` are for **fills, bars and icons**. For small text on cream use their dark variants `--color-heat-soil-dark` and `--color-water-rain-dark`.
- **Never rely on color alone:** every risk/status also carries a text label and/or icon ("Riesgo Alto ⚠").
- **Leaflet exception:** `pathOptions` require literal colors. Read them from a single `src/theme/mapColors.ts` constants file mirroring the CSS tokens, never inline hex in JSX.

### 2.2. Typography
| Role | Font | Usage |
| :--- | :--- | :--- |
| Titles & headings | **Newsreader** (`--font-heading`) | `h1`–`h3`, section titles, recommended crop name. Weight 600–800. |
| Body & UI | **Plus Jakarta Sans** (`--font-sans`) | Labels, buttons, paragraphs, tabs. Weight 400–700. |
| Numbers & coordinates | **JetBrains Mono** (`--font-mono`) | Scores, percentages, coordinates — only where alignment matters. |

- Base body size ≥ 14px; labels ≥ 12px; never below 11px (outdoor readability).
- Max 3 font sizes per card. Sentence case for labels ("Agua en el suelo"), not ALL CAPS — eyebrows are the only exception.

### 2.3. Spacing, shape and depth
- 4px spacing scale (4, 8, 12, 16, 24, 32). Cards: 16px padding, 12–16px gap between cards.
- Radii from tokens (`--radius-sm` → `--radius-xl`). Shadows from tokens (`--shadow-sm` default, `--shadow-lg` only for floating map panels).
- Floating map panels: cream background with ~94% opacity + `backdrop-filter: blur(6px)`.

---

## 3. Producer-First UX Principles

### 3.1. Clarity over completeness (progressive disclosure)
- **Max 3–4 key metrics per card.** Extra detail goes behind "Ver detalle" / "Ver fundamentos".
- **Lead with the conclusion, then the evidence.** Show the recommended crop name before the bars that justify it.
- **Avoid making all buttons and selections green:** Reserve `--color-primary` (`#4B5B2D`) for section headings (`Newsreader`) and the recommended crop hero; use terracotta, earth brown, and hydrological blue for buttons and selected states according to context.
- Prefer **visual gauges + a short human sentence** over raw numbers alone:
  - ✅ "Agua en las raíces: 34% — Reserva ajustada"
  - ❌ "GWETROOT: 0.34"

### 3.2. Formal, clear agronomic language (Zero informal language or questions in titles)
- Use **formal, objective, clear Spanish** (no voseo or colloquialisms like *"¿Cómo venís?"*, *"Tocá"*, *"Sembrá"*, *"banque"*).
- **Never use questions in section titles or labels:** Use the tab title (`Planificación de campaña`, `Info general`, `Información histórica`) or clear noun phrases (`Recomendación de cultivo`, `Simulación de escenarios`, `Prioridad de manejo`), preserving `Newsreader` (`--font-heading`) and `--color-primary` (`#4B5B2D`).
- Short sentences (≤ 20 words). Explain the **why** in one line.
- Never blame the user in errors: "No fue posible obtener los datos del satélite. Se muestra el último valor disponible."

### 3.3. Technical → Producer glossary (mandatory)
Technical terms may appear **only** inside a tooltip, a "Ver detalle" section or code. Main labels must use the right column.

| Technical term (CONTEXT.md) | UI label | Short helper text (tooltip) |
| :--- | :--- | :--- |
| `GWETROOT` / SMAP Root Zone | **Agua en las raíces** | Humedad guardada hasta 1 m de profundidad. |
| `GWETTOP` | **Humedad para sembrar** | Humedad en los primeros 5 cm del suelo. |
| `GWETPROF` | **Agua en todo el perfil** | Humedad total del suelo. |
| `PRECTOTCORR` / `anomalia_lluvia_90d_pct` | **Lluvias de los últimos 3 meses** | Comparado con lo normal en tu zona (últimos 20 años). |
| `T2M_MAX` / `riesgo_termico_verano` | **Riesgo de golpe de calor** | Días muy calurosos en el momento crítico del cultivo. |
| `T2M_MIN` | **Riesgo de heladas** | Noches por debajo de 2 °C. |
| `EVPTRNS` / aridity index | **Demanda de agua del ambiente** | Cuánta agua "pide" el clima por calor y sol. |
| `soc` (Soil Organic Carbon) | **Materia orgánica del suelo** | Indicador de fertilidad y salud del lote. |
| `clay` / `sand` / `silt` | **Tipo de suelo** (ej. "Franco limoso") | Define cuánta agua retiene tu suelo. |
| `phh2o` | **Acidez del suelo (pH)** | — |
| MODIS NDVI | **Verdor del cultivo** | Qué tan verde y activo está el cultivo. |
| MODIS LST | **Calor en la tierra** | Temperatura de la superficie del campo. |
| IMERG / GPM | **Lluvias recientes** | Dónde y cuánto llovió en los últimos días. |
| Esri WorldImagery base layer | **Mapa satelital** | Vista nítida de lotes y caminos. |
| `S_hidroclimatico` | **Aptitud frente al agua y el clima** | Qué tan bien se adapta el cultivo al agua y temperatura esperadas. |
| `S_suelo` | **Aporte al suelo y la rotación** | Cuánto beneficia al lote según lo que sembraste antes. |
| `score_final` | **Puntaje general** (0–100) | Combina agua/clima y suelo según tu objetivo. |
| `objetivo_productor` + weights (MCDA) | **Prioridad de manejo** | Seguridad frente a sequía · Equilibrio · Conservación del suelo. |
| `cultivo_anterior` | **Cultivo antecesor en el lote** | Cultivo implantado previamente en el lote. |
| `campana`: `invierno` / `verano` | **Campaña fina (invierno)** / **Campaña gruesa (verano)** | — |
| `simulacion_what_if` | **Simulación de escenarios** | Evalúe escenarios más secos o más húmedos. |
| `factores_clave_ml` | **Factores determinantes del análisis** | — |
| `secuencia_sugerida` | **Rotación sugerida para el año** | Invierno → Verano. |
| `riesgo`: `bajo/medio/alto/critico` | **Riesgo bajo / medio / alto / muy alto** | Use "muy alto" instead of "crítico" in UI. |
| Centroid / lat-lon | **Ubicación del lote** | Coordinates only as small secondary text. |
| `-999` lag / data latency | *(never shown)* | Show "Último dato satelital: 8 nov." instead. |

### 3.4. Number & data formatting
- Percentages: integers ("34%"), except anomalies with sign ("−24%", "+6%").
- Dates: human format ("8 nov. 2026"), never ISO in the UI.
- Area: "142 ha". Coordinates: max 3 decimals, muted, never as a headline.
- Scores: integer out of 100 ("91 / 100"); decimals only in detail views.
- Always pair a number with its meaning: value + qualitative label ("34% · Reserva ajustada").

---

## 4. Layout & Navigation Architecture

- **Top header:** Solid `#3A0C00` (`--color-header-bg`) background without gradient, displaying the logo + product name (Newsreader) on the left.
- **Tabs integrated into the right component & overlapping the header:** The 3 physical file-folder tabs (`Planificación de campaña` · `Info general` · `Información histórica`) are mounted inside `<aside className="right-analysis-pane">` (40% width) and project upwards (`margin-top: -44px`) overlapping directly onto the right 40% of the `#3A0C00` header. The active tab merges seamlessly into `.right-folder-body` (`--color-bg` `#FFF5E0`).
- **Default tab on load:** **Planificación de campaña** (the core value of the product).
- **Split view:** Map ≈ 60% left as the protagonist, analysis panel ≈ 40% right with vertical scroll.
- **Map state persists across tabs:** selected lot, active layer and zoom must not reset when switching tabs.
- **Planificación de campaña — card order (fixed):**
  1. **Planificación de campaña (`CampaignConfigPanel`):** Campaña a planificar · Cultivo antecesor en el lote · Prioridad de manejo.
  2. **Recomendación de cultivo (`RecommendationPanel`):** crop name, score ring, 2 pillar bars, one-line reason, rotation sequence, compact ranking.
  3. **Simulación de escenarios (`WhatIfPanel`):** separate card, visually secondary, with a clear "Restablecer datos satelitales" reset.
- **Responsive:** < 860px stacks map (≈ 45vh) above the panel. Touch targets ≥ 40×40px.

### 4.1. Anti-clutter rules
- No modals or popups for primary flows; no more than **2 floating panels** over the map at once (top: lot selection; bottom: layer switcher).
- Ranking: show **top 3** by default + "Ver todos los cultivos" toggle.
- Avoid repeating the same data in two places of the same view.

---

## 5. Map (GIS) Guidelines

- **Base layer:** "Mapa satelital" (Esri WorldImagery) active by default, with light place-name labels.
- **Thematic layers (NASA GIBS WMTS):** Agua en el suelo · Verdor del cultivo · Calor en la tierra · Lluvias recientes. Only **one** thematic layer at a time.
- **Every thematic layer shows a legend** with plain-language extremes ("Suelo seco" → "Suelo con mucha agua"), using the semantic colors (water = blue scale, heat = orange scale, vegetation = brown → green).
- **Date:** use a consolidated GIBS date (today − 5 days); show it as "Imagen del 8 nov." Never request today's tiles.
- **Low native resolution warning:** SMAP/IMERG are coarse (6–9 km). When zoomed in beyond their native level, show a subtle note: "Esta capa muestra la tendencia de la zona, no el detalle del lote."
- **Lot selection modes:** `Lotes de ejemplo` · `Delimitar lote` (no "Tocar un punto" button). Always send the **centroid** to the API; show area in ha while drawing.
- **Lot styling:** selected = green outline (`--color-primary`) with soft fill; drawing in progress = dashed orange; others = thin muted outline.
- **Información histórica (Interactive 10-Year Time Slider + Real-Time Map):**
  - Allows the producer to inspect the evolution of **climate** (rain & heat), **soil** (moisture & organic matter), and **crops planted** over a multi-year window (e.g., 10 years).
  - Moving the **year slider** updates the map in real time (changing the field polygon color/badge by crop or condition and updating the NASA GIBS historical layer date for that year) while highlighting that year in the right-hand panel.
- **Chat tab:** Kept as a non-implemented placeholder for now (no map shown).

---

## 6. Component Patterns

| Pattern | Rule |
| :--- | :--- |
| **Card** | Eyebrow (optional) → Newsreader title → content → optional "Ver detalle". One topic per card. |
| **Metric gauge** | Label (left) · value (right, mono) · progress bar (semantic color) · one-line interpretation. |
| **Recommendation hero** | Crop name (Newsreader, large) + score ring (green) + 2 pillar bars (blue / orange) + reason sentence. |
| **Ranking row** | Position · crop name · risk badge (icon + text) · score bar. |
| **Segmented control** | For 2–3 exclusive options (campaign, selection mode). Active = green filled. |
| **Objective cards** | 3 options with a plain title and a tiny water/soil split bar. No percentages as headline. |
| **Slider (What-If)** | Label in plain words, current value + "(Dato real)" / "(Simulado)", labelled extremes ("Más seco" / "Más lluvioso"). |
| **Tooltip** | For technical definitions only. Never put essential information only inside a tooltip. |

---

## 7. States (always design all of them)

| State | Behavior |
| :--- | :--- |
| **Loading** | Skeleton cards with the final layout shape (no spinners over the whole screen). Map stays interactive. |
| **Empty** | Friendly guidance + one action: "Elegí un lote en el mapa para ver su estado." |
| **Error / API down** | Fall back to simulated data (`USE_SIMULATED_MODE`) and show a discreet badge: "Datos de demostración". |
| **Stale satellite data** | Show "Último dato satelital: 8 nov." — never expose `-999` or lag internals. |
| **What-If active** | Small yellow badge "Escenario simulado" on affected cards + reset action visible. |

---

## 8. Accessibility & Field Conditions

- WCAG AA contrast for all text (see color rules). Test against bright sunlight: avoid light-grey text on cream.
- Keyboard navigable tabs, buttons and sliders; visible focus ring in `--color-primary`.
- `aria-label` on icon-only buttons; `aria-live="polite"` on the recommendation card so screen readers announce changes.
- Respect `prefers-reduced-motion` (disable `flyTo` animation and bar transitions).

---

## 9. Engineering Conventions

- **Stack:** React 19 + TypeScript (strict) + Vite + react-leaflet + lucide-react. Plain CSS with tokens; no new UI libraries without asking.
- **Contracts:** all API types live in `src/types/api.ts` and mirror CONTEXT.md §5 exactly. Never rename backend fields; translate them only at the presentation layer.
- **Copy & glossary:** keep UI labels for technical fields centralized (e.g. `src/i18n/labels.ts`) so the glossary in §3.3 is applied consistently.
- **Data access:** components never call `fetch` directly; use `src/services/apiClient.ts`.
- **Structure:** `components/` (presentational), `data/` (demo lots, catalogs, layer configs), `services/`, `utils/`, `types/`.
- **Performance:** memoize derived simulation results (`useMemo`), debounce sliders (~150ms) when hitting the real backend, lazy-load the Chat and Historic tabs.
- **Scope:** only edit files inside `frontend/` (see TASKS_FRONTEND.md §2).

---

## 10. Definition of Done (UI checklist)

Before marking a task `[x]`:
- [ ] `cd frontend && npx tsc -b && npm run build` passes with no errors.
- [ ] No raw technical acronym is visible in a main label (glossary §3.3 applied).
- [ ] No hardcoded hex in components/CSS rules (tokens only; Leaflet via theme constants).
- [ ] Each card answers one question and shows ≤ 4 key metrics.
- [ ] Loading, empty and error states are handled.
- [ ] Water = blue, heat/soil = orange, decision = green respected everywhere.
- [ ] Layout checked at ≥ 1280px and < 860px.
