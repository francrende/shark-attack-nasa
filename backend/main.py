"""App FastAPI de Shark Attack. Levantar desde ``backend/``: ``uvicorn main:app --reload --port 8000``."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ml.predictor import get_predictor
from routers.simulate import router as simulate_router

ORIGENES_CORS_DEFAULT = "http://localhost:5173,http://127.0.0.1:5173"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_predictor()  # carga modelo_agro.joblib una sola vez, antes del primer pedido
    yield


app = FastAPI(title="Shark Attack API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", ORIGENES_CORS_DEFAULT).split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(simulate_router)


@app.get("/health", tags=["salud"])
def health() -> dict[str, str]:
    return {"status": "ok"}
