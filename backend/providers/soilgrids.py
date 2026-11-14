"""Provider de ISRIC SoilGrids v2 (BACK-3).

Devuelve el perfil edáfico 0–30 cm (ponderado por espesor) de un punto, con una cascada
de respaldo:

1. Punto pedido.
2. Si el píxel no tiene dato (``null``: zona urbana / agua): 4 vecinos a ~500 m (N, S, E, O).
3. Si hay timeout / 429 / 5xx / red, o los vecinos tampoco tienen dato: arcilla de la
   localidad GeoINTA más cercana (≤ 100 km), con advertencia visible.
4. Fuera de 100 km: ``SoilGridsUnavailable`` (el router lo mapea a 503).

Respeta el límite de ISRIC (5 llamadas/minuto por IP) con un limitador de ventana
deslizante, y cachea por coordenada redondeada (~100 m) sin vencimiento.

BACK-4: corte automático (1 timeout/429 → 5 min sin llamar a ISRIC), caché vía la interfaz
enchufable de ``providers.cache``, lotes de ejemplo precargados (``fuente="precache"``) y
marca ``reintentar_soilgrids`` en los fallbacks por fallas transitorias (nunca se cachean).
"""

from __future__ import annotations

import asyncio
import json
import math
import time
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

from providers.cache import clave_coordenada, obtener_cache

BASE_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
PROPIEDADES = ["clay", "sand", "silt", "soc", "phh2o"]
PROFUNDIDADES: dict[str, int] = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}  # espesor en cm
D_FACTOR_DEFAULT = 10.0
TIMEOUT_S = 8.0
OFFSET_VECINO_GRADOS = 0.0045  # ~500 m en latitud
RADIO_FALLBACK_KM = 100.0
LIMITE_LLAMADAS = 5
VENTANA_LIMITE_S = 60.0
CACHE_DECIMALES = 3  # ~100 m (ver providers.cache.clave_coordenada)
ESPACIO_SUELO = "suelo"
DURACION_CORTE_S = 300.0
RADIO_LOTE_EJEMPLO_KM = 0.1
RUTA_LOTES_EJEMPLO = Path(__file__).parent / "data" / "suelo_lotes_ejemplo.json"

ADV_FALLBACK = (
    "Textura estimada regionalmente, carbono orgánico no disponible: "
    "el ajuste de rotación por carbono no se aplicó."
)
ADV_VECINO = (
    "Perfil de suelo tomado a ~500 m del punto marcado "
    "(sin dato en SoilGrids: zona urbana o espejo de agua)."
)
ADV_SIN_SOC = "Carbono orgánico no disponible: el ajuste de rotación por carbono no se aplicó."
ADV_SIN_PH = "pH no disponible: el ajuste de rotación por pH no se aplicó."
ADV_SIN_TEXTURA = "Arena/limo no disponibles: no se pudo determinar la clase textural."

Fuente = Literal["isric_soilgrids_v2", "isric_soilgrids_v2_vecino", "precache", "fallback_regional"]

