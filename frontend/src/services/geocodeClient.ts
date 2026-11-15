import type { Coordenadas } from '../types/api'
import { getProvincesBounds, isPointInProvinces } from '../utils/geo'

export interface MapSearchResult {
  id: string
  label: string
  secondaryLabel: string
  coords: Coordenadas
  zoom: number
  bounds?: [[number, number], [number, number]]
  /** Polígonos de límites de la localidad/departamento en orden Leaflet [lat, lon]. */
  polygons?: [number, number][][][]
  inSelectedProvinces: boolean
  isCoordinateMatch?: boolean
}

interface NominatimAddress {
  city?: string
  town?: string
  village?: string
  hamlet?: string
  municipality?: string
  county?: string
  state_district?: string
  state?: string
  road?: string
  suburb?: string
  neighbourhood?: string
}

interface NominatimGeoJson {
  type?: string
  coordinates?: unknown
}

interface NominatimItem {
  place_id: number | string
  lat: string
  lon: string
  boundingbox?: [string, string, string, string]
  geojson?: NominatimGeoJson
  name?: string
  display_name?: string
  addresstype?: string
  type?: string
  address?: NominatimAddress
}

const COORDINATES_REGEX =
  /^\s*(-?\d{1,2}(?:[.,]\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:[.,]\d+)?)\s*$/

/**
 * Intenta interpretar una búsqueda como par latitud/longitud (p. ej. "-33.95, -60.57").
 */
export function parseCoordinateQuery(
  rawQuery: string,
  provinceIds: string[]
): MapSearchResult | null {
  const match = COORDINATES_REGEX.exec(rawQuery)
  if (!match) return null

  const lat = Number(match[1].replace(',', '.'))
  const lon = Number(match[2].replace(',', '.'))
  if (
    !Number.isFinite(lat) ||
    !Number.isFinite(lon) ||
    lat < -90 ||
    lat > 90 ||
    lon < -180 ||
    lon > 180
  ) {
    return null
  }

  return {
    id: `coords-${lat.toFixed(5)}-${lon.toFixed(5)}`,
    label: `${lat.toFixed(4)}, ${lon.toFixed(4)}`,
    secondaryLabel: isPointInProvinces(lat, lon, provinceIds)
      ? 'Coordenadas geográficas'
      : 'Coordenadas fuera de provincias activas',
    coords: { lat, lon },
    zoom: 14,
    inSelectedProvinces: isPointInProvinces(lat, lon, provinceIds),
    isCoordinateMatch: true,
  }
}

function getZoomForResult(item: NominatimItem): number {
  const kind = (item.addresstype ?? item.type ?? '').toLowerCase()
  if (kind === 'state' || kind === 'province' || kind === 'region') return 8
  if (kind === 'county' || kind === 'state_district') return 10
  if (kind === 'city' || kind === 'municipality') return 12
  if (kind === 'town' || kind === 'village' || kind === 'suburb') return 13
  if (kind === 'hamlet' || kind === 'neighbourhood' || kind === 'road') {
    return 14
  }
  return 12
}

function formatLocationLabels(item: NominatimItem): {
  label: string
  secondaryLabel: string
} {
  const addr = item.address
  const fallbackParts = (item.display_name ?? '')
    .split(',')
    .map((part) => part.trim())
    .filter((part) => part.length > 0 && part.toLowerCase() !== 'argentina')

  const primary =
    item.name?.trim() ||
    addr?.city ||
    addr?.town ||
    addr?.village ||
    addr?.hamlet ||
    addr?.municipality ||
    addr?.road ||
    fallbackParts[0] ||
    'Ubicación'

  const contextParts: string[] = []
  const area = addr?.municipality || addr?.county || addr?.state_district
  if (area && area !== primary) {
    contextParts.push(area)
  }
  if (addr?.state && addr.state !== primary) {
    contextParts.push(addr.state)
  }

  if (contextParts.length === 0 && fallbackParts.length > 1) {
    contextParts.push(...fallbackParts.slice(1, 3))
  }

  return {
    label: primary,
    secondaryLabel: contextParts.join(' · ') || 'Argentina',
  }
}

