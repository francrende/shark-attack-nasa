"""Tests de BACK-6: fórmulas de features y constructor de insumos del ML (sin red)."""

import asyncio
from datetime import date, timedelta

import httpx
import pytest

from providers import nasa_telemetry, soilgrids, srtm
from providers.cache import CacheEnCapas, CacheMemoria, clave_celda_power, configurar_cache, obtener_cache
from providers.features import (
    FEATURES_ACTUALES,
    FEATURES_FUTURAS,
    InsumosML,
    aplicar_topes,
    calendario_eventos,
    codificar_evento,
    construir_insumos_ml,
    escenarios_ventana_futura,
    indice_aridez,
)
from providers.resiliencia import ContadorDiario, CorteAutomatico, EsperaMinima, LimitadorTasa

HOY = date(2026, 11, 14)


def _rango(a: date, b: date) -> list[date]:
    return [a + timedelta(days=i) for i in range((b - a).days + 1)]


# ---------- aridez ----------


def test_aridez_con_evptrns():
    lluvia = [152 / 90] * 90
    ev = [202 / 90] * 90
    assert indice_aridez(lluvia, ev, [30.0] * 90, [15.0] * 90) == pytest.approx(152 / 202)


def test_aridez_minimo_diario_y_denominador_30():
    # EVPTRNS diminuto -> suma < 45 -> Hargreaves con Tmedia 22,5: clip(3,6) * 90 = 324
    assert indice_aridez([1.0] * 90, [0.0] * 90, [30.0] * 90, [15.0] * 90) == pytest.approx(90 / 324)


def test_aridez_hargreaves_con_topes():
    # Tmedia 50 -> 8,0 -> tope 6,5 ; Tmedia 0 -> 0 -> piso 1,2
    assert indice_aridez([1.0] * 2, [None, None], [50.0, 0.0], [50.0, 0.0], ) == pytest.approx(2 / 30)


def test_aridez_none_en_evptrns_no_suma():
    v = indice_aridez([100.0], [None, 50.0], [30.0, 30.0], [15.0, 15.0])
    assert v == pytest.approx(100 / 50)


# ---------- eventos y calendario ----------


@pytest.mark.parametrize(
    "p,tx,tn,esperado",
    [
        (0, 20, 10, "0"),
        (50.0, 34.0, 2.0, "0"),  # umbrales estrictos
        (50.1, 20, 10, "1"),
        (0, 34.1, 10, "2"),
        (0, 20, 1.9, "4"),
        (60, 36, 1, "7"),
        (None, None, None, "0"),
    ],
)
def test_codificar_evento(p, tx, tn, esperado):
    assert codificar_evento(p, tx, tn) == esperado


def test_calendario_rellena_huecos_y_agrupa_por_anio():
    fechas = _rango(date(2023, 12, 30), date(2024, 1, 2))
    cal = calendario_eventos(fechas, [60, None, 0, 0], [36, 36, None, 20], [10, 10, 10, None])
    # día 2: lluvia rellena con 60 (ffill) ; día 3: tmax rellena con 36
    assert cal == {2023: "33", 2024: "20"}


# ---------- escenarios de la ventana futura ----------


def _cal_desde(func, desde=date(2006, 1, 1), hasta=date(2025, 12, 31)):
    fechas = _rango(desde, hasta)
    p = [func(d)[0] for d in fechas]
    tx = [func(d)[1] for d in fechas]
    tn = [func(d)[2] for d in fechas]
    return calendario_eventos(fechas, p, tx, tn)


def test_escenarios_cantidad_de_anios():
    cal = _cal_desde(lambda d: (0, 20, 10))
    assert len(escenarios_ventana_futura(cal, date(2026, 11, 11))) == 19  # 2025 no completa
    assert len(escenarios_ventana_futura(cal, date(2026, 1, 10))) == 20


def test_escenarios_cruzan_el_anio_y_mantienen_el_mismo_anio():
    # 2010: calor todo diciembre y enero; heladas solo en enero de 2011
    def f(d):
        calor = 40 if (d.year == 2010 and d.month == 12) or (d.year == 2011 and d.month == 1) else 20
        helada = 0 if d.year == 2011 and d.month == 1 else 10
        return (0, calor, helada)

    esc = {e["anio"]: e for e in escenarios_ventana_futura(_cal_desde(f), date(2026, 11, 30))}
    # Ventana 1/12/2010 -> 28/2/2011: 31 días de dic + 31 de ene con calor; 31 heladas
    assert esc[2010]["frecuencia_estres_termico"] == 45  # 62 -> tope 45
    assert esc[2010]["frecuencia_riesgo_helada"] == 31
    assert esc[2011]["frecuencia_estres_termico"] == 0


