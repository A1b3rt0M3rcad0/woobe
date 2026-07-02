import { ApiError, UnauthorizedError } from './errors'

function resolveBaseUrl(value: string | undefined): string {
  const baseUrl = value?.trim()

  if (!baseUrl) {
    throw new Error('VITE_API_URL must be configured with an absolute API URL')
  }

  try {
    const url = new URL(baseUrl)
    if (url.protocol !== 'http:' && url.protocol !== 'https:') {
      throw new Error('Invalid API URL protocol')
    }
    return url.toString().replace(/\/+$/, '')
  } catch {
    throw new Error(`VITE_API_URL must be an absolute HTTP(S) URL. Received: ${baseUrl}`)
  }
}

const BASE_URL = resolveBaseUrl(import.meta.env.VITE_API_URL)
const AUTH_REFRESH_PATH = '/identity/auth/refresh'
const AUTH_PUBLIC_PATHS = new Set([
  '/identity/auth/login',
  '/identity/auth/register',
  AUTH_REFRESH_PATH,
])
const CSRF_COOKIE_NAME = 'projectrai_csrf'
const CSRF_HEADER_NAME = 'X-CSRF-Token'
const CSRF_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

interface RequestOptions {
  headers?: Record<string, string>
  params?: Record<string, string | number | undefined>
}

interface ApiEnvelope<T> {
  success: boolean
  message?: string
  data?: T
}

let refreshPromise: Promise<void> | null = null

function buildUrl(path: string, params?: RequestOptions['params']): string {
  let url = `${BASE_URL}${path}`

  if (params) {
    const searchParams = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== '') {
        searchParams.set(key, String(value))
      }
    }
    const qs = searchParams.toString()
    if (qs) url += `?${qs}`
  }

  return url
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null

  const prefix = `${encodeURIComponent(name)}=`
  const value = document.cookie
    .split('; ')
    .find((entry) => entry.startsWith(prefix))

  return value ? decodeURIComponent(value.slice(prefix.length)) : null
}

export function getCsrfHeaders(method: string): Record<string, string> {
  if (!CSRF_METHODS.has(method.toUpperCase())) return {}

  const token = readCookie(CSRF_COOKIE_NAME)
  if (!token) return {}

  return { [CSRF_HEADER_NAME]: token }
}

function redirectToLogin(): void {
  if (typeof window !== 'undefined') {
    window.location.href = '/login'
  }
}

export async function refreshAuthSession(): Promise<void> {
  if (refreshPromise) return refreshPromise

  refreshPromise = (async () => {
    const res = await fetch(buildUrl(AUTH_REFRESH_PATH), {
      method: 'POST',
      credentials: 'include',
    })

    if (res.status === 401) {
      throw new UnauthorizedError()
    }

    let data: ApiEnvelope<unknown> | null = null
    try {
      data = await res.json()
    } catch {
      data = null
    }

    if (!res.ok) {
      throw new ApiError(data?.message || 'Unable to refresh authentication session', res.status, data?.data)
    }
  })().finally(() => {
    refreshPromise = null
  })

  return refreshPromise
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options?: RequestOptions,
  hasRetriedAuth = false,
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options?.headers || {}),
    ...getCsrfHeaders(method),
  }

  if (body !== undefined && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  let res: Response
  try {
    res = await fetch(buildUrl(path, options?.params), {
      method,
      headers,
      credentials: 'include',
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
    })
  } catch (err) {
    if (err instanceof TypeError) {
      throw new ApiError(
        'Network error. API unavailable or CORS blocked the request.',
        0,
        null,
      )
    }
    throw new ApiError(
      err instanceof Error ? err.message : 'Unknown network error',
      0,
      null,
    )
  }

  if (import.meta.env.DEV) {
    const maybeBody = body ? JSON.stringify(body).slice(0, 200) : ''
    console.log(`[API] ${method} ${path} → ${res.status}${maybeBody ? ` ${maybeBody}` : ''}`)
  }

  if (res.status === 401 && !hasRetriedAuth && !AUTH_PUBLIC_PATHS.has(path)) {
    try {
      await refreshAuthSession()
      return request<T>(method, path, body, options, true)
    } catch {
      if (import.meta.env.DEV) console.warn('[API] Refresh failed — redirecting to login')
      redirectToLogin()
      throw new UnauthorizedError()
    }
  }

  if (res.status === 401) {
    if (import.meta.env.DEV) console.warn('[API] 401 Unauthorized — redirecting to login')
    if (!AUTH_PUBLIC_PATHS.has(path)) {
      redirectToLogin()
    }
    throw new UnauthorizedError()
  }

  let data: ApiEnvelope<T> | null = null
  try {
    data = await res.json()
    if (import.meta.env.DEV && res.ok) {
      const bodyPreview = JSON.stringify(data?.data).slice(0, 100)
      console.log(`[API] ${method} ${path} → OK${bodyPreview ? ` ${bodyPreview}` : ''}`)
    }
  } catch {
    if (!res.ok) {
      throw new ApiError(
        data?.message || `Server error: ${method} ${path} (status ${res.status})`,
        res.status,
        null,
      )
    }
  }

  if (!res.ok) {
    const errorMsg = data?.message
      || (res.status === 400 ? 'Validation error'
        : res.status === 404 ? `Resource not found: ${method} ${path}`
        : res.status === 405 ? `Method not allowed: ${method} ${path}. Check frontend API client.`
        : res.status === 403 ? 'Permission denied'
        : res.status >= 500 ? `Server error: ${method} ${path}`
        : `Request failed with status ${res.status}`)
    if (import.meta.env.DEV) {
      console.error(`[API] ERROR ${method} ${path} → ${res.status}: ${errorMsg}`, data)
    }
    throw new ApiError(errorMsg, res.status, data?.data)
  }

  return data?.data as T
}

export function get<T>(path: string, options?: RequestOptions): Promise<T> {
  return request<T>('GET', path, undefined, options)
}

export function post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
  return request<T>('POST', path, body, options)
}

export function patch<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
  return request<T>('PATCH', path, body, options)
}

export function put<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
  return request<T>('PUT', path, body, options)
}

export function del<T>(path: string, options?: RequestOptions): Promise<T> {
  return request<T>('DELETE', path, undefined, options)
}