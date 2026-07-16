import type { UsageInfo } from '@/features/playground/types'

import type {
  AgentNodeId,
  Environment,
  NetworkBinding,
} from './networkWorkspaceTypes'
import {
  currentSignature,
  networkLabel,
  type NetworkAgentInvocation,
  type NetworkExecution,
} from './networkChatExecution'
import {
  executionCompletionTime,
  hashComposition,
  type NetworkTraceEvent,
  type NetworkTraceEventStatus,
  type NetworkTraceRecord,
  type NetworkTraceSource,
} from './networkObservabilityTypes'
import type { NetworkAgentContext } from './networkSessionTypes'

function invocationEvents(
  root: NetworkAgentInvocation,
  startedAt: string,
  initialSequence: number,
) {
  const events: NetworkTraceEvent[] = []
  let sequence = initialSequence
  const base = new Date(startedAt).getTime()

  const push = (
    type: string,
    label: string,
    invocation: NetworkAgentInvocation,
    status: NetworkTraceEventStatus,
    payload: Record<string, unknown>,
  ) => {
    sequence += 1
    events.push({
      id: `${invocation.spanId}-${sequence}`,
      type,
      label,
      timestamp: new Date(base + sequence * 83).toISOString(),
      sequence,
      spanId: invocation.spanId,
      parentSpanId: invocation.parentSpanId,
      nodeId: invocation.nodeId,
      status,
      payload,
    })
  }

  const visit = (invocation: NetworkAgentInvocation) => {
    push(
      'network.agent.context.resolved',
      `${invocation.agentName} context ${invocation.contextState}`,
      invocation,
      'success',
      {
        node_id: invocation.nodeId,
        agent_id: invocation.agentId,
        agent_session_id: invocation.agentSessionId,
        session_mode: invocation.contextState === 'stateless' ? 'stateless' : 'stateful',
        resolution: invocation.contextState,
        previous_invocations: invocation.previousInvocationCount,
      },
    )
    push(
      'network.agent.invocation.started',
      `${invocation.agentName} started`,
      invocation,
      'running',
      {
        agent_id: invocation.agentId,
        node_id: invocation.nodeId,
        source: invocation.source,
        version: invocation.version,
        provider: invocation.provider,
        model: invocation.model,
        input: invocation.input,
      },
    )

    for (const tool of invocation.tools) {
      const failed =
        tool.success === false ||
        tool.status === 'failed' ||
        tool.status === 'error'
      push(
        failed ? 'network.tool.call.failed' : 'network.tool.call.completed',
        `${tool.tool_name} ${failed ? 'failed' : 'completed'}`,
        invocation,
        failed ? 'error' : 'success',
        {
          tool_call_id: tool.tool_call_id,
          tool_name: tool.tool_name,
          duration_ms: tool.duration_ms,
          input: tool.input,
          output: tool.output,
          error: tool.error,
        },
      )
    }

    if (invocation.sources.length > 0) {
      push(
        'network.knowledge.sources.retrieved',
        `${invocation.sources.length} source${invocation.sources.length === 1 ? '' : 's'} retrieved`,
        invocation,
        'success',
        { sources: invocation.sources },
      )
    }

    for (const child of invocation.children) {
      push(
        'network.route.evaluated',
        `Route evaluated for ${child.agentName}`,
        invocation,
        'success',
        {
          route_key: child.nodeId,
          candidate_node: child.nodeId,
          selected: true,
          confidence: child.nodeId === 'billing' ? 0.96 : 0.92,
        },
      )
      push(
        'network.route.selected',
        `${child.agentName} selected`,
        invocation,
        'success',
        {
          selected_node: child.nodeId,
          child_span_id: child.spanId,
          child_trace_id: child.childTraceId,
          reason: `Request matched the ${child.nodeId ?? 'specialist'} route`,
        },
      )
      visit(child)
    }

    const failed = invocation.status === 'error'
    push(
      failed ? 'network.agent.invocation.failed' : 'network.agent.invocation.completed',
      `${invocation.agentName} ${failed ? 'failed' : 'completed'}`,
      invocation,
      failed ? 'error' : 'success',
      {
        duration_ms: invocation.durationMs,
        usage: invocation.usage,
        cost_usd: invocation.costUsd,
        output: invocation.output,
        output_parse_error: invocation.outputParseError,
        child_trace_id: invocation.childTraceId,
      },
    )
  }

  visit(root)
  return { events, lastSequence: sequence }
}

