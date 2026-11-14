import { useMemo, useState } from 'react'
import {
  Compass,
  History,
  Info,
  MessageSquare,
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
import { generateSimulatedResponse } from './services/apiClient'
import type {
  Campana,
  Coordenadas,
  CultivoId,
  DemoField,
  GibsLayerId,
  ObjetivoProductor,
  SelectionMode,
  SimulacionWhatIf,
} from './types/api'
import { calculatePolygonAreaHa } from './utils/geo'

export type NavTabId = 'planificacion' | 'info_general' | 'historico' | 'chat'

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

  // Estado agronómico y simulación What-If
  const [campana, setCampana] = useState<Campana>(defaultField.campanaDefault)
  const [cultivoAnterior, setCultivoAnterior] = useState<CultivoId>(
    defaultField.cultivoAnteriorDefault
  )
  const [objetivoProductor, setObjetivoProductor] =
    useState<ObjetivoProductor>('equilibrio')
  const [whatIf, setWhatIf] = useState<SimulacionWhatIf>({
    override_humedad_radicular_pct: null,
    variacion_lluvia_esperada_pct: 0,
  })

  // Estado de la pestaña 'Información histórica' (10 años en vivo con el mapa)
  const [historicalYear, setHistoricalYear] = useState<number>(2026)
  const [historicalMetric, setHistoricalMetric] =
    useState<HistoricalMetricId>('cultivos')

  // Cálculo reactivo instantáneo en cada cambio de estado
  const simulationResult = useMemo(() => {
    return generateSimulatedResponse({
      coordenadas: selectedCoords,
      campana,
      cultivo_anterior: cultivoAnterior,
      objetivo_productor: objetivoProductor,
      simulacion_what_if: whatIf,
    })
  }, [selectedCoords, campana, cultivoAnterior, objetivoProductor, whatIf])

  // Humedad base sin override para mostrar en el control What-If
  const baselineResult = useMemo(() => {
    return generateSimulatedResponse({
      coordenadas: selectedCoords,
      campana,
      cultivo_anterior: cultivoAnterior,
      objetivo_productor: objetivoProductor,
      simulacion_what_if: {
        override_humedad_radicular_pct: null,
        variacion_lluvia_esperada_pct: 0,
      },
    })
  }, [selectedCoords, campana, cultivoAnterior, objetivoProductor])

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
        ? 'Mi lote dibujado'
        : 'Dibujando lote en el mapa...'
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
    setCampana(field.campanaDefault)
    setCultivoAnterior(field.cultivoAnteriorDefault)
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

  const handleSelectPoint = (coords: Coordenadas) => {
    setSelectedDemoFieldId(null)
    setSelectedCoords(coords)
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
      {/* HEADER SUPERIOR LIMPIO Y MINIMALISTA (SKILLS_FRONTEND.md §4) */}
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
              Cuaderno de campo satelital · Rotación y agua para tu lote
            </p>
          </div>
        </div>

        <nav className="top-nav-tabs" aria-label="Navegación principal">
          <button
            type="button"
            className={`nav-tab-btn ${activeTab === 'planificacion' ? 'active' : ''}`}
            onClick={() => setActiveTab('planificacion')}
          >
            <Compass size={15} />
            <span>Planificación de campaña</span>
          </button>

          <button
            type="button"
            className={`nav-tab-btn ${activeTab === 'info_general' ? 'active' : ''}`}
            onClick={() => setActiveTab('info_general')}
          >
            <Info size={15} />
            <span>Info general</span>
          </button>

          <button
            type="button"
            className={`nav-tab-btn ${activeTab === 'historico' ? 'active' : ''}`}
            onClick={() => setActiveTab('historico')}
          >
            <History size={15} />
            <span>Información histórica</span>
          </button>

          <button
            type="button"
            className="nav-tab-btn disabled"
            disabled
            title="El asistente de chat estará disponible próximamente"
          >
            <MessageSquare size={15} />
            <span>Chat</span>
            <span className="nav-tab-soon-badge">Próximamente</span>
          </button>
        </nav>
      </header>

      {/* CONTENIDO SEGÚN LA PESTAÑA ACTIVA (MAPA ~60% IZQ + PANEL ~40% DER) */}
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
            onSelectPoint={handleSelectPoint}
            onUpdateCustomPolygon={handleUpdateCustomPolygon}
            onChangeGibsLayer={setActiveGibsLayer}
          />
        </section>

        <aside className="right-analysis-pane">
          {activeTab === 'planificacion' && (
            <>
              <CampaignConfigPanel
                campana={campana}
                cultivoAnterior={cultivoAnterior}
                objetivoProductor={objetivoProductor}
                onChangeCampana={setCampana}
                onChangeCultivoAnterior={setCultivoAnterior}
                onChangeObjetivo={setObjetivoProductor}
              />

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

          {activeTab === 'info_general' && (
            <TelemetryCards
              ubicacion={simulationResult.ubicacion}
              loteLabel={currentLoteLabel}
              superficieHa={currentSuperficieHa}
              telemetria={simulationResult.telemetria_nasa}
              perfilSuelo={simulationResult.perfil_suelo}
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
        </aside>
      </main>
    </div>
  )
}

export default App
