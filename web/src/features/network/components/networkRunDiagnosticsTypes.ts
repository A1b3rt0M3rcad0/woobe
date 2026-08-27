export interface NetworkContextSourceSummary {
  units: number | null
  share: number | null
}

export interface NetworkContextAgentSummary {
  agent_id: string
  agent_run_count: number
  model_invocation_count: number
  input_units: number | null
  peak_utilization: number | null
  delegation_units: number | null
  delegation_share: number | null
  run_ids: string[]
}

export interface NetworkContextOverview {
  telemetry_status: 'complete' | 'partial' | 'unknown'
  model_invocation_count: number
  input_units: number | null
  input_measurement: 'reported' | 'mixed' | 'estimated' | 'unknown'
  peak_utilization: number | null
  median_utilization: number | null
  budget_unknown_count: number
  health_warning_count: number
  compaction_saving_units: number | null
  truncation_count: number
  selection_ratio: number | null
  source_units: Record<string, NetworkContextSourceSummary>
  agents: NetworkContextAgentSummary[]
}

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
  context: NetworkContextOverview
}
