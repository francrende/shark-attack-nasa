# ML-21: Ablación de las filas What-If con fórmula FAO

- **Issue:** EREIA-10 (Multica)
- **Módulos:** ML
- **Depende de:** —

## Objetivo

Medir si conviene quitar del entrenamiento las filas What-If cuyo label sale de la fórmula FAO (cerca del 4 % del peso), y quitarlas si no aportan.

## Contexto

- Desde ML-6 el label es el rinde real de MAGyP, pero el dataset conserva filas sintéticas What-If con label de la fórmula FAO ([`backend/ml/fao_labels.py`](../backend/ml/fao_labels.py)) para dar sensibilidad a los sliders.
- La fórmula sola predice peor que "año normal" (MAE 23,5 contra 18,4), así que esas filas pueden meter ruido.

## Alcance por módulo

### ML

- Archivos: `backend/ml/generate_dataset.py`, `backend/ml/train_baseline.py`, `backend/ml/modelo_agro.joblib` (solo si se adopta), `backend/ml/data/training_metrics.json`.
- Cambios: entrenar con y sin esas filas, con los mismos hiperparámetros y la misma validación, y comparar.
- **Dataset y versión:** dataset MAGyP actual (`dataset_magyp_*.csv.gz`), bundle `ml10-magyp` 2.2.0.
- **Métrica objetivo con umbral:** se adopta "sin filas FAO" si el Brier fuera de muestra en producción no empeora más de 0,5 % y la respuesta What-If sigue siendo monótona y con sentido (lluvia −25 % baja el puntaje de todos los cultivos).
- **Baseline de comparación:** bundle actual (`training_metrics.json`).

## Criterios de aceptación

- [ ] Tabla con y sin filas FAO en el PR: MAE en producción y What-If, Brier y AUC fuera de muestra.
- [ ] Decisión registrada en el issue; si se quitan, el bundle se reentrena.
- [ ] `test_predictor.py` en verde (incluidos los tests de sensibilidad What-If).

## Cómo verificar

```bash
cd backend && python -m ml.train_baseline && python -m pytest ml -q
```

## Fuera de alcance

- Reemplazar la sensibilidad What-If por M1 reentrenado (ML-19).
