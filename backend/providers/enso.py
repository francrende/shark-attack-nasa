"""Índice ENSO (ONI de NOAA CPC) para el modelo de ML (ML-7).

El ONI (Oceanic Niño Index) es la anomalía de temperatura del Pacífico ecuatorial
(Niño 3.4) en estaciones móviles de 3 meses. Es la principal señal de predictibilidad
estacional para la región pampeana: La Niña (ONI ≤ −0,5) suele traer sequía y El Niño
(ONI ≥ +0,5) años húmedos.

- ``oni_al(t)``: el último ONI **publicado** al decidir en ``t``. NOAA publica la estación
  terminada a comienzos del mes siguiente, así que se toma la estación que termina en el mes
  de ``t − 40 días`` (sin fuga de información en el entrenamiento).
- ``pesos_por_fase`` (ML-12): años análogos = los de la misma fase ENSO (La Niña / Neutro /
  El Niño) que la actual, con el mismo peso; el resto queda afuera (peso 0).
  Si la fase tiene pocos años, se completa con los de ONI más parecido.
- ``pesos_por_oni``: pesos gaussianos según el parecido de ONI (ML-7; ya no se usa en producción).

Funciones puras sobre una tabla ``{(año, mes_fin): anomalía}``. La tabla sale de
``data/oni.ascii.txt`` (copia empaquetada) o de ``actualizar_oni`` (descarga, opcional).
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from pathlib import Path

URL_ONI = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
RUTA_ONI = Path(__file__).resolve().parent / "data" / "oni.ascii.txt"
ESTACIONES = ("DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ")
DESFASE_PUBLICACION_DIAS = 40
SIGMA_PESOS = 0.5  # ancho de la ponderación de años análogos (unidades de ONI)

TablaOni = dict[tuple[int, int], float]


def parsear_oni(texto: str) -> TablaOni:
    """``{(año, mes en que termina la estación): anomalía}``. NDJ de Y termina en enero de Y+1."""
    tabla: TablaOni = {}
    for linea in texto.splitlines():
        partes = linea.split()
        if len(partes) != 4 or partes[0] not in ESTACIONES:
            continue
        fin = ESTACIONES.index(partes[0]) + 2  # DJF → 2 (febrero), …, NDJ → 13
        anio = int(partes[1]) + (1 if fin > 12 else 0)
        tabla[(anio, (fin - 1) % 12 + 1)] = float(partes[3])
    return tabla


_tabla: TablaOni | None = None


def tabla_oni(ruta: Path = RUTA_ONI) -> TablaOni:
    global _tabla
    if _tabla is None:
        _tabla = parsear_oni(ruta.read_text(encoding="utf-8"))
    return _tabla


def configurar_tabla(tabla: TablaOni | None) -> None:
    """Reemplaza la tabla en memoria (tests o actualización en caliente)."""
    global _tabla
    _tabla = tabla


def oni_al(t: date, tabla: TablaOni | None = None) -> float:
    """Último ONI publicado al decidir en ``t``. Si falta, usa el último disponible anterior."""
    tabla = tabla_oni() if tabla is None else tabla
    ref = t - timedelta(days=DESFASE_PUBLICACION_DIAS)
    anio, mes = ref.year, ref.month
    for _ in range(24):
        if (anio, mes) in tabla:
            return tabla[(anio, mes)]
        anio, mes = (anio, mes - 1) if mes > 1 else (anio - 1, 12)
    raise KeyError(f"Sin ONI publicado hasta {ref}")


def oni_mismo_dia(t: date, anios: list[int], tabla: TablaOni | None = None) -> dict[int, float]:
    """ONI publicado en la misma fecha (día/mes de ``t``) de cada año análogo."""
    out = {}
    for anio in anios:
        try:
            dia = date(anio, t.month, t.day)
        except ValueError:  # 29/2
            dia = date(anio, 2, 28)
        out[anio] = oni_al(dia, tabla)
    return out


def pesos_por_oni(oni_actual: float, oni_analogos: dict[int, float], sigma: float = SIGMA_PESOS) -> dict[int, float]:
    """Peso gaussiano por año: los años con fase ENSO parecida pesan más (nunca 0)."""
    return {a: math.exp(-0.5 * ((v - oni_actual) / sigma) ** 2) + 1e-6 for a, v in oni_analogos.items()}


UMBRAL_FASE = 0.5  # NOAA: El Niño si ONI >= +0,5; La Niña si ONI <= -0,5
MIN_ANIOS_ANALOGOS = 5
NOMBRE_FASE = {"nina": "La Niña", "neutro": "ENSO neutro", "nino": "El Niño"}


def fase_enso(oni: float) -> str:
    """``"nina"``, ``"neutro"`` o ``"nino"`` según el ONI."""
    if oni >= UMBRAL_FASE:
        return "nino"
    if oni <= -UMBRAL_FASE:
        return "nina"
    return "neutro"


def pesos_por_fase(oni_actual: float, oni_analogos: dict[int, float]) -> dict[int, float]:
    """Peso 1 a los años con la misma fase ENSO que hoy y 0 al resto (ML-12).

    Con el peso gaussiano, un ONI extremo dejaba todo el peso en uno o dos años (N efectivo 1,5
    con ONI +2,5) mientras el conteo de años desfavorables y el peor escenario seguían usando
    todos los años, incluso los de la fase opuesta. Filtrar por fase hace que promedio, P10,
    conteo y peor escenario salgan del mismo conjunto. Si la fase tiene menos de
    ``MIN_ANIOS_ANALOGOS`` años, se completa hasta ese mínimo con los de ONI más parecido.
    """
    fase = fase_enso(oni_actual)
    pesos = {a: 1.0 if fase_enso(v) == fase else 0.0 for a, v in oni_analogos.items()}
    faltan = MIN_ANIOS_ANALOGOS - int(sum(pesos.values()))
    if faltan > 0:
        otros = sorted((a for a, p in pesos.items() if p == 0.0), key=lambda a: (abs(oni_analogos[a] - oni_actual), a))
        for a in otros[:faltan]:
            pesos[a] = 1.0
    return pesos


async def actualizar_oni(client, ruta: Path = RUTA_ONI, timeout_s: float = 20.0) -> TablaOni:  # pragma: no cover - red
    """Descarga el ONI vigente, lo guarda en ``ruta`` y lo deja activo en memoria."""
    resp = await client.get(URL_ONI, timeout=timeout_s)
    resp.raise_for_status()
    tabla = parsear_oni(resp.text)
    if tabla:
        ruta.write_text(resp.text, encoding="utf-8")
        configurar_tabla(tabla)
    return tabla
