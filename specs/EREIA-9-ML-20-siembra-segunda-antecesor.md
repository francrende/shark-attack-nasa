# ML-20: Fecha de siembra de segunda según el antecesor

- **Issue:** EREIA-9 (Multica)
- **Módulos:** ML
- **Depende de:** —

## Objetivo

Que los cultivos de segunda (`soja_segunda`, `maiz_tardio` y `sorgo` de segunda) distingan si vienen de cebada o de trigo. La cebada se cosecha 2–3 semanas antes, lo que permite sembrar antes y suele dar más rinde. Es una mejora acotada y no requiere reentrenar.

## Contexto

- Hoy los cultivos de segunda usan el mismo calendario después de trigo, cebada o camelina ([`backend/ml/calendario_siembra.py`](../backend/ml/calendario_siembra.py)), y el modelo no recibe el antecesor como feature. Por eso, tras trigo y tras cebada, el puntaje de agua y clima es idéntico.
- El texto del motivo de lote ocupado (ML-11, `motivo_lote_ocupado` en `backend/services/rotation_matrix.py`) dice "noviembre-diciembre" para todos los antecesores.

## Alcance por módulo

### ML

- Archivos: `backend/ml/calendario_siembra.py`, `backend/ml/escenarios.py`, `backend/ml/predictor.py`, `backend/services/rotation_matrix.py`, tests.
- Cambios:
  1. Adelantar el inicio de siembra de los cultivos de segunda cuando el antecesor es cebada (por ejemplo, 15 días), y con él el período crítico de los años análogos.
  2. Ajustar el texto del motivo: "noviembre" para cebada y "noviembre-diciembre" para trigo.
  3. Sin cambios en el bundle: la ventana se corre en la inferencia.
- **Dataset y versión:** no aplica (sin reentrenamiento); bundle actual.
- **Métrica objetivo con umbral:** ninguna métrica del modelo debe empeorar. Chequeo de cordura: con los mismos datos, el puntaje de `soja_segunda` tras cebada es distinto del de tras trigo.
- **Baseline de comparación:** salida actual de `/simulate` (golden `simulate_golden_back24.json` para antecesores que no sean cebada).

## Criterios de aceptación

- [ ] Para el mismo lote y la misma fecha, `soja_segunda` tras cebada usa un período crítico que empieza antes que tras trigo (test).
- [ ] El golden no cambia para antecesores que no sean cebada.
- [ ] El motivo de lote ocupado cambia según el antecesor.

## Cómo verificar

```bash
cd backend && python -m pytest ml services/test_rotation_matrix.py routers/test_simulate.py -q
```

## Fuera de alcance

- Fenología por grados-día y fecha de siembra real (ML-23).

## Preguntas abiertas

- ¿Cuántos días se adelanta tras cebada? ¿Y tras camelina?
