import { describe, expect, it, vi } from 'vitest'

import {
  getAgentStreamStopState,
  resetAgentStreamStopState,
  setAgentStreamStopState,
  subscribeAgentStreamStopState,
} from './stream-stop-state'

describe('Agent stream stop state', () => {
  it('tracks running cancellation as a distinct stopping state', () => {
    resetAgentStreamStopState()
    expect(getAgentStreamStopState()).toBe('idle')

    setAgentStreamStopState('stopping')
    expect(getAgentStreamStopState()).toBe('stopping')

    setAgentStreamStopState('idle')
    expect(getAgentStreamStopState()).toBe('idle')
  })

  it('notifies observers only when the state actually changes', () => {
    resetAgentStreamStopState()
    const listener = vi.fn()
    const unsubscribe = subscribeAgentStreamStopState(listener)

    setAgentStreamStopState('idle')
    setAgentStreamStopState('stopping')
    setAgentStreamStopState('stopping')
    setAgentStreamStopState('idle')

    expect(listener).toHaveBeenCalledTimes(2)
    unsubscribe()
  })

  it('can be reset after a request failure or terminal stream', () => {
    setAgentStreamStopState('stopping')
    resetAgentStreamStopState()

    expect(getAgentStreamStopState()).toBe('idle')
  })
})