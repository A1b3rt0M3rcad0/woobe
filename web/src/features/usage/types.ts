export type UsageBucket = 'hour' | 'day'
export type UsageEnvironment = 'all' | 'draft' | 'staging' | 'production'
export type UsageGroupBy = 'agent' | 'model' | 'provider' | 'environment' | 'release'
export type UsageRange = '24h' | '7d' | '30d' | '90d'

export interface ProjectUsageParams {
  projectId: string
  from: string
  to: string
  bucket: UsageBucket
  environment: UsageEnvironment
  group_by: UsageGroupBy
  agent_id?: string
  provider_model_id?: string
  release_id?: string
  top_limit?: number
}

export interface ProjectUsageSummary {
  runtime_requests: number
  successful_requests: number
  failed_requests: number
  cancelled_requests: number
  llm_calls: number
  input_tokens: number
  output_tokens: number
  known_cost_usd: number | null
  priced_requests: number
  partial_cost_requests: number
  unpriced_requests: number
  cost_coverage_percent: number | null
  cost_per_priced_request: number | null
  tokens_per_request: number | null
  failed_spend_usd: number
  request_change_percent: number | null
  cost_change_percent: number | null
}

export interface ProjectUsageTimeseriesPoint {
  bucket_start: string
  runtime_requests: number
  successful_requests: number
  failed_requests: number
  llm_calls: number
  input_tokens: number
  output_tokens: number
  known_cost_usd: number | null
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
  runtime_requests: number
  successful_requests: number
  llm_calls: number
  input_tokens: number
  output_tokens: number
  cost_per_priced_request: number | null
  cost_coverage_percent: number | null
}

export interface ProjectUsageExecution {
  trace_id: string
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
  known_cost_usd: number | null
  cost_status: string
  started_at: string | null
}

export interface ProjectUsageDataQuality {
  fully_priced_requests: number
  partial_requests: number
  unpriced_requests: number
  missing_model_attribution: number
  missing_release_attribution: number
  aggregation_lag_seconds: number | null
}

export interface ProjectUsage {
  project_id: string
  generated_at: string
  data_through: string | null
  from: string
  to: string
  bucket: UsageBucket
  environment: UsageEnvironment
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
