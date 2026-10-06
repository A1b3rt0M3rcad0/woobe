import { describe, expect, it } from 'vitest'
import { expirationAfterDate } from './expiration'
import { constrainedConditions } from './AccessRolePicker'

describe('date-only CLI key expiration', () => {
  it('includes the selected local day and stops at the following midnight', () => {
    const selected = new Date(2026, 11, 31, 15, 35)
    const expiration = expirationAfterDate(selected)!
    expect(expiration.getFullYear()).toBe(2027)
    expect(expiration.getMonth()).toBe(0)
    expect(expiration.getDate()).toBe(1)
    expect(expiration.getHours()).toBe(0)
    expect(expiration.getMinutes()).toBe(0)
    expect(selected.getDate()).toBe(31)
    expect(expirationAfterDate(null)).toBeNull()
  })
})

describe('delegated role restrictions', () => {
  it('preserves inherited restrictions and narrows category conditions', () => {
    expect(
      constrainedConditions(
        { environments: ['staging', 'production'] },
        { environments: ['staging'], target_ids: ['agent-a'] },
      ),
    ).toEqual({ environments: ['staging'], target_ids: ['agent-a'] })
    expect(
      constrainedConditions(
        { environments: ['production'] },
        { environments: ['staging'] },
      ),
    ).toBeNull()
  })
})
