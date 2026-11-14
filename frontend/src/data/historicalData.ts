import { CULTIVOS_CATALOGO, DEMO_FIELDS } from './demoFields'
import { THEME_COLORS } from '../theme/mapColors'
import type { Coordenadas, CultivoId, GibsLayerId } from '../types/api'

export type HistoricalMetricId =
  | 'cultivos'
  | 'lluvias'
  | 'evaporacion'
  | 'temperatura'
  | 'suelo'

export interface HistoricalMetricMeta {
  id: HistoricalMetricId
  label: string
  unit: string
  category: 'decision' | 'water' | 'heat'
  helperText: string
  suggestedGibsLayer: GibsLayerId
}

export const HISTORICAL_METRICS: HistoricalMetricMeta[] = [
  {
    id: 'cultivos',
    label: 'Cultivos sembrados (rotación)',
    unit: '',
    category: 'decision',
    helperText:
      'Secuencia anual de cultivos implantados en el lote y alternancia entre gramíneas, leguminosas y oleaginosas.',
    suggestedGibsLayer: 'modis_ndvi',
  },
  {
    id: 'lluvias',
    label: 'Lluvias y agua en el suelo',
    unit: 'mm',
    category: 'water',
    helperText:
      'Precipitación acumulada anual y disponibilidad hídrica en zona radicular.',
    suggestedGibsLayer: 'smap_root_zone',
  },
  {
    id: 'evaporacion',
    label: 'Evaporación y demanda de agua del ambiente',
    unit: 'mm/día',
    category: 'water',
    helperText:
      'Demanda evaporativa diaria del ambiente asociada a radiación solar, temperatura y viento.',
    suggestedGibsLayer: 'smap_root_zone',
  },
  {
    id: 'temperatura',
    label: 'Temperatura y días de golpe de calor',
    unit: 'días > 34 °C',
    category: 'heat',
    helperText:
      'Frecuencia de jornadas con temperaturas superiores a 34 °C durante el período estival.',
    suggestedGibsLayer: 'modis_lst_day',
  },
  {
    id: 'suelo',
    label: 'Materia orgánica y salud del suelo',
    unit: 'g/kg',
    category: 'heat',
    helperText:
      'Evolución del carbono orgánico del suelo según el balance de aporte y extracción de la rotación.',
    suggestedGibsLayer: 'modis_ndvi',
  },
]

export const HISTORICAL_YEARS = [
  2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026,
] as const

export interface YearRecord {
  year: number
  /** Fecha satelital consolidada de NASA GIBS para ese año */
  gibsDate: string
  cultivoInvierno: string
  cultivoVeranoId: CultivoId
  cultivoVeranoNombre: string
  familiaCultivo: 'graminea' | 'leguminosa' | 'oleaginosa' | 'crucifera'
  estadoCampana: 'Muy buena' | 'Normal' | 'Seca' | 'Muy seca'
  lluviaAnualMm: number
  aguaRaicesPct: number
  evaporacionMmDia: number
  diasGolpeCalor: number
  tempMaxVeranoC: number
  materiaOrganicaGKg: number
}

// Secuencias de rotación de 10 años para cada lote demo
const ROTACIONES_POR_LOTE: Record<
  string,
  { invierno: string; verano: CultivoId }[]
