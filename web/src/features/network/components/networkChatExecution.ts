import type { SourceInfo, ToolCallInfo, UsageInfo } from '@/features/playground/types'
import type { NetworkRuntimeEvent } from '@/features/network/types'

import type { AgentNodeId, Environment, NetworkBinding, NodeId } from './networkWorkspaceTypes'

export type AgentInvocationStatus = 'pending' | 'running' | 'success' | 'error' | 'skipped'

export interface NetworkAgentInvocation {
  spanId: string
  parentSpanId: string | null
  sequence: number
  nodeId?: AgentNodeId
  agentId: string
  agentName: string
  agentSessionId: string | null
  contextState: 'created' | 'reused' | 'stateless'
  previousInvocationCount: number
  childTraceId: string | null
  provider?: string | null
  model?: string | null
  source: NetworkBinding['source']
  version: string
  status: AgentInvocationStatus
  durationMs?: number | null
  usage?: UsageInfo | null
  costUsd?: number | null
  input?: unknown
  output?: string | null
  parsedOutput?: Record<string, unknown> | null
  outputParseError?: string | null
  failure?: NetworkInvocationFailure | null
  tools: ToolCallInfo[]
  sources: SourceInfo[]
  children: NetworkAgentInvocation[]
}

export interface NetworkInvocationFailure {
  code: string
  stage: string
  message: string
  retryable: boolean
}

export interface NetworkExecution {
  id: string
  traceId: string | null
  status: 'running' | 'success' | 'error'
  environment: Environment
  startedAt: string
  durationMs: number
  costUsd: number | null
  path: NodeId[]
  root: NetworkAgentInvocation
}

export interface NetworkTurn {
  id: string
  user: string
  answer: string
  parsedOutput?: Record<string, unknown> | null
  outputParseError?: string | null
  provider: string
  model: string
  usage: UsageInfo | null
  execution: NetworkExecution
}

export interface RuntimeEventRecord {
  eventType: string
  event: NetworkRuntimeEvent
}

export function networkLabel(environment: Environment, version?: string | number | null) {
  if (environment === 'draft') return `Draft r${version ?? 'current'}`
  if (environment === 'staging') return version ? `Staging ${version}` : 'Current Staging'
  return version ? `Production ${version}` : 'Current Production'
}

export function currentSignature(
  environment: Environment,
  bindings: Record<AgentNodeId, NetworkBinding>,
) {
  const signature = Object.values(bindings)
    .sort((left, right) => left.nodeId.localeCompare(right.nodeId))
    .map((binding) => (
      `${binding.nodeId}:${binding.agent.id}:${binding.source}:${binding.ref}:${binding.dirty ? 'preview' : 'saved'}`
    ))
    .join('|')
  return `${environment}|${signature}`
}

export function invocationCount(root: NetworkAgentInvocation): number {
  return 1 + root.children.reduce((total, child) => total + invocationCount(child), 0)
}

export function delegationCount(root: NetworkAgentInvocation): number {
  return root.children.length
    + root.children.reduce((total, child) => total + delegationCount(child), 0)
}

export function toolCount(root: NetworkAgentInvocation): number {
  return root.tools.length + root.children.reduce((total, child) => total + toolCount(child), 0)
}

export function sourceCount(root: NetworkAgentInvocation): number {
  return root.sources.length + root.children.reduce((total, child) => total + sourceCount(child), 0)
}

export function invocationPath(root: NetworkAgentInvocation): string[] {
  const primaryChild = root.children[0]
  if (!primaryChild) return [root.agentName]
  return [root.agentName, ...invocationPath(primaryChild)]
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? value as Record<string, unknown> : {}
}

function asUsage(value: unknown): UsageInfo | null {
  const usage = asRecord(value)
  if (
    typeof usage.input_tokens !== 'number'
    || typeof usage.output_tokens !== 'number'
    || typeof usage.total_tokens !== 'number'
  ) return null
  return {
    input_tokens: usage.input_tokens,
    output_tokens: usage.output_tokens,
    total_tokens: usage.total_tokens,
    cost_usd: typeof usage.cost_usd === 'number' ? usage.cost_usd : null,
  }
}

