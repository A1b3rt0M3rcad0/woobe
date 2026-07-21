export type EvaluationTargetType = 'agent' | 'network'
export type EvaluationSourceType = 'draft' | 'staging' | 'release'
export type EvaluationRunStatus =
  | 'queued'
  | 'snapshotting'
  | 'executing'
  | 'judging'
  | 'aggregating'
  | 'completed'
  | 'partially_completed'
  | 'failed'
  | 'cancel_requested'
  | 'cancelled'

export type EvaluationToolRisk = 'low' | 'medium' | 'high'

export interface EvaluationCaseInput {
  name: string
  message: string
  initial_context?: Record<string, unknown>
  expected_contract?: Record<string, unknown>
  severity?: 'low' | 'normal' | 'high' | 'critical'
  weight?: number
  blocking?: boolean
  tags?: string[]
  production_frequency?: number | null
}

export interface EvaluationDatasetVersion {
  id: string
  version: string
  content_hash: string
  change_description: string | null
  created_at: string
}

export interface EvaluationDataset {
  id: string
  project_id: string
  name: string
  description: string
  status: string
  current_version_id: string | null
  current_version: string | null
  content_hash: string | null
  case_count: number
  created_at: string
  updated_at: string
  versions?: EvaluationDatasetVersion[]
  cases?: Array<{
    id: string
    position: number
    name: string
    input_payload: Record<string, unknown>
    initial_context?: Record<string, unknown> | null
    expected_contract: Record<string, unknown>
    severity: string
    weight: number
    blocking: boolean
    tags: string[]
    production_frequency?: number | null
  }>
}

export interface EvaluationSuite {
  id: string
  project_id: string
  name: string
  description: string
  target_type: EvaluationTargetType
  status: string
  current_version_id: string | null
  current_version: string | null
  dataset_version_id: string | null
  judge_provider_model_id: string | null
  judge_config?: Record<string, unknown>
  rubric?: Record<string, unknown>
  deterministic_checks?: Record<string, unknown>
  acceptance_policy?: Record<string, unknown>
  repetition_policy?: Record<string, unknown>
  estimate_defaults?: Record<string, unknown>
  suite_hash?: string | null
  created_at: string
  updated_at: string
}

export interface EvaluationTargetInput {
  target_type: EvaluationTargetType
  source_type: EvaluationSourceType
  entity_id: string
  version_id?: string
}

export interface EvaluationTarget {
  id: string
  side: 'single' | 'candidate' | 'baseline'
  target_type: EvaluationTargetType
  source_type: EvaluationSourceType
  entity_id: string
  environment: string
  agent_release_id: string | null
  network_version_id: string | null
  snapshot_hash: string
  composition_hash: string | null
  display_name: string
  display_version: string
}

export interface EvaluationEstimateScenario {
  provider_cost_usd?: number | null
  latency_ms_per_run?: number | null
  agent_runs?: number | null
}

export interface EvaluationEstimate {
  id: string
  target_id: string
  volume: number
  volume_unit: string
  confidence: string
  observation_summary: Record<string, unknown>
  scenarios: Record<'optimistic' | 'expected' | 'conservative', EvaluationEstimateScenario>
  limitations: string[]
}

export interface EvaluationCheck {
  id: string
  evaluator_key: string
  evaluator_type: string
  dimension: string
  status: string
  score: number | null
  blocking: boolean
  reason: string | null
  evidence?: Record<string, unknown> | null
}

export interface EvaluationTrial {
  id: string
  target_id: string
  side: string
  repetition: number
  pair_key: string
  status: string
  score: number | null
  passed: boolean | null
  trace_id: string | null
  agent_run_id: string | null
  network_execution_id: string | null
  output?: Record<string, unknown> | null
  metrics?: Record<string, unknown> | null
  failure_code?: string | null
  failure_detail?: string | null
  case?: {
    id: string
    name: string
    input_payload: Record<string, unknown>
    initial_context?: Record<string, unknown> | null
    expected_contract: Record<string, unknown>
  } | null
  checks?: EvaluationCheck[]
}

export interface EvaluationRun {
  id: string
  project_id: string
  suite_version_id: string
  mode: 'absolute' | 'comparison'
  status: EvaluationRunStatus
  repetitions: number
  qualification_status: string | null
  overall_score: number | null
  pass_rate: number | null
  aggregate_result: Record<string, any> | null
  estimated_preflight_cost: number | null
  measured_total_cost: number | null
  failure_code: string | null
  failure_detail: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  targets: EvaluationTarget[]
  trials?: EvaluationTrial[]
  judge_calls?: Array<Record<string, any>>
  estimates?: EvaluationEstimate[]
}

export interface EvaluationPreflightTool {
  id: string
  name: string
  risk_level: EvaluationToolRisk
  source: string
}

export interface EvaluationPreflight {
  tools: EvaluationPreflightTool[]
  requires_acknowledgement: boolean
  blocked_high_risk_tool_ids: string[]
  risk_counts: Record<EvaluationToolRisk, number>
}

export interface EvaluationPreview {
  mode: 'absolute' | 'comparison'
  candidate: Record<string, any>
  baseline: Record<string, any> | null
  case_count: number
  repetitions: number
  target_run_count: number
  judge_call_count: number
  judge_provider_model_id: string
  tool_execution_warning: string
  preflight: EvaluationPreflight
  requires_confirmation: boolean
  can_execute: boolean
}

export interface CreateEvaluationRunInput {
  suite_version_id: string
  repetitions: number
  candidate: EvaluationTargetInput
  baseline?: EvaluationTargetInput
  acknowledge_tool_side_effects?: boolean
  approved_high_risk_tool_ids?: string[]
  idempotency_key?: string
}

export interface CreateEvaluationDatasetInput {
  name: string
  description?: string
  change_description?: string
  cases: EvaluationCaseInput[]
}

export interface CreateEvaluationSuiteInput {
  name: string
  description?: string
  target_type: EvaluationTargetType
  dataset_version_id: string
  judge_provider_model_id: string
  judge_config?: Record<string, unknown>
  rubric?: Record<string, unknown>
  deterministic_checks?: Record<string, unknown>
  acceptance_policy?: Record<string, unknown>
  repetition_policy?: Record<string, unknown>
  estimate_defaults?: Record<string, unknown>
}
