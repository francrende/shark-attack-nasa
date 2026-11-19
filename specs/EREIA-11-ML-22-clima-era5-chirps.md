# ML-22: Clima con ERA5-Land y CHIRPS

- **Issue:** EREIA-11 (Multica)
- **Módulos:** ML, BACK
- **Depende de:** BACK-35 (las descargas pesadas no pueden ir en el request)

## Objetivo

Decidir, y si conviene migrar, el clima de entrenamiento y producción de NASA POWER (~50 km, humedad radicular hasta 1 m) a ERA5-Land (~9 km, desde 1950, 4 capas de humedad hasta 289 cm, todo lo necesario para ET0 Penman-Monteith) y CHIRPS (lluvia a 5 km desde 1981, calibrada con estaciones). Hay que decidirlo **antes** de ML-19, para no entrenar dos veces.

## Contexto

- Hoy todo el clima sale de NASA POWER ([`backend/providers/nasa_power.py`](../backend/providers/nasa_power.py), [`nasa_telemetry.py`](../backend/providers/nasa_telemetry.py)). `EVPTRNS` es evapotranspiración real, no demanda.
- Desde el 2026-11-17 se puede usar cualquier fuente, no solo NASA.
- Las estaciones de SMN e INTA sirven para validar y corregir sesgos.

## Alcance por módulo

### ML

- Archivos: `backend/ml/generate_dataset.py`, `backend/ml/escenarios.py`, dataset y bundle.
- Cambios: comparar NASA POWER contra ERA5-Land + CHIRPS en la misma configuración del modelo; validar contra estaciones.
- **Dataset y versión:** ERA5-Land diario (Copernicus CDS), CHIRPS 2.0 diario, 1981–2025, recorte Región Pampeana; anotar las versiones en `dataset_magyp_metadata.json`.
- **Métrica objetivo con umbral:** se migra si el MAE What-If (clima conocido) mejora al menos un 3 % y el Brier fuera de muestra en producción no empeora. Error contra estaciones SMN/INTA menor que el de NASA POWER en lluvia acumulada del período crítico.
- **Baseline de comparación:** bundle actual con NASA POWER (`training_metrics.json`).

### BACK

- Archivos: `backend/providers/` (provider nuevo), `backend/providers/cache_supabase.py`, jobs de BACK-35.
- Cambios: el dato reciente de producción sale de la misma fuente que el entrenamiento (paridad de features), precalculado por celda en Supabase. NASA POWER queda como respaldo y para la latencia de los últimos días (ERA5-Land tiene ~5 días de atraso).

## Criterios de aceptación

- [ ] Informe de comparación (en el issue o en el PR) con las métricas de arriba.
- [ ] Si se migra: entrenamiento y producción usan la misma fuente y las mismas funciones de features; tests en verde; `/simulate` < 1,5 s.
- [ ] Si no se migra: la decisión y los números quedan en el issue.

## Cómo verificar

```bash
cd backend && python -m ml.generate_dataset && python -m ml.train_baseline && python -m pytest -q
```

## Fuera de alcance

- Features nuevas sobre ERA5 (ML-23).
- Humedad SAOCOM por lote (ML-29).

## Preguntas abiertas

- ¿Acceso a CDS con qué cuenta? ¿Dónde se guarda el raster recortado?
