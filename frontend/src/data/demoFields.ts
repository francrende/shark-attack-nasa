import { THEME_COLORS } from '../theme/mapColors'
import type {
  Campana,
  CultivoId,
  DemoField,
  GibsLayerConfig,
  ObjetivoProductor,
} from '../types/api'

// ============================================================================
// 4 LOTES DEMO EN LA REGIÓN PAMPEANA CON POLÍGONOS REALES Y PERFILES VARIADOS
// ============================================================================

export const DEMO_FIELDS: DemoField[] = [
  {
    id: 'lote-pergamino',
    nombre: 'Lote "La Estela" (Pergamino)',
    localidad: 'Pergamino',
    provincia: 'Buenos Aires',
    superficieHa: 142,
    centroide: { lat: -33.95, lon: -60.57 },
    poligono: [
      [-33.9442, -60.5775],
      [-33.9442, -60.5625],
      [-33.9558, -60.5625],
      [-33.9558, -60.5775],
    ],
    cultivoAnteriorDefault: 'soja_primera',
    campanaDefault: 'verano',
    descripcionAgronomica:
      'Zona Núcleo Pampeana. Suelo Argiudol típico (franco limoso), saliendo de Soja de 1ra con déficit de rastrojo y reserva hídrica radicular ajustada (34%).',
    telemetriaBase: {
      fecha_ultimo_dato_valido: '2026-11-08',
      indice_humedad_radicular_pct: 34.0,
      indice_humedad_superficial_pct: 28.5,
      anomalia_lluvia_90d_pct: -24.2,
      riesgo_termico_verano: 'alto',
      arcilla_pct: 26,
      limo_pct: 52,
      arena_pct: 22,
      evapotranspiracion_mm_dia: 4.8,
    },
    sueloBase: {
      textura_predominante: 'franco_limoso',
      carbono_organico_g_kg: 18.4,
      condicion_rotacion_previa: 'deficit_rastrojo_por_soja',
    },
  },
  {
    id: 'lote-venado-tuerto',
    nombre: 'Lote "San Martín" (Venado Tuerto)',
    localidad: 'Venado Tuerto',
    provincia: 'Santa Fe',
    superficieHa: 195,
    centroide: { lat: -33.745, lon: -61.968 },
    poligono: [
      [-33.7385, -61.9765],
      [-33.7385, -61.9595],
      [-33.7515, -61.9595],
      [-33.7515, -61.9765],
    ],
    cultivoAnteriorDefault: 'trigo',
    campanaDefault: 'verano',
    descripcionAgronomica:
      'Sur de Santa Fe. Excelente recarga en perfil radicular (64% SMAP) tras lluvias primaverales normales (+6.5%). Lote con buen rastrojo de Trigo y alta materia orgánica.',
    telemetriaBase: {
      fecha_ultimo_dato_valido: '2026-11-08',
      indice_humedad_radicular_pct: 64.0,
      indice_humedad_superficial_pct: 58.0,
      anomalia_lluvia_90d_pct: 6.5,
      riesgo_termico_verano: 'moderado',
      arcilla_pct: 28,
      limo_pct: 48,
      arena_pct: 24,
      evapotranspiracion_mm_dia: 4.2,
    },
    sueloBase: {
      textura_predominante: 'franco_arcillo_limoso',
      carbono_organico_g_kg: 22.1,
      condicion_rotacion_previa: 'buena_cobertura_graminea',
    },
  },
  {
    id: 'lote-marcos-juarez',
    nombre: 'Lote "El Médano" (Marcos Juárez)',
    localidad: 'Marcos Juárez',
    provincia: 'Córdoba',
    superficieHa: 168,
    centroide: { lat: -32.698, lon: -62.105 },
    poligono: [
      [-32.6915, -62.1135],
      [-32.6915, -62.0965],
      [-32.7045, -62.0965],
      [-32.7045, -62.1135],
    ],
    cultivoAnteriorDefault: 'soja_segunda',
    campanaDefault: 'verano',
    descripcionAgronomica:
      'Sudeste de Córdoba. Escenario de estrés hidroclimático severo (25% humedad radicular, anomalía de lluvias -31.5%) y alta demanda termo-evaporativa.',
    telemetriaBase: {
      fecha_ultimo_dato_valido: '2026-11-08',
      indice_humedad_radicular_pct: 25.0,
      indice_humedad_superficial_pct: 21.0,
      anomalia_lluvia_90d_pct: -31.5,
      riesgo_termico_verano: 'extremo',
      arcilla_pct: 21,
      limo_pct: 49,
      arena_pct: 30,
      evapotranspiracion_mm_dia: 5.6,
    },
    sueloBase: {
      textura_predominante: 'franco',
      carbono_organico_g_kg: 15.6,
      condicion_rotacion_previa: 'alerta_extraccion_nutrientes',
    },
  },
  {
    id: 'lote-tres-arroyos',
    nombre: 'Lote "La Reserva" (Tres Arroyos)',
    localidad: 'Tres Arroyos',
    provincia: 'Buenos Aires (Sur)',
    superficieHa: 230,
    centroide: { lat: -38.375, lon: -60.275 },
    poligono: [
      [-38.3675, -60.2855],
      [-38.3675, -60.2645],
      [-38.3825, -60.2645],
      [-38.3825, -60.2855],
    ],
    cultivoAnteriorDefault: 'girasol',
    campanaDefault: 'invierno',
    descripcionAgronomica:
      'Zona Austral / Sudeste Bonaerense. Ambiente templado con menor estrés térmico estival, humedad en perfil intermedia (49%) ideal para planificar fina o girasol/maíz tardío.',
    telemetriaBase: {
      fecha_ultimo_dato_valido: '2026-11-08',
      indice_humedad_radicular_pct: 49.0,
      indice_humedad_superficial_pct: 44.5,
      anomalia_lluvia_90d_pct: -8.0,
      riesgo_termico_verano: 'bajo',
      arcilla_pct: 23,
      limo_pct: 39,
      arena_pct: 38,
      evapotranspiracion_mm_dia: 3.6,
    },
    sueloBase: {
      textura_predominante: 'franco_arenoso',
      carbono_organico_g_kg: 19.8,
      condicion_rotacion_previa: 'rotacion_equilibrada_oleaginosa',
    },
  },
]

