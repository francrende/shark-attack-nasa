import {
  CULTIVOS_CATALOGO,
  DEMO_FIELDS,
  OBJETIVOS_PRODUCTOR_META,
} from '../data/demoFields'
import type {
  Campana,
  Coordenadas,
  CultivoAnterior,
  CultivoId,
  HistorialResponse,
  RankingCultivoItem,
  RiesgoNivel,
  SimulateRequest,
  SimulateResponse,
  TelemetryResponse,
} from '../types/api'

/**
 * Por decisión acordada en TASKS_FRONTEND.md (FRONT-1), mientras el equipo de Backend
 * desarrolla en paralelo su rama, el Frontend opera con datos simulados reactivos 100% fieles
 * al contrato JSON de la Sección 5 de CONTEXT.md.
 * Cuando el Backend esté listo, basta cambiar `USE_SIMULATED_MODE = false`.
 */
export const USE_SIMULATED_MODE = false
// VITE_API_URL es la base del backend (igual que authClient y fieldsClient).
const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')
const BACKEND_API_URL = `${API_BASE_URL}/api/v1/simulate`
const TELEMETRY_API_URL = `${API_BASE_URL}/api/v1/telemetry`

// ============================================================================
// MATRIZ DE TRANSICIÓN AGRONÓMICA Y SCORING EN FRONTEND (Secciones 4.2 a 4.4)
// ============================================================================

const CANDIDATOS_POR_CAMPANA: Record<Campana, CultivoId[]> = {
  invierno: [
    'trigo',
    'cebada',
    'vicia_cobertura',
    'avena_cobertura',
    'camelina',
  ],
  verano: [
    'sorgo',
    'maiz_tardio',
    'girasol',
    'maiz_temprano',
    'soja_primera',
    'soja_segunda',
  ],
}

/**
 * Calcula el puntaje de salud del suelo y rotación (S_suelo de 0 a 100)
 * según la transición `cultivo_anterior -> cultivo_candidato` y el carbono orgánico.
 */
function computeSoilScore(
  cultivoAnterior: CultivoAnterior,
  cultivoCandidato: CultivoId,
  socGKg: number
): number {
  const famAnterior =
    cultivoAnterior === 'barbecho'
      ? 'barbecho'
      : (CULTIVOS_CATALOGO[cultivoAnterior]?.familia ?? 'leguminosa')
  const famCandidato = CULTIVOS_CATALOGO[cultivoCandidato]?.familia ?? 'graminea'

  // Penalización fuerte al monocultivo directo
  if (cultivoAnterior === cultivoCandidato) {
    return 20
  }

  // Soja -> Soja (ej. soja_primera -> soja_segunda o viceversa)
  if (
    (cultivoAnterior === 'soja_primera' || cultivoAnterior === 'soja_segunda') &&
    (cultivoCandidato === 'soja_primera' || cultivoCandidato === 'soja_segunda')
  ) {
    return 24
  }

  let baseScore = 70

  // Leguminosa (Soja / Vicia) -> Gramínea (Sorgo, Maíz, Trigo, Cebada, Avena): rotación ideal C/N
  if (famAnterior === 'leguminosa' && famCandidato === 'graminea') {
    if (cultivoCandidato === 'sorgo' || cultivoCandidato === 'maiz_tardio') {
      baseScore = 95
    } else if (cultivoCandidato === 'maiz_temprano') {
      baseScore = 92
    } else {
      baseScore = 90
    }
  } else if (famAnterior === 'leguminosa' && famCandidato === 'oleaginosa') {
    baseScore = 76
  } else if (famAnterior === 'graminea' && famCandidato === 'leguminosa') {
    // Gramínea -> Vicia o Soja de 2da/1ra aprovecha fijación biológica y corta ciclo de enfermedades
    if (cultivoCandidato === 'vicia_cobertura') {
      baseScore = 94
    } else if (cultivoCandidato === 'soja_segunda') {
      baseScore = 86
    } else {
      baseScore = 82
    }
  } else if (famAnterior === 'graminea' && famCandidato === 'graminea') {
    // Gramínea tras gramínea requiere más Nitrógeno, pero aporta mucho carbono
    baseScore = 64
  } else if (famCandidato === 'crucifera') {
    baseScore = 78
  }

  // Ajuste por nivel de Carbono Orgánico (SOC): si el lote tiene bajo SOC (< 17 g/kg),
  // premiamos aún más a las gramíneas y coberturas y penalizamos cultivos extractivos
  if (socGKg < 17.5) {
    if (famCandidato === 'graminea' || cultivoCandidato === 'vicia_cobertura') {
      baseScore = Math.min(98, baseScore + 4)
    } else if (
      cultivoCandidato === 'soja_primera' ||
      cultivoCandidato === 'soja_segunda'
    ) {
      baseScore = Math.max(18, baseScore - 10)
    }
  }

  return Math.round(baseScore * 10) / 10
}

