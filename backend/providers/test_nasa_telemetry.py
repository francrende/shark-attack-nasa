"""Tests de BACK-2 (sin red)."""

import asyncio
from datetime import date, timedelta

import httpx
import pytest

from providers import nasa_telemetry
from providers.cache import CacheEnCapas, CacheMemoria, clave_celda_power, configurar_cache, obtener_cache
from providers.nasa_power import NasaPowerDailySeries, NasaPowerUnavailable
from providers.nasa_telemetry import (
    ANALOGOS_START,
    HIST_END,
    HIST_START,
    Ventana90d,
    anomalia_lluvia_90d_pct,
    build_telemetria_nasa,
    calcular_referencia,
    clasificar_riesgo_termico,
    climatologia_lluvia_90d_por_doy,
    dias_calor_verano_promedio,
    fecha_de_corte,
    tendencia_humedad_15d_pct,
    tormentas_extremas_90d,
    ventana_90d_rellena,
)
from schemas import TelemetriaNasa

HOY = date(2026, 11, 14)


class Reloj:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture(autouse=True)
def _estado_limpio():
    """Caché vacía y sin climatología precalculada en cada test."""
    reloj = Reloj()
    configurar_cache(CacheEnCapas(CacheMemoria(reloj=reloj)))
    nasa_telemetry.reiniciar_estado({})
    yield reloj
    configurar_cache(CacheEnCapas(CacheMemoria()))
    nasa_telemetry.reiniciar_estado(None)


# ---------- helpers ----------


