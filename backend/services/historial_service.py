"""Historial real de un lote por campaña agrícola (BACK-31): lluvia, agua en raíces, rinde de la
zona (MAGyP) y cosechas guardadas del campo.

- **Campaña agrícola** = julio del año ``Y`` a junio de ``Y+1`` (rótulo "2022/23"), desde 2006/07.
- **Lluvia** (mm) y **agua en raíces** (``GWETROOT``) salen de NASA POWER: la serie mensual para los
  años cerrados (una consulta, en caché persistente) y la diaria para el año pasado y el actual,
  que NASA todavía no publica como mensuales.
- **Lo normal** es el promedio de las campañas completas del período.
"""

from __future__ import annotations

import asyncio
import calendar
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from typing import Any

import httpx

from ml import calendario_siembra as cal
from ml.departamentos import departamento_mas_cercano, departamento_por_codigo
from ml.rinde import rinde_zona_por_campana
from providers.cache import clave_celda_power, obtener_cache
from providers.nasa_power import fetch_daily_range, fetch_monthly_range

ANIO_DESDE = 2006
PARAMS = ["PRECTOTCORR_SUM", "GWETROOT"]
PARAMS_DIARIOS = ["PRECTOTCORR", "GWETROOT"]
ESPACIO_MENSUAL = "nasa_mensual"
ESPACIO_DIARIO = "nasa_historial_diario"
TTL_DIARIO_S = 6 * 3600.0
# Un mes cuenta como completo si tiene dato válido en al menos este porcentaje de los días.
MIN_DIAS_VALIDOS_MES = 0.8
# Días mínimos con dato para promediar el agua en raíces de un mes parcial.
MIN_DIAS_AGUA = 10
MESES_CAMPANA: tuple[tuple[int, int], ...] = tuple((0, m) for m in range(7, 13)) + tuple((1, m) for m in range(1, 7))

Mensual = dict[tuple[int, int], dict[str, float | None]]


def anio_campana_de_fecha(fecha: date) -> int:
    """Campaña agrícola (julio a junio) a la que pertenece una fecha."""
    return fecha.year if fecha.month >= 7 else fecha.year - 1


def etiqueta(anio: int) -> str:
    return f"{anio}/{(anio + 1) % 100:02d}"


# ---------------------------------------------------------------------------
# Datos de NASA POWER
# ---------------------------------------------------------------------------


def _mensual_a_json(m: Mapping[str, Mapping[tuple[int, int], float | None]]) -> dict[str, dict[str, float | None]]:
    return {p: {f"{a}{mes:02d}": v for (a, mes), v in serie.items()} for p, serie in m.items()}


def _json_a_mensual(d: Mapping[str, Mapping[str, float | None]]) -> dict[str, dict[tuple[int, int], float | None]]:
    return {p: {(int(k[:4]), int(k[4:])): v for k, v in serie.items()} for p, serie in d.items()}


def agregar_diario(serie: Any) -> Mensual:
    """Lluvia (suma) y agua en raíces (promedio) por mes, solo con meses con datos suficientes."""
    por_mes: dict[tuple[int, int], dict[str, list[float]]] = {}
    dia = serie.start
    while dia <= serie.end:
        clave = (dia.year, dia.month)
        for p in PARAMS_DIARIOS:
            v = serie.series.get(p, {}).get(dia)
            if v is not None:
                por_mes.setdefault(clave, {}).setdefault(p, []).append(float(v))
        dia += timedelta(days=1)
    salida: Mensual = {}
    for clave, valores in por_mes.items():
        lluvias = valores.get("PRECTOTCORR", [])
        gw = valores.get("GWETROOT", [])
        # Días del mes calendario (no del rango pedido): el mes en curso nunca cuenta como completo.
        total = calendar.monthrange(*clave)[1]
        salida[clave] = {
            # Mes en curso o con datos faltantes: se informa la lluvia acumulada hasta el último dato.
            "lluvia_mm": round(sum(lluvias), 1) if lluvias else None,
            "lluvia_completa": len(lluvias) >= MIN_DIAS_VALIDOS_MES * total,
            # El agua en raíces es un promedio: un mes parcial con suficientes días sirve (el mes en curso).
            "agua_raices": (sum(gw) / len(gw)) if len(gw) >= min(MIN_DIAS_VALIDOS_MES * total, MIN_DIAS_AGUA) else None,
        }
    return salida


