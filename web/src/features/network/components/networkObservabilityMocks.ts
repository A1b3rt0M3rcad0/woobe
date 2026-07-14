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

function failTimeoutTrace(record: NetworkTraceRecord): NetworkTraceRecord {
  const failureMessage = 'Gateway timeout from the service-status provider'
  const failedInvocation = record.execution.root.children[0]
  if (!failedInvocation) return record

  const failedSpanId = failedInvocation.spanId
  const failedRoot = {
    ...record.execution.root,
    children: record.execution.root.children.map((invocation) => invocation.spanId === failedSpanId
      ? {
          ...invocation,
          status: 'error' as const,
          output: 'The service status provider did not respond before the Tool timeout.',
          tools: invocation.tools.map((tool) => ({
            ...tool,
            status: 'error',
            success: false,
            output: null,
            error: failureMessage,
          })),
        }
      : invocation),
  }

  const events = record.events.map((event) => {
    if (event.spanId === failedSpanId && event.type === 'network.tool.call.completed') {
      return {
        ...event,
        type: 'network.tool.call.failed',
        label: `${String(event.payload.tool_name ?? 'Tool')} failed`,
        status: 'error' as const,
        payload: {
          ...event.payload,
          success: false,
          output: null,
          error: failureMessage,
        },
      }
    }
    if (event.spanId === failedSpanId && event.type === 'network.agent.invocation.completed') {
      return {
        ...event,
        type: 'network.agent.invocation.failed',
        label: `${failedInvocation.agentName} failed`,
        status: 'error' as const,
        payload: {
          ...event.payload,
          output: 'The service status provider did not respond before the Tool timeout.',
          error: failureMessage,
        },
      }
    }
    if (event.type === 'network.execution.completed') {
      return {
        ...event,
        type: 'network.execution.failed',
        label: 'Network execution failed',
        nodeId: 'technical' as const,
        status: 'error' as const,
        payload: {
          ...event.payload,
          duration_ms: 730,
          cost_usd: 0.004,
          error: failureMessage,
        },
      }
    }
    return event
  })

  return {
    ...record,
    answer: 'The Network stopped after the service-status Tool timed out.',
    status: 'error',
    durationMs: 730,
    costUsd: 0.004,
    execution: {
      ...record.execution,
      status: 'error',
      durationMs: 730,
      costUsd: 0.004,
      path: ['entry', 'coordinator', 'technical'],
      root: failedRoot,
    },
    events,
  }
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

  const timeout = failTimeoutTrace(createTrace({
    message: 'The public API is returning a 504 timeout.',
    environment: 'draft',
    bindings: draft,
    sessionId: draftSession.id,
    contexts: draftSession.agentContexts,
    title: 'API timeout investigation',
    minutesAgo: 21,
    id: 'network-trace-timeout',
    traceId: '92a3589e-b7f1-49ec-88d7-cb2558f43144',
  }))

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
