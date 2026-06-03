export interface Trace {
  id: string
  project_id: string
  agent_id?: string
  session_id?: string
  status: string
  provider?: string
  model?: string
  fallback_used?: boolean
  total_latency_ms?: number
  total_cost_usd?: number
  error?: string
  data?: Record<string, unknown>
  created_at?: string
}

export interface TraceEvent {
  id: string
  trace_id: string
  event_type: string
  latency_ms?: number
  cost_usd?: number
  payload?: Record<string, unknown>
  payload_ref?: string
  created_at?: string
}

export interface TraceDetail {
  trace: Trace
  events: TraceEvent[]
}
