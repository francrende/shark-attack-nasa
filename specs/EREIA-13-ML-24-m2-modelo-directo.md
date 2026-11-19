# ML-24: M2, modelo directo y probabilístico con pronóstico estacional

- **Issue:** EREIA-13 (Multica)
- **Módulos:** ML, BACK
- **Depende de:** ML-19 (ML-23 suma)

## Objetivo

Un modelo entrenado **solo con lo que se sabe al momento de decidir**, que es el régimen en el que se usa, y que prediga directamente lo que se muestra: la probabilidad de año malo y el rango de rinde. M1 queda para el What-If y el seguimiento.

## Contexto

- Hoy un solo modelo cumple dos roles: se entrena con el clima observado del período crítico, pero en producción recibe años análogos. Por eso se "achata": en 2022/23 el puntaje real fue 22 y el predicho 44.
- La probabilidad y el rango se derivan del error de un modelo de media ([`backend/ml/calibracion.py`](../backend/ml/calibracion.py)).
- Fuera de muestra: Brier +3,5 % contra la frecuencia típica y AUC 0,61. Trigo, cebada, girasol y sorgo no anticipan.
- La hiperparametrización se elige hoy con clima observado.

## Alcance por módulo

### ML

- Archivos: `backend/ml/train_baseline.py`, `backend/ml/predictor.py`, `backend/ml/calibracion.py`, módulo nuevo de M2, bundle versionado con M1 + M2, tests.
- Cambios:
  1. Clasificador de "año malo" con calibración isotónica + regresión por cuantiles (P10, P50, P90).
  2. Features: estado actual del suelo y del agua; cultivo y días hasta la siembra; análogos **resumidos** (media y P10 de la lluvia crítica, días de calor esperados, fracción de análogos secos); pronóstico estacional C3S multimodelo o NMME (probabilidad por tercil de lluvia y temperatura para el trimestre crítico); pronóstico ENSO de IRI/CPC, IOD (DMI) y SAM/AAO.
  3. Selección de hiperparámetros dejando una campaña afuera **en régimen de producción**.
  4. Una fila por cultivo (no años × cultivos): baja el costo del request.
- **Dataset y versión:** el de ML-19 + archivo histórico de pronósticos (hindcasts) C3S/NMME e IRI para las mismas campañas; anotar las versiones en la metadata.
- **Métrica objetivo con umbral:** Brier fuera de muestra contra la frecuencia típica **> +7 %** (el doble del actual), AUC de año malo > 0,65, cobertura P10/P90 entre 8 % y 12 %, y al menos 2 cultivos de invierno con la puerta de publicación abierta.
- **Baseline de comparación:** distribución predictiva actual (ML-16) y bundle de ML-19.

### BACK

- Archivos: `backend/providers/` (providers de pronóstico estacional y teleconexiones), jobs de BACK-35, `backend/schemas.py` si cambia el contrato.
- Cambios: descarga mensual de C3S/NMME e IRI precalculada por celda, nunca dentro del request. El contrato de `/simulate` no cambia de forma: `prob_anio_malo`, `puntaje_anio_malo/bueno` y `rinde_kg_ha` pasan a salir de M2.

## Criterios de aceptación

- [ ] Se cumple la métrica objetivo, con la tabla antes/después en el PR.
- [ ] El bundle carga M1 y M2 una sola vez al arrancar (`get_predictor()`); RAM < 400 MB y `/simulate` < 1,5 s.
- [ ] Sin pronóstico estacional disponible, M2 cae a una versión sin esas features y lo avisa en `advertencias`.

## Cómo verificar

```bash
cd backend && python -m ml.train_baseline && python -m pytest -q
```

## Fuera de alcance

- Seguimiento con NDVI (ML-25).

## Preguntas abiertas

- ¿C3S o NMME? ¿Hay hindcasts suficientes desde 1981 o el entrenamiento de M2 arranca en 1993?
- Usar pronósticos publicados, ¿es compatible con la regla "sin pronósticos forzados"? (Propuesta: sí, porque son de terceros y se muestran como probabilidad.)
