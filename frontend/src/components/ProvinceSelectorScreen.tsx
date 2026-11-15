import { memo, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent, MouseEvent } from 'react'
import {
  ArrowLeft,
  Check,
  Loader2,
  LogOut,
  MapPin,
  RotateCcw,
  User,
  X,
} from 'lucide-react'
import { BrandBlock } from './BrandBlock'
import { THEME_COLORS } from '../theme/mapColors'
import {
  PAMPEAN_PROVINCE_IDS,
  getAllProvinces,
  getFeaturePolygons,
  getProvinceById,
} from '../utils/geo'

interface ProvinceSelectorScreenProps {
  /** Selección inicial (p. ej. al volver a editar el filtro). */
  initialSelected: string[]
  isSaving: boolean
  errorMsg: string | null
  isDemo: boolean
  userLabel?: string
  onApply: (provinceIds: string[]) => void
  /** Solo se informa al reeditar el filtro: permite volver al mapa sin cambios. */
  onCancel?: () => void
  onLogout: () => void
}

interface ProvinceShape {
  /** Identificador único de pieza visual (permite rotular Islas Malvinas aparte de Tierra del Fuego). */
  key: string
  /** ID oficial de provincia usado en selección y backend. */
  id: string
  nombre: string
  enabled: boolean
  path: string
  /** Centro vertical proyectado para ordenar el pintado de norte a sur. */
  sortY: number
}

// ---------------------------------------------------------------------------
// Proyección plana con inclinación 3D:
//   x = (lon - minLon) * cos(-38°),  y = (maxLat - lat) * TILT_Y
// Arquitectura de capas Z para garantizar coplanaridad en reposo y bordes nítidos:
//   1. Sombras base + zócalo 3D uniforme de las 24 provincias (siempre debajo).
//   2. Caras superiores de las 19 provincias bloqueadas en y=0 (mismo plano).
//   3. Sub-capas sincronizadas para las 5 habilitadas: sombras -> paredes -> caras.
//      En reposo (lift=0) quedan al ras en y=0; en hover/selección suben a LIFT_ACTIVE.
// ---------------------------------------------------------------------------

const MEAN_LAT_COS = Math.cos((-38 * Math.PI) / 180)
const TILT_Y = 0.62
const VIEWBOX_PADDING = 0.8
const BASE_EXTRUDE_LAYERS = 2
const BASE_DEPTH = 0.14
const LIFT_EXTRUDE_LAYERS = 3
const LIFT_THICKNESS = 0.13
const LIFT_ACTIVE = 0.18
const MALVINAS_LON_SPLIT = -62.5
const LOCKED_TOOLTIP = 'Próximamente — Región en expansión'
const MALVINAS_TOOLTIP = '¡Son argentinas!'

