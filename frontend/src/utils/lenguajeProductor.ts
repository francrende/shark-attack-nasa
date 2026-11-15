/**
 * Traducción de los datos del modelo a lenguaje de productor (FRONT-36).
 *
 * Fuente única de los textos de la tabla de traducción de TASKS_FRONTEND.md (FRONT-36):
 * nada de "P10", "puntaje", "ensemble", "análogos" ni "/100" en la vista principal.
 * Funciones puras, sin React.
 */

import type { CamposDistribucionPredictiva, DepartamentoReferencia, FaseEnso, FaseEnsoId } from '../types/api'
import { formatQq } from './formatters'

export type Nivel = 'bueno' | 'neutro' | 'malo'

export interface TextoConNivel {
  texto: string
  nivel: Nivel
}

/** "Rinde bajo" = 15% o más bajo lo normal de la zona (definición del modelo, ML-16). */
export const DEFINICION_RINDE_BAJO =
  'Rinde bajo: 15% o más por debajo de lo normal de la zona.'

/** Cociente frente a lo habitual a partir del cual se habla de más o menos riesgo. */
const COCIENTE_MAS_RIESGO = 1.3
const COCIENTE_MENOS_RIESGO = 0.77

// ---------------------------------------------------------------------------
// Frecuencias
// ---------------------------------------------------------------------------

/**
 * Una sola escala para todas las frecuencias, porque se comparan entre sí ("1 de cada 6,
 * normalmente 1 de cada 4"): por debajo de 0,35, "1 de cada N"; desde 0,35, "N de cada 10".
 * Mezclar "2 de cada 10" con "1 de cada 4" no se puede comparar, y redondear a décimos hace que
 * 0,18 y 0,24 se lean iguales.
 */
export function frecuencia(p: number): string {
  if (p <= 0.05) return 'menos de 1 de cada 20'
  if (p < 0.35) return `1 de cada ${Math.round(1 / p)}`
  return `${Math.round(p * 10)} de cada 10`
}

export function comparacionHabitual(p: number, pTipica: number): TextoConNivel {
  const cociente = pTipica > 0 ? p / pTipica : 1
  if (cociente >= COCIENTE_MAS_RIESGO) return { texto: 'Más riesgo que lo habitual', nivel: 'malo' }
  if (cociente <= COCIENTE_MENOS_RIESGO) return { texto: 'Menos riesgo que lo habitual', nivel: 'bueno' }
  return { texto: 'Riesgo parecido a lo habitual', nivel: 'neutro' }
}

export interface TextoRiesgoAnioMalo {
  /** Línea principal, con la frecuencia destacada. */
  frecuencia: string
  titulo: string
  detalle: string
  nivel: Nivel
  /** Texto corto para la fila compacta del ranking. */
  corto: string
}

/**
 * Riesgo de año malo de un cultivo. Con anticipación: frecuencia del año + comparación.
 * Sin anticipación: solo la frecuencia habitual, sin flecha ni alerta. Sin datos: null.
 */
export function textoRiesgoAnioMalo(
  datos: CamposDistribucionPredictiva,
  nombreCultivo: string
): TextoRiesgoAnioMalo | null {
  const tipica = datos.prob_anio_malo_tipica
  if (tipica == null) return null
  const habitual = frecuencia(tipica)
  if (datos.anticipa_diferencias && datos.prob_anio_malo != null) {
    const frecuenciaAnio = frecuencia(datos.prob_anio_malo)
    const comp = comparacionHabitual(datos.prob_anio_malo, tipica)
    return {
      frecuencia: frecuenciaAnio,
      titulo: 'campañas como esta terminan con rinde bajo',
      detalle: `${comp.texto} (normalmente ${habitual}).`,
      nivel: comp.nivel,
      corto: `${frecuenciaAnio} con rinde bajo`,
    }
  }
  return {
    frecuencia: habitual,
    titulo: `campañas de ${nombreCultivo.toLowerCase()} terminan con rinde bajo en esta zona`,
    detalle:
      'Para este cultivo todavía no podemos anticipar si este año viene mejor o peor que lo habitual.',
    nivel: 'neutro',
    corto: 'riesgo habitual',
  }
}

// ---------------------------------------------------------------------------
// Rinde
// ---------------------------------------------------------------------------

/** Rinde esperado contra lo normal: "+6%", "−13%" o "similar a lo normal". */
export function rindeVsNormal(esperado: number, normal: number): TextoConNivel {
  if (normal <= 0) return { texto: 'similar a lo normal', nivel: 'neutro' }
  const pct = Math.round((esperado / normal - 1) * 100)
  if (Math.abs(pct) <= 2) return { texto: 'similar a lo normal', nivel: 'neutro' }
  if (pct > 0) return { texto: `+${pct}%`, nivel: 'bueno' }
  return { texto: `−${Math.abs(pct)}%`, nivel: 'malo' }
}

