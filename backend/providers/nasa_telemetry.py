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
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from providers.cache import clave_celda_power, obtener_cache
from providers.features import calendario_eventos, calendario_lluvia
from providers.nasa_power import (
    NasaPowerDailySeries,
    NasaPowerUnavailable,
    _validar_coordenadas,
    dict_a_serie,
    fetch_daily_range,
    fetch_daily_window,
    serie_a_dict,
)
from schemas import RiesgoTermico, TelemetriaNasa

VENTANA_RECIENTE_DIAS = 100  # 90 días de anomalía + margen para el lag -999 (hasta 10 días)
VENTANA_ANOMALIA_DIAS = 90
MIN_DIAS_VALIDOS = 75  # = min_periods del rolling del script de ML
PARAMS_CORTE = ("PRECTOTCORR", "GWETROOT", "GWETTOP")

# Climatología de lluvia (feature anomalia_lluvia_90d_pct) y días de calor promedio: 2006–2025,
# el mismo período con el que se entrenó el modelo.
HIST_START = date(2006, 1, 1)
HIST_END = date(2025, 12, 31)
# ML-13: el calendario de años análogos (escenarios del ensemble) arranca en 1981, primer año
# de NASA POWER diario. No cambia ninguna feature del modelo: solo suma escenarios.
ANALOGOS_START = date(1981, 1, 1)
HIST_PARAMETROS = ["PRECTOTCORR", "T2M_MAX", "T2M_MIN"]  # T2M_MIN: heladas (BACK-6)

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

# Caché (BACK-4): clave = celda de la grilla de NASA POWER (0,5° × 0,625°)
# Cambiar si cambia el cálculo de la climatología, los días de calor o el calendario de eventos.
# v2 (BACK-6): agrega T2M_MIN y el calendario de eventos diarios para los escenarios del ensemble.
VERSION_CALCULO = "telemetria-v4"  # v3: + calendario de lluvia diaria (ML-7); v4: análogos desde 1981 (ML-13)
ESPACIO_HIST = "nasa_hist"
ESPACIO_RECIENTE = "nasa_reciente"
TTL_RECIENTE_S = 6 * 3600.0
RUTA_PRECALCULO = Path(__file__).parent / "data" / "climatologia_pampa.json"

logger = logging.getLogger(__name__)

MSG_NASA_CAIDA = (
    "NASA POWER no está respondiendo en este momento, así que no podemos leer la humedad "
    "y la lluvia satelital de tu lote. Probá de nuevo en unos minutos."
)


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


# ---------------------------------------------------------------------------
# Referencia histórica (climatología + días de calor) cacheada por celda
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenciaHistorica:
    clim_por_doy: dict[int, float]
    dias_calor_verano_promedio: float
    # año -> un carácter por día con los bits tormenta/calor/helada (providers.features)
    calendario_eventos: dict[int, str] = field(default_factory=dict)
    calendario_lluvia: dict[int, str] = field(default_factory=dict)  # 2 caracteres por día (ML-7)


def recortar_serie(serie: NasaPowerDailySeries, desde: date, hasta: date) -> NasaPowerDailySeries:
    """Sub-serie con los días en [desde, hasta]."""
    inicio, fin = max(desde, serie.start), min(hasta, serie.end)
    return NasaPowerDailySeries(
        lat=serie.lat,
        lon=serie.lon,
        start=inicio,
        end=fin,
        series={p: {d: v for d, v in vals.items() if inicio <= d <= fin} for p, vals in serie.series.items()},
        elevacion_m=serie.elevacion_m,
    )


def calcular_referencia(serie_hist: NasaPowerDailySeries) -> ReferenciaHistorica:
    """Climatología y días de calor sobre 2006–2025; calendarios de análogos sobre toda la serie."""
    clima = recortar_serie(serie_hist, HIST_START, HIST_END)
    lluvia = serie_hist.series.get("PRECTOTCORR", {})
    tmax = serie_hist.series.get("T2M_MAX", {})
    tmin = serie_hist.series.get("T2M_MIN", {})
    fechas = sorted(lluvia)
    return ReferenciaHistorica(
        clim_por_doy=climatologia_lluvia_90d_por_doy(clima),
        dias_calor_verano_promedio=dias_calor_verano_promedio(clima),
        calendario_eventos=calendario_eventos(
            fechas,
            [lluvia.get(d) for d in fechas],
            [tmax.get(d) for d in fechas],
            [tmin.get(d) for d in fechas],
        ),
        calendario_lluvia=calendario_lluvia(fechas, [lluvia.get(d) for d in fechas]),
    )


