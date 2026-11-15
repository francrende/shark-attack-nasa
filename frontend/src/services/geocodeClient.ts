import type { Coordenadas } from '../types/api'
import {
  getAllProvinces,
  getProvinceLatLngPolygons,
  getProvincesBounds,
  isPointInProvinces,
  type ProvinceFeature,
} from '../utils/geo'

export interface MapSearchResult {
  id: string
  label: string
  secondaryLabel: string
  coords: Coordenadas
  zoom: number
  bounds?: [[number, number], [number, number]]
  /** Polígonos de límites de la localidad/provincia en orden Leaflet [lat, lon]. */
  polygons?: [number, number][][][]
  inSelectedProvinces: boolean
  isCoordinateMatch?: boolean
}

const ARGENTINA_BOUNDS = {
  minLat: -55.6,
  maxLat: -21.5,
  minLon: -73.8,
  maxLon: -53.4,
} as const

const PHOTON_ARGENTINA_BBOX = `${ARGENTINA_BOUNDS.minLon},${ARGENTINA_BOUNDS.minLat},${ARGENTINA_BOUNDS.maxLon},${ARGENTINA_BOUNDS.maxLat}`
const GEOREF_BASE_URL = 'https://apis.datos.gob.ar/georef/api'
const PHOTON_URL = 'https://photon.komoot.io/api/'

const COORDINATES_REGEX =
  /^\s*(-?\d{1,2}(?:[.,]\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:[.,]\d+)?)\s*$/

const SEARCH_CACHE_MAX = 60
const searchCache = new Map<string, MapSearchResult[]>()

type CandidateKind =
  | 'province'
  | 'city'
  | 'localidad'
  | 'department'
  | 'neighbourhood'
  | 'address'
  | 'poi'

interface SearchCandidate {
  result: MapSearchResult
  normLabel: string
  provinceNorm: string
  kind: CandidateKind
  sourceRank: number
  fromGeoref: boolean
  fromPhoton: boolean
}

interface ParsedQuery {
  raw: string
  photonQuery: string
  georefQuery: string
  departmentQuery: string
  provinceHint: ProvinceFeature | null
  looksLikeAddress: boolean
}

interface GeorefPoint {
  lat?: number
  lon?: number
}

interface GeorefItem {
  id?: string | number
  nombre?: string
  categoria?: string
  centroide?: GeorefPoint
  provincia?: { id?: string; nombre?: string }
  departamento?: { id?: string; nombre?: string }
  municipio?: { id?: string; nombre?: string }
}

interface GeorefResponse {
  localidades?: GeorefItem[]
  localidades_censales?: GeorefItem[]
  departamentos?: GeorefItem[]
}

interface PhotonProperties {
  osm_id?: number | string
  osm_type?: string
  osm_key?: string
  osm_value?: string
  type?: string
  name?: string
  countrycode?: string
  state?: string
  county?: string
  city?: string
  town?: string
  village?: string
  locality?: string
  district?: string
  street?: string
  housenumber?: string
  extent?: [number, number, number, number]
}

interface PhotonFeature {
  geometry?: {
    type?: string
    coordinates?: [number, number]
  }
  properties?: PhotonProperties
}

interface PhotonResponse {
  features?: PhotonFeature[]
}

const PROVINCE_ALIAS_TO_ID: Readonly<Record<string, string>> = {
  caba: 'caba',
  'cap fed': 'caba',
  'capital federal': 'caba',
  'ciudad de buenos aires': 'caba',
  'ciudad autonoma de buenos aires': 'caba',
  'bs as': 'buenos_aires',
  bsas: 'buenos_aires',
  pba: 'buenos_aires',
  'pcia de buenos aires': 'buenos_aires',
  'provincia de buenos aires': 'buenos_aires',
  'sta fe': 'santa_fe',
  'e rios': 'entre_rios',
  'sgo del estero': 'santiago_del_estero',
  'tierra del fuego': 'tierra_del_fuego',
}

