# TASKS_ML.md — Tablero y Protocolo de Tareas Atómicas (Track ML, FAO-56 & Agronomía)

> **Fuente de la Verdad:** Antes de proponer o programar cualquier tarea, el agente DEBE leer [`../../CONTEXT.md`](../../CONTEXT.md) (especialmente las **Secciones 4, 5 y 8**).

---

## 1. Protocolo Obligatorio para el Agente (Cómo trabajar con el Desarrollador)

Cada vez que el desarrollador te pida crear, detallar o avanzar con una tarea de Machine Learning o Agronomía, seguí **estrictamente estos 4 pasos en orden**:

1. **Consultar el Contexto General:** Revisá la arquitectura de ML y la matriz agronómica en la **Sección 4** y el contrato JSON en la **Sección 5** de [`../../CONTEXT.md`](../../CONTEXT.md).
2. **Hacer Preguntas de Definición (Obligatorio ANTES de cerrar la especificación o programar):**
   - No asumas decisiones agronómicas o de modelado que estén abiertas (ej. catálogo final de cultivos por campaña, puntajes exactos de penalización por monocultivo, comportamiento de las curvas FAO-56 ante sequía o exceso hídrico, hiperparámetros del modelo, umbrales para clasificar el riesgo como bajo/medio/alto/crítico, idioma y formato de `factores_clave_ml` y `explicacion`).
   - **Hacele preguntas claras y concretas al desarrollador** para alinear esos criterios antes de escribir la especificación final.
3. **Documentar la Tarea Atómica en este archivo:**
   - Con las respuestas del desarrollador, redactá la especificación de la tarea en la sección **3. Especificación de Tareas Atómicas** de este archivo usando la plantilla estándar y marcala como `[~]` (En progreso).
4. **Implementar y Verificar (Definition of Done):**
   - Escribí el código respetando el **Scope Exclusivo de Carpetas**, ejecutá las pruebas/entrenamiento de verificación y, cuando pasen sin errores, marcá la tarea como `[x]`.

---

## 2. Reglas de Aislamiento (Cero Conflictos en Git)

- **Archivos Permitidos (Scope Exclusivo de ML & Agronomía):**
  - `backend/ml/*` (`train_baseline.py`, `predictor.py`, `modelo_agro.joblib`, etc.)
  - `backend/services/rotation_matrix.py`
  - `backend/ml/TASKS_ML.md`
- **Archivos Prohibidos:** NO modificar `backend/schemas.py`, `backend/providers/*`, `backend/routers/*`, `backend/services/simulation_service.py`, `backend/main.py` ni `frontend/*` (pertenecen a otros miembros del equipo).

---

## 3. Tablero de Tareas Atómicas (ML & Agronomía)

*(Vacío inicialmente — El agente irá agregando aquí cada tarea junto con el desarrollador luego de la etapa de preguntas).*

| ID | Tarea Atómica | Archivos Involucrados | Depende de | Estado |
| :--- | :--- | :--- | :---: | :---: |
| *Ej: ML-1* | *(A definir con el agente)* | `backend/ml/...` | — | `[ ]` |

---

## 4. Plantilla para Especificar cada Nueva Tarea

Cuando el agente y el desarrollador terminen de responder las preguntas de definición de una tarea, el agente debe agregarla aquí abajo siguiendo este formato:

```markdown
### `[ ]` ML-X: <Título corto de la tarea>
- **Objetivo:** <Qué resuelve exactamente esta unidad atómica>
- **Archivos Permitidos:** `<lista de archivos exclusivos>`
- **Decisiones Acordadas con el Desarrollador:**
  - <Decisión 1 respondida en las preguntas previas>
  - <Decisión 2 respondida en las preguntas previas>
- **Especificación Técnica:**
  1. <Paso técnico 1>
  2. <Paso técnico 2>
- **Definition of Done (Comando de Verificación):**
  - `<comando ejecutable para comprobar que funciona>`
```
