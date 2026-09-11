import { describe, expect, it } from 'vitest'

import type { NetworkTurn } from './networkChatExecution'
import { reconcileNetworkTurns } from './networkTurnReconciliation'

function turn(id: string): NetworkTurn {
  return {
    id,
    user: id,
    answer: id,
    provider: 'test',
    model: 'test',
    usage: null,
    execution: {
      id,
      traceId: null,
      status: 'success',
      environment: 'draft',
      startedAt: '2026-07-15T00:00:00Z',
      durationMs: 1,
      costUsd: null,
      path: [],
      root: {
        spanId: id,
        runId: null,
        parentSpanId: null,
        sequence: 1,
        agentId: id,
        agentName: id,
        agentSessionId: null,
        contextState: 'stateless',
        previousInvocationCount: 0,
        childTraceId: null,
        source: 'draft',
        version: 'r1',
        status: 'success',
        tools: [],
        sources: [],
        children: [],
      },
    },
  }
}

describe('reconcileNetworkTurns', () => {
  it('keeps a live turn while the persisted query is still stale', () => {
    expect(reconcileNetworkTurns([], [turn('live')]).map((item) => item.id)).toEqual(['live'])
  })

  it('deduplicates a live turn once persistence returns the same execution', () => {
    expect(reconcileNetworkTurns([turn('run-1')], [turn('run-1')])).toHaveLength(1)
  })
})
