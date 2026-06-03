import { getToken, clearToken } from '@/lib/auth/token'
import { ApiError, UnauthorizedError } from './errors'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface RequestOptions {
  headers?: Record<string, string>
  params?: Record<string, string | number | undefined>
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options?: RequestOptions,
): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    ...(options?.headers || {}),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  let url = `${BASE_URL}${path}`

  if (options?.params) {
    const searchParams = new URLSearchParams()
    for (const [key, value] of Object.entries(options.params)) {
      if (value !== undefined && value !== '') {
        searchParams.set(key, String(value))
      }
    }
    const qs = searchParams.toString()
    if (qs) url += `?${qs}`
  }

  if (body !== undefined && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(url, {
    method,
    headers,
    body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
  })

  if (import.meta.env.DEV) {
    const maybeBody = body ? JSON.stringify(body).slice(0, 200) : ''
    console.log(`[API] ${method} ${path} → ${res.status}${maybeBody ? ` ${maybeBody}` : ''}`)
  }

  if (res.status === 401) {
    if (import.meta.env.DEV) console.warn(`[API] 401 Unauthorized — clearing token and redirecting to login`)
    clearToken()
    window.location.href = '/login'
    throw new UnauthorizedError()
  }

  let data: { success: boolean; message?: string; data?: T } | null = null
  try {
    data = await res.json()
    if (import.meta.env.DEV && res.ok) {
      const bodyPreview = JSON.stringify(data?.data).slice(0, 100)
      console.log(`[API] ${method} ${path} → OK${bodyPreview ? ` ${bodyPreview}` : ''}`)
    }
  } catch {
    if (!res.ok) {
      throw new ApiError(`Request failed with status ${res.status}`, res.status)
    }
  }

  if (!res.ok) {
    const errorMsg = res.status === 400
      ? data?.message || 'Validation error'
      : res.status === 404
        ? `Resource not found: ${method} ${path}`
        : res.status === 405
          ? `Method not allowed: ${method} ${path}. Check frontend API client.`
          : res.status === 403
            ? 'Permission denied'
            : res.status >= 500
              ? `Server error: ${method} ${path}`
              : data?.message || `Request failed with status ${res.status}`
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
