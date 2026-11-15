import { useEffect, useMemo, useState } from 'react'
import L from 'leaflet'
import {
  CircleMarker,
  MapContainer,
  Marker,
  Polygon,
  Polyline,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import {
  type HistoricalMetricId,
  type VisualHistorico,
} from '../data/historicalData'
import { getFieldColorByIndex, THEME_COLORS } from '../theme/mapColors'
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
  /** FRONT-39: color y textos reales del lote seleccionado para la campaña (null sin datos). */
  visual: VisualHistorico | null
}

const VERTEX_HANDLE_ICON = L.divIcon({
  className: 'poly-vertex-handle',
  iconSize: [14, 14],
  iconAnchor: [7, 7],
})

const MIDPOINT_HANDLE_ICON = L.divIcon({
  className: 'poly-midpoint-handle',
  html: '+',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
})

export interface SearchCameraTarget {
  label: string
  coords: Coordenadas
  zoom: number
  bounds?: [[number, number], [number, number]]
  polygons?: [number, number][][][]
  requestId: number
}

interface MapViewProps {
  selectedCoords: Coordenadas
  userFields: UserField[]
  selectedFieldId: string | null
  editingFieldId?: string | null
  isDrawingNewField: boolean
  customPolygon: [number, number][]
  historicalMode?: HistoricalMapConfig
  selectedProvinces: string[]
  searchTarget?: SearchCameraTarget | null
  fieldFocusRequestId?: number
  onOutsideProvinceClick?: (message: string) => void
  onSelectUserField: (field: UserField) => void
  onUpdateCustomPolygon: (
    points: [number, number][],
    centroid?: Coordenadas
  ) => void
}

