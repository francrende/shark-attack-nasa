"""Features del modelo de ML: fórmulas únicas para entrenamiento y producción (BACK-6).

La parte superior del módulo son **funciones puras sin E/S** pensadas para que
``backend/ml/generate_dataset.py`` las importe en lugar de mantener su propia copia, de modo
que entrenamiento e inferencia calculen exactamente igual. Replican hoy la lógica de
``extract_real_90d_windows`` (esquema de doble ventana de CONTEXT.md §4.3).

``construir_insumos_ml`` (al final) es el orquestador online: consulta los providers y
devuelve las features actuales + los escenarios históricos por año de la ventana futura,
que el predictor usa como ensemble (``predict_ensemble``, lado ML).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # solo tipos; los imports reales son perezosos (módulo usable sin httpx)
    import httpx

# ---------------------------------------------------------------------------
# Constantes (idénticas a generate_dataset.py)
# ---------------------------------------------------------------------------

UMBRAL_TORMENTA_MM = 50.0  # PRECTOTCORR > 50
UMBRAL_CALOR_C = 34.0  # T2M_MAX > 34
UMBRAL_HELADA_C = 2.0  # T2M_MIN < 2
BIT_TORMENTA, BIT_CALOR, BIT_HELADA = 1, 2, 4
VENTANA_FUTURA_DIAS = 90

EVAP_MIN_DIARIA = 0.1
EVAP_MIN_TOTAL_MM = 45.0  # por debajo se usa la aproximación de Hargreaves
HARGREAVES_FACTOR = 0.16
HARGREAVES_MIN, HARGREAVES_MAX = 1.2, 6.5
ARIDEZ_DENOM_MIN = 30.0

FEATURES_ACTUALES: tuple[str, ...] = (
    "gwetroot_saturacion_pct",
    "gwettop_saturacion_pct",
    "tendencia_humedad_15d_pct",
    "anomalia_lluvia_90d_pct",
    "indice_aridez_evaporativa",
    "pendiente_terreno_pct",
    "elevacion_m",
    "textura_arcilla_pct",
)
FEATURES_FUTURAS: tuple[str, ...] = (
    "frecuencia_tormentas_extremas",
    "frecuencia_estres_termico",
    "frecuencia_riesgo_helada",
)

# (mínimo, máximo, decimales | None = entero)
TOPES: dict[str, tuple[float, float, int | None]] = {
    "gwetroot_saturacion_pct": (5.0, 99.0, 2),
    "gwettop_saturacion_pct": (5.0, 99.0, 2),
    "tendencia_humedad_15d_pct": (-40.0, 40.0, 2),
    "anomalia_lluvia_90d_pct": (-80.0, 140.0, 2),
    "indice_aridez_evaporativa": (0.08, 3.0, 3),
    "frecuencia_tormentas_extremas": (0, 12, None),
    "frecuencia_estres_termico": (0, 45, None),
    "frecuencia_riesgo_helada": (0, 55, None),
    "pendiente_terreno_pct": (0.10, 8.2, 2),
    "elevacion_m": (6.0, 580.0, 1),
    "textura_arcilla_pct": (9.0, 52.0, 2),
}


# ---------------------------------------------------------------------------
# Funciones puras
# ---------------------------------------------------------------------------


def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def aplicar_topes(features: dict[str, Any]) -> dict[str, Any]:
    """Aplica los rangos y redondeos del entrenamiento a las features presentes en ``TOPES``."""
    salida = dict(features)
    for nombre, (lo, hi, decimales) in TOPES.items():
        if nombre not in salida or salida[nombre] is None:
            continue
        valor = _clip(float(salida[nombre]), lo, hi)
        salida[nombre] = int(valor) if decimales is None else round(valor, decimales)
    return salida


def indice_aridez(
    lluvia: Sequence[float],
    evptrns: Sequence[float | None],
    t2m_max: Sequence[float],
    t2m_min: Sequence[float],
) -> float:
    """Lluvia / demanda evaporativa de la ventana pasada (sin topes; ver ``aplicar_topes``).

    Igual que el entrenamiento: ``EVPTRNS`` con mínimo diario 0,1; si la suma es < 45 mm se usa
    ``Σ clip(0,16·Tmedia, 1,2, 6,5)`` (Hargreaves). Los ``None`` de EVPTRNS no suman (pandas
    ignora NaN en ``sum``).
    """
    evap = sum(max(EVAP_MIN_DIARIA, v) for v in evptrns if v is not None)
    if evap < EVAP_MIN_TOTAL_MM:
        evap = sum(
            _clip(0.5 * (tx + tn) * HARGREAVES_FACTOR, HARGREAVES_MIN, HARGREAVES_MAX)
            for tx, tn in zip(t2m_max, t2m_min)
        )
    return sum(lluvia) / max(ARIDEZ_DENOM_MIN, evap)


def codificar_evento(prectotcorr: float | None, t2m_max: float | None, t2m_min: float | None) -> str:
    """Un carácter '0'..'7' con los bits tormenta (1), calor (2) y helada (4) de un día."""
    bits = 0
    if prectotcorr is not None and prectotcorr > UMBRAL_TORMENTA_MM:
        bits |= BIT_TORMENTA
    if t2m_max is not None and t2m_max > UMBRAL_CALOR_C:
        bits |= BIT_CALOR
    if t2m_min is not None and t2m_min < UMBRAL_HELADA_C:
        bits |= BIT_HELADA
    return chr(ord("0") + bits)


def ffill_bfill(valores: Sequence[float | None]) -> list[float | None]:
    salida = list(valores)
    ultimo: float | None = None
    for i, v in enumerate(salida):
        if v is None:
            salida[i] = ultimo
        else:
            ultimo = v
    siguiente: float | None = None
    for i in range(len(salida) - 1, -1, -1):
        if salida[i] is None:
            salida[i] = siguiente
        else:
            siguiente = salida[i]
    return salida


def calendario_eventos(
    fechas: Sequence[date],
    prectotcorr: Sequence[float | None],
    t2m_max: Sequence[float | None],
    t2m_min: Sequence[float | None],
) -> dict[int, str]:
    """Calendario de eventos diarios por año, rellenando huecos con ffill/bfill sobre toda la serie.

    ``fechas`` debe venir ordenada y sin huecos (serie diaria continua).
    """
    p, tx, tn = ffill_bfill(prectotcorr), ffill_bfill(t2m_max), ffill_bfill(t2m_min)
    por_anio: dict[int, list[str]] = {}
    for i, dia in enumerate(fechas):
        por_anio.setdefault(dia.year, []).append(codificar_evento(p[i], tx[i], tn[i]))
    return {anio: "".join(chars) for anio, chars in por_anio.items()}


def _contar(chars: Iterable[str]) -> tuple[int, int, int]:
    tormentas = calor = helada = 0
    for ch in chars:
        bits = ord(ch) - ord("0")
        tormentas += bits & BIT_TORMENTA != 0
        calor += bits & BIT_CALOR != 0
        helada += bits & BIT_HELADA != 0
    return tormentas, calor, helada


def escenarios_ventana_futura(
    calendario: dict[int, str], corte: date, dias: int = VENTANA_FUTURA_DIAS
) -> list[dict[str, int]]:
    """Valores reales de cada año para la ventana ``[corte+1, corte+dias]`` (con topes).

    Solo años con la ventana completa dentro del calendario. Si el corte es 29/2 y el año no es
    bisiesto se usa 28/2. ``anio`` es el año del día de corte equivalente.
    """
    escenarios: list[dict[str, int]] = []
    for anio in sorted(calendario):
        try:
            base = date(anio, corte.month, corte.day)
        except ValueError:
            base = date(anio, 2, 28)
        inicio = base + timedelta(days=1)
        fin = inicio + timedelta(days=dias - 1)

        chars: list[str] = []
        completo = True
        for a in range(inicio.year, fin.year + 1):
            texto = calendario.get(a)
            desde = (inicio - date(a, 1, 1)).days if a == inicio.year else 0
            hasta = (fin - date(a, 1, 1)).days if a == fin.year else None
            if texto is None or (hasta is not None and hasta >= len(texto)) or (hasta is None and desde > len(texto)):
                completo = False
                break
            chars.extend(texto[desde : (hasta + 1 if hasta is not None else None)])
        if not completo or len(chars) != dias:
            continue

        tormentas, calor, helada = _contar(chars)
        escenarios.append(
            {"anio": anio, **aplicar_topes(dict(zip(FEATURES_FUTURAS, (tormentas, calor, helada))))}
        )
    return escenarios


# ---------------------------------------------------------------------------
# Orquestador online
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InsumosML:
    """Todo lo que necesita el predictor (y ``/simulate`` para armar la respuesta)."""

    features_actuales: dict[str, Any]  # las 8 de FEATURES_ACTUALES, con topes
    escenarios_historicos: list[dict[str, int]]  # FEATURES_FUTURAS por año
    fecha_corte: date
    telemetria: Any  # schemas.TelemetriaNasa
    perfil_suelo: Any  # providers.soilgrids.PerfilSueloSatelital
    topografia: Any  # providers.srtm.TopografiaSrtm
    advertencias: tuple[str, ...] = field(default_factory=tuple)


def _columna_ventana(serie: Any, param: str, fechas_ventana: list[date], corte: date) -> list[float | None]:
    """Columna rellenada (ffill/bfill sobre la serie reciente hasta el corte) alineada a la ventana."""
    fechas = sorted(d for d in serie.series.get(param, {}) if d <= corte)
    valores = ffill_bfill([serie.series.get(param, {}).get(d) for d in fechas])
    por_fecha = dict(zip(fechas, valores))
    return [por_fecha.get(d) for d in fechas_ventana]


async def construir_insumos_ml(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
    today: date | None = None,
) -> InsumosML:
    """Consulta en paralelo NASA POWER, SoilGrids y SRTM y arma las entradas del modelo.

    Raises:
        ValueError: coordenadas fuera de rango.
        NasaPowerUnavailable / SoilGridsUnavailable / SrtmUnavailable: según el provider.
    """
    import httpx as _httpx

    from providers.nasa_power import NasaPowerUnavailable, _validar_coordenadas
    from providers.nasa_telemetry import (
        build_telemetria_nasa,
        obtener_referencia_historica,
        obtener_ventana_reciente,
        tendencia_humedad_15d_pct,
        ventana_90d_rellena,
    )
    from providers.soilgrids import fetch_perfil_suelo
    from providers.srtm import fetch_topografia

    _validar_coordenadas(lat, lon)
    today = today or datetime.now(timezone.utc).date()

    async def _armar(c: _httpx.AsyncClient) -> InsumosML:
        telemetria, perfil, topo = await asyncio.gather(
            build_telemetria_nasa(lat, lon, client=c, today=today),
            fetch_perfil_suelo(lat, lon, client=c),
            fetch_topografia(lat, lon, client=c),
        )
        # Ya quedaron en caché por build_telemetria_nasa: no generan requests nuevos.
        reciente = await obtener_ventana_reciente(lat, lon, c, today)
        referencia = await obtener_referencia_historica(lat, lon, c)

        corte = telemetria.fecha_ultimo_dato_valido
        ventana = ventana_90d_rellena(reciente, corte)
        evptrns = _columna_ventana(reciente, "EVPTRNS", ventana.fechas, corte)
        tmax = _columna_ventana(reciente, "T2M_MAX", ventana.fechas, corte)
        tmin = _columna_ventana(reciente, "T2M_MIN", ventana.fechas, corte)
        if any(v is None for v in tmax + tmin) and sum(v for v in evptrns if v is not None) < EVAP_MIN_TOTAL_MM:
            raise NasaPowerUnavailable("Sin EVPTRNS ni temperaturas válidas para el índice de aridez")

        crudas = {
            "gwetroot_saturacion_pct": reciente.series["GWETROOT"][corte] * 100.0,
            "gwettop_saturacion_pct": reciente.series["GWETTOP"][corte] * 100.0,
            "tendencia_humedad_15d_pct": tendencia_humedad_15d_pct(ventana),
            "anomalia_lluvia_90d_pct": telemetria.anomalia_lluvia_90d_pct,
            "indice_aridez_evaporativa": indice_aridez(ventana.lluvia, evptrns, tmax, tmin),  # type: ignore[arg-type]
            "pendiente_terreno_pct": topo.pendiente_terreno_pct,
            "elevacion_m": topo.elevacion_m,
            "textura_arcilla_pct": perfil.arcilla_pct,
        }
        return InsumosML(
            features_actuales=aplicar_topes(crudas),
            escenarios_historicos=escenarios_ventana_futura(referencia.calendario_eventos, corte),
            fecha_corte=corte,
            telemetria=telemetria,
            perfil_suelo=perfil,
            topografia=topo,
            advertencias=tuple(perfil.advertencias) + tuple(topo.advertencias),
        )

    if client is None:
        async with _httpx.AsyncClient() as propio:
            return await _armar(propio)
    return await _armar(client)
