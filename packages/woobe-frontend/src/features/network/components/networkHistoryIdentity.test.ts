import { describe, expect, it } from 'vitest'

import type { NetworkExecutionHistoryResource, NetworkMessageResource } from '@/features/network/types'
import { hydrateNetworkHistory } from './networkHistory'
import type { NetworkSession } from './networkSessionTypes'
import type { NetworkBinding } from './networkWorkspaceTypes'

const invocationId = '01993dc0-7a4a-7000-8000-000000000001'

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

const session: NetworkSession = {
  id: 'session-1',
  projectId: 'project-1',
  networkId: 'network-1',
  title: 'History identity',
  environment: 'draft',
  networkVersion: null,
  versionLabel: 'Draft r1',
  draftRevision: 1,
  compositionHash: 'hash',
  status: 'active',
  createdAt: '2026-09-11T03:20:00.000Z',
  lastMessageAt: '2026-09-11T03:20:01.000Z',
  messageCount: 2,
  traceCount: 1,
  agentContexts: [],
}

function execution(): NetworkExecutionHistoryResource {
  return {
    id: 'execution-1',
    status: 'completed',
    draft_revision: 1,
    network_version_id: null,
    root_trace_id: 'trace-root',
    failure_code: null,
    failure: null,
    started_at: '2026-09-11T03:20:00.000Z',
    completed_at: '2026-09-11T03:20:01.000Z',
    events: [
      {
        id: 'event-started',
        sequence: 1,
        event_type: 'agent_invocation_started',
        invocation_id: invocationId,
        parent_invocation_id: null,
        node_id: 'node-root',
        agent_id: 'agent-root',
        depth: 0,
        // Legacy SQL history written before Agent Run identity became explicit.
        data: {
          label: 'Root Agent',
          source: 'draft',
          version: 'r1',
          provider: 'custom',
          model: 'test-model',
        },
        created_at: '2026-09-11T03:20:00.000Z',
      },
      {
        id: 'event-completed',
        sequence: 2,
        event_type: 'agent_invocation_completed',
        invocation_id: invocationId,
        parent_invocation_id: null,
        node_id: 'node-root',
        agent_id: 'agent-root',
        depth: 0,
        data: {
          trace_id: 'trace-root',
          output: 'done',
          usage: {
            input_tokens: 3,
            output_tokens: 2,
            total_tokens: 5,
            cost_usd: 0.001,
          },
        },
        created_at: '2026-09-11T03:20:01.000Z',
      },
      {
        id: 'event-terminal',
        sequence: 3,
        event_type: 'execution_completed',
        invocation_id: null,
        parent_invocation_id: null,
        node_id: null,
        agent_id: null,
        depth: null,
        data: { trace_id: 'trace-root' },
        created_at: '2026-09-11T03:20:01.000Z',
      },
    ],
  }
}

describe('Network persisted Agent Run identity', () => {
  it('reconstructs the canonical Agent Run id from legacy invocation history after reload', () => {
    const persisted = execution()
    const messages: NetworkMessageResource[] = [
      {
        id: 'message-user',
        network_execution_id: persisted.id,
        role: 'user',
        content: 'hello',
        data: null,
        created_at: persisted.started_at!,
        execution: persisted,
      },
      {
        id: 'message-assistant',
        network_execution_id: persisted.id,
        role: 'assistant',
        content: 'done',
        data: null,
        created_at: persisted.completed_at!,
        execution: persisted,
      },
    ]

    const result = hydrateNetworkHistory({
      messages,
      environment: 'draft',
      bindings: { 'node-root': binding },
      session,
      versionLabel: 'Draft r1',
    })

    expect(result.turns).toHaveLength(1)
    expect(result.turns[0].execution.root.spanId).toBe(invocationId)
    expect(result.turns[0].execution.root.runId).toBe(invocationId)
    expect(result.traces[0].execution.root.runId).toBe(invocationId)
  })
})