/** "Rinde esperado: 34 qq/ha (lo normal en la zona es 32 qq/ha, +6%)". */
export function textoRindeEsperado(esperado: number, normal: number): string {
  const comp = rindeVsNormal(esperado, normal)
  if (comp.texto === 'similar a lo normal') return `${formatQq(esperado)}, similar a lo normal en la zona`
  return `${formatQq(esperado)} (lo normal en la zona es ${formatQq(normal)}, ${comp.texto})`
}

/** Para cuando no hay kg/ha: desvío del puntaje hidroclimático (50 = año normal). */
export function textoDesvioNormal(hidro: number): TextoConNivel {
  const pct = Math.round(hidro - 50)
  if (Math.abs(pct) <= 2) return { texto: 'En línea con un año normal', nivel: 'neutro' }
  if (pct > 0) return { texto: `+${pct}% sobre un año normal`, nivel: 'bueno' }
  return { texto: `−${Math.abs(pct)}% bajo un año normal`, nivel: 'malo' }
}

// ---------------------------------------------------------------------------
// Suelo, ENSO y referencias
// ---------------------------------------------------------------------------

export function textoAporteSuelo(suelo: number): TextoConNivel {
  if (suelo >= 75) return { texto: 'Muy bueno', nivel: 'bueno' }
  if (suelo >= 55) return { texto: 'Bueno', nivel: 'bueno' }
  if (suelo >= 35) return { texto: 'Regular', nivel: 'neutro' }
  return { texto: 'Malo', nivel: 'malo' }
}

const FASES: Record<FaseEnsoId, { singular: string; plural: string }> = {
  nina: { singular: 'La Niña (años más secos)', plural: 'con La Niña (años más secos)' },
  nino: { singular: 'El Niño (años más húmedos)', plural: 'con El Niño (años más húmedos)' },
  neutro: { singular: 'año neutro (ni Niño ni Niña)', plural: 'neutras (ni Niño ni Niña)' },
}

export function textoFaseEnso(fase: FaseEnsoId): string {
  return FASES[fase].singular
}

/** "Comparamos con 12 campañas con El Niño (años más húmedos) desde 1981 en esta zona." */
export function textoComparamosCon(aniosEvaluados: number | null | undefined, fase: FaseEnso | null | undefined): string | null {
  if (!aniosEvaluados) return null
  const fasePlural = fase ? ` ${FASES[fase.fase].plural}` : ''
  const desde = fase ? ` desde ${fase.anios_analogos_desde}` : ''
  return `Comparamos con ${aniosEvaluados} campañas${fasePlural}${desde} en esta zona.`
}

/** Fuente de "lo normal" y aviso de que el lote puede rendir distinto. */
export function textoReferenciaZona(dep: DepartamentoReferencia | null | undefined): string | null {
  if (!dep) return null
  const lejos = dep.distancia_km > 30 ? ` (el departamento más cercano, a ${Math.round(dep.distancia_km)} km)` : ''
  return `Lo normal de la zona es el promedio de ${dep.nombre} (${dep.provincia})${lejos} según el Ministerio de Agricultura (MAGyP). Tu lote puede rendir distinto.`
}

export const TEXTO_COBERTURA_SIN_RINDE =
  'Cultivo de servicio: no se cosecha, su valor está en el suelo y el agua que deja.'

// ---------------------------------------------------------------------------
// Estados sin backend (FRONT-36, tabla de estados)
// ---------------------------------------------------------------------------

const FUENTES: Record<string, string> = {
  nasa_power: 'los datos satelitales de NASA',
  soilgrids: 'el mapa de suelos',
  srtm: 'el relieve del terreno',
}

export function nombreFuente(fuente: string | null | undefined): string {
  return (fuente && FUENTES[fuente]) || 'un servicio de datos externo'
}

