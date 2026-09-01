import { describe, expect, it, vi } from 'vitest'
import {
  resolveApiKeyExpiration,
  type ApiKeyExpirationValue,
} from './ApiKeyExpirationField'

describe('ApiKeyExpirationField', () => {
  it('keeps no-expiration keys without an expiration timestamp', () => {
    const value: ApiKeyExpirationValue = { preset: 'never', customDate: null }

    expect(resolveApiKeyExpiration(value)).toBeNull()
  })

  it('returns the exact custom expiration date', () => {
    const customDate = new Date('2026-07-24T21:30:00.000Z')
    const value: ApiKeyExpirationValue = { preset: 'custom', customDate }

    expect(resolveApiKeyExpiration(value)).toBe(customDate)
  })

  it('resolves the 90-day default from the current time', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-09T15:00:00.000Z'))

    const resolved = resolveApiKeyExpiration({ preset: '90d', customDate: null })

    expect(resolved?.toISOString()).toBe('2026-10-07T15:00:00.000Z')
    vi.useRealTimers()
  })
})