/**
 * Calcula el puntaje de aptitud hidroclimática (S_hidroclimatico de 0 a 100)
 * emulando las curvas agroclimáticas FAO-56 + NASA POWER (Sección 4.2).
 */
function computeHydroclimaticScore(
  cultivoCandidato: CultivoId,
  gwetrootPct: number,
  anomaliaLluviaPct: number,
  riesgoTermico: string,
  arcillaPct: number
): number {
  // Índice hídrico combinado (saturación radicular + efecto de anomalía de lluvia)
  const ofertaHidricaEfectiva = Math.max(
    5,
    Math.min(100, gwetrootPct + anomaliaLluviaPct * 0.45)
  )

  const penalizacionCalor =
    riesgoTermico === 'extremo'
      ? 18
      : riesgoTermico === 'alto'
        ? 11
        : riesgoTermico === 'moderado'
          ? 4
          : 0

  // Bonus de retención en suelos francos/arcillosos equilibrados (24% a 30%)
  const bonusRetencion = arcillaPct >= 24 && arcillaPct <= 32 ? 3 : 0

  let score = 70

  switch (cultivoCandidato) {
    case 'sorgo': {
      // Muy rústico y eficiente en sequía (30-55% humedad radicular) y resistente al calor
      if (ofertaHidricaEfectiva < 45) {
        score = 84 + (ofertaHidricaEfectiva / 45) * 6 - penalizacionCalor * 0.2
      } else {
        score = 88 - Math.max(0, (ofertaHidricaEfectiva - 75) * 0.3)
      }
      break
    }
    case 'maiz_tardio': {
      // Escapa al estrés térmico de enero, muy plástico en reservas medias (32-65%)
      score =
        66 +
        Math.min(26, ofertaHidricaEfectiva * 0.42) -
        penalizacionCalor * 0.35 +
        bonusRetencion
      break
    }
    case 'girasol': {
      // Raíz pivotante tolerante a déficit hídrico moderado y calor
      score =
        76 +
        Math.min(16, ofertaHidricaEfectiva * 0.25) -
        Math.max(0, (ofertaHidricaEfectiva - 72) * 0.45) -
        penalizacionCalor * 0.25
      break
    }
    case 'maiz_temprano': {
      // Altísimo potencial con buena agua (> 55%), pero cae abruptamente con sequía + calor en floración
      if (ofertaHidricaEfectiva >= 55) {
        score = 86 + (ofertaHidricaEfectiva - 55) * 0.3 - penalizacionCalor * 0.5
      } else {
        score =
          38 +
          (ofertaHidricaEfectiva / 55) * 34 -
          penalizacionCalor * 0.9 +
          bonusRetencion
      }
      break
    }
    case 'soja_primera': {
      // Sensible a déficit hídrico estival severo
      score =
        42 +
        Math.min(44, ofertaHidricaEfectiva * 0.62) -
        penalizacionCalor * 0.65
      break
    }
    case 'soja_segunda': {
      // Requiere buena humedad superficial y recarga estival
      score =
        38 +
        Math.min(45, ofertaHidricaEfectiva * 0.6) -
        penalizacionCalor * 0.7
      break
    }
    case 'trigo': {
      score = 52 + Math.min(42, ofertaHidricaEfectiva * 0.65) + bonusRetencion
      break
    }
    case 'cebada': {
      score = 58 + Math.min(36, ofertaHidricaEfectiva * 0.58)
      break
    }
    case 'vicia_cobertura': {
      score = 68 + Math.min(26, ofertaHidricaEfectiva * 0.42)
      break
    }
    case 'avena_cobertura': {
      score = 72 + Math.min(22, ofertaHidricaEfectiva * 0.35)
      break
    }
    case 'camelina': {
      // Muy tolerante a perfiles invernales más secos
      score =
        78 +
        Math.min(14, ofertaHidricaEfectiva * 0.25) -
        Math.max(0, (ofertaHidricaEfectiva - 70) * 0.35)
      break
    }
  }

  return Math.round(Math.max(12, Math.min(98, score)) * 10) / 10
}

