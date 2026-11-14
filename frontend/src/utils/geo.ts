import type { Coordenadas } from '../types/api'

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
