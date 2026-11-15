"""Punto de entrada principal de la API FastAPI de Shark Attack."""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("uvicorn.error")  # el logger que uvicorn ya muestra (logs de Render)

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import get_settings  # noqa: E402
from ml.predictor import get_predictor  # noqa: E402
from providers.cache import (  # noqa: E402
    TTL_POR_ESPACIO_DEFAULT,
    CacheEnCapas,
    CacheMemoria,
    configurar_cache,
)
from providers.cache_supabase import CacheSupabase, crear_cache_supabase  # noqa: E402
from providers.nasa_telemetry import ESPACIO_HIST, cargar_climatologia_precalculada  # noqa: E402
from routers import auth, campaigns, fields  # noqa: E402
from routers.simulate import router as simulate_router  # noqa: E402
from routers.telemetry import router as telemetry_router  # noqa: E402

settings = get_settings()

_cache_persistente: CacheSupabase | None = None


def _no_esta_en_el_precalculo(espacio: str, clave: str) -> bool:
    """No subir a Supabase el histórico de celdas que ya vienen en el JSON del repo."""
    return not (espacio == ESPACIO_HIST and clave in cargar_climatologia_precalculada())


async def _iniciar_cache_persistente() -> CacheSupabase | None:
    """BACK-18: precarga la caché de Supabase y la enchufa como capa secundaria."""
    cache = crear_cache_supabase(settings, filtro_escritura=_no_esta_en_el_precalculo)
    if cache is None:
        return None
    filas = await asyncio.to_thread(cache.hidratar)
    logger.info("cache_supabase: %d filas precargadas", filas)
    configurar_cache(CacheEnCapas(CacheMemoria(), secundaria=cache, ttl_por_espacio=TTL_POR_ESPACIO_DEFAULT))
    return cache


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Precarga el modelo ML y la caché persistente antes del primer request."""
    global _cache_persistente
    get_predictor()
    _cache_persistente = await _iniciar_cache_persistente()
    try:
        yield
    finally:
        if _cache_persistente is not None:
            await asyncio.to_thread(_cache_persistente.cerrar)


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
app.include_router(telemetry_router)


@app.api_route("/health", methods=["GET", "HEAD"], tags=["Health"])
def health_check() -> dict[str, str | bool]:
    """Verifica el estado del servidor y si Supabase está configurado.

    Acepta HEAD además de GET (BACK-16): algunos servicios de ping (UptimeRobot)
    consultan con HEAD, y sin esto FastAPI responde 405.
    """
    return {
        "status": "ok",
        "supabase_configured": settings.is_supabase_configured,
        "cache_persistente": _cache_persistente is not None,
    }
