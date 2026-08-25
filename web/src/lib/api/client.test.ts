import { afterEach, describe, expect, it, vi } from 'vitest'

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

function apiResponse(data: unknown, status = 200) {
  return new Response(
    JSON.stringify({
      success: status >= 200 && status < 300,
      data,
    }),
    {
      status,
      headers: { 'Content-Type': 'application/json' },
    },
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
  vi.resetModules()
})

describe('API authentication refresh', () => {
  it('does not rotate the session again for a delayed 401 from the previous auth generation', async () => {
    vi.stubEnv('VITE_API_URL', 'http://api.test')

    const firstA = deferred<Response>()
    const firstB = deferred<Response>()
    let attemptsA = 0
    let attemptsB = 0
    let refreshCount = 0

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)

      if (url.endsWith('/resource-a')) {
        attemptsA += 1
        return attemptsA === 1
          ? firstA.promise
          : apiResponse({ value: 'a' })
      }

      if (url.endsWith('/resource-b')) {
        attemptsB += 1
        return attemptsB === 1
          ? firstB.promise
          : apiResponse({ value: 'b' })
      }

      if (url.endsWith('/identity/auth/refresh')) {
        refreshCount += 1
        return apiResponse({ csrf: 'rotated-csrf' })
      }

      throw new Error(`Unexpected request: ${url}`)
    })

    vi.stubGlobal('fetch', fetchMock)
    const { get } = await import('./client')

    const requestA = get<{ value: string }>('/resource-a')
    const requestB = get<{ value: string }>('/resource-b')

    firstA.resolve(apiResponse(null, 401))
    await expect(requestA).resolves.toEqual({ value: 'a' })
    expect(refreshCount).toBe(1)

    firstB.resolve(apiResponse(null, 401))
    await expect(requestB).resolves.toEqual({ value: 'b' })

    expect(refreshCount).toBe(1)
    expect(attemptsA).toBe(2)
    expect(attemptsB).toBe(2)
  })
})

describe('Community instance bootstrap', () => {
  it('posts the initial bootstrap without requesting an authenticated CSRF token', async () => {
    vi.stubEnv('VITE_API_URL', 'http://api.test')

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url.endsWith('/identity/auth/csrf')) {
        throw new Error('Bootstrap must not request CSRF before authentication')
      }

      if (url.endsWith('/identity/instance/bootstrap')) {
        expect(init?.method).toBe('POST')
        expect(new Headers(init?.headers).has('X-CSRF-Token')).toBe(false)
        return apiResponse({ csrf: 'bootstrap-csrf' }, 201)
      }

      throw new Error(`Unexpected request: ${url}`)
    })

    vi.stubGlobal('fetch', fetchMock)
    const { post } = await import('./client')

    await expect(
      post('/identity/instance/bootstrap', {
        email: 'owner@example.test',
        password: 'ReleaseGate123!',
      }),
    ).resolves.toEqual({ csrf: 'bootstrap-csrf' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
