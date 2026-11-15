/**
 * Último resultado real de `/simulate` por lote (FRONT-36, estados sin backend).
 *
 * Se guarda en el navegador solo como comodidad: si el backend no responde, el panel muestra el
 * último resultado real de ese lote con su fecha en lugar de datos de ejemplo. Nunca se guardan
 * respuestas de ejemplo ni simulaciones What-If. Si `localStorage` no está disponible, todo
 * sigue funcionando sin resultado guardado.
 */

import type { Campana, CultivoAnterior, ObjetivoProductor, SimulateResponse } from '../types/api'

const PREFIJO = 'ereia.ultimoResultado.v1:'
const MAXIMO_ENTRADAS = 20
/** Más viejo que esto, el aviso agrega que puede estar desactualizado. */
export const DIAS_DESACTUALIZADO = 7

export interface ClaveResultado {
  fieldId?: string | null
  lat: number
  lon: number
  campana: Campana
  cultivoAnterior: CultivoAnterior
  objetivo: ObjetivoProductor
}

export interface ResultadoGuardado {
  respuesta: SimulateResponse
  consultadoEn: string
}

export function claveResultado(c: ClaveResultado): string {
  const lugar = c.fieldId ? `campo:${c.fieldId}` : `coord:${c.lat.toFixed(3)},${c.lon.toFixed(3)}`
  return `${PREFIJO}${lugar}|${c.campana}|${c.cultivoAnterior}|${c.objetivo}`
}

function almacen(): Storage | null {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    return null
  }
}

function leer(storage: Storage, clave: string): ResultadoGuardado | null {
  try {
    const crudo = storage.getItem(clave)
    if (!crudo) return null
    const valor = JSON.parse(crudo) as ResultadoGuardado
    return valor?.respuesta && valor?.consultadoEn ? valor : null
  } catch {
    return null
  }
}

/** Descarta las entradas más viejas para no pasar de `MAXIMO_ENTRADAS`. */
function podar(storage: Storage): void {
  const entradas: { clave: string; fecha: string }[] = []
  for (let i = 0; i < storage.length; i += 1) {
    const clave = storage.key(i)
    if (!clave?.startsWith(PREFIJO)) continue
    const valor = leer(storage, clave)
    entradas.push({ clave, fecha: valor?.consultadoEn ?? '' })
  }
  entradas.sort((a, b) => b.fecha.localeCompare(a.fecha))
  for (const { clave } of entradas.slice(MAXIMO_ENTRADAS)) {
    storage.removeItem(clave)
  }
}

export function guardarUltimoResultado(clave: string, respuesta: SimulateResponse): void {
  if (respuesta.es_ejemplo) return
  const storage = almacen()
  if (!storage) return
  try {
    const valor: ResultadoGuardado = { respuesta, consultadoEn: new Date().toISOString() }
    storage.setItem(clave, JSON.stringify(valor))
    podar(storage)
  } catch {
    // Cuota llena o almacenamiento bloqueado: se sigue sin guardar.
  }
}

export function leerUltimoResultado(clave: string): ResultadoGuardado | null {
  const storage = almacen()
  if (!storage) return null
  return leer(storage, clave)
}

export function estaDesactualizado(consultadoEn: string, ahora: Date = new Date()): boolean {
  const t = new Date(consultadoEn).getTime()
  if (Number.isNaN(t)) return true
  return ahora.getTime() - t > DIAS_DESACTUALIZADO * 24 * 60 * 60 * 1000
}