function classifyRisk(
  scoreFinal: number,
  scoreHidro: number,
  cultivo: CultivoId,
  riesgoTermico: string
): RiesgoNivel {
  if (
    cultivo === 'maiz_temprano' &&
    scoreHidro < 62 &&
    (riesgoTermico === 'alto' || riesgoTermico === 'extremo')
  ) {
    return 'critico'
  }
  if (scoreFinal >= 78 && scoreHidro >= 68) return 'bajo'
  if (scoreFinal >= 65) return 'medio'
  if (scoreFinal >= 45) return 'alto'
  return 'critico'
}

function buildSuggestedSequence(
  campana: Campana,
  ganador: CultivoId,
  segundo: CultivoId
): string {
  const nombreGanador = CULTIVOS_CATALOGO[ganador]?.nombre ?? ganador
  const nombreSegundo = CULTIVOS_CATALOGO[segundo]?.nombre ?? segundo

  if (campana === 'verano') {
    if (ganador === 'sorgo' || ganador === 'maiz_tardio') {
      return 'Sorgo o Maíz tardío (verano)'
    }
    return `${nombreGanador} o ${nombreSegundo} (verano)`
  }
  return `${nombreGanador} o ${nombreSegundo} (invierno)`
}

/**
 * Encuentra el perfil regional más cercano a las coordenadas elegidas o interpola variaciones
 * suaves si el usuario hace clic libre o dibuja un polígono nuevo en el mapa.
 */