# Copia de AGRO_LOCATIONS (backend/ml/generate_dataset.py): arcilla de respaldo calibrada
# con Cartas de Suelo GeoINTA. Se copia (no se importa) para no acoplarse al track de ML.
LOCALIDADES_GEOINTA: tuple[dict[str, Any], ...] = (
    {"id": "pergamino_ba", "nombre": "Pergamino (Pampa Ondulada)", "lat": -33.89, "lon": -60.57, "arcilla_pct": 25.4},
    {"id": "venado_tuerto_sf", "nombre": "Venado Tuerto (Sur Santa Fe)", "lat": -33.75, "lon": -61.97, "arcilla_pct": 23.8},
    {"id": "marcos_juarez_cba", "nombre": "Marcos Juárez (Sudeste Córdoba)", "lat": -32.70, "lon": -62.10, "arcilla_pct": 24.5},
    {"id": "rio_cuarto_cba", "nombre": "Río Cuarto (Suroeste Córdoba)", "lat": -33.12, "lon": -64.35, "arcilla_pct": 17.2},
    {"id": "trenque_lauquen_ba", "nombre": "Trenque Lauquen (Pampa Arenosa)", "lat": -35.97, "lon": -62.73, "arcilla_pct": 15.8},
    {"id": "tandil_ba", "nombre": "Tandil (Pampa Serrana / Sudeste)", "lat": -37.32, "lon": -59.13, "arcilla_pct": 27.6},
    {"id": "balcarce_ba", "nombre": "Balcarce (Sudeste Bonaerense)", "lat": -37.85, "lon": -58.26, "arcilla_pct": 26.8},
    {"id": "tres_arroyos_ba", "nombre": "Tres Arroyos (Sur Bonaerense / Fina)", "lat": -38.37, "lon": -60.28, "arcilla_pct": 24.9},
    {"id": "chascomus_ba", "nombre": "Chascomús (Cuenca del Salado)", "lat": -35.57, "lon": -58.01, "arcilla_pct": 33.5},
    {"id": "parana_er", "nombre": "Paraná (Lomadas Entrerrianas)", "lat": -31.74, "lon": -60.51, "arcilla_pct": 37.2},
    {"id": "rafaela_sf", "nombre": "Rafaela (Centro Santa Fe)", "lat": -31.25, "lon": -61.49, "arcilla_pct": 28.4},
    {"id": "general_pico_lp", "nombre": "General Pico (Noreste La Pampa)", "lat": -35.66, "lon": -63.75, "arcilla_pct": 14.9},
    {"id": "junin_ba", "nombre": "Junín (Noroeste Bonaerense)", "lat": -34.58, "lon": -60.95, "arcilla_pct": 21.6},
    {"id": "azul_ba", "nombre": "Azul (Centro Bonaerense)", "lat": -36.78, "lon": -59.86, "arcilla_pct": 29.8},
    {"id": "victoria_er", "nombre": "Victoria (Sur Entre Ríos - Vertisoles)", "lat": -32.62, "lon": -60.15, "arcilla_pct": 38.5},
)


class SoilGridsUnavailable(Exception):
    """No hay dato de SoilGrids ni localidad de respaldo a menos de 100 km."""


@dataclass(frozen=True)
class PerfilSueloSatelital:
    arcilla_pct: float | None
    arena_pct: float | None
    limo_pct: float | None
    carbono_organico_g_kg: float | None
    ph: float | None
    textura_predominante: str | None
    fuente: Fuente
    distancia_fuente_km: float
    localidad_fallback: str | None
    advertencias: tuple[str, ...]
    # True si es un dato aproximado por una falla transitoria (corte, timeout, 429, 5xx, red,
    # límite de llamadas): quien lo persista debe reintentar SoilGrids al reabrir el campo.
    reintentar_soilgrids: bool = False


def perfil_a_dict(perfil: PerfilSueloSatelital) -> dict[str, Any]:
    datos = asdict(perfil)
    datos["advertencias"] = list(perfil.advertencias)
    return datos


def dict_a_perfil(datos: dict[str, Any]) -> PerfilSueloSatelital:
    return PerfilSueloSatelital(**{**datos, "advertencias": tuple(datos.get("advertencias", ()))})


# ---------------------------------------------------------------------------
# Limitador de tasa, corte automático y estado del módulo
# ---------------------------------------------------------------------------


