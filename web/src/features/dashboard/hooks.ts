import { useMemo } from 'react'
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

export function projectOverviewQueryKey(params: ProjectOverviewParams) {
  return [
    'project-overview',
    params.projectId,
    params.environment,
    params.range,
    params.bucket,
    params.from,
    params.to,
    params.recentLimit ?? 5,
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
  now?: Date
  recentLimit?: number
}

export function useProjectOverview(options: UseProjectOverviewOptions) {
  const anchorTimestamp = options.now?.getTime()
  const window = useMemo(
    () => resolveOverviewWindow(options.range, options.now),
    [options.range, anchorTimestamp],
  )
  const params: ProjectOverviewParams = {
    projectId: options.projectId ?? '',
    environment: options.environment,
    recentLimit: options.recentLimit,
    ...window,
  }

  return useQuery({
    queryKey: projectOverviewQueryKey(params),
    queryFn: () => getProjectOverview(params),
    enabled: Boolean(options.projectId),
    staleTime: PROJECT_OVERVIEW_STALE_TIME_MS,
    refetchInterval: PROJECT_OVERVIEW_REFETCH_INTERVAL_MS,
    refetchOnWindowFocus: true,
  })
}

export type { DashboardBucket }
