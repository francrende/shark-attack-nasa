"""Tests de BACK-2 (sin red)."""

import asyncio
from datetime import date, timedelta

import httpx
import pytest

from providers.nasa_power import NasaPowerDailySeries, NasaPowerUnavailable
from providers.nasa_telemetry import (
    HIST_END,
    HIST_START,
    Ventana90d,
    anomalia_lluvia_90d_pct,
    build_telemetria_nasa,
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
        if req.url.params["start"] == HIST_START.strftime("%Y%m%d"):
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
    hist = max(25.0, clim[corte.timetuple().tm_yday])
    assert telemetria.anomalia_lluvia_90d_pct == pytest.approx(
        round(max(-80, min(140, (180.0 - hist) / hist * 100)), 2)
    )

    # 2 requests: reciente de 100 días + histórico 2006–2025
    starts = sorted(p["start"] for p in llamadas)
    assert starts == ["20060101", (HOY - timedelta(days=99)).strftime("%Y%m%d")]
    hist_call = next(p for p in llamadas if p["start"] == "20060101")
    assert hist_call["end"] == "20251231"
    assert hist_call["parameters"] == "PRECTOTCORR,T2M_MAX"

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
        if req.url.params["start"] == "20060101":
            return httpx.Response(503)
        return httpx.Response(200, json=_payload(_reciente()))

    async def _go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await build_telemetria_nasa(-33.95, -60.57, client=client, today=HOY)

    with pytest.raises(NasaPowerUnavailable):
        asyncio.run(_go())