function extractLeafletPolygons(
  geojson?: NominatimGeoJson
): [number, number][][][] | undefined {
  if (!geojson || !Array.isArray(geojson.coordinates)) return undefined

  const flipRing = (ring: unknown): [number, number][] | null => {
    if (!Array.isArray(ring) || ring.length < 3) return null
    const pts: [number, number][] = []
    for (const coord of ring) {
      if (!Array.isArray(coord) || coord.length < 2) continue
      const lon = Number(coord[0])
      const lat = Number(coord[1])
      if (Number.isFinite(lat) && Number.isFinite(lon)) {
        pts.push([lat, lon])
      }
    }
    return pts.length >= 3 ? pts : null
  }

  const parsePolygonRings = (rings: unknown): [number, number][][] | null => {
    if (!Array.isArray(rings)) return null
    const parsed: [number, number][][] = []
    for (const ring of rings) {
      const flipped = flipRing(ring)
      if (flipped) parsed.push(flipped)
    }
    return parsed.length > 0 ? parsed : null
  }

  if (geojson.type === 'Polygon') {
    const poly = parsePolygonRings(geojson.coordinates)
    return poly ? [poly] : undefined
  }

  if (geojson.type === 'MultiPolygon') {
    const polys: [number, number][][][] = []
    for (const polyCoords of geojson.coordinates) {
      const poly = parsePolygonRings(polyCoords)
      if (poly) polys.push(poly)
    }
    return polys.length > 0 ? polys : undefined
  }

  return undefined
}

function parseNominatimBounds(
  rawBox?: [string, string, string, string]
): [[number, number], [number, number]] | undefined {
  if (!Array.isArray(rawBox) || rawBox.length !== 4) return undefined
  const south = Number(rawBox[0])
  const north = Number(rawBox[1])
  const west = Number(rawBox[2])
  const east = Number(rawBox[3])
  if (
    !Number.isFinite(south) ||
    !Number.isFinite(north) ||
    !Number.isFinite(west) ||
    !Number.isFinite(east)
  ) {
    return undefined
  }
  if (Math.abs(north - south) < 0.002 && Math.abs(east - west) < 0.002) {
    return undefined
  }
  return [
    [south, west],
    [north, east],
  ]
}

async function fetchNominatimResults(
  query: string,
  provinceIds: string[],
  restrictArgentina: boolean,
  signal?: AbortSignal
): Promise<NominatimItem[]> {
  const [[south, west], [north, east]] = getProvincesBounds(provinceIds)
  const params = new URLSearchParams({
    format: 'jsonv2',
    addressdetails: '1',
    polygon_geojson: '1',
    polygon_threshold: '0.005',
    limit: '6',
    'accept-language': 'es',
    viewbox: `${west},${north},${east},${south}`,
    bounded: '0',
    q: query,
  })
  if (restrictArgentina) {
    params.set('countrycodes', 'ar')
  }

  const response = await fetch(
    `https://nominatim.openstreetmap.org/search?${params.toString()}`,
    {
      signal,
      headers: {
        Accept: 'application/json',
      },
    }
  )

  if (!response.ok) {
    throw new Error('No fue posible buscar la ubicación. Intente nuevamente.')
  }

  const data = (await response.json()) as NominatimItem[]
  return Array.isArray(data) ? data : []
}

/**
 * Busca localidades, departamentos, direcciones o coordenadas priorizando Argentina y la Región Pampeana.
 */
export async function searchMapLocations(
  rawQuery: string,
  provinceIds: string[],
  signal?: AbortSignal
): Promise<MapSearchResult[]> {
  const query = rawQuery.trim()
  if (!query) return []

  const coordResult = parseCoordinateQuery(query, provinceIds)
  if (coordResult) {
    return [coordResult]
  }

  let data = await fetchNominatimResults(query, provinceIds, true, signal)
  if (data.length === 0) {
    data = await fetchNominatimResults(query, provinceIds, false, signal)
  }

  const results: MapSearchResult[] = []
  for (const item of data) {
    const lat = Number(item.lat)
    const lon = Number(item.lon)
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue

    const { label, secondaryLabel } = formatLocationLabels(item)
    results.push({
      id: String(item.place_id),
      label,
      secondaryLabel,
      coords: { lat, lon },
      zoom: getZoomForResult(item),
      bounds: parseNominatimBounds(item.boundingbox),
      polygons: extractLeafletPolygons(item.geojson),
      inSelectedProvinces: isPointInProvinces(lat, lon, provinceIds),
    })
  }

  // Prioriza ubicaciones que caen dentro de las provincias seleccionadas manteniendo orden relativo
  results.sort((a, b) => Number(b.inSelectedProvinces) - Number(a.inSelectedProvinces))
  return results.slice(0, 5)
}
