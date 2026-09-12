import { describe, expect, it } from 'vitest'

import type { NetworkExecution, NetworkTurn } from './networkChatExecution'
import {
  persistedTurnSupersedesLocal,
  reconcileNetworkTurns,
} from './networkTurnReconciliation'

function turn(
  id: string,
  status: NetworkExecution['status'] = 'success',
  answer = id,
): NetworkTurn {
  return {
    id,
    user: id,
    answer,
    provider: 'test',
    model: 'test',
    usage: null,
    execution: {
      id,
      traceId: null,
      status,
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
        status: status === 'error' ? 'error' : status === 'cancelled' ? 'cancelled' : status,
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

  it('keeps the terminal local turn while PostgreSQL still reports the same execution as running', () => {
    const result = reconcileNetworkTurns(
      [turn('run-1', 'running', '')],
      [turn('run-1', 'success', 'durable stream answer')],
    )

    expect(result).toHaveLength(1)
    expect(result[0].execution.status).toBe('success')
    expect(result[0].answer).toBe('durable stream answer')
  })

  it.each(['success', 'error', 'cancelled'] as const)(
    'does not let stale running SQL replace a local %s terminal outcome',
    (status) => {
      expect(
        persistedTurnSupersedesLocal(
          turn('run-1', 'running'),
          turn('run-1', status),
        ),
      ).toBe(false)
    },
  )

  it('switches back to the persisted turn once PostgreSQL reaches a terminal outcome', () => {
    const result = reconcileNetworkTurns(
      [turn('run-1', 'success', 'projected answer')],
      [turn('run-1', 'success', 'stream answer')],
    )

    expect(result).toHaveLength(1)
    expect(result[0].answer).toBe('projected answer')
    expect(persistedTurnSupersedesLocal(result[0], turn('run-1'))).toBe(true)
  })
})
