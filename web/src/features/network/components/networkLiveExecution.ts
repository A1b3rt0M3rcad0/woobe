import type { SourceInfo, ToolCallInfo } from '@/features/playground/types'
import type { NetworkRuntimeEvent } from '@/features/network/types'

import type { AgentNodeId } from './networkWorkspaceTypes'

export type LiveNetworkAgentStatus = 'running' | 'success' | 'error'

export interface LiveNetworkAgent {
  invocationId: string
  nodeId?: AgentNodeId
  name: string
  depth: number
  status: LiveNetworkAgentStatus
  startedAt?: string | null
  durationMs?: number | null
}

export interface LiveNetworkToolCall extends ToolCallInfo {
  invocationId?: string | null
  startedAt?: string | null
}

export interface LiveNetworkExecutionState {
  agents: LiveNetworkAgent[]
  tools: LiveNetworkToolCall[]
  sources: SourceInfo[]
}

export function emptyLiveNetworkExecution(): LiveNetworkExecutionState {
  return { agents: [], tools: [], sources: [] }
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

function resolvedToolName(
  existing: LiveNetworkToolCall,
  candidate: LiveNetworkToolCall,
): string {
  if (
    existing.tool_name.startsWith('Delegate to ')
    && candidate.tool_name.startsWith('delegate_to_')
  ) return existing.tool_name
  return candidate.tool_name
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
    ? { ...tool, ...candidate, tool_name: resolvedToolName(tool, candidate) }
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
    if (!toolName) return tools
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

function delegationToolName(target: string): string {
  const slug = target
    .trim()
    .toLowerCase()
    .replace(/-/g, '_')
    .replace(/[^a-z0-9_]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '')
  return `delegate_to_${slug}`.slice(0, 64)
}

function labelDelegationTool(
  tools: LiveNetworkToolCall[],
  invocationId: string | null | undefined,
  target: string,
): LiveNetworkToolCall[] {
  const expectedName = delegationToolName(target)
  let matched = false
  const renamed = tools.map((tool) => {
    if (
      tool.invocationId === invocationId
      && tool.status === 'running'
      && tool.tool_name === expectedName
    ) {
      matched = true
      return { ...tool, tool_name: `Delegate to ${target}` }
    }
    return tool
  })
  if (matched) return renamed

  const fallbackIndex = [...renamed].reverse().findIndex((tool) => (
    tool.invocationId === invocationId && tool.status === 'running'
  ))
  if (fallbackIndex < 0) return renamed
  const actualIndex = renamed.length - fallbackIndex - 1
  return renamed.map((tool, index) => (
    index === actualIndex ? { ...tool, tool_name: `Delegate to ${target}` } : tool
  ))
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

  if ((eventType === 'agent_invocation_completed' || eventType === 'agent_invocation_failed') && invocationId) {
    const current = state.agents.find((agent) => agent.invocationId === invocationId)
    const status: LiveNetworkAgentStatus = eventType === 'agent_invocation_completed' ? 'success' : 'error'
    return {
      agents: updateAgent(state.agents, invocationId, {
        status,
        durationMs: elapsedMilliseconds(current?.startedAt, event.created_at),
      }),
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
    if (!toolName) return state
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
    if (!toolName) return state
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

  if (eventType === 'delegation_started') {
    const target = asString(event.data.target)
    if (!target) return state
    return {
      ...state,
      tools: labelDelegationTool(state.tools, invocationId, target),
    }
  }

  if (eventType === 'execution_failed' || eventType === 'execution_cancelled') {
    return {
      ...state,
      agents: state.agents.map((agent) => (
        agent.status === 'running' ? { ...agent, status: 'error' } : agent
      )),
      tools: state.tools.map((tool) => (
        tool.status === 'running'
          ? { ...tool, status: 'error', success: false, error_code: 'execution_stopped', error: 'Network execution stopped' }
          : tool
      )),
    }
  }

  return state
}
