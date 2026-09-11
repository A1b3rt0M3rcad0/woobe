import { describe, expect, it } from 'vitest'

import { ApiError } from '@/lib/api/errors'
import { agentRunDetailRefetchInterval } from './hooks'

describe('Agent Run detail polling policy', () => {
  it('stops interval polling after a definitive 404', () => {
    expect(agentRunDetailRefetchInterval(undefined, new ApiError('Resource not found', 404))).toBe(false)
  })

  it('stops polling for a terminal Agent Run', () => {
    expect(agentRunDetailRefetchInterval({ status: 'completed' }, null)).toBe(false)
  })

  it('keeps polling while a known Agent Run is still active', () => {
    expect(agentRunDetailRefetchInterval({ status: 'running' }, null)).toBe(1_500)
  })
})
