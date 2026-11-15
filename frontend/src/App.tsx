import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import {
  Compass,
  History,
  Info,
} from 'lucide-react'
import './App.css'
import { AuthScreen } from './components/AuthScreen'
import { BrandBlock } from './components/BrandBlock'
import { FieldsSubheader } from './components/FieldsSubheader'
import { ProvinceSelectorScreen } from './components/ProvinceSelectorScreen'
import { RecommendationPanel } from './components/RecommendationPanel'
import {
  CampaignConfigPanel,
  WhatIfPanel,
} from './components/SimulationControls'
import { TelemetryCards } from './components/TelemetryCards'
import { UserSettingsModal } from './components/UserSettingsModal'

const HistoricalPanel = lazy(() =>
  import('./components/HistoricalPanel').then((m) => ({
    default: m.HistoricalPanel,
  }))
)
const MapView = lazy(() =>
  import('./components/MapView').then((m) => ({ default: m.MapView }))
)
import { DEMO_FIELDS } from './data/demoFields'
import {
  getHistoricalSeriesForCoords,
  type HistoricalMetricId,
} from './data/historicalData'
import {
  generateSimulatedResponse,
  simulateCropRotation,
} from './services/apiClient'
import {
  clearStoredAuthToken,
  fetchCurrentUser,
  getStoredAuthToken,
  updateUserProvinces,
} from './services/authClient'
import {
  createUserField,
  deleteUserField,
  listUserFields,
  loginDemoAccount,
  removeCachedFieldPolygon,
  saveFieldPolygon,
  updateUserField,
} from './services/fieldsClient'
import type { SearchCameraTarget } from './components/MapView'
import type { MapSearchResult } from './services/geocodeClient'
import type {
  Campana,
  Coordenadas,
  CultivoAnterior,
  ObjetivoProductor,
  SimulacionWhatIf,
  SimulateResponse,
  UserField,
  UserProfile,
} from './types/api'
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

