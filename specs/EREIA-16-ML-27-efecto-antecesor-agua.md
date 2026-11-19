# ML-27: S1/S2, efecto del antecesor y agua que deja cada cultivo

- **Issue:** EREIA-16 (Multica)
- **Módulos:** ML, BACK
- **Depende de:** verificar la disponibilidad de los mapas de cultivo (primer paso de esta tarea)

## Objetivo

Reemplazar dos reglas a mano por modelos aprendidos de datos:

- **S1:** cuánto cambia el rinde del cultivo siguiente según el anterior. Reemplaza a `SPECIFIC_TRANSITION_SCORES`.
- **S2:** con cuánta agua queda el perfil después de cada cultivo. Reemplaza a `penalizacion_demanda_hidrica`.

## Contexto

- Las dos reglas están en [`backend/services/rotation_matrix.py`](../backend/services/rotation_matrix.py), y los consumos de agua (`CONSUMO_AGUA_CICLO_MM`) son orientativos.
- Hoy solo se conoce el `cultivo_anterior` que declara el usuario. Los mapas de cultivo darían la historia de rotación de cada píxel sin cargarla.
- **A verificar antes de modelar:** desde qué campaña hay mapas de INTA (Mapa Nacional de Cultivos) discriminados por cultivo, y qué cobertura y detalle de clases tiene MapBiomas en la Pampa argentina.

## Alcance por módulo

### ML

- Archivos: módulos nuevos en `backend/ml/`, `backend/services/rotation_matrix.py`, tests.
- Cambios:
  1. **S1, inferencia causal sobre datos observacionales** (double ML o matching): por ejemplo, "maíz tras soja" contra "maíz tras maíz" con el mismo clima y suelo. El antecesor no es aleatorio (los mejores lotes suelen llevar maíz), así que se valida contra ensayos de rotación.
  2. **S2, supervisado:** mapas de cultivo + humedad del suelo al cosechar (ERA5-Land, SAOCOM).
- **Dataset y versión:** Mapa Nacional de Cultivos de INTA y/o MapBiomas Argentina (colección y años), rinde o NDVI del cultivo siguiente, humedad ERA5-Land.
- **Métrica objetivo con umbral:** S1 con efectos del mismo signo que los ensayos de rotación publicados, con un intervalo de confianza que no incluya cero en las transiciones principales. S2 con error de agua al cosechar menor que la regla actual (MAE en mm, validado dejando una campaña afuera).
- **Baseline de comparación:** `SPECIFIC_TRANSITION_SCORES` y `penalizacion_demanda_hidrica` actuales.

### BACK

- Archivos: `backend/providers/` (lectura de los mapas de cultivo por lote), `backend/schemas.py`.
- Cambios: historia de rotación detectada de los últimos 5 años por lote, guardada en el campo, como alternativa a lo que declara el usuario.

## Criterios de aceptación

- [ ] Informe de disponibilidad de los mapas (años, clases, resolución) en el issue antes de modelar.
- [ ] Se cumplen las métricas; las reglas a mano se reemplazan detrás de una bandera hasta validarlas.
- [ ] La respuesta comunica que los efectos son observacionales y deben validarse contra ensayos.

## Cómo verificar

```bash
cd backend && python -m pytest services/test_rotation_matrix.py ml -q
```

## Fuera de alcance

- Carbono y erosión (ML-26).
- Planificador de secuencias (ML-28).
