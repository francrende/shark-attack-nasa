"""Primitivas de resiliencia compartidas por los providers (BACK-5).

- ``LimitadorTasa``: ventana deslizante (p. ej. ISRIC: 5 llamadas/minuto).
- ``CorteAutomatico``: circuit breaker (1 timeout/429 → corte; luego 1 llamada de prueba).
- ``EsperaMinima``: intervalo mínimo entre llamadas, esperando en lugar de fallar
  (p. ej. OpenTopoData: 1 llamada/segundo).
- ``ContadorDiario``: tope de llamadas por día UTC (p. ej. OpenTopoData: 1000/día).
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timezone


class LimitadorTasa:
    """Ventana deslizante: como máximo ``max_llamadas`` en los últimos ``ventana_s`` segundos."""

    def __init__(
        self,
        max_llamadas: int = 5,
        ventana_s: float = 60.0,
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

    def __init__(self, duracion_s: float = 300.0, reloj: Callable[[], float] = time.monotonic) -> None:
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
        self._prueba_en_curso = True  # pasó el corte: se habilita 1 llamada de prueba
        return True

    def registrar_exito(self) -> None:
        self._abierto_hasta = None
        self._prueba_en_curso = False

    def registrar_falla(self) -> None:
        self._abierto_hasta = self._reloj() + self.duracion_s
        self._prueba_en_curso = False


class EsperaMinima:
    """Garantiza ``intervalo_s`` entre llamadas consecutivas, esperando lo que falte."""

    def __init__(
        self,
        intervalo_s: float = 1.0,
        reloj: Callable[[], float] = time.monotonic,
        dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.intervalo_s = intervalo_s
        self._reloj = reloj
        self._dormir = dormir
        self._ultima: float | None = None
        self._lock = asyncio.Lock()

    async def esperar(self) -> None:
        async with self._lock:
            if self._ultima is not None:
                faltante = self._ultima + self.intervalo_s - self._reloj()
                if faltante > 0:
                    await self._dormir(faltante)
            self._ultima = self._reloj()


class ContadorDiario:
    """Tope de llamadas por día (UTC); el contador se reinicia al cambiar la fecha."""

    def __init__(
        self,
        limite: int = 1000,
        hoy: Callable[[], date] = lambda: datetime.now(timezone.utc).date(),
    ) -> None:
        self.limite = limite
        self._hoy = hoy
        self._fecha: date | None = None
        self._usadas = 0

    def reservar(self) -> bool:
        hoy = self._hoy()
        if hoy != self._fecha:
            self._fecha, self._usadas = hoy, 0
        if self._usadas >= self.limite:
            return False
        self._usadas += 1
        return True
