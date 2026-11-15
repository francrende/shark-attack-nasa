"""Punto de entrada principal de la API FastAPI de Shark Attack."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import get_settings  # noqa: E402
from ml.predictor import get_predictor  # noqa: E402
from routers import auth, campaigns, fields  # noqa: E402
from routers.simulate import router as simulate_router  # noqa: E402

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_predictor()  # carga modelo_agro.joblib una sola vez, antes del primer pedido
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API de Shark Attack para gestión de usuarios, campos, campañas y simulación agronómica.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(fields.router)
app.include_router(campaigns.router)
app.include_router(simulate_router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str | bool]:
    """Verifica el estado del servidor y si Supabase está configurado."""
    return {
        "status": "ok",
        "supabase_configured": settings.is_supabase_configured,
    }
