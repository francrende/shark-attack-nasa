"""Features del modelo de ML: fórmulas únicas para entrenamiento y producción (BACK-6).

La parte superior del módulo son **funciones puras sin E/S** pensadas para que
``backend/ml/generate_dataset.py`` las importe en lugar de mantener su propia copia, de modo
que entrenamiento e inferencia calculen exactamente igual. Replican hoy la lógica de
``extract_real_90d_windows`` (estado actual [t-89, t] + período crítico, ver backend/ml/AGENTS.md).

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
# ML-7: las futuras se miden en el período crítico de cada cultivo y suman la lluvia acumulada.
FEATURE_LLUVIA_CRITICA = "lluvia_periodo_critico_mm"
FEATURES_PERIODO_CRITICO: tuple[str, ...] = (*FEATURES_FUTURAS, FEATURE_LLUVIA_CRITICA)

# Calendario de lluvia diaria: 2 caracteres base 64 por día, en décimas de mm (tope 409,5 mm/día).
_B64 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
LLUVIA_ESCALA_MM = 0.1
LLUVIA_MAX_UNIDADES = 64 * 64 - 1

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
    "lluvia_periodo_critico_mm": (0.0, 1500.0, 1),
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


def codificar_lluvia(mm: float | None) -> str:
    unidades = 0 if mm is None else int(round(max(0.0, mm) / LLUVIA_ESCALA_MM))
    unidades = min(unidades, LLUVIA_MAX_UNIDADES)
    return _B64[unidades // 64] + _B64[unidades % 64]


def decodificar_lluvia(texto: str) -> list[float]:
    idx = {c: i for i, c in enumerate(_B64)}
    return [(idx[texto[i]] * 64 + idx[texto[i + 1]]) * LLUVIA_ESCALA_MM for i in range(0, len(texto), 2)]


def calendario_lluvia(fechas: Sequence[date], prectotcorr: Sequence[float | None]) -> dict[int, str]:
    """Lluvia diaria por año (2 caracteres por día), con huecos rellenos por ffill/bfill."""
    p = ffill_bfill(prectotcorr)
    por_anio: dict[int, list[str]] = {}
    for i, dia in enumerate(fechas):
        por_anio.setdefault(dia.year, []).append(codificar_lluvia(p[i]))
    return {anio: "".join(chars) for anio, chars in por_anio.items()}


def _tramo(calendario: dict[int, str], inicio: date, dias: int, ancho: int = 1) -> str | None:
    """Caracteres de ``[inicio, inicio+dias-1]`` (``ancho`` caracteres por día), o None si falta algo."""
    fin = inicio + timedelta(days=dias - 1)
    partes: list[str] = []
    for a in range(inicio.year, fin.year + 1):
        texto = calendario.get(a)
        if texto is None:
            return None
        desde = (inicio - date(a, 1, 1)).days if a == inicio.year else 0
        hasta = (fin - date(a, 1, 1)).days if a == fin.year else len(texto) // ancho - 1
        if hasta >= len(texto) // ancho:
            return None
        partes.append(texto[desde * ancho : (hasta + 1) * ancho])
    tramo = "".join(partes)
    return tramo if len(tramo) == dias * ancho else None


def features_ventana(
    calendario_eventos: dict[int, str],
    calendario_lluvia: dict[int, str],
    inicio: date,
    dias: int = VENTANA_FUTURA_DIAS,
) -> dict[str, Any] | None:
    """Tormentas, calor, heladas y lluvia acumulada de ``[inicio, inicio+dias-1]`` (con topes).

    Función única para entrenamiento (período crítico observado) y producción (años análogos).
    """
    eventos = _tramo(calendario_eventos, inicio, dias)
    lluvia = _tramo(calendario_lluvia, inicio, dias, ancho=2)
    if eventos is None or lluvia is None:
        return None
    return features_de_tramos(eventos, lluvia)


def tramo(calendario: dict[int, str], inicio: date, dias: int, ancho: int = 1) -> str | None:
    """Versión pública de ``_tramo`` (ML-18: ventanas armadas con dos tramos)."""
    if dias <= 0:
        return ""
    return _tramo(calendario, inicio, dias, ancho)


def features_de_tramos(eventos: str, lluvia: str) -> dict[str, Any]:
    """Tormentas, calor, heladas y lluvia (con topes) de un tramo ya armado.

    ML-18: el seguimiento une los días observados de la campaña con el resto de cada año
    análogo y calcula con esta misma función, igual que ``features_ventana``.
    """
    tormentas, calor, helada = _contar(eventos)
    return aplicar_topes(
        dict(zip(FEATURES_PERIODO_CRITICO, (tormentas, calor, helada, round(sum(decodificar_lluvia(lluvia)), 1))))
    )


def contar_eventos(chars: Iterable[str]) -> tuple[int, int, int]:
    """(tormentas, días de calor, heladas) de un tramo de eventos, sin topes (para mostrar)."""
    return _contar(chars)


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
        chars = _tramo(calendario, inicio, dias)
        if chars is None:
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
    # ML-7: calendarios diarios 2006–2025 de la celda (escenarios por cultivo en su período
    # crítico) y ONI publicado al corte (ponderación de años análogos y feature del modelo).
    calendario_eventos: dict[int, str] = field(default_factory=dict)
    calendario_lluvia: dict[int, str] = field(default_factory=dict)
    oni_actual: float | None = None


def _columna_ventana(serie: Any, param: str, fechas_ventana: list[date], corte: date) -> list[float | None]:
    """Columna rellenada (ffill/bfill sobre la serie reciente hasta el corte) alineada a la ventana."""
    fechas = sorted(d for d in serie.series.get(param, {}) if d <= corte)
    valores = ffill_bfill([serie.series.get(param, {}).get(d) for d in fechas])
    por_fecha = dict(zip(fechas, valores))
    return [por_fecha.get(d) for d in fechas_ventana]


def features_actuales_desde_series(
    reciente: Any,
    corte: date,
    clim_por_doy: dict[int, float],
    *,
    pendiente_terreno_pct: float,
    elevacion_m: float,
    textura_arcilla_pct: float,
) -> dict[str, Any]:
    """Las 8 features actuales (con topes) a partir de la serie diaria hasta ``corte``.

    Función pura compartida por producción (``construir_insumos_ml``) y entrenamiento
    (``ml/generate_dataset.py``, ML-6) para que ambos calculen exactamente igual.
    ``reciente`` es una ``NasaPowerDailySeries`` que cubre al menos los 100 días previos.

    Raises:
        NasaPowerUnavailable: sin datos válidos suficientes en la ventana.
    """
    from providers.nasa_power import NasaPowerUnavailable
    from providers.nasa_telemetry import anomalia_lluvia_90d_pct, tendencia_humedad_15d_pct, ventana_90d_rellena

    ventana = ventana_90d_rellena(reciente, corte)
    evptrns = _columna_ventana(reciente, "EVPTRNS", ventana.fechas, corte)
    tmax = _columna_ventana(reciente, "T2M_MAX", ventana.fechas, corte)
    tmin = _columna_ventana(reciente, "T2M_MIN", ventana.fechas, corte)
    if any(v is None for v in tmax + tmin) and sum(v for v in evptrns if v is not None) < EVAP_MIN_TOTAL_MM:
        raise NasaPowerUnavailable("Sin EVPTRNS ni temperaturas válidas para el índice de aridez")
    gwetroot = reciente.series["GWETROOT"].get(corte)
    gwettop = reciente.series["GWETTOP"].get(corte)
    if gwetroot is None or gwettop is None:
        raise NasaPowerUnavailable(f"Sin GWETROOT/GWETTOP válidos en el corte {corte}")

    crudas = {
        "gwetroot_saturacion_pct": gwetroot * 100.0,
        "gwettop_saturacion_pct": gwettop * 100.0,
        "tendencia_humedad_15d_pct": tendencia_humedad_15d_pct(ventana),
        "anomalia_lluvia_90d_pct": anomalia_lluvia_90d_pct(ventana, clim_por_doy, corte),
        "indice_aridez_evaporativa": indice_aridez(ventana.lluvia, evptrns, tmax, tmin),  # type: ignore[arg-type]
        "pendiente_terreno_pct": pendiente_terreno_pct,
        "elevacion_m": elevacion_m,
        "textura_arcilla_pct": textura_arcilla_pct,
    }
    return aplicar_topes(crudas)


async def construir_insumos_ml(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
    today: date | None = None,
    campo: Any = None,
    persistir_campo: Any = None,
) -> InsumosML:
    """Arma las entradas del modelo con el servicio único de datos del lote (BACK-24).

    ``campo`` (fila de ``public.fields``) y ``persistir_campo`` son opcionales: con ellos se
    aplica la política del campo (datos fijos guardados, búsqueda y guardado de lo que falte).
    Sin ellos, el comportamiento es el de siempre (providers con su caché).

    Raises:
        ValueError: coordenadas fuera de rango.
        NasaPowerUnavailable / SoilGridsUnavailable / SrtmUnavailable: según el provider.
    """
    # Import diferido: services.datos_lote importa providers (evita el ciclo al cargar).
    from providers.enso import oni_al
    from providers.nasa_telemetry import armar_telemetria
    from services.datos_lote import obtener_datos_lote

    datos = await obtener_datos_lote(
        lat, lon, campo=campo, persistir_campo=persistir_campo, client=client, today=today, exigir_todo=True
    )
    reciente, referencia = datos.reciente, datos.referencia
    perfil, topo = datos.perfil_suelo, datos.topografia

    telemetria = armar_telemetria(reciente, referencia)
    corte = telemetria.fecha_ultimo_dato_valido
    features = features_actuales_desde_series(
        reciente,
        corte,
        referencia.clim_por_doy,
        pendiente_terreno_pct=topo.pendiente_terreno_pct,
        elevacion_m=topo.elevacion_m,
        textura_arcilla_pct=perfil.arcilla_pct,
    )
    return InsumosML(
        features_actuales=features,
        escenarios_historicos=escenarios_ventana_futura(referencia.calendario_eventos, corte),
        fecha_corte=corte,
        telemetria=telemetria,
        perfil_suelo=perfil,
        topografia=topo,
        advertencias=tuple(perfil.advertencias) + tuple(topo.advertencias),
        calendario_eventos=referencia.calendario_eventos,
        calendario_lluvia=referencia.calendario_lluvia,
        oni_actual=oni_al(corte),
    )