function resolveTelemetryAndSoilForCoords(lat: number, lon: number) {
  let closest = DEMO_FIELDS[0]
  let minDistance = Number.POSITIVE_INFINITY

  for (const field of DEMO_FIELDS) {
    const dLat = lat - field.centroide.lat
    const dLon = lon - field.centroide.lon
    const dist = Math.sqrt(dLat * dLat + dLon * dLon)
    if (dist < minDistance) {
      minDistance = dist
      closest = field
    }
  }

  // Si está exactamente en el lote demo (distancia < 0.03 grados), devolvemos los datos exactos del lote
  if (minDistance < 0.03) {
    return {
      telemetria: { ...closest.telemetriaBase },
      suelo: { ...closest.sueloBase },
    }
  }

  // Si hizo clic en otro punto del mapa o dibujó un lote nuevo, aplicamos un gradiente geográfico realista:
  // Hacia el oeste (menor longitud, más continental) baja la humedad y sube la amplitud térmica;
  // Hacia el sur (menor latitud) baja el estrés térmico estival.
  const deltaLon = lon - closest.centroide.lon
  const deltaLat = lat - closest.centroide.lat

  const humedadRadicular = Math.round(
    Math.max(
      16,
      Math.min(
        85,
        closest.telemetriaBase.indice_humedad_radicular_pct +
          deltaLon * 4.2 -
          deltaLat * 1.5
      )
    ) * 10
  ) / 10

  const humedadSuperficial = Math.round(
    Math.max(12, Math.min(82, humedadRadicular - 4.5)) * 10
  ) / 10

  const anomaliaLluvia = Math.round(
    Math.max(
      -45,
      Math.min(35, closest.telemetriaBase.anomalia_lluvia_90d_pct + deltaLon * 5.0)
    ) * 10
  ) / 10

  const riesgoTermico =
    lat > -33.2 && humedadRadicular < 32
      ? 'extremo'
      : lat > -35.0 && humedadRadicular < 42
        ? 'alto'
        : lat < -36.8
          ? 'bajo'
          : 'moderado'

  const soc =
    Math.round(
      Math.max(
        13.5,
        Math.min(26.0, closest.sueloBase.carbono_organico_g_kg + deltaLon * 0.9)
      ) * 10
    ) / 10

  return {
    telemetria: {
      fecha_ultimo_dato_valido: closest.telemetriaBase.fecha_ultimo_dato_valido,
      indice_humedad_radicular_pct: humedadRadicular,
      indice_humedad_superficial_pct: humedadSuperficial,
      anomalia_lluvia_90d_pct: anomaliaLluvia,
      riesgo_termico_verano: riesgoTermico,
      arcilla_pct: closest.telemetriaBase.arcilla_pct,
    },
    suelo: {
      textura_predominante: closest.sueloBase.textura_predominante,
      carbono_organico_g_kg: soc,
      condicion_rotacion_previa: closest.sueloBase.condicion_rotacion_previa,
    },
  }
}

