# ML — modelo de rinde, motor de recomendación y agronomía

Lo global está en el [`AGENTS.md`](../../AGENTS.md) de la raíz y lo del servidor en [`backend/AGENTS.md`](../AGENTS.md). Este módulo es dueño de `backend/ml/` y de `backend/services/rotation_matrix.py`.

## Stack

scikit-learn 1.9.1 (`HistGradientBoostingRegressor` con restricciones de monotonía), numpy, pandas y joblib. `matplotlib` solo para reportes: `pip install -r ml/requirements-dev.txt`.

## Estructura

```
predictor.py           AgroPredictor + get_predictor() (singleton). predict_ensemble (planificación) y
                       predict_seguimiento (campaña sembrada). Fusión MCDA, riesgo, explicación, factores clave
escenarios.py          años análogos por fase ENSO (desde 1981) y ventana mezclada para el seguimiento
calibracion.py         distribución predictiva fuera de muestra: prob. de año malo, rango año malo/bueno, puerta por cultivo
calendario_siembra.py  inicio de siembra y OFFSET_PERIODO_CRITICO por cultivo
magyp.py               rindes MAGyP, tendencias Theil–Sen y label (--tendencias regenera tendencias_magyp.json)
rinde.py, departamentos.py  puntaje → kg/ha con la tendencia del departamento más cercano (hasta 75 km)
fao_labels.py          curvas FAO GAEZ/FAO-56: solo para filas What-If, línea base y factor Ky
generate_dataset.py    arma el dataset (MAGyP + NASA POWER + SRTM + SoilGrids + ONI)
train_baseline.py      entrena, valida dejando una campaña afuera, calibra y guarda el bundle
visualize_model.py     gráficos en reports/
modelo_agro.joblib     bundle versionado (modelo + calibración + metadatos); se commitea
data/                  datasets .csv.gz, training_metrics.json, tendencias; raw/ y cache/ fuera de git
../services/rotation_matrix.py  pilar suelo, cobertura 12 meses, secuencias, lote ocupado, penalización hídrica
```

## Comandos (desde `backend/`)

```bash
python -m pytest ml services/test_rotation_matrix.py -q      # tests del módulo
python -m ml.generate_dataset [--solo-descargas | --sin-red]  # dataset; necesita ml/data/raw/estimaciones_agricolas.csv
python -m ml.train_baseline                                  # reentrena y recalibra (tarda)
python -m ml.train_baseline --solo-evaluar                   # reevalúa el bundle guardado
python -m ml.train_baseline --solo-calibrar                  # recalcula solo la distribución predictiva
python -m ml.train_baseline --seguimiento                    # prueba retrospectiva del seguimiento
python -m ml.visualize_model                                 # regenera reports/*.png
python -m ml.magyp --tendencias                              # regenera data/tendencias_magyp.json
```

`ml/data/raw/estimaciones_agricolas.csv` (MAGyP) no está en git. Se descarga del portal de datos de MAGyP y va en esa ruta.

## Cómo funciona (invariantes)

- **Label:** rinde MAGyP departamental, ajustado por la superficie abandonada, contra su tendencia: `puntaje = 50 + 100 × (rinde / tendencia − 1)`. **50 es un año normal.** Solo los 8 cultivos con rinde MAGyP entran al modelo.
- **Coberturas y camelina** (`vicia_cobertura`, `avena_cobertura`, `camelina`) no pasan por el modelo. Se puntúan relativo a trigo y cebada con el `Ky` de FAO-56: `S = 50 + Ky/Ky_ref × (S_ref − 50)`.
- **Features:** estado del suelo en `[t−89, t]` (conocido al decidir) + clima del período crítico (90 días desde `inicio_siembra + OFFSET`) + suelo, topografía, cultivo, `dias_hasta_siembra` y `oni_actual`.
  - En el entrenamiento, el período crítico es el observado.
  - En producción son **años análogos** de la misma fase ENSO (o los de ONI más parecido, si la fase tiene menos de 5 años).
  - Las fórmulas viven en `providers/features.py` y las comparten los dos regímenes.
- **Monotonía:** más días de calor o de helada nunca suben el puntaje. No la saques.
- **Validación:** siempre agrupada por campaña (dejar una campaña afuera). Las filas de un mismo año están correlacionadas entre departamentos: la unidad independiente es la **campaña**, no la fila.
- **Distribución predictiva:** el rango y la probabilidad de año malo salen del error real fuera de muestra (`calibracion.py`), no del P10 de los análogos. Un cultivo publica `prob_anio_malo` solo si le gana a la frecuencia típica fuera de muestra; si no, `null` y `anticipa_diferencias = false`.
- **Puntaje final:** `w_clima · S_hidroclimatico + w_suelo · S_suelo`, con pesos por `objetivo_productor`: resiliencia 0,75/0,25, equilibrio 0,5/0,5, conservación 0,3/0,7.
  - Con `GWETROOT` < 45 % se resta hasta 10 puntos por la demanda hídrica del cultivo.
  - Los cultivos no sembrables (lote ocupado o fuera de ventana) van al final del ranking y nunca se recomiendan.
- **Umbrales de riesgo** (`predictor.py`): crítico < 40, alto 40–45, medio 45–50, bajo ≥ 50.
  - Sube un nivel si el P10 de los análogos es < 30.
  - Con `S_suelo` < 35 el riesgo es al menos alto.
  - Un año análogo es desfavorable si su puntaje es < 40.

## Al cambiar el modelo

- Toda mejora se mide **fuera de muestra en régimen de producción** (años análogos, no clima observado). Se compara contra el bundle actual y contra las líneas base "año normal" y "frecuencia típica": Brier, AUC de año malo, cobertura de P10/P90 y MAE.
- Reentrenar cambia `modelo_agro.joblib`, `data/training_metrics.json` y, si corresponde, `reports/`. Commiteá los tres juntos y poné las métricas antes/después en el PR.
- Si cambia la versión de scikit-learn, actualizá `backend/requirements.txt` en el mismo PR. El bundle guarda `sklearn_version`.
- Tiempo de `/simulate` < 1,5 s y RAM del proceso < 400 MB: el ensemble corre en **un solo batch** `años × cultivos`, nunca un `predict` por fila.

## Límites que la salida siempre tiene que comunicar

- Antes de sembrar, el rinde es poco predecible: rango y probabilidad, nunca "predicción de rinde" con un número.
- El rinde es del **departamento**, no del lote. El clima es regional (celdas de unos 50 km).
- Los nutrientes se estiman, no se miden. P, K y pH reales salen solo de un análisis de suelo.
- Los efectos de rotación aprendidos de datos observacionales pueden confundir causa con selección: hay que validarlos contra ensayos.
- Consumos de agua y puntajes de la matriz de rotación son orientativos y requieren validación local.