// ============================================================================
// METADATOS DE CULTIVOS Y ETIQUETAS AGRONÓMICAS
// ============================================================================

export interface CultivoMeta {
  id: CultivoId
  nombre: string
  campana: Campana
  familia: 'graminea' | 'leguminosa' | 'oleaginosa' | 'crucifera'
  aporteCarbonoLabel: string
  demandaHidricaLabel: string
}

export const CULTIVOS_CATALOGO: Record<CultivoId, CultivoMeta> = {
  // Campaña Fina (Invierno)
  trigo: {
    id: 'trigo',
    nombre: 'Trigo',
    campana: 'invierno',
    familia: 'graminea',
    aporteCarbonoLabel: 'Alto aporte de rastrojo C/N',
    demandaHidricaLabel: 'Media-Alta',
  },
  cebada: {
    id: 'cebada',
    nombre: 'Cebada Cervecera',
    campana: 'invierno',
    familia: 'graminea',
    aporteCarbonoLabel: 'Buen rastrojo y liberación temprana del lote',
    demandaHidricaLabel: 'Media',
  },
  vicia_cobertura: {
    id: 'vicia_cobertura',
    nombre: 'Vicia (Cultivo de Cobertura)',
    campana: 'invierno',
    familia: 'leguminosa',
    aporteCarbonoLabel: 'Fijación biológica de Nitrógeno (+80 a 120 kg N/ha)',
    demandaHidricaLabel: 'Moderada',
  },
  avena_cobertura: {
    id: 'avena_cobertura',
    nombre: 'Avena (Cultivo de Cobertura)',
    campana: 'invierno',
    familia: 'graminea',
    aporteCarbonoLabel: 'Cobertura rápida, control de malezas y macroporosidad',
    demandaHidricaLabel: 'Baja-Media',
  },
  camelina: {
    id: 'camelina',
    nombre: 'Camelina',
    campana: 'invierno',
    familia: 'crucifera',
    aporteCarbonoLabel: 'Bajo consumo hídrico y renta invernal de ciclo corto',
    demandaHidricaLabel: 'Baja',
  },
  // Campaña Gruesa (Verano)
  maiz_temprano: {
    id: 'maiz_temprano',
    nombre: 'Maíz Temprano',
    campana: 'verano',
    familia: 'graminea',
    aporteCarbonoLabel: 'Máximo volumen de rastrojo y secuestro de carbono',
    demandaHidricaLabel: 'Alta (período crítico en diciembre/enero)',
  },
  maiz_tardio: {
    id: 'maiz_tardio',
    nombre: 'Maíz Tardío',
    campana: 'verano',
    familia: 'graminea',
    aporteCarbonoLabel: 'Alto aporte de carbono con escape al estrés de enero',
    demandaHidricaLabel: 'Media-Alta (floración en febrero)',
  },
  soja_primera: {
    id: 'soja_primera',
    nombre: 'Soja de 1ra',
    campana: 'verano',
    familia: 'leguminosa',
    aporteCarbonoLabel: 'Rastrojo de rápida descomposición (baja relación C/N)',
    demandaHidricaLabel: 'Media-Alta',
  },
  soja_segunda: {
    id: 'soja_segunda',
    nombre: 'Soja de 2da (Post-Fina)',
    campana: 'verano',
    familia: 'leguminosa',
    aporteCarbonoLabel: 'Complementa gramínea invernal en secuencia intensiva',
    demandaHidricaLabel: 'Media',
  },
  girasol: {
    id: 'girasol',
    nombre: 'Girasol',
    campana: 'verano',
    familia: 'oleaginosa',
    aporteCarbonoLabel: 'Raíz pivotante profunda que explora agua subsuperficial',
    demandaHidricaLabel: 'Baja-Media (tolerante a sequía)',
  },
  sorgo: {
    id: 'sorgo',
    nombre: 'Sorgo Granífero',
    campana: 'verano',
    familia: 'graminea',
    aporteCarbonoLabel: 'Excelente rastrojo, estructura radicular y rusticidad hídrica',
    demandaHidricaLabel: 'Baja (alta eficiencia en uso del agua)',
  },
}