export function generateSimulatedResponse(
  request: SimulateRequest
): SimulateResponse {
  const { coordenadas, campana, cultivo_anterior, objetivo_productor, simulacion_what_if } =
    request

  const base = resolveTelemetryAndSoilForCoords(coordenadas.lat, coordenadas.lon)

  // Aplicar overrides de la simulación "What-If" si el usuario movió los sliders
  const gwetrootEfectivo =
    simulacion_what_if?.override_humedad_radicular_pct !== null &&
    simulacion_what_if?.override_humedad_radicular_pct !== undefined
      ? simulacion_what_if.override_humedad_radicular_pct
      : base.telemetria.indice_humedad_radicular_pct

  const variacionLluvia = simulacion_what_if?.variacion_lluvia_esperada_pct ?? 0
  const anomaliaEfectiva =
    Math.round((base.telemetria.anomalia_lluvia_90d_pct + variacionLluvia) * 10) /
    10

  const gwettopEfectivo =
    simulacion_what_if?.override_humedad_radicular_pct !== null &&
    simulacion_what_if?.override_humedad_radicular_pct !== undefined
      ? Math.round(Math.max(10, Math.min(95, gwetrootEfectivo * 0.88)) * 10) / 10
      : base.telemetria.indice_humedad_superficial_pct

  // Determinar condición de rotación previa según cultivo_anterior seleccionado
  const condicionRotacion =
    cultivo_anterior === 'soja_primera' || cultivo_anterior === 'soja_segunda'
      ? 'deficit_rastrojo_por_soja'
      : cultivo_anterior === 'vicia_cobertura'
        ? 'suelo_enriquecido_en_nitrogeno'
        : 'buena_cobertura_graminea'

  const { pesoClima, pesoSuelo } = OBJETIVOS_PRODUCTOR_META[objetivo_productor]

  const candidatos = CANDIDATOS_POR_CAMPANA[campana]

  const evaluados: (RankingCultivoItem & {
    sub_scores: { hidroclimatico: number; suelo: number }
  })[] = candidatos.map((cultivo) => {
    const hidro = computeHydroclimaticScore(
      cultivo,
      gwetrootEfectivo,
      anomaliaEfectiva,
      base.telemetria.riesgo_termico_verano,
      base.telemetria.arcilla_pct
    )
    const suelo = computeSoilScore(
      cultivo_anterior,
      cultivo,
      base.suelo.carbono_organico_g_kg
    )
    const scoreFinal =
      Math.round((pesoClima * hidro + pesoSuelo * suelo) * 10) / 10

    const riesgo = classifyRisk(
      scoreFinal,
      hidro,
      cultivo,
      base.telemetria.riesgo_termico_verano
    )

    return {
      cultivo,
      score_final: scoreFinal,
      riesgo,
      sub_scores: {
        hidroclimatico: hidro,
        suelo,
      },
    }
  })

  evaluados.sort((a, b) => b.score_final - a.score_final)

  const ganador = evaluados[0]
  const segundo = evaluados[1] ?? evaluados[0]
  const nombreGanador =
    CULTIVOS_CATALOGO[ganador.cultivo as CultivoId]?.nombre ?? ganador.cultivo
  const nombreAnterior =
    cultivo_anterior === 'barbecho'
      ? 'Barbecho'
      : (CULTIVOS_CATALOGO[cultivo_anterior]?.nombre ?? cultivo_anterior)

  const humedadRedondeada = Math.round(gwetrootEfectivo)
  const lluviaRedondeada = Math.round(anomaliaEfectiva)

  const factoresClave: string[] = [
    gwetrootEfectivo < 42
      ? `Reserva de agua en raíces ajustada (${humedadRedondeada}%): se prioriza un cultivo tolerante al déficit hídrico.`
      : `Buena disponibilidad de agua en zona radicular (${humedadRedondeada}%) para sostener el ciclo del cultivo.`,
    condicionRotacion === 'deficit_rastrojo_por_soja'
      ? `El lote proviene de ${nombreAnterior} y requiere incorporar rastrojo y sistema radicular para recuperar cobertura.`
      : `La rotación posterior a ${nombreAnterior} favorece el control de malezas y el balance de nutrientes del suelo.`,
    anomaliaEfectiva < 0
      ? `Las precipitaciones de los últimos 3 meses registraron un desvío de −${Math.abs(lluviaRedondeada)}% respecto al promedio.`
      : `Las precipitaciones de los últimos 3 meses se ubicaron un +${lluviaRedondeada}% por encima del promedio histórico.`,
  ]

  const explicacion =
    gwetrootEfectivo < 42
      ? `Se recomienda ${nombreGanador} por su mayor tolerancia al déficit hídrico (${humedadRedondeada}% en zona radicular) y su aporte estructural al suelo luego de ${nombreAnterior}. Frente a alternativas de mayor requerimiento hídrico o a la repetición del cultivo previo, alcanza ${Math.round(ganador.sub_scores.hidroclimatico)} puntos de aptitud hidroclimática y ${Math.round(ganador.sub_scores.suelo)} puntos de beneficio edáfico.`
      : `Se recomienda ${nombreGanador} dado que aprovecha eficientemente la humedad disponible en el perfil (${humedadRedondeada}% en zona radicular) y sostiene una secuencia de rotación equilibrada tras ${nombreAnterior}. Combina ${Math.round(ganador.sub_scores.hidroclimatico)} puntos de adaptación hidroclimática con ${Math.round(ganador.sub_scores.suelo)} puntos de aporte al suelo.`

  return {
    ubicacion: {
      lat: Math.round(coordenadas.lat * 10000) / 10000,
      lon: Math.round(coordenadas.lon * 10000) / 10000,
    },
    telemetria_nasa: {
      fecha_ultimo_dato_valido: base.telemetria.fecha_ultimo_dato_valido,
      indice_humedad_radicular_pct: gwetrootEfectivo,
      indice_humedad_superficial_pct: gwettopEfectivo,
      anomalia_lluvia_90d_pct: anomaliaEfectiva,
      riesgo_termico_verano: base.telemetria.riesgo_termico_verano,
    },
    perfil_suelo: {
      textura_predominante: base.suelo.textura_predominante,
      carbono_organico_g_kg: base.suelo.carbono_organico_g_kg,
      condicion_rotacion_previa: condicionRotacion,
    },
    recomendacion_principal: {
      cultivo: ganador.cultivo,
      secuencia_sugerida: buildSuggestedSequence(
        campana,
        ganador.cultivo as CultivoId,
        segundo.cultivo as CultivoId
      ),
      score_final: ganador.score_final,
      sub_scores: ganador.sub_scores,
      factores_clave_ml: factoresClave,
      explicacion,
    },
    // Modo demostración: sin probabilidades ni qq/ha (no se inventan), marcado como ejemplo.
    ranking_cultivos: evaluados,
    departamento_referencia: null,
    fase_enso: null,
    es_ejemplo: true,
  }
}

