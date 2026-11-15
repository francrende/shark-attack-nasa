/**
 * Información histórica del lote (FRONT-39): solo datos reales de `GET /api/v1/historial` (BACK-31).
 *
 * Antes este archivo generaba una serie inventada (rotaciones escritas a mano y clima con factores
 * fijos). Ahora solo define las métricas de la pestaña y funciones puras que traducen los datos
 * reales a textos y colores para el panel y el mapa.
 */

import { THEME_COLORS } from '../theme/mapColors'
import type { CampanaHistorial, GibsLayerId, HistorialResponse } from '../types/api'

export type HistoricalMetricId = 'cultivos' | 'lluvias' | 'suelo'

export interface HistoricalMetricMeta {
  id: HistoricalMetricId
  label: string
  helperText: string
  suggestedGibsLayer: GibsLayerId
}

export const HISTORICAL_METRICS: HistoricalMetricMeta[] = [
  {
    id: 'cultivos',
    label: 'Cosechas del lote y rinde de la zona',
    helperText:
      'Lo que se sembró y cosechó en este lote según tus campañas guardadas, y cómo le fue a la zona cada campaña según el Ministerio de Agricultura (MAGyP).',
    suggestedGibsLayer: 'modis_ndvi',
  },
  {
    id: 'lluvias',
    label: 'Lluvia por campaña',
    helperText:
      'Lluvia total de julio a junio según NASA POWER (clima regional, no medido en el lote), contra lo normal del lugar.',
    suggestedGibsLayer: 'imerg_precip',
  },
  {
    id: 'suelo',
    label: 'Agua en las raíces',
    helperText:
      'Humedad del suelo en la zona de raíces (NASA POWER): promedio de la campaña y el mes más seco, contra lo normal.',
    suggestedGibsLayer: 'smap_root_zone',
  },
]

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

/** "2023-01" → "enero de 2023". */
export function nombreMes(aaaamm: string): string {
  const [a, m] = aaaamm.split('-').map(Number)
  return MESES[m - 1] ? `${MESES[m - 1]} de ${a}` : aaaamm
}

/** "2023-01" → "enero". */
export function nombreMesCorto(aaaamm: string): string {
  const m = Number(aaaamm.split('-')[1])
  return MESES[m - 1] ?? aaaamm
}

/** "+12%", "−37%" o "normal" (dentro de ±5%). */
export function textoDesvio(pct: number | null): string {
  if (pct == null) return ''
  if (Math.abs(pct) <= 5) return 'normal'
  return pct > 0 ? `+${pct}%` : `−${Math.abs(pct)}%`
}

export type NivelLluvia = 'muy_seca' | 'seca' | 'normal' | 'humeda' | 'muy_humeda'

export function nivelLluvia(pct: number | null): NivelLluvia | null {
  if (pct == null) return null
  if (pct <= -25) return 'muy_seca'
  if (pct <= -10) return 'seca'
  if (pct < 10) return 'normal'
  if (pct < 25) return 'humeda'
  return 'muy_humeda'
}

export const TEXTO_NIVEL_LLUVIA: Record<NivelLluvia, string> = {
  muy_seca: 'Campaña muy seca',
  seca: 'Campaña seca',
  normal: 'Lluvia normal',
  humeda: 'Campaña húmeda',
  muy_humeda: 'Campaña muy húmeda',
}

/** Campaña inicial al abrir la pestaña: la última completa (si no hay, la más reciente). */
export function campanaInicial(h: HistorialResponse | null): number | null {
  if (!h || h.campanas.length === 0) return null
  const completas = h.campanas.filter((c) => c.completa)
  return (completas[completas.length - 1] ?? h.campanas[h.campanas.length - 1]).anio
}

/**
 * Fecha de la imagen satelital (NASA GIBS) de una campaña: 15 de enero, en pleno verano. Para la
 * campaña en curso, a lo sumo 7 días atrás (las imágenes llegan con atraso).
 */
export function fechaGibsCampana(anio: number, hoy: Date = new Date()): string {
  const enero = new Date(Date.UTC(anio + 1, 0, 15))
  const tope = new Date(Date.UTC(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - 7))
  const fecha = enero > tope ? tope : enero
  return fecha.toISOString().slice(0, 10)
}

export interface VisualHistorico {
  fillColor: string
  strokeColor: string
  badgeText: string
  detailText: string
}

const NOMBRES_MAGYP: Record<string, string> = {
  trigo: 'Trigo',
  cebada: 'Cebada',
  maiz: 'Maíz',
  soja_primera: 'Soja de 1ra',
  soja_segunda: 'Soja de 2da',
  girasol: 'Girasol',
  sorgo: 'Sorgo',
}

export function nombreCultivoMagyp(cultivo: string): string {
  return NOMBRES_MAGYP[cultivo] ?? cultivo
}

/** Color y textos del lote seleccionado en el mapa para la campaña y la métrica elegidas. */
export function visualHistorico(
  c: CampanaHistorial | null,
  metric: HistoricalMetricId,
  nombreCultivo: (id: string) => string
): VisualHistorico | null {
  if (!c) return null
  switch (metric) {
    case 'lluvias': {
      const nivel = nivelLluvia(c.lluvia_vs_normal_pct)
      const fillColor =
        nivel === 'muy_seca' || nivel === 'seca'
          ? THEME_COLORS.heatSoil
          : nivel === 'humeda' || nivel === 'muy_humeda'
            ? THEME_COLORS.waterRainDark
            : THEME_COLORS.waterRain
      const desvio = textoDesvio(c.lluvia_vs_normal_pct)
      return {
        fillColor,
        strokeColor: THEME_COLORS.waterRainDark,
        badgeText: `${c.etiqueta}: ${c.lluvia_mm ?? '—'} mm${desvio ? ` (${desvio})` : ''}`,
        detailText: nivel ? TEXTO_NIVEL_LLUVIA[nivel] : 'Campaña en curso',
      }
    }
    case 'suelo': {
      const seco = c.agua_raices_mes_mas_seco_pct
      const normal = c.agua_raices_mes_mas_seco_normal_pct
      const bache = seco != null && normal != null ? seco - normal : 0
      return {
        fillColor: bache <= -8 ? THEME_COLORS.heatSoil : bache <= -3 ? THEME_COLORS.goldYellow : THEME_COLORS.waterRain,
        strokeColor: THEME_COLORS.earthBrown,
        badgeText: `${c.etiqueta}: ${c.agua_raices_promedio_pct ?? '—'}% agua en raíces`,
        detailText: c.mes_mas_seco
          ? `Mes más seco: ${nombreMes(c.mes_mas_seco)} (${seco}% contra ${normal}% normal)`
          : 'Sin dato de humedad',
      }
    }
    case 'cultivos':
    default: {
      const cosechas = c.cosechas_lote
      const texto = cosechas.length > 0 ? cosechas.map((x) => nombreCultivo(x.cultivo)).join(' → ') : 'Sin registro'
      return {
        fillColor: cosechas.length > 0 ? THEME_COLORS.primary : THEME_COLORS.earthBrown,
        strokeColor: THEME_COLORS.primaryDark,
        badgeText: `${c.etiqueta}: ${texto}`,
        detailText: cosechas.length > 0 ? 'Campañas guardadas del lote' : 'No hay campañas guardadas para esta campaña',
      }
    }
  }
}
