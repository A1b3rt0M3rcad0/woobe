import { describe, expect, it } from 'vitest'

import { ApiError } from '@/lib/api/errors'
import {
  agentRunDetailRefetchInterval,
  playgroundTraceRefetchInterval,
} from './hooks'
import type { Trace } from './types'

function trace(status: string): Trace {
  return {
    id: `trace-${status}`,
    project_id: 'project-1',
    status,
  }
}

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

describe('Playground Agent Run list polling policy', () => {
  it('does not poll while the current Run is already observed by SSE', () => {
    expect(playgroundTraceRefetchInterval([trace('running')], true)).toBe(false)
  })

  it('polls only while an active Run exists outside the owned SSE lifecycle', () => {
    expect(playgroundTraceRefetchInterval([trace('running')], false)).toBe(1_500)
  })

  it.each(['completed', 'failed', 'cancelled', 'timed_out', 'uncertain'])(
    'does not poll after %s becomes terminal',
    (status) => {
      expect(playgroundTraceRefetchInterval([trace(status)], false)).toBe(false)
    },
  )

  it('does not poll an empty Run list', () => {
    expect(playgroundTraceRefetchInterval([], false)).toBe(false)
  })
})
