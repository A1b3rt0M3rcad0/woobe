import { getToken, setToken, clearToken } from '@/lib/auth/token'
import { ApiError, UnauthorizedError } from './errors'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const REFRESH_PATH = '/identity/auth/refresh'
const NON_REFRESHABLE_PATHS = new Set([
  '/identity/auth/login',
  '/identity/auth/register',
  REFRESH_PATH,
])

interface RequestOptions {
  headers?: Record<string, string>
  params?: Record<string, string | number | undefined>
  skipAuthRefresh?: boolean
}

interface ApiEnvelope<T> {
  success: boolean
  message?: string
  data?: T
}

interface RefreshData {
  token?: string
  access_token?: string
}

let refreshPromise: Promise<string> | null = null

function buildUrl(path: string, params?: RequestOptions['params']): string {
  let url = `${BASE_URL}${path}`
  if (!params) return url

  const searchParams = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') searchParams.set(key, String(value))
  }
  const query = searchParams.toString()
  if (query) url += `?${query}`
  return url
}

async function readEnvelope<T>(response: Response): Promise<ApiEnvelope<T> | null> {
  try {
    return await response.json() as ApiEnvelope<T>
  } catch {
    return null
  }
}

async function rotateAccessToken(): Promise<string> {
  if (refreshPromise) return refreshPromise

  refreshPromise = (async () => {
    let response: Response
    try {
      response = await fetch(`${BASE_URL}${REFRESH_PATH}`, {
        method: 'POST',
        credentials: 'include',
      })
    } catch {
      clearToken()
      throw new UnauthorizedError('Authentication refresh is unavailable')
    }

    const envelope = await readEnvelope<RefreshData>(response)
    const token = envelope?.data?.token || envelope?.data?.access_token
    if (!response.ok || !token) {
      clearToken()
      throw new UnauthorizedError(envelope?.message || 'Authentication session expired')
    }

    setToken(token)
    return token
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
  retried = false,
): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = { ...(options?.headers || {}) }
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  let response: Response
  try {
    response = await fetch(buildUrl(path, options?.params), {
      method,
      headers,
      credentials: 'include',
      body: body instanceof FormData
        ? body
        : body !== undefined
          ? JSON.stringify(body)
          : undefined,
    })
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ApiError('Network error. API unavailable or CORS blocked the request.', 0, null)
    }
    throw new ApiError(error instanceof Error ? error.message : 'Unknown network error', 0, null)
  }

  if (import.meta.env.DEV) {
    console.log(`[API] ${method} ${path} -> ${response.status}`)
  }

  const mayRefresh = !retried
    && !options?.skipAuthRefresh
    && !NON_REFRESHABLE_PATHS.has(path)

  if (response.status === 401 && mayRefresh) {
    try {
      await rotateAccessToken()
      return request<T>(method, path, body, options, true)
    } catch (error) {
      clearToken()
      if (error instanceof UnauthorizedError) throw error
      throw new UnauthorizedError()
    }
  }

  const envelope = await readEnvelope<T>(response)

  if (response.status === 401) {
    clearToken()
    throw new UnauthorizedError(envelope?.message)
  }

  if (!response.ok) {
    const errorMessage = envelope?.message
      || (response.status === 400 ? 'Validation error'
        : response.status === 404 ? `Resource not found: ${method} ${path}`
        : response.status === 405 ? `Method not allowed: ${method} ${path}`
        : response.status === 403 ? 'Permission denied'
        : response.status >= 500 ? `Server error: ${method} ${path}`
        : `Request failed with status ${response.status}`)
    throw new ApiError(errorMessage, response.status, envelope?.data)
  }

  return envelope?.data as T
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
