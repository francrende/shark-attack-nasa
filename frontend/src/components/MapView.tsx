import { useEffect, useMemo, useState } from 'react'
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
  getLotHistoricalVisualForYear,
  type HistoricalMetricId,
} from '../data/historicalData'
import { THEME_COLORS } from '../theme/mapColors'
import type {
  Coordenadas,
  UserField,
} from '../types/api'
import {
  calculateCentroid,
  getProvinceLatLngPolygons,
  getProvincesBounds,
  isPointInProvinces,
} from '../utils/geo'

const OUTSIDE_PROVINCE_MESSAGE =
  'El punto está fuera de las provincias seleccionadas en la Región Pampeana.'

type LatLngBoundsTuple = [[number, number], [number, number]]

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
  historicalMode?: HistoricalMapConfig
  selectedProvinces: string[]
  onOutsideProvinceClick?: (message: string) => void
  onSelectUserField: (field: UserField) => void
  onUpdateCustomPolygon: (
    points: [number, number][],
    centroid?: Coordenadas
  ) => void
}

function MapCameraController({
  targetCoords,
  zoom,
  fitBoundsTarget,
}: {
  targetCoords: Coordenadas
  zoom: number
  /** Si está definido (sin campo seleccionado), encuadra estos bounds en lugar de volar al punto. */
  fitBoundsTarget: LatLngBoundsTuple | null
}) {
  const map = useMap()
  const [[south, west], [north, east]] = fitBoundsTarget ?? [
    [0, 0],
    [0, 0],
  ]
  const hasBounds = fitBoundsTarget !== null

  useEffect(() => {
    if (hasBounds) {
      map.fitBounds(
        [
          [south, west],
          [north, east],
        ],
        { padding: [32, 32], animate: true, duration: 1.1 }
      )
      return
    }
    map.flyTo([targetCoords.lat, targetCoords.lon], zoom, {
      duration: 1.1,
    })
  }, [map, hasBounds, south, west, north, east, targetCoords.lat, targetCoords.lon, zoom])

  return null
}

function MapInteractionHandler({
  isDrawingNewField,
  onMapClick,
}: {
  isDrawingNewField: boolean
  onMapClick: (lat: number, lon: number) => void
}) {
  useMapEvents({
    click(e) {
      if (isDrawingNewField) {
        onMapClick(e.latlng.lat, e.latlng.lng)
      }
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
  historicalMode,
  selectedProvinces,
  onOutsideProvinceClick,
  onSelectUserField,
  onUpdateCustomPolygon,
}: MapViewProps) {
  const provinceBounds = useMemo(
    () => getProvincesBounds(selectedProvinces),
    [selectedProvinces]
  )
  const provincePolygons = useMemo(
    () => getProvinceLatLngPolygons(selectedProvinces),
    [selectedProvinces]
  )

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

  const isHistoricalActive = Boolean(historicalMode?.active)

  const selectedCoordHistoricalVisual =
    isHistoricalActive && historicalMode
      ? getLotHistoricalVisualForYear(
          selectedCoords,
          historicalMode.year,
          historicalMode.metric
        )
      : null

  const handleInteractiveMapClick = (lat: number, lon: number) => {
    if (!isDrawingNewField) return
    if (!isPointInProvinces(lat, lon, selectedProvinces)) {
      onOutsideProvinceClick?.(OUTSIDE_PROVINCE_MESSAGE)
      return
    }
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
          fitBoundsTarget={selectedFieldId === null ? provinceBounds : null}
        />
        <MapInteractionHandler
          isDrawingNewField={isDrawingNewField}
          onMapClick={handleInteractiveMapClick}
        />

        {/* 1. Capa Base ("Mapa satelital" Esri WorldImagery) */}
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          attribution="Tiles &copy; Esri"
          maxZoom={18}
        />

        {/* 2. Etiquetas de Localidades y Caminos */}
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
          opacity={0.75}
          maxZoom={18}
        />

        {/* 3. Contornos de las provincias seleccionadas (no bloquean los clics del mapa) */}
        {provincePolygons.length > 0 && (
          <Polygon
            positions={provincePolygons}
            pathOptions={{
              color: THEME_COLORS.primary,
              weight: 2.5,
              fillColor: THEME_COLORS.primary,
              fillOpacity: 0.05,
              interactive: false,
            }}
          />
        )}

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
                key={field.id}
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
              key={field.id}
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
    </div>
  )
}
