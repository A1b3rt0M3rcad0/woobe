import { get } from '@/lib/api/client'
import type { Environment } from './components/networkWorkspaceTypes'

export interface ActiveNetworkExecution {
  run_id: string
  execution_id: string
  status: string
  network_session_id: string
  network_id: string
  input_message: string
  created_at?: string | null
}

export async function getActiveNetworkExecution(input: {
  networkSessionId?: string | null
  networkId?: string | null
  environment?: Environment
}): Promise<ActiveNetworkExecution | null> {
  return get<ActiveNetworkExecution | null>('/network/executions/active', {
    params: {
      network_session_id: input.networkSessionId ?? undefined,
      network_id: input.networkId ?? undefined,
      environment: input.environment,
    },
  })
}
