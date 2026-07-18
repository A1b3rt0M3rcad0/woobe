import { useQuery } from '@tanstack/react-query'
import { getProjectOverview } from './api'
import type {
  DashboardBucket,
  DashboardEnvironment,
  DashboardRangePreset,
  ProjectOverviewParams,
} from './types'

export const PROJECT_OVERVIEW_STALE_TIME_MS = 15_000
export const PROJECT_OVERVIEW_REFETCH_INTERVAL_MS = 60_000
export const PROJECT_OVERVIEW_RECENT_LIMIT = 5

interface ProjectOverviewQueryIdentity {
  projectId: string
  environment: DashboardEnvironment
  range: DashboardRangePreset
  recentLimit?: number
}

export function projectOverviewQueryKey(params: ProjectOverviewQueryIdentity) {
  return [
    'project-overview',
    params.projectId,
    params.environment,
    params.range,
    params.recentLimit ?? PROJECT_OVERVIEW_RECENT_LIMIT,
  ] as const
}

export function resolveOverviewWindow(
  range: DashboardRangePreset,
  now: Date = new Date(),
): Pick<ProjectOverviewParams, 'range' | 'bucket' | 'from' | 'to'> {
  const durationMs: Record<DashboardRangePreset, number> = {
    '24h': 24 * 60 * 60 * 1000,
    '7d': 7 * 24 * 60 * 60 * 1000,
    '30d': 30 * 24 * 60 * 60 * 1000,
  }
  return {
    range,
    bucket: range === '24h' ? 'hour' : 'day',
    from: new Date(now.getTime() - durationMs[range]).toISOString(),
    to: now.toISOString(),
  }
}

export interface UseProjectOverviewOptions {
  projectId: string | undefined
  environment: DashboardEnvironment
  range: DashboardRangePreset
  recentLimit?: number
}

export function useProjectOverview(options: UseProjectOverviewOptions) {
  const identity: ProjectOverviewQueryIdentity = {
    projectId: options.projectId ?? '',
    environment: options.environment,
    range: options.range,
    recentLimit: options.recentLimit,
  }

  return useQuery({
    queryKey: projectOverviewQueryKey(identity),
    queryFn: () => {
      const window = resolveOverviewWindow(options.range)
      return getProjectOverview({
        projectId: options.projectId ?? '',
        environment: options.environment,
        recentLimit: options.recentLimit ?? PROJECT_OVERVIEW_RECENT_LIMIT,
        ...window,
      })
    },
    enabled: Boolean(options.projectId),
    placeholderData: (previousData) => previousData,
    staleTime: PROJECT_OVERVIEW_STALE_TIME_MS,
    refetchInterval: PROJECT_OVERVIEW_REFETCH_INTERVAL_MS,
    refetchOnWindowFocus: true,
  })
}

export type { DashboardBucket }
