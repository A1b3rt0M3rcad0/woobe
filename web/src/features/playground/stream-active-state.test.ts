import { describe, expect, it, vi } from 'vitest'

import {
  isAgentStreamActive,
  resetAgentStreamActiveState,
  setAgentStreamActive,
  subscribeAgentStreamActiveState,
} from './stream-active-state'

describe('Agent stream active state', () => {
  it('tracks whether this browser is observing an active Agent Run', () => {
    resetAgentStreamActiveState()
    expect(isAgentStreamActive()).toBe(false)

    setAgentStreamActive(true)
    expect(isAgentStreamActive()).toBe(true)

    resetAgentStreamActiveState()
    expect(isAgentStreamActive()).toBe(false)
  })

  it('notifies observers only on lifecycle transitions', () => {
    resetAgentStreamActiveState()
    const listener = vi.fn()
    const unsubscribe = subscribeAgentStreamActiveState(listener)

    setAgentStreamActive(false)
    setAgentStreamActive(true)
    setAgentStreamActive(true)
    setAgentStreamActive(false)

    expect(listener).toHaveBeenCalledTimes(2)
    unsubscribe()
  })
})