class LimitadorTasa:
    """Ventana deslizante: como máximo ``max_llamadas`` en los últimos ``ventana_s`` segundos."""

    def __init__(
        self,
        max_llamadas: int = LIMITE_LLAMADAS,
        ventana_s: float = VENTANA_LIMITE_S,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_llamadas = max_llamadas
        self.ventana_s = ventana_s
        self._reloj = reloj
        self._marcas: deque[float] = deque()

    def _purgar(self, ahora: float) -> None:
        while self._marcas and ahora - self._marcas[0] >= self.ventana_s:
            self._marcas.popleft()

    def reservar_hasta(self, cantidad: int) -> int:
        """Reserva hasta ``cantidad`` llamadas y devuelve cuántas se concedieron (0..cantidad)."""
        ahora = self._reloj()
        self._purgar(ahora)
        concedidas = max(0, min(cantidad, self.max_llamadas - len(self._marcas)))
        self._marcas.extend([ahora] * concedidas)
        return concedidas


class CorteAutomatico:
    """Circuit breaker: 1 timeout/429 corta ``duracion_s``; luego permite 1 llamada de prueba."""

    def __init__(self, duracion_s: float = DURACION_CORTE_S, reloj: Callable[[], float] = time.monotonic) -> None:
        self.duracion_s = duracion_s
        self._reloj = reloj
        self._abierto_hasta: float | None = None
        self._prueba_en_curso = False

    @property
    def cortado(self) -> bool:
        return self._abierto_hasta is not None

    def permite_llamada(self) -> bool:
        if self._abierto_hasta is None:
            return True
        if self._reloj() < self._abierto_hasta or self._prueba_en_curso:
            return False
        self._prueba_en_curso = True  # pasaron los 5 min: se habilita 1 llamada de prueba
        return True

    def registrar_exito(self) -> None:
        self._abierto_hasta = None
        self._prueba_en_curso = False

    def registrar_falla(self) -> None:
        self._abierto_hasta = self._reloj() + self.duracion_s
        self._prueba_en_curso = False


_SIN_DATO = {"sin_dato": True}  # entrada de caché: punto + 4 vecinos sin dato (determinístico)
_limitador = LimitadorTasa()
_corte = CorteAutomatico()
_lotes_ejemplo: list[dict[str, Any]] | None = None


def reiniciar_estado(
    limitador: LimitadorTasa | None = None,
    corte: CorteAutomatico | None = None,
    lotes_ejemplo: list[dict[str, Any]] | None = None,
) -> None:
    """Reinicia limitador, corte y lotes de ejemplo (uso en tests). La caché se configura
    aparte con ``providers.cache.configurar_cache``."""
    global _limitador, _corte, _lotes_ejemplo
    _limitador = limitador or LimitadorTasa()
    _corte = corte or CorteAutomatico()
    _lotes_ejemplo = lotes_ejemplo


def cargar_lotes_ejemplo(ruta: Path = RUTA_LOTES_EJEMPLO) -> list[dict[str, Any]]:
    """Lee una sola vez los lotes de ejemplo precargados (vacío si no existe el JSON)."""
    global _lotes_ejemplo
    if _lotes_ejemplo is None:
        try:
            _lotes_ejemplo = json.loads(ruta.read_text(encoding="utf-8")).get("lotes", [])
        except FileNotFoundError:
            _lotes_ejemplo = []
    return _lotes_ejemplo


# ---------------------------------------------------------------------------
# Funciones puras
# ---------------------------------------------------------------------------


def _validar_coordenadas(lat: float, lon: float) -> None:
    if not -90.0 <= lat <= 90.0:
        raise ValueError(f"Latitud fuera de rango [-90, 90]: {lat}")
    if not -180.0 <= lon <= 180.0:
        raise ValueError(f"Longitud fuera de rango [-180, 180]: {lon}")


def _parsear(payload: Any) -> dict[str, float | None]:
    """Promedio 0–30 cm ponderado por espesor, en unidades objetivo (%, g/kg, pH).

    Si falta alguna profundidad se pondera con las disponibles; si faltan todas, ``None``.
    Lanza ``ValueError`` si el JSON no tiene la estructura esperada.
    """
    try:
        capas = payload["properties"]["layers"]
    except (KeyError, TypeError) as exc:
        raise ValueError("Respuesta de SoilGrids sin 'properties.layers'") from exc
    if not isinstance(capas, list):
        raise ValueError("'properties.layers' no es una lista")

    resultado: dict[str, float | None] = {p: None for p in PROPIEDADES}
    for capa in capas:
        nombre = capa.get("name")
        if nombre not in resultado:
            continue
        d_factor = float((capa.get("unit_measure") or {}).get("d_factor") or D_FACTOR_DEFAULT)
        suma, peso = 0.0, 0
        for prof in capa.get("depths", []):
            espesor = PROFUNDIDADES.get(prof.get("label"))
            valor = (prof.get("values") or {}).get("mean")
            if espesor is None or valor is None:
                continue
            suma += float(valor) * espesor
            peso += espesor
        resultado[nombre] = (suma / peso) / d_factor if peso else None
    return resultado


def clasificar_textura_usda(arena: float, limo: float, arcilla: float) -> str:
    """Clase textural del triángulo USDA (nombres en español, snake_case).

    Normaliza arena + limo + arcilla a 100 antes de clasificar.
    """
    total = arena + limo + arcilla
    if total <= 0:
        raise ValueError("Arena + limo + arcilla debe ser > 0")
    sand, silt, clay = (arena * 100 / total, limo * 100 / total, arcilla * 100 / total)

    if silt + 1.5 * clay < 15:
        return "arenoso"
    if silt + 2 * clay < 30:
        return "arenoso_franco"
    if (7 <= clay < 20 and sand > 52) or (clay < 7 and silt < 50):
        return "franco_arenoso"
    if 7 <= clay < 27 and 28 <= silt < 50 and sand <= 52:
        return "franco"
    if (silt >= 50 and 12 <= clay < 27) or (50 <= silt < 80 and clay < 12):
        return "franco_limoso"
    if silt >= 80 and clay < 12:
        return "limoso"
    if 20 <= clay < 35 and silt < 28 and sand > 45:
        return "franco_arcillo_arenoso"
    if 27 <= clay < 40 and 20 < sand <= 45:
        return "franco_arcilloso"
    if 27 <= clay < 40 and sand <= 20:
        return "franco_arcillo_limoso"
    if clay >= 35 and sand > 45:
        return "arcillo_arenoso"
    if clay >= 40 and silt >= 40:
        return "arcillo_limoso"
    return "arcilloso"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _localidad_mas_cercana(lat: float, lon: float) -> tuple[dict[str, Any], float] | None:
    mejor = min(
        ((loc, _haversine_km(lat, lon, loc["lat"], loc["lon"])) for loc in LOCALIDADES_GEOINTA),
        key=lambda par: par[1],
    )
    return mejor if mejor[1] <= RADIO_FALLBACK_KM else None


def _vecinos(lat: float, lon: float) -> list[tuple[float, float]]:
    """4 vecinos a ~500 m en orden N, S, E, O (descarta los que salen de rango)."""
    dlon = OFFSET_VECINO_GRADOS / max(math.cos(math.radians(lat)), 1e-6)
    candidatos = [
        (lat + OFFSET_VECINO_GRADOS, lon),
        (lat - OFFSET_VECINO_GRADOS, lon),
        (lat, lon + dlon),
        (lat, lon - dlon),
    ]
    return [(a, b) for a, b in candidatos if -90 <= a <= 90 and -180 <= b <= 180]


def _armar_perfil(
    valores: dict[str, float | None], fuente: Fuente, distancia_km: float
) -> PerfilSueloSatelital:
    def r(v: float | None, nd: int = 1) -> float | None:
        return None if v is None else round(v, nd)

    arcilla, arena, limo = valores["clay"], valores["sand"], valores["silt"]
    advertencias: list[str] = []
    if fuente == "isric_soilgrids_v2_vecino":
        advertencias.append(ADV_VECINO)
    if arena is None or limo is None:
        advertencias.append(ADV_SIN_TEXTURA)
    if valores["soc"] is None:
        advertencias.append(ADV_SIN_SOC)
    if valores["phh2o"] is None:
        advertencias.append(ADV_SIN_PH)

    textura = (
        clasificar_textura_usda(arena, limo, arcilla)
        if arcilla is not None and arena is not None and limo is not None
        else None
    )
    return PerfilSueloSatelital(
        arcilla_pct=r(arcilla),
        arena_pct=r(arena),
        limo_pct=r(limo),
        carbono_organico_g_kg=r(valores["soc"]),
        ph=r(valores["phh2o"], 2),
        textura_predominante=textura,
        fuente=fuente,
        distancia_fuente_km=round(distancia_km, 2),
        localidad_fallback=None,
        advertencias=tuple(advertencias),
    )


def _lote_ejemplo_cercano(lat: float, lon: float) -> PerfilSueloSatelital | None:
    for lote in cargar_lotes_ejemplo():
        distancia = _haversine_km(lat, lon, lote["lat"], lote["lon"])
        if distancia <= RADIO_LOTE_EJEMPLO_KM:
            perfil = dict_a_perfil(lote["perfil"])
            return PerfilSueloSatelital(
                **{**perfil.__dict__, "fuente": "precache", "distancia_fuente_km": round(distancia, 2)}
            )
    return None


def _fallback_regional(lat: float, lon: float, motivo: str, *, transitorio: bool) -> PerfilSueloSatelital:
    cercana = _localidad_mas_cercana(lat, lon)
    if cercana is None:
        raise SoilGridsUnavailable(
            f"SoilGrids sin dato ({motivo}) y ninguna localidad GeoINTA a menos de "
            f"{RADIO_FALLBACK_KM:.0f} km de ({lat}, {lon})"
        )
    loc, distancia = cercana
    return PerfilSueloSatelital(
        arcilla_pct=loc["arcilla_pct"],
        arena_pct=None,
        limo_pct=None,
        carbono_organico_g_kg=None,
        ph=None,
        textura_predominante=None,
        fuente="fallback_regional",
        distancia_fuente_km=round(distancia, 2),
        localidad_fallback=loc["nombre"],
        advertencias=(ADV_FALLBACK,),
        reintentar_soilgrids=transitorio,
    )


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

Estado = Literal["ok", "null", "error"]


async def _consultar(
    client: httpx.AsyncClient, lat: float, lon: float
) -> tuple[Estado, dict[str, float | None] | None, str]:
    """Una llamada a SoilGrids. Devuelve (estado, valores, detalle)."""
    params: list[tuple[str, str | float]] = [("lat", lat), ("lon", lon)]
    params += [("property", p) for p in PROPIEDADES]
    params += [("depth", d) for d in PROFUNDIDADES]
    params.append(("value", "mean"))
    try:
        resp = await client.get(BASE_URL, params=params, timeout=TIMEOUT_S)
    except httpx.TimeoutException:
        _corte.registrar_falla()
        return "error", None, "timeout"
    except httpx.TransportError as exc:
        return "error", None, f"error de red: {exc}"
    if resp.status_code == 429:
        _corte.registrar_falla()
        return "error", None, "HTTP 429 (límite de ISRIC)"
    if resp.status_code != 200:
        return "error", None, f"HTTP {resp.status_code}"
    try:
        valores = _parsear(resp.json())
    except ValueError as exc:
        return "error", None, f"respuesta inválida: {exc}"
    _corte.registrar_exito()
    if valores["clay"] is None:
        return "null", None, "píxel sin dato"
    return "ok", valores, ""


async def _cascada(client: httpx.AsyncClient, lat: float, lon: float, clave: str) -> PerfilSueloSatelital:
    cache = obtener_cache()

    if not _corte.permite_llamada():
        return _fallback_regional(lat, lon, "corte automático activo (ISRIC no responde)", transitorio=True)
    if _limitador.reservar_hasta(1) == 0:
        return _fallback_regional(lat, lon, "límite de 5 llamadas/minuto alcanzado", transitorio=True)

    estado, valores, detalle = await _consultar(client, lat, lon)
    if estado == "ok":
        perfil = _armar_perfil(valores, "isric_soilgrids_v2", 0.0)  # type: ignore[arg-type]
        cache.set(ESPACIO_SUELO, clave, perfil_a_dict(perfil))
        return perfil
    if estado == "error":
        return _fallback_regional(lat, lon, detalle, transitorio=True)

    # Píxel sin dato: vecinos (si el corte y el limitador lo permiten)
    vecinos = _vecinos(lat, lon)
    concedidas = _limitador.reservar_hasta(len(vecinos)) if _corte.permite_llamada() else 0
    if concedidas == 0:
        return _fallback_regional(lat, lon, "píxel sin dato y sin cupo para vecinos", transitorio=True)

    consultados = vecinos[:concedidas]
    resultados = await asyncio.gather(*(_consultar(client, vlat, vlon) for vlat, vlon in consultados))
    for (vlat, vlon), (v_estado, v_valores, _) in zip(consultados, resultados):
        if v_estado == "ok":
            perfil = _armar_perfil(
                v_valores, "isric_soilgrids_v2_vecino", _haversine_km(lat, lon, vlat, vlon)  # type: ignore[arg-type]
            )
            cache.set(ESPACIO_SUELO, clave, perfil_a_dict(perfil))
            return perfil

    if len(consultados) == 4 and all(r[0] == "null" for r in resultados):
        # Determinístico (urbano/agua): se cachea y no se marca para reintentar.
        cache.set(ESPACIO_SUELO, clave, _SIN_DATO)
        return _fallback_regional(lat, lon, "píxel y vecinos sin dato", transitorio=False)
    return _fallback_regional(lat, lon, "píxel sin dato y vecinos incompletos", transitorio=True)


async def fetch_perfil_suelo(
    lat: float, lon: float, *, client: httpx.AsyncClient | None = None
) -> PerfilSueloSatelital:
    """Perfil edáfico 0–30 cm del punto.

    Orden: lote de ejemplo (≤100 m) → caché → SoilGrids (punto, vecinos) → fallback GeoINTA.

    Raises:
        ValueError: coordenadas fuera de rango.
        SoilGridsUnavailable: sin dato y sin localidad GeoINTA a menos de 100 km.
    """
    _validar_coordenadas(lat, lon)

    lote = _lote_ejemplo_cercano(lat, lon)
    if lote is not None:
        return lote

    clave = clave_coordenada(lat, lon)
    cacheado = obtener_cache().get(ESPACIO_SUELO, clave)
    if cacheado == _SIN_DATO:
        return _fallback_regional(lat, lon, "píxel y vecinos sin dato (caché)", transitorio=False)
    if cacheado is not None:
        return dict_a_perfil(cacheado)

    if client is None:
        async with httpx.AsyncClient() as propio:
            return await _cascada(propio, lat, lon, clave)
    return await _cascada(client, lat, lon, clave)
