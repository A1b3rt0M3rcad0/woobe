import { describe, expect, it } from 'vitest'

import { shouldRefreshAgentRunList } from './hooks'

describe('Playground Agent Run cache refresh policy', () => {
  it('refreshes once when the Run identity first becomes known', () => {
    expect(shouldRefreshAgentRunList(null, 'run-1')).toBe(true)
  })

  it('does not refresh again for repeated metadata or run.state frames of the same Run', () => {
    expect(shouldRefreshAgentRunList('run-1', 'run-1')).toBe(false)
  })

  it('does not refresh when a frame has no Run identity', () => {
    expect(shouldRefreshAgentRunList('run-1', null)).toBe(false)
  })

  it('refreshes when a new owned Run starts', () => {
    expect(shouldRefreshAgentRunList('run-1', 'run-2')).toBe(true)
  })
})
