// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  getStoredPlaygroundExternalContext,
  setStoredPlaygroundExternalContext,
} from './playground-session-store'

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  localStorage.clear()
})

describe('Playground External Context persistence', () => {
  it('restores remembered values after a reload-equivalent read', () => {
    setStoredPlaygroundExternalContext(
      'project-1',
      'agent-1',
      'draft',
      { age: 18, name: 'Alberto' },
    )

    expect(getStoredPlaygroundExternalContext(
      'project-1',
      'agent-1',
      'draft',
    )).toEqual({ age: 18, name: 'Alberto' })
  })

  it('isolates remembered values by runtime environment', () => {
    setStoredPlaygroundExternalContext(
      'project-1',
      'agent-1',
      'draft',
      { age: 18 },
    )
    setStoredPlaygroundExternalContext(
      'project-1',
      'agent-1',
      'production',
      { age: 42 },
    )

    expect(getStoredPlaygroundExternalContext(
      'project-1',
      'agent-1',
      'draft',
    )).toEqual({ age: 18 })
    expect(getStoredPlaygroundExternalContext(
      'project-1',
      'agent-1',
      'production',
    )).toEqual({ age: 42 })
    expect(getStoredPlaygroundExternalContext(
      'project-1',
      'agent-1',
      'staging',
    )).toBeNull()
  })

  it('isolates remembered values by Agent', () => {
    setStoredPlaygroundExternalContext(
      'project-1',
      'agent-1',
      'draft',
      { name: 'first' },
    )
    setStoredPlaygroundExternalContext(
      'project-1',
      'agent-2',
      'draft',
      { name: 'second' },
    )

    expect(getStoredPlaygroundExternalContext(
      'project-1',
      'agent-1',
      'draft',
    )).toEqual({ name: 'first' })
    expect(getStoredPlaygroundExternalContext(
      'project-1',
      'agent-2',
      'draft',
    )).toEqual({ name: 'second' })
  })

  it('persists an explicit empty object after Clear instead of falling back to defaults', () => {
    setStoredPlaygroundExternalContext(
      'project-1',
      'agent-1',
      'draft',
      { age: 18 },
    )
    setStoredPlaygroundExternalContext(
      'project-1',
      'agent-1',
      'draft',
      {},
    )

    expect(getStoredPlaygroundExternalContext(
      'project-1',
      'agent-1',
      'draft',
    )).toEqual({})
  })

  it('ignores corrupt or non-object local storage values', () => {
    localStorage.setItem(
      'woobe:agent-external-context:project-1:agent-1:draft',
      '{invalid',
    )
    expect(getStoredPlaygroundExternalContext(
      'project-1',
      'agent-1',
      'draft',
    )).toBeNull()

    localStorage.setItem(
      'woobe:agent-external-context:project-1:agent-1:draft',
      '[]',
    )
    expect(getStoredPlaygroundExternalContext(
      'project-1',
      'agent-1',
      'draft',
    )).toBeNull()
  })
})
