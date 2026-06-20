export type DashboardEnvironment = 'all' | 'draft' | 'staging' | 'production'
export type DashboardBucket = 'hour' | 'day'
export type DashboardRangePreset = '24h' | '7d' | '30d'

export interface ProjectOverviewSummary {
  active_agents: number
  production_agents: number
  requests: number
  request_change_percent: number | null
  avg_latency_ms: number | null
  p95_latency_ms: number | null
  success_rate: number | null
  failed_requests: number
  cost_usd: number | null
  unknown_cost_count: number
}

export interface ProjectOverviewTimeseriesPoint {
  bucket_start: string
  requests: number
  success: number
  failed: number
  avg_latency_ms: number | null
  p95_latency_ms: number | null
  input_tokens: number
  output_tokens: number
  cost_usd: number | null
  unknown_cost_count: number
}

export interface ProjectEnvironmentDistribution {
  draft: number
  staging: number
  production: number
}

export interface ProjectOverviewRelease {
  id: string
  agent_id: string
  agent_name: string
  version: string
  environment: Exclude<DashboardEnvironment, 'all'>
  created_at: string
  promoted_at: string | null
}

export interface ProjectOverviewTrace {
  id: string
  agent_id: string | null
  agent_name: string | null
  environment: Exclude<DashboardEnvironment, 'all'> | null
  status: string
  latency_ms: number | null
  total_tokens: number | null
  cost_usd: number | null
  cost_known: boolean
  started_at: string | null
}

export interface ProjectKnowledgeSummary {
  collections: number
  documents: number
  indexed_documents: number
  failed_documents: number
  storage_bytes: number
  pending_documents: number
}

export interface ProjectToolFailure {
  trace_id: string
  tool_name: string
  occurred_at: string
  error: string | null
}

export interface ProjectToolsSummary {
  total: number
  active: number
  inactive: number
  recent_failures: ProjectToolFailure[]
}

export interface ProjectOverviewCapabilities {
  sessions_jobs: boolean
  ingestion_pipeline: boolean
  activity_feed: boolean
}

export interface ProjectOverview {
  project_id: string
  generated_at: string
  from: string
  to: string
  bucket: DashboardBucket
  environment: DashboardEnvironment
  summary: ProjectOverviewSummary
  timeseries: ProjectOverviewTimeseriesPoint[]
  environment_distribution: ProjectEnvironmentDistribution
  recent_releases: ProjectOverviewRelease[]
  recent_traces: ProjectOverviewTrace[]
  knowledge_summary: ProjectKnowledgeSummary
  tools_summary: ProjectToolsSummary
  capabilities: ProjectOverviewCapabilities
}

export interface ProjectOverviewParams {
  projectId: string
  environment: DashboardEnvironment
  range: DashboardRangePreset
  bucket: DashboardBucket
  from: string
  to: string
  recentLimit?: number
}