export interface FetchFieldTelemetryOptions {
  fieldId?: string | null
  token?: string | null
  signal?: AbortSignal
}

/**
 * Consulta la telemetría inmediata de un lote (`GET /api/v1/telemetry`) sin
 * requerir campaña ni cultivo antecesor ni disparar el modelo ML.
 */
export async function fetchFieldTelemetry(
  coordenadas: Coordenadas,
  optionsOrSignal?: AbortSignal | FetchFieldTelemetryOptions
): Promise<TelemetryResponse> {
  const options: FetchFieldTelemetryOptions =
    optionsOrSignal instanceof AbortSignal
      ? { signal: optionsOrSignal }
      : (optionsOrSignal ?? {})

  const url = new URL(TELEMETRY_API_URL)
  url.searchParams.set('lat', String(coordenadas.lat))
  url.searchParams.set('lon', String(coordenadas.lon))
  if (options.fieldId) {
    url.searchParams.set('field_id', options.fieldId)
  }

  const headers: Record<string, string> = {}
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`
  }

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers,
    signal: options.signal,
  })

  if (!response.ok) {
    let detail = `Error HTTP ${response.status} al consultar /api/v1/telemetry`
    try {
      const payload = (await response.json()) as { detail?: string }
      if (typeof payload?.detail === 'string' && payload.detail.trim()) {
        detail = payload.detail
      }
    } catch {
      // Conservar mensaje HTTP por defecto
    }
    throw new Error(detail)
  }

  return (await response.json()) as TelemetryResponse
}

export class SimulateApiError extends Error {
  status: number

  constructor(status: number, message?: string) {
    super(message || `Error HTTP ${status} al consultar /api/v1/simulate`)
    this.name = 'SimulateApiError'
    this.status = status
  }
}

/** Cuánto se espera a `/simulate` antes de cortar: Render Free tarda 30–60 s en despertar. */
export const TIMEOUT_SIMULACION_MS = 75_000

export type TipoErrorSimulacion = 'servicio_externo' | 'invalido' | 'sin_conexion'

/**
 * Error tipado de `/simulate` (FRONT-36): el panel decide qué mostrar según el tipo, sin caer
 * nunca a datos de ejemplo.
 */
export class SimulacionError extends Error {
  readonly tipo: TipoErrorSimulacion
  readonly fuente: string | null

  constructor(tipo: TipoErrorSimulacion, mensaje: string, fuente: string | null = null) {
    super(mensaje)
    this.name = 'SimulacionError'
    this.tipo = tipo
    this.fuente = fuente
  }
}

export interface SimulateOptions {
  token?: string | null
  signal?: AbortSignal
  timeoutMs?: number
}

function mensajeDetalle(detail: unknown): string | null {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const primero = detail[0] as { msg?: string }
    if (typeof primero?.msg === 'string') return primero.msg
  }
  return null
}

/**
 * Cliente principal de `POST /api/v1/simulate`: envía opcionalmente `field_id`
 * junto con `Authorization: Bearer <token>`, y maneja errores tipados (`401`, `404`, `422`, `503`).
 */
export async function simulateCropRotation(
  request: SimulateRequest,
  options: SimulateOptions = {}
): Promise<SimulateResponse> {
  if (USE_SIMULATED_MODE) {
    return generateSimulatedResponse(request)
  }

  const controller = new AbortController()
  const timer = window.setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? TIMEOUT_SIMULACION_MS
  )
  const cancelarDesdeAfuera = () => controller.abort()
  options.signal?.addEventListener('abort', cancelarDesdeAfuera)

  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`
  }

  const { field_id, ...rest } = request
  const bodyPayload: SimulateRequest = field_id
    ? { field_id, ...rest }
    : rest

  let response: Response
  try {
    response = await fetch(BACKEND_API_URL, {
      method: 'POST',
      headers,
      body: JSON.stringify(bodyPayload),
      signal: controller.signal,
    })
  } catch (err) {
    if (options.signal?.aborted) throw err
    throw new SimulacionError('sin_conexion', 'No pudimos conectarnos con el servidor.')
  } finally {
    window.clearTimeout(timer)
    options.signal?.removeEventListener('abort', cancelarDesdeAfuera)
  }

  if (!response.ok) {
    let cuerpo: { detail?: unknown; fuente?: unknown } = {}
    try {
      cuerpo = (await response.json()) as typeof cuerpo
    } catch {
      // Cuerpo vacío o no JSON
    }
    const detalle = mensajeDetalle(cuerpo.detail)
    if (response.status === 401 || response.status === 404 || response.status === 422) {
      throw new SimulateApiError(response.status, detalle ?? undefined)
    }
    if (response.status === 503 && typeof cuerpo.fuente === 'string') {
      throw new SimulacionError(
        'servicio_externo',
        detalle ?? 'Servicio externo no disponible.',
        cuerpo.fuente
      )
    }
    throw new SimulacionError(
      'sin_conexion',
      detalle ?? `Error HTTP ${response.status} del servidor.`
    )
  }

  return (await response.json()) as SimulateResponse
}