def _rango(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _serie(start: date, end: date, funcs: dict) -> NasaPowerDailySeries:
    dias = _rango(start, end)
    return NasaPowerDailySeries(
        lat=-33.95,
        lon=-60.57,
        start=start,
        end=end,
        series={p: {d: f(d) for d in dias} for p, f in funcs.items()},
    )


def _payload(serie: NasaPowerDailySeries) -> dict:
    return {
        "properties": {
            "parameter": {
                p: {d.strftime("%Y%m%d"): (-999.0 if v is None else v) for d, v in vals.items()}
                for p, vals in serie.series.items()
            }
        }
    }


def _ventana(lluvia=None, gwetroot=None, gwettop=None, n=90) -> Ventana90d:
    fechas = _rango(HOY - timedelta(days=n - 1), HOY)
    return Ventana90d(
        fechas=fechas,
        lluvia=lluvia or [1.0] * n,
        gwetroot=gwetroot or [0.5] * n,
        gwettop=gwettop or [0.5] * n,
    )


def _lluvia_hist(d: date) -> float | None:
    # Patrón determinístico con estacionalidad y algunos -999 aislados.
    if d.day == 13 and d.month in (3, 7):
        return None
    return round(((d.toordinal() * 7) % 11) * 0.6 + (2.0 if d.month in (10, 11, 12, 1, 2, 3) else 0.5), 2)


def _hist_sintetico(tmax=lambda d: 30.0) -> NasaPowerDailySeries:
    return _serie(HIST_START, HIST_END, {"PRECTOTCORR": _lluvia_hist, "T2M_MAX": tmax})


def _reciente(lag_dias: int = 3, **overrides) -> NasaPowerDailySeries:
    inicio = HOY - timedelta(days=99)
    corte = HOY - timedelta(days=lag_dias)

    def con_lag(f):
        return lambda d: None if d > corte else f(d)

    funcs = {
        "PRECTOTCORR": con_lag(lambda d: 2.0),
        "GWETROOT": con_lag(lambda d: 0.46),
        "GWETTOP": con_lag(lambda d: 0.35),
    }
    funcs.update(overrides)
    return _serie(inicio, HOY, funcs)


# ---------- fecha de corte y ventana ----------


def test_fecha_de_corte_es_ultimo_dia_con_los_3_validos():
    corte_root = HOY - timedelta(days=5)
    serie = _reciente(lag_dias=3, GWETROOT=lambda d: None if d > corte_root else 0.4)
    assert fecha_de_corte(serie) == corte_root


def test_fecha_de_corte_sin_dias_validos_lanza():
    serie = _reciente(GWETROOT=lambda d: None)
    with pytest.raises(NasaPowerUnavailable):
        fecha_de_corte(serie)


def test_ventana_termina_en_corte_y_rellena_huecos():
    corte = HOY - timedelta(days=3)
    hueco = corte - timedelta(days=10)

    def lluvia(d):
        if d > corte or d == hueco:
            return None
        return 3.0 if d == hueco - timedelta(days=1) else 1.0

    serie = _reciente(PRECTOTCORR=lluvia)
    ventana = ventana_90d_rellena(serie, corte)

    assert len(ventana.fechas) == 90
    assert ventana.fechas[-1] == corte
    assert ventana.fechas[0] == corte - timedelta(days=89)
    # ffill: el hueco toma el valor del día anterior (3.0)
    assert ventana.lluvia[ventana.fechas.index(hueco)] == 3.0


def test_ventana_con_menos_de_75_validos_lanza():
    corte = HOY - timedelta(days=3)
    huecos = {corte - timedelta(days=i) for i in range(1, 17)}  # 16 huecos -> 74 válidos
    serie = _reciente(PRECTOTCORR=lambda d: None if d > corte or d in huecos else 1.0)
    with pytest.raises(NasaPowerUnavailable):
        ventana_90d_rellena(serie, corte)


def test_ventana_con_75_validos_alcanza():
    corte = HOY - timedelta(days=3)
    huecos = {corte - timedelta(days=i) for i in range(1, 16)}  # 15 huecos -> 75 válidos
    serie = _reciente(PRECTOTCORR=lambda d: None if d > corte or d in huecos else 1.0)
    assert len(ventana_90d_rellena(serie, corte).fechas) == 90


# ---------- climatología (paridad con pandas / generate_dataset.py) ----------


def test_climatologia_paridad_con_pandas():
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")

    serie = _hist_sintetico()
    # Huecos al inicio para ejercitar el bfill.
    serie.series["PRECTOTCORR"][HIST_START] = None
    serie.series["PRECTOTCORR"][HIST_START + timedelta(days=1)] = None

    ours = climatologia_lluvia_90d_por_doy(serie)

    # Réplica literal de extract_real_90d_windows (generate_dataset.py)
    fechas = sorted(serie.series["PRECTOTCORR"])
    df = pd.DataFrame(
        {
            "date": pd.to_datetime([d.isoformat() for d in fechas]),
            "prectotcorr": [
                -999.0 if (v := serie.series["PRECTOTCORR"][d]) is None else v for d in fechas
            ],
        }
    )
    df["doy"] = df["date"].dt.day_of_year
    df.loc[df["prectotcorr"] < -900.0, "prectotcorr"] = np.nan
    df[["prectotcorr"]] = df[["prectotcorr"]].ffill().bfill()
    df["rain_90d"] = df["prectotcorr"].rolling(window=90, min_periods=75).sum()
    theirs = df.groupby("doy")["rain_90d"].mean().to_dict()

    assert set(ours) == set(theirs)
    for doy, valor in theirs.items():
        assert ours[doy] == pytest.approx(valor, rel=1e-9, abs=1e-9)


def test_climatologia_respeta_min_periods():
    serie = _serie(date(2006, 1, 1), date(2006, 4, 30), {"PRECTOTCORR": lambda d: 1.0})
    clim = climatologia_lluvia_90d_por_doy(serie)
    assert 74 not in clim  # día 74 -> solo 74 observaciones
    assert clim[75] == pytest.approx(75.0)  # ventana parcial de 75 días
    assert clim[100] == pytest.approx(90.0)  # ventana completa


def test_climatologia_sin_datos_lanza():
    serie = _serie(date(2006, 1, 1), date(2006, 4, 30), {"PRECTOTCORR": lambda d: None})
    with pytest.raises(NasaPowerUnavailable):
        climatologia_lluvia_90d_por_doy(serie)


# ---------- anomalía ----------


def test_anomalia_positiva_y_negativa():
    doy = HOY.timetuple().tm_yday
    assert anomalia_lluvia_90d_pct(_ventana(lluvia=[2.0] * 90), {doy: 120.0}, HOY) == 50.0
    assert anomalia_lluvia_90d_pct(_ventana(lluvia=[1.0] * 90), {doy: 180.0}, HOY) == -50.0


def test_anomalia_topes():
    doy = HOY.timetuple().tm_yday
    assert anomalia_lluvia_90d_pct(_ventana(lluvia=[0.0] * 90), {doy: 100.0}, HOY) == -80.0
    assert anomalia_lluvia_90d_pct(_ventana(lluvia=[10.0] * 90), {doy: 100.0}, HOY) == 140.0


def test_anomalia_piso_25mm_y_default_180():
    doy = HOY.timetuple().tm_yday
    # hist = max(25, 10) = 25 ; 30 mm -> +20 %
    assert anomalia_lluvia_90d_pct(_ventana(lluvia=[30.0 / 90] * 90), {doy: 10.0}, HOY) == 20.0
    # doy ausente -> 180 ; 90 mm -> -50 %
    assert anomalia_lluvia_90d_pct(_ventana(lluvia=[1.0] * 90), {}, HOY) == -50.0


# ---------- tendencia y tormentas ----------


def test_tendencia_pesos_y_signo():
    root = [0.5] * 75 + [0.5] + [0.45] * 13 + [0.40]  # idx -15 = 0.50, último = 0.40
    top = [0.3] * 75 + [0.3] + [0.35] * 13 + [0.40]  # idx -15 = 0.30, último = 0.40
    # 0.65 * (-10) + 0.35 * (+10) = -3.0
    assert tendencia_humedad_15d_pct(_ventana(gwetroot=root, gwettop=top)) == -3.0


def test_tendencia_topes():
    seco = [0.9] * 76 + [0.2] * 14
    humedo = [0.1] * 76 + [0.9] * 14
    assert tendencia_humedad_15d_pct(_ventana(gwetroot=seco, gwettop=seco)) == -40.0
    assert tendencia_humedad_15d_pct(_ventana(gwetroot=humedo, gwettop=humedo)) == 40.0


def test_tormentas_umbral_y_tope():
    assert tormentas_extremas_90d(_ventana(lluvia=[51.0, 50.0, 60.0] + [0.0] * 87)) == 2
    assert tormentas_extremas_90d(_ventana(lluvia=[80.0] * 20 + [0.0] * 70)) == 12


# ---------- riesgo térmico ----------


def test_dias_calor_solo_temporadas_completas():
    def tmax(d):
        if d.month == 12 and d.day <= 10:
            return 36.0  # 10 días de calor por temporada
        if d.year == 2006 and d.month in (1, 2):
            return 40.0  # temporada incompleta (dic 2005 fuera de rango)
        return 30.0

    # Dic 2025 también tiene 10 días de calor pero su temporada está incompleta.
    assert dias_calor_verano_promedio(_hist_sintetico(tmax)) == 10.0


def test_dias_calor_ignora_999():
    serie = _hist_sintetico(lambda d: None if d.month == 12 else 30.0)
    assert dias_calor_verano_promedio(serie) == 0.0


@pytest.mark.parametrize(
    "dias,esperado",
    [(0, "bajo"), (14.99, "bajo"), (15, "medio"), (24.99, "medio"), (25, "alto"), (40, "alto"), (40.01, "critico")],
)
def test_clasificar_riesgo_termico(dias, esperado):
    assert clasificar_riesgo_termico(dias) == esperado


@pytest.mark.parametrize(
    "punto,dias,esperado",
    [
        ("Balcarce", 11.5, "bajo"),
        ("9 de Julio", 14.1, "bajo"),
        ("Pergamino", 23.8, "medio"),
        ("Marcos Juarez", 31.5, "alto"),
        ("Rafaela", 35.8, "alto"),
        ("Reconquista", 44.7, "critico"),
    ],
)
def test_riesgo_termico_puntos_de_calibracion(punto, dias, esperado):
    assert clasificar_riesgo_termico(dias) == esperado, punto


# ---------- punta a punta ----------


def _run_build(reciente: NasaPowerDailySeries, historico: NasaPowerDailySeries):
    llamadas = []

    def handler(req):
        llamadas.append(dict(req.url.params))
        if req.url.params["start"] == ANALOGOS_START.strftime("%Y%m%d"):
            return httpx.Response(200, json=_payload(historico))
        return httpx.Response(200, json=_payload(reciente))

    async def _go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await build_telemetria_nasa(-33.95, -60.57, client=client, today=HOY)

    return asyncio.run(_go()), llamadas


def test_build_telemetria_punta_a_punta():
    reciente = _reciente(lag_dias=3)
    historico = _hist_sintetico(lambda d: 36.0 if d.month == 1 else 30.0)

    telemetria, llamadas = _run_build(reciente, historico)

    assert isinstance(telemetria, TelemetriaNasa)
    assert telemetria.fecha_ultimo_dato_valido == HOY - timedelta(days=3)
    assert telemetria.indice_humedad_radicular_pct == 46.0
    assert telemetria.indice_humedad_superficial_pct == 35.0
    assert telemetria.tendencia_humedad_15d_pct == 0.0
    assert telemetria.frecuencia_tormentas_extremas_90d == 0
    assert telemetria.riesgo_termico_verano == "alto"  # 31 días/temporada (todo enero)

    corte = telemetria.fecha_ultimo_dato_valido
    clim = climatologia_lluvia_90d_por_doy(historico)
    hist = max(25.0, round(clim[corte.timetuple().tm_yday], 2))  # la caché guarda 2 decimales
    assert telemetria.anomalia_lluvia_90d_pct == pytest.approx(
        round(max(-80, min(140, (180.0 - hist) / hist * 100)), 2)
    )

    # 2 requests: reciente de 100 días + histórico 2006–2025
    starts = sorted(p["start"] for p in llamadas)
    assert starts == ["19810101", (HOY - timedelta(days=99)).strftime("%Y%m%d")]
    hist_call = next(p for p in llamadas if p["start"] == "19810101")
    assert hist_call["end"] == "20251231"
    assert hist_call["parameters"] == "PRECTOTCORR,T2M_MAX,T2M_MIN"  # T2M_MIN desde BACK-6

    # Serializa con las claves exactas del contrato
    assert set(telemetria.model_dump()) == {
        "fecha_ultimo_dato_valido",
        "indice_humedad_radicular_pct",
        "indice_humedad_superficial_pct",
        "tendencia_humedad_15d_pct",
        "anomalia_lluvia_90d_pct",
        "frecuencia_tormentas_extremas_90d",
        "riesgo_termico_verano",
    }


def test_build_sin_gwetroot_valido_lanza():
    reciente = _reciente(GWETROOT=lambda d: None)
    with pytest.raises(NasaPowerUnavailable):
        _run_build(reciente, _hist_sintetico())


def test_build_si_historico_falla_lanza():
    def handler(req):
        if req.url.params["start"] == "19810101":
            return httpx.Response(503)
        return httpx.Response(200, json=_payload(_reciente()))

    async def _go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await build_telemetria_nasa(-33.95, -60.57, client=client, today=HOY)

    with pytest.raises(NasaPowerUnavailable):
        asyncio.run(_go())


# ---------- BACK-4: caché por celda y precálculo ----------


def _handler_contador(reciente, historico, llamadas):
    def handler(req):
        es_hist = req.url.params["start"] == ANALOGOS_START.strftime("%Y%m%d")
        llamadas.append("hist" if es_hist else "reciente")
        return httpx.Response(200, json=_payload(historico if es_hist else reciente))

    return handler


def _build(handler, lat_lon=(-33.95, -60.57), today=HOY):
    async def _go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await build_telemetria_nasa(*lat_lon, client=client, today=today)

    return asyncio.run(_go())


def test_clave_celda_agrupa_y_separa():
    # Verificado contra NASA POWER real: estos 3 puntos devuelven la misma serie
    assert clave_celda_power(-33.95, -60.57) == clave_celda_power(-34.20, -60.90) == clave_celda_power(-33.80, -60.35)
    assert clave_celda_power(-33.95, -60.57) != clave_celda_power(-33.70, -60.57)


def test_segunda_consulta_misma_celda_sin_requests():
    llamadas = []
    handler = _handler_contador(_reciente(), _hist_sintetico(), llamadas)
    t1 = _build(handler, (-33.95, -60.57))
    t2 = _build(handler, (-34.20, -60.90))  # otro lote, misma celda
    assert sorted(llamadas) == ["hist", "reciente"]
    assert t1 == t2


def test_otra_celda_consulta_de_nuevo():
    llamadas = []
    handler = _handler_contador(_reciente(), _hist_sintetico(), llamadas)
    _build(handler, (-33.95, -60.57))
    _build(handler, (-33.70, -60.57))
    assert sorted(llamadas) == ["hist", "hist", "reciente", "reciente"]


def test_ventana_reciente_vence_a_las_6h(_estado_limpio):
    llamadas = []
    handler = _handler_contador(_reciente(), _hist_sintetico(), llamadas)
    _build(handler)
    _estado_limpio.t = 6 * 3600 - 1
    _build(handler)
    assert llamadas.count("reciente") == 1
    _estado_limpio.t = 6 * 3600
    _build(handler)
    assert llamadas.count("reciente") == 2
    assert llamadas.count("hist") == 1  # el histórico no vence


def test_ventana_reciente_de_otro_dia_no_se_reusa():
    llamadas = []
    handler = _handler_contador(_reciente(), _hist_sintetico(), llamadas)
    _build(handler, today=HOY)
    _build(handler, today=HOY + timedelta(days=1))
    assert llamadas.count("reciente") == 2


def test_version_calculo_distinta_se_recalcula():
    llamadas = []
    handler = _handler_contador(_reciente(), _hist_sintetico(), llamadas)
    clave = clave_celda_power(-33.95, -60.57)
    obtener_cache().set(
        nasa_telemetry.ESPACIO_HIST,
        clave,
        {"version_calculo": "vieja", "climatologia_lluvia_90d_por_doy": [100.0] * 366, "dias_calor_verano_promedio": 1.0},
    )
    _build(handler)
    assert "hist" in llamadas
    assert obtener_cache().get(nasa_telemetry.ESPACIO_HIST, clave)["version_calculo"] == nasa_telemetry.VERSION_CALCULO


def test_usa_precalculo_sin_request_historica():
    entrada = nasa_telemetry.referencia_a_dict(
        nasa_telemetry.ReferenciaHistorica(clim_por_doy={d: 200.0 for d in range(1, 367)}, dias_calor_verano_promedio=30.0)
    )
    nasa_telemetry.reiniciar_estado({clave_celda_power(-33.95, -60.57): entrada})
    llamadas = []
    telemetria = _build(_handler_contador(_reciente(), _hist_sintetico(), llamadas))
    assert llamadas == ["reciente"]
    assert telemetria.riesgo_termico_verano == "alto"  # 30 días
    assert telemetria.anomalia_lluvia_90d_pct == -10.0  # 180 mm vs 200 mm


def test_riesgo_se_reclasifica_al_leer():
    # La categoría guardada es vieja; manda el número de días con los umbrales vigentes.
    entrada = nasa_telemetry.referencia_a_dict(
        nasa_telemetry.ReferenciaHistorica(clim_por_doy={d: 200.0 for d in range(1, 367)}, dias_calor_verano_promedio=23.8)
    )
    entrada["riesgo_termico_verano"] = "critico"
    nasa_telemetry.reiniciar_estado({clave_celda_power(-33.95, -60.57): entrada})
    telemetria = _build(_handler_contador(_reciente(), _hist_sintetico(), []))
    assert telemetria.riesgo_termico_verano == "medio"


def test_nasa_caida_mensaje_claro():
    def handler(req):
        return httpx.Response(503)

    with pytest.raises(NasaPowerUnavailable, match="NASA POWER no está respondiendo"):
        _build(handler)


def test_referencia_desde_1981_no_cambia_climatologia_ni_dias_de_calor():
    """ML-13: los años 1981–2005 solo suman análogos; climatología y días de calor siguen en 2006–2025."""
    tmax = lambda d: 36.0 if d.year < 2006 else (35.0 if d.month == 1 and d.day <= 10 else 30.0)  # noqa: E731
    corta = calcular_referencia(_serie(HIST_START, HIST_END, {"PRECTOTCORR": _lluvia_hist, "T2M_MAX": tmax, "T2M_MIN": lambda d: 10.0}))
    larga = calcular_referencia(_serie(ANALOGOS_START, HIST_END, {"PRECTOTCORR": _lluvia_hist, "T2M_MAX": tmax, "T2M_MIN": lambda d: 10.0}))
    assert larga.clim_por_doy == corta.clim_por_doy
    assert larga.dias_calor_verano_promedio == corta.dias_calor_verano_promedio == 10.0
    assert min(larga.calendario_eventos) == 1981 and min(corta.calendario_eventos) == 2006
    assert {a: t for a, t in larga.calendario_eventos.items() if a >= 2006} == corta.calendario_eventos


# ---------- BACK-26: clima histórico por celda desde Supabase (bajo demanda) ----------

import json as _json  # noqa: E402
import time as _time  # noqa: E402

from ml.escenarios import escenarios_por_cultivo  # noqa: E402


@pytest.fixture
def _sin_lector():
    yield
    nasa_telemetry.configurar_lector_hist(None)


def _entrada_sintetica(dias_calor=30.0, mm=200.0):
    return nasa_telemetry.referencia_a_dict(
        nasa_telemetry.ReferenciaHistorica(clim_por_doy={d: mm for d in range(1, 367)}, dias_calor_verano_promedio=dias_calor)
    )


def test_hist_desde_supabase_sin_json_ni_request(_sin_lector):
    pedidas = []
    nasa_telemetry.configurar_lector_hist(lambda clave: pedidas.append(clave) or _entrada_sintetica())
    nasa_telemetry.reiniciar_estado({clave_celda_power(-33.95, -60.57): _entrada_sintetica(dias_calor=1.0)})
    llamadas = []
    telemetria = _build(_handler_contador(_reciente(), _hist_sintetico(), llamadas))
    assert pedidas == [clave_celda_power(-33.95, -60.57)]
    assert llamadas == ["reciente"]
    assert telemetria.riesgo_termico_verano == "alto"  # 30 días: el de Supabase, no el del JSON (1 día)


def test_hist_supabase_con_error_usa_json(_sin_lector):
    def falla(_clave):
        raise RuntimeError("401 invalid api key")

    nasa_telemetry.configurar_lector_hist(falla)
    nasa_telemetry.reiniciar_estado({clave_celda_power(-33.95, -60.57): _entrada_sintetica(dias_calor=30.0)})
    llamadas = []
    telemetria = _build(_handler_contador(_reciente(), _hist_sintetico(), llamadas))
    assert llamadas == ["reciente"]
    assert telemetria.riesgo_termico_verano == "alto"


def test_hist_supabase_lento_corta_por_timeout_y_usa_json(_sin_lector, monkeypatch):
    monkeypatch.setattr(nasa_telemetry, "TIMEOUT_LECTOR_HIST_S", 0.05)
    nasa_telemetry.configurar_lector_hist(lambda _clave: _time.sleep(0.5) or _entrada_sintetica(dias_calor=1.0))
    nasa_telemetry.reiniciar_estado({clave_celda_power(-33.95, -60.57): _entrada_sintetica(dias_calor=30.0)})
    telemetria = _build(_handler_contador(_reciente(), _hist_sintetico(), []))
    assert telemetria.riesgo_termico_verano == "alto"  # el del JSON


def test_hist_supabase_version_vieja_usa_json_y_reescribe(_sin_lector):
    vieja = dict(_entrada_sintetica(dias_calor=1.0), version_calculo="telemetria-v1")
    nasa_telemetry.configurar_lector_hist(lambda _clave: vieja)
    clave = clave_celda_power(-33.95, -60.57)
    nasa_telemetry.reiniciar_estado({clave: _entrada_sintetica(dias_calor=30.0)})
    telemetria = _build(_handler_contador(_reciente(), _hist_sintetico(), []))
    assert telemetria.riesgo_termico_verano == "alto"
    assert obtener_cache().get(nasa_telemetry.ESPACIO_HIST, clave)["version_calculo"] == nasa_telemetry.VERSION_CALCULO


def test_paridad_ensemble_json_vs_supabase_con_celdas_reales():
    """La misma celda leída del JSON o de Supabase (ida y vuelta por jsonb) da la misma
    referencia y los mismos años análogos por cultivo para el ensemble del ML."""
    celdas = _json.loads(nasa_telemetry.RUTA_PRECALCULO.read_text(encoding="utf-8"))["celdas"]
    claves = [clave_celda_power(-33.95, -60.57), clave_celda_power(-29.0, -60.0), clave_celda_power(-37.85, -58.26)]
    for clave in claves:
        desde_json = nasa_telemetry.dict_a_referencia(celdas[clave])
        desde_supabase = nasa_telemetry.dict_a_referencia(_json.loads(_json.dumps(celdas[clave])))
        assert desde_json is not None and desde_json == desde_supabase
        for corte, oni in ((date(2026, 11, 11), -0.6), (date(2026, 5, 20), 0.0)):
            cultivos = ["soja_primera", "maiz_tardio", "girasol", "trigo", "cebada"]
            a = escenarios_por_cultivo(desde_json.calendario_eventos, desde_json.calendario_lluvia, cultivos, corte, oni_actual=oni)
            b = escenarios_por_cultivo(
                desde_supabase.calendario_eventos, desde_supabase.calendario_lluvia, cultivos, corte, oni_actual=oni
            )
            assert a == b
            assert any(a.values())  # hay años análogos
