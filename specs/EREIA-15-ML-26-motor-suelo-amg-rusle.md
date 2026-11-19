# ML-26: Motor de suelo S3 (AMG + RUSLE)

- **Issue:** EREIA-15 (Multica)
- **Módulos:** ML
- **Depende de:** — (mejor después de ML-19, porque usa el rinde predicho)

## Objetivo

Que el pilar suelo deje de ser un puntaje escrito a mano y pase a ser **cantidades**: t C/ha de carbono orgánico y t de suelo/ha/año de erosión. Además conecta los dos pilares: un año seco da menos rinde, menos rastrojo y menos carbono.

## Contexto

- Hoy `S_suelo` sale de puntajes a mano en [`backend/services/rotation_matrix.py`](../backend/services/rotation_matrix.py) (`carbon_balance`, `SPECIFIC_TRANSITION_SCORES`). No hay labels de suelo ni historia del lote.
- Un modelo no supervisado no alcanza: la pregunta "si siembro X, ¿cuánto cambia el carbono?" es causal y necesita un modelo de proceso.
- `meses_activos` y `meses_rastrojo` por cultivo ya existen en la matriz.

## Alcance por módulo

### ML

- Archivos: módulos nuevos `backend/ml/suelo_carbono.py` y `backend/ml/erosion.py`, `backend/services/rotation_matrix.py`, tests.
- Cambios:
  1. **Carbono (AMG, el que usa INTA en la Pampa, o RothC):**
     - Aporte = rinde predicho × índice de cosecha × relación raíz/parte aérea × coeficiente de humificación.
     - Mineralización según temperatura y arcilla.
     - Calibración con los ensayos de rotación de larga duración de INTA (Pergamino, Marcos Juárez, Balcarce) y perfiles fechados de SISINTA, más un ajuste de ML sobre el error.
  2. **Erosión hídrica (RUSLE):** erosividad desde la lluvia diaria, erodabilidad desde el suelo, LS desde el relieve (SRTM) y factor C mes a mes según la cobertura.
  3. `S_suelo` se deriva de esas cantidades (manteniendo la escala 0–100 y los pesos por `objetivo_productor`).
- **Dataset y versión:** ensayos de larga duración de INTA y SISINTA (anotar la fuente y la fecha); lluvia diaria de la fuente vigente (NASA POWER o ML-22).
- **Métrica objetivo con umbral:** error del carbono simulado contra los ensayos de INTA < 15 % del cambio observado a 10 años. RUSLE dentro del rango publicado para la Pampa (orientativo 1–20 t/ha/año según pendiente y cobertura).
- **Baseline de comparación:** `S_suelo` actual de la matriz (el orden de las rotaciones típicas no se debe invertir sin justificación).

## Criterios de aceptación

- [ ] `/simulate` expone carbono y erosión estimados por cultivo (contrato coordinado con BACK) y `S_suelo` sale de ellos.
- [ ] Tests con casos de referencia de los ensayos.
- [ ] La explicación dice que son estimaciones a validar.

## Cómo verificar

```bash
cd backend && python -m pytest services/test_rotation_matrix.py ml -q
```

## Fuera de alcance

- Efecto del antecesor sobre el rinde y agua que deja (ML-27).
- Balance de N y P (BACK-34).

## Preguntas abiertas

- ¿AMG o RothC? ¿Hay acceso a los datos de los ensayos de INTA?
