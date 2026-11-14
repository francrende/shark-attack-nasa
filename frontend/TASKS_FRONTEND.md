# TASKS_FRONTEND.md — Tablero y Protocolo de Tareas Atómicas (Track Frontend, GIS & UI/UX)

> **Fuente de la Verdad:** Antes de proponer o programar cualquier tarea, el agente DEBE leer [`../CONTEXT.md`](../CONTEXT.md) (especialmente las **Secciones 3.2, 5, 6 y 8.2.C**).

---

## 1. Protocolo Obligatorio para el Agente (Cómo trabajar con el Desarrollador)

Cada vez que el desarrollador te pida crear, detallar o avanzar con una tarea de Frontend, seguí **estrictamente estos 4 pasos en orden**:

1. **Consultar el Boceto General:** Revisá el flujo de usuario (Sección 6), las capas satelitales de NASA GIBS (Sección 3.2), el contrato JSON (Sección 5) y el boceto de Frontend (Sección 8.2.C) en [`../CONTEXT.md`](../CONTEXT.md).
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

*(Vacío inicialmente — El agente irá agregando aquí cada tarea junto con el desarrollador luego de la etapa de preguntas).*

| ID | Tarea Atómica | Archivos Involucrados | Depende de | Estado |
| :--- | :--- | :--- | :---: | :---: |
| *Ej: FRONT-1* | *(A definir con el agente)* | `frontend/src/...` | — | `[ ]` |

---

## 4. Plantilla para Especificar cada Nueva Tarea

Cuando el agente y el desarrollador terminen de responder las preguntas de definición de una tarea, el agente debe agregarla aquí abajo siguiendo este formato:

```markdown
### `[ ]` FRONT-X: <Título corto de la tarea>
- **Objetivo:** <Qué resuelve exactamente esta unidad atómica>
- **Archivos Permitidos:** `<lista de archivos exclusivos>`
- **Decisiones Acordadas con el Desarrollador:**
  - <Decisión 1 respondida en las preguntas previas>
  - <Decisión 2 respondida en las preguntas previas>
- **Especificación Técnica:**
  1. <Paso técnico 1>
  2. <Paso técnico 2>
- **Definition of Done (Comando de Verificación):**
  - `cd frontend && npx tsc -b`
```
