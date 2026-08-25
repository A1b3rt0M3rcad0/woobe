import { get } from '@/lib/api/client'

export interface ActiveAgentRun {
  run_id: string
  status: string
  session_id: string | null
  agent_id: string
  environment: string
  created_at?: string | null
}

export async function getActiveAgentRun(sessionId: string): Promise<ActiveAgentRun | null> {
  return get<ActiveAgentRun | null>('/runtime/runs/active', {
    params: { session_id: sessionId },
  })
}