/** "12/11 a las 10:40" a partir de una fecha ISO. */
export function fechaHoraCorta(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const dd = String(d.getDate()).padStart(2, '0')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${dd}/${mm} a las ${hh}:${mi}`
}

// ---------------------------------------------------------------------------
// Seguimiento de campaña (FRONT-37)
// ---------------------------------------------------------------------------

/** "2026-01-06" → "6/1". */
export function diaMes(iso: string): string {
  const [, m, d] = iso.split('-').map(Number)
  return Number.isNaN(m) || Number.isNaN(d) ? iso : `${d}/${m}`
}

const SEMANAS_PERIODO = 13

function etapaQueDefine(campana: 'invierno' | 'verano'): string {
  return campana === 'invierno' ? 'espigazón y llenado de granos' : 'floración y llenado de granos'
}

export interface DatosEtapa {
  etapa: 'previa' | 'en_curso' | 'terminado'
  campana: 'invierno' | 'verano'
  fecha_siembra: string
  inicio_periodo_critico: string
  fin_periodo_critico: string
  dias_observados: number
  dias_periodo_critico: number
}

export function textoEncabezadoSiembra(nombreCultivo: string, fechaSiembra: string): string {
  return `${nombreCultivo} sembrado el ${diaMes(fechaSiembra)}`
}

/** Texto de la etapa y semana actual (tabla de FRONT-37). */
export function textoEtapa(s: DatosEtapa): string {
  const define = etapaQueDefine(s.campana)
  if (s.etapa === 'previa') {
    return `El período que define el rinde (${define}) arranca alrededor del ${diaMes(s.inicio_periodo_critico)}. Hasta entonces, el riesgo es el mismo que al sembrar.`
  }
  if (s.etapa === 'terminado') {
    return `El período que define el rinde terminó el ${diaMes(s.fin_periodo_critico)}. Lo que queda depende de la cosecha.`
  }
  const semana = Math.max(1, Math.ceil(s.dias_observados / 7))
  return `Semana ${semana} de ${SEMANAS_PERIODO} del período que define el rinde (${define}).`
}

export interface TextoEvolucion {
  texto: string
  flecha: '▲' | '▼' | '='
  cambio: string
  nivel: Nivel
}

/** "Riesgo de año malo: 5 de cada 10 (al sembrar era 3 de cada 10) ▲ subió". */
export function textoEvolucion(
  probSiembra: number | null,
  probHoy: number | null,
  probTipica: number | null
): TextoEvolucion | null {
  if (probHoy == null) return null
  const base = probSiembra ?? probTipica
  const referencia = probSiembra != null ? 'al sembrar era' : 'lo habitual es'
  const texto = `${frecuencia(probHoy)}${base != null ? ` (${referencia} ${frecuencia(base)})` : ''}`
  if (base == null) return { texto, flecha: '=', cambio: '', nivel: 'neutro' }
  // La flecha sigue a lo que se lee: si las dos frecuencias se escriben igual, "se mantiene".
  if (frecuencia(probHoy) === frecuencia(base)) return { texto, flecha: '=', cambio: 'se mantiene', nivel: 'neutro' }
  if (probHoy > base) return { texto, flecha: '▲', cambio: 'subió', nivel: 'malo' }
  return { texto, flecha: '▼', cambio: 'bajó', nivel: 'bueno' }
}

export function comparacionLluvia(mm: number, normal: number): string {
  if (normal <= 0) return mm > 0 ? 'más que lo normal' : 'parecido a lo normal'
  const r = mm / normal
  if (r < 0.7) return 'bastante menos que lo normal'
  if (r < 0.9) return 'algo menos que lo normal'
  if (r <= 1.1) return 'parecido a lo normal'
  if (r <= 1.3) return 'algo más que lo normal'
  return 'bastante más que lo normal'
}

/** "Desde el 6/1 llovieron 85 mm, bastante menos que lo normal para estas fechas (171 mm), y hubo 9 días de más de 34 °C." */
export function textoPorQue(o: {
  desde: string
  lluvia_mm: number
  lluvia_normal_mm: number | null
  dias_calor: number
  heladas: number
  tormentas: number
}): string {
  const mm = Math.round(o.lluvia_mm)
  let texto = `Desde el ${diaMes(o.desde)} llovieron ${mm} mm`
  if (o.lluvia_normal_mm != null) {
    texto += `, ${comparacionLluvia(o.lluvia_mm, o.lluvia_normal_mm)} para estas fechas (lo normal es ${Math.round(o.lluvia_normal_mm)} mm)`
  }
  const extras: string[] = []
  if (o.dias_calor > 0) extras.push(`${o.dias_calor} ${o.dias_calor === 1 ? 'día' : 'días'} de más de 34 °C`)
  if (o.heladas > 0) extras.push(`${o.heladas} ${o.heladas === 1 ? 'helada' : 'heladas'}`)
  if (o.tormentas > 0) extras.push(`${o.tormentas} ${o.tormentas === 1 ? 'tormenta fuerte' : 'tormentas fuertes'} (más de 50 mm)`)
  if (extras.length > 0) {
    texto += `, y hubo ${extras.length === 1 ? extras[0] : `${extras.slice(0, -1).join(', ')} y ${extras[extras.length - 1]}`}`
  }
  return `${texto}.`
}

export function textoUltimoDato(fechaUltimoDato: string): string {
  return `Último dato satelital: ${diaMes(fechaUltimoDato)} (los datos llegan con 3 a 7 días de atraso).`
}

export const TEXTO_LO_QUE_NO_VE =
  'Usa clima regional: no ve tormentas locales, plagas, enfermedades ni el manejo del lote.'