/**
 * Historial real del lote por campaña agrícola (`GET /api/v1/historial`, BACK-31 / FRONT-39):
 * lluvia, agua en raíces, rinde de la zona y, con sesión y campo guardado, sus cosechas.
 */
export async function fetchHistorial(
  coordenadas: Coordenadas,
  options: { fieldId?: string | null; token?: string | null; signal?: AbortSignal } = {}
): Promise<HistorialResponse> {
  const url = new URL(`${API_BASE_URL}/api/v1/historial`)
  url.searchParams.set('lat', String(coordenadas.lat))
  url.searchParams.set('lon', String(coordenadas.lon))
  if (options.fieldId && options.token) url.searchParams.set('field_id', options.fieldId)
  const headers: Record<string, string> = {}
  if (options.token) headers.Authorization = `Bearer ${options.token}`

  let response: Response
  try {
    response = await fetch(url.toString(), { method: 'GET', headers, signal: options.signal })
  } catch (err) {
    if (options.signal?.aborted) throw err
    throw new SimulacionError('sin_conexion', 'No pudimos conectarnos con el servidor.')
  }
  if (!response.ok) {
    const cuerpo = (await response.json().catch(() => ({}))) as { detail?: unknown; fuente?: unknown }
    const detalle = mensajeDetalle(cuerpo.detail)
    if (response.status === 503) {
      throw new SimulacionError(
        'servicio_externo',
        detalle ?? 'Servicio externo no disponible.',
        typeof cuerpo.fuente === 'string' ? cuerpo.fuente : 'nasa_power'
      )
    }
    if (response.status === 422) throw new SimulacionError('invalido', detalle ?? 'Ubicación inválida.')
    throw new SimulacionError('sin_conexion', detalle ?? `Error HTTP ${response.status} del servidor.`)
  }
  return (await response.json()) as HistorialResponse
}