async def obtener_mensual(lat: float, lon: float, hoy: date, client: httpx.AsyncClient) -> Mensual:
    """Meses desde julio de 2006 hasta hoy: mensual de NASA para años cerrados, diario para el resto."""
    cache = obtener_cache()
    celda = clave_celda_power(lat, lon)
    hasta_mensual = hoy.year - 2  # el año pasado puede no estar publicado como mensual todavía
    clave_m = f"{celda}|{ANIO_DESDE}-{hasta_mensual}"
    desde_diario = date(hoy.year - 1, 1, 1)
    clave_d = f"{celda}|{desde_diario.isoformat()}|{hoy.isoformat()}"

    async def _mensual() -> dict[str, dict[tuple[int, int], float | None]]:
        cacheado = cache.get(ESPACIO_MENSUAL, clave_m)
        if cacheado is not None:
            return _json_a_mensual(cacheado)
        datos = await fetch_monthly_range(lat, lon, ANIO_DESDE, hasta_mensual, PARAMS, client=client)
        cache.set(ESPACIO_MENSUAL, clave_m, _mensual_a_json(datos))
        return datos

    async def _diario() -> Any:
        from providers.nasa_power import dict_a_serie, serie_a_dict

        cacheado = cache.get(ESPACIO_DIARIO, clave_d)
        if cacheado is not None:
            return dict_a_serie(cacheado)
        serie = await fetch_daily_range(lat, lon, desde_diario, hoy, PARAMS_DIARIOS, client=client)
        cache.set(ESPACIO_DIARIO, clave_d, serie_a_dict(serie), TTL_DIARIO_S)
        return serie

    mensual, diario = await asyncio.gather(_mensual(), _diario())
    salida: Mensual = {}
    for clave, lluvia in mensual.get("PRECTOTCORR_SUM", {}).items():
        gw = mensual.get("GWETROOT", {}).get(clave)
        salida[clave] = {"lluvia_mm": lluvia, "lluvia_completa": lluvia is not None, "agua_raices": gw}
    salida.update(agregar_diario(diario))
    return salida


# ---------------------------------------------------------------------------
# Agregado por campaña (puro, sin E/S)
# ---------------------------------------------------------------------------