function totalUsage(invocations: NetworkAgentInvocation[]): UsageInfo | null {
  const known = invocations.flatMap((invocation) => invocation.usage ? [invocation.usage] : [])
  if (!known.length) return null
  const totals = known.reduce<UsageInfo>((total, usage) => {
    return {
      input_tokens: (total.input_tokens ?? 0) + (usage.input_tokens ?? 0),
      output_tokens: (total.output_tokens ?? 0) + (usage.output_tokens ?? 0),
      total_tokens: (total.total_tokens ?? 0) + (usage.total_tokens ?? 0),
      cost_usd: 0,
    }
  }, { input_tokens: 0, output_tokens: 0, total_tokens: 0, cost_usd: 0 })
  totals.cost_usd = known.every((usage) => typeof usage.cost_usd === 'number')
    ? known.reduce((total, usage) => total + (usage.cost_usd ?? 0), 0)
    : null
  return totals
}

function asFailure(value: unknown): NetworkInvocationFailure {
  const failure = asRecord(value)
  return {
    code: typeof failure.code === 'string' ? failure.code : 'runtime_error',
    stage: typeof failure.stage === 'string' ? failure.stage : 'network_runtime',
    message: typeof failure.message === 'string'
      ? failure.message
      : 'The Agent Run failed before producing a valid result.',
    retryable: failure.retryable === true,
  }
}

function placeholderInvocation(
  bindings: Record<AgentNodeId, NetworkBinding>,
  status: NetworkExecution['status'],
): NetworkAgentInvocation {
  const binding = Object.values(bindings)[0]
  return {
    spanId: 'network-root',
    parentSpanId: null,
    sequence: 0,
    nodeId: binding?.nodeId,
    agentId: binding?.agent.id ?? '',
    agentName: binding?.agent.name ?? 'Network',
    agentSessionId: null,
    contextState: 'created',
    previousInvocationCount: 0,
    childTraceId: null,
    provider: binding?.agent.provider ?? null,
    model: binding?.agent.model ?? null,
    source: binding?.source ?? 'draft',
    version: binding?.version ?? 'current',
    status: status === 'error' ? 'error' : status,
    durationMs: 0,
    usage: null,
    costUsd: null,
    tools: [],
    sources: [],
    children: [],
  }
}

