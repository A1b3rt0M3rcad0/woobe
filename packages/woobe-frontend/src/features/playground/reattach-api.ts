import { get, post } from '@/lib/api/client'

export interface ActiveAgentRun {
  run_id: string
  status: string
  session_id: string | null
  agent_id: string
  environment: string
  created_at?: string | null
}

const activeCancellationRequests = new Map<string, Promise<void>>()

export async function getActiveAgentRun(sessionId: string): Promise<ActiveAgentRun | null> {
  return get<ActiveAgentRun | null>('/runtime/runs/active', {
    params: { session_id: sessionId },
  })
}

export function cancelAgentRun(runId: string): Promise<void> {
  const existing = activeCancellationRequests.get(runId)
  if (existing) return existing

  const request = post(`/runtime/runs/${runId}/cancel`, {})
    .then(() => undefined)
    .finally(() => {
      if (activeCancellationRequests.get(runId) === request) {
        activeCancellationRequests.delete(runId)
      }
    })

  activeCancellationRequests.set(runId, request)
  return request
}
