import { useQuery } from '@tanstack/react-query'
import { getProjectDailyUsage, getProjectUsage } from './api'
import type { ProjectUsageParams, UsageRange } from './types'

export const PROJECT_USAGE_STALE_TIME_MS = 15_000
export const PROJECT_USAGE_REFETCH_INTERVAL_MS = 60_000

export function resolveUsageWindow(range: UsageRange, now: Date = new Date()) {
  const durationMs: Record<UsageRange, number> = {
    '24h': 24 * 60 * 60 * 1000,
    '7d': 7 * 24 * 60 * 60 * 1000,
    '30d': 30 * 24 * 60 * 60 * 1000,
    '90d': 90 * 24 * 60 * 60 * 1000,
  }
  return {
    from: new Date(now.getTime() - durationMs[range]).toISOString(),
    to: now.toISOString(),
    bucket: range === '24h' ? ('hour' as const) : ('day' as const),
  }
}

export function useProjectUsage(params: ProjectUsageParams | undefined) {
  return useQuery({
    queryKey: ['project-usage', params],
    queryFn: () => getProjectUsage(params!),
    enabled: Boolean(params?.projectId),
    staleTime: PROJECT_USAGE_STALE_TIME_MS,
    refetchInterval: PROJECT_USAGE_REFETCH_INTERVAL_MS,
    refetchOnWindowFocus: true,
  })
}

export function useProjectDailyUsage(projectId: string | undefined) {
  return useQuery({
    queryKey: ['project-daily-usage', projectId],
    queryFn: () => getProjectDailyUsage(projectId!),
    enabled: Boolean(projectId),
  })
}
