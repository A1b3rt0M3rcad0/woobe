import { useQuery } from '@tanstack/react-query'
import { getTraces, getTraceDetail, getAskJob, type AskJobResponse, type GetTracesParams } from './api'

export function useTraces(projectId?: string) {
  return useQuery({
    queryKey: ['traces', { projectId }],
    queryFn: () => getTraces({ projectId }),
    enabled: Boolean(projectId),
  })
}

export function useTraceDetail(id: string | undefined) {
  return useQuery({
    queryKey: ['trace', id],
    queryFn: () => getTraceDetail(id!),
    enabled: Boolean(id),
  })
}

export function usePlaygroundTraces(
  projectId?: string,
  agentId?: string,
  sessionId?: string | null,
) {
  return useQuery({
    queryKey: ['traces', { projectId, agentId, sessionId }],
    queryFn: () =>
      getTraces({
        projectId,
        agentId: sessionId ? undefined : agentId,
        sessionId: sessionId ?? undefined,
      } as GetTracesParams),
    enabled: Boolean(projectId) && Boolean(sessionId),
  })
}

export function useAskJob(jobId: string | undefined | null) {
  return useQuery({
    queryKey: ['askJob', jobId],
    queryFn: () => getAskJob(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const data = query.state.data as AskJobResponse | undefined
      if (!data) return 2000
      if (data.status === 'completed' || data.status === 'failed') return false
      return 2000
    },
  })
}
