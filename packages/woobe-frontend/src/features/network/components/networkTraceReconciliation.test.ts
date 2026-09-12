import { describe, expect, it } from 'vitest'

import type { NetworkExecution } from './networkChatExecution'
import type { NetworkTraceRecord } from './networkObservabilityTypes'
import {
  persistedTraceSupersedesLocal,
  reconcileNetworkTraces,
} from './networkTraceReconciliation'

function trace(
  id: string,
  status: NetworkExecution['status'],
  source: NetworkTraceRecord['source'] = 'runtime',
  sessionId = 'session-1',
): NetworkTraceRecord {
  return {
    id,
    traceId: null,
    networkSessionId: sessionId,
    source,
    title: id,
    userMessage: id,
    answer: status === 'running' ? '' : `${status} answer`,
    environment: 'draft',
    networkVersion: 'Draft r1',
    compositionHash: 'hash',
    status,
    startedAt: '2026-09-11T03:00:00.000Z',
    completedAt: status === 'running' ? null : '2026-09-11T03:00:01.000Z',
    durationMs: status === 'running' ? 0 : 1000,
    usage: null,
    costUsd: null,
    agentContexts: [],
    execution: {
      id,
      traceId: null,
      status,
      environment: 'draft',
      startedAt: '2026-09-11T03:00:00.000Z',
      durationMs: status === 'running' ? 0 : 1000,
      costUsd: null,
      path: [],
      root: {
        spanId: id,
        runId: id,
        parentSpanId: null,
        sequence: 1,
        agentId: 'agent-1',
        agentName: 'Agent',
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
    events: [],
  }
}

describe('reconcileNetworkTraces', () => {
  it.each(['success', 'error', 'cancelled'] as const)(
    'keeps a local %s terminal trace while PostgreSQL still reports running',
    (status) => {
      const local = trace('run-1', status, 'chat')
      const persisted = trace('run-1', 'running')

      expect(persistedTraceSupersedesLocal(persisted, local)).toBe(false)
      const result = reconcileNetworkTraces([persisted], [local], 'session-1')

      expect(result).toHaveLength(1)
      expect(result[0]).toBe(local)
      expect(result[0].status).toBe(status)
    },
  )

  it('switches to the persisted trace after the read model reaches terminal', () => {
    const local = trace('run-1', 'success', 'chat')
    const persisted = trace('run-1', 'success', 'runtime')

    const result = reconcileNetworkTraces([persisted], [local], 'session-1')

    expect(result).toEqual([persisted])
  })

  it('preserves unmatched traces and traces from other sessions', () => {
    const running = trace('run-1', 'running')
    const unmatched = trace('run-2', 'success', 'chat')
    const otherSession = trace('run-3', 'success', 'chat', 'session-2')

    const result = reconcileNetworkTraces(
      [running],
      [unmatched, otherSession],
      'session-1',
    )

    expect(result.map((item) => item.id)).toEqual(['run-1', 'run-2', 'run-3'])
  })
})
