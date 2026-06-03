import { get } from '@/lib/api/client'
import type { Trace, TraceDetail } from './types'

export async function getTraces(projectId?: string): Promise<Trace[]> {
  return get<Trace[]>('/observability/traces', { params: { project_id: projectId } })
}

export async function getTraceDetail(traceId: string): Promise<TraceDetail> {
  return get<TraceDetail>(`/observability/traces/${traceId}`)
}
