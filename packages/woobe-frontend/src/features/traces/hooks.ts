import { useQuery } from '@tanstack/react-query'
import { ApiError } from '@/lib/api/errors'
import {
  getAgentRuns,
  getTraces,
  getTraceDetail,
  getTraceModelInvocations,
  getRunModelInvocations,
  getAgentRunDetail,
  getAgentRunDetailByTrace,
  getAskJob,
  type AskJobResponse,
  type GetTracesParams,
} from './api'
import type { AgentRunDetail, ContextModelInvocation, Trace, TraceDetail } from './types'

const TRACE_REFRESH_INTERVAL_MS = 1_500
const IDLE_TRACE_LIST_REFRESH_INTERVAL_MS = 10_000
const TRACE_NOT_FOUND_RETRIES = 20
const CONTEXT_EVIDENCE_NOT_FOUND_RETRIES = 6
const AGENT_RUN_DETAIL_NOT_FOUND_RETRIES = 6

function isTerminalStatus(status: string | undefined): boolean {
  if (!status) return false
  return [
    'completed',
    'success',
    'failed',
    'error',
    'cancelled',
    'canceled',
    'timed_out',
    'timeout',
    'uncertain',
  ].includes(status.toLowerCase())
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

function shouldRetryContextEvidence(failureCount: number, error: Error): boolean {
  if (!(error instanceof ApiError)) return false
  if (error.status === 404) return failureCount < CONTEXT_EVIDENCE_NOT_FOUND_RETRIES
  return error.status >= 500 && failureCount < 2
}

function shouldRetryAgentRunDetail(failureCount: number, error: Error): boolean {
  if (!(error instanceof ApiError)) return false
  if (error.status === 404) return failureCount < AGENT_RUN_DETAIL_NOT_FOUND_RETRIES
  return error.status >= 500 && failureCount < 2
}

export function agentRunDetailRefetchInterval(
  run: Pick<AgentRunDetail, 'status'> | undefined,
  error: Error | null,
): number | false {
  if (error instanceof ApiError && error.status === 404) return false
  return run && isTerminalStatus(run.status) ? false : TRACE_REFRESH_INTERVAL_MS
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

export function useOptionalTraceDetail(id: string | undefined) {
  return useQuery<TraceDetail, Error>({
    queryKey: ['optional-trace', id],
    queryFn: () => getTraceDetail(id!),
    enabled: Boolean(id),
    retry: false,
    staleTime: 30_000,
  })
}

export function useAgentRunDetail({
  runId,
  traceId,
}: {
  runId?: string
  traceId?: string
}) {
  const identity = runId ? { kind: 'run', id: runId } : traceId ? { kind: 'trace', id: traceId } : null
  return useQuery<AgentRunDetail, Error>({
    queryKey: ['agent-run-detail', identity],
    queryFn: () => runId ? getAgentRunDetail(runId) : getAgentRunDetailByTrace(traceId!),
    enabled: Boolean(identity),
    retry: shouldRetryAgentRunDetail,
    retryDelay: (failureCount) => Math.min(300 * 2 ** failureCount, 1_200),
    staleTime: 30_000,
    refetchInterval: (query) => agentRunDetailRefetchInterval(
      query.state.data,
      query.state.error,
    ),
    refetchIntervalInBackground: false,
  })
}

export function useContextModelInvocations({
  runId,
  traceId,
}: {
  runId?: string
  traceId?: string
}) {
  const identity = runId ? { kind: 'run', id: runId } : traceId ? { kind: 'trace', id: traceId } : null
  return useQuery<ContextModelInvocation[], Error>({
    queryKey: ['context-evidence', identity],
    queryFn: () => runId ? getRunModelInvocations(runId) : getTraceModelInvocations(traceId!),
    enabled: Boolean(identity),
    retry: shouldRetryContextEvidence,
    retryDelay: (failureCount) => Math.min(300 * 2 ** failureCount, 1_200),
    staleTime: 30_000,
  })
}

export function useTraceModelInvocations(id: string | undefined) {
  return useContextModelInvocations({ traceId: id })
}

export function useRunModelInvocations(id: string | undefined) {
  return useContextModelInvocations({ runId: id })
}

export function usePlaygroundTraces(
  projectId?: string,
  agentId?: string,
  sessionId?: string | null,
  environment?: string | null,
  liveObservationActive = false,
) {
  return useQuery<Trace[]>({
    queryKey: ['agent-runs', { projectId, agentId, sessionId, environment }],
    queryFn: async () => {
      const runs = await getAgentRuns({
        projectId: projectId!,
        agentId: agentId!,
        sessionId,
        environment,
      })
      return runs.map((run): Trace => ({
        id: run.trace_id,
        project_id: run.project_id,
        agent_id: run.agent_id,
        session_id: run.session_id ?? undefined,
        status: run.status,
        provider: run.provider ?? undefined,
        model: run.model ?? undefined,
        total_latency_ms: run.latency_ms ?? undefined,
        total_cost_usd: run.usage?.cost_usd ?? null,
        error: run.failure_detail ?? run.failure_code ?? undefined,
        data: {
          execution_context: run.environment,
          agent_run_id: run.id,
          input_message: run.input_message,
          origin: run.origin,
          input_tokens: run.usage?.input_tokens ?? null,
          output_tokens: run.usage?.output_tokens ?? null,
          total_tokens: run.usage?.total_tokens ?? null,
          cost_usd: run.usage?.cost_usd ?? null,
        },
        started_at: run.started_at,
        ended_at: run.completed_at,
        created_at: run.created_at ?? run.started_at ?? undefined,
      }))
    },
    enabled: Boolean(projectId) && Boolean(agentId),
    staleTime: 500,
    refetchInterval: (query) => {
      if (liveObservationActive) return false
      return hasActiveTrace(query.state.data) ? TRACE_REFRESH_INTERVAL_MS : false
    },
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
