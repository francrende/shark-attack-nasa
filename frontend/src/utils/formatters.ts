const MESES_CORTOS = [
  'ene.',
  'feb.',
  'mar.',
  'abr.',
  'may.',
  'jun.',
  'jul.',
  'ago.',
  'sep.',
  'oct.',
  'nov.',
  'dic.',
]

/**
 * Convierte una fecha ISO ('2026-11-08') a formato humano ('8 nov. 2026').
 * Nunca expone formato ISO en la interfaz (SKILLS_FRONTEND.md §3.4).
 */
export function formatHumanDate(isoDateStr: string): string {
  const parts = isoDateStr.split('-')
  if (parts.length !== 3) return isoDateStr

  const year = Number(parts[0])
  const monthIdx = Number(parts[1]) - 1
  const day = Number(parts[2])

  if (
    Number.isNaN(year) ||
    Number.isNaN(monthIdx) ||
    Number.isNaN(day) ||
    monthIdx < 0 ||
    monthIdx > 11
  ) {
    return isoDateStr
  }

  return `${day} ${MESES_CORTOS[monthIdx]} ${year}`
}

/**
 * Convierte una fecha ISO ('2024-11-08') a formato corto para el mapa ('8 nov.').
 */
export function formatShortHumanDate(isoDateStr: string): string {
  const parts = isoDateStr.split('-')
  if (parts.length !== 3) return isoDateStr

  const monthIdx = Number(parts[1]) - 1
  const day = Number(parts[2])

  if (
    Number.isNaN(monthIdx) ||
    Number.isNaN(day) ||
    monthIdx < 0 ||
    monthIdx > 11
  ) {
    return isoDateStr
  }

  return `${day} ${MESES_CORTOS[monthIdx]}`
}

/**
 * Formatea una anomalía porcentual como entero con signo ('−24%' o '+7%').
 */
export function formatSignedAnomalyPct(value: number): string {
  const rounded = Math.round(value)
  if (rounded > 0) return `+${rounded}%`
  if (rounded < 0) return `−${Math.abs(rounded)}%`
  return '0% (Normal)'
}
