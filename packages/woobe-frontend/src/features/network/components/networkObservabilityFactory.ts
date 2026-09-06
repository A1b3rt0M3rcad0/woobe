import { operationEventLabel } from '@/features/skills/operations'
import type { UsageInfo } from '@/features/playground/types'

import type { AgentNodeId, Environment, NetworkBinding } from './networkWorkspaceTypes'
import { networkLabel, type NetworkAgentInvocation, type NetworkExecution, type RuntimeEventRecord } from './networkChatExecution'
import { executionCompletionTime, type NetworkTraceEvent, type NetworkTraceRecord, type NetworkTraceSource } from './networkObservabilityTypes'
import type { NetworkAgentContext } from './networkSessionTypes'

function aggregateUsage(root: NetworkAgentInvocation): UsageInfo | null {
  const usage = [root.usage, ...root.children.map(aggregateUsage)].filter((item): item is UsageInfo => item != null)
  if (!usage.length) return null
  const totals = usage.reduce<UsageInfo>((total, item) => ({
    input_tokens: (total.input_tokens ?? 0) + (item.input_tokens ?? 0),
    output_tokens: (total.output_tokens ?? 0) + (item.output_tokens ?? 0),
    total_tokens: (total.total_tokens ?? 0) + (item.total_tokens ?? 0),
    cost_usd: 0,
  }), { input_tokens: 0, output_tokens: 0, total_tokens: 0, cost_usd: 0 })
  totals.cost_usd = usage.every((item) => typeof item.cost_usd === 'number')
    ? usage.reduce((total, item) => total + (item.cost_usd ?? 0), 0)
    : null
  return totals
}

function runtimeTraceEvents(records: RuntimeEventRecord[]): NetworkTraceEvent[] {
  return records.map(({ eventType, event }, index) => ({
    id: event.event_id ?? `${event.execution_id}-${event.sequence ?? index}`,
    type: eventType,
    label: operationEventLabel(eventType.replace(/_/g, ' '), event.data),
    timestamp: event.created_at ?? '',
    sequence: event.sequence ?? index + 1,
    spanId: event.invocation_id,
    parentSpanId: event.parent_invocation_id,
    nodeId: event.node_id ?? undefined,
    status: eventType.includes('cancelled')
      ? 'cancelled'
      : eventType.includes('failed')
        ? 'error'
        : eventType.includes('started') || eventType.includes('accepted')
          ? 'running'
          : 'success',
    payload: event.data,
  }))
}

export function createNetworkTraceRecord({
  execution,
  environment,
  bindings: _bindings,
  networkSessionId,
  title,
  userMessage,
  answer,
  usage,
  agentContexts = [],
  parsedOutput,
  outputParseError,
  source = 'chat',
  runtimeEvents,
  networkVersion,
}: {
  execution: NetworkExecution
  environment: Environment
  bindings: Record<AgentNodeId, NetworkBinding>
  networkSessionId: string
  title: string
  userMessage: string
  answer: string
  usage?: UsageInfo | null
  agentContexts?: NetworkAgentContext[]
  parsedOutput?: Record<string, unknown> | null
  outputParseError?: string | null
  source?: NetworkTraceSource
  runtimeEvents?: RuntimeEventRecord[]
  networkVersion?: string
}): NetworkTraceRecord {
  const accepted = runtimeEvents?.find((record) => record.eventType === 'execution_accepted')?.event.data
  const acceptedVersion = typeof accepted?.network_version === 'string'
    ? networkLabel(environment, accepted.network_version)
    : environment === 'draft' && typeof accepted?.draft_revision === 'number'
      ? `Draft r${accepted.draft_revision}`
      : networkVersion ?? networkLabel(environment)
  const compositionHash = typeof accepted?.composition_hash === 'string'
    ? accepted.composition_hash
    : 'not available'

  return {
    id: execution.id,
    traceId: execution.traceId,
    networkSessionId,
    source,
    title,
    userMessage,
    answer,
    parsedOutput,
    outputParseError,
    environment: execution.environment,
    networkVersion: acceptedVersion,
    compositionHash,
    status: execution.status,
    startedAt: execution.startedAt,
    completedAt: executionCompletionTime(execution),
    durationMs: execution.durationMs,
    usage: usage ?? aggregateUsage(execution.root),
    costUsd: execution.costUsd,
    agentContexts,
    execution,
    events: runtimeEvents?.length ? runtimeTraceEvents(runtimeEvents) : [],
  }
}
