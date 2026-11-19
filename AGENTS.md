# Shark Attack / Ereia — contexto para agentes

Plataforma AgTech de apoyo a la decisión para la Región Pampeana argentina (Buenos Aires, Córdoba, Entre Ríos, La Pampa y Santa Fe). Recomienda qué cultivo sembrar en la campaña vigente y compara rotaciones cruzando clima y humedad satelital (NASA POWER), topografía (SRTM), suelo (SoilGrids) y un modelo entrenado con rindes reales de MAGyP. Nació en NASA Space Apps 2026; la marca visible en la UI es **Ereia**.

## Mapa de módulos

| Módulo | Carpeta | Stack | Contexto propio |
| :--- | :--- | :--- | :--- |
| **BACK** | `backend/` (sin `ml/` ni `services/rotation_matrix.py`) | Python 3.14 + FastAPI + Supabase | [`backend/AGENTS.md`](backend/AGENTS.md) |
| **ML** | `backend/ml/` + `backend/services/rotation_matrix.py` | scikit-learn (HistGradientBoosting), pandas | [`backend/ml/AGENTS.md`](backend/ml/AGENTS.md) |
| **FRONT** | `frontend/` | React 19 + TypeScript + Vite + react-leaflet | [`frontend/AGENTS.md`](frontend/AGENTS.md) |

**Cómo se comunican:**

```
frontend ──HTTP JSON (VITE_API_URL)──► backend/routers ──► services ──► providers (NASA POWER, SRTM, SoilGrids, ONI, Supabase)
                                                              │
                                                              └──► ml.predictor (singleton get_predictor(), carga ml/modelo_agro.joblib al arrancar)
Supabase: Auth (JWT Bearer) + Postgres con RLS (profiles, fields, campaigns, provider_cache)
```

- El contrato frontend ↔ backend es `backend/schemas.py` (Pydantic), publicado en `/docs` y `/openapi.json`. Su espejo en TypeScript es `frontend/src/types/api.ts`. **Si cambia uno, cambia el otro en el mismo PR** o en dos issues enlazados.
- ML no hace I/O de red en producción: recibe features armadas por `backend/providers/features.py`. **Entrenamiento y producción usan las mismas funciones de features**; no dupliques fórmulas.
- Deploy: backend en Render (root `backend/`, auto-deploy desde `main`), frontend en Vercel. Los secretos viven solo en los dashboards y en `.env` locales (fuera del repo).

## Reglas de dominio compartidas

- **Campaña vigente** (FRONT, BACK y ML usan la misma regla): se mira el mes de hoy + 45 días. Si cae entre abril y septiembre, la campaña es `invierno`; si no, `verano`. El frontend bloquea la otra campaña y el backend la rechaza con `422`.
- **Cultivos:** `verano` = `maiz_temprano`, `maiz_tardio`, `soja_primera`, `soja_segunda`, `girasol`, `sorgo`. `invierno` = `trigo`, `cebada`, `vicia_cobertura`, `avena_cobertura`, `camelina`. Los identificadores en snake_case no se renombran.
- **Sin pronósticos forzados:** el sistema no inventa clima futuro. Usa estado observado, años análogos y el ENSO publicado. Toda predicción se muestra como rango y probabilidad, nunca como un número único.
- **Lenguaje de productor** en todo texto que vea el usuario: sin siglas técnicas (ver `frontend/AGENTS.md`). Los textos que arma el backend (`explicacion`, `advertencias`) siguen la misma regla.
- La herramienta apoya la decisión, no la reemplaza: cada respuesta dice qué datos faltan y sugiere validar con un agrónomo local.

## Flujo de trabajo con specs y Multica

El estado del proyecto (qué está hecho, qué falta, quién lo hace) vive **solo en Multica** (workspace `Ereia`). No escribas estado en archivos del repo.

