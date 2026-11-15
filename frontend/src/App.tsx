import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from 'react'
import {
  CheckCircle2,
  Compass,
  History,
  Info,
  User,
  X,
} from 'lucide-react'
import './App.css'
import { AuthScreen } from './components/AuthScreen'
import { BrandBlock } from './components/BrandBlock'
import { FieldsSubheader } from './components/FieldsSubheader'
import { ProvinceSelectorScreen } from './components/ProvinceSelectorScreen'
import { AccionesCampana, type DatosCierre } from './components/AccionesCampana'
import { AvisoEstadoDatos, type EstadoDatos } from './components/AvisoEstadoDatos'
import { RecommendationPanel } from './components/RecommendationPanel'
import { RegistrarSiembraForm } from './components/RegistrarSiembraForm'
import { SeguimientoCampana } from './components/SeguimientoCampana'
import {
  CampaignConfigPanel,
  WhatIfPanel,
} from './components/SimulationControls'
import { TelemetryCards } from './components/TelemetryCards'
import {
  UserSettingsModal,
  type SettingsModalScope,
} from './components/UserSettingsModal'

const HistoricalPanel = lazy(() =>
  import('./components/HistoricalPanel').then((m) => ({
    default: m.HistoricalPanel,
  }))
)
const MapView = lazy(() =>
  import('./components/MapView').then((m) => ({ default: m.MapView }))
)
import { CULTIVOS_CATALOGO, DEMO_FIELDS } from './data/demoFields'
import {
  campanaInicial,
  fechaGibsCampana,
  type HistoricalMetricId,
  visualHistorico,
} from './data/historicalData'
import {
  SimulateApiError,
  fetchFieldTelemetry,
  fetchHistorial,
  generateSimulatedResponse,
  SimulacionError,
  simulateCropRotation,
} from './services/apiClient'
import {
  claveResultado,
  guardarUltimoResultado,
  leerUltimoResultado,
} from './services/ultimoResultado'
import {
  clearStoredAuthToken,
  fetchCurrentUser,
  getStoredAuthToken,
  updateUserProvinces,
} from './services/authClient'
import {
  createUserField,
  deleteUserField,
  getUserField,
  createCampaign,
  deleteCampaign,
  fetchSeguimiento,
  listFieldCampaigns,
  listUserFields,
  loginDemoAccount,
  removeCachedFieldPolygon,
  saveFieldPolygon,
  SeguimientoError,
  updateCampaign,
  updateUserField,
} from './services/fieldsClient'
import type { SearchCameraTarget } from './components/MapView'
import type { MapSearchResult } from './services/geocodeClient'
import type {
  Campana,
  Coordenadas,
  CultivoAnterior,
  CultivoId,
  FieldCampaign,
  HistorialResponse,
  ObjetivoProductor,
  PerfilSueloTelemetria,
  SimulacionWhatIf,
  SeguimientoResponse,
  SimulateResponse,
  TelemetryResponse,
  TopografiaTelemetria,
  UserField,
  UserProfile,
} from './types/api'
import { humanizeAgronomicWarnings } from './utils/formatters'
import {
  PAMPEAN_PROVINCE_IDS,
  calculateCentroid,
  calculatePolygonAreaHa,
  getProvincesBounds,
  isPointInProvinces,
} from './utils/geo'

export type NavTabId = 'planificacion' | 'info_general' | 'historico'
type AuthStatus = 'checking' | 'authenticated' | 'demo' | 'unauthenticated'

/** Filtra los ids de provincias persistidos dejando solo los habilitados (Región Pampeana). */
function sanitizeProvinceIds(ids: string[] | null | undefined): string[] {
  const allowed: readonly string[] = PAMPEAN_PROVINCE_IDS
  return Array.from(new Set(ids ?? [])).filter((id) => allowed.includes(id))
}

/** Centro geográfico (lat/lon) de las provincias seleccionadas. */
function getProvincesCenter(provinceIds: string[]): Coordenadas {
  const [[south, west], [north, east]] = getProvincesBounds(provinceIds)
  return { lat: (south + north) / 2, lon: (west + east) / 2 }
}

function getStoredSoilFromField(
  field: UserField | null
): PerfilSueloTelemetria | null {
  if (!field) return null
  const hasAny =
    field.materia_organica_g_kg != null ||
    field.carbono_organico_g_kg != null ||
    Boolean(field.textura_predominante) ||
    field.arcilla_pct != null
  if (!hasAny) return null
  return {
    textura_predominante: field.textura_predominante ?? null,
    carbono_organico_g_kg: field.carbono_organico_g_kg ?? null,
    materia_organica_g_kg: field.materia_organica_g_kg ?? null,
    arcilla_pct: field.arcilla_pct ?? null,
    arena_pct: field.arena_pct ?? null,
    limo_pct: field.limo_pct ?? null,
    ph: field.ph ?? null,
    fuente: field.suelo_fuente ?? 'desconocida',
    localidad_fallback: field.suelo_localidad_fallback ?? null,
    distancia_fuente_km: field.suelo_distancia_fuente_km ?? 0,
    reintentar_soilgrids: field.reintentar_soilgrids,
  }
}

function getStoredTopoFromField(
  field: UserField | null
): TopografiaTelemetria | null {
  if (
    !field ||
    field.elevacion_m === null ||
    field.elevacion_m === undefined ||
    field.pendiente_terreno_pct === null ||
    field.pendiente_terreno_pct === undefined
  ) {
    return null
  }
  return {
    elevacion_m: field.elevacion_m,
    pendiente_terreno_pct: field.pendiente_terreno_pct,
    fuente: field.topo_fuente ?? 'desconocida',
    fuente_elevacion: field.fuente_elevacion ?? null,
    localidad_fallback: field.topo_localidad_fallback ?? null,
    distancia_fuente_km: field.topo_distancia_fuente_km ?? 0,
    reintentar_srtm: field.reintentar_srtm,
  }
}

/** FRONT-37: cultivos con rinde MAGyP (los únicos con seguimiento, ML-18). */
const CULTIVOS_CON_SEGUIMIENTO = new Set<string>([
  'trigo',
  'cebada',
  'maiz_temprano',
  'maiz_tardio',
  'soja_primera',
  'soja_segunda',
  'girasol',
  'sorgo',
])

