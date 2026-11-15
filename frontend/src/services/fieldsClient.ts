import type {
  CampaignCreateRequest,
  CampaignUpdateRequest,
  FieldCampaign,
  SeguimientoResponse,
  FieldCreateRequest,
  FieldUpdateRequest,
  UserField,
} from '../types/api'
import { loginUser, requestBackendJson } from './authClient'

const POLYGONS_STORAGE_KEY = 'ereia_field_polygons_v1'
const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL || 'demoereia@gmail.com'
const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD || 'contraseñadedemo'

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

export function removeCachedFieldPolygon(fieldId: string): void {
  if (!fieldId) return
  try {
    const cache = readPolygonCache()
    if (fieldId in cache) {
      delete cache[fieldId]
      window.localStorage.setItem(POLYGONS_STORAGE_KEY, JSON.stringify(cache))
    }
  } catch {
    // Ignorar si el navegador bloquea almacenamiento local
  }
}

export function attachCachedPolygons(fields: UserField[]): UserField[] {
  const cache = readPolygonCache()
  return fields.map((field) => {
    if (Array.isArray(field.polygon) && field.polygon.length >= 3) {
      return field
    }
    const cached = cache[field.id]
    return Array.isArray(cached) && cached.length >= 3
      ? { ...field, polygon: cached }
      : { ...field, polygon: undefined }
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

export async function updateUserField(
  token: string,
  fieldId: string,
  payload: FieldUpdateRequest
): Promise<UserField> {
  return requestBackendJson<UserField>(
    `/api/v1/fields/${fieldId}`,
    {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    },
    'No fue posible actualizar el campo seleccionado.'
  )
}

export async function deleteUserField(
  token: string,
  fieldId: string
): Promise<void> {
  await requestBackendJson<null>(
    `/api/v1/fields/${fieldId}`,
    {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
    'No fue posible eliminar el campo seleccionado.'
  )
}

export async function listFieldCampaigns(
  token: string,
  fieldId: string,
  signal?: AbortSignal
): Promise<FieldCampaign[]> {
  const data = await requestBackendJson<FieldCampaign[]>(
    `/api/v1/fields/${fieldId}/campaigns`,
    {
      method: 'GET',
      signal,
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
    'No fue posible obtener el historial de cultivos del campo.'
  )
  return Array.isArray(data) ? data : []
}

export async function createCampaign(
  token: string,
  fieldId: string,
  data: CampaignCreateRequest
): Promise<FieldCampaign> {
  return requestBackendJson<FieldCampaign>(
    `/api/v1/fields/${fieldId}/campaigns`,
    {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(data),
    },
    'No fue posible registrar la siembra.'
  )
}

const SEGUIMIENTO_API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

/** Error tipado del seguimiento: mismo criterio que `/simulate` (FRONT-36). */
export class SeguimientoError extends Error {
  readonly tipo: 'servicio_externo' | 'invalido' | 'sin_conexion'
  readonly fuente: string | null

  constructor(tipo: SeguimientoError['tipo'], mensaje: string, fuente: string | null = null) {
    super(mensaje)
    this.name = 'SeguimientoError'
    this.tipo = tipo
    this.fuente = fuente
  }
}

/** `GET /api/v1/fields/{field_id}/campaigns/{campaign_id}/seguimiento` (BACK-29). */
export async function fetchSeguimiento(
  token: string,
  fieldId: string,
  campaignId: string,
  signal?: AbortSignal
): Promise<SeguimientoResponse> {
  let response: Response
  try {
    response = await fetch(
      `${SEGUIMIENTO_API_BASE}/api/v1/fields/${fieldId}/campaigns/${campaignId}/seguimiento`,
      { method: 'GET', headers: { Authorization: `Bearer ${token}` }, signal }
    )
  } catch (err) {
    if (signal?.aborted) throw err
    throw new SeguimientoError('sin_conexion', 'No pudimos conectarnos con el servidor.')
  }
  if (!response.ok) {
    const cuerpo = (await response.json().catch(() => ({}))) as { detail?: unknown; fuente?: unknown }
    const detalle = typeof cuerpo.detail === 'string' ? cuerpo.detail : null
    if (response.status === 503) {
      throw new SeguimientoError(
        'servicio_externo',
        detalle ?? 'Servicio externo no disponible.',
        typeof cuerpo.fuente === 'string' ? cuerpo.fuente : null
      )
    }
    if (response.status === 422 || response.status === 404) {
      throw new SeguimientoError('invalido', detalle ?? 'No se puede seguir esta campaña.')
    }
    throw new SeguimientoError('sin_conexion', detalle ?? `Error HTTP ${response.status} del servidor.`)
  }
  return (await response.json()) as SeguimientoResponse
}

/** Cierra o edita una campaña (BACK-30): fecha de cosecha, rinde cosechado y notas. */
export async function updateCampaign(
  token: string,
  fieldId: string,
  campaignId: string,
  data: CampaignUpdateRequest
): Promise<FieldCampaign> {
  return requestBackendJson<FieldCampaign>(
    `/api/v1/fields/${fieldId}/campaigns/${campaignId}`,
    {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(data),
    },
    'No fue posible cerrar la campaña.'
  )
}

/** Borra una campaña y su seguimiento guardado (BACK-30). */
export async function deleteCampaign(token: string, fieldId: string, campaignId: string): Promise<void> {
  await requestBackendJson<null>(
    `/api/v1/fields/${fieldId}/campaigns/${campaignId}`,
    {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    },
    'No fue posible borrar la campaña.'
  )
}
