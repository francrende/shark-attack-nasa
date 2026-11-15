"""Años análogos por cultivo en su período crítico, ponderados por ENSO (ML-7).

Lo usan el predictor en producción y ``train_baseline.py`` para evaluar igual que producción.
Para cada cultivo y cada año histórico ``y`` se miden tormentas, calor, heladas y lluvia en la
ventana crítica de ese cultivo en la campaña ``y`` (``calendario_siembra``). El peso del año es
gaussiano en la diferencia entre el ONI publicado hoy y el publicado en la misma fecha de ``y``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from ml import calendario_siembra as cal
from providers.enso import TablaOni, oni_al, pesos_por_oni
from providers.features import features_ventana


def fecha_equivalente(corte: date, anio_campana: int, anio_analogo: int) -> date:
    """La fecha de decisión ``corte`` trasladada a la campaña ``anio_analogo``."""
    anio = corte.year + (anio_analogo - anio_campana)
    try:
        return date(anio, corte.month, corte.day)
    except ValueError:  # 29/2
        return date(anio, 2, 28)


def pesos_analogos(
    corte: date,
    anio_campana: int,
    anios: Iterable[int],
    oni_actual: float | None,
    tabla: TablaOni | None = None,
) -> dict[int, float]:
    """Peso por año análogo según ENSO; uniforme si no hay ONI actual."""
    anios = list(anios)
    if oni_actual is None:
        return {a: 1.0 for a in anios}
    oni_analogos = {a: oni_al(fecha_equivalente(corte, anio_campana, a), tabla) for a in anios}
    return pesos_por_oni(oni_actual, oni_analogos)


def features_criticas(
    calendario_eventos: dict[int, str], calendario_lluvia: dict[int, str], cultivo: str, anio: int
) -> dict[str, Any] | None:
    return features_ventana(
        calendario_eventos, calendario_lluvia, cal.inicio_periodo_critico(cultivo, anio), cal.DIAS_PERIODO_CRITICO
    )


def escenarios_por_cultivo(
    calendario_eventos: dict[int, str],
    calendario_lluvia: dict[int, str],
    cultivos: Iterable[str],
    corte: date,
    *,
    anio_campana: int | None = None,
    oni_actual: float | None = None,
    excluir_anio: int | None = None,
    tabla: TablaOni | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """``{cultivo: [{anio, tormentas, calor, heladas, lluvia, peso}, ...]}`` con ventana completa."""
    anio_campana = cal.anio_campana(corte) if anio_campana is None else anio_campana
    anios = sorted(a for a in calendario_eventos if a != excluir_anio)
    out: dict[str, list[dict[str, Any]]] = {}
    pesos: dict[int, float] | None = None
    for cultivo in cultivos:
        lista = []
        for anio in anios:
            feats = features_criticas(calendario_eventos, calendario_lluvia, cultivo, anio)
            if feats is not None:
                lista.append({"anio": anio, **feats})
        if pesos is None:
            pesos = pesos_analogos(corte, anio_campana, anios, oni_actual, tabla)
        for e in lista:
            e["peso"] = pesos[e["anio"]]
        out[cultivo] = lista
    return out
