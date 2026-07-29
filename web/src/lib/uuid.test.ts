import { afterEach, describe, expect, it, vi } from 'vitest'

import { createUuid } from './uuid'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('createUuid', () => {
  it('uses crypto.randomUUID when the browser exposes it', () => {
    const nativeUuid = '11111111-1111-4111-8111-111111111111'
    vi.stubGlobal('crypto', {
      randomUUID: () => nativeUuid,
      getRandomValues: (bytes: Uint8Array) => bytes,
    })

    expect(createUuid()).toBe(nativeUuid)
  })

  it('creates an RFC 4122 version 4 UUID when randomUUID is unavailable', () => {
    vi.stubGlobal('crypto', {
      getRandomValues: (bytes: Uint8Array) => {
        bytes.fill(0)
        return bytes
      },
    })

    expect(createUuid()).toBe('00000000-0000-4000-8000-000000000000')
  })

  it('keeps the UUID v4 contract when Web Crypto is unavailable', () => {
    vi.stubGlobal('crypto', undefined)
    vi.spyOn(Math, 'random').mockReturnValue(0)

    expect(createUuid()).toBe('00000000-0000-4000-8000-000000000000')
  })
})
