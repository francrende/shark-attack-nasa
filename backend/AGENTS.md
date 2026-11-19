# BACK — API FastAPI, providers y Supabase

Lo global (flujo con Multica, git, estilo) está en el [`AGENTS.md`](../AGENTS.md) de la raíz. `ml/` y `services/rotation_matrix.py` son del módulo ML: ver [`ml/AGENTS.md`](ml/AGENTS.md).

## Stack

Python 3.14.5, FastAPI 0.163, Pydantic 2 + pydantic-settings, httpx (async), supabase-py 2.34 y pytest 9. Las versiones están fijadas con `==` en `requirements.txt` porque el modelo se entrenó con `scikit-learn==1.9.1` y otra versión puede no cargarlo.

## Estructura

```
main.py          app, CORS, lifespan (caché persistente, grilla de suelo, cola de reintentos) y /health (GET y HEAD)
config.py        Settings desde .env: SUPABASE_URL, SUPABASE_KEY, SUPABASE_SECRET_KEY, CACHE_PERSISTENTE, CORS_ORIGINS
schemas.py       todos los modelos Pydantic de request y response (el contrato con el frontend)
routers/         endpoints, sin lógica de negocio
services/        lógica: simulation_service, datos_lote (servicio único de datos del lote), telemetry_service,
                 field_enrichment_service, reintentos_campos, seguimiento_service, historial_service
providers/       clientes externos y cálculo de features: nasa_power, nasa_telemetry, srtm, soilgrids, enso,
                 features, cache, cache_supabase, regional, resiliencia, supabase_client
providers/data/  respaldos versionados: climatologia_pampa.json, oni.ascii.txt, suelo_lotes_ejemplo.json
sql/schema.sql   tablas profiles, fields, campaigns y provider_cache, con RLS por usuario
```

## Endpoints (`/api/v1`)

- `auth`: `POST /register`, `POST /login`, `GET /me`, `PATCH /me/provinces`.
- `fields`: CRUD en `/fields` y `/fields/{id}`. Al crear o mover un campo se completan el suelo y la topografía.
- `campaigns`: CRUD en `/fields/{field_id}/campaigns` y `GET …/{campaign_id}/seguimiento`.
- `POST /simulate`, `GET /telemetry` y `GET /historial`.

La referencia completa está en `/docs`. Los endpoints con sesión usan `Authorization: Bearer <jwt de Supabase>` y leen con el token del usuario, así que RLS filtra solo. Solo la caché y la cola de reintentos usan la secret key.

## Comandos

```bash
cd backend
python -m pytest -q                                   # suite completa, sin red
python -m pytest routers/test_simulate.py -q          # un archivo
uvicorn main:app --reload --port 8000                 # dev
python -m providers.check_nasa_power_live             # chequeos contra APIs reales (también check_srtm_live,
                                                      # check_soilgrids_live, check_features_live, routers.check_simulate_live)
python -m providers.generar_precache                  # regenera respaldos de providers/data (usa red, tarda)
```

Producción (Render): `pip install -r requirements.txt` y `uvicorn main:app --host 0.0.0.0 --port $PORT`, con **un solo worker** porque el plan tiene 512 MB y cada worker carga el modelo.

## Patrones

- **Política de datos del lote** (`services/datos_lote.py`, el único punto de entrada para `/telemetry` y `/simulate`):
  - Suelo, materia orgánica, pendiente y elevación son fijos: se guardan en `public.fields` al crear el campo y de ahí se leen.
  - El clima histórico se guarda por celda de NASA POWER en Supabase (`provider_cache`), con `climatologia_pampa.json` como respaldo.
  - La humedad, la lluvia de 90 días y la tendencia van siempre en vivo, con caché de 6 h en memoria.
- **Resiliencia de providers:**
  - Timeout en vivo de 8 s y corte automático de 5 min tras un timeout o un 429.
  - Cascada de respaldos: suelo ISRIC → grilla ISRIC cada 100 km → GeoINTA regional. Topografía SRTM → elevación de NASA POWER → pendiente regional.
  - Todo respaldo devuelve una entrada en `advertencias`, y el campo queda con `reintentar_soilgrids` o `reintentar_srtm` en `true`.
- **Cola de reintentos** (`services/reintentos_campos.py`): reintenta cada 5 min hasta 12 veces, en modo `segundo_plano=True` (timeout largo, no toca el corte). `FieldResponse.reintento_en_curso` la refleja.
- **Errores:** `422` para un request inválido, incluida la campaña que no corresponde a la fecha. `503` si falta un provider sin respaldo. `/simulate` nunca predice sin años análogos (da 503), mientras que `/telemetry` es tolerante y responde con aviso.
- **I/O inyectable:** providers, reloj, cliente HTTP y cliente de Supabase se pasan como parámetros para poder testear sin red.

## Gotchas

- **NASA POWER tiene de 3 a 7 días de atraso** y devuelve `-999.0` en los últimos días. Siempre se pide una ventana de 30 a 90 días y se toma el último valor válido. `-999` nunca llega al frontend.
- **`GWETROOT` y `GWETTOP` son fracciones de saturación (0–1)**, no humedad volumétrica. En la API van como porcentaje (`× 100`).
- **Imports duales:** el código importa con `try: from backend.x …` y `except ImportError: from x …`, para que funcione desde la raíz y desde `backend/`. Los routers importan como `services.x` y `providers.x`. Importar el mismo módulo con los dos nombres crea **dos singletons** (pasó con la cola de reintentos).
- **ISRIC limita a 5 llamadas por minuto** y tarda de 5 a 25 s. OpenTopoData exige 1 s entre llamadas y tiene tope diario.
- **`TestClient(app)` corre el `lifespan`.** `conftest.py` pone `CACHE_PERSISTENTE=false`; no lo saques o los tests escriben en Supabase real.
- **Golden de regresión:** `routers/data/simulate_golden_back24.json` congela la salida de `/simulate`. Si un cambio la mueve a propósito, regenerala y explicá por qué en el PR.
- **`schema.sql` se aplica a mano:** no hay migraciones. Si agregás columnas, usá `alter table … add column if not exists` y avisá en el PR que hay que correrlo en Supabase.
