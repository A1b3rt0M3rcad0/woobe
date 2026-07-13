import type { AgentNodeId, NetworkBinding } from './networkWorkspaceTypes'
import { makeExecution } from './networkChatExecution'
import { createNetworkTraceRecord } from './networkObservabilityFactory'
import type { NetworkTraceRecord } from './networkObservabilityTypes'

function withTimestamp(
  record: NetworkTraceRecord,
  minutesAgo: number,
): NetworkTraceRecord {
  const startedAt = new Date(Date.now() - minutesAgo * 60_000).toISOString()
  const delta =
    new Date(startedAt).getTime() - new Date(record.startedAt).getTime()
  return {
    ...record,
    startedAt,
    completedAt: record.completedAt
      ? new Date(
          new Date(record.completedAt).getTime() + delta,
        ).toISOString()
      : null,
    execution: { ...record.execution, startedAt },
    events: record.events.map((event) => ({
      ...event,
      timestamp: new Date(
        new Date(event.timestamp).getTime() + delta,
      ).toISOString(),
    })),
  }
}

function forceIdentity(
  record: NetworkTraceRecord,
  id: string,
  traceId: string,
): NetworkTraceRecord {
  return {
    ...record,
    id,
    traceId,
    execution: { ...record.execution, id, traceId },
  }
}

export function createMockNetworkTraces({
  draft,
  staging,
  production,
  currentSessionId,
}: {
  draft: Record<AgentNodeId, NetworkBinding>
  staging: Record<AgentNodeId, NetworkBinding>
  production: Record<AgentNodeId, NetworkBinding>
  currentSessionId: string
}): NetworkTraceRecord[] {
  const invoiceResult = makeExecution(
    'I need help with an invoice that was charged twice.',
    'production',
    production,
  )
  const invoice = forceIdentity(
    withTimestamp(
      createNetworkTraceRecord({
        execution: invoiceResult.execution,
        target: 'production',
        bindings: production,
        sessionId: currentSessionId,
        title: 'Duplicate invoice investigation',
        userMessage:
          'I need help with an invoice that was charged twice.',
        answer: invoiceResult.answer,
        source: 'chat',
      }),
      7,
    ),
    'network-trace-invoice',
    'f1bdbf93-1f5b-46c6-9880-2e5b81d92e11',
  )

  const passwordResult = makeExecution(
    'I need help resetting a password after repeated login errors.',
    'staging',
    staging,
  )
  const password = forceIdentity(
    withTimestamp(
      createNetworkTraceRecord({
        execution: passwordResult.execution,
        target: 'staging',
        bindings: staging,
        sessionId: 'network-session-previous',
        title: 'Password reset guidance',
        userMessage:
          'I need help resetting a password after repeated login errors.',
        answer: passwordResult.answer,
        source: 'runtime',
      }),
      68,
    ),
    'network-trace-password',
    '67fb899a-b44e-4dda-9ce4-2750fd69c181',
  )

  const errorResult = makeExecution(
    'The public API is returning a 504 timeout.',
    'draft',
    draft,
  )
  const failedInvocation = errorResult.execution.root.children[0]
  if (failedInvocation) {
    failedInvocation.status = 'error'
    failedInvocation.output =
      'The service status provider did not respond before the Tool timeout.'
    failedInvocation.tools = failedInvocation.tools.map((tool) => ({
      ...tool,
      status: 'error',
      success: false,
      output: null,
      error: 'Gateway timeout from the service-status provider',
    }))
  }
  errorResult.execution.status = 'error'
  errorResult.execution.durationMs = 730
  errorResult.execution.costUsd = 0.004
  errorResult.execution.path = ['entry', 'coordinator', 'technical']
  const failed = forceIdentity(
    withTimestamp(
      createNetworkTraceRecord({
        execution: errorResult.execution,
        target: 'draft',
        bindings: draft,
        sessionId: currentSessionId,
        title: 'API timeout investigation',
        userMessage: 'The public API is returning a 504 timeout.',
        answer:
          'The Network stopped after the service-status Tool timed out.',
        source: 'chat',
      }),
      21,
    ),
    'network-trace-timeout',
    '92a3589e-b7f1-49ec-88d7-cb2558f43144',
  )

  return [invoice, failed, password].sort(
    (left, right) =>
      new Date(right.startedAt).getTime() -
      new Date(left.startedAt).getTime(),
  )
}
