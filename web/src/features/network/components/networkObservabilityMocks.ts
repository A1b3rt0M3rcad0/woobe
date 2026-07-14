import type { AgentNodeId, NetworkBinding } from './networkWorkspaceTypes'
import { makeExecution } from './networkChatExecution'
import { createNetworkTraceRecord } from './networkObservabilityFactory'
import type { NetworkTraceRecord } from './networkObservabilityTypes'
import type { NetworkSessionsByEnvironment } from './networkSessionTypes'

function withTimestamp(
  record: NetworkTraceRecord,
  minutesAgo: number,
): NetworkTraceRecord {
  const startedAt = new Date(Date.now() - minutesAgo * 60_000).toISOString()
  const delta = new Date(startedAt).getTime() - new Date(record.startedAt).getTime()
  return {
    ...record,
    startedAt,
    completedAt: record.completedAt
      ? new Date(new Date(record.completedAt).getTime() + delta).toISOString()
      : null,
    execution: { ...record.execution, startedAt },
    events: record.events.map((event) => ({
      ...event,
      timestamp: new Date(new Date(event.timestamp).getTime() + delta).toISOString(),
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

function createTrace({
  message,
  environment,
  bindings,
  sessionId,
  contexts,
  title,
  minutesAgo,
  id,
  traceId,
  source = 'chat',
}: {
  message: string
  environment: 'draft' | 'staging' | 'production'
  bindings: Record<AgentNodeId, NetworkBinding>
  sessionId: string
  contexts: NetworkSessionsByEnvironment['draft'][number]['agentContexts']
  title: string
  minutesAgo: number
  id: string
  traceId: string
  source?: 'chat' | 'runtime'
}) {
  const result = makeExecution(message, environment, bindings, sessionId, contexts)
  return forceIdentity(
    withTimestamp(
      createNetworkTraceRecord({
        execution: result.execution,
        environment,
        bindings,
        networkSessionId: sessionId,
        title,
        userMessage: message,
        answer: result.answer,
        usage: result.usage,
        agentContexts: result.agentContexts,
        parsedOutput: result.parsedOutput,
        source,
      }),
      minutesAgo,
    ),
    id,
    traceId,
  )
}

export function createMockNetworkTraces({
  draft,
  staging,
  production,
  sessions,
}: {
  draft: Record<AgentNodeId, NetworkBinding>
  staging: Record<AgentNodeId, NetworkBinding>
  production: Record<AgentNodeId, NetworkBinding>
  sessions: NetworkSessionsByEnvironment
}): NetworkTraceRecord[] {
  const draftSession = sessions.draft[0]
  const stagingSession = sessions.staging[0]
  const productionSession = sessions.production[0]

  const invoice = createTrace({
    message: 'I need help with an invoice that was charged twice.',
    environment: 'production',
    bindings: production,
    sessionId: productionSession.id,
    contexts: productionSession.agentContexts,
    title: 'Duplicate invoice investigation',
    minutesAgo: 7,
    id: 'network-trace-invoice',
    traceId: 'f1bdbf93-1f5b-46c6-9880-2e5b81d92e11',
  })

  const refund = createTrace({
    message: 'Can this duplicated payment be refunded automatically?',
    environment: 'production',
    bindings: production,
    sessionId: productionSession.id,
    contexts: invoice.agentContexts,
    title: 'Refund eligibility check',
    minutesAgo: 5,
    id: 'network-trace-refund',
    traceId: 'a4d29c82-12c7-4bc7-9f11-24d786c5310f',
  })

  const password = createTrace({
    message: 'I need help resetting a password after repeated login errors.',
    environment: 'staging',
    bindings: staging,
    sessionId: stagingSession.id,
    contexts: stagingSession.agentContexts,
    title: 'Password reset validation',
    minutesAgo: 68,
    id: 'network-trace-password',
    traceId: '67fb899a-b44e-4dda-9ce4-2750fd69c181',
    source: 'runtime',
  })

  const timeout = createTrace({
    message: 'The public API is returning a 504 timeout.',
    environment: 'draft',
    bindings: draft,
    sessionId: draftSession.id,
    contexts: draftSession.agentContexts,
    title: 'API timeout investigation',
    minutesAgo: 21,
    id: 'network-trace-timeout',
    traceId: '92a3589e-b7f1-49ec-88d7-cb2558f43144',
  })
  const failedInvocation = timeout.execution.root.children[0]
  if (failedInvocation) {
    failedInvocation.status = 'error'
    failedInvocation.output = 'The service status provider did not respond before the Tool timeout.'
    failedInvocation.tools = failedInvocation.tools.map((tool) => ({
      ...tool,
      status: 'error',
      success: false,
      output: null,
      error: 'Gateway timeout from the service-status provider',
    }))
  }
  timeout.execution.status = 'error'
  timeout.status = 'error'
  timeout.execution.durationMs = 730
  timeout.durationMs = 730
  timeout.execution.costUsd = 0.004
  timeout.costUsd = 0.004
  timeout.execution.path = ['entry', 'coordinator', 'technical']

  const incident = createTrace({
    message: 'Check whether the timeout is limited to one region.',
    environment: 'draft',
    bindings: draft,
    sessionId: draftSession.id,
    contexts: timeout.agentContexts,
    title: 'Regional incident classification',
    minutesAgo: 18,
    id: 'network-trace-incident',
    traceId: 'bcf055d8-ae97-4a65-94b7-d439814d3a61',
  })

  return [refund, invoice, incident, timeout, password].sort(
    (left, right) => new Date(right.startedAt).getTime() - new Date(left.startedAt).getTime(),
  )
}
