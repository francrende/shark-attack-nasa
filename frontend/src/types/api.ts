// ============================================================================
// CONTRATOS DE DATOS API JSON (Sección 5 de CONTEXT.md)
// ============================================================================

export interface Coordenadas {
  lat: number
  lon: number
}

export type Campana = 'invierno' | 'verano'

export type CultivoInvierno =
  | 'trigo'
  | 'cebada'
  | 'vicia_cobertura'
  | 'avena_cobertura'
  | 'camelina'

export type CultivoVerano =
  | 'maiz_temprano'
  | 'maiz_tardio'
  | 'soja_primera'
  | 'soja_segunda'
  | 'girasol'
  | 'sorgo'

export type CultivoId = CultivoInvierno | CultivoVerano

export type ObjetivoProductor =
  | 'resiliencia_hidroclimatica'
  | 'conservacion_suelo'
  | 'equilibrio'

export type RiesgoNivel = 'bajo' | 'medio' | 'alto' | 'critico'

export type RiesgoTermicoVerano = 'bajo' | 'moderado' | 'alto' | 'extremo'

export interface SimulacionWhatIf {
  /** Opcional (0-100): si es null, usa el dato real de NASA POWER (GWETROOT) */
  override_humedad_radicular_pct: number | null
  /** Opcional (-50 a +50): para simular campañas más secas o más húmedas */
  variacion_lluvia_esperada_pct: number
}

export interface SimulateRequest {
  coordenadas: Coordenadas
  campana: Campana
  cultivo_anterior: CultivoId
  objetivo_productor: ObjetivoProductor
  simulacion_what_if?: SimulacionWhatIf
}

export interface TelemetriaNasa {
  fecha_ultimo_dato_valido: string
  indice_humedad_radicular_pct: number
  indice_humedad_superficial_pct: number
  anomalia_lluvia_90d_pct: number
  riesgo_termico_verano: RiesgoTermicoVerano | string
}

export interface PerfilSuelo {
  textura_predominante: string
  carbono_organico_g_kg: number
  condicion_rotacion_previa: string
}

export interface SubScores {
  hidroclimatico: number
  suelo: number
}

export interface RecomendacionPrincipal {
  cultivo: CultivoId | string
  secuencia_sugerida: string
  score_final: number
  sub_scores: SubScores
  factores_clave_ml: string[]
  explicacion: string
}

export interface RankingCultivoItem {
  cultivo: CultivoId | string
  score_final: number
  riesgo: RiesgoNivel
  sub_scores?: SubScores
}

export interface SimulateResponse {
  ubicacion: Coordenadas
  telemetria_nasa: TelemetriaNasa
  perfil_suelo: PerfilSuelo
  recomendacion_principal: RecomendacionPrincipal
  ranking_cultivos: RankingCultivoItem[]
}

// ============================================================================
// TIPOS DE SOPORTE GIS, LOTES DEMO Y CAPAS NASA GIBS
// ============================================================================

export type SelectionMode = 'demo' | 'polygon' | 'point'

export type GibsLayerId =
  | 'none'
  | 'smap_root_zone'
  | 'modis_ndvi'
  | 'modis_lst_day'
  | 'imerg_precip'
  | 'modis_true_color'

export interface GibsLayerConfig {
  id: GibsLayerId
  name: string
  shortLabel: string
  nasaLayerIdentifier: string
  description: string
  format: 'png' | 'jpg'
  tileMatrixSet: string
  maxNativeZoom: number
  defaultOpacity: number
  category: 'water' | 'vegetation' | 'heat' | 'satellite'
  legendMinLabel?: string
  legendMaxLabel?: string
  legendGradient?: string
}

export interface DemoField {
  id: string
  nombre: string
  localidad: string
  provincia: string
  superficieHa: number
  centroide: Coordenadas
  poligono: [number, number][]
  cultivoAnteriorDefault: CultivoId
  campanaDefault: Campana
  descripcionAgronomica: string
  telemetriaBase: TelemetriaNasa & {
    arcilla_pct: number
    limo_pct: number
    arena_pct: number
    evapotranspiracion_mm_dia: number
  }
  sueloBase: PerfilSuelo
}
