# ML-25: M3, seguimiento con NDVI

- **Issue:** EREIA-14 (Multica)
- **Módulos:** ML, BACK, FRONT
- **Depende de:** BACK-35 (worker para los recortes por lote)

## Objetivo

Achicar el rango del seguimiento en campaña mirando el cultivo y no solo el clima regional, y dar alertas ligadas a la etapa fenológica.

## Contexto

- ML-18 mostró que, con el período crítico completo, el clima regional solo achica el rango de ±32 a ±29 puntos. El Brier mejora de +3,4 % a +12,2 % y el AUC de 0,61 a 0,70.
- El seguimiento actual: `GET /api/v1/fields/{field_id}/campaigns/{campaign_id}/seguimiento` ([`backend/services/seguimiento_service.py`](../backend/services/seguimiento_service.py), `predict_seguimiento` en [`backend/ml/predictor.py`](../backend/ml/predictor.py)), que se guarda en `campaigns.simulacion_json["seguimiento"]`.
- MODIS Terra está al final de su vida útil: hay que prever VIIRS (VNP13).

## Alcance por módulo

### ML

- Archivos: `backend/ml/escenarios.py`, `backend/ml/predictor.py`, `backend/ml/train_baseline.py`, módulo nuevo de M3, bundle.
- Cambios:
  1. **Por departamento:** NDVI/EVI de MODIS o VIIRS con máscara de cultivo, como anomalía contra la climatología del píxel (acumulado y pico), más el clima observado por nivel de avance.
  2. **Etapa fenológica** estimada por grados-día desde `campaigns.fecha_inicio`, con alertas por etapa (calor en floración, helada en espigazón, déficit en R3–R5).
  3. **NDRE** (Sentinel-2) como indicador de deficiencia de N.
- **Dataset y versión:** MODIS MOD13Q1 / VIIRS VNP13A1 2000–2024, rinde MAGyP 2000–2024; anotar las colecciones y versiones.
- **Métrica objetivo con umbral:** con el período crítico completo, el rango P10–P90 se achica al menos un 20 % contra ML-18 (±29 puntos) con cobertura entre 8 % y 12 %, y el Brier contra la frecuencia típica > +12,2 %.
- **Baseline de comparación:** prueba retrospectiva de ML-18 (`python -m ml.train_baseline --seguimiento`, `reports/09_seguimiento_retrospectivo.png`).

### BACK

- Archivos: `backend/providers/` (NDVI por departamento, recorte Sentinel-2/HLS por `fields.polygon`), worker de BACK-35, `backend/schemas.py`.
- Cambios: serie de NDVI del lote comparada contra el departamento. Opcional: balance hídrico del lote día a día con un pronóstico de corto plazo publicado (7–14 días, por ejemplo Open-Meteo) para avisar "entra en estrés en ~10 días".

### FRONT

- Archivos: `frontend/src/components/SeguimientoCampana.tsx`, `src/types/api.ts`, `src/utils/lenguajeProductor.ts`.
- Cambios: "Verdor del cultivo" del lote contra la zona ("Su lote va 12 % arriba de la zona"), etapa estimada y alertas por etapa.

## Criterios de aceptación

- [ ] Se cumple la métrica objetivo en la prueba retrospectiva.
- [ ] El recorte por lote corre en segundo plano; el endpoint de seguimiento solo lee.
- [ ] La UI muestra NDVI y etapa sin siglas técnicas.

## Cómo verificar

```bash
cd backend && python -m ml.train_baseline --seguimiento && python -m pytest -q
cd frontend && npm run build && npm run lint
```

## Fuera de alcance

- Modelo directo de planificación (ML-24).
- Zonas de manejo dentro del lote (ML-29).

## Preguntas abiertas

- ¿El pronóstico de corto plazo entra en esta tarea o queda aparte?
