import { get, post } from '@/lib/api/client'
import type { Trace, TraceDetail } from './types'

export interface GetTracesParams {
  projectId?: string
  agentId?: string
  sessionId?: string
  networkId?: string
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

export async function getTraceDetail(traceId: string): Promise<TraceDetail> {
  return get<TraceDetail>(`/observability/traces/${traceId}`)
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
