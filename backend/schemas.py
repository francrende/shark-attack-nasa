"""Modelos Pydantic del contrato API (CONTEXT.md §5)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

RiesgoTermico = Literal["bajo", "medio", "alto", "critico"]


class TelemetriaNasa(BaseModel):
    """Bloque ``telemetria_nasa`` de la respuesta de ``POST /api/v1/simulate`` (dato satelital real)."""

    fecha_ultimo_dato_valido: date
    indice_humedad_radicular_pct: float
    indice_humedad_superficial_pct: float
    tendencia_humedad_15d_pct: float
    anomalia_lluvia_90d_pct: float
    frecuencia_tormentas_extremas_90d: int
    riesgo_termico_verano: RiesgoTermico