export const OBJETIVOS_PRODUCTOR_META: Record<
  ObjetivoProductor,
  {
    titulo: string
    subtitulo: string
    pesoClima: number
    pesoSuelo: number
  }
> = {
  resiliencia_hidroclimatica: {
    titulo: 'Seguridad frente a sequía',
    subtitulo: 'Prioriza cultivos que rindan bien con poca agua o calor fuerte.',
    pesoClima: 0.75,
    pesoSuelo: 0.25,
  },
  equilibrio: {
    titulo: 'Equilibrio',
    subtitulo: 'Balance parejo entre cuidar el agua disponible y mejorar el suelo.',
    pesoClima: 0.5,
    pesoSuelo: 0.5,
  },
  conservacion_suelo: {
    titulo: 'Cuidar el suelo',
    subtitulo: 'Prioriza dejar rastrojo, sumar materia orgánica y rotar cultivos.',
    pesoClima: 0.3,
    pesoSuelo: 0.7,
  },
}

// ============================================================================
// CAPAS SATELITALES NASA GIBS (Sección 3.2 de CONTEXT.md)
// ============================================================================

export const NASA_GIBS_LAYERS: GibsLayerConfig[] = [
  {
    id: 'none',
    name: 'Mapa satelital',
    shortLabel: 'Mapa satelital',
    nasaLayerIdentifier: '',
    description:
      'Vista limpia de alta definición para distinguir bien los alambrados, lotes y caminos rurales.',
    format: 'jpg',
    tileMatrixSet: 'GoogleMapsCompatible_Level9',
    maxNativeZoom: 9,
    defaultOpacity: 0,
    category: 'satellite',
  },
  {
    id: 'smap_root_zone',
    name: 'Reserva de Agua en el Suelo (Zona de Raíces)',
    shortLabel: 'Agua en el Suelo',
    nasaLayerIdentifier: 'SMAP_L4_Analyzed_Root_Zone_Soil_Moisture',
    description:
      'Muestra cuánta humedad hay acumulada bajo tierra (hasta 1 metro de profundidad) para las raíces del cultivo.',
    format: 'png',
    tileMatrixSet: 'GoogleMapsCompatible_Level6',
    maxNativeZoom: 6,
    defaultOpacity: 0.65,
    category: 'water',
    legendMinLabel: 'Suelo seco',
    legendMaxLabel: 'Suelo con mucha agua',
    legendGradient: `linear-gradient(90deg, ${THEME_COLORS.heatSoil} 0%, ${THEME_COLORS.goldYellow} 40%, ${THEME_COLORS.waterRain} 75%, ${THEME_COLORS.waterRainDark} 100%)`,
  },
  {
    id: 'modis_ndvi',
    name: 'Verdor y Salud de los Cultivos',
    shortLabel: 'Verdor del cultivo',
    nasaLayerIdentifier: 'MODIS_Terra_NDVI_8Day',
    description:
      'Qué tan verde, tupido y activo está el cultivo o la cobertura en el campo.',
    format: 'png',
    tileMatrixSet: 'GoogleMapsCompatible_Level9',
    maxNativeZoom: 9,
    defaultOpacity: 0.65,
    category: 'vegetation',
    legendMinLabel: 'Poca cobertura',
    legendMaxLabel: 'Cultivo muy verde',
    legendGradient: `linear-gradient(90deg, ${THEME_COLORS.earthBrown} 0%, ${THEME_COLORS.goldYellow} 35%, ${THEME_COLORS.primaryLighter} 70%, ${THEME_COLORS.primary} 100%)`,
  },
  {
    id: 'modis_lst_day',
    name: 'Calor en la Superficie del Campo',
    shortLabel: 'Calor en la tierra',
    nasaLayerIdentifier: 'MODIS_Terra_Land_Surface_Temp_Day',
    description:
      'Temperatura de la superficie del campo para detectar zonas con mucho calor durante el día.',
    format: 'png',
    tileMatrixSet: 'GoogleMapsCompatible_Level7',
    maxNativeZoom: 7,
    defaultOpacity: 0.65,
    category: 'heat',
    legendMinLabel: 'Templado',
    legendMaxLabel: 'Mucho calor',
    legendGradient: `linear-gradient(90deg, ${THEME_COLORS.waterRain} 0%, ${THEME_COLORS.goldYellow} 50%, ${THEME_COLORS.heatSoil} 80%, ${THEME_COLORS.riskCritical} 100%)`,
  },
  {
    id: 'imerg_precip',
    name: 'Mapa de Lluvias Recientes',
    shortLabel: 'Lluvias recientes',
    nasaLayerIdentifier: 'IMERG_Precipitation_Rate',
    description:
      'Dónde y cuánto llovió en los últimos días en tu zona.',
    format: 'png',
    tileMatrixSet: 'GoogleMapsCompatible_Level6',
    maxNativeZoom: 6,
    defaultOpacity: 0.65,
    category: 'water',
    legendMinLabel: 'Llovizna leve',
    legendMaxLabel: 'Lluvia fuerte',
    legendGradient: `linear-gradient(90deg, ${THEME_COLORS.waterRainSoft} 0%, ${THEME_COLORS.waterRainLight} 45%, ${THEME_COLORS.waterRain} 75%, ${THEME_COLORS.primaryDarker} 100%)`,
  },
]

/**
 * Devuelve una fecha consolidada segura para NASA GIBS (ej. 5 días atrás en formato YYYY-MM-DD)
 * evitando huecos de procesamiento de órbitas del día en curso.
 */
export function getConsolidatedGibsDate(): string {
  // Usamos una fecha satelital real consolidada de NASA GIBS (o dinámica respecto al año real)
  const fallbackConsolidatedDate = '2024-11-08'
  const now = new Date()
  if (now.getFullYear() > 2025) {
    return fallbackConsolidatedDate
  }
  const consolidated = new Date(now.getTime() - 5 * 24 * 60 * 60 * 1000)
  return consolidated.toISOString().split('T')[0]
}
