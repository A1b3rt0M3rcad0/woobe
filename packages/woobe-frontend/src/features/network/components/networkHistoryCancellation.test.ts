import { describe, expect, it } from 'vitest'

import type { NetworkExecutionHistoryResource, NetworkMessageResource } from '@/features/network/types'
import { hydrateNetworkHistory } from './networkHistory'
import type { NetworkSession } from './networkSessionTypes'
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

const session: NetworkSession = {
  id: 'session-1',
  projectId: 'project-1',
  networkId: 'network-1',
  title: 'Test',
  environment: 'draft',
  networkVersion: null,
  versionLabel: 'Draft r1',
  draftRevision: 1,
  compositionHash: 'hash',
  status: 'active',
  createdAt: '2026-08-28T12:00:00.000Z',
  lastMessageAt: '2026-08-28T12:00:01.000Z',
  messageCount: 1,
  traceCount: 1,
  agentContexts: [],
}

function cancelledExecution(): NetworkExecutionHistoryResource {
  return {
    id: 'execution-1',
    status: 'cancelled',
    draft_revision: 1,
    network_version_id: null,
    root_trace_id: null,
    failure_code: null,
    failure: {
      code: 'execution_stopped',
      stage: 'provider_request',
      message: 'The Agent Run failed before producing a valid result.',
      retryable: false,
    },
    started_at: '2026-08-28T12:00:00.000Z',
    completed_at: '2026-08-28T12:00:01.000Z',
    events: [
      {
        id: 'event-1',
        sequence: 1,
        event_type: 'execution_cancelled',
        invocation_id: null,
        parent_invocation_id: null,
        node_id: null,
        agent_id: null,
        depth: null,
        data: {},
        created_at: '2026-08-28T12:00:01.000Z',
      },
    ],
  }
}

describe('Network persisted cancellation history', () => {
  it('does not hydrate failure text as an Assistant answer for a cancelled execution', () => {
    const messages: NetworkMessageResource[] = [
      {
        id: 'message-user',
        network_execution_id: 'execution-1',
        role: 'user',
        content: 'stop this run',
        data: null,
        created_at: '2026-08-28T12:00:00.000Z',
        execution: cancelledExecution(),
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
    expect(result.turns[0].execution.status).toBe('cancelled')
    expect(result.turns[0].answer).toBe('')
  })

  it('preserves a persisted partial Assistant answer for a cancelled execution', () => {
    const execution = cancelledExecution()
    const messages: NetworkMessageResource[] = [
      {
        id: 'message-user',
        network_execution_id: 'execution-1',
        role: 'user',
        content: 'stop this run',
        data: null,
        created_at: '2026-08-28T12:00:00.000Z',
        execution,
      },
      {
        id: 'message-assistant',
        network_execution_id: 'execution-1',
        role: 'assistant',
        content: 'partial answer that was already public',
        data: { cancelled: true, partial: true },
        created_at: '2026-08-28T12:00:00.900Z',
        execution,
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
    expect(result.turns[0].execution.status).toBe('cancelled')
    expect(result.turns[0].answer).toBe('partial answer that was already public')
  })
})
