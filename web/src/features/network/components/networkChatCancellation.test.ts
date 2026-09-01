import { describe, expect, it } from 'vitest'

import { buildTurnFromRuntimeEvents, type RuntimeEventRecord } from './networkChatExecution'
import type { NetworkBinding } from './networkWorkspaceTypes'

const binding = {
  nodeId: 'node-root',
  agent: {
    id: 'agent-root',
    name: 'Root Agent',
    provider: 'custom',
    model: 'test-model',
  },
  source: 'draft',
  ref: 'agent-root',
  version: 'r1',
  draftVersion: 'r1',
  dirty: false,
} as NetworkBinding

function failedThenTerminal(terminal: 'execution_cancelled' | 'execution_failed'): RuntimeEventRecord[] {
  return [
    {
      eventType: 'agent_invocation_started',
      event: {
        protocol_version: 1,
        execution_id: 'execution-1',
        invocation_id: 'root',
        parent_invocation_id: null,
        node_id: 'node-root',
        agent_id: 'agent-root',
        depth: 0,
        sequence: 1,
        created_at: '2026-08-28T12:00:00.000Z',
        data: { label: 'Root Agent' },
      },
    },
    {
      eventType: 'agent_invocation_failed',
      event: {
        protocol_version: 1,
        execution_id: 'execution-1',
        invocation_id: 'root',
        parent_invocation_id: null,
        node_id: 'node-root',
        agent_id: 'agent-root',
        depth: 0,
        sequence: 2,
        created_at: '2026-08-28T12:00:01.000Z',
        data: {
          code: 'execution_stopped',
          stage: 'provider_request',
          message: 'The Agent Run failed before producing a valid result.',
          retryable: false,
        },
      },
    },
    {
      eventType: terminal,
      event: {
        protocol_version: 1,
        execution_id: 'execution-1',
        sequence: 3,
        created_at: '2026-08-28T12:00:01.100Z',
        data: {},
      },
    },
  ]
}

describe('Network cancellation presentation', () => {
  it('does not turn a cancelled empty result into failure copy', () => {
    const turn = buildTurnFromRuntimeEvents({
      records: failedThenTerminal('execution_cancelled'),
      environment: 'draft',
      bindings: { 'node-root': binding },
      executionId: 'execution-1',
      user: 'stop this',
      answer: '',
      terminalStatus: 'cancelled',
    })

    expect(turn.execution.status).toBe('cancelled')
    expect(turn.answer).toBe('')
  })

  it('still exposes causal failure copy for a failed execution', () => {
    const turn = buildTurnFromRuntimeEvents({
      records: failedThenTerminal('execution_failed'),
      environment: 'draft',
      bindings: { 'node-root': binding },
      executionId: 'execution-1',
      user: 'run this',
      answer: '',
      terminalStatus: 'error',
    })

    expect(turn.execution.status).toBe('error')
    expect(turn.answer).toContain('failed before producing')
  })
})
