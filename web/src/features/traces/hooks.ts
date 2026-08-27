import { useQuery } from '@tanstack/react-query'
import { ApiError } from '@/lib/api/errors'
import {
  getTraces,
  getTraceDetail,
  getTraceModelInvocations,
  getAskJob,
  type AskJobResponse,
  type GetTracesParams,
} from './api'
import type { ContextModelInvocation, Trace, TraceDetail } from './types'

const TRACE_REFRESH_INTERVAL_MS = 1_500
const IDLE_TRACE_LIST_REFRESH_INTERVAL_MS = 10_000
const TRACE_NOT_FOUND_RETRIES = 20

function isTerminalStatus(status: string | undefined): boolean {
  if (!status) return false
  return ['completed', 'success', 'failed', 'error', 'cancelled', 'canceled'].includes(
    status.toLowerCase(),
  )
}

function isTerminalTrace(trace: TraceDetail | undefined): boolean {
  return Boolean(trace && isTerminalStatus(trace.status))
}

function hasActiveTrace(traces: Trace[] | undefined): boolean {
  return Boolean(traces?.some((trace) => !isTerminalStatus(trace.status)))
}

function shouldRetryTrace(failureCount: number, error: Error): boolean {
  return error instanceof ApiError
    && error.status === 404
    && failureCount < TRACE_NOT_FOUND_RETRIES
}

export function useTraces(projectId?: string, networkId?: string) {
  return useQuery({
    queryKey: ['traces', { projectId, networkId }],
    queryFn: () => getTraces({ projectId, networkId }),
    enabled: Boolean(projectId),
    staleTime: 2_000,
    refetchInterval: (query) => hasActiveTrace(query.state.data as Trace[] | undefined)
      ? TRACE_REFRESH_INTERVAL_MS
      : IDLE_TRACE_LIST_REFRESH_INTERVAL_MS,
    refetchIntervalInBackground: false,
  })
}

export function useTraceDetail(id: string | undefined) {
  return useQuery<TraceDetail, Error>({
    queryKey: ['trace', id],
    queryFn: () => getTraceDetail(id!),
    enabled: Boolean(id),
    retry: shouldRetryTrace,
    retryDelay: (failureCount) => Math.min(250 * 2 ** failureCount, 1_500),
    refetchInterval: (query) => {
      const trace = query.state.data
      return isTerminalTrace(trace) ? false : TRACE_REFRESH_INTERVAL_MS
    },
    refetchIntervalInBackground: false,
  })
}

export function useTraceModelInvocations(id: string | undefined) {
  return useQuery<ContextModelInvocation[], Error>({
    queryKey: ['trace-context', id],
    queryFn: () => getTraceModelInvocations(id!),
    enabled: Boolean(id),
    retry: shouldRetryTrace,
    retryDelay: (failureCount) => Math.min(250 * 2 ** failureCount, 1_500),
    staleTime: 30_000,
  })
}

export function usePlaygroundTraces(
  projectId?: string,
  agentId?: string,
  sessionId?: string | null,
) {
  return useQuery<Trace[]>({
    queryKey: ['traces', { projectId, agentId, sessionId }],
    queryFn: () =>
      getTraces({
        projectId,
        agentId: sessionId ? undefined : agentId,
        sessionId: sessionId ?? undefined,
      } as GetTracesParams),
    // Agent Runs exist independently of Sessions. Stateless Agents must still
    // expose their Runs through the Agent filter.
    enabled: Boolean(projectId) && Boolean(agentId),
    staleTime: 2_000,
    refetchInterval: (query) => hasActiveTrace(query.state.data)
      ? TRACE_REFRESH_INTERVAL_MS
      : false,
    refetchIntervalInBackground: false,
  })
}

export function useAskJob(jobId: string | undefined | null) {
  return useQuery({
    queryKey: ['askJob', jobId],
    queryFn: () => getAskJob(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const data = query.state.data as AskJobResponse | undefined
      if (!data) return 2_000
      if (data.status === 'completed' || data.status === 'failed') return false
      return 2_000
    },
    refetchIntervalInBackground: false,
  })
}
