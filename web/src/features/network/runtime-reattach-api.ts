import { get } from '@/lib/api/client'

export interface ActiveNetworkExecution {
  run_id: string
  execution_id: string
  status: string
  network_session_id: string
  network_id: string
  input_message: string
  created_at?: string | null
}

export async function getActiveNetworkExecution(
  networkSessionId: string,
): Promise<ActiveNetworkExecution | null> {
  return get<ActiveNetworkExecution | null>('/network/executions/active', {
    params: { network_session_id: networkSessionId },
  })
}
