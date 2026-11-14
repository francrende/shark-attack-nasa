import { useEffect, useState } from 'react'
import {
  CircleMarker,
  MapContainer,
  Polygon,
  Polyline,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import {
  CheckCircle2,
  Info,
  Layers,
  MapPin,
  Pentagon,
  RotateCcw,
  Trash2,
} from 'lucide-react'
import {
  DEMO_FIELDS,
  getConsolidatedGibsDate,
  NASA_GIBS_LAYERS,
} from '../data/demoFields'
import {
  getLotHistoricalVisualForYear,
  type HistoricalMetricId,
} from '../data/historicalData'
import { THEME_COLORS } from '../theme/mapColors'
import type {
  Coordenadas,
  DemoField,
  GibsLayerId,
  SelectionMode,
} from '../types/api'
import { formatShortHumanDate } from '../utils/formatters'
import {
  buildNasaGibsTileUrl,
  calculateCentroid,
  calculatePolygonAreaHa,
} from '../utils/geo'

export interface HistoricalMapConfig {
  active: boolean
  year: number
  metric: HistoricalMetricId
  gibsDateIso: string
}

interface MapViewProps {
  selectedCoords: Coordenadas
  selectionMode: SelectionMode
  selectedDemoFieldId: string | null
  customPolygon: [number, number][]
  isPolygonClosed: boolean
  activeGibsLayer: GibsLayerId
  historicalMode?: HistoricalMapConfig
  onSelectDemoField: (field: DemoField) => void
  onChangeSelectionMode: (mode: SelectionMode) => void
  onUpdateCustomPolygon: (
    points: [number, number][],
    isClosed: boolean,
    centroid?: Coordenadas
  ) => void
  onChangeGibsLayer: (layerId: GibsLayerId) => void
}

function MapCameraController({
  targetCoords,
  zoom,
}: {
  targetCoords: Coordenadas
  zoom: number
}) {
  const map = useMap()

  useEffect(() => {
    map.flyTo([targetCoords.lat, targetCoords.lon], zoom, {
      duration: 1.1,
    })
  }, [map, targetCoords.lat, targetCoords.lon, zoom])

  return null
}

function MapInteractionHandler({
  selectionMode,
  isPolygonClosed,
  onMapClick,
  onZoomChange,
}: {
  selectionMode: SelectionMode
  isPolygonClosed: boolean
  onMapClick: (lat: number, lon: number) => void
  onZoomChange: (zoom: number) => void
}) {
  const map = useMapEvents({
    click(e) {
      if (selectionMode === 'polygon' && !isPolygonClosed) {
        onMapClick(e.latlng.lat, e.latlng.lng)
      }
    },
    zoomend() {
      onZoomChange(map.getZoom())
    },
  })
  return null
}

export function MapView({
  selectedCoords,
  selectionMode,
  selectedDemoFieldId,
  customPolygon,
  isPolygonClosed,
  activeGibsLayer,
  historicalMode,
  onSelectDemoField,
  onChangeSelectionMode,
  onUpdateCustomPolygon,
  onChangeGibsLayer,
}: MapViewProps) {
  const [gibsOpacity, setGibsOpacity] = useState<number>(0.62)
  const [currentZoom, setCurrentZoom] = useState<number>(13)
  const [cameraTarget, setCameraTarget] = useState<{
    coords: Coordenadas
    zoom: number
  }>({
    coords: selectedCoords,
    zoom: 13,
  })

  const currentGibsConfig =
    NASA_GIBS_LAYERS.find((l) => l.id === activeGibsLayer) ??
    NASA_GIBS_LAYERS[0]

  const isHistoricalActive = Boolean(historicalMode?.active)
  const gibsDateIso =
    isHistoricalActive && historicalMode
      ? historicalMode.gibsDateIso
      : getConsolidatedGibsDate()
  const gibsHumanShortDate = formatShortHumanDate(gibsDateIso)

  const drawnAreaHa = Math.round(calculatePolygonAreaHa(customPolygon))
  const drawnCentroid =
    customPolygon.length > 0 ? calculateCentroid(customPolygon) : selectedCoords

  const selectedCoordHistoricalVisual =
    isHistoricalActive && historicalMode
      ? getLotHistoricalVisualForYear(
          selectedCoords,
          historicalMode.year,
          historicalMode.metric
        )
      : null

  // Aviso cuando la capa temática es de baja resolución nativa (SMAP/IMERG = nivel 6) y el zoom es alto
  const isCoarseLayerZoomedIn =
    currentGibsConfig.id !== 'none' &&
    currentGibsConfig.maxNativeZoom <= 6 &&
    currentZoom > 8

  const handleDemoFieldSelect = (field: DemoField) => {
    setCameraTarget({ coords: field.centroide, zoom: 14 })
    onSelectDemoField(field)
  }

  const handleInteractiveMapClick = (lat: number, lon: number) => {
    const roundedLat = Math.round(lat * 10000) / 10000
    const roundedLon = Math.round(lon * 10000) / 10000

    if (selectionMode === 'polygon' && !isPolygonClosed) {
      const nextPoints: [number, number][] = [
        ...customPolygon,
        [roundedLat, roundedLon],
      ]
      const centroid = calculateCentroid(nextPoints)
      onUpdateCustomPolygon(nextPoints, false, centroid)
    }
  }

  const handleUndoVertex = () => {
    if (customPolygon.length === 0) return
    const nextPoints = customPolygon.slice(0, -1)
    const centroid =
      nextPoints.length > 0 ? calculateCentroid(nextPoints) : selectedCoords
    onUpdateCustomPolygon(nextPoints, false, centroid)
  }

  const handleClosePolygon = () => {
    if (customPolygon.length < 3) return
    const centroid = calculateCentroid(customPolygon)
    onUpdateCustomPolygon(customPolygon, true, centroid)
  }

  const handleClearPolygon = () => {
    onUpdateCustomPolygon([], false)
  }

  return (
    <div className="map-wrapper">
      {/* PANEL FLOTANTE 1 (SUPERIOR): SELECCIÓN DE LOTE */}
      <div className="map-overlay-top">
        <div
          className="map-mode-switcher"
          role="group"
          aria-label="Modo de selección de lote"
        >
          <button
            type="button"
            className={`mode-btn ${selectionMode === 'demo' ? 'active' : ''}`}
            onClick={() => onChangeSelectionMode('demo')}
          >
            <MapPin size={15} />
            <span>Lotes de ejemplo</span>
          </button>
          <button
            type="button"
            className={`mode-btn ${selectionMode === 'polygon' ? 'active' : ''}`}
            onClick={() => onChangeSelectionMode('polygon')}
          >
            <Pentagon size={15} />
            <span>Delimitar lote</span>
          </button>
        </div>

        {/* SUB-BARRA CONTEXTUAL SEGÚN EL MODO ELEGIDO */}
        {selectionMode === 'demo' && (
          <div className="map-demo-pills">
            {DEMO_FIELDS.map((field) => {
              const isSelected = field.id === selectedDemoFieldId
              return (
                <button
                  key={field.id}
                  type="button"
                  className={`demo-pill ${isSelected ? 'selected' : ''}`}
                  onClick={() => handleDemoFieldSelect(field)}
                >
                  <span className="demo-pill-dot" />
                  <span>{field.localidad}</span>
                  <span className="demo-pill-ha">{field.superficieHa} ha</span>
                </button>
              )
            })}
          </div>
        )}

        {selectionMode === 'polygon' && (
          <div className="map-polygon-toolbar">
            <div className="polygon-status">
              <span className="polygon-badge">
                {isPolygonClosed
                  ? 'Lote cerrado'
                  : customPolygon.length === 0
                    ? 'Marque los vértices del lote en el mapa'
                    : `${customPolygon.length} vértices marcados`}
              </span>
              {customPolygon.length >= 3 && (
                <span className="polygon-metrics">
                  <strong>{drawnAreaHa} ha</strong> · Ubicación:{' '}
                  <code>
                    {drawnCentroid.lat.toFixed(3)}, {drawnCentroid.lon.toFixed(3)}
                  </code>
                </span>
              )}
            </div>
            <div className="polygon-actions">
              <button
                type="button"
                className="poly-action-btn"
                onClick={handleUndoVertex}
                disabled={customPolygon.length === 0}
                title="Deshacer último vértice"
              >
                <RotateCcw size={14} />
                <span>Deshacer</span>
              </button>
              <button
                type="button"
                className="poly-action-btn primary"
                onClick={handleClosePolygon}
                disabled={customPolygon.length < 3 || isPolygonClosed}
                title="Cerrar polígono y calcular recomendación"
              >
                <CheckCircle2 size={14} />
                <span>Cerrar lote</span>
              </button>
              <button
                type="button"
                className="poly-action-btn danger"
                onClick={handleClearPolygon}
                disabled={customPolygon.length === 0}
                title="Limpiar polígono"
              >
                <Trash2 size={14} />
                <span>Limpiar</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* VISOR SATELITAL LEAFLET */}
      <MapContainer
        center={[selectedCoords.lat, selectedCoords.lon]}
        zoom={13}
        className="leaflet-map-container"
        zoomControl={false}
      >
        <MapCameraController
          targetCoords={cameraTarget.coords}
          zoom={cameraTarget.zoom}
        />
        <MapInteractionHandler
          selectionMode={selectionMode}
          isPolygonClosed={isPolygonClosed}
          onMapClick={handleInteractiveMapClick}
          onZoomChange={setCurrentZoom}
        />

        {/* 1. Capa Base ("Mapa satelital" Esri WorldImagery) */}
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          attribution="Tiles &copy; Esri"
          maxZoom={18}
        />

        {/* 2. Capa Temática NASA GIBS WMTS (actualiza su fecha en modo histórico) */}
        {currentGibsConfig.id !== 'none' &&
          currentGibsConfig.nasaLayerIdentifier && (
            <TileLayer
              key={`${currentGibsConfig.id}-${gibsDateIso}`}
              url={buildNasaGibsTileUrl(
                currentGibsConfig.nasaLayerIdentifier,
                gibsDateIso,
                currentGibsConfig.tileMatrixSet,
                currentGibsConfig.format
              )}
              opacity={gibsOpacity}
              maxNativeZoom={currentGibsConfig.maxNativeZoom}
              maxZoom={18}
              attribution="NASA EOSDIS GIBS"
            />
          )}

        {/* 3. Etiquetas de Localidades y Caminos */}
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
          opacity={0.75}
          maxZoom={18}
        />

        {/* 4. Polígonos de Lotes de ejemplo (cambian de color/dato en vivo en Información histórica) */}
        {DEMO_FIELDS.map((field) => {
          const isSelected =
            selectionMode === 'demo' && field.id === selectedDemoFieldId

          const histVisual =
            isHistoricalActive && historicalMode
              ? getLotHistoricalVisualForYear(
                  field.centroide,
                  historicalMode.year,
                  historicalMode.metric
                )
              : null

          const strokeColor = histVisual
            ? isSelected
              ? THEME_COLORS.bg
              : histVisual.strokeColor
            : isSelected
              ? THEME_COLORS.primary
              : THEME_COLORS.earthBrown

          const fillColor = histVisual
            ? histVisual.fillColor
            : isSelected
              ? THEME_COLORS.primary
              : THEME_COLORS.goldYellow

          const fillOpacity = histVisual
            ? isSelected
              ? 0.52
              : 0.32
            : isSelected
              ? 0.35
              : 0.16

          return (
            <Polygon
              key={`${field.id}-${historicalMode?.year ?? 'now'}-${historicalMode?.metric ?? 'base'}`}
              positions={field.poligono}
              pathOptions={{
                color: strokeColor,
                weight: isSelected ? 3 : 2,
                fillColor,
                fillOpacity,
              }}
              eventHandlers={{
                click: () => {
                  onChangeSelectionMode('demo')
                  handleDemoFieldSelect(field)
                },
              }}
            >
              <Tooltip sticky direction="top">
                <div className="map-tooltip-title">{field.nombre}</div>
                <div className="map-tooltip-sub">
                  {histVisual
                    ? histVisual.detailText
                    : `${field.superficieHa} ha · Agua en las raíces: ${Math.round(field.telemetriaBase.indice_humedad_radicular_pct)}%`}
                </div>
              </Tooltip>
            </Polygon>
          )
        })}

        {/* 5. Polígono Dibujado por el Productor */}
        {selectionMode === 'polygon' && customPolygon.length > 0 && (
          <>
            {isPolygonClosed || customPolygon.length >= 3 ? (
              <Polygon
                positions={customPolygon}
                pathOptions={{
                  color: selectedCoordHistoricalVisual
                    ? THEME_COLORS.bg
                    : isPolygonClosed
                      ? THEME_COLORS.primary
                      : THEME_COLORS.heatSoil,
                  weight: 3,
                  dashArray: isPolygonClosed ? undefined : '6 6',
                  fillColor: selectedCoordHistoricalVisual
                    ? selectedCoordHistoricalVisual.fillColor
                    : isPolygonClosed
                      ? THEME_COLORS.primary
                      : THEME_COLORS.heatSoil,
                  fillOpacity: selectedCoordHistoricalVisual ? 0.48 : 0.3,
                }}
              />
            ) : (
              <Polyline
                positions={customPolygon}
                pathOptions={{
                  color: THEME_COLORS.heatSoil,
                  weight: 3,
                  dashArray: '6 6',
                }}
              />
            )}

            {customPolygon.map(([lat, lon], idx) => (
              <CircleMarker
                key={`${lat}-${lon}-${idx}`}
                center={[lat, lon]}
                radius={5}
                pathOptions={{
                  color: THEME_COLORS.bg,
                  weight: 2,
                  fillColor: THEME_COLORS.heatSoil,
                  fillOpacity: 1,
                }}
              >
                <Tooltip direction="top">Esquina #{idx + 1}</Tooltip>
              </CircleMarker>
            ))}
          </>
        )}

        {/* 6. Marcador de la Ubicación del Lote (muestra el dato del año en vivo en modo histórico) */}
        <CircleMarker
          center={[selectedCoords.lat, selectedCoords.lon]}
          radius={8}
          pathOptions={{
            color: THEME_COLORS.bg,
            weight: 3,
            fillColor: selectedCoordHistoricalVisual
              ? selectedCoordHistoricalVisual.fillColor
              : THEME_COLORS.primary,
            fillOpacity: 1,
          }}
        >
          <Tooltip
            key={`${historicalMode?.year ?? 'live'}-${historicalMode?.metric ?? 'base'}`}
            permanent
            direction="right"
            offset={[10, 0]}
          >
            <span className="map-point-label">
              {selectedCoordHistoricalVisual
                ? selectedCoordHistoricalVisual.badgeText
                : `Ubicación del lote (${selectedCoords.lat.toFixed(3)}, ${selectedCoords.lon.toFixed(3)})`}
            </span>
          </Tooltip>
        </CircleMarker>
      </MapContainer>

      {/* PANEL FLOTANTE 2 (INFERIOR): CAPAS TEMÁTICAS Y LEYENDA */}
      <div className="map-overlay-bottom">
        <div className="gibs-panel-header">
          <div className="gibs-title">
            <Layers size={15} />
            <span>
              {isHistoricalActive && historicalMode
                ? `Capas del mapa · Campaña ${historicalMode.year} (${gibsHumanShortDate} ${historicalMode.year})`
                : `Capas del mapa · Imagen del ${gibsHumanShortDate}`}
            </span>
          </div>
          {currentGibsConfig.id !== 'none' && (
            <label className="gibs-opacity-control">
              <span>Intensidad {Math.round(gibsOpacity * 100)}%</span>
              <input
                type="range"
                aria-label="Intensidad de la capa del mapa"
                min={0.15}
                max={0.95}
                step={0.05}
                value={gibsOpacity}
                onChange={(e) => setGibsOpacity(parseFloat(e.target.value))}
              />
            </label>
          )}
        </div>

        <div className="gibs-layer-buttons">
          {NASA_GIBS_LAYERS.map((layer) => {
            const isActive = layer.id === activeGibsLayer
            return (
              <button
                key={layer.id}
                type="button"
                className={`gibs-btn cat-${layer.category} ${isActive ? 'active' : ''}`}
                onClick={() => onChangeGibsLayer(layer.id)}
              >
                {layer.shortLabel}
              </button>
            )
          })}
        </div>

        <div className="gibs-layer-meta">
          <span className="gibs-layer-desc">{currentGibsConfig.description}</span>
          {currentGibsConfig.legendGradient && (
            <div className="gibs-legend-bar-wrap">
              <span>{currentGibsConfig.legendMinLabel}</span>
              <div
                className="gibs-legend-bar"
                style={{ background: currentGibsConfig.legendGradient }}
              />
              <span>{currentGibsConfig.legendMaxLabel}</span>
            </div>
          )}
        </div>

        {/* Regla §5: aviso sutil cuando una capa regional (SMAP/IMERG) se mira con mucho zoom */}
        {isCoarseLayerZoomedIn && (
          <div className="gibs-coarse-note">
            <Info size={13} />
            <span>
              Esta capa muestra la tendencia de la zona, no el detalle del lote.
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
