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
  field_id?: string | null
  coordenadas: Coordenadas
  campana: Campana
  cultivo_anterior: CultivoAnterior
  objetivo_productor: ObjetivoProductor
  simulacion_what_if?: SimulacionWhatIf
  /**
   * Campo guardado del usuario (BACK-24; requiere token): suelo y topografía del servicio único de
   * datos del lote, y su departamento para el rinde normal (BACK-28). Estricto: 401 sin sesión, 404 si
   * el campo no es del usuario, 422 si las coordenadas no coinciden con las del campo.
   */
  field_id?: string | null
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

/** Alta de una campaña sembrada (BACK-2: POST /api/v1/fields/{id}/campaigns). fecha_inicio = siembra. */
export interface CampaignCreateRequest {
  campana: Campana
  cultivo: string
  fecha_inicio: string
  fecha_fin?: string | null
}

/** Cierre o edición de una campaña (BACK-30: PATCH). fecha_fin = cosecha; rinde_kg_ha = rinde cosechado. */
export interface CampaignUpdateRequest {
  fecha_fin?: string | null
  rinde_kg_ha?: number | null
  resultado_notas?: string | null
}

// ============================================================================
// SEGUIMIENTO DE CAMPAÑA (BACK-29 / ML-18)
// ============================================================================

export type EtapaSeguimiento = 'previa' | 'en_curso' | 'terminado'

export interface PuntoSeguimiento {
  fecha: string
  dias_observados: number
  avance: number
  promedio: number
  prob_anio_malo: number | null
  puntaje_anio_malo: number | null
  puntaje_anio_bueno: number | null
  rinde_kg_ha: RindeKgHa | null
}

export interface ClimaObservado {
  desde: string
  dias: number
  lluvia_mm: number
  lluvia_normal_mm: number | null
  dias_calor: number
  heladas: number
  tormentas: number
}

export interface SeguimientoResponse {
  campana_id: string
  cultivo: string
  campana: Campana
  fecha_siembra: string
  etapa: EtapaSeguimiento
  inicio_periodo_critico: string
  fin_periodo_critico: string
  dias_observados: number
  dias_periodo_critico: number
  fecha_ultimo_dato: string
  serie: PuntoSeguimiento[]
  observado: ClimaObservado | null
  prob_anio_malo_tipica: number | null
  anticipa_diferencias: boolean | null
  rinde_normal_kg_ha: number | null
  fase_enso_siembra: { fase: FaseEnsoId; oni: number } | null
  departamento_referencia: DepartamentoReferencia | null
  anios_analogos: number
  rango_por_avance: boolean
  calculado_el: string
  advertencias: string[]
}

export interface SubScores {
  hidroclimatico: number
  suelo: number
}

/** ML-17: rinde del departamento de referencia en kg/ha (redondeado a 50). */
export interface RindeKgHa {
  esperado: number | null
  anio_malo: number | null
  anio_bueno: number | null
  normal: number | null
  motivo_sin_dato: string | null
}

/**
 * ML-16: distribución predictiva con el error real del modelo (CONTEXT §4.8).
 * Todos opcionales: respuestas viejas o el modo de ejemplo no los traen.
 */
export interface CamposDistribucionPredictiva {
  /** Probabilidad (0–1) de rinde 15% o más bajo lo normal. null si el cultivo no anticipa diferencias. */
  prob_anio_malo?: number | null
  /** Frecuencia habitual (0–1) de años malos del cultivo. */
  prob_anio_malo_tipica?: number | null
  /** Si el sistema anticipa diferencias entre años para este cultivo (hoy: maíz y soja). */
  anticipa_diferencias?: boolean | null
  puntaje_anio_malo?: number | null
  puntaje_anio_bueno?: number | null
  rinde_kg_ha?: RindeKgHa | null
}

export interface DistribucionHidroclimatica extends CamposDistribucionPredictiva {
  promedio: number
  /** P10 del clima de los años análogos (no es el peor 10% de los rindes). */
  p10: number
  p90: number
  anios_desfavorables: number
  anios_evaluados: number
  umbral_desfavorable: number
}

export interface DepartamentoReferencia {
  codigo: string
  nombre: string
  provincia: string
  distancia_km: number
}

export type FaseEnsoId = 'nina' | 'neutro' | 'nino'

export interface FaseEnso {
  fase: FaseEnsoId
  oni: number
  anios_analogos_desde: number
}

export interface RecomendacionPrincipal {
  cultivo: CultivoId | string
  secuencia_sugerida: string
  score_final: number
  sub_scores: SubScores
  distribucion_hidroclimatica?: DistribucionHidroclimatica | null
  rinde_kg_ha?: RindeKgHa | null
  factores_clave_ml: string[]
  explicacion: string
}

export interface RankingCultivoItem extends CamposDistribucionPredictiva {
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
  /** ML-17: departamento MAGyP de referencia; null fuera de cobertura. */
  departamento_referencia?: DepartamentoReferencia | null
  /** BACK-27: fase ENSO con la que se eligieron los años análogos. */
  fase_enso?: FaseEnso | null
  /** Solo del front: respuesta del modo demostración (datos de ejemplo, no del lote). */
  es_ejemplo?: boolean
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
  reintento_en_curso?: boolean
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

// ============================================================================
// HISTORIAL DEL LOTE POR CAMPAÑA (BACK-31: GET /api/v1/historial)
// ============================================================================

export interface RindeZona {
  /** Cultivo MAGyP: trigo, cebada, maiz, soja_primera, soja_segunda, girasol, sorgo. */
  cultivo: string
  rinde_kg_ha: number
  normal_kg_ha: number | null
  vs_normal_pct: number | null
}

export interface CosechaLote {
  id: string
  cultivo: string
  fecha_siembra: string
  fecha_cosecha: string | null
  rinde_kg_ha: number | null
  en_curso: boolean
}

export interface CampanaHistorial {
  anio: number
  etiqueta: string
  completa: boolean
  meses_con_dato: number
  lluvia_mm: number | null
  lluvia_vs_normal_pct: number | null
  /** Campaña en curso: último mes completo comparado contra lo normal ("AAAA-MM"). */
  lluvia_comparada_hasta: string | null
  agua_raices_promedio_pct: number | null
  mes_mas_seco: string | null
  agua_raices_mes_mas_seco_pct: number | null
  agua_raices_mes_mas_seco_normal_pct: number | null
  rinde_zona: RindeZona[]
  cosechas_lote: CosechaLote[]
}

export interface HistorialResponse {
  ubicacion: Coordenadas
  departamento_referencia: DepartamentoReferencia | null
  normales: { lluvia_mm: number | null; agua_raices_pct: number | null; campanas_completas: number }
  campanas: CampanaHistorial[]
  advertencias: string[]
}
