import { useMemo, useState } from 'react'
import {
  Compass,
  History,
  Info,
  MessageSquare,
  Sprout,
} from 'lucide-react'
import './App.css'
import { MapView } from './components/MapView'
import { RecommendationPanel } from './components/RecommendationPanel'
import {
  CampaignConfigPanel,
  WhatIfPanel,
} from './components/SimulationControls'
import { TelemetryCards } from './components/TelemetryCards'
import { DEMO_FIELDS } from './data/demoFields'
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

export type NavTabId = 'info_general' | 'planificacion' | 'historico' | 'chat'

export function App() {
  const defaultField = DEMO_FIELDS[0]

  // Pestaña activa del menú superior
  const [activeTab, setActiveTab] = useState<NavTabId>('info_general')

  // Estado GIS y selección de lote
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
        ? 'Lote Dibujado por el Productor'
        : 'Dibujando Polígono en Mapa...'
    }
    return 'Punto Libre Seleccionado en Mapa'
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
      {/* HEADER SUPERIOR CON MENÚ DE 4 PESTAÑAS */}
      <header className="top-navbar">
        <div className="brand-block">
          <div className="brand-logo">
            <Sprout size={20} />
          </div>
          <div>
            <div className="brand-title-row">
              <h1>SHARK ATTACK</h1>
              <span className="nasa-challenge-badge">
                NASA Space Apps · Field Shift
              </span>
            </div>
            <p className="brand-subtitle">
              Planificación de Rotaciones y Eficiencia Hídrica para tu Campo
            </p>
          </div>
        </div>

        <nav className="top-nav-tabs" aria-label="Navegación principal">
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
            className={`nav-tab-btn ${activeTab === 'planificacion' ? 'active' : ''}`}
            onClick={() => setActiveTab('planificacion')}
          >
            <Compass size={15} />
            <span>Planificación de campaña</span>
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
            className={`nav-tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            <MessageSquare size={15} />
            <span>Chat</span>
          </button>
        </nav>
      </header>

      {/* CONTENIDO SEGÚN LA PESTAÑA ACTIVA */}
      {activeTab === 'chat' ? (
        /* En 'Chat' NO se muestra el mapa satelital */
        <main className="full-page-pane">
          <section className="panel-section empty-tab-section" />
        </main>
      ) : (
        /* En 'Info general', 'Planificación de campaña' e 'Información histórica' se muestra el Mapa a la izquierda */
        <main className="split-dashboard">
          <section className="left-map-pane">
            <MapView
              selectedCoords={selectedCoords}
              selectionMode={selectionMode}
              selectedDemoFieldId={selectedDemoFieldId}
              customPolygon={customPolygon}
              isPolygonClosed={isPolygonClosed}
              activeGibsLayer={activeGibsLayer}
              onSelectDemoField={handleSelectDemoField}
              onChangeSelectionMode={handleChangeSelectionMode}
              onSelectPoint={handleSelectPoint}
              onUpdateCustomPolygon={handleUpdateCustomPolygon}
              onChangeGibsLayer={setActiveGibsLayer}
            />
          </section>

          <aside className="right-analysis-pane">
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

            {activeTab === 'historico' && (
              <section className="panel-section empty-tab-section" />
            )}
          </aside>
        </main>
      )}
    </div>
  )
}

export default App
