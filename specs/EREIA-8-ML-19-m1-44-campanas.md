# ML-19: M1 con 44 campañas, tendencia flexible y ponderación por superficie

- **Issue:** EREIA-8 (Multica)
- **Módulos:** ML
- **Depende de:** ML-22 (decidir antes si el clima se migra a ERA5-Land y CHIRPS, para no entrenar dos veces)

## Objetivo

Pasar de 19 a 44 campañas independientes (1981–2024) para el modelo con clima conocido (M1, el actual), que se usa en el What-If y como motor del seguimiento. Es la palanca más barata y la de mayor impacto esperado: el dato ya está local. Unifica ML-9 (1990+) y la palanca 1 de ML-19.

## Contexto

- Hoy son 19 campañas (2006/07–2024/25). El rinde de un año está muy correlacionado entre departamentos, así que la unidad independiente es la campaña. Cambiar hiperparámetros no ayudó: hacen falta más años.
- `backend/ml/data/raw/estimaciones_agricolas.csv` (MAGyP, fuera de git) ya trae, para las 5 provincias:

| Cultivo MAGyP | Años | Departamentos | Uso |
| :--- | :--- | :---: | :--- |
| trigo total, maíz, girasol, sorgo, soja total | 1981–2024 | 180–186 | Labels directos |
| cebada cervecera + forrajera | 1981–2015 (cebada total 2016–2024) | ~165 | Label de `cebada` |
| soja 1ra / soja 2da | 2000–2024 | 177 | Antes de 2000 solo hay soja total |
| avena | 1981–2024 | 190 | Posible label real de `avena_cobertura` |
| colza | 1991–2024 | 155 | Posible proxy de `camelina` |

- NASA POWER ya se usa desde 1981 para los años análogos (ML-13).
- La tendencia actual es lineal (Theil–Sen, [`backend/ml/magyp.py`](../backend/ml/magyp.py)) y no captura los quiebres de la siembra directa ni de la soja RR.
- Todas las filas pesan igual: un departamento de 1.000 ha pesa lo mismo que uno de 200.000 ha.
- `maiz_temprano` y `maiz_tardio` comparten el rinde "maíz".

## Alcance por módulo

### ML

- Archivos: `backend/ml/magyp.py`, `backend/ml/generate_dataset.py`, `backend/ml/train_baseline.py`, `backend/ml/calibracion.py`, `backend/ml/data/*`, `backend/ml/modelo_agro.joblib`, `backend/ml/test_dataset_magyp.py`, `backend/ml/test_predictor.py`.
- Cambios:
  1. Extender el dataset a 1981–2024 con las reglas de soja anterior a 2000 y cebada que se decidan (Preguntas abiertas).
  2. Tendencia flexible por departamento y cultivo (LOESS o spline penalizado), validada contra la lineal.
  3. Ponderación por superficie sembrada (combinada con el peso 1/n por campaña actual).
  4. Recalcular `tendencias_magyp.json`, la calibración (ML-16) y el seguimiento retrospectivo (ML-18).
- **Dataset y versión:** `estimaciones_agricolas.csv` de MAGyP (anotar la fecha de descarga en `dataset_magyp_metadata.json`); NASA POWER 1981–2025; bundle de partida `ml10-magyp` 2.2.0.
- **Métrica objetivo con umbral:** Brier fuera de muestra (dejando una campaña afuera, régimen de producción) contra la frecuencia típica **> +3,5 %**, sin empeorar el resultado sin 2022/23 (+1,9 %), y **al menos un cultivo de invierno** con mejora positiva. Secundarias: AUC de año malo fuera de muestra > 0,61; cobertura P10/P90 entre 8 % y 12 %; MAE What-If ≤ 14,9.
- **Baseline de comparación:** `backend/ml/data/training_metrics.json` del bundle actual, "año normal" (puntaje 50) y frecuencia típica por cultivo.

## Criterios de aceptación

- [ ] Dataset 1981–2024 generado y reproducible con `python -m ml.generate_dataset`.
- [ ] Se cumple la métrica objetivo, con la tabla antes/después en el PR.
- [ ] La calibración y la puerta por cultivo se recalculan solas en el entrenamiento.
- [ ] `python -m pytest -q` en verde, con `/simulate` dentro de 1,5 s.

## Cómo verificar

```bash
cd backend
python -m ml.generate_dataset
python -m ml.train_baseline
python -m ml.train_baseline --seguimiento
python -m ml.visualize_model
python -m pytest -q
```

## Fuera de alcance

- Modelo directo de producción (ML-24).
- Features nuevas del período crítico (ML-23).
- Clima ERA5-Land (ML-22).

## Preguntas abiertas

- Antes de 2000, ¿la soja total se asigna a `soja_primera` (con una feature de "era") o se excluye?
- ¿Qué tendencia flexible: LOESS o spline?
- ¿Avena y colza pasan a ser labels de `avena_cobertura` y `camelina`, o quedan como experimento aparte?
