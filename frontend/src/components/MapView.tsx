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
import { Info, Layers } from 'lucide-react'
import {
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
  GibsLayerId,
  UserField,
} from '../types/api'
import { formatShortHumanDate } from '../utils/formatters'
import {
  buildNasaGibsTileUrl,
  calculateCentroid,
} from '../utils/geo'

export interface HistoricalMapConfig {
  active: boolean
  year: number
  metric: HistoricalMetricId
  gibsDateIso: string
}

interface MapViewProps {
  selectedCoords: Coordenadas
  userFields: UserField[]
  selectedFieldId: string | null
  isDrawingNewField: boolean
  customPolygon: [number, number][]
  activeGibsLayer: GibsLayerId
  historicalMode?: HistoricalMapConfig
  onSelectUserField: (field: UserField) => void
  onUpdateCustomPolygon: (
    points: [number, number][],
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
  isDrawingNewField,
  onMapClick,
  onZoomChange,
}: {
  isDrawingNewField: boolean
  onMapClick: (lat: number, lon: number) => void
  onZoomChange: (zoom: number) => void
}) {
  const map = useMapEvents({
    click(e) {
      if (isDrawingNewField) {
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
  userFields,
  selectedFieldId,
  isDrawingNewField,
  customPolygon,
  activeGibsLayer,
  historicalMode,
  onSelectUserField,
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

  useEffect(() => {
    if (!isDrawingNewField && selectedFieldId) {
      setCameraTarget({ coords: selectedCoords, zoom: 14 })
    }
  }, [selectedFieldId, selectedCoords.lat, selectedCoords.lon, isDrawingNewField])

  const currentGibsConfig =
    NASA_GIBS_LAYERS.find((l) => l.id === activeGibsLayer) ??
    NASA_GIBS_LAYERS[0]

  const isHistoricalActive = Boolean(historicalMode?.active)
  const gibsDateIso =
    isHistoricalActive && historicalMode
      ? historicalMode.gibsDateIso
      : getConsolidatedGibsDate()
  const gibsHumanShortDate = formatShortHumanDate(gibsDateIso)

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

  const handleInteractiveMapClick = (lat: number, lon: number) => {
    if (!isDrawingNewField) return
    const roundedLat = Math.round(lat * 10000) / 10000
    const roundedLon = Math.round(lon * 10000) / 10000
    const nextPoints: [number, number][] = [
      ...customPolygon,
      [roundedLat, roundedLon],
    ]
    const centroid = calculateCentroid(nextPoints)
    onUpdateCustomPolygon(nextPoints, centroid)
  }

  return (
    <div className="map-wrapper">
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
          isDrawingNewField={isDrawingNewField}
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

        {/* 4. Campos del Usuario desde la Base de Datos */}
        {userFields.map((field) => {
          const isSelected = !isDrawingNewField && field.id === selectedFieldId
          const fieldCoords = { lat: field.lat, lon: field.lon }

          const histVisual =
            isHistoricalActive && historicalMode
              ? getLotHistoricalVisualForYear(
                  fieldCoords,
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

          const tooltipContent = (
            <Tooltip sticky direction="top">
              <div className="map-tooltip-title">{field.nombre}</div>
              <div className="map-tooltip-sub">
                {histVisual
                  ? histVisual.detailText
                  : field.hectareas !== null
                    ? `${Math.round(field.hectareas)} ha`
                    : `${field.lat.toFixed(3)}, ${field.lon.toFixed(3)}`}
              </div>
            </Tooltip>
          )

          if (field.polygon && field.polygon.length >= 3) {
            return (
              <Polygon
                key={`${field.id}-${historicalMode?.year ?? 'now'}-${historicalMode?.metric ?? 'base'}`}
                positions={field.polygon}
                pathOptions={{
                  color: strokeColor,
                  weight: isSelected ? 3 : 2,
                  fillColor,
                  fillOpacity,
                }}
                eventHandlers={{
                  click: () => onSelectUserField(field),
                }}
              >
                {tooltipContent}
              </Polygon>
            )
          }

          return (
            <CircleMarker
              key={`${field.id}-${historicalMode?.year ?? 'now'}-${historicalMode?.metric ?? 'base'}`}
              center={[field.lat, field.lon]}
              radius={isSelected ? 10 : 7}
              pathOptions={{
                color: strokeColor,
                weight: isSelected ? 3 : 2,
                fillColor,
                fillOpacity: 0.75,
              }}
              eventHandlers={{
                click: () => onSelectUserField(field),
              }}
            >
              {tooltipContent}
            </CircleMarker>
          )
        })}

        {/* 5. Polígono en Delimitación para Nuevo Campo */}
        {isDrawingNewField && customPolygon.length > 0 && (
          <>
            {customPolygon.length >= 3 ? (
              <Polygon
                positions={customPolygon}
                pathOptions={{
                  color: THEME_COLORS.heatSoil,
                  weight: 3,
                  dashArray: '6 6',
                  fillColor: THEME_COLORS.heatSoil,
                  fillOpacity: 0.28,
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
