# FRONT — interfaz web (React + Leaflet)

Lo global está en el [`AGENTS.md`](../AGENTS.md) de la raíz.

## Stack

React 19, TypeScript 7 (strict), Vite 8, react-leaflet 5 + Leaflet, lucide-react y oxlint. **CSS plano con variables** (`src/index.css`): sin Tailwind ni librerías de UI nuevas sin preguntar.

## Estructura

```
src/App.tsx            shell: sesión, selección de región, campos, pestañas y estado compartido del mapa
src/components/        presentacionales (MapView, RecommendationPanel, TelemetryCards, HistoricalPanel,
                       SeguimientoCampana, RegistrarSiembraForm, AccionesCampana, AuthScreen, ...)
src/services/          único lugar con fetch: apiClient (simulate, telemetry, historial), authClient,
                       fieldsClient, geocodeClient, ultimoResultado
src/types/api.ts       espejo exacto de backend/schemas.py
src/utils/             formatters, lenguajeProductor (textos para el productor), geo, campana
src/theme/mapColors.ts colores literales para Leaflet/SVG, espejo de los tokens CSS
src/data/              catálogos: provincias, lotes demo
```

## Comandos

```bash
cd frontend
npm run dev        # http://localhost:5173
npm run build      # tsc -b + vite build: es la verificación de tipos
npm run lint       # oxlint
```

Variables (`.env.local`, no se commitea): `VITE_API_URL` (por defecto `http://localhost:8000`), `VITE_DEMO_EMAIL` y `VITE_DEMO_PASSWORD`. Vite las incrusta en el build: en Vercel, cambiarlas requiere redeploy.

## Producto y navegación

- **Una pantalla, una respuesta:** cada pestaña responde su pregunta en menos de 5 segundos. Primero la conclusión, el detalle detrás de "Ver detalle".
  - **Planificación de campaña** (pestaña por defecto): configuración → recomendación → simulación de escenarios.
  - **Info general:** estado del lote.
  - **Información histórica:** campañas reales desde 2006/07.
- **Antes de las pestañas**, la pantalla *Selección de región* (5 provincias pampeanas). Se guarda en `profiles.provincias`, o solo en memoria en modo demo.
- **Layout:** el mapa ocupa ~60 % a la izquierda y el panel ~40 % a la derecha, con pestañas tipo carpeta sobre el header. Por debajo de 860 px se apilan. El estado del mapa (lote, zoom) no se resetea al cambiar de pestaña.
- Solo la campaña vigente está habilitada (regla en el AGENTS.md raíz).

## Diseño ("cuaderno de campo analógico-moderno")

- **Nunca hex en componentes ni CSS:** usá las variables de `src/index.css`. Leaflet y SVG leen de `src/theme/mapColors.ts`.
- **Semántica fija de color:** azul `--color-water-rain` = agua y lluvia; naranja `--color-heat-soil` = calor y suelo; verde = decisión.
  - `--color-primary` se usa para títulos y el cultivo recomendado.
  - `--color-action-green` solo para CTAs primarios (Planificar, Guardar campo, Nuevo campo, Iniciar sesión).
  - Los botones secundarios van en terracota, marrón o azul.
  - Para texto chico sobre crema, usá las variantes `-dark`.
- **Tipografía:** Newsreader para títulos (`--font-heading`), Plus Jakarta Sans para la UI (`--font-sans`) y JetBrains Mono para números alineados. Mínimo 14 px en el cuerpo y 11 px en cualquier texto.
- **Una sola `h2.section-title` por vista.** Sin preguntas en los títulos ni eyebrows que repitan el título. Botones con `border: none`.
- **Anti-clutter:**
  - Como mucho 3–4 métricas por tarjeta y 2 paneles flotantes sobre el mapa.
  - Ranking con top 3 + "Ver todos".
  - No repetir el mismo dato en una vista.
- **Estados siempre diseñados:**
  - Carga: skeleton con la forma final.
  - Vacío: guía + una acción.
  - Error: mensaje sin culpar al usuario + último resultado real guardado (`ultimoResultado`). **Nunca datos inventados.**
  - Dato satelital atrasado: "Último dato satelital: 8 nov.".
  - Escenario simulado activo: badge + botón para restablecer.
- **Accesibilidad:**
  - Contraste WCAG AA (uso al sol).
  - Nunca solo color: siempre texto o ícono junto al riesgo.
  - Foco visible, `aria-label` en botones de solo ícono y `aria-live="polite"` en la recomendación.
  - Respetar `prefers-reduced-motion`.

## Lenguaje de productor (obligatorio)

Español formal, sin voseo ("Seleccione", no "Tocá"). Frases de 20 palabras o menos. Las siglas técnicas solo aparecen en tooltips o "Ver detalle". Centralizá los textos en `utils/lenguajeProductor.ts` y `utils/formatters.ts`.

| Campo técnico | Etiqueta en UI |
| :--- | :--- |
| `GWETROOT` / `indice_humedad_radicular_pct` | Agua en las raíces |
| `GWETTOP` | Humedad para sembrar |
| `anomalia_lluvia_90d_pct` | Lluvias de los últimos 3 meses (contra lo normal) |
| `riesgo_termico_verano` / `T2M_MIN` | Riesgo de golpe de calor / Riesgo de heladas |
| `EVPTRNS` | Demanda de agua del ambiente |
| `soc`, `clay/sand/silt`, `phh2o` | Materia orgánica · Tipo de suelo ("Franco limoso") · Acidez del suelo (pH) |
| `S_hidroclimatico` / `S_suelo` / `score_final` | Aptitud frente al agua y el clima / Aporte al suelo y la rotación / Puntaje general |
| `objetivo_productor` | Prioridad de manejo (Seguridad frente a sequía · Equilibrio · Conservación del suelo) |
| `cultivo_anterior` / `campana` | Cultivo antecesor en el lote / Campaña fina (invierno) · gruesa (verano) |
| `simulacion_what_if` | Simulación de escenarios |
| `prob_anio_malo` | Frecuencia: "3 de cada 10 campañas" |
| `riesgo: critico` | Riesgo muy alto |

**Formatos:** porcentajes enteros ("34 %") y anomalías con signo ("−24 %"); fechas humanas ("8 nov. 2026"), nunca ISO; puntajes "72 / 100"; rinde en qq/ha; coordenadas con 3 decimales como máximo, siempre secundarias. Todo número va con su lectura ("34 % · Reserva ajustada").

## Patrones y gotchas

- **Los componentes nunca llaman a `fetch`:** todo pasa por `src/services/*`. Los campos del backend no se renombran en los tipos; se traducen solo en la capa de presentación.
- Si cambia `backend/schemas.py`, actualizá `src/types/api.ts` en el mismo PR (o en un issue enlazado).
- **Leaflet `pathOptions`** exige colores literales: van en `mapColors.ts`, nunca inline.
- **Modo demo:** no llama a `PATCH /auth/me/provinces` y guarda la selección en memoria.
- **Polling de `reintento_en_curso`:** se consulta `GET /fields/{id}` cada 30 s solo mientras sea `true`.
- `npm run lint` tiene warnings previos en `App.tsx` (`set-state-in-effect`, `exhaustive-deps`). No sumes nuevos.