def campanas_desde_mensual(meses: Mensual, hoy: date) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Lluvia y agua en raíces por campaña agrícola + los valores normales del lote."""
    actual = anio_campana_de_fecha(hoy)
    filas: list[dict[str, Any]] = []
    for anio in range(ANIO_DESDE, actual + 1):
        lluvia = 0.0
        meses_lluvia = 0
        agua: list[tuple[tuple[int, int], float]] = []
        for desplazamiento, mes in MESES_CAMPANA:
            clave = (anio + desplazamiento, mes)
            dato = meses.get(clave)
            if not dato:
                continue
            if dato.get("lluvia_mm") is not None:
                lluvia += float(dato["lluvia_mm"])
                meses_lluvia += 1 if dato.get("lluvia_completa") else 0
            if dato.get("agua_raices") is not None:
                agua.append((clave, float(dato["agua_raices"])))
        completa = meses_lluvia == 12 and anio < actual
        mas_seco = min(agua, key=lambda x: x[1]) if agua else None
        filas.append({
            "anio": anio,
            "etiqueta": etiqueta(anio),
            "completa": completa,
            "meses_con_dato": meses_lluvia,
            "lluvia_mm": round(lluvia) if meses_lluvia or lluvia else None,
            "agua_raices_promedio_pct": round(100 * sum(v for _, v in agua) / len(agua)) if agua else None,
            "mes_mas_seco": f"{mas_seco[0][0]}-{mas_seco[0][1]:02d}" if mas_seco else None,
            "agua_raices_mes_mas_seco_pct": round(100 * mas_seco[1]) if mas_seco else None,
        })

    completas = [f for f in filas if f["completa"]]
    lluvia_normal = round(sum(f["lluvia_mm"] for f in completas) / len(completas)) if completas else None
    agua_normal = (
        round(sum(f["agua_raices_promedio_pct"] for f in completas if f["agua_raices_promedio_pct"] is not None)
              / max(1, sum(1 for f in completas if f["agua_raices_promedio_pct"] is not None)))
        if completas else None
    )
    # Normal de cada mes calendario, para comparar el mes más seco contra lo habitual de ese mes.
    por_mes: dict[int, list[float]] = {}
    for (a, m), dato in meses.items():
        if dato.get("agua_raices") is not None and a >= ANIO_DESDE:
            por_mes.setdefault(m, []).append(float(dato["agua_raices"]))
    for f in filas:
        f["lluvia_comparada_hasta"] = None
        if f["lluvia_mm"] is not None and lluvia_normal and f["completa"]:
            f["lluvia_vs_normal_pct"] = round((f["lluvia_mm"] / lluvia_normal - 1) * 100)
        elif not f["completa"]:
            # Campaña en curso: se compara solo con los meses ya completos, contra lo normal de esos
            # mismos meses en las campañas completas ("−20% de julio a octubre").
            f["lluvia_vs_normal_pct"], f["lluvia_comparada_hasta"] = _comparar_parcial(meses, f["anio"], completas)
        else:
            f["lluvia_vs_normal_pct"] = None
        if f["mes_mas_seco"]:
            valores = por_mes.get(int(f["mes_mas_seco"][5:]), [])
            f["agua_raices_mes_mas_seco_normal_pct"] = round(100 * sum(valores) / len(valores)) if valores else None
        else:
            f["agua_raices_mes_mas_seco_normal_pct"] = None
    return filas, {"lluvia_mm": lluvia_normal, "agua_raices_pct": agua_normal, "campanas_completas": len(completas)}


def _comparar_parcial(
    meses: Mensual, anio: int, completas: Sequence[Mapping[str, Any]]
) -> tuple[int | None, str | None]:
    """(desvío % de la lluvia de los meses completos, último mes comparado "AAAA-MM")."""
    claves: list[tuple[int, int]] = []
    for desplazamiento, mes in MESES_CAMPANA:
        dato = meses.get((anio + desplazamiento, mes))
        if not dato or not dato.get("lluvia_completa") or dato.get("lluvia_mm") is None:
            break  # solo meses completos y consecutivos desde julio
        claves.append((anio + desplazamiento, mes))
    if not claves or not completas:
        return None, None
    actual = sum(float(meses[c]["lluvia_mm"]) for c in claves)
    normales = []
    for f in completas:
        suma = 0.0
        for (a, m) in claves:
            dato = meses.get((f["anio"] + (a - anio), m))
            if not dato or dato.get("lluvia_mm") is None:
                break
            suma += float(dato["lluvia_mm"])
        else:
            normales.append(suma)
    if not normales or sum(normales) <= 0:
        return None, None
    normal = sum(normales) / len(normales)
    ultimo = claves[-1]
    return round((actual / normal - 1) * 100), f"{ultimo[0]}-{ultimo[1]:02d}"


def cosechas_por_campana(campanas: Sequence[Mapping[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    """Campañas guardadas del lote agrupadas por campaña agrícola (por fecha de siembra)."""
    salida: dict[int, list[dict[str, Any]]] = {}
    for c in campanas:
        try:
            siembra = date.fromisoformat(str(c["fecha_inicio"])[:10])
        except (KeyError, ValueError):
            continue
        anio = cal.anio_campana(siembra)
        salida.setdefault(anio, []).append({
            "id": str(c.get("id")),
            "cultivo": str(c.get("cultivo")),
            "fecha_siembra": siembra,
            "fecha_cosecha": c.get("fecha_fin"),
            "rinde_kg_ha": c.get("rinde_kg_ha"),
            "en_curso": not c.get("fecha_fin"),
        })
    for lista in salida.values():
        lista.sort(key=lambda x: x["fecha_siembra"])
    return salida


def _departamento(lat: float, lon: float, campo: Mapping[str, Any] | None) -> dict[str, Any] | None:
    codigo = (campo or {}).get("departamento_codigo")
    if codigo:
        dep = departamento_por_codigo(str(codigo), lat, lon)
        if dep is not None:
            return dep
    return departamento_mas_cercano(lat, lon)


async def obtener_historial(
    lat: float,
    lon: float,
    *,
    hoy: date,
    campo: Mapping[str, Any] | None = None,
    campanas_lote: Sequence[Mapping[str, Any]] | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Respuesta de ``GET /api/v1/historial`` (``HistorialResponse``)."""
    if client is None:
        async with httpx.AsyncClient() as propio:
            meses = await obtener_mensual(lat, lon, hoy, propio)
    else:
        meses = await obtener_mensual(lat, lon, hoy, client)
    filas, normales = campanas_desde_mensual(meses, hoy)
    dep = _departamento(lat, lon, campo)
    zona = rinde_zona_por_campana(dep["codigo"]) if dep else {}
    lote = cosechas_por_campana(campanas_lote or [])
    advertencias = [
        "Lluvia y agua en raíces de NASA POWER: clima regional (~50 km), no medido en el lote.",
    ]
    if dep is None:
        advertencias.append("El lote está fuera de la zona con datos de rinde (región pampeana).")
    if campanas_lote is None:
        advertencias.append("Iniciá sesión y guardá el lote para ver sus cosechas.")
    for f in filas:
        f["rinde_zona"] = zona.get(f["anio"], [])
        f["cosechas_lote"] = lote.get(f["anio"], [])
    return {
        "ubicacion": {"lat": lat, "lon": lon},
        "departamento_referencia": dep,
        "normales": normales,
        "campanas": filas,
        "advertencias": advertencias,
    }
