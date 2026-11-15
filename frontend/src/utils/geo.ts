import type { Coordenadas } from '../types/api'
import argentinaProvincesRaw from '../data/argentinaProvinces.json'

// ============================================================================
// PROVINCIAS DE ARGENTINA (GeoJSON simplificado, 24 jurisdicciones)
// GeoJSON usa [lon, lat]; Leaflet usa [lat, lon]. Cada función documenta su orden.
// ============================================================================

/** Posición GeoJSON: [lon, lat]. */
type GeoPosition = [number, number]
/** Anillo lineal GeoJSON (cerrado). */
type GeoRing = GeoPosition[]

export interface ProvinceProperties {
  id: string
  indec_id: string
  nombre: string
  enabled: boolean
}

export type ProvinceGeometry =
  | { type: 'Polygon'; coordinates: GeoRing[] }
  | { type: 'MultiPolygon'; coordinates: GeoRing[][] }

export interface ProvinceFeature {
  type: 'Feature'
  geometry: ProvinceGeometry
  properties: ProvinceProperties
}

export interface ProvinceFeatureCollection {
  type: 'FeatureCollection'
  features: ProvinceFeature[]
}

/** Provincias de la Región Pampeana habilitadas (debe coincidir con el backend). */
export const PAMPEAN_PROVINCE_IDS = [
  'buenos_aires',
  'cordoba',
  'santa_fe',
  'entre_rios',
  'la_pampa',
] as const

export type PampeanProvinceId = (typeof PAMPEAN_PROVINCE_IDS)[number]

const PROVINCE_COLLECTION =
  argentinaProvincesRaw as unknown as ProvinceFeatureCollection

const PROVINCE_INDEX: ReadonlyMap<string, ProvinceFeature> = new Map(
  PROVINCE_COLLECTION.features.map((feature) => [feature.properties.id, feature])
)

export function getAllProvinces(): ProvinceFeature[] {
  return PROVINCE_COLLECTION.features
}

export function getProvinceById(id: string): ProvinceFeature | undefined {
  return PROVINCE_INDEX.get(id)
}

/** Devuelve los polígonos GeoJSON de una feature como lista de [anillo exterior, ...agujeros]. */
export function getFeaturePolygons(feature: ProvinceFeature): GeoRing[][] {
  return feature.geometry.type === 'Polygon'
    ? [feature.geometry.coordinates]
    : feature.geometry.coordinates
}

/** Etiqueta compacta de provincias, p. ej. "Córdoba · Santa Fe". */
export function getProvincesLabel(provinceIds: string[]): string {
  return provinceIds
    .map((id) => getProvinceById(id)?.properties.nombre ?? id)
    .join(' · ')
}

function resolveProvinces(provinceIds: string[]): ProvinceFeature[] {
  const found: ProvinceFeature[] = []
  for (const id of provinceIds) {
    const feature = PROVINCE_INDEX.get(id)
    if (feature) found.push(feature)
  }
  return found
}

/** Ray-casting sobre un anillo. Recibe lon/lat con el mismo orden que el GeoJSON. */
function isPointInRing(lon: number, lat: number, ring: GeoRing): boolean {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    const crosses =
      yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi
    if (crosses) inside = !inside
  }
  return inside
}

/** Un polígono contiene el punto si está en el anillo exterior y fuera de todos los agujeros. */
function isPointInPolygon(lon: number, lat: number, rings: GeoRing[]): boolean {
  if (rings.length === 0 || !isPointInRing(lon, lat, rings[0])) return false
  for (let h = 1; h < rings.length; h++) {
    if (isPointInRing(lon, lat, rings[h])) return false
  }
  return true
}

/**
 * Indica si el punto (lat, lon en convención Leaflet) cae dentro de alguna de las provincias dadas.
 * Soporta Polygon y MultiPolygon con anillos exteriores e interiores.
 */
export function isPointInProvinces(
  lat: number,
  lon: number,
  provinceIds: string[]
): boolean {
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return false
  for (const feature of resolveProvinces(provinceIds)) {
    for (const rings of getFeaturePolygons(feature)) {
      if (isPointInPolygon(lon, lat, rings)) return true
    }
  }
  return false
}

