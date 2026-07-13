import type {
  NetworkAgentInvocation,
  NetworkExecution,
} from './networkChatExecution'
import type { NetworkRun, NodeId } from './networkWorkspaceTypes'

export type NetworkTraceSource = 'chat' | 'runtime'
export type NetworkTraceEventStatus =
  | 'pending'
  | 'running'
  | 'success'
  | 'error'
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
  traceId: string
  sessionId: string
  source: NetworkTraceSource
  title: string
  userMessage: string
  answer: string
  environment: NetworkExecution['environment']
  networkVersion: string
  compositionHash: string
  status: NetworkExecution['status']
  startedAt: string
  completedAt: string | null
  durationMs: number
  costUsd: number
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
    cost: `$${trace.costUsd.toFixed(3)}`,
    path: trace.execution.path,
    traceId: trace.traceId,
  }
}

export type NetworkTraceInvocation = NetworkAgentInvocation
