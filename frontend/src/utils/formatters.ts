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

/**
 * Traduce advertencias técnicas provenientes de /telemetry, /simulate o campos
 * persistidos a lenguaje agronómico claro en español formal, sin exponer siglas
 * técnicas ni nombres internos de proveedores (ISRIC, SoilGrids, SRTM, NASA POWER).
 */
export function humanizeAgronomicWarning(rawWarning: string): string {
  const trimmed = rawWarning.trim()
  if (!trimmed) return ''

  // Patrón de grilla/referencia distante de suelo (conserva distancia en km)
  const distantSoilMatch = trimmed.match(
    /(?:perfil\s+de\s+suelo|datos?\s+de\s+suelo)(?:\s+de\s+(?:isric|soilgrids))?\s+tomado(?:s)?\s+de\s+un\s+punto\s+de\s+referencia\s+a\s+([\d.,]+)\s*km/i
  )
  if (distantSoilMatch) {
    return `Perfil de suelo tomado de un punto de referencia a ${distantSoilMatch[1]} km. La textura y la materia orgánica son aproximadas.`
  }

  // Patrón de suelo desplazado ~500 m por falta de lectura exacta en el punto
  if (/~?\s*500\s*m/i.test(trimmed) && /(suelo|soilgrids|isric)/i.test(trimmed)) {
    return 'Perfil de suelo tomado de un punto cercano (~500 m), ya que no hubo lectura exacta dentro del lote.'
  }

  // Patrón de pendiente o relieve SRTM no disponible o de modelo
  if (/pendiente\s+tomada\s+del\s+modelo\s+srtm/i.test(trimmed)) {
    return 'Pendiente calculada a partir del modelo satelital de relieve del terreno.'
  }
  if (/topograf[ií]a\s+srtm\s+no\s+disponible/i.test(trimmed)) {
    return 'No se obtuvo el relieve exacto del terreno para esta ubicación; se muestra una estimación aproximada.'
  }

  // Limpieza general de siglas técnicas y nombres de proveedores
  let sanitized = trimmed
    .replace(/\(\s*(?:ISRIC|SoilGrids|SRTM|NASA\s*POWER)[^)]*\)/gi, '')
    .replace(/\bISRIC\s+SoilGrids(?:\s+v\d+)?\b/gi, 'referencia satelital de suelos')
    .replace(/\bisric_soilgrids_v\d+(?:_vecino)?\b/gi, 'referencia satelital de suelos')
    .replace(/\bgrilla_isric\b/gi, 'referencia regional de suelos')
    .replace(/\bSoilGrids\b/gi, 'referencia satelital de suelos')
    .replace(/\bISRIC\b/gi, 'referencia satelital de suelos')
    .replace(/\b(?:opentopodata_)?srtm\s*(?:30\s*m|90\s*m)?\b/gi, 'relieve satelital del terreno')
    .replace(/\bNASA\s*POWER\b/gi, 'observación satelital')
    .replace(/\bGeoINTA\b/gi, 'referencia regional')
    .replace(/\bGWETROOT\b/gi, 'agua en las raíces')
    .replace(/\bGWETTOP\b/gi, 'humedad superficial')
    .replace(/\bsoc\b/gi, 'materia orgánica')
    .replace(/\bphh2o\b/gi, 'pH del suelo')
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+([.,;:])/g, '$1')
    .replace(/\.{2,}/g, '.')
    .trim()

  if (!sanitized) return ''
  return sanitized.charAt(0).toUpperCase() + sanitized.slice(1)
}

/**
 * Combina múltiples fuentes de advertencias agronómicas, las traduce al lenguaje
 * comprensible del productor y elimina duplicados conservando el orden.
 */
export function humanizeAgronomicWarnings(
  sources: ReadonlyArray<readonly string[] | null | undefined>
): string[] {
  const seen = new Set<string>()
  const result: string[] = []

  for (const list of sources) {
    if (!Array.isArray(list)) continue
    for (const item of list) {
      if (typeof item !== 'string') continue
      const formatted = humanizeAgronomicWarning(item)
      if (!formatted) continue
      const dedupeKey = formatted.toLowerCase()
      if (!seen.has(dedupeKey)) {
        seen.add(dedupeKey)
        result.push(formatted)
      }
    }
  }

  return result
}

/** kg/ha → quintales por hectárea (1 qq = 100 kg). */
export function kgHaAQq(kg: number): number {
  return kg / 100
}

/** 3400 → "34 qq/ha" (unidad de uso en Argentina, redondeada a entero). */
export function formatQq(kg: number): string {
  return `${Math.round(kgHaAQq(kg))} qq/ha`
}