> = {
  'lote-pergamino': [
    { invierno: 'Trigo', verano: 'soja_segunda' },
    { invierno: 'Barbecho', verano: 'maiz_temprano' },
    { invierno: 'Barbecho', verano: 'soja_primera' },
    { invierno: 'Vicia (cobertura)', verano: 'maiz_tardio' },
    { invierno: 'Barbecho', verano: 'soja_primera' },
    { invierno: 'Trigo', verano: 'soja_segunda' },
    { invierno: 'Barbecho', verano: 'sorgo' },
    { invierno: 'Vicia (cobertura)', verano: 'maiz_temprano' },
    { invierno: 'Barbecho', verano: 'soja_primera' },
    { invierno: 'Avena (cobertura)', verano: 'sorgo' },
  ],
  'lote-venado-tuerto': [
    { invierno: 'Barbecho', verano: 'maiz_temprano' },
    { invierno: 'Barbecho', verano: 'soja_primera' },
    { invierno: 'Trigo', verano: 'soja_segunda' },
    { invierno: 'Vicia (cobertura)', verano: 'maiz_temprano' },
    { invierno: 'Barbecho', verano: 'soja_primera' },
    { invierno: 'Avena (cobertura)', verano: 'maiz_tardio' },
    { invierno: 'Barbecho', verano: 'girasol' },
    { invierno: 'Trigo', verano: 'soja_segunda' },
    { invierno: 'Vicia (cobertura)', verano: 'maiz_temprano' },
    { invierno: 'Trigo', verano: 'maiz_temprano' },
  ],
  'lote-marcos-juarez': [
    { invierno: 'Barbecho', verano: 'soja_primera' },
    { invierno: 'Barbecho', verano: 'soja_primera' },
    { invierno: 'Trigo', verano: 'soja_segunda' },
    { invierno: 'Barbecho', verano: 'maiz_tardio' },
    { invierno: 'Barbecho', verano: 'soja_primera' },
    { invierno: 'Barbecho', verano: 'sorgo' },
    { invierno: 'Barbecho', verano: 'girasol' },
    { invierno: 'Vicia (cobertura)', verano: 'maiz_tardio' },
    { invierno: 'Trigo', verano: 'soja_segunda' },
    { invierno: 'Barbecho', verano: 'sorgo' },
  ],
  'lote-tres-arroyos': [
    { invierno: 'Cebada', verano: 'soja_segunda' },
    { invierno: 'Barbecho', verano: 'girasol' },
    { invierno: 'Trigo', verano: 'maiz_tardio' },
    { invierno: 'Avena (cobertura)', verano: 'girasol' },
    { invierno: 'Cebada', verano: 'sorgo' },
    { invierno: 'Trigo', verano: 'girasol' },
    { invierno: 'Barbecho', verano: 'maiz_tardio' },
    { invierno: 'Cebada', verano: 'soja_segunda' },
    { invierno: 'Avena (cobertura)', verano: 'girasol' },
    { invierno: 'Trigo', verano: 'girasol' },
  ],
}

// Variación climática anual regional (2017–2026) reflejando años húmedos y años Niña secos (ej. 2018 y 2022–2023)
const CLIMA_ANUAL_FACTOR: {
  year: number
  gibsDate: string
  rainFactor: number
  heatDaysDelta: number
  evapDelta: number
  estado: 'Muy buena' | 'Normal' | 'Seca' | 'Muy seca'
}[] = [
  {
    year: 2017,
    gibsDate: '2017-11-08',
    rainFactor: 1.08,
    heatDaysDelta: -2,
    evapDelta: -0.3,
    estado: 'Muy buena',
  },
  {
    year: 2018,
    gibsDate: '2018-11-08',
    rainFactor: 0.74,
    heatDaysDelta: 6,
    evapDelta: 0.7,
    estado: 'Seca',
  },
  {
    year: 2019,
    gibsDate: '2019-11-08',
    rainFactor: 1.12,
    heatDaysDelta: -3,
    evapDelta: -0.4,
    estado: 'Muy buena',
  },
  {
    year: 2020,
    gibsDate: '2020-11-08',
    rainFactor: 0.92,
    heatDaysDelta: 1,
    evapDelta: 0.1,
    estado: 'Normal',
  },
  {
    year: 2021,
    gibsDate: '2021-11-08',
    rainFactor: 0.86,
    heatDaysDelta: 3,
    evapDelta: 0.3,
    estado: 'Normal',
  },
  {
    year: 2022,
    gibsDate: '2022-11-08',
    rainFactor: 0.68,
    heatDaysDelta: 8,
    evapDelta: 0.9,
    estado: 'Muy seca',
  },
  {
    year: 2023,
    gibsDate: '2023-11-08',
    rainFactor: 0.64,
    heatDaysDelta: 10,
    evapDelta: 1.1,
    estado: 'Muy seca',
  },
  {
    year: 2024,
    gibsDate: '2024-11-08',
    rainFactor: 1.05,
    heatDaysDelta: -1,
    evapDelta: -0.2,
    estado: 'Muy buena',
  },
  {
    year: 2025,
    gibsDate: '2024-11-08',
    rainFactor: 0.96,
    heatDaysDelta: 1,
    evapDelta: 0.0,
    estado: 'Normal',
  },
  {
    year: 2026,
    gibsDate: '2024-11-08',
    rainFactor: 0.84,
    heatDaysDelta: 4,
    evapDelta: 0.4,
    estado: 'Seca',
  },
]

