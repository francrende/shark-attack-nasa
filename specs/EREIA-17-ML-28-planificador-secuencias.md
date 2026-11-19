# ML-28: Estado del lote, planificador de secuencias y explicación con cantidades

- **Issue:** EREIA-17 (Multica)
- **Módulos:** ML, BACK, FRONT
- **Depende de:** ML-24, ML-26, ML-27, BACK-34

## Objetivo

Pasar de "este cultivo tiene 72 puntos" a "le conviene X por estas razones medibles, y si hace Y pasa esto otro", simulando secuencias de 2 o 3 campañas.

## Contexto

- Hoy `compare_rotation_strategies` ([`backend/services/rotation_matrix.py`](../backend/services/rotation_matrix.py)) compara secuencias anuales con puntajes.
- `perfil_mercado` es texto fijo. Sin precios no hay margen.
- Ejemplo de la salida buscada:
  > **Recomendado: vicia de cobertura → maíz tardío.** Su lote viene de 2 sojas seguidas: exportó ~160 kg de N/ha y el carbono bajó ~0,4 t/ha. La vicia aporta ~60 kg de N al maíz (~$X en urea a precios de hoy). El maíz tardío deja 4 veces más rastrojo y la erosión estimada baja de 6 a 2 t/ha/año. Costo: la vicia consume ~40 mm; con el perfil al 55 % el riesgo es bajo. **Contra repetir soja:** a 3 años, margen similar (−4 %), 25 % menos riesgo de año malo y +0,6 t C/ha.

## Alcance por módulo

### ML

- Archivos: módulo nuevo `backend/ml/planificador.py`, `backend/ml/predictor.py`, `backend/services/rotation_matrix.py`.
- Cambios:
  1. **Estado del lote** por campaña: agua en el perfil (S2), balance de N y P (BACK-34), carbono y rastrojo (ML-26), riesgo de erosión (RUSLE), presión de enfermedades y malezas (años seguidos de la misma familia) e historia de rotación (ML-27).
  2. **Planificador:** estado → M2 (rinde y riesgo del cultivo 1) → S1/S2/S3 (cómo queda el lote) → cultivo 2 con ese estado → … → resultado a 3 años. Elección multiobjetivo (margen, riesgo, carbono, erosión, N a reponer) con los pesos de `objetivo_productor`. Reemplaza a `compare_rotation_strategies`.
  3. Una sola predicción en batch; se podan las ramas (los 3 mejores cultivos por campaña).
  4. Explicación desde cantidades + las variables que más pesaron (SHAP), traducidas a lenguaje de productor.
- **Dataset y versión:** los de las tareas de las que depende.
- **Métrica objetivo con umbral:** `/simulate` con planificador < 1,5 s; en una prueba retrospectiva, la secuencia recomendada no tiene más años malos que la estrategia testigo (repetir el antecesor).
- **Baseline de comparación:** `compare_rotation_strategies` actual.

### BACK

- Archivos: provider de precios (MATBA-ROFEX, Bolsa de Comercio de Rosario), `backend/schemas.py`, `backend/services/simulation_service.py`.
- Cambios: precios precalculados (jobs de BACK-35) para un pilar de margen bruto; contrato nuevo de secuencias a 3 años.

### FRONT

- Archivos: `frontend/src/components/RecommendationPanel.tsx` y componentes nuevos, `src/types/api.ts`.
- Cambios: comparación de secuencias a 3 años con las cantidades (N, carbono, erosión, margen, riesgo) y el contraste contra repetir el cultivo.

## Criterios de aceptación

- [ ] Cada número de la explicación sale de un modelo concreto, trazable en el código.
- [ ] Se cumple la métrica de tiempo; RAM < 400 MB.
- [ ] La UI muestra la secuencia recomendada contra la testigo sin siglas técnicas.

## Cómo verificar

```bash
cd backend && python -m pytest -q
cd frontend && npm run build && npm run lint
```

## Fuera de alcance

- Escala de lote (ML-29).
