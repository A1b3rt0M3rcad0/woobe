import { get } from '@/lib/api/client'
import type { DailyUsage } from './types'

export async function getProjectDailyUsage(projectId: string, params?: { limit?: number; offset?: number }): Promise<DailyUsage[]> {
  return get<DailyUsage[]>(`/metering/projects/${projectId}/daily`, { params: params as Record<string, string | number | undefined> })
}
