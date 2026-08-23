export interface NetworkRunDiagnostics {
  schema_version: 1
  execution_id: string
  status: string
  network_wall_latency_ms: number | null
  agent_work_latency_ms: number | null
  llm_runtime_latency_ms: number | null
  tool_work_latency_ms: number | null
  prepare_latency_ms: number | null
  persistence_latency_ms: number | null
  orchestration_latency_ms: number | null
  agent_run_count: number
  delegation_count: number
  max_depth: number
  max_fan_out: number
  llm_call_count: number
  tool_call_count: number
  successful_tool_calls: number
  failed_tool_calls: number
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  usage_complete: boolean
  cost_usd: number | null
  cost_status: 'known' | 'partial' | 'unknown'
  fallback_count: number
  source_count: number
  telemetry_status: 'complete' | 'partial' | 'unknown'
}
