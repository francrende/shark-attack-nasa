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
    titulo: 'Resiliencia Hidroclimática',
    subtitulo: '75% Clima/Agua NASA · 25% Suelo — Prioriza estabilidad ante sequía o calor',
    pesoClima: 0.75,
    pesoSuelo: 0.25,
  },
  equilibrio: {
    titulo: 'Equilibrio Integral',
    subtitulo: '50% Clima/Agua NASA · 50% Suelo — Balance entre seguridad hídrica y rotación',
    pesoClima: 0.5,
    pesoSuelo: 0.5,
  },
  conservacion_suelo: {
    titulo: 'Conservación del Suelo',
    subtitulo: '30% Clima/Agua NASA · 70% Suelo — Prioriza carbono, rastrojo y cortar monocultivo',
    pesoClima: 0.3,
    pesoSuelo: 0.7,
  },
}

// ============================================================================
// CAPAS SATELITALES NASA GIBS (Sección 3.2 de CONTEXT.md)
// ============================================================================

export const NASA_GIBS_LAYERS: GibsLayerConfig[] = [
  {
    id: 'modis_true_color',
    name: 'NASA MODIS Terra — True Color (Reflectancia Corregida)',
    shortLabel: 'NASA True Color',
    nasaLayerIdentifier: 'MODIS_Terra_CorrectedReflectance_TrueColor',
    description:
      'Imagen satelital óptica real de la NASA actualizada diariamente (250 m) combinada con detalle de lote.',
    format: 'jpg',
    tileMatrixSet: 'GoogleMapsCompatible_Level9',
    maxNativeZoom: 9,
    defaultOpacity: 0.45,
    category: 'satellite',
  },
  {
    id: 'smap_root_zone',
    name: 'NASA SMAP L4 — Humedad en Zona Radicular',
    shortLabel: 'SMAP Humedad Radicular',
    nasaLayerIdentifier: 'SMAP_L4_Analyzed_Root_Zone_Soil_Moisture',
    description:
      'Fracción de humedad asimilada hasta 1 metro de profundidad por la misión SMAP (9 km).',
    format: 'png',
    tileMatrixSet: 'GoogleMapsCompatible_Level6',
    maxNativeZoom: 6,
    defaultOpacity: 0.65,
    category: 'water',
    legendMinLabel: 'Seco (< 20%)',
    legendMaxLabel: 'Saturado (> 80%)',
    legendGradient: 'linear-gradient(90deg, #F05D23 0%, #D99B26 40%, #4A7B9D 75%, #2E5670 100%)',
  },
  {
    id: 'modis_ndvi',
    name: 'NASA MODIS Terra — Índice de Vegetación (NDVI 8-Day)',
    shortLabel: 'MODIS NDVI (Verdor)',
    nasaLayerIdentifier: 'MODIS_Terra_NDVI_8Day',
    description:
      'Biomasa fotosintéticamente activa y cobertura vegetal acumulada cada 8 días (250 m).',
    format: 'png',
    tileMatrixSet: 'GoogleMapsCompatible_Level9',
    maxNativeZoom: 9,
    defaultOpacity: 0.65,
    category: 'vegetation',
    legendMinLabel: 'Suelo desnudo (0.1)',
    legendMaxLabel: 'Cobertura densa (0.9)',
    legendGradient: 'linear-gradient(90deg, #8C5A3C 0%, #D99B26 35%, #8AA15B 70%, #4B5B2D 100%)',
  },
  {
    id: 'modis_lst_day',
    name: 'NASA MODIS Terra — Temperatura Superficial (LST Día)',
    shortLabel: 'MODIS Temp. Superficial',
    nasaLayerIdentifier: 'MODIS_Terra_Land_Surface_Temp_Day',
    description:
      'Temperatura radiométrica de la superficie terrestre para monitoreo de golpe de calor (1 km).',
    format: 'png',
    tileMatrixSet: 'GoogleMapsCompatible_Level7',
    maxNativeZoom: 7,
    defaultOpacity: 0.65,
    category: 'heat',
    legendMinLabel: 'Templado (15°C)',
    legendMaxLabel: 'Estrés Térmico (> 42°C)',
    legendGradient: 'linear-gradient(90deg, #4A7B9D 0%, #D99B26 50%, #F05D23 80%, #B8292F 100%)',
  },
  {
    id: 'imerg_precip',
    name: 'NASA GPM IMERG — Tasa de Precipitación',
    shortLabel: 'IMERG Lluvias (GPM)',
    nasaLayerIdentifier: 'IMERG_Precipitation_Rate',
    description:
      'Estimación satelital de tasa de precipitación global derivada de la constelación GPM.',
    format: 'png',
    tileMatrixSet: 'GoogleMapsCompatible_Level6',
    maxNativeZoom: 6,
    defaultOpacity: 0.65,
    category: 'water',
    legendMinLabel: '0.1 mm/h',
    legendMaxLabel: '> 25 mm/h',
    legendGradient: 'linear-gradient(90deg, #E2EFF7 0%, #6FA0C2 45%, #4A7B9D 75%, #252F14 100%)',
  },
  {
    id: 'none',
    name: 'Solo Satélite de Alta Resolución (Esri WorldImagery)',
    shortLabel: 'Solo Satélite',
    nasaLayerIdentifier: '',
    description: 'Imagen satelital óptica de alta resolución para visualizar divisiones de lotes y caminos.',
    format: 'jpg',
    tileMatrixSet: 'GoogleMapsCompatible_Level9',
    maxNativeZoom: 9,
    defaultOpacity: 0,
    category: 'satellite',
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