def test_escenarios_29_febrero():
    cal = _cal_desde(lambda d: (0, 20, 10))
    esc = escenarios_ventana_futura(cal, date(2028, 2, 29))
    assert len(esc) == 20
    assert all(set(e) == {"anio", *FEATURES_FUTURAS} for e in esc)


def test_escenarios_tope_tormentas():
    cal = _cal_desde(lambda d: (80, 20, 10))
    assert escenarios_ventana_futura(cal, date(2026, 3, 1))[0]["frecuencia_tormentas_extremas"] == 12


def test_escenarios_paridad_con_pandas():
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")

    def f(d):
        if d.day == 13 and d.month == 3:
            return (None, None, None)  # huecos
        return ((d.toordinal() * 37) % 61, 25 + (d.toordinal() * 7) % 13, (d.toordinal() * 11) % 9 - 2)

    fechas = _rango(date(2006, 1, 1), date(2025, 12, 31))
    cal = calendario_eventos(fechas, *[[f(d)[i] for d in fechas] for i in range(3)])

    df = pd.DataFrame(
        {
            "date": pd.to_datetime([d.isoformat() for d in fechas]),
            "prectotcorr": [np.nan if f(d)[0] is None else f(d)[0] for d in fechas],
            "t2m_max": [np.nan if f(d)[1] is None else f(d)[1] for d in fechas],
            "t2m_min": [np.nan if f(d)[2] is None else f(d)[2] for d in fechas],
        }
    )
    cols = ["prectotcorr", "t2m_max", "t2m_min"]
    df[cols] = df[cols].ffill().bfill()

    corte = date(2026, 11, 11)
    nuestros = {e["anio"]: e for e in escenarios_ventana_futura(cal, corte)}
    for anio, esc in nuestros.items():
        t = pd.Timestamp(date(anio, corte.month, corte.day))
        idx = int(df.index[df["date"] == t][0])
        win_future = df.iloc[idx + 1 : idx + 91]  # igual que generate_dataset.py
        assert esc["frecuencia_tormentas_extremas"] == min(12, int((win_future["prectotcorr"] > 50.0).sum()))
        assert esc["frecuencia_estres_termico"] == min(45, int((win_future["t2m_max"] > 34.0).sum()))
        assert esc["frecuencia_riesgo_helada"] == min(55, int((win_future["t2m_min"] < 2.0).sum()))


# ---------- topes ----------


def test_aplicar_topes():
    t = aplicar_topes(
        {
            "gwetroot_saturacion_pct": 2.0,
            "gwettop_saturacion_pct": 99.9,
            "tendencia_humedad_15d_pct": -55.123,
            "anomalia_lluvia_90d_pct": 200,
            "indice_aridez_evaporativa": 0.75249,
            "pendiente_terreno_pct": 0.0,
            "elevacion_m": 900,
            "textura_arcilla_pct": 23.456,
            "frecuencia_estres_termico": 51,
            "otra": "intacta",
        }
    )
    assert t["gwetroot_saturacion_pct"] == 5.0
    assert t["gwettop_saturacion_pct"] == 99.0
    assert t["tendencia_humedad_15d_pct"] == -40.0
    assert t["anomalia_lluvia_90d_pct"] == 140.0
    assert t["indice_aridez_evaporativa"] == 0.752
    assert t["pendiente_terreno_pct"] == 0.10
    assert t["elevacion_m"] == 580.0
    assert t["textura_arcilla_pct"] == 23.46
    assert t["frecuencia_estres_termico"] == 45 and isinstance(t["frecuencia_estres_termico"], int)
    assert t["otra"] == "intacta"


def test_aplicar_topes_respeta_none():
    assert aplicar_topes({"textura_arcilla_pct": None})["textura_arcilla_pct"] is None


# ---------- construir_insumos_ml (punta a punta con mocks) ----------


@pytest.fixture(autouse=True)
def _estado_limpio():
    configurar_cache(CacheEnCapas(CacheMemoria()))
    nasa_telemetry.reiniciar_estado({})
    soilgrids.reiniciar_estado(lotes_ejemplo=[])

    class Reloj:
        t = 0.0

        def __call__(self):
            return self.t

        async def dormir(self, s):
            self.t += s

    r = Reloj()
    srtm.reiniciar_estado(CorteAutomatico(reloj=r), EsperaMinima(reloj=r, dormir=r.dormir), ContadorDiario())
    yield
    configurar_cache(CacheEnCapas(CacheMemoria()))
    nasa_telemetry.reiniciar_estado(None)
    soilgrids.reiniciar_estado()
    srtm.reiniciar_estado()