1. Cada tarea es un issue en Multica con una spec en `specs/`.
2. Antes de implementar, leé el issue (`multica issue get <id>`) y la spec enlazada.
3. Si la spec es ambigua o le falta algo, preguntá antes de codear.
4. Al terminar, comentá en el issue qué se hizo y el link al PR.

Detalles:
- **Títulos de issue:** `BACK-N: …`, `FRONT-N: …` o `ML-N: …`, con N correlativo por módulo. Una funcionalidad que cruza módulos es **un** issue y **una** spec con una sección por módulo; lleva el prefijo del módulo principal y los labels de todos los que toca.
- **Specs:** copiá [`specs/_template.md`](specs/_template.md) a `specs/EREIA-<n>-<slug>.md` (el `EREIA-<n>` es el identificador real del issue). La spec describe qué y cómo verificar; no lleva estado.
- **Decisiones nuevas** que surjan durante la implementación: actualizá la spec en el mismo PR y dejá constancia en un comentario del issue.
- Para operar Multica: `multica issue list --output json`, `multica issue status <id> <estado>`, `multica issue comment add <id> --content-file <archivo>` (el archivo tiene que estar dentro del repo; borralo después).

## Git y PRs

- **Ramas:** una por issue, desde `main`, con el identificador: `<tipo>/EREIA-<n>-<slug>` (por ejemplo `feat/EREIA-12-auth-patch-me`). No commitees directo a `main`.
- **Commits:** Conventional Commits en español, con el módulo como scope y el identificador del issue: `feat(back): PATCH /auth/me (BACK-15, EREIA-12)`. Si un commit toca varios módulos, nombralos todos (`feat(ml,back): …`).
- **PRs:** el título lleva el `EREIA-<n>` para que Multica lo enlace. Usá `Closes EREIA-<n>` solo si mergear debe cerrar el issue. Describí qué se verificó y con qué comando.
- **Zona de cada módulo:** un PR toca solo las carpetas de su módulo. Si hace falta tocar otra (por ejemplo, ML necesita un campo nuevo en `schemas.py`), decilo en la spec y avisale a quien tiene ese módulo antes de mergear.
- No commitees `.env`, `backend/ml/data/raw/`, `backend/ml/data/cache/` ni `node_modules/`.

## Tests y verificación

Antes de abrir un PR, corré lo que aplique al módulo que tocaste:

```bash
# Backend + ML (desde backend/, con el .venv activo): unos 400 tests, sin red
cd backend && python -m pytest -q

# Frontend: chequeo de tipos + build, y lint
cd frontend && npm run build && npm run lint
```

- Los tests nunca usan la red ni la base real: `backend/conftest.py` apaga la caché persistente. Los `check_*_live.py` sí llaman a las APIs reales y se corren a mano.
- Cada test nuevo va junto al módulo que prueba (`test_<modulo>.py` en la misma carpeta).
- Las métricas del modelo se comparan contra `backend/ml/data/training_metrics.json`, no contra números escritos en docs.

## Estilo

- **Idioma:** código, docstrings, comentarios, mensajes de error y UI en **español** (identificadores sin tildes). Los términos técnicos estándar (`router`, `provider`, `fetch`) quedan en inglés.
- Python: type hints, `from __future__ import annotations`, funciones puras para los cálculos e I/O inyectable para testear.
- TypeScript estricto; nada de `any` nuevo sin justificar.
- Comentarios solo para el porqué (una decisión, un límite de una API). No referencies IDs de tareas en el código.

## Setup rápido

```bash
# Backend: http://localhost:8000 (Swagger en /docs)
cd backend
python -m venv .venv && .venv\Scripts\Activate.ps1   # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                                  # completar las credenciales de Supabase
uvicorn main:app --reload --port 8000

# Frontend: http://localhost:5173
cd frontend
npm install
cp .env.example .env.local                            # VITE_API_URL y usuario demo
npm run dev
```

El esquema de base está en `backend/sql/schema.sql` y se aplica a mano en el SQL Editor de Supabase.