function buildShapeFromPolygons(
  key: string,
  id: string,
  nombre: string,
  enabled: boolean,
  polygons: [number, number][][][],
  project: (lon: number, lat: number) => [number, number],
  fmt: (n: number) => number
): ProvinceShape {
  let path = ''
  let largestArea = -1
  let sortY = 0

  for (const rings of polygons) {
    rings.forEach((ring, ringIndex) => {
      const projected = ring.map(([lon, lat]) => project(lon, lat))
      if (projected.length < 3) return
      path +=
        projected
          .map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${fmt(x)} ${fmt(y)}`)
          .join('') + 'Z'

      if (ringIndex === 0) {
        const xs = projected.map(([x]) => x)
        const ys = projected.map(([, y]) => y)
        const bx0 = Math.min(...xs)
        const bx1 = Math.max(...xs)
        const by0 = Math.min(...ys)
        const by1 = Math.max(...ys)
        const area = (bx1 - bx0) * (by1 - by0)
        if (area > largestArea) {
          largestArea = area
          sortY = (by0 + by1) / 2
        }
      }
    })
  }

  return { key, id, nombre, enabled, path, sortY }
}

function buildProvinceShapes(): {
  allShapes: ProvinceShape[]
  lockedShapes: ProvinceShape[]
  enabledShapes: ProvinceShape[]
  viewBox: string
  width: number
  height: number
} {
  const features = getAllProvinces()

  let minLon = Infinity
  let maxLon = -Infinity
  let minLat = Infinity
  let maxLat = -Infinity
  for (const feature of features) {
    for (const rings of getFeaturePolygons(feature)) {
      for (const [lon, lat] of rings[0] ?? []) {
        if (lon < minLon) minLon = lon
        if (lon > maxLon) maxLon = lon
        if (lat < minLat) minLat = lat
        if (lat > maxLat) maxLat = lat
      }
    }
  }

  const project = (lon: number, lat: number): [number, number] => [
    (lon - minLon) * MEAN_LAT_COS,
    (maxLat - lat) * TILT_Y,
  ]
  const fmt = (n: number) => Math.round(n * 1000) / 1000

  const shapes: ProvinceShape[] = []
  for (const feature of features) {
    const { id, nombre, enabled } = feature.properties
    const polygons = getFeaturePolygons(feature)

    if (id === 'tierra_del_fuego') {
      const continentalPolys = polygons.filter(
        (rings) => (rings[0]?.[0]?.[0] ?? -70) <= MALVINAS_LON_SPLIT
      )
      const malvinasPolys = polygons.filter(
        (rings) => (rings[0]?.[0]?.[0] ?? -70) > MALVINAS_LON_SPLIT
      )
      if (continentalPolys.length > 0) {
        shapes.push(
          buildShapeFromPolygons(
            'tierra_del_fuego',
            id,
            nombre,
            enabled,
            continentalPolys,
            project,
            fmt
          )
        )
      }
      if (malvinasPolys.length > 0) {
        shapes.push(
          buildShapeFromPolygons(
            'islas_malvinas',
            id,
            'Islas Malvinas',
            enabled,
            malvinasPolys,
            project,
            fmt
          )
        )
      }
      continue
    }

    shapes.push(
      buildShapeFromPolygons(id, id, nombre, enabled, polygons, project, fmt)
    )
  }

  shapes.sort((a, b) => a.sortY - b.sortY)

  const width = (maxLon - minLon) * MEAN_LAT_COS
  const height = (maxLat - minLat) * TILT_Y
  const viewBox = [
    -VIEWBOX_PADDING,
    -VIEWBOX_PADDING - LIFT_ACTIVE,
    width + VIEWBOX_PADDING * 2,
    height + VIEWBOX_PADDING * 2 + LIFT_ACTIVE + BASE_DEPTH,
  ]
    .map(fmt)
    .join(' ')

  return {
    allShapes: shapes,
    lockedShapes: shapes.filter((s) => !s.enabled),
    enabledShapes: shapes.filter((s) => s.enabled),
    viewBox,
    width,
    height,
  }
}

const {
  allShapes: ALL_SHAPES,
  lockedShapes: LOCKED_SHAPES,
  enabledShapes: ENABLED_SHAPES,
  viewBox: MAP_VIEWBOX,
  width: MAP_WIDTH,
  height: MAP_HEIGHT,
} = buildProvinceShapes()

/** Base 3D uniforme debajo de las 24 caras planas (solo asoma en el perímetro exterior). */
const MapBaseRelief = memo(function MapBaseRelief() {
  const step = BASE_DEPTH / BASE_EXTRUDE_LAYERS
  return (
    <>
      <g
        filter="url(#province-shadow-blur)"
        style={{
          opacity: 0.2,
          transform: `translate(0.05px, ${BASE_DEPTH + 0.05}px)`,
        }}
      >
        {ALL_SHAPES.map((shape) => (
          <path
            key={`base-shadow-${shape.key}`}
            d={shape.path}
            fill={THEME_COLORS.terracottaDarker}
          />
        ))}
      </g>
      <g>
        {Array.from({ length: BASE_EXTRUDE_LAYERS }, (_, i) => {
          const sideFill =
            i < BASE_EXTRUDE_LAYERS / 2
              ? THEME_COLORS.earthBrownDark
              : THEME_COLORS.earthBrown
          const offsetY = (BASE_EXTRUDE_LAYERS - i) * step
          return (
            <g key={i} style={{ transform: `translateY(${offsetY}px)` }}>
              {ALL_SHAPES.map((shape) => (
                <path
                  key={`base-ext-${i}-${shape.key}`}
                  d={shape.path}
                  fillRule="evenodd"
                  fill={sideFill}
                  stroke={sideFill}
                  strokeWidth={1.6}
                  strokeLinejoin="round"
                  vectorEffect="non-scaling-stroke"
                />
              ))}
            </g>
          )
        })}
      </g>
    </>
  )
})

const LockedProvinceTop = memo(function LockedProvinceTop({
  shape,
  isHovered,
}: {
  shape: ProvinceShape
  isHovered: boolean
}) {
  return (
    <path
      d={shape.path}
      fillRule="evenodd"
      className="province-3d-top"
      fill={isHovered ? THEME_COLORS.regionLockedHover : THEME_COLORS.regionLocked}
      stroke={isHovered ? THEME_COLORS.earthBrown : THEME_COLORS.regionLockedBorder}
      strokeWidth={isHovered ? 1.2 : 0.95}
      strokeLinejoin="round"
      vectorEffect="non-scaling-stroke"
    />
  )
})

const EnabledShadow = memo(function EnabledShadow({
  shape,
  lifted,
}: {
  shape: ProvinceShape
  lifted: boolean
}) {
  const lift = lifted ? LIFT_ACTIVE : 0
  return (
    <path
      d={shape.path}
      className="province-3d-shadow"
      fill={THEME_COLORS.terracottaDarker}
      filter="url(#province-shadow-blur)"
      style={{
        opacity: lifted ? 0.34 : 0,
        transform: `translate(${lift * 0.22}px, ${lift * 0.55}px)`,
      }}
    />
  )
})

const EnabledExtrudeSides = memo(function EnabledExtrudeSides({
  shape,
  isSelected,
  lifted,
}: {
  shape: ProvinceShape
  isSelected: boolean
  lifted: boolean
}) {
  const lift = lifted ? LIFT_ACTIVE : 0
  const thickness = lifted ? LIFT_THICKNESS : 0
  const sideColor = isSelected
    ? THEME_COLORS.terracottaDark
    : THEME_COLORS.earthBrown
  const sideDeepColor = isSelected
    ? THEME_COLORS.terracottaDarker
    : THEME_COLORS.earthBrownDark

  return (
    <g
      className="province-3d-lift"
      style={{
        opacity: lifted ? 1 : 0,
        transform: `translateY(${-lift}px)`,
      }}
    >
      {Array.from({ length: LIFT_EXTRUDE_LAYERS }, (_, i) => {
        const sideFill =
          i < LIFT_EXTRUDE_LAYERS / 2 ? sideDeepColor : sideColor
        const offsetY =
          ((LIFT_EXTRUDE_LAYERS - i) / LIFT_EXTRUDE_LAYERS) * thickness
        return (
          <path
            key={i}
            d={shape.path}
            fillRule="evenodd"
            fill={sideFill}
            stroke={sideFill}
            strokeWidth={1.4}
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
            style={{ transform: `translateY(${offsetY}px)` }}
          />
        )
      })}
    </g>
  )
})

const EnabledProvinceTop = memo(function EnabledProvinceTop({
  shape,
  isSelected,
  isHovered,
}: {
  shape: ProvinceShape
  isSelected: boolean
  isHovered: boolean
}) {
  const lifted = isSelected || isHovered
  const lift = lifted ? LIFT_ACTIVE : 0
  const fill = isSelected
    ? THEME_COLORS.terracotta
    : isHovered
      ? THEME_COLORS.regionTopHover
      : THEME_COLORS.regionTop
  const edge = isSelected
    ? THEME_COLORS.terracottaDarker
    : THEME_COLORS.earthBrownDark

  return (
    <g
      className="province-3d-lift"
      style={{ transform: `translateY(${-lift}px)` }}
    >
      <path
        d={shape.path}
        fillRule="evenodd"
        className="province-3d-top"
        fill={fill}
        stroke={edge}
        strokeWidth={isSelected ? 1.5 : isHovered ? 1.4 : 1.1}
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      <path
        d={shape.path}
        fillRule="evenodd"
        className="province-3d-shine"
        fill="url(#province-shine)"
        style={{ opacity: isHovered ? 0.95 : 0.45 }}
      />
    </g>
  )
})

export function ProvinceSelectorScreen({
  initialSelected,
  isSaving,
  errorMsg,
  isDemo,
  userLabel,
  onApply,
  onCancel,
  onLogout,
}: ProvinceSelectorScreenProps) {
  const [selected, setSelected] = useState<string[]>(() =>
    initialSelected.filter((id) =>
      (PAMPEAN_PROVINCE_IDS as readonly string[]).includes(id)
    )
  )
  const [hoveredKey, setHoveredKey] = useState<string | null>(null)
  const mapRef = useRef<HTMLDivElement | null>(null)
  const tooltipRef = useRef<HTMLDivElement | null>(null)
  const stageRectRef = useRef<DOMRect | null>(null)
  const pointerRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 })

  const selectedSet = useMemo(() => new Set(selected), [selected])

  const shapeByKey = useMemo(
    () => new Map(ALL_SHAPES.map((shape) => [shape.key, shape])),
    []
  )

  const toggleProvince = (id: string) => {
    if (isSaving) return
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    )
  }

  const moveTooltip = (clientX: number, clientY: number, refreshRect = false) => {
    const rect =
      (!refreshRect && stageRectRef.current) ||
      mapRef.current?.getBoundingClientRect() ||
      null
    if (!rect) return
    stageRectRef.current = rect
    const x = clientX - rect.left
    const y = clientY - rect.top
    pointerRef.current = { x, y }
    if (tooltipRef.current) {
      tooltipRef.current.style.transform = `translate3d(${x + 14}px, ${y + 14}px, 0)`
    }
  }

  const clearHover = () => {
    stageRectRef.current = null
    setHoveredKey(null)
  }

  useLayoutEffect(() => {
    if (!hoveredKey || !tooltipRef.current) return
    const { x, y } = pointerRef.current
    tooltipRef.current.style.transform = `translate3d(${x + 14}px, ${y + 14}px, 0)`
  }, [hoveredKey])

  const handleKeyDown = (
    event: KeyboardEvent<SVGPathElement>,
    shape: ProvinceShape
  ) => {
    if (!shape.enabled) return
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      toggleProvince(shape.id)
    }
  }

  const hoveredShape = hoveredKey ? shapeByKey.get(hoveredKey) : undefined
  const canApply = selected.length > 0 && !isSaving
  const totalEnabled = PAMPEAN_PROVINCE_IDS.length

  return (
    <div className="province-screen">
      <header className="top-navbar">
        <div className="top-navbar-left">
          <BrandBlock />
          <div className="header-session-bar">
            {isDemo ? (
              <span className="header-demo-pill">Modo demo</span>
            ) : (
              <span className="header-user-pill">
                <User size={14} aria-hidden="true" />
                <span>{userLabel || 'Mi cuenta'}</span>
              </span>
            )}
            <button
              type="button"
              className="header-session-btn"
              onClick={onLogout}
              disabled={isSaving}
            >
              <LogOut size={14} aria-hidden="true" />
              <span>{isDemo ? 'Salir del modo demo' : 'Cerrar sesión'}</span>
            </button>
          </div>
        </div>
      </header>

      <main className="province-main">
        <section className="province-map-area" aria-label="Mapa de Argentina">
          <div
            className="province-map-stage"
            ref={mapRef}
            onMouseLeave={clearHover}
          >
            <svg
              className="province-map-svg"
              viewBox={MAP_VIEWBOX}
              preserveAspectRatio="xMidYMid meet"
              role="group"
              aria-label="Provincias de Argentina"
              onMouseLeave={clearHover}
            >
              <defs>
                <filter
                  id="province-shadow-blur"
                  x="-25%"
                  y="-25%"
                  width="150%"
                  height="150%"
                >
                  <feGaussianBlur stdDeviation="0.13" />
                </filter>
                <linearGradient
                  id="province-shine"
                  gradientUnits="userSpaceOnUse"
                  x1="0"
                  y1="0"
                  x2={MAP_WIDTH}
                  y2={MAP_HEIGHT}
                >
                  <stop offset="0" stopColor={THEME_COLORS.bg} stopOpacity="0.55" />
                  <stop offset="0.5" stopColor={THEME_COLORS.bg} stopOpacity="0" />
                  <stop offset="1" stopColor={THEME_COLORS.terracottaDarker} stopOpacity="0.32" />
                </linearGradient>
              </defs>

              {/* Capa visual (no interactiva), ordenada por plano Z */}
              <g pointerEvents="none">
                {/* 1. Sombras y zócalo base debajo de todas las provincias */}
                <MapBaseRelief />

                {/* 2. Las 19 jurisdicciones bloqueadas al nivel base */}
                {LOCKED_SHAPES.map((shape) => (
                  <LockedProvinceTop
                    key={shape.key}
                    shape={shape}
                    isHovered={hoveredKey === shape.key}
                  />
                ))}

                {/* 3a. Sombras de las provincias habilitadas levantadas */}
                {ENABLED_SHAPES.map((shape) => (
                  <EnabledShadow
                    key={`sh-${shape.key}`}
                    shape={shape}
                    lifted={
                      selectedSet.has(shape.id) || hoveredKey === shape.key
                    }
                  />
                ))}

                {/* 3b. Paredes laterales de las provincias habilitadas levantadas */}
                {ENABLED_SHAPES.map((shape) => (
                  <EnabledExtrudeSides
                    key={`ex-${shape.key}`}
                    shape={shape}
                    isSelected={selectedSet.has(shape.id)}
                    lifted={
                      selectedSet.has(shape.id) || hoveredKey === shape.key
                    }
                  />
                ))}

                {/* 3c. Caras superiores de las 5 habilitadas (en reposo al ras; al subir tapan bordes internos entre sí) */}
                {ENABLED_SHAPES.map((shape) => (
                  <EnabledProvinceTop
                    key={shape.key}
                    shape={shape}
                    isSelected={selectedSet.has(shape.id)}
                    isHovered={hoveredKey === shape.key}
                  />
                ))}
              </g>

              {/* Capa de interacción: áreas fijas e invisibles (evita parpadeo al elevarse) */}
              <g>
                {ALL_SHAPES.map((shape) => {
                  const isSelected = selectedSet.has(shape.id)
                  const lockedDesc =
                    shape.key === 'islas_malvinas'
                      ? MALVINAS_TOOLTIP
                      : LOCKED_TOOLTIP
                  return (
                    <path
                      key={`hit-${shape.key}`}
                      d={shape.path}
                      fillRule="evenodd"
                      fill="transparent"
                      stroke="none"
                      className={`province-shape ${
                        shape.enabled ? 'province-shape-enabled' : 'province-shape-locked'
                      }`}
                      role={shape.enabled ? 'button' : undefined}
                      tabIndex={shape.enabled ? 0 : undefined}
                      aria-pressed={shape.enabled ? isSelected : undefined}
                      aria-disabled={shape.enabled ? undefined : true}
                      aria-label={
                        shape.enabled
                          ? `${shape.nombre}${isSelected ? ', seleccionada' : ''}`
                          : `${shape.nombre}. ${lockedDesc}`
                      }
                      onMouseEnter={(e: MouseEvent<SVGPathElement>) => {
                        moveTooltip(e.clientX, e.clientY, true)
                        setHoveredKey((prev) =>
                          prev === shape.key ? prev : shape.key
                        )
                      }}
                      onMouseMove={(e: MouseEvent<SVGPathElement>) => {
                        moveTooltip(e.clientX, e.clientY)
                      }}
                      onMouseLeave={() =>
                        setHoveredKey((prev) =>
                          prev === shape.key ? null : prev
                        )
                      }
                      onFocus={(e) => {
                        if (!shape.enabled) return
                        const stage = mapRef.current?.getBoundingClientRect()
                        const box = e.currentTarget.getBoundingClientRect()
                        if (!stage) return
                        stageRectRef.current = stage
                        pointerRef.current = {
                          x: box.left + box.width / 2 - stage.left,
                          y: box.top + box.height / 2 - stage.top,
                        }
                        setHoveredKey(shape.key)
                      }}
                      onBlur={clearHover}
                      onClick={(e: MouseEvent<SVGPathElement>) => {
                        if (shape.enabled) {
                          toggleProvince(shape.id)
                        } else {
                          moveTooltip(e.clientX, e.clientY, true)
                          setHoveredKey(shape.key)
                        }
                      }}
                      onKeyDown={(e) => handleKeyDown(e, shape)}
                    />
                  )
                })}
              </g>
            </svg>

            {hoveredShape && (
              <div
                ref={tooltipRef}
                className={`province-tooltip ${
                  hoveredShape.enabled ? '' : 'province-tooltip-locked'
                }`}
                role="tooltip"
              >
                <strong>{hoveredShape.nombre}</strong>
                <span>
                  {hoveredShape.key === 'islas_malvinas'
                    ? MALVINAS_TOOLTIP
                    : hoveredShape.enabled
                      ? selectedSet.has(hoveredShape.id)
                        ? 'Quitar de la selección'
                        : 'Agregar a la selección'
                      : LOCKED_TOOLTIP}
                </span>
              </div>
            )}
          </div>

          <ul className="province-legend" aria-label="Referencias del mapa">
            <li>
              <span
                className="province-legend-swatch"
                style={{
                  background: THEME_COLORS.regionTop,
                  borderColor: THEME_COLORS.earthBrownDark,
                }}
              />
              Disponible
            </li>
            <li>
              <span
                className="province-legend-swatch"
                style={{
                  background: THEME_COLORS.terracotta,
                  borderColor: THEME_COLORS.terracottaDarker,
                }}
              />
              Seleccionada
            </li>
            <li>
              <span
                className="province-legend-swatch"
                style={{
                  background: THEME_COLORS.regionLocked,
                  borderColor: THEME_COLORS.regionLockedBorder,
                }}
              />
              Próximamente
            </li>
          </ul>
        </section>

        <aside className="right-analysis-pane" aria-label="Resumen de selección">
          <div className="right-folder-body province-folder-body">
            <section className="panel-section province-selector-card">
              <div className="province-card-top">
                <div className="section-header-row">
                  <h2 className="section-title">Selección de región</h2>
                  <span className="coords-pill" aria-live="polite">
                    <code>
                      {selected.length}/{totalEnabled}
                    </code>
                    <span className="coords-ha">provincias</span>
                  </span>
                </div>

                <p className="province-panel-text">
                  Cobertura habilitada para la Región Pampeana. Seleccione en el
                  mapa las provincias donde se ubican sus campos.
                </p>
              </div>

              <div className="province-selection-body">
                <div className="control-group">
                  <div className="province-control-header">
                    <span className="control-label">
                      <MapPin size={14} aria-hidden="true" />
                      <span>Provincias incluidas</span>
                    </span>
                    <button
                      type="button"
                      className="reset-whatif-btn province-reset-btn"
                      disabled={selected.length === 0 || isSaving}
                      onClick={() => setSelected([])}
                    >
                      <RotateCcw size={13} aria-hidden="true" />
                      <span>Limpiar selección</span>
                    </button>
                  </div>

                  <div
                    className={`what-if-box province-selection-box ${
                      selected.length === 0 ? 'is-empty' : ''
                    }`}
                  >
                    {selected.length === 0 ? (
                      <p className="empty-rotation-text">
                        Aún no hay provincias seleccionadas. Seleccione al menos una
                        jurisdicción en el mapa.
                      </p>
                    ) : (
                      <ul className="province-chip-list">
                        {selected.map((id) => (
                          <li key={id}>
                            <button
                              type="button"
                              className="province-chip"
                              onClick={() => toggleProvince(id)}
                              disabled={isSaving}
                              aria-label={`Quitar ${getProvinceById(id)?.properties.nombre ?? id}`}
                            >
                              <Check size={13} aria-hidden="true" />
                              <span>{getProvinceById(id)?.properties.nombre ?? id}</span>
                              <X size={13} aria-hidden="true" />
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>

                {errorMsg && (
                  <div className="province-panel-error" role="alert">
                    {errorMsg}
                  </div>
                )}
              </div>

              <div className="province-card-actions">
                <div className="plan-action-footer">
                  <span className="plan-status-hint">
                    {selected.length === 0
                      ? 'Seleccione al menos una provincia.'
                      : 'El mapa climático filtrará los campos de esta área.'}
                  </span>
                  <button
                    type="button"
                    className="plan-submit-btn"
                    disabled={!canApply}
                    onClick={() => onApply(selected)}
                  >
                    {isSaving ? (
                      <>
                        <Loader2 size={16} className="province-spin" aria-hidden="true" />
                        <span>Guardando...</span>
                      </>
                    ) : (
                      <span>Aplicar y continuar</span>
                    )}
                  </button>
                </div>

                {onCancel && (
                  <div className="province-back-row">
                    <button
                      type="button"
                      className="detail-link-btn province-back-link"
                      disabled={isSaving}
                      onClick={onCancel}
                    >
                      <ArrowLeft size={14} aria-hidden="true" />
                      <span>Volver al mapa climático</span>
                    </button>
                  </div>
                )}
              </div>
            </section>

            <section
              className="panel-section empty-rotation-card what-if-standalone-section province-coverage-card"
              aria-label="Alcance geográfico"
            >
              <span className="section-eyebrow">Cobertura territorial actual</span>
              <p className="empty-rotation-text">
                Habilitadas: Buenos Aires, Córdoba, Entre Ríos, La Pampa y Santa
                Fe. Puede elegir más de una si un campo cruza un límite
                provincial; el resto permanece en expansión.
              </p>
            </section>
          </div>
        </aside>
      </main>
    </div>
  )
}
