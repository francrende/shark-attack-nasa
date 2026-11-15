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
from providers.nasa_telemetry import ESPACIO_HIST, configurar_lector_hist  # noqa: E402
from providers.soilgrids import ESPACIO_GRILLA, registrar_grilla  # noqa: E402
from services.reintentos_campos import detener_reintentos, iniciar_reintentos  # noqa: E402
from routers import auth, campaigns, fields  # noqa: E402
from routers.simulate import router as simulate_router  # noqa: E402
from routers.telemetry import router as telemetry_router  # noqa: E402

settings = get_settings()

_cache_persistente: CacheSupabase | None = None
_filas_precargadas = 0
_puntos_grilla_suelo = 0


async def _iniciar_cache_persistente() -> CacheSupabase | None:
    """BACK-18: precarga la caché de Supabase y la enchufa como capa secundaria."""
    global _filas_precargadas, _puntos_grilla_suelo
    cache = crear_cache_supabase(settings)
    if cache is None:
        return None
    filas = await asyncio.to_thread(cache.hidratar)
    _filas_precargadas = filas
    # BACK-19: la grilla de suelo viene en la misma precarga (sin consultas extra).
    _puntos_grilla_suelo = registrar_grilla(cache.entradas(ESPACIO_GRILLA))
    logger.info("cache_supabase: %d filas precargadas (%d puntos de grilla de suelo)", filas, _puntos_grilla_suelo)
    configurar_cache(CacheEnCapas(CacheMemoria(), secundaria=cache, ttl_por_espacio=TTL_POR_ESPACIO_DEFAULT))
    # BACK-26: el clima histórico por celda se lee de Supabase bajo demanda (JSON de respaldo).
    configurar_lector_hist(lambda clave: cache.leer(ESPACIO_HIST, clave))
    return cache


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Precarga el modelo ML y la caché persistente antes del primer request."""
    global _cache_persistente
    get_predictor()
    _cache_persistente = await _iniciar_cache_persistente()
    # BACK-25: reintentos de ISRIC/SRTM en segundo plano (misma bandera que la caché persistente).
    await iniciar_reintentos(settings)
    try:
        yield
    finally:
        await detener_reintentos()
        if _cache_persistente is not None:
            configurar_lector_hist(None)
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


@app.head("/health", include_in_schema=False)  # BACK-16: pings con HEAD; fuera del OpenAPI (sin ID duplicado)
@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str | bool | int]:
    """Verifica el estado del servidor y si Supabase está configurado.

    Acepta HEAD además de GET (BACK-16): algunos servicios de ping (UptimeRobot)
    consultan con HEAD, y sin esto FastAPI responde 405.
    """
    return {
        "status": "ok",
        "supabase_configured": settings.is_supabase_configured,
        "cache_persistente": _cache_persistente is not None,
        # Filas de provider_cache bajadas en el último arranque (verificación sin mirar logs).
        "cache_filas_precargadas": _filas_precargadas,
        "grilla_suelo_puntos": _puntos_grilla_suelo,
    }
