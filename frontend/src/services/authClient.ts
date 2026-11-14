import type {
  AuthLoginRequest,
  AuthRegisterRequest,
  AuthResponse,
  UserProfile,
} from '../types/api'

const RAW_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const API_BASE_URL = RAW_API_URL
  .replace(/\/api\/v1\/simulate\/?$/, '')
  .replace(/\/+$/, '')

const TOKEN_STORAGE_KEY = 'shark_attack_access_token'

export function getStoredAuthToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

export function setStoredAuthToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token)
  } catch {
    // Ignorar si el navegador bloquea almacenamiento local
  }
}

export function clearStoredAuthToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY)
  } catch {
    // Ignorar si el navegador bloquea almacenamiento local
  }
}

function parseErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') {
    return fallback
  }

  const record = payload as Record<string, unknown>
  if (typeof record.detail === 'string' && record.detail.trim()) {
    return record.detail
  }

  if (Array.isArray(record.detail) && record.detail.length > 0) {
    const first = record.detail[0] as Record<string, unknown> | undefined
    if (first && typeof first.msg === 'string') {
      return first.msg
    }
  }

  if (typeof record.message === 'string' && record.message.trim()) {
    return record.message
  }

  return fallback
}

async function requestAuthJson<T>(
  path: string,
  options: RequestInit,
  fallbackError: string
): Promise<T> {
  let response: Response

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    })
  } catch {
    throw new Error(
      'No fue posible conectar con el servidor de autenticación. Verifique que el backend esté en ejecución o ingrese en modo demo.'
    )
  }

  const data = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(parseErrorMessage(data, fallbackError))
  }

  return data as T
}

export function extractUserFromAuthResponse(
  data: AuthResponse,
  fallbackEmail = '',
  fallbackName = ''
): UserProfile {
  const candidate = data.user ?? data.profile
  if (candidate) {
    return {
      id: candidate.id || '',
      email: candidate.email || fallbackEmail,
      nombre: candidate.nombre || fallbackName,
    }
  }
  return {
    id: '',
    email: fallbackEmail,
    nombre: fallbackName,
  }
}

export async function loginUser(
  payload: AuthLoginRequest
): Promise<AuthResponse> {
  return requestAuthJson<AuthResponse>(
    '/api/v1/auth/login',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
    'No fue posible iniciar sesión. Verifique su correo y contraseña.'
  )
}

export async function registerUser(
  payload: AuthRegisterRequest
): Promise<AuthResponse> {
  return requestAuthJson<AuthResponse>(
    '/api/v1/auth/register',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
    'No fue posible crear la cuenta. Verifique los datos ingresados.'
  )
}

export async function fetchCurrentUser(token: string): Promise<UserProfile> {
  return requestAuthJson<UserProfile>(
    '/api/v1/auth/me',
    {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
    'La sesión ha expirado. Inicie sesión nuevamente.'
  )
}
