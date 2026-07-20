export type ReleaseChangeKind = 'compatibility' | 'feature' | 'change'
export type ReleaseRuntimeTarget = 'playground' | 'staging' | 'production'
export type ReleaseStatus = 'draft' | 'staging' | 'released' | 'production' | 'archived' | 'rolled_back'

export type AgentRelease = {
  id: string
  project_id: string
  agent_id: string
  version: string
  status: ReleaseStatus
  name?: string | null
  model?: string | null
  provider?: string | null
  promoted_at?: string | null
  created_at?: string | null
}

export function releaseToRuntimePayload(target: ReleaseRuntimeTarget, releaseId?: string | null): Record<string, unknown> {
  if (target === 'production') return { execution_context: 'production' }
  if (target === 'staging') return { execution_context: 'staging' }
  return releaseId
    ? { execution_context: 'playground', loaded_release_id: releaseId }
    : { execution_context: 'playground' }
}