export function buildExecutionFromRuntimeEvents({
  records,
  environment,
  bindings,
  executionId,
  answer,
  fallbackTraceId,
  terminalStatus = 'success',
}: {
  records: RuntimeEventRecord[]
  environment: Environment
  bindings: Record<AgentNodeId, NetworkBinding>
  executionId: string
  answer: string
  fallbackTraceId?: string
  terminalStatus?: NetworkExecution['status']
}): { execution: NetworkExecution; usage: UsageInfo | null; provider: string; model: string } {
  const sorted = [...records].sort(
    (left, right) => (left.event.sequence ?? 0) - (right.event.sequence ?? 0),
  )
  const invocations = new Map<string, NetworkAgentInvocation>()
  let traceId: string | null = fallbackTraceId || null

  for (const { eventType, event } of sorted) {
    const invocationId = event.invocation_id
    if (eventType === 'agent_invocation_started' && invocationId) {
      const binding = event.node_id ? bindings[event.node_id] : undefined
      const runtimeSource = event.data.source
      invocations.set(invocationId, {
        spanId: invocationId,
        parentSpanId: event.parent_invocation_id ?? null,
        sequence: event.sequence ?? invocations.size + 1,
        nodeId: event.node_id ?? undefined,
        agentId: event.agent_id ?? binding?.agent.id ?? '',
        agentName: String(event.data.label ?? binding?.agent.name ?? 'Agent'),
        agentSessionId: null,
        contextState: 'created',
        previousInvocationCount: 0,
        childTraceId: null,
        provider: typeof event.data.provider === 'string'
          ? event.data.provider
          : binding?.agent.provider ?? null,
        model: typeof event.data.model === 'string'
          ? event.data.model
          : binding?.agent.model ?? null,
        source: runtimeSource === 'draft' || runtimeSource === 'staging' || runtimeSource === 'release'
          ? runtimeSource
          : binding?.source ?? (environment === 'production' ? 'release' : environment),
        version: typeof event.data.version === 'string'
          ? event.data.version
          : binding?.version ?? 'current',
        status: 'running',
        input: event.data.input,
        tools: [],
        sources: [],
        children: [],
      })
      continue
    }
    if (eventType === 'agent_invocation_completed' && invocationId) {
      const current = invocations.get(invocationId)
      if (!current) continue
      const usage = asUsage(event.data.usage)
      const childTraceId = typeof event.data.trace_id === 'string' ? event.data.trace_id : null
      if (!current.parentSpanId && childTraceId) traceId = childTraceId
      current.status = 'success'
      current.agentSessionId = typeof event.data.agent_session_id === 'string'
        ? event.data.agent_session_id
        : null
      current.childTraceId = childTraceId
      current.provider = typeof event.data.provider === 'string' ? event.data.provider : current.provider
      current.model = typeof event.data.model === 'string' ? event.data.model : current.model
      current.usage = usage
      current.costUsd = typeof usage?.cost_usd === 'number' ? usage.cost_usd : null
      current.output = typeof event.data.output === 'string' ? event.data.output : null
      current.tools = Array.isArray(event.data.tool_calls)
        ? event.data.tool_calls as ToolCallInfo[]
        : []
      current.sources = Array.isArray(event.data.sources)
        ? event.data.sources as SourceInfo[]
        : []
      current.parsedOutput = event.data.parsed_output != null
        ? asRecord(event.data.parsed_output)
        : null
      current.outputParseError = typeof event.data.output_parse_error === 'string'
        ? event.data.output_parse_error
        : null
      continue
    }
    if (eventType === 'agent_invocation_failed' && invocationId) {
      const current = invocations.get(invocationId)
      if (!current) continue
      current.status = 'error'
      current.failure = asFailure(event.data)
      continue
    }
    if (eventType === 'execution_completed' && typeof event.data.trace_id === 'string') {
      traceId = event.data.trace_id
    }
  }

  const ordered = [...invocations.values()].sort((left, right) => left.sequence - right.sequence)
  for (const invocation of ordered) invocation.children = []
  for (const invocation of ordered) {
    if (!invocation.parentSpanId) continue
    invocations.get(invocation.parentSpanId)?.children.push(invocation)
  }

  const status = terminalStatus
  const root = ordered.find((item) => !item.parentSpanId)
    ?? placeholderInvocation(bindings, status)
  if (status === 'error' && root.status === 'running') {
    root.status = 'error'
    const terminalFailure = [...sorted]
      .reverse()
      .find((item) => item.eventType === 'execution_failed')
    root.failure = terminalFailure ? asFailure(terminalFailure.event.data) : null
  }

  const startedAt = sorted.find((item) => item.event.created_at)?.event.created_at
    ?? new Date().toISOString()
  const completedAt = [...sorted].reverse().find((item) => item.event.created_at)?.event.created_at
    ?? startedAt
  const durationMs = Math.max(0, new Date(completedAt).getTime() - new Date(startedAt).getTime())
  for (const invocation of ordered) {
    if (invocation.durationMs == null) invocation.durationMs = durationMs
  }
  const usage = totalUsage(ordered)
  const path = ordered
    .map((item) => item.nodeId)
    .filter((value): value is string => Boolean(value)) as NodeId[]

  return {
    execution: {
      id: executionId,
      traceId,
      status,
      environment,
      startedAt,
      durationMs,
      costUsd: typeof usage?.cost_usd === 'number' ? usage.cost_usd : null,
      path,
      root,
    },
    usage,
    provider: root.provider ?? '',
    model: root.model ?? '',
  }
}

export function buildTurnFromRuntimeEvents({
  records,
  environment,
  bindings,
  executionId,
  user,
  answer,
  fallbackTraceId,
  terminalStatus,
}: {
  records: RuntimeEventRecord[]
  environment: Environment
  bindings: Record<AgentNodeId, NetworkBinding>
  executionId: string
  user: string
  answer: string
  fallbackTraceId?: string
  terminalStatus?: NetworkExecution['status']
}): NetworkTurn {
  const built = buildExecutionFromRuntimeEvents({
    records,
    environment,
    bindings,
    executionId,
    answer,
    fallbackTraceId,
    terminalStatus,
  })
  return {
    id: executionId,
    user,
    answer: answer || built.execution.root.failure?.message || '',
    parsedOutput: built.execution.root.parsedOutput,
    outputParseError: built.execution.root.outputParseError,
    provider: built.provider,
    model: built.model,
    usage: built.usage,
    execution: built.execution,
  }
}
