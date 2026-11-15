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

/** Antecesor del lote: un cultivo o barbecho (lote sin cultivo en la campaña anterior). */
export type CultivoAnterior = CultivoId | 'barbecho'

export type ObjetivoProductor =
  | 'resiliencia_hidroclimatica'
  | 'conservacion_suelo'
  | 'equilibrio'

export type RiesgoNivel = 'bajo' | 'medio' | 'alto' | 'critico'

export type RiesgoTermicoVerano =
  | 'bajo'
  | 'medio'
  | 'moderado'
  | 'alto'
  | 'critico'
  | 'extremo'

export interface SimulacionWhatIf {
  /** Opcional (0-100): si es null, usa el dato real de NASA POWER (GWETROOT) */
  override_humedad_radicular_pct: number | null
  /** Opcional (-50 a +50): para simular campañas más secas o más húmedas */
  variacion_lluvia_esperada_pct: number
}

export interface SimulateRequest {
  coordenadas: Coordenadas
  campana: Campana
  cultivo_anterior: CultivoAnterior
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
  materia_organica_g_kg?: number | null
  condicion_rotacion_previa: string
}

export interface TopografiaTelemetria {
  elevacion_m: number
  pendiente_terreno_pct: number
  fuente: string
  fuente_elevacion?: string | null
  localidad_fallback: string | null
  distancia_fuente_km: number
  reintentar_srtm?: boolean
}

export interface PerfilSueloTelemetria {
  textura_predominante: string | null
  carbono_organico_g_kg: number | null
  materia_organica_g_kg?: number | null
  condicion_rotacion_previa?: string | null
  arcilla_pct: number | null
  arena_pct: number | null
  limo_pct: number | null
  ph: number | null
  fuente: string
  localidad_fallback: string | null
  distancia_fuente_km: number
  reintentar_soilgrids?: boolean
}

export interface TelemetriaNasaInfo {
  fecha_ultimo_dato_valido: string
  indice_humedad_radicular_pct: number
  indice_humedad_superficial_pct: number
  tendencia_humedad_15d_pct?: number
  anomalia_lluvia_90d_pct: number | null
  frecuencia_tormentas_extremas_90d?: number
  riesgo_termico_verano: RiesgoTermicoVerano | string | null
}

export interface TelemetryResponse {
  ubicacion: Coordenadas
  telemetria_nasa: TelemetriaNasaInfo | null
  topografia_srtm: TopografiaTelemetria | null
  perfil_suelo: PerfilSueloTelemetria
  advertencias?: string[]
}

export interface FieldCampaign {
  id: string
  field_id: string
  user_id: string
  campana: Campana
  cultivo: string
  fecha_inicio: string
  fecha_fin: string | null
  rinde_kg_ha: number | null
  resultado_notas: string | null
  created_at: string
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
  /** La ventana de siembra de este cultivo ya terminó (ML-7). */
  fuera_de_ventana_siembra?: boolean
  /** Motivo por el que hoy no se puede sembrar (lote ocupado o ventana cerrada); null si se puede (ML-11). */
  motivo_no_sembrable?: string | null
  score_hidroclimatico_p10?: number
  anios_desfavorables?: number
  anios_evaluados?: number
}

export interface SimulateResponse {
  ubicacion: Coordenadas
  telemetria_nasa: TelemetriaNasa
  perfil_suelo: PerfilSuelo
  recomendacion_principal: RecomendacionPrincipal
  ranking_cultivos: RankingCultivoItem[]
  advertencias?: string[]
}

// ============================================================================
// TIPOS DE SOPORTE GIS, LOTES DEMO Y CAPAS NASA GIBS
// ============================================================================

export type SelectionMode = 'demo' | 'polygon'

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

// ============================================================================
// CONTRATOS DE AUTENTICACIÓN (BACK-3: /api/v1/auth/*)
// ============================================================================

export interface AuthRegisterRequest {
  email: string
  password: string
  nombre: string
}

export interface AuthLoginRequest {
  email: string
  password: string
}

export interface UserProfile {
  id: string
  email: string
  nombre: string
  /** null/[] = el usuario aún no completó el filtro inicial de provincias. */
  provincias?: string[] | null
  created_at?: string | null
}

export interface UserUpdateRequest {
  nombre?: string
  email?: string
  password?: string
}

export interface AuthResponse {
  access_token: string | null
  refresh_token?: string | null
  token_type?: string
  user?: UserProfile
  profile?: UserProfile
  requiere_confirmacion_email?: boolean
}

// ============================================================================
// CONTRATOS DE GESTIÓN DE CAMPOS / LOTES (BACK-4: /api/v1/fields)
// ============================================================================

export interface UserField {
  id: string
  user_id?: string
  nombre: string
  lat: number
  lon: number
  hectareas: number | null
  created_at?: string
  polygon?: [number, number][] | null
  // Datos propios de suelo (SoilGrids / respaldo regional + materia orgánica)
  ph?: number | null
  limo_pct?: number | null
  arena_pct?: number | null
  arcilla_pct?: number | null
  textura_predominante?: string | null
  carbono_organico_g_kg?: number | null
  materia_organica_g_kg?: number | null
  suelo_fuente?: string | null
  suelo_advertencias?: string[]
  suelo_localidad_fallback?: string | null
  suelo_distancia_fuente_km?: number | null
  reintentar_soilgrids?: boolean
  // Datos propios de topografía (SRTM / respaldo regional)
  elevacion_m?: number | null
  pendiente_terreno_pct?: number | null
  fuente_elevacion?: string | null
  topo_fuente?: string | null
  topo_advertencias?: string[]
  topo_localidad_fallback?: string | null
  topo_distancia_fuente_km?: number | null
  reintentar_srtm?: boolean
}

export interface FieldCreateRequest {
  nombre: string
  lat: number
  lon: number
  hectareas?: number | null
  polygon?: [number, number][] | null
}

export interface FieldUpdateRequest {
  nombre?: string
  lat?: number
  lon?: number
  hectareas?: number | null
  polygon?: [number, number][] | null
}
