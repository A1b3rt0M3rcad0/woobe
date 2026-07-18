export type DashboardEnvironment = 'all' | 'draft' | 'staging' | 'production'
export type DashboardBucket = 'hour' | 'day'
export type DashboardRangePreset = '24h' | '7d' | '30d'
export type OverviewRunSource = 'playground' | 'api' | 'job' | 'network' | 'event' | 'schedule' | 'unknown'
export type OverviewChangeResource = 'agent' | 'network'
export type OverviewChangeAction = 'draft_updated' | 'staged' | 'released' | 'rolled_back' | 'reactivated'

export interface ProjectOverviewSummary {
  active_agents: number
  production_agents: number
  network_count: number
  staging_networks: number
  production_networks: number

  agent_runs: number
  direct_agent_runs: number
  network_agent_runs: number
  terminal_agent_runs: number
  successful_agent_runs: number
  completed_with_issues_agent_runs: number
  failed_agent_runs: number
  timed_out_agent_runs: number
  cancelled_agent_runs: number
  running_agent_runs: number
  agent_run_change_percent: number | null
  avg_agent_run_duration_ms: number | null
  p95_agent_run_duration_ms: number | null
  agent_run_success_rate: number | null
  agent_run_error_rate: number | null
  agent_run_cost_usd: number | null
  priced_agent_runs: number
  unknown_agent_run_cost_count: number

  network_runs: number
  terminal_network_runs: number
  successful_network_runs: number
  completed_with_issues_network_runs: number
  failed_network_runs: number
  timed_out_network_runs: number
  uncertain_network_runs: number
  cancelled_network_runs: number
  running_network_runs: number
  network_run_success_rate: number | null
  network_run_error_rate: number | null
  avg_network_run_duration_ms: number | null
  p95_network_run_duration_ms: number | null
  avg_agent_runs_per_network_run: number | null

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
  agent_runs: number
  agent_run_success: number
  agent_run_completed_with_issues: number
  agent_run_failed: number
  agent_run_timed_out: number
  agent_run_cancelled: number
  agent_run_running: number
  agent_run_success_rate: number | null
  avg_agent_run_duration_ms: number | null
  p95_agent_run_duration_ms: number | null
  network_runs: number
  network_run_success: number
  network_run_completed_with_issues: number
  network_run_failed: number
  network_run_timed_out: number
  network_run_uncertain: number
  network_run_cancelled: number
  network_run_running: number
  network_run_success_rate: number | null
  avg_network_run_duration_ms: number | null
  input_tokens: number
  output_tokens: number
  cost_usd: number | null
  unknown_cost_count: number
  requests: number
  success: number
  failed: number
  avg_latency_ms: number | null
  p95_latency_ms: number | null
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
  release_notes: string | null
  created_at: string
  promoted_at: string | null
}

export interface ProjectOverviewNetworkRelease {
  id: string
  network_id: string
  network_name: string
  version: string
  environment: 'staging' | 'production'
  change_description: string | null
  activation_kind: string | null
  rollback_of_version_id: string | null
  agent_count: number
  created_at: string
}

export interface ProjectOverviewChange {
  id: string
  resource_type: OverviewChangeResource
  resource_id: string
  resource_name: string
  environment: Exclude<DashboardEnvironment, 'all'>
  action: OverviewChangeAction
  version: string | null
  revision: number | null
  description: string | null
  occurred_at: string
  immutable: boolean
}

export interface ProjectOverviewTrace {
  id: string
  agent_id: string | null
  agent_name: string | null
  environment: Exclude<DashboardEnvironment, 'all'> | 'playground' | null
  source?: OverviewRunSource
  status: string
  latency_ms: number | null
  total_tokens: number | null
  cost_usd: number | null
  cost_known: boolean
  started_at: string | null
}

export interface ProjectOverviewNetworkRun {
  id: string
  network_id: string
  network_name: string
  environment: Exclude<DashboardEnvironment, 'all'>
  status: string
  duration_ms: number | null
  cost_usd: number | null
  cost_known: boolean
  priced_agent_runs: number
  total_agent_runs: number
  unknown_cost_count: number
  root_trace_id: string | null
  started_at: string | null
  completed_at: string | null
}

export interface ProjectOverviewIssueEntity {
  entity_id: string | null
  name: string
  failure_count: number
}

export interface ProjectOverviewFailureCode {
  code: string
  failure_count: number
}

export interface ProjectOverviewFailurePeak {
  bucket_start: string
  failure_count: number
}

export interface ProjectOverviewOperationalIssues {
  top_agent_failures: ProjectOverviewIssueEntity[]
  top_network_failures: ProjectOverviewIssueEntity[]
  top_failure_codes: ProjectOverviewFailureCode[]
  failure_peak: ProjectOverviewFailurePeak | null
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
  recent_network_releases: ProjectOverviewNetworkRelease[]
  recent_changes: ProjectOverviewChange[]
  recent_traces: ProjectOverviewTrace[]
  recent_network_runs: ProjectOverviewNetworkRun[]
  operational_issues: ProjectOverviewOperationalIssues
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
