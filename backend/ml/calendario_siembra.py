"""Calendario de siembra pampeano y regla de campaña (ML-6).

Fuente única para el dataset (`generate_dataset.py`) y, desde ML-7, para el predictor
(`dias_hasta_siembra`). La regla de campaña es la de CONTEXT §4.1 y del backend
(`services/simulation_service.campana_vigente`): mes de (t + 45 días) entre abril y
septiembre → invierno.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

Campana = Literal["invierno", "verano"]

ANTICIPACION_CAMPANA_DIAS = 45
MESES_INVIERNO = range(4, 10)  # abril..septiembre
PASO_VENTANAS_DIAS = 10

# (mes, día) de inicio y fin de siembra. Calendario único pampeano acordado en ML-6.
CALENDARIO: dict[str, dict[str, object]] = {
    # Verano: anio_campana Y → siembra entre ago/Y y ene/Y+1
    "maiz_temprano": {"campana": "verano", "inicio": (9, 15), "fin": (10, 31)},
    "maiz_tardio": {"campana": "verano", "inicio": (12, 1), "fin": (1, 10)},
    "soja_primera": {"campana": "verano", "inicio": (10, 25), "fin": (12, 10)},
    "soja_segunda": {"campana": "verano", "inicio": (12, 10), "fin": (1, 15)},
    "girasol": {"campana": "verano", "inicio": (9, 15), "fin": (11, 15)},
    "sorgo": {"campana": "verano", "inicio": (11, 1), "fin": (12, 20)},
    # Invierno: anio_campana Y → siembra dentro del año Y
    "trigo": {"campana": "invierno", "inicio": (5, 20), "fin": (7, 31)},
    "cebada": {"campana": "invierno", "inicio": (6, 1), "fin": (7, 20)},
    "camelina": {"campana": "invierno", "inicio": (5, 15), "fin": (6, 30)},
    "vicia_cobertura": {"campana": "invierno", "inicio": (3, 1), "fin": (4, 30)},
    "avena_cobertura": {"campana": "invierno", "inicio": (2, 15), "fin": (4, 30)},
}


# Período crítico (ML-7): ventana de 90 días que arranca OFFSET días después del inicio de
# siembra y cubre la etapa que define el rinde (floración/llenado en verano, espigazón y llenado
# en los cereales de invierno, crecimiento en las coberturas).
DIAS_PERIODO_CRITICO = 90
OFFSET_PERIODO_CRITICO: dict[str, int] = {
    "maiz_temprano": 45,
    "maiz_tardio": 45,
    "soja_primera": 55,
    "soja_segunda": 45,
    "girasol": 45,
    "sorgo": 45,
    "trigo": 100,
    "cebada": 95,
    "camelina": 70,
    "vicia_cobertura": 0,
    "avena_cobertura": 0,
}


def campana_de(t: date) -> Campana:
    """Campaña habilitada en la fecha ``t`` (regla §4.1)."""
    centro = t + timedelta(days=ANTICIPACION_CAMPANA_DIAS)
    return "invierno" if centro.month in MESES_INVIERNO else "verano"


def anio_campana(t: date) -> int:
    """Año de inicio de la campaña MAGyP ("Y/Y+1") habilitada en ``t``.

    Verano: habilitada de mediados de agosto de Y a mediados de febrero de Y+1.
    Invierno: habilitada de mediados de febrero a mediados de agosto de Y.
    """
    if campana_de(t) == "verano" and t.month < 7:
        return t.year - 1
    return t.year


def _fecha_en_campana(cultivo: str, mes_dia: tuple[int, int], anio: int) -> date:
    mes, dia = mes_dia
    if CALENDARIO[cultivo]["campana"] == "verano" and mes < 7:
        return date(anio + 1, mes, dia)
    return date(anio, mes, dia)


def inicio_siembra(cultivo: str, anio: int) -> date:
    return _fecha_en_campana(cultivo, CALENDARIO[cultivo]["inicio"], anio)  # type: ignore[arg-type]


def fin_siembra(cultivo: str, anio: int) -> date:
    return _fecha_en_campana(cultivo, CALENDARIO[cultivo]["fin"], anio)  # type: ignore[arg-type]


def dias_hasta_siembra(cultivo: str, t: date, anio: int | None = None) -> int:
    """Días desde ``t`` hasta el inicio de siembra (negativo dentro de la ventana de siembra)."""
    anio = anio_campana(t) if anio is None else anio
    return (inicio_siembra(cultivo, anio) - t).days


def cultivos_de(campana: Campana) -> list[str]:
    return [c for c, meta in CALENDARIO.items() if meta["campana"] == campana]


def habilitacion(campana: Campana, anio: int) -> date:
    """Primer día en que ``campana`` del año de campaña ``anio`` queda habilitada."""
    dia = date(anio, 8, 1) if campana == "verano" else date(anio, 1, 1)
    while campana_de(dia) != campana:
        dia += timedelta(days=1)
    return dia


def fechas_ventana(campana: Campana, anio: int, paso: int = PASO_VENTANAS_DIAS) -> list[date]:
    """Fechas de evaluación t cada ``paso`` días, desde la habilitación hasta el último fin de siembra."""
    desde = habilitacion(campana, anio)
    hasta = max(fin_siembra(c, anio) for c in cultivos_de(campana))
    fechas = []
    t = desde
    while t <= hasta:
        fechas.append(t)
        t += timedelta(days=paso)
    return fechas


def inicio_periodo_critico(cultivo: str, anio: int) -> date:
    """Primer día de la ventana crítica de 90 días del cultivo en la campaña ``anio``."""
    return inicio_siembra(cultivo, anio) + timedelta(days=OFFSET_PERIODO_CRITICO[cultivo])
