import { useQuery } from '@tanstack/react-query'
import { getTraces, getTraceDetail } from './api'

export function useTraces(projectId?: string) {
  return useQuery({
    queryKey: ['traces', projectId],
    queryFn: () => getTraces(projectId!),
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
