# BACK-33: Riesgo térmico coherente entre `/telemetry` y `/simulate`

- **Issue:** EREIA-5 (Multica)
- **Módulos:** BACK, ML
- **Depende de:** BACK-24

## Objetivo

Que Info general y Planificación de campaña no muestren dos riesgos de golpe de calor distintos para el mismo lote, o que la diferencia se explique en la UI.

## Contexto

- En verano, `/simulate` calcula `telemetria_nasa.riesgo_termico_verano` con los días de calor de los **años análogos de la fase ENSO vigente** (ML-12).
- `/telemetry` lo calcula con el **promedio histórico** de la celda.
- Para el mismo lote puede dar "medio" en una pestaña y "bajo" en la otra. Se observó en BACK-24, en (−33,40, −62,80).
- Código: [`backend/providers/nasa_telemetry.py`](../backend/providers/nasa_telemetry.py) (`indicadores_telemetria`), [`backend/services/simulation_service.py`](../backend/services/simulation_service.py) y [`backend/ml/escenarios.py`](../backend/ml/escenarios.py).

## Alcance por módulo

### BACK

- Archivos: `backend/services/telemetry_service.py`, `backend/providers/nasa_telemetry.py`, `backend/schemas.py` (si cambia el contrato), tests.
- Cambios, según la opción elegida:
  - (a) `/telemetry` también usa los análogos de la fase ENSO.
  - (b) Los dos endpoints exponen ambos valores con nombres distintos.

### ML

- Archivos: `backend/ml/escenarios.py` (solo si hay que exponer una función de días de calor por fase reutilizable).
- Cambios: validar que la opción elegida no cambie las features del modelo.

## Criterios de aceptación

- [ ] Para el mismo lote y la misma fecha, las dos pestañas muestran el mismo riesgo térmico, o dos indicadores con etiquetas distintas que se entienden en la UI.
- [ ] El golden `simulate_golden_back24.json` no cambia, salvo que se elija la opción (b).
- [ ] Hay un test que compara los dos endpoints para un mismo punto mockeado.

## Cómo verificar

```bash
cd backend && python -m pytest routers/test_telemetry.py routers/test_simulate.py -q
```

## Fuera de alcance

- Cambiar el umbral de calor (va con ML-23).

## Preguntas abiertas

- ¿Opción (a) o (b)? (a) es más simple para el productor; (b) conserva la referencia histórica en Info general.
