import { get, post } from '@/lib/api/client'
import type { AgentRunDetail, ContextModelInvocation, Trace, TraceDetail } from './types'

export interface GetTracesParams {
  projectId?: string
  agentId?: string
  sessionId?: string
  networkId?: string
}

export interface AgentRunSummary {
  id: string
  trace_id: string
  project_id: string
  agent_id: string
  session_id: string | null
  environment: string
  origin: string
  status: string
  input_message: string
  provider: string | null
  model: string | null
  usage: {
    input_tokens?: number | null
    output_tokens?: number | null
    total_tokens?: number | null
    cost_usd?: number | null
  } | null
  failure_code: string | null
  failure_detail: string | null
  latency_ms: number | null
  started_at: string | null
  completed_at: string | null
  created_at: string | null
  updated_at: string | null
}

export async function getTraces(params?: GetTracesParams): Promise<Trace[]> {
  return get<Trace[]>('/observability/traces', {
    params: {
      project_id: params?.projectId,
      agent_id: params?.agentId,
      session_id: params?.sessionId,
      network_id: params?.networkId,
    },
  })
}

export async function getAgentRuns(params: {
  projectId: string
  agentId: string
  sessionId?: string | null
  environment?: string | null
  limit?: number
}): Promise<AgentRunSummary[]> {
  return get<AgentRunSummary[]>('/runtime/runs', {
    params: {
      project_id: params.projectId,
      agent_id: params.agentId,
      session_id: params.sessionId ?? undefined,
      environment: params.environment ?? undefined,
      limit: params.limit ?? 100,
    },
  })
}

export async function getTraceDetail(traceId: string): Promise<TraceDetail> {
  return get<TraceDetail>(`/observability/traces/${traceId}`)
}

export async function getAgentRunDetail(runId: string): Promise<AgentRunDetail> {
  return get<AgentRunDetail>(`/runtime/runs/${runId}`)
}

export async function getAgentRunDetailByTrace(traceId: string): Promise<AgentRunDetail> {
  return get<AgentRunDetail>(`/runtime/runs/by-trace/${traceId}`)
}

export async function getTraceModelInvocations(traceId: string): Promise<ContextModelInvocation[]> {
  return get<ContextModelInvocation[]>(`/runtime/runs/by-trace/${traceId}/model-invocations`)
}

export async function getRunModelInvocations(runId: string): Promise<ContextModelInvocation[]> {
  return get<ContextModelInvocation[]>(`/runtime/runs/${runId}/model-invocations`)
}

export interface CreateAskJobParams {
  project_id: string
  agent_id: string
  message: string
  session_id?: string | null
}

export interface AskJobResponse {
  job_id: string
  status: string
  result?: Record<string, unknown> | null
  error?: string | null
  trace_id?: string | null
  created_at?: string | null
  started_at?: string | null
  completed_at?: string | null
}

export async function createAskJob(params: CreateAskJobParams): Promise<{ job_id: string; status: string }> {
  return post<{ job_id: string; status: string }>('/runtime/ask/jobs', params)
}

export async function getAskJob(jobId: string): Promise<AskJobResponse> {
  return get<AskJobResponse>(`/runtime/ask/jobs/${jobId}`)
}
