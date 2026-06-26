import { get } from '@/lib/api/client'
import type { ProjectOverview, ProjectOverviewParams } from './types'

const PROJECT_OVERVIEW_RECENT_LIMIT = 3

export async function getProjectOverview(params: ProjectOverviewParams): Promise<ProjectOverview> {
  return get<ProjectOverview>(`/core/projects/${params.projectId}/overview`, {
    params: {
      environment: params.environment,
      from: params.from,
      to: params.to,
      bucket: params.bucket,
      recent_limit: params.recentLimit ?? PROJECT_OVERVIEW_RECENT_LIMIT,
    },
  })
}
