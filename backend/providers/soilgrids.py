"""Provider de ISRIC SoilGrids v2 (BACK-3).

Devuelve el perfil edáfico 0–30 cm (ponderado por espesor) de un punto, con una cascada
de respaldo:

1. Punto pedido.
2. Si el píxel no tiene dato (``null``: zona urbana / agua): 4 vecinos a ~500 m (N, S, E, O).
3. Si hay timeout / 429 / 5xx / red, o los vecinos tampoco tienen dato:
   a. BACK-19: perfil ISRIC del punto de la grilla precargada (Supabase, cada ~100 km) más
      cercano (≤ 100 km), con advertencia visible.
   b. Si no hay grilla cerca: arcilla de la localidad GeoINTA más cercana (≤ 100 km).
4. Sin grilla ni localidad a 100 km: ``SoilGridsUnavailable`` (el router lo mapea a 503).

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
# BACK-19: con puntos cada 100 km, el peor caso dentro de las provincias es ~111 km (puntas finas).
RADIO_GRILLA_KM = 120.0
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
ADV_GRILLA = (
    "Perfil de suelo de ISRIC tomado de un punto de referencia a {distancia:.0f} km "
    "(ISRIC no respondió a tiempo o no tiene dato en el punto). Textura y carbono son aproximados."
)
ADV_SIN_SOC = "Carbono orgánico no disponible: el ajuste de rotación por carbono no se aplicó."
ADV_SIN_PH = "pH no disponible: el ajuste de rotación por pH no se aplicó."
ADV_SIN_TEXTURA = "Arena/limo no disponibles: no se pudo determinar la clase textural."

Fuente = Literal[
    "isric_soilgrids_v2", "isric_soilgrids_v2_vecino", "precache", "grilla_isric", "fallback_regional"
]
ESPACIO_GRILLA = "suelo_grilla"  # BACK-19: filas de provider_cache con la grilla de ~100 km

# Tabla GeoINTA, limitador y corte automático: compartidos con el provider de SRTM (BACK-5).
# Se reexportan con los mismos nombres para no romper a quien ya los importa desde acá.
from providers.regional import LOCALIDADES_GEOINTA, haversine_km, localidad_mas_cercana  # noqa: E402
from providers.resiliencia import CorteAutomatico, LimitadorTasa  # noqa: E402,F401


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


_SIN_DATO = {"sin_dato": True}  # entrada de caché: punto + 4 vecinos sin dato (determinístico)
_limitador = LimitadorTasa(LIMITE_LLAMADAS, VENTANA_LIMITE_S)
_corte = CorteAutomatico(DURACION_CORTE_S)
_lotes_ejemplo: list[dict[str, Any]] | None = None
_grilla: list[dict[str, Any]] = []  # BACK-19: [{"lat", "lon", "perfil"}], vacía hasta registrarla


def reiniciar_estado(
    limitador: LimitadorTasa | None = None,
    corte: CorteAutomatico | None = None,
    lotes_ejemplo: list[dict[str, Any]] | None = None,
    grilla: dict[str, Any] | None = None,
) -> None:
    """Reinicia limitador, corte, lotes de ejemplo y grilla (uso en tests). La caché se
    configura aparte con ``providers.cache.configurar_cache``."""
    global _limitador, _corte, _lotes_ejemplo
    _limitador = limitador or LimitadorTasa(LIMITE_LLAMADAS, VENTANA_LIMITE_S)
    _corte = corte or CorteAutomatico(DURACION_CORTE_S)
    _lotes_ejemplo = lotes_ejemplo
    registrar_grilla(grilla or {})


def registrar_grilla(entradas: dict[str, Any]) -> int:
    """BACK-19: carga la grilla de suelo (``CacheSupabase.entradas("suelo_grilla")``).

    Cada valor es ``{"lat", "lon", "perfil": perfil_a_dict(...)}``. Las entradas mal formadas
    se descartan. Devuelve cuántos puntos quedaron cargados.
    """
    global _grilla
    puntos = []
    for valor in entradas.values():
        try:
            dict_a_perfil(valor["perfil"])  # valida la forma
            puntos.append({"lat": float(valor["lat"]), "lon": float(valor["lon"]), "perfil": valor["perfil"]})
        except (KeyError, TypeError, ValueError):
            continue
    _grilla = puntos
    return len(puntos)


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


_haversine_km = haversine_km  # alias histórico (tests y código de BACK-3)


def _localidad_mas_cercana(lat: float, lon: float) -> tuple[dict[str, Any], float] | None:
    return localidad_mas_cercana(lat, lon, RADIO_FALLBACK_KM)


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


def _punto_grilla_mas_cercano(
    lat: float, lon: float, radio_km: float = RADIO_GRILLA_KM
) -> tuple[dict[str, Any], float] | None:
    """Punto de la grilla más cercano y su distancia, o ``None`` si no hay ninguno a ``radio_km``."""
    if not _grilla:
        return None
    mejor = min(((p, _haversine_km(lat, lon, p["lat"], p["lon"])) for p in _grilla), key=lambda par: par[1])
    return mejor if mejor[1] <= radio_km else None


def _perfil_de_grilla(punto: dict[str, Any], distancia: float, *, transitorio: bool) -> PerfilSueloSatelital:
    base = dict_a_perfil(punto["perfil"])
    # Las advertencias propias del punto (p. ej. sin carbono) siguen valiendo; la de "vecino a
    # 500 m" se reemplaza por la de la grilla.
    propias = tuple(a for a in base.advertencias if a != ADV_VECINO)
    return PerfilSueloSatelital(
        **{
            **base.__dict__,
            "fuente": "grilla_isric",
            "distancia_fuente_km": round(distancia, 2),
            "localidad_fallback": None,
            "advertencias": (ADV_GRILLA.format(distancia=distancia),) + propias,
            "reintentar_soilgrids": transitorio,
        }
    )


def _fallback_regional(lat: float, lon: float, motivo: str, *, transitorio: bool) -> PerfilSueloSatelital:
    """Grilla ISRIC (BACK-19) → localidad GeoINTA → ``SoilGridsUnavailable``. Nunca se cachea."""
    en_grilla = _punto_grilla_mas_cercano(lat, lon)
    if en_grilla is not None:
        return _perfil_de_grilla(*en_grilla, transitorio=transitorio)
    cercana = _localidad_mas_cercana(lat, lon)
    if cercana is None:
        raise SoilGridsUnavailable(
            f"SoilGrids sin dato ({motivo}), sin punto de grilla ISRIC a {RADIO_GRILLA_KM:.0f} km "
            f"ni localidad GeoINTA a {RADIO_FALLBACK_KM:.0f} km de ({lat}, {lon})"
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
    client: httpx.AsyncClient, lat: float, lon: float, timeout_s: float = TIMEOUT_S
) -> tuple[Estado, dict[str, float | None] | None, str]:
    """Una llamada a SoilGrids. Devuelve (estado, valores, detalle).

    ``timeout_s`` solo se cambia en la generación offline de la grilla (BACK-19).
    """
    params: list[tuple[str, str | float]] = [("lat", lat), ("lon", lon)]
    params += [("property", p) for p in PROPIEDADES]
    params += [("depth", d) for d in PROFUNDIDADES]
    params.append(("value", "mean"))
    try:
        resp = await client.get(BASE_URL, params=params, timeout=timeout_s)
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

    Orden: lote de ejemplo (≤100 m) → caché → SoilGrids (punto, vecinos) → grilla ISRIC
    (BACK-19) → fallback GeoINTA.

    Raises:
        ValueError: coordenadas fuera de rango.
        SoilGridsUnavailable: sin dato y sin punto de grilla ni localidad GeoINTA a 100 km.
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