def referencia_a_dict(ref: ReferenciaHistorica) -> dict[str, Any]:
    """Formato de caché / JSON precalculado: climatología como lista de 366 valores (doy 1..366)."""
    return {
        "version_calculo": VERSION_CALCULO,
        "climatologia_lluvia_90d_por_doy": [
            None if (v := ref.clim_por_doy.get(doy)) is None else round(v, 2) for doy in range(1, 367)
        ],
        "dias_calor_verano_promedio": round(ref.dias_calor_verano_promedio, 2),
        # Solo referencia: al leer se reclasifica con los umbrales vigentes.
        "riesgo_termico_verano": clasificar_riesgo_termico(ref.dias_calor_verano_promedio),
        "calendario_eventos": {str(anio): texto for anio, texto in sorted(ref.calendario_eventos.items())},
        "calendario_lluvia": {str(anio): texto for anio, texto in sorted(ref.calendario_lluvia.items())},
    }


def dict_a_referencia(datos: Any) -> ReferenciaHistorica | None:
    """``None`` si la entrada es de otra ``version_calculo`` o está mal formada."""
    try:
        if datos["version_calculo"] != VERSION_CALCULO:
            return None
        lista = datos["climatologia_lluvia_90d_por_doy"]
        if len(lista) != 366:
            return None
        return ReferenciaHistorica(
            clim_por_doy={doy: float(v) for doy, v in enumerate(lista, start=1) if v is not None},
            dias_calor_verano_promedio=float(datos["dias_calor_verano_promedio"]),
            calendario_eventos={int(a): str(t) for a, t in datos.get("calendario_eventos", {}).items()},
            calendario_lluvia={int(a): str(t) for a, t in datos.get("calendario_lluvia", {}).items()},
        )
    except (KeyError, TypeError, ValueError):
        return None


_precalculo: dict[str, Any] | None = None  # clave de celda -> entrada (carga perezosa)

# BACK-26: lector del clima histórico por celda en Supabase (``provider_cache``, espacio
# ``nasa_hist``). Lo enchufa ``main.py``; sin lector (tests, sin secret key) se salta ese paso.
LectorHist = Callable[[str], Any]
TIMEOUT_LECTOR_HIST_S = 2.0
_lector_hist: LectorHist | None = None


def configurar_lector_hist(lector: LectorHist | None) -> None:
    """Enchufa (o quita, con ``None``) la lectura bajo demanda desde Supabase."""
    global _lector_hist
    _lector_hist = lector


async def _leer_hist_supabase(clave: str) -> ReferenciaHistorica | None:
    """La celda desde Supabase, o ``None`` si no hay lector, no está, es de otra versión,
    tarda más de ``TIMEOUT_LECTOR_HIST_S`` o falla. Nunca lanza."""
    if _lector_hist is None:
        return None
    try:
        datos = await asyncio.wait_for(asyncio.to_thread(_lector_hist, clave), TIMEOUT_LECTOR_HIST_S)
    except Exception as exc:  # noqa: BLE001 - se sigue con el JSON del repo
        logger.warning("nasa_hist: Supabase no respondió para %s (%s); uso el JSON", clave, exc)
        return None
    return dict_a_referencia(datos) if datos is not None else None


def cargar_climatologia_precalculada(ruta: Path = RUTA_PRECALCULO) -> dict[str, Any]:
    """Lee una sola vez el JSON precalculado de la región pampeana (vacío si no existe)."""
    global _precalculo
    if _precalculo is None:
        try:
            _precalculo = json.loads(ruta.read_text(encoding="utf-8")).get("celdas", {})
        except FileNotFoundError:
            _precalculo = {}
    return _precalculo


def reiniciar_estado(precalculo: dict[str, Any] | None = None) -> None:
    """Para tests: reemplaza el precálculo cargado (``{}`` = sin precálculo)."""
    global _precalculo
    _precalculo = precalculo


