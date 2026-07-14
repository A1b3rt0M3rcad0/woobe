import type {
  AgentNodeId,
  ChatTarget,
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
      },
    )

    for (const tool of invocation.tools) {
      const failed =
        tool.success === false ||
        tool.status === 'failed' ||
        tool.status === 'error'
      push(
        failed
          ? 'network.tool.call.failed'
          : 'network.tool.call.completed',
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
          reason: `Request matched the ${child.nodeId ?? 'specialist'} route`,
        },
      )
      visit(child)
    }

    const failed = invocation.status === 'error'
    push(
      failed
        ? 'network.agent.invocation.failed'
        : 'network.agent.invocation.completed',
      `${invocation.agentName} ${failed ? 'failed' : 'completed'}`,
      invocation,
      failed ? 'error' : 'success',
      {
        duration_ms: invocation.durationMs,
        usage: invocation.usage,
        cost_usd: invocation.costUsd,
        output: invocation.output,
        output_parse_error: invocation.outputParseError,
      },
    )
  }

  visit(root)
  return { events, lastSequence: sequence }
}

export function createNetworkTraceRecord({
  execution,
  target,
  bindings,
  sessionId,
  title,
  userMessage,
  answer,
  source = 'chat',
}: {
  execution: NetworkExecution
  target: ChatTarget
  bindings: Record<AgentNodeId, NetworkBinding>
  sessionId: string
  title: string
  userMessage: string
  answer: string
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
      target,
      network_version: networkLabel(target),
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
    sessionId,
    source,
    title,
    userMessage,
    answer,
    environment: execution.environment,
    networkVersion: networkLabel(target),
    compositionHash: hashComposition(currentSignature(target, bindings)),
    status: execution.status,
    startedAt,
    completedAt: executionCompletionTime(execution),
    durationMs: execution.durationMs,
    costUsd: execution.costUsd,
    execution,
    events: [startEvent, enteredEvent, ...invocation.events, finalEvent],
  }
}