function getPolygonBounds(points: [number, number][]): LatLngBoundsTuple | null {
  if (points.length < 3) return null
  let south = Infinity
  let west = Infinity
  let north = -Infinity
  let east = -Infinity
  for (const [lat, lon] of points) {
    if (lat < south) south = lat
    if (lat > north) north = lat
    if (lon < west) west = lon
    if (lon > east) east = lon
  }
  return [
    [south, west],
    [north, east],
  ]
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

function MapCameraController({
  targetCoords,
  zoom,
  fitBoundsTarget,
  boundsMaxZoom,
  searchRequestId,
  fieldFocusRequestId,
}: {
  targetCoords: Coordenadas
  zoom: number
  /** Si está definido (búsqueda por área, campo o vista de provincias), encuadra estos bounds en lugar de volar al punto. */
  fitBoundsTarget: LatLngBoundsTuple | null
  boundsMaxZoom?: number
  searchRequestId: number
  fieldFocusRequestId: number
}) {
  const map = useMap()
  const [[south, west], [north, east]] = fitBoundsTarget ?? [
    [0, 0],
    [0, 0],
  ]
  const hasBounds = fitBoundsTarget !== null

  useEffect(() => {
    const animate = !prefersReducedMotion()
    map.stop()
    if (hasBounds) {
      const bounds: LatLngBoundsTuple = [
        [south, west],
        [north, east],
      ]
      const pad: [number, number] =
        searchRequestId > 0 ? [20, 20] : fieldFocusRequestId > 0 ? [48, 48] : [32, 32]
      if (animate) {
        map.flyToBounds(bounds, {
          padding: pad,
          maxZoom: boundsMaxZoom,
          duration: 1.1,
        })
      } else {
        map.fitBounds(bounds, {
          padding: pad,
          maxZoom: boundsMaxZoom,
          animate: false,
        })
      }
      return
    }
    if (animate) {
      map.flyTo([targetCoords.lat, targetCoords.lon], zoom, {
        duration: 1.1,
      })
    } else {
      map.setView([targetCoords.lat, targetCoords.lon], zoom, { animate: false })
    }
  }, [
    map,
    hasBounds,
    south,
    west,
    north,
    east,
    boundsMaxZoom,
    targetCoords.lat,
    targetCoords.lon,
    zoom,
    searchRequestId,
    fieldFocusRequestId,
  ])

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
  editingFieldId = null,
  isDrawingNewField,
  customPolygon,
  historicalMode,
  selectedProvinces,
  searchTarget = null,
  fieldFocusRequestId = 0,
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

  const selectedFieldBounds = useMemo(() => {
    if (!selectedFieldId) return null
    const field = userFields.find((f) => f.id === selectedFieldId)
    return field?.polygon ? getPolygonBounds(field.polygon) : null
  }, [userFields, selectedFieldId])

  const [cameraTarget, setCameraTarget] = useState<{
    coords: Coordenadas
    zoom: number
    bounds: LatLngBoundsTuple | null
  }>({
    coords: selectedCoords,
    zoom: 13,
    bounds: null,
  })

  useEffect(() => {
    if (!isDrawingNewField && selectedFieldId) {
      setCameraTarget({
        coords: selectedCoords,
        zoom: 14,
        bounds: selectedFieldBounds,
      })
    }
  }, [
    selectedFieldId,
    selectedCoords.lat,
    selectedCoords.lon,
    selectedFieldBounds,
    isDrawingNewField,
    fieldFocusRequestId,
  ])

  useEffect(() => {
    if (editingFieldId) {
      setCameraTarget({
        coords: selectedCoords,
        zoom: 14,
        bounds: selectedFieldBounds,
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editingFieldId])

  const isHistoricalActive = Boolean(historicalMode?.active)

  // FRONT-39: solo el lote seleccionado tiene historial real (se pide al backend al abrir la pestaña).
  const selectedCoordHistoricalVisual =
    isHistoricalActive && historicalMode ? historicalMode.visual : null

  const commitPolygonPoints = (nextPoints: [number, number][]) => {
    const centroid =
      nextPoints.length > 0 ? calculateCentroid(nextPoints) : undefined
    onUpdateCustomPolygon(nextPoints, centroid)
  }

  const handleInteractiveMapClick = (lat: number, lon: number) => {
    if (!isDrawingNewField) return
    if (!isPointInProvinces(lat, lon, selectedProvinces)) {
      onOutsideProvinceClick?.(OUTSIDE_PROVINCE_MESSAGE)
      return
    }
    const roundedLat = Math.round(lat * 10000) / 10000
    const roundedLon = Math.round(lon * 10000) / 10000
    commitPolygonPoints([...customPolygon, [roundedLat, roundedLon]])
  }

  const handleMoveVertex = (
    idx: number,
    lat: number,
    lon: number,
    notifyOutside = false
  ): boolean => {
    if (!isPointInProvinces(lat, lon, selectedProvinces)) {
      if (notifyOutside) {
        onOutsideProvinceClick?.(OUTSIDE_PROVINCE_MESSAGE)
      }
      return false
    }
    const roundedLat = Math.round(lat * 10000) / 10000
    const roundedLon = Math.round(lon * 10000) / 10000
    const nextPoints = customPolygon.map((pt, pointIdx): [number, number] =>
      pointIdx === idx ? [roundedLat, roundedLon] : pt
    )
    commitPolygonPoints(nextPoints)
    return true
  }

  const handleRemoveVertex = (idx: number) => {
    if (customPolygon.length <= 3) return
    commitPolygonPoints(customPolygon.filter((_, pointIdx) => pointIdx !== idx))
  }

  const handleInsertMidpoint = (
    afterIdx: number,
    lat: number,
    lon: number
  ) => {
    if (!isPointInProvinces(lat, lon, selectedProvinces)) {
      onOutsideProvinceClick?.(OUTSIDE_PROVINCE_MESSAGE)
      return
    }
    const nextPoints = [...customPolygon]
    nextPoints.splice(afterIdx + 1, 0, [lat, lon])
    commitPolygonPoints(nextPoints)
  }

  const activeTargetCoords = searchTarget
    ? searchTarget.coords
    : cameraTarget.coords
  const activeTargetZoom = searchTarget ? searchTarget.zoom : cameraTarget.zoom
  const activeFitBounds = searchTarget
    ? searchTarget.bounds ?? null
    : selectedFieldId === null
      ? provinceBounds
      : cameraTarget.bounds
  const activeBoundsMaxZoom = searchTarget?.bounds
    ? 15
    : cameraTarget.bounds
      ? 16
      : undefined

  return (
    <div className="map-wrapper">
      {/* VISOR SATELITAL LEAFLET */}
      <MapContainer
        center={[selectedCoords.lat, selectedCoords.lon]}
        zoom={13}
        className="leaflet-map-container"
        zoomControl={false}
        attributionControl={false}
      >
        <MapCameraController
          targetCoords={activeTargetCoords}
          zoom={activeTargetZoom}
          fitBoundsTarget={activeFitBounds}
          boundsMaxZoom={activeBoundsMaxZoom}
          searchRequestId={searchTarget?.requestId ?? 0}
          fieldFocusRequestId={fieldFocusRequestId}
        />
        <MapInteractionHandler
          isDrawingNewField={isDrawingNewField}
          onMapClick={handleInteractiveMapClick}
        />

        {/* 1. Capa Base ("Mapa satelital" Esri WorldImagery) */}
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
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
        {userFields.map((field, idx) => {
          if (field.id === editingFieldId) return null
          const isSelected = !isDrawingNewField && field.id === selectedFieldId
          const { hex: fieldColor } = getFieldColorByIndex(idx)

          const histVisual =
            isHistoricalActive && historicalMode && isSelected ? historicalMode.visual : null

          const strokeColor = histVisual
            ? isSelected
              ? THEME_COLORS.bg
              : histVisual.strokeColor
            : fieldColor

          const fillColor = histVisual ? histVisual.fillColor : fieldColor

          const fillOpacity = histVisual
            ? isSelected
              ? 0.58
              : 0.36
            : isSelected
              ? 0.65
              : 0.24

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
                  weight: isSelected ? 3.5 : 2,
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
              <Marker
                key={`poly-vertex-${idx}`}
                position={[lat, lon]}
                icon={VERTEX_HANDLE_ICON}
                draggable
                eventHandlers={{
                  click: (e) => {
                    L.DomEvent.stopPropagation(e)
                  },
                  drag: (e) => {
                    const pos = e.target.getLatLng()
                    handleMoveVertex(idx, pos.lat, pos.lng)
                  },
                  dragend: (e) => {
                    const pos = e.target.getLatLng()
                    const moved = handleMoveVertex(idx, pos.lat, pos.lng, true)
                    if (!moved && customPolygon[idx]) {
                      e.target.setLatLng(customPolygon[idx])
                    }
                  },
                  contextmenu: (e) => {
                    L.DomEvent.stopPropagation(e)
                    handleRemoveVertex(idx)
                  },
                }}
              >
                <Tooltip direction="top">
                  {customPolygon.length > 3
                    ? `Esquina #${idx + 1} · Arrastrar o clic derecho para quitar`
                    : `Esquina #${idx + 1} · Arrastrar para ajustar`}
                </Tooltip>
              </Marker>
            ))}

            {customPolygon.length >= 3 &&
              customPolygon.map(([lat, lon], idx) => {
                const [nextLat, nextLon] =
                  customPolygon[(idx + 1) % customPolygon.length]
                const midLat = Math.round(((lat + nextLat) / 2) * 10000) / 10000
                const midLon = Math.round(((lon + nextLon) / 2) * 10000) / 10000
                return (
                  <Marker
                    key={`poly-mid-${idx}`}
                    position={[midLat, midLon]}
                    icon={MIDPOINT_HANDLE_ICON}
                    eventHandlers={{
                      click: (e) => {
                        L.DomEvent.stopPropagation(e)
                        handleInsertMidpoint(idx, midLat, midLon)
                      },
                    }}
                  >
                    <Tooltip direction="top">Agregar esquina</Tooltip>
                  </Marker>
                )
              })}
          </>
        )}

        {/* 6. Límites o marcador de ubicación buscada */}
        {searchTarget && !isDrawingNewField && searchTarget.polygons?.length ? (
          <Polygon
            positions={searchTarget.polygons}
            pathOptions={{
              color: THEME_COLORS.terracottaDark,
              weight: 2.5,
              dashArray: '6 5',
              fillColor: THEME_COLORS.terracotta,
              fillOpacity: 0.08,
              interactive: false,
            }}
          />
        ) : null}

        {searchTarget && !isDrawingNewField && (
          <CircleMarker
            center={[searchTarget.coords.lat, searchTarget.coords.lon]}
            radius={searchTarget.polygons?.length ? 5 : 7}
            interactive={false}
            pathOptions={{
              color: THEME_COLORS.terracottaDark,
              weight: 2.5,
              fillColor: THEME_COLORS.bg,
              fillOpacity: 0.95,
            }}
          >
            <Tooltip permanent direction="top" offset={[0, -8]}>
              <span className="map-point-label">{searchTarget.label}</span>
            </Tooltip>
          </CircleMarker>
        )}

        {/* 7. Marcador de la Ubicación del Lote (muestra el dato del año en vivo en modo histórico) */}
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