/**
 * Bounds combinados de las provincias en formato Leaflet: [[southLat, westLon], [northLat, eastLon]].
 * Si no hay provincias válidas, usa la Región Pampeana completa.
 */
export function getProvincesBounds(
  provinceIds: string[]
): [[number, number], [number, number]] {
  let features = resolveProvinces(provinceIds)
  if (features.length === 0) {
    features = resolveProvinces([...PAMPEAN_PROVINCE_IDS])
  }

  let south = Infinity
  let west = Infinity
  let north = -Infinity
  let east = -Infinity
  for (const feature of features) {
    for (const rings of getFeaturePolygons(feature)) {
      for (const [lon, lat] of rings[0] ?? []) {
        if (lat < south) south = lat
        if (lat > north) north = lat
        if (lon < west) west = lon
        if (lon > east) east = lon
      }
    }
  }
  return [
    [south, west],
    [north, east],
  ]
}

/**
 * Polígonos de las provincias en formato Leaflet [lat, lon] (multi-polígono con agujeros),
 * listos para `<Polygon positions={...} />` sin invertir ejes.
 */
export function getProvinceLatLngPolygons(
  provinceIds: string[]
): [number, number][][][] {
  const result: [number, number][][][] = []
  for (const feature of resolveProvinces(provinceIds)) {
    for (const rings of getFeaturePolygons(feature)) {
      result.push(
        rings.map((ring) =>
          ring.map(([lon, lat]): [number, number] => [lat, lon])
        )
      )
    }
  }
  return result
}
/**
 * Calcula el centroide geométrico de un polígono de coordenadas [lat, lon][].
 */
export function calculateCentroid(points: [number, number][]): Coordenadas {
  if (points.length === 0) {
    return { lat: -33.95, lon: -60.57 }
  }
  if (points.length === 1) {
    return { lat: points[0][0], lon: points[0][1] }
  }

  let sumLat = 0
  let sumLon = 0
  for (const [lat, lon] of points) {
    sumLat += lat
    sumLon += lon
  }

  return {
    lat: Math.round((sumLat / points.length) * 10000) / 10000,
    lon: Math.round((sumLon / points.length) * 10000) / 10000,
  }
}

/**
 * Calcula la superficie aproximada en hectáreas (ha) de un polígono [lat, lon][]
 * usando proyección equirectangular local sobre el radio terrestre medio.
 */
export function calculatePolygonAreaHa(points: [number, number][]): number {
  if (points.length < 3) return 0

  const EARTH_RADIUS_M = 6371000
  const centroid = calculateCentroid(points)
  const lat0Rad = (centroid.lat * Math.PI) / 180
  const cosLat0 = Math.cos(lat0Rad)

  // Convertir cada vértice a coordenadas planas locales (metros)
  const metersPoints = points.map(([lat, lon]) => {
    const x = ((lon - centroid.lon) * Math.PI) / 180 * EARTH_RADIUS_M * cosLat0
    const y = ((lat - centroid.lat) * Math.PI) / 180 * EARTH_RADIUS_M
    return { x, y }
  })

  // Fórmula de Gauss (Shoelace)
  let areaM2 = 0
  for (let i = 0; i < metersPoints.length; i++) {
    const j = (i + 1) % metersPoints.length
    areaM2 += metersPoints[i].x * metersPoints[j].y
    areaM2 -= metersPoints[j].x * metersPoints[i].y
  }

  const areaHa = Math.abs(areaM2) / 2 / 10000
  return Math.round(areaHa * 10) / 10
}

/**
 * Construye la URL WMTS de NASA GIBS (EPSG:3857) según la Sección 3.2 de CONTEXT.md.
 */
export function buildNasaGibsTileUrl(
  layerIdentifier: string,
  dateStr: string,
  tileMatrixSet: string,
  format: 'png' | 'jpg'
): string {
  return `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${layerIdentifier}/default/${dateStr}/${tileMatrixSet}/{z}/{y}/{x}.${format}`
}
