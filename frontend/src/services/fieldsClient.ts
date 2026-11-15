import type { FieldCreateRequest, UserField } from '../types/api'
import { loginUser, requestBackendJson } from './authClient'

const POLYGONS_STORAGE_KEY = 'ereia_field_polygons_v1'
const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL || 'demo@ereia.app'
const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD || 'demo1234'

function readPolygonCache(): Record<string, [number, number][]> {
  try {
    const raw = window.localStorage.getItem(POLYGONS_STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

export function saveFieldPolygon(
  fieldId: string,
  polygon: [number, number][]
): void {
  if (!fieldId || polygon.length < 3) return
  try {
    const cache = readPolygonCache()
    cache[fieldId] = polygon
    window.localStorage.setItem(POLYGONS_STORAGE_KEY, JSON.stringify(cache))
  } catch {
    // Ignorar si el navegador bloquea almacenamiento local
  }
}

export function attachCachedPolygons(fields: UserField[]): UserField[] {
  const cache = readPolygonCache()
  return fields.map((field) => {
    const cached = cache[field.id]
    return Array.isArray(cached) && cached.length >= 3
      ? { ...field, polygon: cached }
      : field
  })
}

export async function loginDemoAccount(): Promise<string> {
  const response = await loginUser({
    email: DEMO_EMAIL,
    password: DEMO_PASSWORD,
  })
  if (!response.access_token) {
    throw new Error('No se recibió token de acceso para el usuario demo.')
  }
  return response.access_token
}

export async function listUserFields(token: string): Promise<UserField[]> {
  const data = await requestBackendJson<
    UserField[] | { fields?: UserField[]; items?: UserField[] }
  >(
    '/api/v1/fields',
    {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
    'No fue posible obtener los campos registrados.'
  )

  const list = Array.isArray(data)
    ? data
    : Array.isArray(data.fields)
      ? data.fields
      : Array.isArray(data.items)
        ? data.items
        : []

  return attachCachedPolygons(list)
}

export async function createUserField(
  token: string,
  payload: FieldCreateRequest
): Promise<UserField> {
  return requestBackendJson<UserField>(
    '/api/v1/fields',
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    },
    'No fue posible guardar el nuevo campo.'
  )
}