const ABBREVIATION_EXPANSIONS: ReadonlyArray<[RegExp, string]> = [
  [/\bgral\.?\b/gi, 'General'],
  [/\bcnel\.?\b/gi, 'Coronel'],
  [/\bsta\.?\b/gi, 'Santa'],
  [/\bsto\.?\b/gi, 'Santo'],
  [/\bpte\.?\b/gi, 'Presidente'],
  [/\bing\.?\b/gi, 'Ingeniero'],
  [/\bdr\.?\b/gi, 'Doctor'],
  [/\bsgto\.?\b/gi, 'Sargento'],
  [/\bcmte\.?\b/gi, 'Comandante'],
  [/\btte\.?\b/gi, 'Teniente'],
  [/\balmte\.?\b/gi, 'Almirante'],
  [/\bgdor\.?\b/gi, 'Gobernador'],
  [/\bbme\.?\b/gi, 'Bartolomé'],
  [/\bvte\.?\b/gi, 'Vicente'],
]

const NUMERIC_NAME_REPLACEMENTS: ReadonlyArray<[RegExp, string]> = [
  [/\bnueve de julio\b/gi, '9 de Julio'],
  [/\bveinticinco de mayo\b/gi, '25 de Mayo'],
  [/\bdoce de octubre\b/gi, '12 de Octubre'],
  [/\bprimero de mayo\b/gi, '1 de Mayo'],
]

function cleanDisplayText(value: string | undefined | null): string {
  if (!value) return ''
  return value.replace(/\u00ad/g, '').replace(/\s+/g, ' ').trim()
}

