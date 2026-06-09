import { get } from '@/lib/api/client'
import type { Trace, TraceDetail } from './types'

export interface GetTracesParams {
  projectId?: string
  agentId?: string
  sessionId?: string
}

export async function getTraces(params?: GetTracesParams): Promise<Trace[]> {
  return get<Trace[]>('/observability/traces', {
    params: {
      project_id: params?.projectId,
      agent_id: params?.agentId,
      session_id: params?.sessionId,
    },
  })
}

export async function getTraceDetail(traceId: string): Promise<TraceDetail> {
  return get<TraceDetail>(`/observability/traces/${traceId}`)
}