function aggregateUsage(root: NetworkAgentInvocation): UsageInfo {
  const childUsage = root.children.map(aggregateUsage)
  return {
    input_tokens: (root.usage?.input_tokens ?? 0) + childUsage.reduce((total, item) => total + (item.input_tokens ?? 0), 0),
    output_tokens: (root.usage?.output_tokens ?? 0) + childUsage.reduce((total, item) => total + (item.output_tokens ?? 0), 0),
    total_tokens: (root.usage?.total_tokens ?? 0) + childUsage.reduce((total, item) => total + (item.total_tokens ?? 0), 0),
    cost_usd: (root.costUsd ?? 0) + childUsage.reduce((total, item) => total + (item.cost_usd ?? 0), 0),
  }
}

export function createNetworkTraceRecord({
  execution,
  environment,
  bindings,
  networkSessionId,
  title,
  userMessage,
  answer,
  usage,
  agentContexts = [],
  parsedOutput,
  outputParseError,
  source = 'chat',
}: {
  execution: NetworkExecution
  environment: Environment
  bindings: Record<AgentNodeId, NetworkBinding>
  networkSessionId: string
  title: string
  userMessage: string
  answer: string
  usage?: UsageInfo
  agentContexts?: NetworkAgentContext[]
  parsedOutput?: Record<string, unknown> | null
  outputParseError?: string | null
  source?: NetworkTraceSource
}): NetworkTraceRecord {
  const startedAt = execution.startedAt
  const startEvent: NetworkTraceEvent = {
    id: `${execution.id}-start`,
    type: 'network.execution.started',
    label: 'Network execution started',
    timestamp: startedAt,
    sequence: 1,
    nodeId: 'entry',
    status: 'running',
    payload: {
      environment,
      network_version: networkLabel(environment),
      network_session_id: networkSessionId,
      message: userMessage,
      max_hops: 8,
      timeout_seconds: 90,
    },
  }
  const enteredEvent: NetworkTraceEvent = {
    id: `${execution.id}-entry`,
    type: 'network.node.entered',
    label: 'ENTRY accepted request',
    timestamp: new Date(new Date(startedAt).getTime() + 42).toISOString(),
    sequence: 2,
    nodeId: 'entry',
    status: 'success',
    payload: { node_id: 'entry' },
  }
  const invocation = invocationEvents(execution.root, startedAt, 2)
  const finalSequence = invocation.lastSequence + 1
  const lastPathNode = execution.path[execution.path.length - 1]
  const finalEvent: NetworkTraceEvent = {
    id: `${execution.id}-final`,
    type:
      execution.status === 'error'
        ? 'network.execution.failed'
        : execution.status === 'running'
          ? 'network.execution.progress'
          : 'network.execution.completed',
    label:
      execution.status === 'error'
        ? 'Network execution failed'
        : execution.status === 'running'
          ? 'Network execution in progress'
          : 'Network execution completed',
    timestamp: executionCompletionTime(execution) ?? new Date().toISOString(),
    sequence: finalSequence,
    nodeId: execution.status === 'success' ? 'end' : lastPathNode,
    status:
      execution.status === 'error'
        ? 'error'
        : execution.status === 'running'
          ? 'running'
          : 'success',
    payload: {
      duration_ms: execution.durationMs,
      cost_usd: execution.costUsd,
      answer,
      trace_id: execution.traceId,
    },
  }

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
    networkVersion: networkLabel(environment),
    compositionHash: hashComposition(currentSignature(environment, bindings)),
    status: execution.status,
    startedAt,
    completedAt: executionCompletionTime(execution),
    durationMs: execution.durationMs,
    usage: usage ?? aggregateUsage(execution.root),
    costUsd: execution.costUsd,
    agentContexts,
    execution,
    events: [startEvent, enteredEvent, ...invocation.events, finalEvent],
  }
}
