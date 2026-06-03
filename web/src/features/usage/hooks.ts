import { useQuery } from '@tanstack/react-query'
import { getProjectDailyUsage } from './api'

export function useProjectUsage(projectId: string | undefined) {
  return useQuery({
    queryKey: ['project-usage', projectId],
    queryFn: () => getProjectDailyUsage(projectId!),
    enabled: Boolean(projectId),
  })
}
