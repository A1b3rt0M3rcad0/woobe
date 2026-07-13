import { describe, expect, it } from 'vitest'
import {
  ENVIRONMENT_APPEARANCE,
  getEnvironmentAppearance,
  isRuntimeEnvironmentAppearanceKey,
} from '../environment-appearance'

describe('environment appearance', () => {
  it('uses the Overview amber palette for Staging', () => {
    expect(ENVIRONMENT_APPEARANCE.staging).toMatchObject({
      dot: 'bg-amber-400',
      border: 'border-amber-500/35',
      background: 'bg-amber-500/10',
      text: 'text-amber-300',
      chartColor: '#fbbf24',
    })
  })

  it('keeps Production and Draft visually distinct', () => {
    expect(ENVIRONMENT_APPEARANCE.production.dot).toBe('bg-emerald-400')
    expect(ENVIRONMENT_APPEARANCE.draft.dot).toBe('bg-blue-400')
  })

  it('resolves supported environments case-insensitively', () => {
    expect(getEnvironmentAppearance(' Staging ')).toBe(ENVIRONMENT_APPEARANCE.staging)
    expect(getEnvironmentAppearance('PRODUCTION')).toBe(ENVIRONMENT_APPEARANCE.production)
  })

  it('does not reinterpret operational statuses as environments', () => {
    expect(isRuntimeEnvironmentAppearanceKey('warning')).toBe(false)
    expect(getEnvironmentAppearance('warning')).toBeNull()
  })
})