export function App() {
  const defaultField = DEMO_FIELDS[0]

  const [authStatus, setAuthStatus] = useState<AuthStatus>('checking')
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null)
  const [activeToken, setActiveToken] = useState<string | null>(null)

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
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false)

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
  const [isSimulating, setIsSimulating] = useState<boolean>(false)
  const [isHistoricalReady, setIsHistoricalReady] = useState<boolean>(false)
  const [hasPlanned, setHasPlanned] = useState<boolean>(false)

  // Estado de la pestaña 'Información histórica' (10 años en vivo con el mapa)
  const [historicalYear, setHistoricalYear] = useState<number>(2026)
  const [historicalMetric, setHistoricalMetric] =
    useState<HistoricalMetricId>('cultivos')

  const isRotationReady = campana !== null && cultivoAnterior !== null

  // Paso 1: Apenas estén completos campaña y cultivo anterior, realiza el pedido de datos históricos
  useEffect(() => {
    setHasPlanned(false)
    setSimulationResult(null)

    if (!campana || !cultivoAnterior) {
      setIsHistoricalReady(false)
      return
    }

    let cancelled = false
    setIsHistoricalReady(false)

    const timer = window.setTimeout(() => {
      if (!cancelled) {
        getHistoricalSeriesForCoords(selectedCoords)
        setIsHistoricalReady(true)
      }
    }, 150)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [selectedCoords, campana, cultivoAnterior])

  // Paso 2: Al presionar "Planificar" (o al ajustar objetivo/What-If ya planificado), consulta la recomendación
  useEffect(() => {
    if (!hasPlanned || !campana || !cultivoAnterior) {
      setIsSimulating(false)
      return
    }

    let cancelled = false
    setIsSimulating(true)

    const timer = window.setTimeout(async () => {
      try {
        const result = await simulateCropRotation({
          coordenadas: selectedCoords,
          campana,
          cultivo_anterior: cultivoAnterior,
          objetivo_productor: objetivoProductor,
          simulacion_what_if: whatIf,
        })
        if (!cancelled) {
          setSimulationResult(result)
        }
      } catch {
        if (!cancelled) {
          setSimulationResult(
            generateSimulatedResponse({
              coordenadas: selectedCoords,
              campana,
              cultivo_anterior: cultivoAnterior,
              objetivo_productor: objetivoProductor,
              simulacion_what_if: whatIf,
            })
          )
        }
      } finally {
        if (!cancelled) {
          setIsSimulating(false)
        }
      }
    }, 150)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [hasPlanned, selectedCoords, campana, cultivoAnterior, objetivoProductor, whatIf])

  const handlePlan = () => {
    if (!isRotationReady) return
    setHasPlanned(true)
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

  // Fecha satelital histórica correspondiente al año elegido
  const currentHistoricalGibsDate = useMemo(() => {
    const series = getHistoricalSeriesForCoords(selectedCoords)
    const found = series.find((r) => r.year === historicalYear)
    return found?.gibsDate ?? '2024-11-08'
  }, [selectedCoords, historicalYear])

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
    return 'Ubicación seleccionada en el mapa'
  }, [isDrawingNewField, selectedUserField, customPolygon.length])

  const currentSuperficieHa = useMemo(() => {
    if (isDrawingNewField && customPolygon.length >= 3) {
      return calculatePolygonAreaHa(customPolygon)
    }
    if (selectedUserField && selectedUserField.hectareas !== null) {
      return selectedUserField.hectareas
    }
    return null
  }, [isDrawingNewField, selectedUserField, customPolygon])

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
    setWhatIf({
      override_humedad_radicular_pct: null,
      variacion_lluvia_esperada_pct: 0,
    })
  }

  const handleSelectSearchLocation = (result: MapSearchResult) => {
    setMapSearchTarget((prev) => ({
      label: result.label,
      coords: result.coords,
      zoom: result.zoom,
      bounds: result.bounds,
      polygons: result.polygons,
      requestId: (prev?.requestId ?? 0) + 1,
    }))
  }

  const handleStartDrawing = () => {
    setEditingPolygonField(null)
    setIsDrawingNewField(true)
    setCustomPolygon([])
    setFieldsError(null)
  }

  const handleStartEditingPolygon = (field: UserField) => {
    setMapSearchTarget(null)
    setIsSettingsOpen(false)
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

  const handleLogout = () => {
    clearStoredAuthToken()
    setCurrentUser(null)
    setActiveToken(null)
    setUserFields([])
    setSelectedFieldId(null)
    setSelectedProvinces([])
    setIsProvinceFilterApplied(false)
    setProvincesError(null)
    setIsSettingsOpen(false)
    setEditingPolygonField(null)
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
            isDemo={authStatus === 'demo'}
            isUserSettingsOpen={isSettingsOpen}
            onUserAction={() => {
              if (authStatus === 'demo') {
                handleLogout()
              } else {
                setProvincesError(null)
                setIsSettingsOpen(true)
              }
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
                year: historicalYear,
                metric: historicalMetric,
                gibsDateIso: currentHistoricalGibsDate,
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
              className={`nav-tab-btn ${activeTab === 'planificacion' ? 'active' : ''}`}
              onClick={() => setActiveTab('planificacion')}
            >
              <Compass size={14} />
              <span>Planificación de campaña</span>
            </button>

            <button
              type="button"
              className={`nav-tab-btn ${activeTab === 'info_general' ? 'active' : ''}`}
              onClick={() => setActiveTab('info_general')}
            >
              <Info size={14} />
              <span>Info general</span>
            </button>

            <button
              type="button"
              className={`nav-tab-btn ${activeTab === 'historico' ? 'active' : ''}`}
              onClick={() => setActiveTab('historico')}
            >
              <History size={14} />
              <span>Información histórica</span>
            </button>
          </nav>

          <div className="right-folder-body">
            {activeTab === 'planificacion' && (
              <>
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

                {hasPlanned && simulationResult && (
                  <>
                    <RecommendationPanel
                      recomendacion={simulationResult.recomendacion_principal}
                      ranking={simulationResult.ranking_cultivos}
                      isWhatIfActive={isWhatIfActive}
                    />

                    <WhatIfPanel
                      whatIf={whatIf}
                      nasaDetectedHumidityPct={
                        baselineResult.telemetria_nasa.indice_humedad_radicular_pct
                      }
                      onChangeWhatIf={setWhatIf}
                      onResetWhatIf={handleResetWhatIf}
                    />
                  </>
                )}
              </>
            )}

            {activeTab === 'info_general' && (
              <TelemetryCards
                ubicacion={baselineResult.ubicacion}
                loteLabel={currentLoteLabel}
                superficieHa={currentSuperficieHa}
                telemetria={
                  simulationResult?.telemetria_nasa ??
                  baselineResult.telemetria_nasa
                }
                perfilSuelo={
                  simulationResult?.perfil_suelo ?? baselineResult.perfil_suelo
                }
                isWhatIfActive={isWhatIfActive}
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
                  ubicacion={selectedCoords}
                  loteLabel={currentLoteLabel}
                  selectedYear={historicalYear}
                  selectedMetric={historicalMetric}
                  onChangeYear={setHistoricalYear}
                  onChangeMetric={setHistoricalMetric}
                />
              </Suspense>
            )}
          </div>
        </aside>
      </main>

      <UserSettingsModal
        isOpen={isSettingsOpen && authStatus === 'authenticated'}
        user={currentUser}
        accessToken={activeToken}
        fields={visibleFields}
        selectedProvinces={selectedProvinces}
        isSavingProvinces={isSavingProvinces}
        provincesError={provincesError}
        onClose={() => setIsSettingsOpen(false)}
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
