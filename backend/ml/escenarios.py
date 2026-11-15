"""Años análogos por cultivo en su período crítico, ponderados por ENSO (ML-7).

Lo usan el predictor en producción y ``train_baseline.py`` para evaluar igual que producción.
Para cada cultivo y cada año histórico ``y`` se miden tormentas, calor, heladas y lluvia en la
ventana crítica de ese cultivo en la campaña ``y`` (``calendario_siembra``). Son análogos los
años cuya fase ENSO (ONI publicado en la misma fecha de ``y``) coincide con la de hoy (ML-12).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta
from typing import Any

from ml import calendario_siembra as cal
from providers.enso import TablaOni, oni_al, pesos_por_fase
from providers.features import contar_eventos, decodificar_lluvia, features_de_tramos, features_ventana, tramo


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
    """Peso por año: 1 si comparte la fase ENSO de hoy, 0 si no; uniforme si no hay ONI actual."""
    anios = list(anios)
    if oni_actual is None:
        return {a: 1.0 for a in anios}
    oni_analogos = {a: oni_al(fecha_equivalente(corte, anio_campana, a), tabla) for a in anios}
    return pesos_por_fase(oni_actual, oni_analogos)


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
    """``{cultivo: [{anio, tormentas, calor, heladas, lluvia, peso}, ...]}`` con ventana completa.

    Solo devuelve los años análogos (peso > 0): los de otra fase ENSO no aparecen.
    """
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
        out[cultivo] = [e for e in lista if e["peso"] > 0.0]
    return out


# ---------------------------------------------------------------------------
# ML-18: seguimiento en campaña (ventana mezclada)
# ---------------------------------------------------------------------------


def inicio_periodo_critico_real(cultivo: str, fecha_siembra: date) -> date:
    """Inicio del período crítico a partir de la fecha de siembra real (no del calendario fijo)."""
    return fecha_siembra + timedelta(days=cal.OFFSET_PERIODO_CRITICO[cultivo])


def dias_observados(inicio: date, ultimo_dato: date, dias: int = cal.DIAS_PERIODO_CRITICO) -> int:
    """Días del período crítico ``[inicio, inicio+dias)`` que ya tienen dato observado."""
    return max(0, min(dias, (ultimo_dato - inicio).days + 1))


def ventana_mezclada(
    observado_eventos: dict[int, str],
    observado_lluvia: dict[int, str],
    analogo_eventos: dict[int, str],
    analogo_lluvia: dict[int, str],
    inicio: date,
    inicio_analogo: date,
    d: int,
    dias: int = cal.DIAS_PERIODO_CRITICO,
) -> dict[str, Any] | None:
    """Features de una ventana de ``dias``: los ``d`` primeros observados y el resto del año análogo."""
    ev_obs = tramo(observado_eventos, inicio, d)
    ll_obs = tramo(observado_lluvia, inicio, d, ancho=2)
    ev_resto = tramo(analogo_eventos, inicio_analogo + timedelta(days=d), dias - d)
    ll_resto = tramo(analogo_lluvia, inicio_analogo + timedelta(days=d), dias - d, ancho=2)
    if ev_obs is None or ll_obs is None or ev_resto is None or ll_resto is None:
        return None
    return features_de_tramos(ev_obs + ev_resto, ll_obs + ll_resto)


def escenarios_en_curso(
    calendario_eventos: dict[int, str],
    calendario_lluvia: dict[int, str],
    observado_eventos: dict[int, str],
    observado_lluvia: dict[int, str],
    cultivo: str,
    fecha_siembra: date,
    ultimo_dato: date,
    oni_siembra: float | None,
    *,
    anio_campana: int | None = None,
    tabla: TablaOni | None = None,
    cache_pesos: dict[Any, dict[int, float]] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Años análogos del período crítico con los días ya observados de la campaña (ML-18).

    Para cada año análogo ``a`` (misma fase ENSO que el ONI publicado a la fecha de siembra) la
    ventana es: días observados ``[inicio, inicio + d)`` + resto del año ``a`` desde ``inicio_a + d``.
    Con ``d = 0`` coincide con los análogos antes de sembrar; con ``d = 90`` todos los años dan la
    ventana observada. Devuelve ``(escenarios, d)``.
    """
    inicio = inicio_periodo_critico_real(cultivo, fecha_siembra)
    d = dias_observados(inicio, ultimo_dato)
    anio_c = cal.anio_campana(fecha_siembra) if anio_campana is None else anio_campana
    anios = sorted(a for a in calendario_eventos if a != anio_c)
    clave = (fecha_siembra, anio_c, oni_siembra)
    if cache_pesos is not None and clave in cache_pesos:
        pesos = cache_pesos[clave]
    else:
        pesos = pesos_analogos(fecha_siembra, anio_c, anios, oni_siembra, tabla)
        if cache_pesos is not None:
            cache_pesos[clave] = pesos
    lista: list[dict[str, Any]] = []
    for a in anios:
        if pesos.get(a, 0.0) <= 0.0:
            continue
        inicio_a = fecha_equivalente(inicio, anio_c, a)
        feats = ventana_mezclada(
            observado_eventos, observado_lluvia, calendario_eventos, calendario_lluvia, inicio, inicio_a, d
        )
        if feats is not None:
            lista.append({"anio": a, **feats, "peso": pesos[a]})
    return lista, d


def clima_observado(
    calendario_eventos: dict[int, str],
    calendario_lluvia: dict[int, str],
    observado_eventos: dict[int, str],
    observado_lluvia: dict[int, str],
    inicio: date,
    d: int,
    anios_analogos: list[int],
    anio_campana: int,
) -> dict[str, Any] | None:
    """Lo que pasó en los ``d`` días observados y la lluvia mediana de los análogos esos mismos días."""
    if d <= 0:
        return None
    ev = tramo(observado_eventos, inicio, d)
    ll = tramo(observado_lluvia, inicio, d, ancho=2)
    if ev is None or ll is None:
        return None
    tormentas, calor, heladas = contar_eventos(ev)
    lluvias = []
    for a in anios_analogos:
        tramo_a = tramo(calendario_lluvia, fecha_equivalente(inicio, anio_campana, a), d, ancho=2)
        if tramo_a:
            lluvias.append(sum(decodificar_lluvia(tramo_a)))
    return {
        "desde": inicio,
        "dias": d,
        "lluvia_mm": round(float(sum(decodificar_lluvia(ll))), 1),
        "lluvia_normal_mm": round(float(sorted(lluvias)[len(lluvias) // 2]), 1) if lluvias else None,
        "dias_calor": int(calor),
        "heladas": int(heladas),
        "tormentas": int(tormentas),
    }
