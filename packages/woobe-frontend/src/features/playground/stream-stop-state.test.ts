import { describe, expect, it, vi } from 'vitest'

import {
  getAgentStreamStopState,
  resetAgentStreamStopState,
  setAgentStreamStopState,
  subscribeAgentStreamStopState,
} from './stream-stop-state'

describe('Agent stream stop state', () => {
  it('tracks idle -> running -> stopping -> idle explicitly', () => {
    resetAgentStreamStopState()
    expect(getAgentStreamStopState()).toBe('idle')

    setAgentStreamStopState('running')
    expect(getAgentStreamStopState()).toBe('running')

    setAgentStreamStopState('stopping')
    expect(getAgentStreamStopState()).toBe('stopping')

    resetAgentStreamStopState()
    expect(getAgentStreamStopState()).toBe('idle')
  })

  it('returns to running rather than idle when a Stop request itself fails', () => {
    setAgentStreamStopState('running')
    setAgentStreamStopState('stopping')
    setAgentStreamStopState('running')

    expect(getAgentStreamStopState()).toBe('running')
  })

  it('notifies observers only when the state actually changes', () => {
    resetAgentStreamStopState()
    const listener = vi.fn()
    const unsubscribe = subscribeAgentStreamStopState(listener)

    setAgentStreamStopState('idle')
    setAgentStreamStopState('running')
    setAgentStreamStopState('running')
    setAgentStreamStopState('stopping')
    setAgentStreamStopState('stopping')
    setAgentStreamStopState('idle')

    expect(listener).toHaveBeenCalledTimes(3)
    unsubscribe()
  })

  it('can be reset after a terminal stream', () => {
    setAgentStreamStopState('stopping')
    resetAgentStreamStopState()

    expect(getAgentStreamStopState()).toBe('idle')
  })
})