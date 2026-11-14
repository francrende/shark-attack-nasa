import { useEffect, useMemo, useState } from 'react'
import {
  Compass,
  History,
  Info,
  Sprout,
} from 'lucide-react'
import './App.css'
import { HistoricalPanel } from './components/HistoricalPanel'
import { MapView } from './components/MapView'
import { RecommendationPanel } from './components/RecommendationPanel'
import {
  CampaignConfigPanel,
  WhatIfPanel,
} from './components/SimulationControls'
import { TelemetryCards } from './components/TelemetryCards'
import { DEMO_FIELDS } from './data/demoFields'
import {
  getHistoricalSeriesForCoords,
  type HistoricalMetricId,
} from './data/historicalData'
import {
  generateSimulatedResponse,
  simulateCropRotation,
} from './services/apiClient'
import type {
  Campana,
  Coordenadas,
  CultivoId,
  DemoField,
  GibsLayerId,
  ObjetivoProductor,
  SelectionMode,
  SimulacionWhatIf,
  SimulateResponse,
} from './types/api'
import { calculatePolygonAreaHa } from './utils/geo'

export type NavTabId = 'planificacion' | 'info_general' | 'historico'

export function App() {
  const defaultField = DEMO_FIELDS[0]

  // Por regla de SKILLS_FRONTEND.md §3 y §4, la app inicia directamente en 'Planificación de campaña'
  const [activeTab, setActiveTab] = useState<NavTabId>('planificacion')

  // Estado GIS y selección de lote (persiste entre pestañas)
  const [selectionMode, setSelectionMode] = useState<SelectionMode>('demo')
  const [selectedDemoFieldId, setSelectedDemoFieldId] = useState<string | null>(
    defaultField.id
  )
  const [selectedCoords, setSelectedCoords] = useState<Coordenadas>(
    defaultField.centroide
  )
  const [customPolygon, setCustomPolygon] = useState<[number, number][]>([])
  const [isPolygonClosed, setIsPolygonClosed] = useState<boolean>(false)
  const [activeGibsLayer, setActiveGibsLayer] =
    useState<GibsLayerId>('none')

  // Estado agronómico y simulación What-If (campaña y cultivo anterior inician sin selección)
  const [campana, setCampana] = useState<Campana | null>(null)
  const [cultivoAnterior, setCultivoAnterior] = useState<CultivoId | null>(null)
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

  const selectedDemoField = useMemo(
    () => DEMO_FIELDS.find((f) => f.id === selectedDemoFieldId) ?? null,
    [selectedDemoFieldId]
  )

  const currentLoteLabel = useMemo(() => {
    if (selectionMode === 'demo' && selectedDemoField) {
      return selectedDemoField.nombre
    }
    if (selectionMode === 'polygon') {
      return customPolygon.length >= 3
        ? 'Lote delimitado en el mapa'
        : 'Delimitación de lote en curso'
    }
    return 'Ubicación seleccionada en el mapa'
  }, [selectionMode, selectedDemoField, customPolygon.length])

  const currentSuperficieHa = useMemo(() => {
    if (selectionMode === 'demo' && selectedDemoField) {
      return selectedDemoField.superficieHa
    }
    if (selectionMode === 'polygon' && customPolygon.length >= 3) {
      return calculatePolygonAreaHa(customPolygon)
    }
    return null
  }, [selectionMode, selectedDemoField, customPolygon])

  const handleSelectDemoField = (field: DemoField) => {
    setSelectionMode('demo')
    setSelectedDemoFieldId(field.id)
    setSelectedCoords(field.centroide)
    setWhatIf({
      override_humedad_radicular_pct: null,
      variacion_lluvia_esperada_pct: 0,
    })
  }

  const handleChangeSelectionMode = (mode: SelectionMode) => {
    setSelectionMode(mode)
    if (mode === 'demo' && !selectedDemoFieldId) {
      handleSelectDemoField(DEMO_FIELDS[0])
    }
  }

  const handleUpdateCustomPolygon = (
    points: [number, number][],
    isClosed: boolean,
    centroid?: Coordenadas
  ) => {
    setCustomPolygon(points)
    setIsPolygonClosed(isClosed)
    if (centroid) {
      setSelectedCoords(centroid)
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

  return (
    <div className="app-shell">
      {/* HEADER SUPERIOR SÓLIDO (#3A0C00) */}
      <header className="top-navbar">
        <div className="brand-block">
          <div className="brand-logo" aria-hidden="true">
            <Sprout size={20} />
          </div>
          <div>
            <div className="brand-title-row">
              <h1>Shark Attack</h1>
            </div>
            <p className="brand-subtitle">
              Monitoreo satelital y planificación agronómica de rotaciones
            </p>
          </div>
        </div>
      </header>

      {/* CONTENIDO PRINCIPAL (MAPA ~60% IZQ + CARPETA DERECHA ~40% CON PESTAÑAS SUPERPUESTAS AL HEADER) */}
      <main className="split-dashboard">
        <section className="left-map-pane">
          <MapView
            selectedCoords={selectedCoords}
            selectionMode={selectionMode}
            selectedDemoFieldId={selectedDemoFieldId}
            customPolygon={customPolygon}
            isPolygonClosed={isPolygonClosed}
            activeGibsLayer={activeGibsLayer}
            historicalMode={{
              active: activeTab === 'historico',
              year: historicalYear,
              metric: historicalMetric,
              gibsDateIso: currentHistoricalGibsDate,
            }}
            onSelectDemoField={handleSelectDemoField}
            onChangeSelectionMode={handleChangeSelectionMode}
            onUpdateCustomPolygon={handleUpdateCustomPolygon}
            onChangeGibsLayer={setActiveGibsLayer}
          />
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
              <HistoricalPanel
                ubicacion={selectedCoords}
                loteLabel={currentLoteLabel}
                selectedYear={historicalYear}
                selectedMetric={historicalMetric}
                onChangeYear={setHistoricalYear}
                onChangeMetric={setHistoricalMetric}
              />
            )}
          </div>
        </aside>
      </main>
    </div>
  )
}

export default App