export function getHistoricalSeriesForCoords(coords: Coordenadas): YearRecord[] {
  // Encontrar el lote demo más cercano
  let closest = DEMO_FIELDS[0]
  let minDistance = Number.POSITIVE_INFINITY

  for (const field of DEMO_FIELDS) {
    const dLat = coords.lat - field.centroide.lat
    const dLon = coords.lon - field.centroide.lon
    const dist = Math.sqrt(dLat * dLat + dLon * dLon)
    if (dist < minDistance) {
      minDistance = dist
      closest = field
    }
  }

  const rotacion =
    ROTACIONES_POR_LOTE[closest.id] ?? ROTACIONES_POR_LOTE['lote-pergamino']

  const baseRainMm =
    closest.id === 'lote-venado-tuerto'
      ? 960
      : closest.id === 'lote-pergamino'
        ? 910
        : closest.id === 'lote-tres-arroyos'
          ? 780
          : 810

  const baseHeatDays =
    closest.telemetriaBase.riesgo_termico_verano === 'extremo'
      ? 14
      : closest.telemetriaBase.riesgo_termico_verano === 'alto'
        ? 11
        : closest.telemetriaBase.riesgo_termico_verano === 'moderado'
          ? 8
          : 5

  let currentSoc = closest.sueloBase.carbono_organico_g_kg - 0.6

  return CLIMA_ANUAL_FACTOR.map((clima, idx) => {
    const rot = rotacion[idx] ?? rotacion[0]
    const metaVerano = CULTIVOS_CATALOGO[rot.verano]
    const fam = metaVerano?.familia ?? 'graminea'

    // Evolución de la materia orgánica según si hubo gramínea/cobertura o monocultivo de soja
    if (fam === 'graminea' || rot.invierno.includes('Vicia')) {
      currentSoc += 0.25
    } else if (fam === 'leguminosa') {
      currentSoc -= 0.2
    } else {
      currentSoc += 0.05
    }

    const lluviaAnualMm = Math.round(baseRainMm * clima.rainFactor)
    const aguaRaicesPct = Math.max(
      18,
      Math.min(
        82,
        Math.round(
          closest.telemetriaBase.indice_humedad_radicular_pct * clima.rainFactor +
            (clima.rainFactor > 1 ? 12 : -2)
        )
      )
    )
    const evaporacionMmDia =
      Math.round(
        Math.max(
          3.1,
          closest.telemetriaBase.evapotranspiracion_mm_dia + clima.evapDelta
        ) * 10
      ) / 10

    const diasGolpeCalor = Math.max(2, baseHeatDays + clima.heatDaysDelta)
    const tempMaxVeranoC = Math.round(28 + diasGolpeCalor * 0.45)

    return {
      year: clima.year,
      gibsDate: clima.gibsDate,
      cultivoInvierno: rot.invierno,
      cultivoVeranoId: rot.verano,
      cultivoVeranoNombre: metaVerano?.nombre ?? rot.verano,
      familiaCultivo: fam,
      estadoCampana: clima.estado,
      lluviaAnualMm,
      aguaRaicesPct,
      evaporacionMmDia,
      diasGolpeCalor,
      tempMaxVeranoC,
      materiaOrganicaGKg: Math.round(currentSoc * 10) / 10,
    }
  })
}

