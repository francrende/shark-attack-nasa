"""Generador del dataset de entrenamiento con rindes reales de MAGyP (ML-6).

Uso (desde ``backend/``)::

    python -m ml.generate_dataset                  # descargas faltantes + dataset
    python -m ml.generate_dataset --solo-descargas # solo MAGyP, georef, suelo/topografía y NASA
    python -m ml.generate_dataset --sin-red        # falla si falta algún dato en caché

Pasos:
1. **Label**: CSV de MAGyP → región pampeana → puntaje vs. tendencia (``magyp.py``).
2. **Departamentos**: centroide de georef + suelo (SoilGrids 0–30 cm) y topografía (SRTM, Horn
   3×3), con los providers del backend (Tarea C.3). Sin jitter: la variación espacial es real.
3. **NASA POWER** diaria 2005-10 → 2025-12 por celda (deduplicada), secuencial y reanudable.
4. **Filas**: por departamento × campaña × fecha t (cada 10 días, desde la habilitación de la
   campaña hasta el fin de siembra de cada cultivo). Las features actuales salen de
   ``providers.features.features_actuales_desde_series`` y las futuras del calendario de
   eventos del backend (Tarea C.2): entrenamiento y producción calculan igual.
5. **Split por campaña**, pesos ``1/n_ventanas``, filas FAO (coberturas) y What-If (label delta)
   solo en train.
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml import calendario_siembra as cal
from ml.fao_labels import CROP_CATALOG, FEATURE_COLUMNS, TARGET_COLUMN, compute_fao_hydroclimatic_score
from ml.magyp import (
    CULTIVO_MODELO_A_MAGYP,
    PROVINCIAS_PAMPA,
    calcular_labels,
    descargar_csv,
    filtrar_pampa,
)

__all__ = ["CROP_CATALOG", "FEATURE_COLUMNS", "TARGET_COLUMN", "compute_fao_hydroclimatic_score"]

SEED = 42
ML_DIR = Path(__file__).resolve().parent
DATA_DIR = ML_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
CACHE_NASA_DIR = DATA_DIR / "cache" / "nasa"
# ML-13: años 1981–2005 (solo lluvia y temperaturas) para los escenarios de años análogos.
CACHE_NASA_ANALOGOS_DIR = DATA_DIR / "cache" / "nasa_analogos_1981"
MAGYP_CRUDO = RAW_DIR / "estimaciones_agricolas.csv"
MAGYP_PAMPA = DATA_DIR / "magyp_pampa.csv"
DEPARTAMENTOS_JSON = DATA_DIR / "departamentos_pampa.json"
SALIDA_SPLIT = DATA_DIR / "dataset_magyp_{split}.csv.gz"
SALIDA_ESCENARIOS = DATA_DIR / "dataset_magyp_escenarios.csv.gz"
METADATA_JSON = DATA_DIR / "dataset_magyp_metadata.json"

ANIOS_TRAIN = range(2006, 2019)  # campañas 2006/07 … 2018/19
ANIOS_VAL = range(2019, 2022)  # 2019/20 … 2021/22
ANIOS_TEST = range(2022, 2025)  # 2022/23 … 2024/25
# ML-7: la tendencia de rinde se ajusta con todo el período (label = desvío vs. tendencia de
# largo plazo, igual en todos los splits). Solo usa rindes, nunca clima.
ANIOS_TENDENCIA = range(2006, 2025)

NASA_INICIO = date(2005, 10, 1)  # 100 días antes de la primera ventana (feb-2006)
NASA_FIN = date(2025, 12, 31)
NASA_PARAMETROS = ["GWETROOT", "GWETTOP", "PRECTOTCORR", "T2M_MAX", "T2M_MIN", "EVPTRNS"]
ANALOGOS_INICIO = date(1981, 1, 1)  # = providers.nasa_telemetry.ANALOGOS_START
ANALOGOS_FIN = NASA_INICIO - timedelta(days=1)
DIAS_SERIE_RECIENTE = 100  # igual que VENTANA_RECIENTE_DIAS del backend
TIMEOUT_CELDA_S = 240.0
REINTENTOS_RED = 3
TIMEOUT_SUELO_OFFLINE_S = 90.0
CONCURRENCIA_SUELO = 4
INTERVALO_SUELO_S = 13.0  # < 5 llamadas/minuto de ISRIC
ESPERAS_REINTENTO_S = (15.0, 30.0, 60.0, 310.0, 310.0)  # la última supera el corte automático (300 s)

# 15 features del modelo ML-7: 8 actuales + 4 del período crítico + dias_hasta_siembra + ONI + cultivo
FEATURE_COLUMNS_V2: list[str] = [
    "gwetroot_saturacion_pct",
    "gwettop_saturacion_pct",
    "tendencia_humedad_15d_pct",
    "anomalia_lluvia_90d_pct",
    "indice_aridez_evaporativa",
    "pendiente_terreno_pct",
    "elevacion_m",
    "textura_arcilla_pct",
    "frecuencia_tormentas_extremas",
    "frecuencia_estres_termico",
    "frecuencia_riesgo_helada",
    "lluvia_periodo_critico_mm",
    "dias_hasta_siembra",
    "oni_actual",
    "cultivo_candidato",
]
NUMERIC_FEATURES_V2: list[str] = FEATURE_COLUMNS_V2[:-1]

CULTIVOS_COBERTURA = ("vicia_cobertura", "avena_cobertura", "camelina")
PESO_COBERTURA_FAO = 0.5
PESO_WHAT_IF = 0.25
FRACCION_WHAT_IF = 0.15

ORIGEN_MAGYP = "magyp_real"
ORIGEN_COBERTURA = "fao_cobertura"
ORIGEN_WHAT_IF = "whatif_delta"


def split_de(anio: int) -> str | None:
    if anio in ANIOS_TRAIN:
        return "train"
    if anio in ANIOS_VAL:
        return "val"
    if anio in ANIOS_TEST:
        return "test"
    return None


# ---------------------------------------------------------------------------
# 1. MAGyP
# ---------------------------------------------------------------------------


def cargar_magyp(sin_red: bool = False) -> pd.DataFrame:
    if MAGYP_PAMPA.exists():
        return pd.read_csv(MAGYP_PAMPA, dtype={"departamento_id": str})
    if not MAGYP_CRUDO.exists():
        if sin_red:
            raise FileNotFoundError(f"Falta {MAGYP_PAMPA} y no se permite red")
        print(f"Descargando MAGyP → {MAGYP_CRUDO}")
        descargar_csv(MAGYP_CRUDO)
    crudo = pd.read_csv(MAGYP_CRUDO, encoding="utf-8", dtype={"departamento_id": str}, low_memory=False)
    df = filtrar_pampa(crudo)
    df.to_csv(MAGYP_PAMPA, index=False)
    return df


# ---------------------------------------------------------------------------
# 2. Departamentos: centroide + suelo + topografía (providers del backend)
# ---------------------------------------------------------------------------


def _leer_json(ruta: Path) -> dict[str, Any]:
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def _guardar_json(ruta: Path, datos: Any) -> None:
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ruta)


# Códigos INDEC que cambiaron después de la serie de MAGyP (georef → MAGyP).
# Chascomús pasó de 06217 a 06218 al crearse Lezama (06466); MAGyP mantiene el código viejo.
GEOREF_A_MAGYP: dict[str, str] = {"06218": "06217"}


async def cargar_centroides(ids: set[str], client: Any) -> dict[str, dict[str, Any]]:
    deps = _leer_json(DEPARTAMENTOS_JSON)
    faltan = ids - set(deps)
    if not faltan:
        return deps
    for prov in PROVINCIAS_PAMPA:
        resp = await client.get(
            "https://apis.datos.gob.ar/georef/api/departamentos",
            params={"provincia": prov, "max": 500, "campos": "id,nombre,centroide"},
            timeout=30.0,
        )
        resp.raise_for_status()
        for d in resp.json()["departamentos"]:
            dep_id = GEOREF_A_MAGYP.get(d["id"], d["id"])
            if dep_id in faltan:
                deps[dep_id] = {
                    "nombre": d["nombre"],
                    "provincia": PROVINCIAS_PAMPA[prov],
                    "lat": round(d["centroide"]["lat"], 5),
                    "lon": round(d["centroide"]["lon"], 5),
                }
    sin_match = sorted(ids - set(deps))
    if sin_match:
        print(f"AVISO: {len(sin_match)} departamentos MAGyP sin centroide en georef: {sin_match}")
    _guardar_json(DEPARTAMENTOS_JSON, deps)
    return deps


def _necesita_estaticos(dep: dict[str, Any]) -> bool:
    return "suelo" not in dep or "topografia" not in dep or dep["suelo"].get("reintentar") or dep["topografia"].get("reintentar")


async def completar_estaticos(deps: dict[str, dict[str, Any]], client: Any) -> None:
    """Suelo y topografía por centroide, reintentando los fallbacks transitorios.

    Offline se tolera la latencia de ISRIC (~30 s por consulta en horas pico): timeout largo y
    hasta ``CONCURRENCIA_SUELO`` consultas en vuelo, lanzadas cada ``INTERVALO_SUELO_S`` para no
    superar el límite de 5 llamadas/minuto. Producción no cambia (timeout de 8 s).
    """
    from providers import soilgrids
    from providers.soilgrids import SoilGridsUnavailable, fetch_perfil_suelo
    from providers.srtm import SrtmUnavailable, fetch_topografia

    soilgrids.TIMEOUT_S = TIMEOUT_SUELO_OFFLINE_S
    semaforo = asyncio.Semaphore(CONCURRENCIA_SUELO)
    ritmo = asyncio.Lock()
    pendientes = [i for i, d in deps.items() if _necesita_estaticos(d)]
    hechos = 0

    async def _paciente(dep, fetch, excepcion, flag: str, pausar: bool):
        resultado = None
        for espera in ESPERAS_REINTENTO_S:
            if pausar:
                async with ritmo:  # espacia los lanzamientos a ISRIC
                    await asyncio.sleep(INTERVALO_SUELO_S)
            try:
                resultado = await fetch(dep["lat"], dep["lon"], client=client)
                if not getattr(resultado, flag):
                    return resultado
            except excepcion as exc:
                print(f"    {dep['nombre']}: {exc} — reintento en {espera:.0f}s")
            await asyncio.sleep(espera)
        return resultado

    async def _uno(dep_id: str) -> None:
        nonlocal hechos
        dep = deps[dep_id]
        async with semaforo:
            perfil = await _paciente(dep, fetch_perfil_suelo, SoilGridsUnavailable, "reintentar_soilgrids", True)
        topo = await _paciente(dep, fetch_topografia, SrtmUnavailable, "reintentar_srtm", False)
        hechos += 1
        if perfil is None or topo is None:
            print(f"  estáticos {hechos}/{len(pendientes)} {dep['nombre']}: sin dato, se reintenta en la próxima corrida")
            return
        dep["suelo"] = {"arcilla_pct": perfil.arcilla_pct, "fuente": perfil.fuente, "reintentar": perfil.reintentar_soilgrids}
        dep["topografia"] = {
            "elevacion_m": topo.elevacion_m,
            "pendiente_terreno_pct": topo.pendiente_terreno_pct,
            "fuente": topo.fuente,
            "reintentar": topo.reintentar_srtm,
        }
        _guardar_json(DEPARTAMENTOS_JSON, deps)
        print(f"  estáticos {hechos}/{len(pendientes)} {dep['nombre']}: arcilla {perfil.arcilla_pct} ({perfil.fuente}), "
              f"pendiente {topo.pendiente_terreno_pct} ({topo.fuente})")

    print(f"Suelo y topografía: {len(pendientes)} departamentos por completar")
    await asyncio.gather(*(_uno(d) for d in pendientes))


# ---------------------------------------------------------------------------
# 3. NASA POWER por celda
# ---------------------------------------------------------------------------


def _ruta_celda(clave: str, directorio: Path = CACHE_NASA_DIR) -> Path:
    return directorio / f"{clave.replace(',', '_')}.json.gz"


def _leer_gz(ruta: Path) -> Any | None:
    from providers.nasa_power import dict_a_serie

    if not ruta.exists():
        return None
    with gzip.open(ruta, "rt", encoding="utf-8") as f:
        return dict_a_serie(json.load(f))


def leer_serie_celda(clave: str) -> Any | None:
    """Serie 2005-10 → 2025-12 de la celda, con 1981–2005 antepuesto si está descargado (ML-13)."""
    from providers.nasa_power import NasaPowerDailySeries

    serie = _leer_gz(_ruta_celda(clave))
    if serie is None:
        return None
    previa = _leer_gz(_ruta_celda(clave, CACHE_NASA_ANALOGOS_DIR))
    if previa is None:
        return serie
    series = {p: {**previa.series.get(p, {}), **vals} for p, vals in serie.series.items()}
    return NasaPowerDailySeries(
        lat=serie.lat, lon=serie.lon, start=previa.start, end=serie.end, series=series, elevacion_m=serie.elevacion_m
    )


async def descargar_celdas(deps: dict[str, dict[str, Any]], client: Any) -> None:
    from providers.cache import clave_celda_power
    from providers.nasa_power import fetch_daily_range, serie_a_dict

    CACHE_NASA_DIR.mkdir(parents=True, exist_ok=True)
    celdas: dict[str, tuple[float, float]] = {}
    for dep in deps.values():
        celdas.setdefault(clave_celda_power(dep["lat"], dep["lon"]), (dep["lat"], dep["lon"]))
    pendientes = [(k, v) for k, v in celdas.items() if not _ruta_celda(k).exists()]
    print(f"NASA POWER: {len(celdas)} celdas, {len(pendientes)} por descargar")
    for n, (clave, (lat, lon)) in enumerate(pendientes, 1):
        t0 = time.monotonic()
        for intento in range(REINTENTOS_RED):
            try:
                serie = await asyncio.wait_for(
                    fetch_daily_range(lat, lon, NASA_INICIO, NASA_FIN, NASA_PARAMETROS, client=client),
                    TIMEOUT_CELDA_S,
                )
                break
            except Exception as exc:  # noqa: BLE001 - red: reintentar y seguir
                print(f"  celda {clave} intento {intento + 1} falló: {exc}")
                await asyncio.sleep(10.0 * (intento + 1))
        else:
            continue
        tmp = _ruta_celda(clave).with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(serie_a_dict(serie), f)
        tmp.replace(_ruta_celda(clave))
        print(f"  celda {n}/{len(pendientes)} {clave} ({time.monotonic() - t0:.1f}s)")


async def descargar_celdas_analogos(deps: dict[str, dict[str, Any]], client: Any) -> None:
    """ML-13: 1981 → 2005-09 de cada celda (lluvia y temperaturas), para los años análogos."""
    from providers.cache import clave_celda_power
    from providers.nasa_power import fetch_daily_range, serie_a_dict
    from providers.nasa_telemetry import HIST_PARAMETROS

    CACHE_NASA_ANALOGOS_DIR.mkdir(parents=True, exist_ok=True)
    celdas: dict[str, tuple[float, float]] = {}
    for dep in deps.values():
        celdas.setdefault(clave_celda_power(dep["lat"], dep["lon"]), (dep["lat"], dep["lon"]))
    pendientes = [(k, v) for k, v in celdas.items() if not _ruta_celda(k, CACHE_NASA_ANALOGOS_DIR).exists()]
    print(f"NASA POWER 1981–2005 (análogos): {len(celdas)} celdas, {len(pendientes)} por descargar", flush=True)
    for n, (clave, (lat, lon)) in enumerate(pendientes, 1):
        t0 = time.monotonic()
        for intento in range(REINTENTOS_RED):
            try:
                serie = await asyncio.wait_for(
                    fetch_daily_range(lat, lon, ANALOGOS_INICIO, ANALOGOS_FIN, HIST_PARAMETROS, client=client),
                    TIMEOUT_CELDA_S,
                )
                break
            except Exception as exc:  # noqa: BLE001 - red: reintentar y seguir
                print(f"  celda {clave} intento {intento + 1} falló: {exc}", flush=True)
                await asyncio.sleep(10.0 * (intento + 1))
        else:
            continue
        destino = _ruta_celda(clave, CACHE_NASA_ANALOGOS_DIR)
        tmp = destino.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(serie_a_dict(serie), f)
        tmp.replace(destino)
        print(f"  análogos {n}/{len(pendientes)} {clave} ({time.monotonic() - t0:.1f}s)", flush=True)


# ---------------------------------------------------------------------------
# 4. Filas (funciones puras)
# ---------------------------------------------------------------------------


def recortar_serie(serie: Any, desde: date, hasta: date) -> Any:
    """Sub-serie [desde, hasta] (como la ventana reciente que consulta producción)."""
    from providers.nasa_power import NasaPowerDailySeries

    dias = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]
    return NasaPowerDailySeries(
        lat=serie.lat,
        lon=serie.lon,
        start=desde,
        end=hasta,
        series={p: {d: v.get(d) for d in dias if d in v} for p, v in serie.series.items()},
    )


def referencia_historica(serie: Any) -> Any:
    """Igual que el precálculo del backend: climatología 2006–2025 y análogos desde 1981 (ML-13)."""
    from providers.nasa_telemetry import ANALOGOS_START, HIST_END, HIST_PARAMETROS, calcular_referencia

    hist = recortar_serie(serie, max(ANALOGOS_START, serie.start), HIST_END)
    hist = type(hist)(
        lat=hist.lat, lon=hist.lon, start=hist.start, end=hist.end,
        series={p: hist.series[p] for p in HIST_PARAMETROS},
    )
    return calcular_referencia(hist)


def features_actuales_en(serie: Any, referencia: Any, corte: date, estaticos: dict[str, float]) -> dict[str, Any] | None:
    """Las 8 features actuales en ``corte`` (misma función que producción) + ONI publicado."""
    from providers.enso import oni_al
    from providers.features import features_actuales_desde_series
    from providers.nasa_power import NasaPowerUnavailable

    reciente = recortar_serie(serie, corte - timedelta(days=DIAS_SERIE_RECIENTE - 1), corte)
    try:
        actuales = features_actuales_desde_series(reciente, corte, referencia.clim_por_doy, **estaticos)
    except NasaPowerUnavailable:
        return None
    return {**actuales, "oni_actual": oni_al(corte)}


def filas_departamento(
    dep_id: str,
    serie: Any,
    estaticos: dict[str, float],
    labels: dict[tuple[str, int], float],
    anios: range,
    escenarios_out: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Filas reales (MAGyP) y de cobertura (sin label aún) de un departamento.

    Las features futuras son las **observadas en el período crítico** del cultivo en esa campaña.
    Si se pasa ``escenarios_out``, agrega las features críticas de cada cultivo y año histórico del
    departamento (para que ML-7 evalúe con años análogos, igual que producción).
    """
    from ml.escenarios import features_criticas

    referencia = referencia_historica(serie)
    cal_ev, cal_ll = referencia.calendario_eventos, referencia.calendario_lluvia
    criticas: dict[tuple[str, int], dict[str, Any] | None] = {}

    def _critica(cultivo: str, anio: int) -> dict[str, Any] | None:
        if (cultivo, anio) not in criticas:
            criticas[(cultivo, anio)] = features_criticas(cal_ev, cal_ll, cultivo, anio)
        return criticas[(cultivo, anio)]

    filas: list[dict[str, Any]] = []
    for anio in anios:
        for campana in ("invierno", "verano"):
            cultivos = cal.cultivos_de(campana)
            for t in cal.fechas_ventana(campana, anio):
                actuales = None
                for cultivo in cultivos:
                    if t > cal.fin_siembra(cultivo, anio):
                        continue
                    magyp = CULTIVO_MODELO_A_MAGYP.get(cultivo)
                    if magyp is not None and (magyp, anio) not in labels:
                        continue
                    critica = _critica(cultivo, anio)
                    if critica is None:
                        continue
                    if actuales is None:
                        actuales = features_actuales_en(serie, referencia, t, estaticos)
                        if actuales is None:
                            break
                    filas.append(
                        {
                            "departamento_id": dep_id,
                            "anio_campana": anio,
                            "campana": campana,
                            "fecha_t": t.isoformat(),
                            **actuales,
                            **critica,
                            "dias_hasta_siembra": cal.dias_hasta_siembra(cultivo, t, anio),
                            "cultivo_candidato": cultivo,
                            "cultivo_id": CROP_CATALOG[cultivo]["id"],
                            TARGET_COLUMN: labels[(magyp, anio)] if magyp is not None else np.nan,
                            "origen_muestra": ORIGEN_MAGYP if magyp is not None else ORIGEN_COBERTURA,
                        }
                    )
    if escenarios_out is not None:
        for cultivo in cal.CALENDARIO:
            for anio in sorted(cal_ev):
                c = _critica(cultivo, anio)
                if c is not None:
                    escenarios_out.append({"departamento_id": dep_id, "cultivo_candidato": cultivo, "anio": anio, **c})
    return filas


