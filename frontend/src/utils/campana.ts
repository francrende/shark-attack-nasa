import type { Campana } from '../types/api'

/**
 * Regla de campaña vigente (CONTEXT.md §4.1), idéntica a la del backend y el entrenamiento:
 * se mira el mes de hoy + 45 días; si cae entre abril y septiembre, la campaña habilitada es
 * invierno, si no, verano. El backend rechaza (422) la campaña que no corresponde a la fecha.
 */
const ANTICIPACION_CAMPANA_DIAS = 45
const MESES_INVIERNO = new Set([4, 5, 6, 7, 8, 9])

function sumarDias(fecha: Date, dias: number): Date {
  const copia = new Date(fecha.getFullYear(), fecha.getMonth(), fecha.getDate())
  copia.setDate(copia.getDate() + dias)
  return copia
}

export function campanaVigente(hoy: Date = new Date()): Campana {
  const centro = sumarDias(hoy, ANTICIPACION_CAMPANA_DIAS)
  return MESES_INVIERNO.has(centro.getMonth() + 1) ? 'invierno' : 'verano'
}

/** Primer día desde `hoy` en que `campana` queda habilitada. */
export function proximaHabilitacion(campana: Campana, hoy: Date = new Date()): Date {
  let dia = sumarDias(hoy, 0)
  for (let i = 0; i < 366 && campanaVigente(dia) !== campana; i++) {
    dia = sumarDias(dia, 1)
  }
  return dia
}
