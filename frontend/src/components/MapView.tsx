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
  Crosshair,
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
import type {
  Coordenadas,
  DemoField,
  GibsLayerId,
  SelectionMode,
} from '../types/api'
import {
  buildNasaGibsTileUrl,
  calculateCentroid,
  calculatePolygonAreaHa,
} from '../utils/geo'

interface MapViewProps {
  selectedCoords: Coordenadas
  selectionMode: SelectionMode
  selectedDemoFieldId: string | null
  customPolygon: [number, number][]
  isPolygonClosed: boolean
  activeGibsLayer: GibsLayerId
  onSelectDemoField: (field: DemoField) => void
  onChangeSelectionMode: (mode: SelectionMode) => void
  onSelectPoint: (coords: Coordenadas) => void
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
      duration: 1.15,
    })
  }, [map, targetCoords.lat, targetCoords.lon, zoom])

  return null
}

function MapClickHandler({
  selectionMode,
  isPolygonClosed,
  onMapClick,
}: {
  selectionMode: SelectionMode
  isPolygonClosed: boolean
  onMapClick: (lat: number, lon: number) => void
}) {
  useMapEvents({
    click(e) {
      if (selectionMode === 'point') {
        onMapClick(e.latlng.lat, e.latlng.lng)
      } else if (selectionMode === 'polygon' && !isPolygonClosed) {
        onMapClick(e.latlng.lat, e.latlng.lng)
      }
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
  onSelectDemoField,
  onChangeSelectionMode,
  onSelectPoint,
  onUpdateCustomPolygon,
  onChangeGibsLayer,
}: MapViewProps) {
  const [gibsOpacity, setGibsOpacity] = useState<number>(0.62)
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
  const gibsDate = getConsolidatedGibsDate()

  const drawnAreaHa = calculatePolygonAreaHa(customPolygon)
  const drawnCentroid =
    customPolygon.length > 0 ? calculateCentroid(customPolygon) : selectedCoords

  const handleDemoFieldSelect = (field: DemoField) => {
    setCameraTarget({ coords: field.centroide, zoom: 14 })
    onSelectDemoField(field)
  }

  const handleInteractiveMapClick = (lat: number, lon: number) => {
    const roundedLat = Math.round(lat * 10000) / 10000
    const roundedLon = Math.round(lon * 10000) / 10000

    if (selectionMode === 'point') {
      onSelectPoint({ lat: roundedLat, lon: roundedLon })
    } else if (selectionMode === 'polygon' && !isPolygonClosed) {
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
      {/* BARRA FLOTANTE SUPERIOR: 3 MODOS DE SELECCIÓN DE LOTE */}
      <div className="map-overlay-top">
        <div className="map-mode-switcher">
          <button
            type="button"
            className={`mode-btn ${selectionMode === 'demo' ? 'active' : ''}`}
            onClick={() => onChangeSelectionMode('demo')}
          >
            <MapPin size={15} />
            <span>Lotes Demo</span>
          </button>
          <button
            type="button"
            className={`mode-btn ${selectionMode === 'polygon' ? 'active' : ''}`}
            onClick={() => onChangeSelectionMode('polygon')}
          >
            <Pentagon size={15} />
            <span>Dibujar Lote</span>
          </button>
          <button
            type="button"
            className={`mode-btn ${selectionMode === 'point' ? 'active' : ''}`}
            onClick={() => onChangeSelectionMode('point')}
          >
            <Crosshair size={15} />
            <span>Clic Rápido</span>
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
                    ? 'Hacé clic en el mapa para marcar vértices'
                    : `${customPolygon.length} vértices marcados`}
              </span>
              {customPolygon.length >= 3 && (
                <span className="polygon-metrics">
                  <strong>{drawnAreaHa} ha</strong> · Centroide:{' '}
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
                title="Deshacer último punto"
              >
                <RotateCcw size={14} />
                <span>Deshacer punto</span>
              </button>
              <button
                type="button"
                className="poly-action-btn primary"
                onClick={handleClosePolygon}
                disabled={customPolygon.length < 3 || isPolygonClosed}
                title="Cerrar polígono del lote y simular"
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

        {selectionMode === 'point' && (
          <div className="map-point-hint">
            <Crosshair size={14} />
            <span>
              Tocá cualquier punto del mapa para analizar el agua y el suelo de ese lote (
              <code>
                {selectedCoords.lat.toFixed(4)}, {selectedCoords.lon.toFixed(4)}
              </code>
              )
            </span>
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
        <MapClickHandler
          selectionMode={selectionMode}
          isPolygonClosed={isPolygonClosed}
          onMapClick={handleInteractiveMapClick}
        />

        {/* 1. Capa Base Óptica de Alta Resolución (Esri WorldImagery) */}
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          attribution="Tiles &copy; Esri &mdash; Source: Esri, USDA, USGS, GeoEye"
          maxZoom={18}
        />

        {/* 2. Superposición Satelital NASA GIBS WMTS (True Color por defecto, SMAP, NDVI, LST, IMERG) */}
        {currentGibsConfig.id !== 'none' &&
          currentGibsConfig.nasaLayerIdentifier && (
            <TileLayer
              key={`${currentGibsConfig.id}-${gibsDate}`}
              url={buildNasaGibsTileUrl(
                currentGibsConfig.nasaLayerIdentifier,
                gibsDate,
                currentGibsConfig.tileMatrixSet,
                currentGibsConfig.format
              )}
              opacity={gibsOpacity}
              maxNativeZoom={currentGibsConfig.maxNativeZoom}
              maxZoom={18}
              attribution="NASA EOSDIS GIBS / Worldview"
            />
          )}

        {/* 3. Etiquetas Híbridas de Localidades y Rutas */}
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
          opacity={0.75}
          maxZoom={18}
        />

        {/* 4. Polígonos de Lotes Demo pre-cargados */}
        {DEMO_FIELDS.map((field) => {
          const isSelected =
            selectionMode === 'demo' && field.id === selectedDemoFieldId
          return (
            <Polygon
              key={field.id}
              positions={field.poligono}
              pathOptions={{
                color: isSelected ? '#FFF5E0' : '#4B5B2D',
                weight: isSelected ? 3 : 2,
                fillColor: isSelected ? '#4B5B2D' : '#D99B26',
                fillOpacity: isSelected ? 0.38 : 0.2,
              }}
              eventHandlers={{
                click: () => {
                  onChangeSelectionMode('demo')
                  handleDemoFieldSelect(field)
                },
              }}
            >
              <Tooltip sticky direction="top">
                <div style={{ fontWeight: 700, color: '#4B5B2D' }}>
                  {field.nombre}
                </div>
                <div style={{ fontSize: '12px', color: '#22181C' }}>
                  {field.superficieHa} ha · Humedad Radicular:{' '}
                  {field.telemetriaBase.indice_humedad_radicular_pct}%
                </div>
              </Tooltip>
            </Polygon>
          )
        })}

        {/* 5. Polígono Dibujado por el Productor (Modo 'polygon') */}
        {selectionMode === 'polygon' && customPolygon.length > 0 && (
          <>
            {isPolygonClosed || customPolygon.length >= 3 ? (
              <Polygon
                positions={customPolygon}
                pathOptions={{
                  color: isPolygonClosed ? '#4B5B2D' : '#F05D23',
                  weight: 3,
                  dashArray: isPolygonClosed ? undefined : '6 6',
                  fillColor: isPolygonClosed ? '#4B5B2D' : '#F05D23',
                  fillOpacity: 0.32,
                }}
              />
            ) : (
              <Polyline
                positions={customPolygon}
                pathOptions={{
                  color: '#F05D23',
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
                  color: '#FFF5E0',
                  weight: 2,
                  fillColor: '#F05D23',
                  fillOpacity: 1,
                }}
              >
                <Tooltip direction="top">Vértice #{idx + 1}</Tooltip>
              </CircleMarker>
            ))}
          </>
        )}

        {/* 6. Marcador del Centroide / Coordenada Activa Analizada por NASA POWER */}
        <CircleMarker
          center={[selectedCoords.lat, selectedCoords.lon]}
          radius={8}
          pathOptions={{
            color: '#FFF5E0',
            weight: 3,
            fillColor: '#4B5B2D',
            fillOpacity: 1,
          }}
        >
          <Tooltip permanent direction="right" offset={[10, 0]}>
            <span
              style={{
                fontWeight: 700,
                fontSize: '11px',
                color: '#22181C',
              }}
            >
              Lote analizado ({selectedCoords.lat.toFixed(3)},{' '}
              {selectedCoords.lon.toFixed(3)})
            </span>
          </Tooltip>
        </CircleMarker>
      </MapContainer>

      {/* PANEL FLOTANTE INFERIOR: FILTROS VISUALES DEL MAPA EXPLICADOS EN SIMPLE */}
      <div className="map-overlay-bottom">
        <div className="gibs-panel-header">
          <div className="gibs-title">
            <Layers size={15} />
            <span>Filtros del Mapa: ¿Qué querés observar en la zona?</span>
          </div>
          {currentGibsConfig.id !== 'none' && (
            <label className="gibs-opacity-control">
              <span>Intensidad del filtro {Math.round(gibsOpacity * 100)}%</span>
              <input
                type="range"
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
      </div>
    </div>
  )
}