export function App() {
  const defaultField = DEMO_FIELDS[0]

  const [authStatus, setAuthStatus] = useState<AuthStatus>('checking')
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null)
  const [activeToken, setActiveToken] = useState<string | null>(null)
  const [authNotice, setAuthNotice] = useState<string | null>(null)

  // Filtro previo de provincias (Región Pampeana)
  const [selectedProvinces, setSelectedProvinces] = useState<string[]>([])
  const [isProvinceFilterApplied, setIsProvinceFilterApplied] =
    useState<boolean>(false)
  const [isSavingProvinces, setIsSavingProvinces] = useState<boolean>(false)
  const [provincesError, setProvincesError] = useState<string | null>(null)

  /**
   * Usuario registrado: si el perfil ya trae provincias, salta el selector.
   * (El modo demo nunca lee provincias de BD: siempre arranca en el selector.)
   */
  const initProvincesFromProfile = (user: UserProfile) => {
    const saved = sanitizeProvinceIds(user.provincias)
    if (saved.length > 0) {
      setSelectedProvinces(saved)
      setIsProvinceFilterApplied(true)
    } else {
      setSelectedProvinces([])
      setIsProvinceFilterApplied(false)
    }
    setProvincesError(null)
  }

  useEffect(() => {
    let cancelled = false
    const token = getStoredAuthToken()
    if (!token) {
      setAuthStatus('unauthenticated')
      return
    }

    fetchCurrentUser(token)
      .then((user) => {
        if (cancelled) return
        initProvincesFromProfile(user)
        setCurrentUser(user)
        setActiveToken(token)
        setAuthStatus('authenticated')
      })
      .catch(() => {
        if (cancelled) return
        clearStoredAuthToken()
        setCurrentUser(null)
        setActiveToken(null)
        setAuthStatus('unauthenticated')
      })

    return () => {
      cancelled = true
    }
  }, [])

  // Por regla de SKILLS_FRONTEND.md §3 y §4, la app inicia directamente en 'Planificación de campaña'
  const [activeTab, setActiveTab] = useState<NavTabId>('planificacion')
  const [settingsScope, setSettingsScope] =
    useState<SettingsModalScope | null>(null)

  // Estado GIS y gestión de campos del usuario desde backend (FRONT-21)
  const [userFields, setUserFields] = useState<UserField[]>([])
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null)
  const [isFieldsLoading, setIsFieldsLoading] = useState<boolean>(false)
  const [isSavingField, setIsSavingField] = useState<boolean>(false)
  const [fieldsError, setFieldsError] = useState<string | null>(null)
  const [isDrawingNewField, setIsDrawingNewField] = useState<boolean>(false)
  const [editingPolygonField, setEditingPolygonField] =
    useState<UserField | null>(null)
  const [selectedCoords, setSelectedCoords] = useState<Coordenadas>(
    defaultField.centroide
  )
  const [customPolygon, setCustomPolygon] = useState<[number, number][]>([])
  const [mapSearchTarget, setMapSearchTarget] =
    useState<SearchCameraTarget | null>(null)
  const [fieldFocusRequestId, setFieldFocusRequestId] = useState<number>(0)

  // Estado agronómico y simulación What-If (campaña y cultivo anterior inician sin selección)
  const [campana, setCampana] = useState<Campana | null>(null)
  const [cultivoAnterior, setCultivoAnterior] = useState<CultivoAnterior | null>(null)
  const [objetivoProductor, setObjetivoProductor] =
    useState<ObjetivoProductor>('equilibrio')
  const [whatIf, setWhatIf] = useState<SimulacionWhatIf>({
    override_humedad_radicular_pct: null,
    variacion_lluvia_esperada_pct: 0,
  })
  const [simulationResult, setSimulationResult] =
    useState<SimulateResponse | null>(null)
  const [simulationError, setSimulationError] = useState<string | null>(null)
  const [simulationRetryCount, setSimulationRetryCount] = useState<number>(0)
  const [isSimulating, setIsSimulating] = useState<boolean>(false)
  // FRONT-36: estado de los datos cuando el backend no responde (nunca datos de ejemplo por error)
  const [avisoDatos, setAvisoDatos] = useState<EstadoDatos | null>(null)
  const [reintentoSimulacion, setReintentoSimulacion] = useState<number>(0)
  const [isHistoricalReady, setIsHistoricalReady] = useState<boolean>(false)
  const [hasPlanned, setHasPlanned] = useState<boolean>(false)

  // Telemetría inmediata de Info general y último cultivo guardado en BD (FRONT-34)
  const [fieldTelemetry, setFieldTelemetry] =
    useState<TelemetryResponse | null>(null)
  const [isTelemetryLoading, setIsTelemetryLoading] = useState<boolean>(false)
  const [telemetryError, setTelemetryError] = useState<string | null>(null)
  const [telemetryRetryCount, setTelemetryRetryCount] = useState<number>(0)
  const [fieldDataNotice, setFieldDataNotice] = useState<string | null>(null)
  const [latestFieldCampaign, setLatestFieldCampaign] =
    useState<FieldCampaign | null>(null)
  // Campañas guardadas del lote, de la más reciente a la más vieja (FRONT-34 / FRONT-37)
  const [fieldCampaigns, setFieldCampaigns] = useState<FieldCampaign[]>([])
  // FRONT-37: seguimiento de la campaña sembrada del lote
  const [seguimiento, setSeguimiento] = useState<SeguimientoResponse | null>(null)
  const [seguimientoCargando, setSeguimientoCargando] = useState<boolean>(false)
  const [seguimientoAviso, setSeguimientoAviso] = useState<EstadoDatos | null>(null)
  const [seguimientoReintento, setSeguimientoReintento] = useState<number>(0)

  // Estado de la pestaña 'Información histórica' (10 años en vivo con el mapa)
  // FRONT-39: campaña agrícola elegida (año de inicio, julio a junio) e historial real del lote
  const [historicalYear, setHistoricalYear] = useState<number | null>(null)
  const [historial, setHistorial] = useState<HistorialResponse | null>(null)
  const [historialCargando, setHistorialCargando] = useState<boolean>(false)
  const [historialAviso, setHistorialAviso] = useState<EstadoDatos | null>(null)
  const [historialReintento, setHistorialReintento] = useState<number>(0)
  const [historicalMetric, setHistoricalMetric] =
    useState<HistoricalMetricId>('cultivos')

  const isRotationReady = campana !== null && cultivoAnterior !== null

  // Paso 1: Apenas estén completos campaña y cultivo anterior, realiza el pedido de datos históricos
  useEffect(() => {
    setHasPlanned(false)
    setSimulationResult(null)
    setSimulationError(null)
    setAvisoDatos(null)

    if (!campana || !cultivoAnterior) {
      setIsHistoricalReady(false)
      return
    }

    let cancelled = false
    setIsHistoricalReady(false)

    const timer = window.setTimeout(() => {
      if (!cancelled) {
        setIsHistoricalReady(true)
      }
    }, 150)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [selectedCoords, campana, cultivoAnterior])

  // Paso 2: Al presionar "Planificar" (o al ajustar objetivo/What-If ya planificado), consulta la recomendación.
  // FRONT-36: si el backend falla nunca se muestran datos de ejemplo; se usa el último resultado
  // real guardado de ese lote o un aviso claro con "Reintentar".
  useEffect(() => {
    if (!hasPlanned || !campana || !cultivoAnterior) {
      setIsSimulating(false)
      return
    }

    let cancelled = false
    const controller = new AbortController()
    setSimulationError(null)
    setIsSimulating(true)
    setAvisoDatos(null)

    const conWhatIf =
      whatIf.override_humedad_radicular_pct !== null || whatIf.variacion_lluvia_esperada_pct !== 0
    const clave = claveResultado({
      fieldId: selectedFieldId,
      lat: selectedCoords.lat,
      lon: selectedCoords.lon,
      campana,
      cultivoAnterior,
      objetivo: objetivoProductor,
    })
    const guardado = conWhatIf ? null : leerUltimoResultado(clave)

    // Render Free tarda 30–60 s en despertar: a los 5 s se avisa y, si hay, se muestra lo guardado.
    const avisoDespertar = window.setTimeout(() => {
      if (cancelled) return
      setAvisoDatos({ tipo: 'despertando', consultadoEn: guardado?.consultadoEn ?? null })
      if (guardado) setSimulationResult(guardado.respuesta)
    }, 5000)

    const activeSavedField =
      !isDrawingNewField && editingPolygonField === null && selectedFieldId
        ? (userFields.find(
            (field) =>
              field.id === selectedFieldId &&
              isPointInProvinces(field.lat, field.lon, selectedProvinces)
          ) ?? null)
        : null

    const requestCoords = activeSavedField
      ? { lat: activeSavedField.lat, lon: activeSavedField.lon }
      : selectedCoords

    const timer = window.setTimeout(async () => {
      try {
        const result = await simulateCropRotation(
          {
            ...(activeSavedField ? { field_id: activeSavedField.id } : {}),
            coordenadas: requestCoords,
            coordenadas: selectedCoords,
            campana,
            cultivo_anterior: cultivoAnterior,
            objetivo_productor: objetivoProductor,
            simulacion_what_if: whatIf,
          },
          activeToken,
          controller.signal
            field_id: authStatus === 'authenticated' ? selectedFieldId : null,
          },
          { token: authStatus === 'authenticated' ? activeToken : null, signal: controller.signal }
        )
        if (!cancelled) {
          setSimulationError(null)
          setSimulationResult(result)
          setAvisoDatos(result.es_ejemplo ? { tipo: 'demo' } : null)
          if (!conWhatIf) guardarUltimoResultado(clave, result)
        }
      } catch (err) {
        if (cancelled || controller.signal.aborted) return

        if (err instanceof SimulateApiError) {
          if (err.status === 401) {
            handleLogout(
              'Su sesión expiró o dejó de ser válida. Inicie sesión nuevamente.'
            )
            return
          }
          if (err.status === 404 || err.status === 422) {
            setSimulationResult(null)
            setSimulationError('Ocurrió un error inesperado')
            return
          }
        if (cancelled) return
        if (err instanceof SimulacionError && err.tipo === 'servicio_externo') {
          setSimulationResult(null)
          setAvisoDatos({ tipo: 'servicio_externo', fuente: err.fuente })
        } else if (err instanceof SimulacionError && err.tipo === 'invalido') {
          setSimulationResult(null)
          setAvisoDatos({ tipo: 'invalido', mensaje: err.message })
        } else {
          setSimulationResult(guardado?.respuesta ?? null)
          setAvisoDatos({ tipo: 'sin_conexion', consultadoEn: guardado?.consultadoEn ?? null })
        }

        setSimulationResult(
          generateSimulatedResponse({
            coordenadas: requestCoords,
            campana,
            cultivo_anterior: cultivoAnterior,
            objetivo_productor: objetivoProductor,
            simulacion_what_if: whatIf,
          })
        )
      } finally {
        window.clearTimeout(avisoDespertar)
        if (!cancelled) {
          setIsSimulating(false)
        }
      }
    }, 150)

    return () => {
      cancelled = true
      controller.abort()
      window.clearTimeout(timer)
      window.clearTimeout(avisoDespertar)
    }
  }, [
    hasPlanned,
    selectedCoords,
    selectedFieldId,
    userFields,
    selectedProvinces,
    isDrawingNewField,
    editingPolygonField,
    activeToken,
    campana,
    cultivoAnterior,
    objetivoProductor,
    whatIf,
    simulationRetryCount,
    selectedFieldId,
    authStatus,
    activeToken,
    reintentoSimulacion,
  ])

  const handlePlan = () => {
    if (!isRotationReady) return
    setSimulationError(null)
    setHasPlanned(true)
  }

  // Telemetría inmediata de Info general al seleccionar o guardar un campo (FRONT-34 / FRONT-35)
  const selectedLat = selectedCoords.lat
  const selectedLon = selectedCoords.lon

  useEffect(() => {
    if (authStatus !== 'authenticated' && authStatus !== 'demo') return
    if (!isProvinceFilterApplied || isFieldsLoading) return
    if (isDrawingNewField || editingPolygonField !== null) return

    const controller = new AbortController()
    setFieldTelemetry(null)
    setTelemetryError(null)
    setIsTelemetryLoading(true)

    fetchFieldTelemetry(
      { lat: selectedLat, lon: selectedLon },
      {
        fieldId: selectedFieldId,
        token: activeToken,
        signal: controller.signal,
      }
    )
      .then((data) => {
        if (controller.signal.aborted) return
        setFieldTelemetry(data)
        if (selectedFieldId) {
          setUserFields((prev) =>
            prev.map((field) => {
              if (field.id !== selectedFieldId) return field
              return {
                ...field,
                ph: data.perfil_suelo.ph ?? field.ph,
                limo_pct: data.perfil_suelo.limo_pct ?? field.limo_pct,
                arena_pct: data.perfil_suelo.arena_pct ?? field.arena_pct,
                arcilla_pct: data.perfil_suelo.arcilla_pct ?? field.arcilla_pct,
                textura_predominante:
                  data.perfil_suelo.textura_predominante ??
                  field.textura_predominante,
                carbono_organico_g_kg:
                  data.perfil_suelo.carbono_organico_g_kg ??
                  field.carbono_organico_g_kg,
                materia_organica_g_kg:
                  data.perfil_suelo.materia_organica_g_kg ??
                  field.materia_organica_g_kg,
                suelo_fuente: data.perfil_suelo.fuente,
                suelo_localidad_fallback: data.perfil_suelo.localidad_fallback,
                suelo_distancia_fuente_km:
                  data.perfil_suelo.distancia_fuente_km,
                reintentar_soilgrids: data.perfil_suelo.reintentar_soilgrids,
                ...(data.topografia_srtm
                  ? {
                      elevacion_m: data.topografia_srtm.elevacion_m,
                      pendiente_terreno_pct:
                        data.topografia_srtm.pendiente_terreno_pct,
                      fuente_elevacion:
                        data.topografia_srtm.fuente_elevacion ??
                        field.fuente_elevacion,
                      topo_fuente: data.topografia_srtm.fuente,
                      topo_localidad_fallback:
                        data.topografia_srtm.localidad_fallback,
                      topo_distancia_fuente_km:
                        data.topografia_srtm.distancia_fuente_km,
                      reintentar_srtm: data.topografia_srtm.reintentar_srtm,
                    }
                  : {}),
              }
            })
          )
        }
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        setFieldTelemetry(null)
        setTelemetryError(
          err instanceof Error
            ? err.message
            : 'No fue posible obtener la telemetría del lote.'
        )
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsTelemetryLoading(false)
        }
      })

    return () => {
      controller.abort()
    }
  }, [
    authStatus,
    isProvinceFilterApplied,
    isFieldsLoading,
    isDrawingNewField,
    editingPolygonField,
    selectedFieldId,
    activeToken,
    selectedLat,
    selectedLon,
    telemetryRetryCount,
  ])

  // Último cultivo guardado en BD para el campo seleccionado (FRONT-34)
  useEffect(() => {
    if (
      (authStatus !== 'authenticated' && authStatus !== 'demo') ||
      !activeToken ||
      !selectedFieldId
    ) {
      setFieldCampaigns([])
      return
    }

    const controller = new AbortController()
    setFieldCampaigns([])

    listFieldCampaigns(activeToken, selectedFieldId, controller.signal)
      .then((campaigns) => {
        if (!controller.signal.aborted) {
          setFieldCampaigns(campaigns)
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setFieldCampaigns([])
        }
      })

    return () => {
      controller.abort()
    }
  }, [authStatus, activeToken, selectedFieldId])

  // FRONT-37: campaña sembrada en curso (la más reciente, sin fecha de fin, sembrada hace menos
  // de 9 meses y con rinde)
  const campanaEnCurso = useMemo(() => {
    const c = fieldCampaigns[0]
    if (!c || c.fecha_fin || !CULTIVOS_CON_SEGUIMIENTO.has(c.cultivo)) return null
    const dias = (Date.now() - Date.parse(`${c.fecha_inicio}T00:00:00`)) / 86_400_000
    return dias >= 0 && dias <= 270 ? c : null
  }, [fieldCampaigns])

  // FRONT-34: "último cultivo" = la campaña más reciente que no es la que está creciendo ahora.
  // La siembra en curso no es el antecesor del lote.
  const latestFieldCampaign = useMemo(
    () => fieldCampaigns.find((c) => c.id !== campanaEnCurso?.id) ?? null,
    [fieldCampaigns, campanaEnCurso]
  )

  useEffect(() => {
    setSeguimiento(null)
    setSeguimientoAviso(null)
    if (authStatus !== 'authenticated' || !activeToken || !selectedFieldId || !campanaEnCurso) {
      setSeguimientoCargando(false)
      return
    }
    const controller = new AbortController()
    setSeguimientoCargando(true)
    fetchSeguimiento(activeToken, selectedFieldId, campanaEnCurso.id, controller.signal)
      .then((res) => {
        if (!controller.signal.aborted) setSeguimiento(res)
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        if (err instanceof SeguimientoError && err.tipo === 'servicio_externo') {
          setSeguimientoAviso({ tipo: 'servicio_externo', fuente: err.fuente })
        } else if (err instanceof SeguimientoError && err.tipo === 'invalido') {
          setSeguimientoAviso({ tipo: 'invalido', mensaje: err.message })
        } else {
          setSeguimientoAviso({ tipo: 'sin_conexion' })
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setSeguimientoCargando(false)
      })
    return () => controller.abort()
  }, [authStatus, activeToken, selectedFieldId, campanaEnCurso, seguimientoReintento])

  const handleRegistrarSiembra = async (datos: {
    cultivo: CultivoId
    campana: Campana
    fechaSiembra: string
  }) => {
    if (!activeToken || !selectedFieldId) throw new Error('Iniciá sesión para registrar la siembra.')
    const creada = await createCampaign(activeToken, selectedFieldId, {
      campana: datos.campana,
      cultivo: datos.cultivo,
      fecha_inicio: datos.fechaSiembra,
    })
    setFieldCampaigns((previas) => [creada, ...previas])
  }

  // FRONT-38: cerrar la campaña en curso (cosecha y rinde real) o borrarla.
  const handleCerrarCampana = async (datos: DatosCierre) => {
    if (!activeToken || !selectedFieldId || !campanaEnCurso) return
    const cerrada = await updateCampaign(activeToken, selectedFieldId, campanaEnCurso.id, {
      fecha_fin: datos.fechaFin,
      rinde_kg_ha: datos.rindeKgHa,
      resultado_notas: datos.notas,
    })
    setFieldCampaigns((previas) => previas.map((c) => (c.id === cerrada.id ? cerrada : c)))
  }

  const handleBorrarCampana = async () => {
    if (!activeToken || !selectedFieldId || !campanaEnCurso) return
    const id = campanaEnCurso.id
    await deleteCampaign(activeToken, selectedFieldId, id)
    setFieldCampaigns((previas) => previas.filter((c) => c.id !== id))
  }

  // Telemetría base para Info general y valor real de humedad en What-If
  const baselineResult = useMemo(() => {
    return generateSimulatedResponse({
      coordenadas: selectedCoords,
      campana: campana ?? defaultField.campanaDefault,
      cultivo_anterior: cultivoAnterior ?? defaultField.cultivoAnteriorDefault,
      objetivo_productor: objetivoProductor,
      simulacion_what_if: {
        override_humedad_radicular_pct: null,
        variacion_lluvia_esperada_pct: 0,
      },
    })
  }, [
    selectedCoords,
    campana,
    cultivoAnterior,
    objetivoProductor,
    defaultField.campanaDefault,
    defaultField.cultivoAnteriorDefault,
  ])

  // FRONT-39: historial real del lote (BACK-31), al abrir la pestaña o cambiar de lote
  useEffect(() => {
    if (activeTab !== 'historico') return
    const controller = new AbortController()
    setHistorialCargando(true)
    setHistorialAviso(null)
    const conSesion = authStatus === 'authenticated' && activeToken
    fetchHistorial(selectedCoords, {
      fieldId: conSesion ? selectedFieldId : null,
      token: conSesion ? activeToken : null,
      signal: controller.signal,
    })
      .then((res) => {
        if (controller.signal.aborted) return
        setHistorial(res)
        setHistoricalYear((prev) => (prev != null && res.campanas.some((c) => c.anio === prev) ? prev : campanaInicial(res)))
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        setHistorial(null)
        if (err instanceof SimulacionError && err.tipo === 'servicio_externo') {
          setHistorialAviso({ tipo: 'servicio_externo', fuente: err.fuente })
        } else if (err instanceof SimulacionError && err.tipo === 'invalido') {
          setHistorialAviso({ tipo: 'invalido', mensaje: err.message })
        } else {
          setHistorialAviso({ tipo: 'sin_conexion' })
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setHistorialCargando(false)
      })
    return () => controller.abort()
  }, [activeTab, selectedCoords, selectedFieldId, authStatus, activeToken, historialReintento, fieldCampaigns])

  // Imagen satelital de la campaña elegida (15 de enero, pleno verano)
  const currentHistoricalGibsDate = useMemo(
    () => fechaGibsCampana(historicalYear ?? new Date().getFullYear() - 1),
    [historicalYear]
  )

  const historialVisual = useMemo(
    () =>
      visualHistorico(
        historial?.campanas.find((c) => c.anio === historicalYear) ?? null,
        historicalMetric,
        (id) => CULTIVOS_CATALOGO[id as CultivoId]?.nombre ?? id
      ),
    [historial, historicalYear, historicalMetric]
  )

  // Solo los campos que caen dentro de las provincias seleccionadas
  const visibleFields = useMemo(
    () =>
      userFields.filter((f) => isPointInProvinces(f.lat, f.lon, selectedProvinces)),
    [userFields, selectedProvinces]
  )

  const selectedUserField = useMemo(
    () => visibleFields.find((f) => f.id === selectedFieldId) ?? null,
    [visibleFields, selectedFieldId]
  )

  // Polling cada 30 s mientras el campo seleccionado tenga reintento_en_curso = true (FRONT-42)
  useEffect(() => {
    const pollingFieldId = selectedUserField?.id
    const isRetrying = selectedUserField?.reintento_en_curso === true

    if (
      (authStatus !== 'authenticated' && authStatus !== 'demo') ||
      !activeToken ||
      !pollingFieldId ||
      !isRetrying ||
      isDrawingNewField ||
      editingPolygonField !== null
    ) {
      return
    }

    let cancelled = false
    let activeController: AbortController | null = null
    let prevSueloFuente = selectedUserField.suelo_fuente ?? null
    let prevTopoFuente = selectedUserField.topo_fuente ?? null

    const pollField = async () => {
      if (cancelled) return
      activeController?.abort()
      const controller = new AbortController()
      activeController = controller

      try {
        const freshField = await getUserField(
          activeToken,
          pollingFieldId,
          controller.signal
        )
        if (cancelled || controller.signal.aborted) return

        const nextSueloFuente = freshField.suelo_fuente ?? null
        const nextTopoFuente = freshField.topo_fuente ?? null
        const sueloChanged =
          Boolean(nextSueloFuente) && nextSueloFuente !== prevSueloFuente
        const topoChanged =
          Boolean(nextTopoFuente) && nextTopoFuente !== prevTopoFuente

        prevSueloFuente = nextSueloFuente
        prevTopoFuente = nextTopoFuente

        setUserFields((prev) =>
          prev.map((field) => {
            if (field.id !== pollingFieldId) return field
            return {
              ...freshField,
              polygon:
                Array.isArray(freshField.polygon) && freshField.polygon.length >= 3
                  ? freshField.polygon
                  : field.polygon,
            }
          })
        )

        if (sueloChanged || topoChanged) {
          const message =
            sueloChanged && topoChanged
              ? 'Llegaron los datos reales de suelo y topografía de su lote.'
              : sueloChanged
                ? 'Llegó el dato real del suelo de su lote.'
                : 'Llegó el dato real de topografía de su lote.'

          setFieldDataNotice(message)
          setTelemetryRetryCount((c) => c + 1)
          setSimulationRetryCount((c) => c + 1)
        }
      } catch {
        // Ignorar fallas transitorias en el polling en segundo plano; se reintenta al próximo ciclo
      }
    }

    const intervalId = window.setInterval(pollField, 30_000)

    return () => {
      cancelled = true
      activeController?.abort()
      window.clearInterval(intervalId)
    }
  }, [
    authStatus,
    activeToken,
    selectedUserField?.id,
    selectedUserField?.reintento_en_curso,
    isDrawingNewField,
    editingPolygonField,
  ])

  useEffect(() => {
    if (!fieldDataNotice) return
    const timer = window.setTimeout(() => {
      setFieldDataNotice(null)
    }, 7000)
    return () => {
      window.clearTimeout(timer)
    }
  }, [fieldDataNotice])

  // Reconciliar el campo seleccionado con el filtro de provincias (carga de campos y al aplicar):
  // nunca autoselecciona un campo fuera de las provincias elegidas.
  useEffect(() => {
    if (!isProvinceFilterApplied) return
    if (selectedFieldId && visibleFields.some((f) => f.id === selectedFieldId)) {
      return
    }
    if (visibleFields.length > 0) {
      const first = visibleFields[0]
      setSelectedFieldId(first.id)
      setSelectedCoords({ lat: first.lat, lon: first.lon })
      return
    }
    // Sin campos en las provincias elegidas: MapView encuadra la región completa
    setSelectedFieldId(null)
    setSelectedCoords(getProvincesCenter(selectedProvinces))
  }, [isProvinceFilterApplied, visibleFields, selectedFieldId, selectedProvinces])

  const currentLoteLabel = useMemo(() => {
    if (isDrawingNewField) {
      return customPolygon.length >= 3
        ? 'Nuevo campo delimitado'
        : 'Delimitación de nuevo campo en curso'
    }
    if (selectedUserField) {
      return selectedUserField.nombre
    }
    return 'Sin campo'
  }, [isDrawingNewField, selectedUserField, customPolygon.length])

  // Cargar campos del usuario (o usuario demo en BD) al iniciar sesión / entrar en demo
  useEffect(() => {
    if (authStatus !== 'authenticated' && authStatus !== 'demo') return
    let cancelled = false

    const loadFields = async () => {
      setIsFieldsLoading(true)
      setFieldsError(null)
      try {
        let token = activeToken
        if (authStatus === 'demo' && !token) {
          token = await loginDemoAccount()
          if (cancelled) return
          setActiveToken(token)
        }
        if (!token) return
        const fields = await listUserFields(token)
        if (cancelled) return
        setUserFields(fields)
        // La selección de campo la resuelve el efecto de filtro por provincias
      } catch (err) {
        if (cancelled) return
        setFieldsError(
          err instanceof Error
            ? err.message
            : 'No fue posible cargar los campos desde el servidor.'
        )
      } finally {
        if (!cancelled) setIsFieldsLoading(false)
      }
    }

    loadFields()
    return () => {
      cancelled = true
    }
  }, [authStatus, activeToken])

  const handleSelectUserField = (field: UserField) => {
    setMapSearchTarget(null)
    setIsDrawingNewField(false)
    setEditingPolygonField(null)
    setCustomPolygon([])
    setSelectedFieldId(field.id)
    setSelectedCoords({ lat: field.lat, lon: field.lon })
    setFieldFocusRequestId((prev) => prev + 1)
    setFieldsError(null)
    setFieldDataNotice(null)
    setWhatIf({
      override_humedad_radicular_pct: null,
      variacion_lluvia_esperada_pct: 0,
    })
  }

  const handleSelectSearchLocation = useCallback((result: MapSearchResult) => {
    setMapSearchTarget((prev) => ({
      label: result.label,
      coords: result.coords,
      zoom: result.zoom,
      bounds: result.bounds,
      polygons: result.polygons,
      requestId: (prev?.requestId ?? 0) + 1,
    }))
  }, [])

  const handleStartDrawing = () => {
    setEditingPolygonField(null)
    setIsDrawingNewField(true)
    setCustomPolygon([])
    setFieldsError(null)
  }

  const handleStartEditingPolygon = (field: UserField) => {
    setMapSearchTarget(null)
    setSettingsScope(null)
    setIsDrawingNewField(false)
    setEditingPolygonField(field)
    setSelectedFieldId(field.id)
    setFieldsError(null)
    if (Array.isArray(field.polygon) && field.polygon.length >= 3) {
      setCustomPolygon(field.polygon)
      setSelectedCoords(calculateCentroid(field.polygon))
    } else {
      setCustomPolygon([])
      setSelectedCoords({ lat: field.lat, lon: field.lon })
    }
  }

  const handleCancelDrawing = () => {
    setIsDrawingNewField(false)
    setEditingPolygonField(null)
    setCustomPolygon([])
    setFieldsError(null)
    if (selectedUserField) {
      setSelectedCoords({
        lat: selectedUserField.lat,
        lon: selectedUserField.lon,
      })
    } else {
      setSelectedCoords(getProvincesCenter(selectedProvinces))
    }
  }

  const handleUpdateCustomPolygon = (
    points: [number, number][],
    centroid?: Coordenadas
  ) => {
    setCustomPolygon(points)
    if (centroid) {
      setSelectedCoords(centroid)
    }
  }

  const handleUndoVertex = () => {
    if (customPolygon.length === 0) return
    const nextPoints = customPolygon.slice(0, -1)
    setCustomPolygon(nextPoints)
    if (nextPoints.length > 0) {
      setSelectedCoords(calculateCentroid(nextPoints))
    }
  }

  const handleClearPolygon = () => {
    setCustomPolygon([])
  }

  const handleSaveNewField = async (nombre: string) => {
    if (!activeToken) {
      setFieldsError(
        'No hay una sesión activa contra el backend para guardar el campo.'
      )
      return
    }
    if (customPolygon.length < 3) return

    setIsSavingField(true)
    setFieldsError(null)
    try {
      const centroid = calculateCentroid(customPolygon)
      const areaHa = Math.round(calculatePolygonAreaHa(customPolygon) * 10) / 10

      if (editingPolygonField) {
        const targetId = editingPolygonField.id
        const updated = await updateUserField(activeToken, targetId, {
          nombre,
          lat: centroid.lat,
          lon: centroid.lon,
          hectareas: areaHa,
          polygon: customPolygon,
        })
        saveFieldPolygon(targetId, customPolygon)
        const updatedWithPolygon: UserField = {
          ...editingPolygonField,
          ...updated,
          polygon:
            Array.isArray(updated.polygon) && updated.polygon.length >= 3
              ? updated.polygon
              : customPolygon,
        }
        setUserFields((prev) =>
          prev.map((field) =>
            field.id === targetId ? updatedWithPolygon : field
          )
        )
        setMapSearchTarget(null)
        setSelectedFieldId(targetId)
        setSelectedCoords(centroid)
        setEditingPolygonField(null)
        setCustomPolygon([])
        return
      }

      const created = await createUserField(activeToken, {
        nombre,
        lat: centroid.lat,
        lon: centroid.lon,
        hectareas: areaHa,
        polygon: customPolygon,
      })
      saveFieldPolygon(created.id, customPolygon)
      const createdWithPolygon: UserField = {
        ...created,
        polygon:
          Array.isArray(created.polygon) && created.polygon.length >= 3
            ? created.polygon
            : customPolygon,
      }
      setMapSearchTarget(null)
      setUserFields((prev) => [createdWithPolygon, ...prev])
      setSelectedFieldId(created.id)
      setSelectedCoords(centroid)
      setIsDrawingNewField(false)
      setCustomPolygon([])
    } catch (err) {
      setFieldsError(
        err instanceof Error
          ? err.message
          : 'No fue posible guardar el campo.'
      )
    } finally {
      setIsSavingField(false)
    }
  }

  const handleRenameField = async (fieldId: string, nombre: string) => {
    if (!activeToken) {
      throw new Error(
        'La sesión no se encuentra activa. Inicie sesión nuevamente.'
      )
    }
    const updated = await updateUserField(activeToken, fieldId, { nombre })
    setUserFields((prev) =>
      prev.map((field) => {
        if (field.id !== fieldId) return field
        return {
          ...field,
          ...updated,
          polygon:
            Array.isArray(updated.polygon) && updated.polygon.length >= 3
              ? updated.polygon
              : field.polygon,
        }
      })
    )
  }

  const handleDeleteField = async (fieldId: string) => {
    if (!activeToken) {
      throw new Error(
        'La sesión no se encuentra activa. Inicie sesión nuevamente.'
      )
    }
    await deleteUserField(activeToken, fieldId)
    removeCachedFieldPolygon(fieldId)

    const remaining = userFields.filter((field) => field.id !== fieldId)
    setUserFields(remaining)

    if (selectedFieldId === fieldId) {
      const remainingVisible = remaining.filter((f) =>
        isPointInProvinces(f.lat, f.lon, selectedProvinces)
      )
      const nextField = remainingVisible[0] ?? null
      setSelectedFieldId(nextField ? nextField.id : null)
      setSelectedCoords(
        nextField
          ? { lat: nextField.lat, lon: nextField.lon }
          : getProvincesCenter(selectedProvinces)
      )
    }
  }

  const handleResetWhatIf = () => {
    setWhatIf({
      override_humedad_radicular_pct: null,
      variacion_lluvia_esperada_pct: 0,
    })
  }

  const isWhatIfActive =
    whatIf.override_humedad_radicular_pct !== null ||
    whatIf.variacion_lluvia_esperada_pct !== 0

  const handleAuthenticated = (user: UserProfile, token: string) => {
    setAuthNotice(null)
    const finish = (profile: UserProfile) => {
      initProvincesFromProfile(profile)
      setCurrentUser(profile)
      setActiveToken(token)
      setAuthStatus('authenticated')
    }

    // Si el login no informó provincias (undefined), se consulta el perfil en BD
    if (user.provincias !== undefined) {
      finish(user)
      return
    }
    fetchCurrentUser(token)
      .then((profile) => finish({ ...user, provincias: profile.provincias ?? null }))
      .catch(() => finish({ ...user, provincias: null }))
  }

  const handleEnterDemo = () => {
    setAuthNotice(null)
    setCurrentUser(null)
    setActiveToken(null)
    // Demo: la selección vive solo en memoria y siempre arranca en el selector
    setSelectedProvinces([])
    setIsProvinceFilterApplied(false)
    setProvincesError(null)
    setAuthStatus('demo')
  }

  const commitProvinces = (provinceIds: string[]) => {
    setMapSearchTarget(null)
    setIsDrawingNewField(false)
    setEditingPolygonField(null)
    setCustomPolygon([])
    setFieldsError(null)
    setSelectedProvinces(provinceIds)
    setIsProvinceFilterApplied(true)
  }

  const handleApplyProvinces = async (provinceIds: string[]): Promise<boolean> => {
    setProvincesError(null)

    // Modo demo (cuenta compartida): NUNCA se persiste en BD
    if (authStatus !== 'authenticated' || !activeToken) {
      commitProvinces(provinceIds)
      return true
    }

    setIsSavingProvinces(true)
    try {
      const updated = await updateUserProvinces(activeToken, provinceIds)
      const saved = sanitizeProvinceIds(updated.provincias)
      const finalIds = saved.length > 0 ? saved : provinceIds
      setCurrentUser((prev) =>
        prev ? { ...prev, provincias: finalIds } : prev
      )

      const fieldsToRemove = userFields.filter(
        (field) => !isPointInProvinces(field.lat, field.lon, finalIds)
      )

      if (fieldsToRemove.length > 0) {
        const results = await Promise.allSettled(
          fieldsToRemove.map((field) => deleteUserField(activeToken, field.id))
        )
        const deletedIds = new Set<string>()
        results.forEach((res, idx) => {
          if (res.status === 'fulfilled') {
            const deletedId = fieldsToRemove[idx].id
            deletedIds.add(deletedId)
            removeCachedFieldPolygon(deletedId)
          }
        })

        if (deletedIds.size > 0) {
          setUserFields((prev) =>
            prev.filter((field) => !deletedIds.has(field.id))
          )
          if (selectedFieldId && deletedIds.has(selectedFieldId)) {
            setSelectedFieldId(null)
          }
        }

        if (deletedIds.size < fieldsToRemove.length) {
          commitProvinces(finalIds)
          setProvincesError(
            'Se actualizaron las provincias, pero no fue posible eliminar algunos campos asociados.'
          )
          return false
        }
      }

      commitProvinces(finalIds)
      return true
    } catch (err) {
      setProvincesError(
        err instanceof Error
          ? err.message
          : 'No fue posible guardar las provincias seleccionadas.'
      )
      return false
    } finally {
      setIsSavingProvinces(false)
    }
  }

  const handleLogout = (notice?: unknown) => {
    clearStoredAuthToken()
    setCurrentUser(null)
    setActiveToken(null)
    setUserFields([])
    setSelectedFieldId(null)
    setSelectedProvinces([])
    setIsProvinceFilterApplied(false)
    setProvincesError(null)
    setSettingsScope(null)
    setEditingPolygonField(null)
    setSimulationError(null)
    setSimulationResult(null)
    setFieldDataNotice(null)
    setHasPlanned(false)
    setAuthNotice(typeof notice === 'string' ? notice : null)
    setAuthStatus('unauthenticated')
  }

  if (authStatus === 'checking') {
    return (
      <div className="auth-checking-shell">
        <div className="auth-checking-card">
          <img
            src="/ereia-icon.png"
            alt=""
            className="auth-checking-icon"
            aria-hidden="true"
          />
          <span>Verificando sesión...</span>
        </div>
      </div>
    )
  }

  if (authStatus === 'unauthenticated') {
    return (
      <AuthScreen
        initialError={authNotice}
        onAuthenticated={handleAuthenticated}
        onEnterDemo={handleEnterDemo}
      />
    )
  }

  // Filtro previo: mapa plano de Argentina (primera vez o demo)
  if (!isProvinceFilterApplied) {
    return (
      <ProvinceSelectorScreen
        initialSelected={selectedProvinces}
        isSaving={isSavingProvinces}
        errorMsg={provincesError}
        isDemo={authStatus === 'demo'}
        userLabel={currentUser?.nombre || currentUser?.email}
        onApply={handleApplyProvinces}
        onLogout={handleLogout}
      />
    )
  }

  return (
    <div className="app-shell">
      {/* HEADER SUPERIOR (#FFF5E0) */}
      <header className="top-navbar">
        <div className="top-navbar-left">
          <BrandBlock />
        </div>
      </header>

      {/* CONTENIDO PRINCIPAL (MAPA ~60% IZQ + CARPETA DERECHA ~40% CON PESTAÑAS SUPERPUESTAS AL HEADER) */}
      <main className="split-dashboard">
        <section className="left-map-pane">
          <FieldsSubheader
            fields={visibleFields}
            selectedFieldId={selectedFieldId}
            selectedProvinces={selectedProvinces}
            isLoading={isFieldsLoading}
            isSaving={isSavingField}
            errorMsg={fieldsError}
            isDrawing={isDrawingNewField || editingPolygonField !== null}
            editingField={editingPolygonField}
            customPolygon={customPolygon}
            isMapSettingsOpen={settingsScope === 'map'}
            onOpenMapSettings={() => {
              setProvincesError(null)
              setSettingsScope('map')
            }}
            onSelectSearchLocation={handleSelectSearchLocation}
            onSelectField={handleSelectUserField}
            onStartDrawing={handleStartDrawing}
            onCancelDrawing={handleCancelDrawing}
            onUndoVertex={handleUndoVertex}
            onClearPolygon={handleClearPolygon}
            onSaveField={handleSaveNewField}
          />
          <Suspense fallback={<div className="map-wrapper" />}>
            <MapView
              selectedCoords={selectedCoords}
              userFields={visibleFields}
              selectedFieldId={selectedFieldId}
              editingFieldId={editingPolygonField?.id ?? null}
              isDrawingNewField={
                isDrawingNewField || editingPolygonField !== null
              }
              customPolygon={customPolygon}
              historicalMode={{
                active: activeTab === 'historico',
                year: historicalYear ?? new Date().getFullYear() - 1,
                metric: historicalMetric,
                gibsDateIso: currentHistoricalGibsDate,
                visual: historialVisual,
              }}
              selectedProvinces={selectedProvinces}
              searchTarget={mapSearchTarget}
              fieldFocusRequestId={fieldFocusRequestId}
              onOutsideProvinceClick={setFieldsError}
              onSelectUserField={handleSelectUserField}
              onUpdateCustomPolygon={handleUpdateCustomPolygon}
            />
          </Suspense>
        </section>

        <aside className="right-analysis-pane">
          <nav className="top-nav-tabs" aria-label="Navegación del panel derecho">
            <button
              type="button"
              className={`nav-tab-btn ${activeTab === 'planificacion' && settingsScope !== 'user' ? 'active' : ''}`}
              onClick={() => {
                setSettingsScope(null)
                setActiveTab('planificacion')
              }}
            >
              <Compass size={14} />
              <span>Planificación de campaña</span>
            </button>

            <button
              type="button"
              className={`nav-tab-btn ${activeTab === 'info_general' && settingsScope !== 'user' ? 'active' : ''}`}
              onClick={() => {
                setSettingsScope(null)
                setActiveTab('info_general')
              }}
            >
              <Info size={14} />
              <span>Info general</span>
            </button>

            <button
              type="button"
              className={`nav-tab-btn ${activeTab === 'historico' && settingsScope !== 'user' ? 'active' : ''}`}
              onClick={() => {
                setSettingsScope(null)
                setActiveTab('historico')
              }}
            >
              <History size={14} />
              <span>Información histórica</span>
            </button>

            <button
              type="button"
              className={`nav-tab-btn nav-tab-user ${settingsScope === 'user' ? 'active' : ''}`}
              onClick={() => {
                if (authStatus === 'demo') {
                  handleLogout()
                } else {
                  setProvincesError(null)
                  setSettingsScope('user')
                }
              }}
              aria-label={
                authStatus === 'demo'
                  ? 'Iniciar sesión o crear cuenta'
                  : 'Cuenta de usuario e idioma'
              }
              title={
                authStatus === 'demo'
                  ? 'Iniciar sesión o crear cuenta'
                  : 'Usuario e idioma'
              }
            >
              <User size={15} aria-hidden="true" />
            </button>
          </nav>

          <div className="right-folder-body">
            {fieldDataNotice && (
              <div className="field-data-notice" role="status" aria-live="polite">
                <div className="field-data-notice-content">
                  <CheckCircle2 size={15} aria-hidden="true" />
                  <span>{fieldDataNotice}</span>
                </div>
                <button
                  type="button"
                  className="field-data-notice-close"
                  onClick={() => setFieldDataNotice(null)}
                  aria-label="Cerrar notificación"
                >
                  <X size={14} aria-hidden="true" />
                </button>
              </div>
            )}

            {activeTab === 'planificacion' && (
              <>
                {authStatus === 'authenticated' && selectedFieldId && campanaEnCurso && (
                  <SeguimientoCampana
                    nombreCultivo={CULTIVOS_CATALOGO[campanaEnCurso.cultivo as CultivoId]?.nombre ?? campanaEnCurso.cultivo}
                    seguimiento={seguimiento}
                    cargando={seguimientoCargando}
                    aviso={seguimientoAviso}
                    onReintentar={() => setSeguimientoReintento((n) => n + 1)}
                    acciones={
                      <AccionesCampana
                        key={campanaEnCurso.id}
                        nombreCultivo={CULTIVOS_CATALOGO[campanaEnCurso.cultivo as CultivoId]?.nombre ?? campanaEnCurso.cultivo}
                        fechaSiembra={campanaEnCurso.fecha_inicio}
                        onCerrar={handleCerrarCampana}
                        onBorrar={handleBorrarCampana}
                      />
                    }
                  />
                )}
                {authStatus === 'authenticated' && selectedFieldId && !campanaEnCurso && (
                  <RegistrarSiembraForm onRegistrar={handleRegistrarSiembra} />
                )}
                {authStatus === 'demo' && (
                  <section className="panel-section seguimiento-section seguimiento-demo">
                    <p className="seg-invitacion">Registrate y guardá tu lote para seguir la campaña semana a semana.</p>
                  </section>
                )}
                <CampaignConfigPanel
                  fieldName={selectedUserField?.nombre ?? null}
                  isDrawingField={isDrawingNewField || editingPolygonField !== null}
                  campana={campana}
                  cultivoAnterior={cultivoAnterior}
                  objetivoProductor={objetivoProductor}
                  canPlan={isRotationReady}
                  isPlanning={isSimulating}
                  isHistoricalReady={isHistoricalReady}
                  onChangeCampana={setCampana}
                  onChangeCultivoAnterior={setCultivoAnterior}
                  onChangeObjetivo={setObjetivoProductor}
                  onPlan={handlePlan}
                />

                {!hasPlanned && (
                  <section className="panel-section empty-rotation-card">
                    <span className="section-eyebrow">ESTRATEGIA DE ROTACIÓN</span>
                    <p className="empty-rotation-text">
                      {!isRotationReady
                        ? 'Seleccione el tipo de campaña y el cultivo antecesor para consultar los datos históricos.'
                        : 'Elija la prioridad de manejo y presione "Planificar" para generar la recomendación de cultivo.'}
                    </p>
                  </section>
                )}

                {hasPlanned && avisoDatos && (
                  <AvisoEstadoDatos
                    estado={avisoDatos}
                    onReintentar={() => setReintentoSimulacion((n) => n + 1)}
                  />
                )}

                {hasPlanned && isSimulating && !simulationResult && (
                  <section
                    className="panel-section skeleton-card"
                    aria-busy="true"
                    aria-label="Calculando estrategia de rotación"
                  >
                    <div className="skeleton-line short" />
                    <div className="skeleton-line title" />
                    <div className="skeleton-box" />
                    <div className="skeleton-line" />
                  </section>
                )}

                {hasPlanned && !isSimulating && simulationError && (
                  <RecommendationPanel
                    recomendacion={null}
                    ranking={[]}
                    errorMessage={simulationError}
                    onRetry={() => setSimulationRetryCount((c) => c + 1)}
                  />
                )}

                {hasPlanned && simulationResult && (
                  <>
                    <RecommendationPanel
                      recomendacion={simulationResult.recomendacion_principal}
                      ranking={simulationResult.ranking_cultivos}
                      advertencias={humanizeAgronomicWarnings([
                        simulationResult.advertencias,
                        !isDrawingNewField && editingPolygonField === null
                          ? selectedUserField?.suelo_advertencias
                          : undefined,
                        !isDrawingNewField && editingPolygonField === null
                          ? selectedUserField?.topo_advertencias
                          : undefined,
                      ])}
                      isWhatIfActive={isWhatIfActive}
                      faseEnso={simulationResult.fase_enso}
                      departamento={simulationResult.departamento_referencia}
                    />

                    {avisoDatos?.tipo === 'sin_conexion' ? (
                      <section className="panel-section what-if-sin-conexion">
                        <p>Necesitás conexión para simular escenarios.</p>
                      </section>
                    ) : (
                      <WhatIfPanel
                        whatIf={whatIf}
                        nasaDetectedHumidityPct={
                          baselineResult.telemetria_nasa.indice_humedad_radicular_pct
                        }
                        onChangeWhatIf={setWhatIf}
                        onResetWhatIf={handleResetWhatIf}
                      />
                    )}
                  </>
                )}
              </>
            )}

            {activeTab === 'info_general' && (
              <TelemetryCards
                loteLabel={currentLoteLabel}
                isFieldAssigned={Boolean(selectedUserField)}
                telemetria={
                  simulationResult?.telemetria_nasa ??
                  fieldTelemetry?.telemetria_nasa ??
                  null
                }
                perfilSuelo={
                  simulationResult?.perfil_suelo ??
                  fieldTelemetry?.perfil_suelo ??
                  getStoredSoilFromField(selectedUserField)
                }
                topografia={
                  fieldTelemetry?.topografia_srtm ??
                  getStoredTopoFromField(selectedUserField)
                }
                advertencias={humanizeAgronomicWarnings([
                  !isDrawingNewField && editingPolygonField === null
                    ? selectedUserField?.suelo_advertencias
                    : undefined,
                  !isDrawingNewField && editingPolygonField === null
                    ? selectedUserField?.topo_advertencias
                    : undefined,
                  fieldTelemetry?.advertencias,
                  simulationResult?.advertencias,
                ])}
                latestCampaign={latestFieldCampaign}
                isLoading={isTelemetryLoading && !simulationResult}
                errorMessage={!simulationResult ? telemetryError : null}
                onRetry={() => setTelemetryRetryCount((c) => c + 1)}
                isWhatIfActive={isWhatIfActive}
                isRetryingFieldData={
                  selectedUserField?.reintento_en_curso === true &&
                  !isDrawingNewField &&
                  editingPolygonField === null
                }
              />
            )}

            {activeTab === 'historico' && (
              <Suspense
                fallback={
                  <section className="panel-section skeleton-card" aria-busy="true">
                    <div className="skeleton-line short" />
                    <div className="skeleton-line title" />
                    <div className="skeleton-box" />
                  </section>
                }
              >
                <HistoricalPanel
                  loteLabel={currentLoteLabel}
                  historial={historial}
                  cargando={historialCargando}
                  aviso={historialAviso}
                  onReintentar={() => setHistorialReintento((n) => n + 1)}
                  selectedYear={historicalYear}
                  selectedMetric={historicalMetric}
                  onChangeYear={setHistoricalYear}
                  onChangeMetric={setHistoricalMetric}
                  nombreCultivo={(id) => CULTIVOS_CATALOGO[id as CultivoId]?.nombre ?? id}
                />
              </Suspense>
            )}
          </div>
        </aside>
      </main>

      <UserSettingsModal
        isOpen={
          settingsScope !== null &&
          (settingsScope === 'map' || authStatus === 'authenticated')
        }
        scope={settingsScope ?? 'user'}
        isDemo={authStatus === 'demo'}
        user={currentUser}
        accessToken={activeToken}
        fields={visibleFields}
        selectedProvinces={selectedProvinces}
        isSavingProvinces={isSavingProvinces}
        provincesError={provincesError}
        onClose={() => setSettingsScope(null)}
        onUserUpdated={(updatedUser) => setCurrentUser(updatedUser)}
        onSaveProvinces={handleApplyProvinces}
        onRenameField={handleRenameField}
        onEditFieldPolygon={handleStartEditingPolygon}
        onDeleteField={handleDeleteField}
        onLogout={handleLogout}
      />
    </div>
  )
}

export default App
