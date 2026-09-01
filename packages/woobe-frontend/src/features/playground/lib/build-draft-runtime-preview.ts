export type DraftRuntimeSource = 'current_draft' | 'draft_unsaved'

interface BuildDraftRuntimePreviewInput {
  projectId: string
  agentId: string
  sessionId: string | null
  activeSource: DraftRuntimeSource
  snapshot: Record<string, unknown>
}

export function buildDraftRuntimePreview({
  projectId,
  agentId,
  sessionId,
  activeSource,
  snapshot,
}: BuildDraftRuntimePreviewInput) {
  return {
    source: activeSource,
    endpoint: '/runtime/ask/stream',
    method: 'POST',
    payload: {
      project_id: projectId,
      agent_id: agentId,
      message: '<message entered in playground chat>',
      session_id: sessionId,
      execution_context: 'playground',
      metadata: {
        client_sent_at: '<runtime timestamp>',
      },
      snapshot_override: snapshot,
    },
  }
}
