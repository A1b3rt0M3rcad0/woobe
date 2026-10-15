import { describe, expect, it } from 'vitest'
import { formatCurrency, formatLatency, formatTokens } from './number'

describe('operational number formatting', () => {
  it('keeps a measured micro-cost distinct from a free operation', () => {
    expect(formatCurrency(.00000004)).toBe('$0.00000004')
    expect(formatCurrency(0)).toBe('$0.0000')
    expect(formatCurrency(null)).toBe('—')
  })
  it('does not present non-finite telemetry as a numeric result', () => {
    for (const value of [NaN, Infinity, -Infinity]) {
      expect(formatCurrency(value)).toBe('—')
      expect(formatTokens(value)).toBe('—')
      expect(formatLatency(value)).toBe('—')
    }
  })
})
