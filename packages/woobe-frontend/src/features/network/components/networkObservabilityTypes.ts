import type { UsageInfo } from '@/features/playground/types'

import type {
  NetworkAgentInvocation,
  NetworkExecution,
} from './networkChatExecution'
import type { NetworkRun, NodeId } from './networkWorkspaceTypes'
import type { NetworkAgentContext } from './networkSessionTypes'

export type NetworkTraceSource = 'chat' | 'runtime'
export type NetworkTraceEventStatus =
  | 'pending'
  | 'running'
  | 'success'
  | 'error'
  | 'cancelled'
  | 'skipped'

export interface NetworkTraceEvent {
  id: string
  type: string
  label: string
  timestamp: string
  sequence: number
  spanId?: string | null
  parentSpanId?: string | null
  nodeId?: NodeId
  status?: NetworkTraceEventStatus
  payload: Record<string, unknown>
}

export interface NetworkTraceRecord {
  id: string
  traceId: string | null
  networkSessionId: string
  source: NetworkTraceSource
  title: string
  userMessage: string
  answer: string
  parsedOutput?: Record<string, unknown> | null
  outputParseError?: string | null
  environment: NetworkExecution['environment']
  networkVersion: string
  compositionHash: string
  status: NetworkExecution['status']
  startedAt: string
  completedAt: string | null
  durationMs: number
  usage: UsageInfo | null
  costUsd: number | null
  agentContexts: NetworkAgentContext[]
  execution: NetworkExecution
  events: NetworkTraceEvent[]
}

export function hashComposition(signature: string): string {
  let hash = 2166136261
  for (let index = 0; index < signature.length; index += 1) {
    hash ^= signature.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return `cmp_${(hash >>> 0).toString(16).padStart(8, '0')}`
}

export function executionCompletionTime(
  execution: NetworkExecution,
): string | null {
  if (execution.status === 'running') return null
  return new Date(
    new Date(execution.startedAt).getTime() + execution.durationMs,
  ).toISOString()
}

export function traceToRun(trace: NetworkTraceRecord): NetworkRun {
  return {
    id: trace.id,
    title: trace.title,
    environment: trace.environment,
    status: trace.status,
    duration: `${(trace.durationMs / 1000).toFixed(2)}s`,
    cost: trace.costUsd == null ? 'Unknown' : `$${trace.costUsd.toFixed(3)}`,
    path: trace.execution.path,
    traceId: trace.traceId ?? undefined,
  }
}

export type NetworkTraceInvocation = NetworkAgentInvocation
