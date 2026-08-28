import type { NetworkMessageResource } from '@/features/network/types'

import { buildTurnFromRuntimeEvents, type NetworkAgentInvocation, type NetworkExecution, type NetworkTurn, type RuntimeEventRecord } from './networkChatExecution'
import { createNetworkTraceRecord } from './networkObservabilityFactory'
import type { NetworkTraceRecord } from './networkObservabilityTypes'
import type { NetworkAgentContext, NetworkSession } from './networkSessionTypes'
import type { AgentNodeId, Environment, NetworkBinding } from './networkWorkspaceTypes'

function historyRecords(message: NetworkMessageResource, sessionId: string): RuntimeEventRecord[] {
  const execution = message.execution
  if (!execution) return []
  return execution.events.map((item) => ({
    eventType: item.event_type,
    event: {
      protocol_version: 1,
      event_id: item.id,
      sequence: item.sequence,
      execution_id: execution.id,
      network_session_id: sessionId,
      invocation_id: item.invocation_id,
      parent_invocation_id: item.parent_invocation_id,
      node_id: item.node_id,
      agent_id: item.agent_id,
      depth: item.depth,
      data: item.data,
      created_at: item.created_at,
    },
  }))
}

function terminalStatus(status: string): NetworkExecution['status'] {
  if (status === 'completed') return 'success'
  if (status === 'running' || status === 'queued') return 'running'
  if (status === 'cancelled') return 'cancelled'
  return 'error'
}

function invocationContexts(root: NetworkAgentInvocation, session: NetworkSession): NetworkAgentContext[] {
  const byNode = new Map<string, NetworkAgentContext>()
  const visit = (invocation: NetworkAgentInvocation) => {
    if (invocation.nodeId) {
      const existing = byNode.get(invocation.nodeId)
      const invokedAt = invocation.completedAt
        ?? invocation.startedAt
        ?? session.lastMessageAt
        ?? session.createdAt
      const invocationMessageCount = invocation.contextState === 'stateless'
        ? 0
        : 1 + (invocation.output != null ? 1 : 0)
      byNode.set(invocation.nodeId, {
        id: existing?.id ?? `${session.id}:${invocation.nodeId}`,
        networkSessionId: session.id,
        nodeId: invocation.nodeId,
        agentId: invocation.agentId,
        agentName: invocation.agentName,
        sessionMode: invocation.contextState === 'stateless' ? 'stateless' : 'stateful',
        agentSessionId: invocation.agentSessionId ?? existing?.agentSessionId ?? null,
        source: invocation.source,
        version: invocation.version,
        invocationCount: (existing?.invocationCount ?? 0) + 1,
        messageCount: (existing?.messageCount ?? 0) + invocationMessageCount,
        createdAt: existing?.createdAt ?? invokedAt,
        lastInvokedAt: invokedAt,
      })
    }
    invocation.children.forEach(visit)
  }
  visit(root)
  return [...byNode.values()]
}

export interface HydratedNetworkHistory {
  turns: NetworkTurn[]
  traces: NetworkTraceRecord[]
}

export function hydrateNetworkHistory({ messages, environment, bindings, session, versionLabel }: { messages: NetworkMessageResource[]; environment: Environment; bindings: Record<AgentNodeId, NetworkBinding>; session: NetworkSession; versionLabel: string }): HydratedNetworkHistory {
  type HistoryGroup = { user?: NetworkMessageResource; assistant?: NetworkMessageResource; executionMessage?: NetworkMessageResource }
  const grouped = new Map<string, HistoryGroup>()
  for (const message of messages) {
    const executionId = message.network_execution_id
    if (!executionId) continue
    const current = grouped.get(executionId) ?? {}
    if (message.role === 'user') current.user = message
    if (message.role === 'assistant') current.assistant = message
    if (message.execution) current.executionMessage = message
    grouped.set(executionId, current)
  }

  const turns: NetworkTurn[] = []
  const traces: NetworkTraceRecord[] = []
  for (const [executionId, group] of grouped.entries()) {
    const source = group.assistant?.execution ? group.assistant : group.executionMessage
    if (!source?.execution) continue
    const records = historyRecords(source, session.id)
    const user = group.user?.content ?? ''
    const answer = group.assistant?.content
      ?? (source.execution.status === 'cancelled' ? '' : source.execution.failure?.message ?? '')
    const turn = buildTurnFromRuntimeEvents({ records, environment, bindings, executionId, user, answer, fallbackTraceId: source.execution.root_trace_id ?? undefined, terminalStatus: terminalStatus(source.execution.status) })
    const contexts = session.agentContexts.length ? session.agentContexts : invocationContexts(turn.execution.root, session)
    turns.push(turn)
    traces.push(createNetworkTraceRecord({ execution: turn.execution, environment, bindings, networkSessionId: session.id, title: user || 'Network Run', userMessage: user, answer: turn.answer, usage: turn.usage, agentContexts: contexts, parsedOutput: turn.parsedOutput, outputParseError: turn.outputParseError, source: 'runtime', runtimeEvents: records, networkVersion: versionLabel }))
  }
  return { turns, traces }
}
