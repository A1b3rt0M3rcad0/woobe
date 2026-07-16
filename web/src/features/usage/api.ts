import { get } from '@/lib/api/client'
import type { DailyUsage, ProjectUsage, ProjectUsageParams } from './types'

export async function getProjectUsage(params: ProjectUsageParams): Promise<ProjectUsage> {
  const { projectId, ...query } = params
  return get<ProjectUsage>(`/metering/projects/${projectId}/usage`, {
    params: query as Record<string, string | number | undefined>,
  })
}

export async function getProjectDailyUsage(
  projectId: string,
  params?: { limit?: number; offset?: number },
): Promise<DailyUsage[]> {
  return get<DailyUsage[]>(`/metering/projects/${projectId}/daily`, {
    params: params as Record<string, string | number | undefined>,
  })
}
