"""Tests de ML-6: calendario, label MAGyP, armado de filas y paridad con producción (sin red)."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

import httpx
import numpy as np
import pandas as pd
import pytest

from ml import calendario_siembra as cal
from ml.generate_dataset import (
    FEATURE_COLUMNS_V2,
    ORIGEN_COBERTURA,
    ORIGEN_MAGYP,
    ORIGEN_WHAT_IF,
    TARGET_COLUMN,
    ajustar_mapeo_cuantiles,
    aplicar_mapeo,
    asignar_pesos,
    construir_dataset,
    features_actuales_en,
    filas_departamento,
    recortar_serie,
    referencia_historica,
    split_de,
)
from ml.magyp import calcular_labels, filtrar_pampa, puntaje_vs_tendencia, tendencia_theil_sen
from ml.escenarios import escenarios_por_cultivo, fecha_equivalente, pesos_analogos
from providers import enso
from providers.features import (
    FEATURES_ACTUALES,
    FEATURES_PERIODO_CRITICO,
    calendario_lluvia,
    codificar_lluvia,
    construir_insumos_ml,
    decodificar_lluvia,
    features_ventana,
)
from providers.nasa_power import NasaPowerDailySeries
from providers.test_features import HOY, _estado_limpio, _handler, _historico, _reciente  # noqa: F401
from services.simulation_service import campana_vigente

# ---------------------------------------------------------------------------
# Calendario
# ---------------------------------------------------------------------------


def test_regla_de_campana_igual_al_backend():
    dia = date(2023, 1, 1)
    while dia < date(2025, 1, 1):
        assert cal.campana_de(dia) == campana_vigente(dia), dia
        dia += timedelta(days=1)


def test_anio_campana_y_fechas_de_siembra():
    assert cal.anio_campana(date(2022, 11, 10)) == 2022  # verano 2022/23
    assert cal.anio_campana(date(2023, 1, 20)) == 2022  # sigue verano 2022/23
    assert cal.anio_campana(date(2023, 5, 1)) == 2023  # invierno 2023/24
    assert cal.inicio_siembra("maiz_tardio", 2022) == date(2022, 12, 1)
    assert cal.fin_siembra("maiz_tardio", 2022) == date(2023, 1, 10)  # cruza de año
    assert cal.inicio_siembra("trigo", 2023) == date(2023, 5, 20)


def test_dias_hasta_siembra():
    assert cal.dias_hasta_siembra("soja_primera", date(2022, 10, 15)) == 10
    assert cal.dias_hasta_siembra("soja_primera", date(2022, 11, 4)) == -10  # dentro de la ventana
    assert cal.dias_hasta_siembra("maiz_tardio", date(2023, 1, 5)) == -35


def test_fechas_ventana_desde_habilitacion_hasta_ultimo_fin():
    verano = cal.fechas_ventana("verano", 2022)
    assert cal.campana_de(verano[0]) == "verano"
    assert cal.campana_de(verano[0] - timedelta(days=1)) == "invierno"
    assert verano[-1] <= date(2023, 1, 15) < verano[-1] + timedelta(days=10)
    assert all((b - a).days == 10 for a, b in zip(verano, verano[1:]))
    invierno = cal.fechas_ventana("invierno", 2023)
    assert all(cal.campana_de(t) == "invierno" for t in invierno)


# ---------------------------------------------------------------------------
# Label MAGyP
# ---------------------------------------------------------------------------


def test_theil_sen_robusto_a_un_anio_de_sequia():
    x = np.arange(2006, 2019)
    y = 3000 + 50 * (x - 2006)
    y = y.astype(float)
    y[2] = 800  # 2008/09
    pendiente, ordenada = tendencia_theil_sen(x, y)
    assert pendiente == pytest.approx(50.0)
    assert ordenada + pendiente * 2010 == pytest.approx(3200.0)


def test_puntaje_vs_tendencia():
    assert puntaje_vs_tendencia(1000, 1000) == pytest.approx(50.0)
    assert puntaje_vs_tendencia(800, 1000) == pytest.approx(30.0)
    assert puntaje_vs_tendencia(400, 1000) == pytest.approx(0.0)
    assert puntaje_vs_tendencia(2000, 1000) == pytest.approx(100.0)


def _crudo(filas):
    base = {"provincia": "Buenos Aires", "departamento": "Pergamino", "provincia_id": "06"}
    return pd.DataFrame([{**base, **f} for f in filas])


def test_filtrar_cebada_cervecera_hasta_2015_y_total_desde_2016():
    filas = []
    for anio in (2014, 2015, 2016, 2017):
        for cultivo in ("cebada cervecera", "cebada total", "cebada forrajera"):
            filas.append({
                "departamento_id": "6623", "campania": f"{anio}/{anio + 1}", "cultivo": cultivo,
                "superficie_sembrada_ha": 5000, "superficie_cosechada_ha": 5000,
                "produccion_tm": 15000, "rendimiento_kgxha": 3000,
            })
    out = filtrar_pampa(_crudo(filas))
    assert out["departamento_id"].eq("06623").all()
    assert sorted(out["anio_campana"]) == [2014, 2015, 2016, 2017]  # uno por año, sin forrajera
    assert set(out["cultivo_magyp"]) == {"cebada"}


def _serie_dep(rendimientos, fc=None, sembrada=10000):
    filas = []
    for i, (anio, rinde) in enumerate(rendimientos.items()):
        f = 1.0 if fc is None else fc[i]
        filas.append({
            "departamento_id": "06623", "cultivo_magyp": "maiz", "anio_campana": anio,
            "superficie_sembrada_ha": sembrada, "superficie_cosechada_ha": sembrada * f,
            "produccion_tm": rinde * sembrada * f / 1000.0, "rendimiento_kgxha": rinde,
        })
    return pd.DataFrame(filas)


def test_ajuste_por_abandono_penaliza_solo_lo_extra():
    anios = list(range(2006, 2019))
    fc = [0.75] * len(anios)  # 25% de silo habitual
    fc[3] = 0.375  # sequía: se abandonó la mitad de lo habitual
    lab = calcular_labels(_serie_dep({a: 8000.0 for a in anios}, fc=fc), anios)
    normal = lab[lab["anio_campana"] != 2009]
    assert normal["puntaje"].eq(50.0).all()  # el silo habitual no penaliza
    seco = lab[lab["anio_campana"] == 2009].iloc[0]
    assert seco["rinde_ajustado"] == pytest.approx(4000.0)
    assert seco["puntaje"] == pytest.approx(0.0)


def test_filtros_superficie_y_minimo_de_anios():
    anios = list(range(2006, 2019))
    assert calcular_labels(_serie_dep({a: 8000.0 for a in anios}, sembrada=500), anios).empty
    pocos = list(range(2006, 2013))  # 7 campañas de train < 8
    assert calcular_labels(_serie_dep({a: 8000.0 for a in pocos}), anios).empty


def test_tendencia_solo_con_train_y_extrapolada_a_test():
    anios = list(range(2006, 2025))
    rindes = {a: 5000.0 + 100 * (a - 2006) for a in anios}
    rindes[2022] = 0.8 * (5000.0 + 100 * 16)  # sequía de test
    lab = calcular_labels(_serie_dep(rindes), range(2006, 2019)).set_index("anio_campana")
    assert lab.loc[2020, "puntaje"] == pytest.approx(50.0)
    assert lab.loc[2022, "puntaje"] == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# Filas y dataset
# ---------------------------------------------------------------------------


def _serie_completa() -> NasaPowerDailySeries:
    """Histórico 2006–2025 + humedad/EVPTRNS constantes (como los mocks del backend)."""
    hist = _historico()
    dias = sorted(hist["PRECTOTCORR"])
    inicio = date(2005, 10, 1)
    previos = [inicio + timedelta(days=i) for i in range((dias[0] - inicio).days)]
    todos = previos + dias
    series = {
        "PRECTOTCORR": {d: hist["PRECTOTCORR"].get(d, 1.8) for d in todos},
        "T2M_MAX": {d: hist["T2M_MAX"].get(d, 30.0) for d in todos},
        "T2M_MIN": {d: hist["T2M_MIN"].get(d, 15.0) for d in todos},
        "GWETROOT": {d: 0.46 for d in todos},
        "GWETTOP": {d: 0.35 for d in todos},
        "EVPTRNS": {d: 2.2 for d in todos},
    }
    return NasaPowerDailySeries(lat=-33.95, lon=-60.57, start=todos[0], end=todos[-1], series=series)


ESTATICOS = {"pendiente_terreno_pct": 0.8, "elevacion_m": 69.0, "textura_arcilla_pct": 23.4}


def test_paridad_features_actuales_con_construir_insumos_ml():
    """La función del dataset da las mismas 8 features que producción para la misma serie y corte."""
    registro: list[str] = []

    async def _go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(_handler(registro))) as client:
            return await construir_insumos_ml(-33.95, -60.57, client=client, today=HOY)

    ins = asyncio.run(_go())
    corte = ins.fecha_corte

    hist = _historico()
    reciente = _reciente(corte)
    series = {p: dict(hist.get(p, {})) for p in ("PRECTOTCORR", "T2M_MAX", "T2M_MIN")}
    for p, valores in reciente.items():
        series.setdefault(p, {}).update(valores)
    todos = sorted(set().union(*[set(v) for v in series.values()]))
    serie = NasaPowerDailySeries(lat=-33.95, lon=-60.57, start=todos[0], end=todos[-1], series=series)

    from providers.features import features_actuales_desde_series
    from providers.nasa_telemetry import calcular_referencia

    hist_serie = NasaPowerDailySeries(
        lat=-33.95, lon=-60.57, start=date(2006, 1, 1), end=date(2025, 12, 31),
        series={p: hist[p] for p in ("PRECTOTCORR", "T2M_MAX", "T2M_MIN")},
    )
    ref = calcular_referencia(hist_serie)
    estaticos = {
        "pendiente_terreno_pct": ins.topografia.pendiente_terreno_pct,
        "elevacion_m": ins.topografia.elevacion_m,
        "textura_arcilla_pct": ins.perfil_suelo.arcilla_pct,
    }
    recorte = recortar_serie(serie, corte - timedelta(days=99), corte)
    actuales = features_actuales_desde_series(recorte, corte, ref.clim_por_doy, **estaticos)
    assert actuales == ins.features_actuales


def test_features_actuales_en_tiene_las_8_y_el_oni():
    serie = _serie_completa()
    ref = referencia_historica(serie)
    t = date(2012, 9, 25)
    f = features_actuales_en(serie, ref, t, ESTATICOS)
    assert set(f) == set(FEATURES_ACTUALES) | {"oni_actual"}
    assert f["oni_actual"] == enso.oni_al(t)


def test_periodo_critico_observado_en_las_filas():
    """maiz_temprano 2012: ventana crítica 30/10/2012–27/01/2013 incluye el calor del 1 al 20/12."""
    serie = _serie_completa()
    filas = filas_departamento("06623", serie, ESTATICOS, {("maiz", 2012): 40.0}, range(2012, 2013))
    maiz = [f for f in filas if f["cultivo_candidato"] == "maiz_temprano"]
    assert maiz and all(f["frecuencia_estres_termico"] == 20 for f in maiz)
    assert all(f["lluvia_periodo_critico_mm"] == pytest.approx(162.0) for f in maiz)  # 1,8 mm × 90
    assert cal.inicio_periodo_critico("maiz_temprano", 2012) == date(2012, 10, 30)


def test_calendario_lluvia_y_ventana():
    assert decodificar_lluvia(codificar_lluvia(12.34) + codificar_lluvia(0) + codificar_lluvia(999)) == pytest.approx([12.3, 0.0, 409.5])
    fechas = [date(2010, 1, 1) + timedelta(days=i) for i in range(385)]  # calendarios: años desde el 1/1
    lluvias = [None] * 359 + [5.0] + [1.0] * 25  # 25/12 = día 359; bfill rellena hacia atrás
    cal_ll = calendario_lluvia(fechas, lluvias)
    cal_ev = {a: "0" * (len(t) // 2) for a, t in cal_ll.items()}
    f = features_ventana(cal_ev, cal_ll, date(2010, 12, 25), dias=10)  # cruza de año
    assert f["lluvia_periodo_critico_mm"] == pytest.approx(5.0 + 5.0 + 8.0)  # bfill del primer día
    assert features_ventana(cal_ev, cal_ll, date(2011, 1, 10), dias=30) is None  # ventana incompleta
    assert set(f) == set(FEATURES_PERIODO_CRITICO)


def test_filas_departamento_y_pesos():
    serie = _serie_completa()
    labels = {(c, 2012): 40.0 for c in ("maiz", "soja_primera", "soja_segunda", "girasol", "sorgo", "trigo", "cebada")}
    filas = filas_departamento("06623", serie, ESTATICOS, labels, range(2012, 2013))
    df = pd.DataFrame(filas)
    assert set(FEATURE_COLUMNS_V2) <= set(df.columns)
    reales = df[df["origen_muestra"] == ORIGEN_MAGYP]
    assert reales[TARGET_COLUMN].eq(40.0).all()
    assert set(df.loc[df["origen_muestra"] == ORIGEN_COBERTURA, "cultivo_candidato"]) == {
        "vicia_cobertura", "avena_cobertura", "camelina"
    }
    # cada fila está en la campaña correcta y antes del fin de siembra de su cultivo
    for r in df.itertuples():
        t = date.fromisoformat(r.fecha_t)
        assert cal.campana_de(t) == r.campana
        assert t <= cal.fin_siembra(r.cultivo_candidato, r.anio_campana)
        assert r.dias_hasta_siembra == cal.dias_hasta_siembra(r.cultivo_candidato, t, r.anio_campana)
    pesos = asignar_pesos(reales)
    sumas = pesos.groupby([reales["departamento_id"], reales["anio_campana"], reales["cultivo_candidato"]]).sum()
    assert np.allclose(sumas, 1.0)


def test_sin_label_no_hay_filas_de_ese_cultivo():
    serie = _serie_completa()
    filas = filas_departamento("06623", serie, ESTATICOS, {("trigo", 2012): 55.0}, range(2012, 2013))
    cultivos = {f["cultivo_candidato"] for f in filas if f["origen_muestra"] == ORIGEN_MAGYP}
    assert cultivos == {"trigo"}


def test_construir_dataset_split_fao_y_what_if_solo_en_train():
    serie = _serie_completa()
    rng = np.random.default_rng(0)
    filas = []
    for anio in (2010, 2011, 2020, 2023):
        labels = {(c, anio): float(rng.uniform(10, 90)) for c in ("maiz", "soja_primera", "trigo", "cebada")}
        filas += filas_departamento("06623", serie, ESTATICOS, labels, range(anio, anio + 1))
    df, mapeos = construir_dataset(filas)
    assert set(mapeos) == {"invierno", "verano"}
    assert set(df["split"]) == {"train", "val", "test"}
    no_train = df[df["split"] != "train"]
    assert no_train["origen_muestra"].eq(ORIGEN_MAGYP).all()
    train = df[df["split"] == "train"]
    assert {ORIGEN_MAGYP, ORIGEN_COBERTURA, ORIGEN_WHAT_IF} <= set(train["origen_muestra"])
    wi = train[train["origen_muestra"] == ORIGEN_WHAT_IF]
    reales = train[train["origen_muestra"] == ORIGEN_MAGYP]
    assert len(wi) == round(0.15 * len(reales))
    assert df[TARGET_COLUMN].between(0, 100).all()
    assert df["sample_weight"].gt(0).all()


def test_mapeo_cuantiles_monotono():
    fao = np.linspace(40, 95, 500)
    label = np.linspace(0, 100, 500)
    mapeo = ajustar_mapeo_cuantiles(fao, label)
    assert aplicar_mapeo(np.array([40.0]), mapeo)[0] == pytest.approx(0.0)
    assert aplicar_mapeo(np.array([95.0]), mapeo)[0] == pytest.approx(100.0)
    vals = aplicar_mapeo(np.linspace(30, 100, 50), mapeo)
    assert np.all(np.diff(vals) >= 0)


def test_split_por_campana():
    assert split_de(2006) == split_de(2018) == "train"
    assert split_de(2019) == split_de(2021) == "val"
    assert split_de(2022) == split_de(2024) == "test"
    assert split_de(2025) is None


def test_escenarios_por_cultivo_excluye_el_anio_y_pondera_por_oni():
    serie = _serie_completa()
    ref = referencia_historica(serie)
    corte = date(2022, 9, 25)
    esc = escenarios_por_cultivo(
        ref.calendario_eventos, ref.calendario_lluvia, ["maiz_temprano", "trigo"], corte,
        anio_campana=2022, oni_actual=enso.oni_al(corte), excluir_anio=2022,
    )
    anios = {e["anio"] for e in esc["maiz_temprano"]}
    assert 2022 not in anios
    assert 2025 not in anios  # la ventana 2025/26 no está completa
    assert set(FEATURES_PERIODO_CRITICO) | {"anio", "peso"} <= set(esc["maiz_temprano"][0])
    # ML-12: 2022/23 fue La Niña → son análogos 2010/11 (La Niña), no 2015/16 (El Niño fuerte)
    assert 2010 in anios and 2015 not in anios
    assert len(anios) == enso.MIN_ANIOS_ANALOGOS  # pocas Niñas a esa fecha: se completa por cercanía
    assert all(enso.oni_al(fecha_equivalente(corte, 2022, a)) < 0 for a in anios)
    assert all(e["peso"] == 1.0 for e in esc["maiz_temprano"])
    assert pesos_analogos(corte, 2022, [2010, 2015], None) == {2010: 1.0, 2015: 1.0}
    assert fecha_equivalente(date(2023, 1, 5), 2022, 2010) == date(2011, 1, 5)


def test_pesos_por_fase_y_completado_por_cercania():
    """ML-12: misma fase → 1, otra → 0; con pocos años en la fase se completa con los más cercanos."""
    onis = {2007: -1.0, 2010: -1.4, 2011: -0.8, 2020: -0.8, 2021: -0.6, 2013: -0.3, 2015: 2.0, 2023: 1.5, 2009: 0.7}
    assert enso.fase_enso(0.5) == "nino" and enso.fase_enso(-0.5) == "nina" and enso.fase_enso(0.49) == "neutro"
    pesos = enso.pesos_por_fase(-0.9, onis)
    assert {a for a, p in pesos.items() if p} == {2007, 2010, 2011, 2020, 2021}
    completado = enso.pesos_por_fase(2.4, onis)  # 3 años El Niño → se suman los 2 de ONI más cercano
    assert {a for a, p in completado.items() if p} == {2015, 2023, 2009, 2013, 2021}
    assert set(completado.values()) == {0.0, 1.0}


def test_escenarios_out_tiene_todos_los_cultivos_y_anios():
    serie = _serie_completa()
    salida: list = []
    filas_departamento("06623", serie, ESTATICOS, {("trigo", 2022): 50.0}, range(2022, 2023), salida)
    cultivos = {e["cultivo_candidato"] for e in salida}
    assert cultivos == set(cal.CALENDARIO)
    assert {e["anio"] for e in salida if e["cultivo_candidato"] == "trigo"} >= set(range(2006, 2025))


# ---------------------------------------------------------------------------
# ML-17: tendencias por departamento (rinde en kg/ha)
# ---------------------------------------------------------------------------


def test_tendencias_reproducen_la_tendencia_del_label():
    """La tendencia exportada, proyectada a cada campaña, es la misma que usa el label."""
    from ml.magyp import MAGYP_CSV, tendencia_en, tendencias_por_departamento

    df = pd.read_csv(MAGYP_CSV, dtype={"departamento_id": str})
    deps = sorted(df["departamento_id"].unique())[:15]
    muestra = df[df["departamento_id"].isin(deps)]
    anios = range(2006, 2025)
    labels = calcular_labels(muestra, anios)
    tend = tendencias_por_departamento(muestra, anios)
    assert len(labels) > 0
    for (dep, cultivo), g in labels.groupby(["departamento_id", "cultivo_magyp"]):
        params = tend[dep]["cultivos"][cultivo]
        esperado = tendencia_en(params, g["anio_campana"].to_numpy())
        np.testing.assert_allclose(esperado, g["tendencia_kgxha"].to_numpy(), rtol=1e-5)


def test_tendencias_json_al_dia():
    """``tendencias_magyp.json`` coincide con regenerarlo desde ``magyp_pampa.csv``."""
    import json

    from ml.generate_dataset import ANIOS_TENDENCIA
    from ml.magyp import MAGYP_CSV, TENDENCIAS_JSON, tendencias_por_departamento

    guardado = json.loads(TENDENCIAS_JSON.read_text(encoding="utf-8"))
    df = pd.read_csv(MAGYP_CSV, dtype={"departamento_id": str})
    nuevo = tendencias_por_departamento(df, ANIOS_TENDENCIA)
    assert guardado["anios"] == [ANIOS_TENDENCIA.start, ANIOS_TENDENCIA.stop - 1]
    assert guardado["departamentos"] == json.loads(json.dumps(nuevo, ensure_ascii=False))
