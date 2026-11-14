import { useMemo, useState } from 'react'
import { Satellite, Sprout } from 'lucide-react'
import './App.css'
import { MapView } from './components/MapView'
import { RecommendationPanel } from './components/RecommendationPanel'
import { SimulationControls } from './components/SimulationControls'
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

export function App() {
  const defaultField = DEMO_FIELDS[0]

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
    useState<GibsLayerId>('modis_true_color')

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
      {/* HEADER SUPERIOR */}
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
              Planificación de Rotaciones y Eficiencia Hídrica con Telemetría
              Satelital NASA + SoilGrids
            </p>
          </div>
        </div>

        <div className="navbar-status-group">
          <div className="status-indicator">
            <Satellite size={14} />
            <span>Sensores: NASA POWER · SMAP L4 · MODIS · SoilGrids</span>
          </div>
        </div>
      </header>

      {/* LAYOUT SPLIT-SCREEN (~58% MAPA IZQ / ~42% PANEL LATERAL DER) */}
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
          <TelemetryCards
            ubicacion={simulationResult.ubicacion}
            loteLabel={currentLoteLabel}
            superficieHa={currentSuperficieHa}
            telemetria={simulationResult.telemetria_nasa}
            perfilSuelo={simulationResult.perfil_suelo}
            isWhatIfActive={isWhatIfActive}
          />

          <SimulationControls
            campana={campana}
            cultivoAnterior={cultivoAnterior}
            objetivoProductor={objetivoProductor}
            whatIf={whatIf}
            nasaDetectedHumidityPct={
              baselineResult.telemetria_nasa.indice_humedad_radicular_pct
            }
            onChangeCampana={setCampana}
            onChangeCultivoAnterior={setCultivoAnterior}
            onChangeObjetivo={setObjetivoProductor}
            onChangeWhatIf={setWhatIf}
            onResetWhatIf={handleResetWhatIf}
          />

          <RecommendationPanel
            recomendacion={simulationResult.recomendacion_principal}
            ranking={simulationResult.ranking_cultivos}
          />
        </aside>
      </main>
    </div>
  )
}

export default App
