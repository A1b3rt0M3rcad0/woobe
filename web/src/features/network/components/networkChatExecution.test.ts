import { describe, expect, it } from 'vitest'

import {
  buildTurnFromRuntimeEvents,
  currentSignature,
  networkLabel,
  type RuntimeEventRecord,
} from './networkChatExecution'
import type { NetworkBinding } from './networkWorkspaceTypes'

const binding = {
  nodeId: 'node-root',
  agent: {
    id: 'agent-root',
    name: 'Root Agent',
    provider: 'openai',
    model: 'gpt-test',
  },
  source: 'draft',
  ref: 'agent-root',
  version: 'r7',
  draftVersion: 'r7',
  dirty: false,
} as NetworkBinding

describe('Network runtime event projection', () => {
  it('builds a real invocation tree from SSE events', () => {
    const records: RuntimeEventRecord[] = [
      {
        eventType: 'agent_invocation_started',
        event: {
          protocol_version: 1,
          execution_id: 'execution-1',
          invocation_id: 'invocation-1',
          parent_invocation_id: null,
          node_id: 'node-root',
          agent_id: 'agent-root',
          depth: 0,
          data: { label: 'Root Agent' },
          sequence: 2,
          created_at: '2026-07-14T10:00:00.000Z',
        },
      },
      {
        eventType: 'agent_invocation_completed',
        event: {
          protocol_version: 1,
          execution_id: 'execution-1',
          invocation_id: 'invocation-1',
          parent_invocation_id: null,
          node_id: 'node-root',
          agent_id: 'agent-root',
          depth: 0,
          data: {
            trace_id: 'trace-1',
            output: 'answer',
            provider: 'openai',
            model: 'gpt-test',
            usage: { input_tokens: 5, output_tokens: 3, total_tokens: 8, cost_usd: 0.01 },
          },
          sequence: 3,
          created_at: '2026-07-14T10:00:00.500Z',
        },
      },
    ]

    const turn = buildTurnFromRuntimeEvents({
      records,
      environment: 'draft',
      bindings: { 'node-root': binding },
      executionId: 'execution-1',
      user: 'hello',
      answer: 'answer',
    })

    expect(turn.execution.root.agentName).toBe('Root Agent')
    expect(turn.execution.root.output).toBe('answer')
    expect(turn.execution.path).toEqual(['entry', 'node-root', 'end'])
    expect(turn.usage.total_tokens).toBe(8)
    expect(turn.execution.traceId).toBe('trace-1')
  })

  it('signs any dynamic node ids without fixed roles', () => {
    expect(currentSignature('draft', { 'node-root': binding })).toContain('node-root')
    expect(currentSignature('draft', { 'node-root': binding })).not.toContain('billing')
    expect(networkLabel('draft', 7)).toBe('Draft r7')
  })
})
