import { useQuery } from '@tanstack/react-query'
import { ApiError } from '@/lib/api/errors'
import {
  getTraces,
  getTraceDetail,
  getAskJob,
  type AskJobResponse,
  type GetTracesParams,
} from './api'
import type { Trace, TraceDetail } from './types'

const TRACE_REFRESH_INTERVAL_MS = 1_000
const TRACE_LIST_REFRESH_INTERVAL_MS = 1_500
const TRACE_NOT_FOUND_RETRIES = 20

function isTerminalTrace(trace: TraceDetail | undefined): boolean {
  if (!trace) return false
  return ['completed', 'success', 'failed', 'error', 'cancelled', 'canceled'].includes(
    trace.status.toLowerCase(),
  )
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
    refetchInterval: TRACE_LIST_REFRESH_INTERVAL_MS,
    refetchIntervalInBackground: true,
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
    refetchIntervalInBackground: true,
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
    refetchInterval: TRACE_LIST_REFRESH_INTERVAL_MS,
    refetchIntervalInBackground: true,
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
  })
}