/**
 * Calcula el color y texto que debe mostrar cada lote en el mapa para un año y variable histórica.
 * Respeta estrictamente la semántica de colores de SKILLS_FRONTEND.md §2.1.
 */
export function getLotHistoricalVisualForYear(
  coords: Coordenadas,
  year: number,
  metricId: HistoricalMetricId
): {
  fillColor: string
  strokeColor: string
  badgeText: string
  detailText: string
} {
  const series = getHistoricalSeriesForCoords(coords)
  const record =
    series.find((r) => r.year === year) ?? series[series.length - 1]

  switch (metricId) {
    case 'cultivos': {
      // Gramíneas = Verde primario; Oleaginosas = Dorado; Leguminosas = Tierra/Naranja
      const fillColor =
        record.familiaCultivo === 'graminea'
          ? THEME_COLORS.primary
          : record.familiaCultivo === 'oleaginosa'
            ? THEME_COLORS.goldYellow
            : THEME_COLORS.heatSoil
      return {
        fillColor,
        strokeColor: THEME_COLORS.primaryDark,
        badgeText: `${record.year}: ${record.cultivoVeranoNombre}`,
        detailText: `Invierno: ${record.cultivoInvierno} → Verano: ${record.cultivoVeranoNombre}`,
      }
    }
    case 'lluvias': {
      const fillColor =
        record.aguaRaicesPct >= 52
          ? THEME_COLORS.waterRainDark
          : record.aguaRaicesPct >= 38
            ? THEME_COLORS.waterRain
            : THEME_COLORS.heatSoil
      return {
        fillColor,
        strokeColor: THEME_COLORS.waterRainDark,
        badgeText: `${record.year}: ${record.lluviaAnualMm} mm (${record.aguaRaicesPct}% agua)`,
        detailText: `Lluvia anual: ${record.lluviaAnualMm} mm · Agua en raíces: ${record.aguaRaicesPct}%`,
      }
    }
    case 'evaporacion': {
      const fillColor =
        record.evaporacionMmDia >= 5.2
          ? THEME_COLORS.heatSoil
          : record.evaporacionMmDia >= 4.4
            ? THEME_COLORS.goldYellow
            : THEME_COLORS.waterRain
      return {
        fillColor,
        strokeColor: THEME_COLORS.earthBrown,
        badgeText: `${record.year}: ${record.evaporacionMmDia} mm/día`,
        detailText: `Demanda de agua del ambiente: ${record.evaporacionMmDia} mm/día`,
      }
    }
    case 'temperatura': {
      const fillColor =
        record.diasGolpeCalor >= 14
          ? THEME_COLORS.riskCritical
          : record.diasGolpeCalor >= 9
            ? THEME_COLORS.heatSoil
            : THEME_COLORS.goldYellow
      return {
        fillColor,
        strokeColor: THEME_COLORS.heatSoil,
        badgeText: `${record.year}: ${record.diasGolpeCalor} días de calor (${record.tempMaxVeranoC} °C)`,
        detailText: `${record.diasGolpeCalor} días > 34 °C · Máxima media: ${record.tempMaxVeranoC} °C`,
      }
    }
    case 'suelo': {
      const fillColor =
        record.materiaOrganicaGKg >= 20
          ? THEME_COLORS.primary
          : record.materiaOrganicaGKg >= 17.5
            ? THEME_COLORS.earthBrown
            : THEME_COLORS.heatSoil
      return {
        fillColor,
        strokeColor: THEME_COLORS.earthBrown,
        badgeText: `${record.year}: ${record.materiaOrganicaGKg} g/kg materia orgánica`,
        detailText: `Materia orgánica: ${record.materiaOrganicaGKg} g/kg · Rotación con ${record.cultivoVeranoNombre}`,
      }
    }
  }
}
