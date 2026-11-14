"""Construcción del bloque ``telemetria_nasa`` (BACK-2).

Los cálculos replican ``extract_real_90d_windows`` de ``backend/ml/generate_dataset.py``
para que inferencia y entrenamiento vean exactamente las mismas features
(ffill/bfill de huecos, rolling 90d con min_periods=75, climatología por día del año,
topes de anomalía, tendencia y tormentas).

Se implementa en Python puro (sin pandas) para no sumar latencia en el camino online;
``test_nasa_telemetry.py`` valida la paridad contra pandas.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx

from providers.nasa_power import (
    NasaPowerDailySeries,
    NasaPowerUnavailable,
    fetch_daily_range,
    fetch_daily_window,
)
from schemas import RiesgoTermico, TelemetriaNasa

VENTANA_RECIENTE_DIAS = 100  # 90 días de anomalía + margen para el lag -999 (hasta 10 días)
VENTANA_ANOMALIA_DIAS = 90
MIN_DIAS_VALIDOS = 75  # = min_periods del rolling del script de ML
PARAMS_CORTE = ("PRECTOTCORR", "GWETROOT", "GWETTOP")

HIST_START = date(2006, 1, 1)
HIST_END = date(2025, 12, 31)
HIST_PARAMETROS = ["PRECTOTCORR", "T2M_MAX"]

# Constantes de generate_dataset.py
HIST_LLUVIA_MIN_MM = 25.0
HIST_LLUVIA_DEFAULT_MM = 180.0
ANOMALIA_MIN, ANOMALIA_MAX = -80.0, 140.0
TENDENCIA_MIN, TENDENCIA_MAX = -40.0, 40.0
PESO_RAIZ, PESO_SUPERFICIE = 0.65, 0.35
TENDENCIA_OFFSET = 15  # iloc[-15] -> 14 días antes del corte
TORMENTA_UMBRAL_MM = 50.0
TORMENTAS_MAX = 12

UMBRAL_CALOR_C = 34.0
# Umbrales de riesgo térmico (promedio de días > 34 °C en dic–feb, 2006–2025).
# Calibrados sobre 12 puntos de la región (NASA POWER / MERRA-2): Balcarce 11,5 · Tres Arroyos 13,7 ·
# 9 de Julio 14,1 · Río Cuarto 23,7 · Pergamino 23,8 · Gral. Pico 26,2 · Gualeguaychú 30,3 ·
# Marcos Juárez 31,5 · Paraná 34,5 · Rafaela 35,8 · Reconquista 44,7 · Charata 55,8.
RIESGO_BAJO_HASTA = 15.0  # < 15 -> bajo
RIESGO_MEDIO_HASTA = 25.0  # [15, 25) -> medio
RIESGO_ALTO_HASTA = 40.0  # [25, 40] -> alto ; > 40 -> critico


def _clip(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, valor))


def _ffill_bfill(valores: list[float | None]) -> list[float | None]:
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


@dataclass(frozen=True)
class Ventana90d:
    fechas: list[date]
    lluvia: list[float]
    gwetroot: list[float]
    gwettop: list[float]


def fecha_de_corte(serie: NasaPowerDailySeries) -> date:
    """Último día en que PRECTOTCORR, GWETROOT y GWETTOP son válidos a la vez."""
    columnas = [serie.series.get(p, {}) for p in PARAMS_CORTE]
    fechas = set(columnas[0]).intersection(*columnas[1:])
    for dia in sorted(fechas, reverse=True):
        if all(col[dia] is not None for col in columnas):
            return dia
    raise NasaPowerUnavailable(
        f"Sin ningún día con {', '.join(PARAMS_CORTE)} válidos en la ventana {serie.start} -> {serie.end}"
    )


def ventana_90d_rellena(serie: NasaPowerDailySeries, corte: date) -> Ventana90d:
    """Ventana de hasta 90 días que termina en ``corte``, con huecos rellenos por ffill/bfill.

    El relleno se hace sobre toda la serie reciente hasta el corte (como el script de ML,
    que rellena la serie completa antes de cortar ventanas).
    """
    fechas = sorted(d for d in serie.series.get("PRECTOTCORR", {}) if d <= corte)
    fechas_ventana = fechas[-VENTANA_ANOMALIA_DIAS:]

    lluvia_cruda = [serie.series["PRECTOTCORR"].get(d) for d in fechas_ventana]
    validos = sum(v is not None for v in lluvia_cruda)
    if validos < MIN_DIAS_VALIDOS:
        raise NasaPowerUnavailable(
            f"Solo {validos} días válidos de PRECTOTCORR en la ventana de 90 días (mínimo {MIN_DIAS_VALIDOS})"
        )

    n = len(fechas_ventana)

    def _columna(param: str) -> list[float]:
        valores = _ffill_bfill([serie.series.get(param, {}).get(d) for d in fechas])[-n:]
        if any(v is None for v in valores):
            raise NasaPowerUnavailable(f"Serie {param} sin datos válidos para rellenar la ventana")
        return valores  # type: ignore[return-value]

    return Ventana90d(
        fechas=fechas_ventana,
        lluvia=_columna("PRECTOTCORR"),
        gwetroot=_columna("GWETROOT"),
        gwettop=_columna("GWETTOP"),
    )


def climatologia_lluvia_90d_por_doy(serie_hist: NasaPowerDailySeries) -> dict[int, float]:
    """Promedio por día del año de la lluvia acumulada en 90 días (rolling min_periods=75)."""
    lluvia = serie_hist.series.get("PRECTOTCORR", {})
    fechas = sorted(lluvia)
    valores = _ffill_bfill([lluvia[d] for d in fechas])
    if not valores or any(v is None for v in valores):
        raise NasaPowerUnavailable("Serie histórica de PRECTOTCORR sin datos válidos")

    acumulado = [0.0]
    for v in valores:
        acumulado.append(acumulado[-1] + v)  # type: ignore[operator]

    sumas: dict[int, float] = {}
    conteos: dict[int, int] = {}
    for i, dia in enumerate(fechas):
        inicio = max(0, i - VENTANA_ANOMALIA_DIAS + 1)
        if i + 1 - inicio < MIN_DIAS_VALIDOS:
            continue
        doy = dia.timetuple().tm_yday
        sumas[doy] = sumas.get(doy, 0.0) + (acumulado[i + 1] - acumulado[inicio])
        conteos[doy] = conteos.get(doy, 0) + 1
    return {doy: sumas[doy] / conteos[doy] for doy in sumas}


def anomalia_lluvia_90d_pct(ventana: Ventana90d, clim: dict[int, float], corte: date) -> float:
    lluvia_90d = sum(ventana.lluvia)
    doy = corte.timetuple().tm_yday
    hist = max(HIST_LLUVIA_MIN_MM, clim.get(doy, HIST_LLUVIA_DEFAULT_MM))
    anomalia = (lluvia_90d - hist) / hist * 100.0
    return round(_clip(anomalia, ANOMALIA_MIN, ANOMALIA_MAX), 2)


def tendencia_humedad_15d_pct(ventana: Ventana90d) -> float:
    if len(ventana.fechas) < TENDENCIA_OFFSET:
        raise NasaPowerUnavailable("Ventana demasiado corta para calcular la tendencia de 15 días")
    raiz = (ventana.gwetroot[-1] - ventana.gwetroot[-TENDENCIA_OFFSET]) * 100.0
    sup = (ventana.gwettop[-1] - ventana.gwettop[-TENDENCIA_OFFSET]) * 100.0
    tendencia = PESO_RAIZ * raiz + PESO_SUPERFICIE * sup
    return round(_clip(tendencia, TENDENCIA_MIN, TENDENCIA_MAX), 2)


def tormentas_extremas_90d(ventana: Ventana90d) -> int:
    eventos = sum(1 for v in ventana.lluvia if v > TORMENTA_UMBRAL_MM)
    return int(_clip(eventos, 0, TORMENTAS_MAX))


def dias_calor_verano_promedio(serie_hist: NasaPowerDailySeries) -> float:
    """Promedio de días con T2M_MAX > 34 °C entre el 1/12 y fin de febrero (solo temporadas completas)."""
    tmax = serie_hist.series.get("T2M_MAX", {})
    conteos: list[int] = []
    for anio in range(serie_hist.start.year, serie_hist.end.year):
        inicio = date(anio, 12, 1)
        fin = date(anio + 1, 3, 1) - timedelta(days=1)
        if inicio < serie_hist.start or fin > serie_hist.end:
            continue
        dia, dias_calor = inicio, 0
        while dia <= fin:
            valor = tmax.get(dia)
            if valor is not None and valor > UMBRAL_CALOR_C:
                dias_calor += 1
            dia += timedelta(days=1)
        conteos.append(dias_calor)
    if not conteos:
        raise NasaPowerUnavailable("Serie histórica sin temporadas de verano completas")
    return sum(conteos) / len(conteos)


def clasificar_riesgo_termico(dias: float) -> RiesgoTermico:
    if dias < RIESGO_BAJO_HASTA:
        return "bajo"
    if dias < RIESGO_MEDIO_HASTA:
        return "medio"
    if dias <= RIESGO_ALTO_HASTA:
        return "alto"
    return "critico"


async def build_telemetria_nasa(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
    today: date | None = None,
) -> TelemetriaNasa:
    """Arma ``telemetria_nasa`` consultando en paralelo la ventana reciente y el histórico 2006–2025.

    Raises:
        ValueError: coordenadas fuera de rango.
        NasaPowerUnavailable: NASA POWER no responde o no hay datos válidos suficientes.
    """
    today = today or datetime.now(timezone.utc).date()

    async def _consultar(c: httpx.AsyncClient) -> tuple[NasaPowerDailySeries, NasaPowerDailySeries]:
        return await asyncio.gather(
            fetch_daily_window(lat, lon, dias=VENTANA_RECIENTE_DIAS, client=c, today=today),
            fetch_daily_range(lat, lon, HIST_START, HIST_END, HIST_PARAMETROS, client=c),
        )

    if client is None:
        async with httpx.AsyncClient() as propio:
            reciente, historico = await _consultar(propio)
    else:
        reciente, historico = await _consultar(client)

    corte = fecha_de_corte(reciente)
    ventana = ventana_90d_rellena(reciente, corte)
    clim = climatologia_lluvia_90d_por_doy(historico)

    return TelemetriaNasa(
        fecha_ultimo_dato_valido=corte,
        indice_humedad_radicular_pct=round(reciente.series["GWETROOT"][corte] * 100.0, 1),
        indice_humedad_superficial_pct=round(reciente.series["GWETTOP"][corte] * 100.0, 1),
        tendencia_humedad_15d_pct=tendencia_humedad_15d_pct(ventana),
        anomalia_lluvia_90d_pct=anomalia_lluvia_90d_pct(ventana, clim, corte),
        frecuencia_tormentas_extremas_90d=tormentas_extremas_90d(ventana),
        riesgo_termico_verano=clasificar_riesgo_termico(dias_calor_verano_promedio(historico)),
    )