def _payload_nasa(series: dict) -> dict:
    return {
        "geometry": {"coordinates": [-60.57, -33.95, 70.0]},
        "properties": {
            "parameter": {
                p: {d.strftime("%Y%m%d"): (-999.0 if v is None else v) for d, v in vals.items()}
                for p, vals in series.items()
            }
        },
    }


def _reciente(corte: date) -> dict:
    dias = _rango(HOY - timedelta(days=99), HOY)

    def lag(v):
        return lambda d: None if d > corte else v

    return {
        p: {d: f(d) for d in dias}
        for p, f in {
            "PRECTOTCORR": lag(152 / 90),
            "GWETROOT": lag(0.46),
            "GWETTOP": lag(0.35),
            "EVPTRNS": lag(202 / 90),
            "T2M_MAX": lag(30.0),
            "T2M_MIN": lag(15.0),
        }.items()
    }


def _historico() -> dict:
    dias = _rango(date(2006, 1, 1), date(2025, 12, 31))
    return {
        "PRECTOTCORR": {d: 1.8 for d in dias},
        "T2M_MAX": {d: (36.0 if d.month == 12 and d.day <= 20 else 30.0) for d in dias},
        "T2M_MIN": {d: 15.0 for d in dias},
    }


SUELO = {
    "properties": {
        "layers": [
            {"name": n, "unit_measure": {"d_factor": 10}, "depths": [{"label": e, "values": {"mean": v}} for e in ("0-5cm", "5-15cm", "15-30cm")]}
            for n, v in {"clay": 234, "sand": 142, "silt": 624, "soc": 179, "phh2o": 64}.items()
        ]
    }
}


def _handler(registro: list[str], *, suelo_ok: bool = True):
    corte = HOY - timedelta(days=3)

    def h(req):
        host = req.url.host
        if "power.larc" in host:
            es_hist = req.url.params["start"] == "20060101"
            registro.append("nasa_hist" if es_hist else "nasa_reciente")
            return httpx.Response(200, json=_payload_nasa(_historico() if es_hist else _reciente(corte)))
        if "isric" in host:
            registro.append("suelo")
            return httpx.Response(200, json=SUELO) if suelo_ok else httpx.Response(503)
        registro.append("srtm")
        return httpx.Response(200, json={"results": [{"elevation": 69.0}] * 9})

    return h


def _construir(handler):
    async def _go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await construir_insumos_ml(-33.95, -60.57, client=client, today=HOY)

    return asyncio.run(_go())


def test_insumos_punta_a_punta():
    registro: list[str] = []
    ins = _construir(_handler(registro))

    assert isinstance(ins, InsumosML)
    assert set(ins.features_actuales) == set(FEATURES_ACTUALES)
    f = ins.features_actuales
    assert f["gwetroot_saturacion_pct"] == 46.0
    assert f["gwettop_saturacion_pct"] == 35.0
    assert f["indice_aridez_evaporativa"] == round(152 / 202, 3)
    assert f["pendiente_terreno_pct"] == 0.10  # plano -> tope inferior
    assert f["elevacion_m"] == 69.0
    assert f["textura_arcilla_pct"] == 23.4
    assert ins.fecha_corte == HOY - timedelta(days=3)

    assert len(ins.escenarios_historicos) == 19
    # Ventana 12/11 -> 9/2: diciembre aporta 20 días de calor por año
    assert {e["frecuencia_estres_termico"] for e in ins.escenarios_historicos} == {20}

    # Una sola consulta por fuente: la ventana reciente y la referencia salen de la caché
    assert sorted(registro) == ["nasa_hist", "nasa_reciente", "srtm", "suelo"]
    assert ins.telemetria.indice_humedad_radicular_pct == 46.0
    assert ins.perfil_suelo.textura_predominante == "franco_limoso"
    assert ins.advertencias == ()


def test_insumos_combinan_advertencias_de_providers():
    ins = _construir(_handler([], suelo_ok=False))
    assert ins.perfil_suelo.fuente == "fallback_regional"
    assert any("Textura estimada regionalmente" in a for a in ins.advertencias)
    assert ins.features_actuales["textura_arcilla_pct"] == 25.4  # arcilla GeoINTA


def test_entrada_v1_en_cache_se_recalcula():
    clave = clave_celda_power(-33.95, -60.57)
    obtener_cache().set(
        nasa_telemetry.ESPACIO_HIST,
        clave,
        {"version_calculo": "telemetria-v1", "climatologia_lluvia_90d_por_doy": [100.0] * 366, "dias_calor_verano_promedio": 1.0},
    )
    registro: list[str] = []
    ins = _construir(_handler(registro))
    assert "nasa_hist" in registro
    assert len(ins.escenarios_historicos) == 19
    assert obtener_cache().get(nasa_telemetry.ESPACIO_HIST, clave)["version_calculo"] == nasa_telemetry.VERSION_CALCULO