async def obtener_referencia_historica(lat: float, lon: float, client: httpx.AsyncClient) -> ReferenciaHistorica:
    """Memoria -> Supabase (BACK-26, esa celda) -> JSON precalculado -> cálculo en vivo (1981–2025).

    Lo que sale de Supabase, del JSON o del cálculo queda en la caché. Al escribir, la capa
    de Supabase sube lo que no tenía (JSON o cálculo en vivo) y no reescribe lo que ya leyó.
    """
    cache = obtener_cache()
    clave = clave_celda_power(lat, lon)

    ref = dict_a_referencia(cache.get(ESPACIO_HIST, clave))
    if ref is not None:
        return ref

    ref = await _leer_hist_supabase(clave)
    if ref is None:
        entrada_pre = cargar_climatologia_precalculada().get(clave)
        ref = dict_a_referencia(entrada_pre) if entrada_pre is not None else None
    if ref is None:
        serie = await fetch_daily_range(lat, lon, ANALOGOS_START, HIST_END, HIST_PARAMETROS, client=client)
        ref = calcular_referencia(serie)

    entrada = referencia_a_dict(ref)
    cache.set(ESPACIO_HIST, clave, entrada)
    # Devolver siempre la versión serializada (redondeada) para que la primera consulta
    # y las siguientes desde caché den exactamente el mismo resultado.
    return dict_a_referencia(entrada)  # type: ignore[return-value]


async def obtener_ventana_reciente(
    lat: float, lon: float, client: httpx.AsyncClient, today: date
) -> NasaPowerDailySeries:
    """Ventana de 100 días cacheada por celda con TTL de 6 h (y solo si es del mismo día)."""
    cache = obtener_cache()
    clave = clave_celda_power(lat, lon)

    cacheado = cache.get(ESPACIO_RECIENTE, clave)
    if cacheado is not None and cacheado.get("end") == today.isoformat():
        return dict_a_serie(cacheado)

    serie = await fetch_daily_window(lat, lon, dias=VENTANA_RECIENTE_DIAS, client=client, today=today)
    cache.set(ESPACIO_RECIENTE, clave, serie_a_dict(serie), TTL_RECIENTE_S)
    return serie


async def build_telemetria_nasa(
    lat: float,
    lon: float,
    *,
    client: httpx.AsyncClient | None = None,
    today: date | None = None,
) -> TelemetriaNasa:
    """Arma ``telemetria_nasa`` (ventana reciente + referencia histórica, ambas cacheadas por celda).

    Raises:
        ValueError: coordenadas fuera de rango.
        NasaPowerUnavailable: NASA POWER no responde (mensaje apto para el usuario) o no hay
            datos válidos suficientes.
    """
    _validar_coordenadas(lat, lon)
    today = today or datetime.now(timezone.utc).date()

    async def _consultar(c: httpx.AsyncClient) -> tuple[NasaPowerDailySeries, ReferenciaHistorica]:
        return await asyncio.gather(
            obtener_ventana_reciente(lat, lon, c, today),
            obtener_referencia_historica(lat, lon, c),
        )

    try:
        if client is None:
            async with httpx.AsyncClient() as propio:
                reciente, referencia = await _consultar(propio)
        else:
            reciente, referencia = await _consultar(client)
    except NasaPowerUnavailable as exc:
        raise NasaPowerUnavailable(f"{MSG_NASA_CAIDA} (detalle: {exc})") from exc

    corte = fecha_de_corte(reciente)
    ventana = ventana_90d_rellena(reciente, corte)

    return TelemetriaNasa(
        fecha_ultimo_dato_valido=corte,
        indice_humedad_radicular_pct=round(reciente.series["GWETROOT"][corte] * 100.0, 1),
        indice_humedad_superficial_pct=round(reciente.series["GWETTOP"][corte] * 100.0, 1),
        tendencia_humedad_15d_pct=tendencia_humedad_15d_pct(ventana),
        anomalia_lluvia_90d_pct=anomalia_lluvia_90d_pct(ventana, referencia.clim_por_doy, corte),
        frecuencia_tormentas_extremas_90d=tormentas_extremas_90d(ventana),
        riesgo_termico_verano=clasificar_riesgo_termico(referencia.dias_calor_verano_promedio),
    )