def asignar_pesos(df: pd.DataFrame) -> pd.Series:
    """1/n_ventanas por departamento × campaña × cultivo (cada campaña real pesa 1 en total)."""
    n = df.groupby(["departamento_id", "anio_campana", "cultivo_candidato"])["fecha_t"].transform("size")
    return 1.0 / n


def ajustar_mapeo_cuantiles(fao: np.ndarray, label: np.ndarray, n: int = 101) -> tuple[np.ndarray, np.ndarray]:
    q = np.linspace(0, 100, n)
    x = np.percentile(fao, q)
    y = np.percentile(label, q)
    x, idx = np.unique(x, return_index=True)  # interp necesita x estrictamente creciente
    return x, y[idx]


def aplicar_mapeo(valores: np.ndarray, mapeo: tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    return np.interp(valores, mapeo[0], mapeo[1])


def _fao(fila: dict[str, Any]) -> float:
    return compute_fao_hydroclimatic_score(fila, crop_name=fila["cultivo_candidato"], rng=None, noise_std=0.0)


def perturbar_what_if(fila: dict[str, Any], rng: np.random.Generator) -> dict[str, Any]:
    """Escenarios extremos de ML-1 (seco, húmedo, falsa recarga, secado rápido), sin tocar estáticos."""
    from providers.features import aplicar_topes

    f = dict(fila)
    modo = int(rng.integers(0, 4))
    if modo == 0:
        f["gwetroot_saturacion_pct"] = float(rng.uniform(12.0, 34.0))
        f["gwettop_saturacion_pct"] = float(np.clip(f["gwetroot_saturacion_pct"] + rng.normal(-4.0, 6.0), 8.0, 48.0))
        f["anomalia_lluvia_90d_pct"] = float(np.clip(f["anomalia_lluvia_90d_pct"] - rng.uniform(18.0, 45.0), -70.0, -15.0))
        f["indice_aridez_evaporativa"] = float(np.clip(f["indice_aridez_evaporativa"] * rng.uniform(0.45, 0.75), 0.12, 0.70))
        f["lluvia_periodo_critico_mm"] = float(f["lluvia_periodo_critico_mm"] * rng.uniform(0.4, 0.7))
        if f["campana"] == "verano":
            f["frecuencia_estres_termico"] = int(np.clip(f["frecuencia_estres_termico"] + rng.integers(3, 10), 4, 45))
    elif modo == 1:
        f["gwetroot_saturacion_pct"] = float(rng.uniform(80.0, 97.0))
        f["gwettop_saturacion_pct"] = float(np.clip(f["gwetroot_saturacion_pct"] + rng.normal(3.0, 4.0), 75.0, 99.0))
        f["anomalia_lluvia_90d_pct"] = float(np.clip(f["anomalia_lluvia_90d_pct"] + rng.uniform(20.0, 50.0), 15.0, 120.0))
        f["frecuencia_tormentas_extremas"] = int(np.clip(f["frecuencia_tormentas_extremas"] + rng.integers(1, 5), 1, 9))
        f["indice_aridez_evaporativa"] = float(np.clip(f["indice_aridez_evaporativa"] * rng.uniform(1.25, 1.80), 1.10, 2.60))
        f["lluvia_periodo_critico_mm"] = float(f["lluvia_periodo_critico_mm"] * rng.uniform(1.3, 1.8))
    elif modo == 2:
        f["gwetroot_saturacion_pct"] = float(rng.uniform(16.0, 34.5))
        f["gwettop_saturacion_pct"] = float(rng.uniform(60.0, 86.0))
        f["tendencia_humedad_15d_pct"] = float(rng.normal(3.0, 5.0))
    else:
        f["gwetroot_saturacion_pct"] = float(rng.uniform(22.0, 42.0))
        f["tendencia_humedad_15d_pct"] = float(rng.uniform(-28.0, -14.0))
    numericas = {k: f[k] for k in FEATURE_COLUMNS_V2[:-1] if k not in ("dias_hasta_siembra", "oni_actual")}
    f.update(aplicar_topes(numericas))
    return f


def construir_dataset(filas: list[dict[str, Any]], seed: int = SEED) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Split, pesos, mapeo FAO→MAGyP, filas de cobertura y What-If (solo train)."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(filas)
    df["split"] = df["anio_campana"].map(split_de)
    df = df[df["split"].notna()].copy()

    reales = df[df["origen_muestra"] == ORIGEN_MAGYP].copy()
    reales["sample_weight"] = asignar_pesos(reales)

    # Mapeo FAO → escala MAGyP por campaña, ajustado solo con train
    reales["fao_raw"] = [_fao(r) for r in reales.to_dict("records")]
    mapeos: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for campana, g in reales[reales["split"] == "train"].groupby("campana"):
        mapeos[campana] = ajustar_mapeo_cuantiles(g["fao_raw"].to_numpy(), g[TARGET_COLUMN].to_numpy())

    # Coberturas (FAO mapeado), solo train
    cob = df[(df["origen_muestra"] == ORIGEN_COBERTURA) & (df["split"] == "train")].copy()
    if len(cob):
        cob[TARGET_COLUMN] = [
            float(aplicar_mapeo(np.array([_fao(r)]), mapeos[r["campana"]])[0]) for r in cob.to_dict("records")
        ]
        cob["sample_weight"] = PESO_COBERTURA_FAO * asignar_pesos(cob)

    # What-If con label delta, solo train
    train_reales = reales[reales["split"] == "train"]
    n_wi = int(round(FRACCION_WHAT_IF * len(train_reales)))
    elegidas = train_reales.sample(n=n_wi, random_state=seed) if n_wi else train_reales.iloc[:0]
    wi_filas = []
    for r in elegidas.to_dict("records"):
        p = perturbar_what_if(r, rng)
        mapeo = mapeos[r["campana"]]
        delta = aplicar_mapeo(np.array([_fao(p)]), mapeo)[0] - aplicar_mapeo(np.array([r["fao_raw"]]), mapeo)[0]
        p[TARGET_COLUMN] = float(np.clip(r[TARGET_COLUMN] + delta, 0.0, 100.0))
        p["sample_weight"] = PESO_WHAT_IF * r["sample_weight"]
        p["origen_muestra"] = ORIGEN_WHAT_IF
        wi_filas.append(p)
    wi = pd.DataFrame(wi_filas)

    final = pd.concat([reales.drop(columns="fao_raw"), cob, wi.drop(columns="fao_raw", errors="ignore")], ignore_index=True)
    final[TARGET_COLUMN] = final[TARGET_COLUMN].astype(float).round(2)
    columnas = [
        "split", "origen_muestra", "departamento_id", "anio_campana", "campana", "fecha_t",
        *NUMERIC_FEATURES_V2, "cultivo_candidato", "cultivo_id", TARGET_COLUMN, "sample_weight",
    ]
    mapeo_meta = {c: {"fao": m[0].round(2).tolist(), "magyp": m[1].round(2).tolist()} for c, m in mapeos.items()}
    return final[columnas], mapeo_meta


def resumen(df: pd.DataFrame, labels: pd.DataFrame, deps: dict[str, Any]) -> dict[str, Any]:
    reales = df[df["origen_muestra"] == ORIGEN_MAGYP]
    sequias = {}
    for anio in (2008, 2017, 2022):
        g = reales[(reales["anio_campana"] == anio) & reales["cultivo_candidato"].isin(["maiz_temprano", "maiz_tardio", "soja_primera", "soja_segunda"])]
        sequias[f"{anio}/{anio + 1}"] = round(float(np.average(g[TARGET_COLUMN], weights=g["sample_weight"])), 1) if len(g) else None
    fuentes_suelo = pd.Series([d.get("suelo", {}).get("fuente") for d in deps.values()]).value_counts().to_dict()
    fuentes_topo = pd.Series([d.get("topografia", {}).get("fuente") for d in deps.values()]).value_counts().to_dict()
    return {
        "version": "ml6-magyp-v1",
        "features": FEATURE_COLUMNS_V2,
        "target": TARGET_COLUMN,
        "splits": {"train": [ANIOS_TRAIN.start, ANIOS_TRAIN.stop - 1], "val": [ANIOS_VAL.start, ANIOS_VAL.stop - 1], "test": [ANIOS_TEST.start, ANIOS_TEST.stop - 1]},
        "filas": df.groupby(["split", "origen_muestra"]).size().unstack(fill_value=0).to_dict(orient="index"),
        "campanas_reales": reales.groupby("split")[["departamento_id", "anio_campana", "cultivo_candidato"]].apply(lambda g: len(g.drop_duplicates())).to_dict(),
        "departamentos": int(reales["departamento_id"].nunique()),
        "labels_magyp": int(len(labels)),
        "label_por_cultivo": reales.groupby("cultivo_candidato")[TARGET_COLUMN].describe().round(1).to_dict(orient="index"),
        "label_medio_por_split": reales.groupby("split")[TARGET_COLUMN].mean().round(1).to_dict(),
        "sanidad_sequias_maiz_soja": sequias,
        "fuentes_suelo": fuentes_suelo,
        "fuentes_topografia": fuentes_topo,
    }


# ---------------------------------------------------------------------------
# 5. Orquestación
# ---------------------------------------------------------------------------


async def descargas(ids: set[str]) -> dict[str, dict[str, Any]]:
    import httpx

    async with httpx.AsyncClient() as client:
        deps = await cargar_centroides(ids, client)
        resultados = await asyncio.gather(
            completar_estaticos(deps, client),
            descargar_celdas(deps, client),
            descargar_celdas_analogos(deps, client),
            return_exceptions=True,
        )
        for r in resultados:
            if isinstance(r, BaseException):
                print(f"AVISO: una descarga terminó con error (se reanuda en la próxima corrida): {r!r}")
    return deps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--solo-descargas", action="store_true")
    parser.add_argument("--sin-red", action="store_true")
    args = parser.parse_args()

    from providers.cache import clave_celda_power

    magyp = cargar_magyp(sin_red=args.sin_red)
    labels = calcular_labels(magyp, ANIOS_TENDENCIA)
    ids = set(labels["departamento_id"])
    print(f"MAGyP: {len(labels)} labels en {len(ids)} departamentos")

    deps = _leer_json(DEPARTAMENTOS_JSON) if args.sin_red else asyncio.run(descargas(ids))
    if args.solo_descargas:
        return 0

    por_dep = {
        dep_id: {(r.cultivo_magyp, int(r.anio_campana)): float(r.puntaje) for r in g.itertuples()}
        for dep_id, g in labels.groupby("departamento_id")
    }
    filas: list[dict[str, Any]] = []
    escenarios: list[dict[str, Any]] = []
    series: dict[str, Any] = {}
    omitidos = []
    t0 = time.monotonic()
    for n, dep_id in enumerate(sorted(ids), 1):
        dep = deps.get(dep_id)
        if dep is None or dep.get("suelo", {}).get("arcilla_pct") is None or "topografia" not in dep:
            omitidos.append(dep_id)
            continue
        clave = clave_celda_power(dep["lat"], dep["lon"])
        if clave not in series:
            series[clave] = leer_serie_celda(clave)
        if series[clave] is None:
            omitidos.append(dep_id)
            continue
        estaticos = {
            "pendiente_terreno_pct": dep["topografia"]["pendiente_terreno_pct"],
            "elevacion_m": dep["topografia"]["elevacion_m"],
            "textura_arcilla_pct": dep["suelo"]["arcilla_pct"],
        }
        filas.extend(
            filas_departamento(
                dep_id, series[clave], estaticos, por_dep[dep_id], range(ANIOS_TRAIN.start, ANIOS_TEST.stop), escenarios
            )
        )
        if n % 20 == 0:
            print(f"  filas: {n}/{len(ids)} departamentos ({time.monotonic() - t0:.0f}s)")
    if omitidos:
        print(f"AVISO: {len(omitidos)} departamentos sin datos completos (omitidos): {omitidos}")

    df, mapeos = construir_dataset(filas)
    pd.DataFrame(escenarios).to_csv(SALIDA_ESCENARIOS, index=False, compression="gzip")
    for split, g in df.groupby("split"):
        g.drop(columns="split").to_csv(SALIDA_SPLIT.with_name(SALIDA_SPLIT.name.format(split=split)), index=False, compression="gzip")
    meta = resumen(df, labels, deps)
    meta["mapeo_fao_a_magyp"] = mapeos
    meta["departamentos_omitidos"] = omitidos
    _guardar_json(METADATA_JSON, meta)
    print(json.dumps({k: meta[k] for k in ("filas", "departamentos", "label_medio_por_split", "sanidad_sequias_maiz_soja")}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
