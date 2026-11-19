# BACK-24: Servicio único de datos del lote, con verificación de `field_id` en Render

- **Issue:** EREIA-4 (Multica)
- **Módulos:** BACK
- **Depende de:** BACK-22, BACK-23, BACK-26

## Objetivo

Cerrar BACK-24: que `GET /api/v1/telemetry` y `POST /api/v1/simulate` usen un solo servicio de datos del lote y que `/simulate` acepte `field_id`. El código está mergeado en `main` (`add9f18`). Falta el Definition of Done en Render con un campo real y su `field_id`.

## Contexto

- El servicio único está en [`backend/services/datos_lote.py`](../backend/services/datos_lote.py), con la política descripta en [`backend/AGENTS.md`](../backend/AGENTS.md) ("Política de datos del lote").
- `/simulate` acepta `field_id`: sin token da `401`, un campo ajeno o inexistente `404`, y coordenadas a más de 0,001° del campo `422`.
- El frontend ya envía `field_id` y `Authorization` en `/simulate` (FRONT-40).
- Regresión: `backend/routers/data/simulate_golden_back24.json`.
- Verificado en Render el 15/11/2026 sin `field_id`: los seis indicadores coinciden entre los dos endpoints.
- `riesgo_termico_verano` difiere en verano a propósito (ML-12). Ese tema va en BACK-33, no acá.

## Alcance por módulo

### BACK

- Archivos: ninguno, salvo que la verificación encuentre un bug.
- Cambios: verificación en producción. Al terminar, avisar a quien tiene BACK-20 a BACK-23 (el servicio reescribió `telemetry_service.py`).

## Criterios de aceptación

- [ ] En Render, `GET /api/v1/telemetry?field_id=<id>` y `POST /api/v1/simulate` con ese mismo `field_id` devuelven el mismo `anomalia_lluvia_90d_pct`, la misma humedad radicular y superficial, la misma tendencia y las mismas tormentas.
- [ ] Con un campo que ya tiene suelo y topografía reales (`reintentar_soilgrids = false`, `reintentar_srtm = false`), `/simulate` no consulta ISRIC ni SRTM (logs de Render).
- [ ] El resultado de la verificación queda en un comentario del issue, con fecha y el campo usado.

## Cómo verificar

```bash
cd backend && python -m pytest -q   # sigue en verde
```

Manual: desde `https://shark-attack-nasa.vercel.app`, con el usuario demo, elegir un campo, abrir Info general y Planificar, y comparar en DevTools → Network las respuestas de `/telemetry` y `/simulate`.

## Fuera de alcance

- Unificar `riesgo_termico_verano` entre los endpoints (BACK-33).
