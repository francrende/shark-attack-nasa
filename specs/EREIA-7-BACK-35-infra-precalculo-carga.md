# BACK-35: Precálculo offline, workers y test de carga

- **Issue:** EREIA-7 (Multica)
- **Módulos:** BACK
- **Depende de:** — (conviene antes de ML-22, ML-24 y ML-25, que suman descargas pesadas)

## Objetivo

Que sumar modelos y fuentes (ERA5-Land, NDVI, pronóstico estacional) no rompa los objetivos de `/simulate` < 1,5 s y RAM < 400 MB. El request solo combina modelos chicos sobre datos ya preparados; lo pesado corre offline.

## Contexto

Medición del 2026-11-17 con el modelo actual:

| Medición | Valor |
| :--- | :--- |
| `modelo_agro.joblib` | 0,25 MB |
| RAM al cargarlo | ~120 MB, casi toda por importar scikit-learn y numpy |
| Predecir 2.000 filas | ~260 ms en la primera llamada, contando el arranque |
| Límite de Render Free | 512 MB |

- Los modelos no son el cuello de botella: las llamadas a APIs externas ya son la mayor parte del tiempo de `/simulate`.
- La caché persistente en Supabase (`provider_cache`) y el clima por celda ya existen (BACK-18, BACK-26).

## Alcance por módulo

### BACK

- Archivos: `backend/providers/*`, `backend/main.py`, scripts nuevos de jobs, `backend/sql/schema.sql`.
- Cambios:
  1. **Jobs programados** (diario o semanal): precalculan y guardan en Supabase los datos ya resumidos por celda o departamento (clima, pronóstico estacional, NDVI). El request solo lee.
  2. **Worker en segundo plano** para recortes por lote (Sentinel-2/HLS); el resultado se guarda en `campaigns.simulacion_json`.
  3. Elegir la tecnología de jobs (cron de Render, GitHub Actions o Celery/Redis), con PostGIS si hace falta geometría.
  4. **Test de carga reproducible** (por ejemplo, `locust` o un script con `httpx`) que mida p50/p95 de `/simulate` y la RAM del proceso.
  5. Plan de hosting: Render Starter o superior en producción. El ping de BACK-17 queda solo mientras dure el plan Free.

## Criterios de aceptación

- [ ] Hay un comando de test de carga documentado en `backend/AGENTS.md`, con resultado base registrado en el issue.
- [ ] `/simulate` con caché tibia: p95 < 1,5 s; RAM < 400 MB.
- [ ] Ningún request descarga datasets pesados: todo sale de tablas precalculadas o de la caché.

## Cómo verificar

```bash
cd backend && python -m pytest -q
# + el comando de test de carga que se agregue
```

## Fuera de alcance

- Las fuentes nuevas en sí (ML-22, ML-24, ML-25).

## Preguntas abiertas

- ¿Qué infraestructura de jobs, según el presupuesto (Render cron, GitHub Actions, Celery/Redis)?
