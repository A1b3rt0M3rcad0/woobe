export type UsageBucket = 'hour' | 'day'
export type UsageEnvironment = 'all' | 'draft' | 'staging' | 'production'
export type UsageOperation = 'all' | 'agent' | 'network'
export type UsageGroupBy = 'agent' | 'network' | 'model' | 'provider' | 'environment' | 'release'
export type UsageRange = '24h' | '7d' | '30d' | '90d'
export type UsageRunType = 'agent' | 'network'

export interface ProjectUsageParams {
  projectId: string
  from: string
  to: string
  bucket: UsageBucket
  environment: UsageEnvironment
  operation: UsageOperation
  group_by: UsageGroupBy
  network_id?: string
  agent_id?: string
  provider_model_id?: string
  release_id?: string
  top_limit?: number
}

export interface ProjectUsageSummary {
  known_cost_usd: number | null
  failed_spend_usd: number
  cost_change_percent: number | null
  cost_coverage_percent: number | null

  agent_runs: number
  direct_agent_runs: number
  network_agent_runs: number
  successful_agent_runs: number
  failed_agent_runs: number
  cancelled_agent_runs: number
  priced_agent_runs: number
  partial_cost_agent_runs: number
  unpriced_agent_runs: number
  agent_run_change_percent: number | null
  agent_run_success_rate: number | null
  cost_per_priced_agent_run: number | null
  median_agent_run_cost_usd: number | null
  p95_agent_run_cost_usd: number | null

  network_runs: number
  successful_network_runs: number
  failed_network_runs: number
  cancelled_network_runs: number
  priced_network_runs: number
  partial_cost_network_runs: number
  unpriced_network_runs: number
  network_run_change_percent: number | null
  network_run_success_rate: number | null
  network_run_cost_usd: number | null
  cost_per_priced_network_run: number | null
  median_network_run_cost_usd: number | null
  p95_network_run_cost_usd: number | null
  avg_agent_runs_per_network_run: number | null

  llm_calls: number
  input_tokens: number
  output_tokens: number

  runtime_requests: number
  successful_requests: number
  failed_requests: number
  cancelled_requests: number
  priced_requests: number
  partial_cost_requests: number
  unpriced_requests: number
  cost_per_priced_request: number | null
  tokens_per_request: number | null
  request_change_percent: number | null
}

export interface ProjectUsageTimeseriesPoint {
  bucket_start: string
  agent_runs: number
  direct_agent_runs: number
  network_agent_runs: number
  successful_agent_runs: number
  failed_agent_runs: number
  network_runs: number
  successful_network_runs: number
  failed_network_runs: number
  known_cost_usd: number | null
  network_run_cost_usd: number | null
  agent_cost_per_run: number | null
  network_cost_per_run: number | null
  llm_calls: number
  input_tokens: number
  output_tokens: number
  priced_agent_runs: number
  partial_cost_agent_runs: number
  unpriced_agent_runs: number
  runtime_requests: number
  successful_requests: number
  failed_requests: number
  priced_requests: number
  partial_cost_requests: number
  unpriced_requests: number
}

export interface ProjectUsageComposition {
  input_tokens: number
  output_tokens: number
  embedding_tokens: number
  tool_calls: number
  vector_queries: number
}

export interface ProjectUsageBreakdownRow {
  key: string
  label: string
  known_cost_usd: number | null
  share_percent: number
  agent_runs: number
  network_runs: number
  successful_agent_runs: number
  llm_calls: number
  input_tokens: number
  output_tokens: number
  cost_per_priced_agent_run: number | null
  cost_coverage_percent: number | null
  runtime_requests: number
  successful_requests: number
  cost_per_priced_request: number | null
}

export interface ProjectUsageExecution {
  run_id: string
  run_type: UsageRunType
  trace_id?: string | null
  network_id?: string | null
  network_name?: string | null
  network_execution_id?: string | null
  network_version_id?: string | null
  agent_id: string | null
  agent_name: string | null
  environment: string | null
  release_id: string | null
  release_version: string | null
  provider: string | null
  model: string | null
  status: string
  llm_calls: number
  input_tokens: number
  output_tokens: number
  tool_calls: number
  agent_runs_count: number
  duration_ms: number | null
  known_cost_usd: number | null
  cost_status: string
  started_at: string | null
}

export interface ProjectUsageDataQuality {
  fully_priced_agent_runs: number
  partial_agent_runs: number
  unpriced_agent_runs: number
  fully_priced_network_runs: number
  partial_network_runs: number
  unpriced_network_runs: number
  missing_model_attribution: number
  missing_release_attribution: number
  aggregation_lag_seconds: number | null
  fully_priced_requests: number
  partial_requests: number
  unpriced_requests: number
}

export interface ProjectUsage {
  project_id: string
  generated_at: string
  data_through: string | null
  from: string
  to: string
  bucket: UsageBucket
  environment: UsageEnvironment
  operation: UsageOperation
  group_by: UsageGroupBy
  summary: ProjectUsageSummary
  timeseries: ProjectUsageTimeseriesPoint[]
  composition: ProjectUsageComposition
  breakdown: ProjectUsageBreakdownRow[]
  top_executions: ProjectUsageExecution[]
  data_quality: ProjectUsageDataQuality
}

export interface DailyUsage {
  project_id: string
  day: string
  requests: number
  input_tokens: number
  output_tokens: number
  cost_usd: number
}