function normalizeSearchText(value: string): string {
  return cleanDisplayText(value)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function isWithinArgentinaBounds(lat: number, lon: number): boolean {
  return (
    Number.isFinite(lat) &&
    Number.isFinite(lon) &&
    lat >= ARGENTINA_BOUNDS.minLat &&
    lat <= ARGENTINA_BOUNDS.maxLat &&
    lon >= ARGENTINA_BOUNDS.minLon &&
    lon <= ARGENTINA_BOUNDS.maxLon
  )
}

function parseRawCoordinatePair(
  rawQuery: string
): { lat: number; lon: number } | null {
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
  return { lat, lon }
}

/**
 * Indica si el texto corresponde a un par de coordenadas válido pero ubicado fuera de Argentina.
 */
export function isCoordinateOutsideArgentina(rawQuery: string): boolean {
  const pair = parseRawCoordinatePair(rawQuery)
  return pair !== null && !isWithinArgentinaBounds(pair.lat, pair.lon)
}

/**
 * Intenta interpretar una búsqueda como par latitud/longitud dentro de Argentina (p. ej. "-33.95, -60.57").
 */
export function parseCoordinateQuery(
  rawQuery: string,
  provinceIds: string[]
): MapSearchResult | null {
  const pair = parseRawCoordinatePair(rawQuery)
  if (!pair || !isWithinArgentinaBounds(pair.lat, pair.lon)) return null

  const { lat, lon } = pair
  return {
    id: `coords-${lat.toFixed(5)}-${lon.toFixed(5)}`,
    label: `${lat.toFixed(4)}, ${lon.toFixed(4)}`,
    secondaryLabel: isPointInProvinces(lat, lon, provinceIds)
      ? 'Coordenadas geográficas'
      : 'Coordenadas en Argentina (fuera de provincias activas)',
    coords: { lat, lon },
    zoom: 14,
    inSelectedProvinces: isPointInProvinces(lat, lon, provinceIds),
    isCoordinateMatch: true,
  }
}

function findProvinceByText(text: string): ProvinceFeature | null {
  const norm = normalizeSearchText(text)
  if (!norm) return null

  const provinces = getAllProvinces()
  const aliasId = PROVINCE_ALIAS_TO_ID[norm]
  if (aliasId) {
    return provinces.find((p) => p.properties.id === aliasId) ?? null
  }

  for (const prov of provinces) {
    if (normalizeSearchText(prov.properties.nombre) === norm) {
      return prov
    }
  }
  return null
}

function expandForGeoref(text: string): string {
  let result = cleanDisplayText(text)
  for (const [pattern, replacement] of ABBREVIATION_EXPANSIONS) {
    result = result.replace(pattern, replacement)
  }
  for (const [pattern, replacement] of NUMERIC_NAME_REPLACEMENTS) {
    result = result.replace(pattern, replacement)
  }
  return result.replace(/\s+/g, ' ').trim()
}

function parseSearchQuery(rawQuery: string): ParsedQuery {
  const cleaned = cleanDisplayText(rawQuery)
  const parts = cleaned
    .split(',')
    .map((p) => p.trim())
    .filter((p) => p.length > 0)

  // Quita sufijo país ("..., Argentina" o "..., AR") si el usuario pegó una dirección completa
  if (parts.length > 1) {
    const lastNorm = normalizeSearchText(parts[parts.length - 1])
    if (lastNorm === 'argentina' || lastNorm === 'ar' || lastNorm === 'rep argentina') {
      parts.pop()
    }
  }

  let provinceHint: ProvinceFeature | null = null
  if (parts.length > 1) {
    const maybeProv = findProvinceByText(parts[parts.length - 1])
    if (maybeProv) {
      provinceHint = maybeProv
      parts.pop()
    }
  }

  const baseTerm = parts.join(', ').trim() || cleaned
  const georefQuery = expandForGeoref(baseTerm)
  const departmentQuery = georefQuery
    .replace(/^(partido\s+de|departamento\s+de|departamento|depto\.?|municipio\s+de)\s+/i, '')
    .trim()

  const photonQuery = provinceHint
    ? `${georefQuery}, ${provinceHint.properties.nombre}`
    : baseTerm

  const looksLikeAddress =
    (/\d/.test(baseTerm) && !/^(9|25|12|1|2|3|20)\s+de\b/i.test(baseTerm)) ||
    /^(av|avda|avenida|calle|ruta|rp|rn|bv|boulevard|bulevar|diag|diagonal)\b/i.test(
      baseTerm
    )

  return {
    raw: cleaned,
    photonQuery,
    georefQuery,
    departmentQuery: departmentQuery || georefQuery,
    provinceHint,
    looksLikeAddress,
  }
}

function searchLocalProvinces(
  parsed: ParsedQuery,
  provinceIds: string[]
): SearchCandidate[] {
  if (parsed.provinceHint) return []
  const normQuery = normalizeSearchText(parsed.georefQuery)
  if (normQuery.length < 3) return []

  const results: SearchCandidate[] = []
  const aliasId = PROVINCE_ALIAS_TO_ID[normQuery]

  for (const prov of getAllProvinces()) {
    const provName = prov.properties.nombre
    const normProv = normalizeSearchText(provName)
    const matches =
      prov.properties.id === aliasId ||
      normProv === normQuery ||
      normProv.startsWith(normQuery) ||
      normProv.includes(normQuery)
    if (!matches) continue

    const bounds = getProvincesBounds([prov.properties.id])
    const centerLat = (bounds[0][0] + bounds[1][0]) / 2
    const centerLon = (bounds[0][1] + bounds[1][1]) / 2

    results.push({
      result: {
        id: `prov-${prov.properties.id}`,
        label: provName,
        secondaryLabel:
          prov.properties.id === 'caba'
            ? 'Ciudad Autónoma · Argentina'
            : 'Provincia · Argentina',
        coords: { lat: centerLat, lon: centerLon },
        zoom: prov.properties.id === 'caba' ? 11 : 7,
        bounds,
        polygons: getProvinceLatLngPolygons([prov.properties.id]),
        inSelectedProvinces: provinceIds.includes(prov.properties.id),
      },
      normLabel: normProv,
      provinceNorm: normProv,
      kind: 'province',
      sourceRank: 4,
      fromGeoref: true,
      fromPhoton: false,
    })
  }

  return results
}

async function fetchGeorefEndpoint(
  endpoint: 'localidades' | 'localidades-censales' | 'departamentos',
  nombre: string,
  provinciaIndecId: string | undefined,
  max: number,
  signal?: AbortSignal
): Promise<GeorefItem[]> {
  const params = new URLSearchParams({
    nombre,
    max: String(max),
    campos:
      endpoint === 'departamentos'
        ? 'id,nombre,provincia.nombre,categoria,centroide'
        : 'id,nombre,provincia.nombre,departamento.nombre,municipio.nombre,categoria,centroide',
  })
  if (provinciaIndecId) {
    params.set('provincia', provinciaIndecId)
  }

  const response = await fetch(
    `${GEOREF_BASE_URL}/${endpoint}?${params.toString()}`,
    {
      signal,
      headers: { Accept: 'application/json' },
    }
  )

  if (!response.ok) {
    throw new Error(`Georef HTTP ${response.status}`)
  }

  const data = (await response.json()) as GeorefResponse
  if (endpoint === 'localidades') return data.localidades ?? []
  if (endpoint === 'localidades-censales') return data.localidades_censales ?? []
  return data.departamentos ?? []
}

async function fetchGeorefCandidates(
  parsed: ParsedQuery,
  provinceIds: string[],
  signal?: AbortSignal
): Promise<SearchCandidate[]> {
  const provId = parsed.provinceHint?.properties.indec_id

  const [locRes, lcRes, deptoRes] = await Promise.allSettled([
    fetchGeorefEndpoint('localidades', parsed.georefQuery, provId, 8, signal),
    fetchGeorefEndpoint(
      'localidades-censales',
      parsed.georefQuery,
      provId,
      6,
      signal
    ),
    fetchGeorefEndpoint(
      'departamentos',
      parsed.departmentQuery,
      provId,
      4,
      signal
    ),
  ])

  const allFailed =
    locRes.status === 'rejected' &&
    lcRes.status === 'rejected' &&
    deptoRes.status === 'rejected'

  if (allFailed) {
    throw locRes.reason
  }

  const candidates: SearchCandidate[] = []

  const pushItems = (
    items: GeorefItem[],
    kind: CandidateKind,
    sourceRank: number,
    zoom: number,
    idPrefix: string
  ) => {
    for (const item of items) {
      const lat = Number(item.centroide?.lat)
      const lon = Number(item.centroide?.lon)
      if (!isWithinArgentinaBounds(lat, lon)) continue

      const name = cleanDisplayText(item.nombre)
      if (!name) continue

      const provName = cleanDisplayText(item.provincia?.nombre) || 'Argentina'
      const deptoName = cleanDisplayText(item.departamento?.nombre)
      const muniName = cleanDisplayText(item.municipio?.nombre)

      const contextParts: string[] = []
      if (kind === 'department') {
        contextParts.push(cleanDisplayText(item.categoria) || 'Departamento')
      } else {
        const area = deptoName || muniName
        if (area && normalizeSearchText(area) !== normalizeSearchText(name)) {
          contextParts.push(area)
        }
      }
      if (provName && normalizeSearchText(provName) !== normalizeSearchText(name)) {
        contextParts.push(provName)
      }

      candidates.push({
        result: {
          id: `${idPrefix}-${String(item.id ?? `${lat}-${lon}`)}`,
          label: name,
          secondaryLabel: contextParts.join(' · ') || 'Argentina',
          coords: { lat, lon },
          zoom,
          inSelectedProvinces: isPointInProvinces(lat, lon, provinceIds),
        },
        normLabel: normalizeSearchText(name),
        provinceNorm: normalizeSearchText(provName),
        kind,
        sourceRank,
        fromGeoref: true,
        fromPhoton: false,
      })
    }
  }

  if (locRes.status === 'fulfilled') {
    pushItems(locRes.value, 'localidad', 3, 13, 'georef-loc')
  }
  if (lcRes.status === 'fulfilled') {
    pushItems(lcRes.value, 'localidad', 1, 13, 'georef-lc')
  }
  if (deptoRes.status === 'fulfilled') {
    pushItems(deptoRes.value, 'department', 2, 10, 'georef-dep')
  }

  return candidates
}

function parsePhotonExtent(
  extent?: [number, number, number, number]
): [[number, number], [number, number]] | undefined {
  if (!Array.isArray(extent) || extent.length !== 4) return undefined
  // Photon extent: [west, north, east, south]
  const west = Number(extent[0])
  const north = Number(extent[1])
  const east = Number(extent[2])
  const south = Number(extent[3])
  if (
    !Number.isFinite(west) ||
    !Number.isFinite(north) ||
    !Number.isFinite(east) ||
    !Number.isFinite(south)
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

function classifyPhotonFeature(props: PhotonProperties): {
  kind: CandidateKind
  zoom: number
} {
  const val = (props.osm_value ?? props.type ?? '').toLowerCase()
  const key = (props.osm_key ?? '').toLowerCase()

  if (val === 'state' || val === 'province' || val === 'region') {
    return { kind: 'province', zoom: 7 }
  }
  if (val === 'city') return { kind: 'city', zoom: 12 }
  if (val === 'town') return { kind: 'city', zoom: 13 }
  if (val === 'village' || val === 'hamlet' || val === 'locality') {
    return { kind: 'localidad', zoom: 13 }
  }
  if (val === 'county' || val === 'district' || val === 'administrative') {
    return { kind: 'department', zoom: 10 }
  }
  if (val === 'suburb' || val === 'quarter' || val === 'neighbourhood') {
    return { kind: 'neighbourhood', zoom: 14 }
  }
  if (
    key === 'highway' ||
    val === 'house' ||
    val === 'residential' ||
    val === 'street' ||
    Boolean(props.street)
  ) {
    return { kind: 'address', zoom: 15 }
  }
  if (
    key === 'railway' ||
    key === 'amenity' ||
    key === 'tourism' ||
    key === 'shop' ||
    key === 'leisure' ||
    key === 'office' ||
    key === 'craft' ||
    key === 'industrial' ||
    key === 'power' ||
    key === 'building' ||
    val === 'station' ||
    val === 'bus_stop' ||
    val === 'school'
  ) {
    return { kind: 'poi', zoom: 14 }
  }
  return { kind: 'localidad', zoom: 12 }
}

function formatPhotonLabels(props: PhotonProperties): {
  label: string
  secondaryLabel: string
} {
  const primary =
    cleanDisplayText(props.name) ||
    cleanDisplayText(
      [props.street, props.housenumber].filter(Boolean).join(' ')
    ) ||
    cleanDisplayText(props.city) ||
    cleanDisplayText(props.town) ||
    cleanDisplayText(props.village) ||
    cleanDisplayText(props.state) ||
    'Ubicación'

  const contextParts: string[] = []
  const locality =
    cleanDisplayText(props.city) ||
    cleanDisplayText(props.town) ||
    cleanDisplayText(props.village) ||
    cleanDisplayText(props.county)
  if (
    locality &&
    normalizeSearchText(locality) !== normalizeSearchText(primary)
  ) {
    contextParts.push(locality)
  }

  const state = cleanDisplayText(props.state)
  if (state && normalizeSearchText(state) !== normalizeSearchText(primary)) {
    contextParts.push(state)
  }

  return {
    label: primary,
    secondaryLabel: contextParts.join(' · ') || 'Argentina',
  }
}

async function fetchPhotonCandidates(
  parsed: ParsedQuery,
  provinceIds: string[],
  signal?: AbortSignal
): Promise<SearchCandidate[]> {
  const params = new URLSearchParams({
    q: parsed.photonQuery,
    limit: '10',
    bbox: PHOTON_ARGENTINA_BBOX,
  })

  const response = await fetch(`${PHOTON_URL}?${params.toString()}`, {
    signal,
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) {
    throw new Error(`Photon HTTP ${response.status}`)
  }

  const data = (await response.json()) as PhotonResponse
  const features = Array.isArray(data.features) ? data.features : []
  const candidates: SearchCandidate[] = []

  for (const feature of features) {
    const props = feature.properties
    const coords = feature.geometry?.coordinates
    if (!props || !Array.isArray(coords) || coords.length < 2) continue

    // Filtro estricto a Argentina
    if ((props.countrycode ?? '').toUpperCase() !== 'AR') continue

    const lon = Number(coords[0])
    const lat = Number(coords[1])
    if (!isWithinArgentinaBounds(lat, lon)) continue

    const { label, secondaryLabel } = formatPhotonLabels(props)
    const { kind, zoom } = classifyPhotonFeature(props)
    const provName = cleanDisplayText(props.state)

    candidates.push({
      result: {
        id: `photon-${String(props.osm_type ?? 'n')}-${String(props.osm_id ?? `${lat}-${lon}`)}`,
        label,
        secondaryLabel,
        coords: { lat, lon },
        zoom,
        bounds: parsePhotonExtent(props.extent),
        inSelectedProvinces: isPointInProvinces(lat, lon, provinceIds),
      },
      normLabel: normalizeSearchText(label),
      provinceNorm: normalizeSearchText(provName),
      kind,
      sourceRank: 2,
      fromGeoref: false,
      fromPhoton: true,
    })
  }

  return candidates
}

function approxDistanceKm(a: Coordenadas, b: Coordenadas): number {
  const dLat = (a.lat - b.lat) * 111
  const dLon = (a.lon - b.lon) * 90
  return Math.hypot(dLat, dLon)
}

function mergeCandidates(candidates: SearchCandidate[]): SearchCandidate[] {
  const merged: SearchCandidate[] = []

  for (const candidate of candidates) {
    const existing = merged.find((item) => {
      if ((item.kind === 'province') !== (candidate.kind === 'province')) {
        return false
      }
      if (item.kind === 'province' && candidate.kind === 'province') {
        return item.normLabel === candidate.normLabel
      }
      if (
        item.provinceNorm &&
        candidate.provinceNorm &&
        item.provinceNorm !== candidate.provinceNorm
      ) {
        return false
      }
      const distKm = approxDistanceKm(item.result.coords, candidate.result.coords)
      const sameName = item.normLabel === candidate.normLabel
      const similarName =
        item.normLabel.includes(candidate.normLabel) ||
        candidate.normLabel.includes(item.normLabel)
      const sameSpotSameKind =
        distKm < 1.2 &&
        (item.kind === candidate.kind ||
          (item.kind === 'city' && candidate.kind === 'localidad') ||
          (item.kind === 'localidad' && candidate.kind === 'city'))

      return (
        sameSpotSameKind ||
        (sameName && distKm < 12) ||
        (similarName && distKm < 12 && item.kind === candidate.kind)
      )
    })

    if (!existing) {
      merged.push({ ...candidate })
      continue
    }

    existing.fromGeoref = existing.fromGeoref || candidate.fromGeoref
    existing.fromPhoton = existing.fromPhoton || candidate.fromPhoton

    // Conserva la mejor fuente de nombre/etiqueta (p. ej. Georef localidades > localidades-censales)
    if (candidate.sourceRank > existing.sourceRank) {
      const preservedBounds = existing.result.bounds ?? candidate.result.bounds
      const preservedPolygons =
        existing.result.polygons ?? candidate.result.polygons
      existing.result = {
        ...candidate.result,
        bounds: preservedBounds,
        polygons: preservedPolygons,
      }
      existing.normLabel = candidate.normLabel
      existing.kind = candidate.kind
      existing.sourceRank = candidate.sourceRank
    } else {
      if (!existing.result.bounds && candidate.result.bounds) {
        existing.result.bounds = candidate.result.bounds
      }
      if (!existing.result.polygons && candidate.result.polygons) {
        existing.result.polygons = candidate.result.polygons
      }
    }
  }

  return merged
}

function scoreCandidate(candidate: SearchCandidate, parsed: ParsedQuery): number {
  const normRaw = normalizeSearchText(parsed.raw)
  const normGeo = normalizeSearchText(parsed.georefQuery)
  const label = candidate.normLabel

  let score = 0

  if (label === normGeo || label === normRaw) {
    score += 70
  } else if (label.startsWith(normGeo) || label.startsWith(normRaw)) {
    score += 40
  } else {
    const tokens = normGeo.split(' ').filter((t) => t.length >= 2)
    if (tokens.length > 0 && tokens.every((t) => label.includes(t))) {
      score += 22
    }
  }

  if (parsed.provinceHint) {
    const targetProv = normalizeSearchText(parsed.provinceHint.properties.nombre)
    if (candidate.provinceNorm === targetProv) {
      score += 80
    } else if (candidate.provinceNorm) {
      score -= 80
    }
  }

  if (candidate.result.inSelectedProvinces) {
    score += 24
  }

  if (candidate.fromGeoref && candidate.fromPhoton) {
    score += 22
  }

  switch (candidate.kind) {
    case 'city':
      score += 28
      break
    case 'localidad':
      score += 24
      break
    case 'province':
      score += label === normGeo || label === normRaw ? 32 : 20
      break
    case 'department':
      score += 14
      break
    case 'neighbourhood':
      score += 10
      break
    case 'address':
      score += parsed.looksLikeAddress ? 20 : -12
      break
    case 'poi':
      score -= 28
      break
  }

  return score
}

/**
 * Busca localidades, departamentos, provincias, direcciones o coordenadas exclusivamente en Argentina.
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
  if (isCoordinateOutsideArgentina(query)) {
    return []
  }

  const cacheKey = `${normalizeSearchText(query)}|${[...provinceIds].sort().join(',')}`
  const cached = searchCache.get(cacheKey)
  if (cached) {
    return cached
  }

  const parsed = parseSearchQuery(query)
  const localProvinces = searchLocalProvinces(parsed, provinceIds)

  const [georefSettled, photonSettled] = await Promise.allSettled([
    fetchGeorefCandidates(parsed, provinceIds, signal),
    fetchPhotonCandidates(parsed, provinceIds, signal),
  ])

  if (signal?.aborted) {
    throw new DOMException('Aborted', 'AbortError')
  }

  if (
    georefSettled.status === 'rejected' &&
    photonSettled.status === 'rejected' &&
    localProvinces.length === 0
  ) {
    throw new Error('No fue posible buscar la ubicación. Intente nuevamente.')
  }

  const combined: SearchCandidate[] = [...localProvinces]
  if (georefSettled.status === 'fulfilled') {
    combined.push(...georefSettled.value)
  }
  if (photonSettled.status === 'fulfilled') {
    combined.push(...photonSettled.value)
  }

  const merged = mergeCandidates(combined)

  // Si el usuario especificó provincia explícita y hay coincidencias de esa provincia, ocultar las de otras
  const targetProvNorm = parsed.provinceHint
    ? normalizeSearchText(parsed.provinceHint.properties.nombre)
    : null

  const filtered = targetProvNorm
    ? merged.some((c) => c.provinceNorm === targetProvNorm)
      ? merged.filter((c) => c.provinceNorm === targetProvNorm)
      : merged
    : merged

  filtered.sort((a, b) => {
    const diff = scoreCandidate(b, parsed) - scoreCandidate(a, parsed)
    if (diff !== 0) return diff
    return a.result.label.localeCompare(b.result.label, 'es')
  })

  const finalResults = filtered.slice(0, 6).map((item) => item.result)

  if (searchCache.size >= SEARCH_CACHE_MAX) {
    const oldestKey = searchCache.keys().next().value
    if (oldestKey !== undefined) {
      searchCache.delete(oldestKey)
    }
  }
  searchCache.set(cacheKey, finalResults)

  return finalResults
}
