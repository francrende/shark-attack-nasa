"""Capa de caché persistente en Supabase (BACK-18).

Segunda capa de ``CacheEnCapas`` (BACK-10) sobre la tabla ``public.provider_cache``:

    espacio text, clave text, valor jsonb, actualizado_en timestamptz, PK (espacio, clave)

Diseño:
- **Lectura sin espera:** ``hidratar()`` baja al arrancar las filas de los espacios de
  precarga a una copia en memoria. ``get`` solo lee esa copia: un ``/simulate`` nunca
  espera a Supabase.
- **Lectura bajo demanda (BACK-26):** ``nasa_hist`` (~53 KB por celda) no se precarga. Se
  lee de a una celda con ``leer`` cuando se la necesita.
- **Escritura en segundo plano:** ``set`` actualiza la copia y encola un upsert. Un hilo
  daemon los manda en lotes.
- **Nunca rompe el servidor:** cualquier falla de Supabase (tabla inexistente, red,
  credencial) se loguea y el backend sigue solo con memoria.
- **Credencial:** la secret key (``sb_secret_...``), que saltea RLS. La tabla no tiene
  políticas, así que la publishable key (pública) no puede leer ni escribir.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from typing import Any

from providers.cache import _copia_json

logger = logging.getLogger(__name__)

TABLA = "provider_cache"
# Todo lo que no vence. `nasa_reciente` (TTL 6 h) queda solo en memoria.
ESPACIOS_PERSISTIDOS: frozenset[str] = frozenset(
    # BACK-31: "nasa_mensual" (meses de años ya cerrados, no cambian)
    {"suelo", "topografia", "nasa_elevacion", "nasa_hist", "suelo_grilla", "nasa_mensual"}
)
# BACK-26: el clima histórico por celda se lee bajo demanda, no al arrancar (15,8 MB).
ESPACIOS_BAJO_DEMANDA: frozenset[str] = frozenset({"nasa_hist"})
ESPACIOS_PRECARGA: frozenset[str] = ESPACIOS_PERSISTIDOS - ESPACIOS_BAJO_DEMANDA
TAM_LOTE_DIRECTO = 10  # filas grandes (nasa_hist): lotes chicos por request
TAM_PAGINA = 1000  # máximo de filas por request de PostgREST
TAM_LOTE_ESCRITURA = 50
TIMEOUT_REQUEST_S = 10.0

FiltroEscritura = Callable[[str, str], bool]

_FIN = object()


class CacheSupabase:
    """Cumple el ``Protocol`` ``Cache``. El cliente de Supabase se inyecta (tests: uno falso)."""

    def __init__(
        self,
        cliente: Any,
        *,
        espacios: frozenset[str] = ESPACIOS_PERSISTIDOS,
        tabla: str = TABLA,
        tam_pagina: int = TAM_PAGINA,
        filtro_escritura: FiltroEscritura | None = None,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self._cliente = cliente
        self.espacios = espacios
        self._tabla = tabla
        self._tam_pagina = tam_pagina
        self._filtro = filtro_escritura
        self._reloj = reloj
        self._datos: dict[tuple[str, str], Any] = {}
        self._lock = threading.Lock()
        self._cola: queue.Queue[Any] = queue.Queue()
        self._hilo: threading.Thread | None = None
        self.escrituras_fallidas = 0

    # --- Protocol Cache -------------------------------------------------------------------

    def get(self, espacio: str, clave: str) -> Any | None:
        with self._lock:
            valor = self._datos.get((espacio, clave))
        return None if valor is None else _copia_json(valor)

    def set(self, espacio: str, clave: str, valor: Any, ttl_s: float | None = None) -> None:
        """Solo persiste espacios de la lista, sin TTL y que pasen el filtro de escritura."""
        if espacio not in self.espacios or ttl_s is not None:
            return
        if self._filtro is not None and not self._filtro(espacio, clave):
            return
        copia = _copia_json(valor)
        with self._lock:
            if self._datos.get((espacio, clave)) == copia:
                return  # ya está así en Supabase (leído o escrito antes): no se reescribe
            self._datos[(espacio, clave)] = copia
        self._asegurar_hilo()
        self._cola.put((espacio, clave, copia))

    # --- Precarga -------------------------------------------------------------------------

    def hidratar(self, timeout_s: float = 10.0) -> int:
        """Baja las filas de los espacios persistidos, paginando. Devuelve cuántas cargó.

        Si Supabase falla o se pasa el tiempo, se queda con lo que llegó a bajar.
        """
        limite = self._reloj() + timeout_s
        cargadas = 0
        desde = 0
        try:
            while True:
                if self._reloj() >= limite:
                    logger.warning("cache_supabase: precarga cortada por tiempo (%d filas)", cargadas)
                    break
                resp = (
                    self._cliente.table(self._tabla)
                    .select("espacio,clave,valor")
                    .in_("espacio", sorted(self.espacios - ESPACIOS_BAJO_DEMANDA))
                    .order("espacio")
                    .order("clave")
                    .range(desde, desde + self._tam_pagina - 1)
                    .execute()
                )
                filas = resp.data or []
                with self._lock:
                    for fila in filas:
                        self._datos[(fila["espacio"], fila["clave"])] = fila["valor"]
                cargadas += len(filas)
                if len(filas) < self._tam_pagina:
                    break
                desde += self._tam_pagina
        except Exception as exc:  # noqa: BLE001 - nunca debe impedir el arranque
            logger.warning("cache_supabase: precarga fallida, sigo con memoria (%s)", exc)
        return cargadas

    def leer(self, espacio: str, clave: str) -> Any | None:
        """BACK-26: una fila bajo demanda (bloqueante: llamarla desde un thread).

        Primero la copia en memoria; si no está, Supabase, y queda en la copia. Nunca lanza:
        ante un error devuelve ``None`` (el que llama sigue con su respaldo).
        """
        with self._lock:
            if (espacio, clave) in self._datos:
                return _copia_json(self._datos[(espacio, clave)])
        try:
            resp = (
                self._cliente.table(self._tabla)
                .select("valor")
                .eq("espacio", espacio)
                .eq("clave", clave)
                .limit(1)
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("cache_supabase: no se pudo leer %s/%s (%s)", espacio, clave, exc)
            return None
        filas = resp.data or []
        if not filas:
            return None
        valor = filas[0]["valor"]
        with self._lock:
            self._datos[(espacio, clave)] = valor
        return _copia_json(valor)

    def claves(self, espacio: str) -> set[str]:
        """Claves guardadas de un espacio, paginando (para scripts reanudables). Lanza si falla."""
        claves: set[str] = set()
        desde = 0
        while True:
            resp = (
                self._cliente.table(self._tabla)
                .select("clave")
                .eq("espacio", espacio)
                .order("clave")
                .range(desde, desde + self._tam_pagina - 1)
                .execute()
            )
            filas = resp.data or []
            claves.update(f["clave"] for f in filas)
            if len(filas) < self._tam_pagina:
                return claves
            desde += self._tam_pagina

    def escribir_directo(self, espacio: str, entradas: dict[str, Any], tam_lote: int = TAM_LOTE_DIRECTO) -> int:
        """Upsert sincrónico en lotes chicos (scripts offline con filas grandes). Lanza si falla."""
        items = list(entradas.items())
        for i in range(0, len(items), tam_lote):
            filas = [{"espacio": espacio, "clave": c, "valor": _copia_json(v)} for c, v in items[i : i + tam_lote]]
            self._cliente.table(self._tabla).upsert(filas).execute()
        return len(items)

    def entradas(self, espacio: str) -> dict[str, Any]:
        """Todas las entradas cargadas de un espacio (BACK-19: la grilla de suelo)."""
        with self._lock:
            return {c: _copia_json(v) for (e, c), v in self._datos.items() if e == espacio}

    # --- Escritura en segundo plano --------------------------------------------------------

    def _asegurar_hilo(self) -> None:
        if self._hilo is not None and self._hilo.is_alive():
            return
        with self._lock:
            if self._hilo is None or not self._hilo.is_alive():
                self._hilo = threading.Thread(target=self._trabajar, name="cache_supabase", daemon=True)
                self._hilo.start()

    def _trabajar(self) -> None:
        while True:
            item = self._cola.get()
            fin = item is _FIN
            lote: dict[tuple[str, str], Any] = {}
            if not fin:
                lote[(item[0], item[1])] = item[2]
            # Junta lo que haya en la cola (dedupe: Postgres rechaza dos filas con la misma PK
            # en un mismo upsert).
            while not fin and len(lote) < TAM_LOTE_ESCRITURA:
                try:
                    siguiente = self._cola.get_nowait()
                except queue.Empty:
                    break
                if siguiente is _FIN:
                    fin = True
                    break
                lote[(siguiente[0], siguiente[1])] = siguiente[2]
            if lote:
                self._escribir(lote)
            if fin:
                return

    def _escribir(self, lote: dict[tuple[str, str], Any]) -> None:
        filas = [{"espacio": e, "clave": c, "valor": v} for (e, c), v in lote.items()]
        try:
            self._cliente.table(self._tabla).upsert(filas).execute()
        except Exception as exc:  # noqa: BLE001 - una escritura perdida no rompe nada
            self.escrituras_fallidas += len(filas)
            logger.warning("cache_supabase: no se pudieron escribir %d filas (%s)", len(filas), exc)

    def cerrar(self, timeout_s: float = 5.0) -> None:
        """Vacía la cola de escritura (best-effort) y detiene el hilo."""
        if self._hilo is None or not self._hilo.is_alive():
            return
        self._cola.put(_FIN)
        self._hilo.join(timeout_s)


def crear_cache_supabase(settings: Any, *, filtro_escritura: FiltroEscritura | None = None) -> CacheSupabase | None:
    """``None`` (solo memoria) si está desactivada o falta la secret key o la URL."""
    if not getattr(settings, "cache_persistente", True):
        return None
    url = (settings.supabase_url or "").strip()
    clave = (settings.supabase_secret_key or "").strip()
    if not url or not clave:
        logger.warning("cache_supabase: sin SUPABASE_SECRET_KEY, la caché queda solo en memoria")
        return None
    from supabase import ClientOptions, create_client

    cliente = create_client(url, clave, options=ClientOptions(postgrest_client_timeout=TIMEOUT_REQUEST_S))
    return CacheSupabase(cliente, filtro_escritura=filtro_escritura)
