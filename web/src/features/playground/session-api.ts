import { get } from '@/lib/api/client'
import type { RuntimeEnvironment } from '@/features/agents/types'
import type { SessionListItem, SessionListPage } from './types'

export async function getAgentSessionsByEnvironment(
  agentId: string,
  projectId: string,
  environment: RuntimeEnvironment,
  params: { limit?: number; cursor?: string | null } = {},
): Promise<SessionListPage> {
  const response = await get<SessionListPage | SessionListItem[]>(`/runtime/agents/${agentId}/sessions`, {
    params: {
      project_id: projectId,
      environment,
      limit: params.limit,
      cursor: params.cursor ?? undefined,
    },
  })

  if (Array.isArray(response)) {
    return {
      items: response,
      next_cursor: null,
      has_next: false,
    }
  }

  return response
}
