import type { SourceInfo, ToolCallInfo } from '@/features/playground/types'
import type { NetworkRuntimeEvent } from '@/features/network/types'

import type { AgentNodeId } from './networkWorkspaceTypes'

export type LiveNetworkAgentStatus = 'running' | 'success' | 'error' | 'cancelled'
export type LiveNetworkDelegationStatus = 'running' | 'success' | 'error' | 'skipped' | 'cancelled'

export interface LiveNetworkAgent {
  invocationId: string
  nodeId?: AgentNodeId
  name: string
  depth: number
  status: LiveNetworkAgentStatus
  startedAt?: string | null
  durationMs?: number | null
}

export interface LiveNetworkDelegation {
  id: string
  invocationId?: string | null
  targetNodeId?: AgentNodeId
  target: string
  status: LiveNetworkDelegationStatus
  startedAt?: string | null
  completedAt?: string | null
  reason?: string | null
}

export interface LiveNetworkToolCall extends ToolCallInfo {
  invocationId?: string | null
  startedAt?: string | null
}

export interface LiveNetworkExecutionState {
  agents: LiveNetworkAgent[]
  delegations: LiveNetworkDelegation[]
  tools: LiveNetworkToolCall[]
  sources: SourceInfo[]
}

export function emptyLiveNetworkExecution(): LiveNetworkExecutionState {
  return { agents: [], delegations: [], tools: [], sources: [] }
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? value as Record<string, unknown> : {}
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function asBoolean(value: unknown): boolean | null {
  return typeof value === 'boolean' ? value : null
}

function isDelegationToolName(value: string | null): boolean {
  return Boolean(value?.startsWith('delegate_to_'))
}

function sourceKey(source: SourceInfo, index: number): string {
  if (source.chunk_id) return `chunk:${source.chunk_id}`
  if (source.document_id) return `document:${source.document_id}:${source.page_number ?? 'unknown'}`
  return `unknown:${index}`
}

function mergeSources(current: SourceInfo[], rawSources: unknown): SourceInfo[] {
  if (!Array.isArray(rawSources)) return current

  const merged = new Map<string, SourceInfo>()
  current.forEach((source, index) => merged.set(sourceKey(source, index), source))
  rawSources.forEach((rawSource, index) => {
    const source = asRecord(rawSource) as SourceInfo
    merged.set(sourceKey(source, current.length + index), source)
  })
  return [...merged.values()]
}

function upsertTool(
  tools: LiveNetworkToolCall[],
  candidate: LiveNetworkToolCall,
): LiveNetworkToolCall[] {
  const key = candidate.tool_call_id
  if (!key) return [...tools, candidate]
  const index = tools.findIndex((tool) => tool.tool_call_id === key)
  if (index < 0) return [...tools, candidate]
  return tools.map((tool, toolIndex) => toolIndex === index
    ? { ...tool, ...candidate }
    : tool)
}

function mergeCompletedTools(
  current: LiveNetworkToolCall[],
  rawTools: unknown,
  invocationId?: string | null,
): LiveNetworkToolCall[] {
  if (!Array.isArray(rawTools)) return current
  return rawTools.reduce<LiveNetworkToolCall[]>((tools, rawTool) => {
    const tool = asRecord(rawTool)
    const toolName = asString(tool.tool_name)
    if (!toolName || isDelegationToolName(toolName)) return tools
    return upsertTool(tools, {
      tool_call_id: asString(tool.tool_call_id),
      tool_name: toolName,
      input: tool.input,
      output: tool.output,
      duration_ms: asNumber(tool.duration_ms) ?? undefined,
      success: asBoolean(tool.success),
      status: asString(tool.status),
      error_code: asString(tool.error_code),
      error: asString(tool.error),
      invocationId,
    })
  }, current)
}

function delegationId(event: NetworkRuntimeEvent, target: string): string {
  const fingerprint = asString(event.data.task_fingerprint)
  if (fingerprint) return fingerprint
  return `${event.invocation_id ?? 'root'}:${asString(event.data.target_node_id) ?? target}`
}

function upsertDelegation(
  delegations: LiveNetworkDelegation[],
  candidate: LiveNetworkDelegation,
): LiveNetworkDelegation[] {
  const index = delegations.findIndex((delegation) => delegation.id === candidate.id)
  if (index < 0) return [...delegations, candidate]
  return delegations.map((delegation, delegationIndex) => delegationIndex === index
    ? { ...delegation, ...candidate }
    : delegation)
}

function elapsedMilliseconds(startedAt?: string | null, completedAt?: string | null): number | null {
  if (!startedAt || !completedAt) return null
  const elapsed = new Date(completedAt).getTime() - new Date(startedAt).getTime()
  return Number.isFinite(elapsed) && elapsed >= 0 ? elapsed : null
}

function updateAgent(
  agents: LiveNetworkAgent[],
  invocationId: string,
  update: Partial<LiveNetworkAgent>,
): LiveNetworkAgent[] {
  const index = agents.findIndex((agent) => agent.invocationId === invocationId)
  if (index < 0) {
    return [...agents, {
      invocationId,
      name: 'Agent',
      depth: 0,
      status: 'running',
      ...update,
    }]
  }
  return agents.map((agent, agentIndex) => (
    agentIndex === index ? { ...agent, ...update } : agent
  ))
}

function updateDelegationFromEvent(
  state: LiveNetworkExecutionState,
  eventType: string,
  event: NetworkRuntimeEvent,
): LiveNetworkExecutionState {
  const target = asString(event.data.target) ?? asString(event.data.target_node_id) ?? 'Agent'
  const id = delegationId(event, target)
  const existing = state.delegations.find((delegation) => delegation.id === id)
  const status: LiveNetworkDelegationStatus = eventType === 'delegation_started'
    ? 'running'
    : eventType === 'delegation_completed'
      ? 'success'
      : eventType === 'delegation_skipped'
        ? 'skipped'
        : 'error'
  return {
    ...state,
    delegations: upsertDelegation(state.delegations, {
      id,
      invocationId: event.invocation_id ?? existing?.invocationId ?? null,
      targetNodeId: (asString(event.data.target_node_id) as AgentNodeId | null) ?? existing?.targetNodeId,
      target: asString(event.data.target) ?? existing?.target ?? target,
      status,
      startedAt: eventType === 'delegation_started'
        ? event.created_at ?? null
        : existing?.startedAt ?? null,
      completedAt: eventType === 'delegation_started'
        ? existing?.completedAt ?? null
        : event.created_at ?? null,
      reason: asString(event.data.reason) ?? existing?.reason ?? null,
    }),
  }
}

export function applyNetworkRuntimeEvent(
  state: LiveNetworkExecutionState,
  eventType: string,
  event: NetworkRuntimeEvent,
): LiveNetworkExecutionState {
  const invocationId = event.invocation_id ?? null

  if (eventType === 'agent_invocation_started' && invocationId) {
    return {
      ...state,
      agents: updateAgent(state.agents, invocationId, {
        nodeId: event.node_id ? event.node_id as AgentNodeId : undefined,
        name: asString(event.data.label) ?? 'Agent',
        depth: event.depth ?? 0,
        status: 'running',
        startedAt: event.created_at ?? null,
      }),
    }
  }

  if ((eventType === 'agent_invocation_completed' || eventType === 'agent_invocation_failed' || eventType === 'agent_invocation_cancelled') && invocationId) {
    const current = state.agents.find((agent) => agent.invocationId === invocationId)
    const status: LiveNetworkAgentStatus = eventType === 'agent_invocation_completed'
      ? 'success'
      : eventType === 'agent_invocation_cancelled'
        ? 'cancelled'
        : 'error'
    return {
      agents: updateAgent(state.agents, invocationId, {
        status,
        durationMs: elapsedMilliseconds(current?.startedAt, event.created_at),
      }),
      delegations: state.delegations,
      tools: eventType === 'agent_invocation_completed'
        ? mergeCompletedTools(state.tools, event.data.tool_calls, invocationId)
        : state.tools,
      sources: eventType === 'agent_invocation_completed'
        ? mergeSources(state.sources, event.data.sources)
        : state.sources,
    }
  }

  if (eventType === 'tool_call_started') {
    const toolCallId = asString(event.data.tool_call_id)
    const toolName = asString(event.data.tool_name)
    if (!toolName || isDelegationToolName(toolName)) return state
    return {
      ...state,
      tools: upsertTool(state.tools, {
        tool_call_id: toolCallId,
        tool_name: toolName,
        input: event.data.input,
        success: null,
        status: 'running',
        invocationId,
        startedAt: asString(event.data.started_at) ?? event.created_at ?? null,
      }),
    }
  }

  if (eventType === 'tool_call_completed') {
    const toolCallId = asString(event.data.tool_call_id)
    const toolName = asString(event.data.tool_name)
    if (!toolName || isDelegationToolName(toolName)) return state
    return {
      ...state,
      tools: upsertTool(state.tools, {
        tool_call_id: toolCallId,
        tool_name: toolName,
        input: event.data.input,
        output: event.data.output,
        duration_ms: asNumber(event.data.duration_ms) ?? undefined,
        success: asBoolean(event.data.success),
        status: asString(event.data.status),
        error_code: asString(event.data.error_code),
        error: asString(event.data.error),
        invocationId,
      }),
    }
  }

  if (eventType === 'sources') {
    return { ...state, sources: mergeSources(state.sources, event.data.sources) }
  }

  if (
    eventType === 'delegation_started'
    || eventType === 'delegation_completed'
    || eventType === 'delegation_failed'
    || eventType === 'delegation_skipped'
  ) {
    return updateDelegationFromEvent(state, eventType, event)
  }

  if (eventType === 'execution_failed') {
    return {
      ...state,
      agents: state.agents.map((agent) => (
        agent.status === 'running' ? { ...agent, status: 'error' } : agent
      )),
      delegations: state.delegations.map((delegation) => (
        delegation.status === 'running' ? { ...delegation, status: 'error' } : delegation
      )),
      tools: state.tools.map((tool) => (
        tool.status === 'running'
          ? { ...tool, status: 'error', success: false, error_code: 'execution_stopped', error: 'Network execution stopped' }
          : tool
      )),
    }
  }

  if (eventType === 'execution_cancelled') {
    return {
      ...state,
      agents: state.agents.map((agent) => (
        agent.status === 'running' ? { ...agent, status: 'cancelled' } : agent
      )),
      delegations: state.delegations.map((delegation) => (
        delegation.status === 'running' ? { ...delegation, status: 'cancelled' } : delegation
      )),
      tools: state.tools.map((tool) => (
        tool.status === 'running'
          ? { ...tool, status: 'cancelled', success: false, error_code: null, error: null }
          : tool
      )),
    }
  }

  return state
}
