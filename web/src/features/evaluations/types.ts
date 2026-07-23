export type EvaluationTargetType = 'agent' | 'network'
export type EvaluationSourceType = 'draft' | 'staging' | 'release'
export type EvaluationCaseType = 'success' | 'refusal' | 'handled_error' | 'expected_failure'
export type EvaluationInteractionMode = 'single_turn' | 'session'
export type EvaluationTestStructure = 'single_turn' | 'session' | 'mixed'
export type SuiteAuthoringSource = 'manual' | 'json_import' | 'ai_generated'
export type EvaluationRunMode = 'absolute' | 'comparison' | 'model_experiment'
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

export interface ExpectedOutcome {
  type: EvaluationCaseType
  allowed_failure_origins?: string[]
  allowed_failure_stages?: string[]
  allowed_failure_codes?: string[]
  required_behavior?: string[]
  forbidden_behavior?: string[]
}

export interface EvaluationSessionTurnInput {
  position?: number
  message: string
  input_payload?: { message: string }
  expected_behavior?: string[]
  forbidden_behavior?: string[]
}

export interface EvaluationCaseInput {
  name: string
  case_type?: EvaluationCaseType
  interaction_mode?: EvaluationInteractionMode
  message: string
  turns?: EvaluationSessionTurnInput[]
  initial_context?: Record<string, unknown>
  expected_outcome?: ExpectedOutcome
  expected_contract?: Record<string, any>
  severity?: 'low' | 'normal' | 'high' | 'critical'
  weight?: number
  blocking?: boolean
  tags?: string[]
  production_frequency?: number | null
}

export interface EvaluatorSuiteDraft {
  schema_version: number
  suite?: {
    suggested_name?: string
    description?: string
    objective?: string
  }
  coverage?: Record<string, number>
  cases: EvaluationCaseInput[]
}

export interface SuiteValidationIssue {
  path?: string
  code?: string
  message: string
  positions?: number[]
}

export interface SuiteValidationReference {
  mode: 'generic' | 'target_bound'
  target_type?: EvaluationTargetType
  source_type?: EvaluationSourceType
  entity_id?: string
  display_name?: string
  display_version?: string
  snapshot_hash?: string | null
  context_hash?: string | null
}

export interface SuiteValidationResult {
  valid: boolean
  errors: SuiteValidationIssue[]
  warnings: SuiteValidationIssue[]
  coverage: Record<string, number>
  interaction_coverage?: Record<EvaluationInteractionMode, number>
  case_count: number
  cases: EvaluationCaseInput[]
  reference?: SuiteValidationReference
}

export interface SuiteContextPreview {
  target: {
    target_type: EvaluationTargetType
    source_type: EvaluationSourceType
    entity_id: string
    display_name: string
    display_version: string
    snapshot_hash: string
  }
  context_hash: string
  context_budget: {
    estimated_input_tokens: number
    maximum_input_tokens: number
    reserved_output_tokens: number
    safety_margin_tokens: number
    truncation_applied: boolean
    truncated_sections: string[]
    preserved_sections: string[]
    estimation_strategy: string
  }
  context_sections: string[]
  reserved_output_tokens: number
  context_window: number
  estimated_cost_usd: number | null
  cost_status: string
  cost_reason?: string | null
}

export interface GenerateSuiteDraftInput {
  target: EvaluationTargetInput
  generator_provider_model_id: string
  objective: string
  case_count: number
  coverage?: Record<string, number>
  error_case_ratio?: number
  language?: string
  maximum_input_tokens?: number
  maximum_cost_usd?: number | null
  test_structure?: EvaluationTestStructure
  minimum_session_turns?: number
  maximum_session_turns?: number
}

export interface GeneratedSuiteDraft {
  authoring_call_id: string
  authoring_source: 'ai_generated'
  source_snapshot_hash: string
  source_context_hash: string
  generator: {
    provider_model_id: string
    provider: string
    model: string
    input_tokens: number | null
    output_tokens: number | null
    cost_usd: number | null
    latency_ms: number
    error?: string | null
  }
  context_budget: SuiteContextPreview['context_budget']
  validation: SuiteValidationResult
  draft: EvaluatorSuiteDraft
}

export interface CreateComposedSuiteInput {
  name: string
  description?: string
  target_type: EvaluationTargetType
  judge_provider_model_id: string
  draft: EvaluatorSuiteDraft
  judge_config?: Record<string, unknown>
  rubric?: Record<string, unknown>
  deterministic_checks?: Record<string, unknown>
  acceptance_policy?: Record<string, unknown>
  repetition_policy?: Record<string, unknown>
  estimate_defaults?: Record<string, unknown>
  authoring_source: SuiteAuthoringSource
  source_snapshot_hash?: string | null
  source_context_hash?: string | null
  authoring_metadata?: Record<string, unknown>
}

export interface EvaluationDatasetVersion {
  id: string
  version: string
  content_hash: string
  change_description: string | null
  authoring_source?: SuiteAuthoringSource
  source_snapshot_hash?: string | null
  source_context_hash?: string | null
  authoring_metadata?: Record<string, unknown> | null
  reviewed_at?: string | null
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
  authoring_source?: SuiteAuthoringSource
  source_snapshot_hash?: string | null
  source_context_hash?: string | null
  authoring_metadata?: Record<string, unknown> | null
  archived_at?: string | null
  archived_by?: string | null
  created_at: string
  updated_at: string
  versions?: EvaluationDatasetVersion[]
  cases?: Array<{
    id: string
    position: number
    name: string
    case_type?: EvaluationCaseType
    interaction_mode?: EvaluationInteractionMode
    input_payload: Record<string, any>
    turns?: EvaluationSessionTurnInput[]
    initial_context?: Record<string, unknown> | null
    expected_contract: Record<string, any>
    severity: string
    weight: number
    blocking: boolean
    tags: string[]
    production_frequency?: number | null
  }>
}

export interface EvaluationSuiteStaleness {
  status: 'generic' | 'current' | 'stale' | 'target_unavailable' | 'current_unknown'
  source_snapshot_hash: string | null
  current_snapshot_hash: string | null
  target_type?: EvaluationTargetType
  entity_id?: string
  source_type?: EvaluationSourceType
  display_version?: string
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
  dataset_id?: string | null
  dataset_version_id: string | null
  case_count?: number
  judge_provider_model_id: string | null
  judge_config?: Record<string, unknown>
  rubric?: Record<string, unknown>
  deterministic_checks?: Record<string, unknown>
  acceptance_policy?: Record<string, unknown>
  repetition_policy?: Record<string, unknown>
  estimate_defaults?: Record<string, unknown>
  suite_hash?: string | null
  authoring_source?: SuiteAuthoringSource
  source_snapshot_hash?: string | null
  source_context_hash?: string | null
  authoring_metadata?: Record<string, unknown> | null
  parent_version_id?: string | null
  change_description?: string | null
  archived_at?: string | null
  archived_by?: string | null
  staleness?: EvaluationSuiteStaleness
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

export type EvaluationExecutionReference =
  | { kind: 'agent_trace'; trace_id: string }
  | { kind: 'network_execution'; network_execution_id: string; trace_id?: string | null }

export interface EvaluationTrialTurn {
  id: string
  position: number
  input_payload: Record<string, any>
  output?: Record<string, any> | null
  metrics?: Record<string, any> | null
  status: string
  agent_session_id?: string | null
  network_session_id?: string | null
  agent_run_id?: string | null
  network_execution_id?: string | null
  trace_id?: string | null
  failure_code?: string | null
  failure_detail?: string | null
  started_at?: string | null
  completed_at?: string | null
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
  execution_reference?: EvaluationExecutionReference | null
  interaction_mode?: EvaluationInteractionMode
  turns?: EvaluationTrialTurn[]
  output?: Record<string, any> | null
  metrics?: Record<string, any> | null
  observed_outcome?: Record<string, any> | null
  failure_origin?: string | null
  failure_stage?: string | null
  failure_code?: string | null
  failure_detail?: string | null
  case?: {
    id: string
    name: string
    case_type?: EvaluationCaseType
    interaction_mode?: EvaluationInteractionMode
    input_payload: Record<string, any>
    turns?: EvaluationSessionTurnInput[]
    initial_context?: Record<string, unknown> | null
    expected_contract: Record<string, any>
  } | null
  checks?: EvaluationCheck[]
}

export interface EvaluationSessionKpis {
  session_count: number
  session_completion_rate: number | null
  turn_count: number
  turn_completion_rate: number | null
  average_turns_per_session: number | null
  cost_usd_per_session: number | null
  cost_usd_per_turn: number | null
  latency_ms_per_session: number | null
  latency_ms_per_turn: number | null
  tokens_per_session: number | null
}

export interface EvaluationKpis {
  schema_version: string
  quality_score: number | null
  pass_rate: number | null
  sample_size: number
  conclusive_trial_count: number
  inconclusive_trial_count: number
  runtime_cost_usd_total: number | null
  runtime_cost_usd_per_trial: number | null
  runtime_pricing_coverage_percent: number
  latency_median_ms: number | null
  latency_p90_ms: number | null
  input_tokens_mean: number | null
  output_tokens_mean: number | null
  tool_calls_mean: number | null
  case_count: number
  stable_case_count: number
  mixed_case_count: number
  failed_case_count: number
  inconclusive_case_count: number
  stable_case_rate: number | null
  session: EvaluationSessionKpis
}

export interface EvaluationExecutionPolicy {
  requested_parallel_pairs?: number
  effective_parallel_pairs?: number
  reason?: string
  pair_members_serialized?: boolean
}

export interface EvaluationRun {
  id: string
  project_id: string
  suite_version_id: string
  mode: EvaluationRunMode
  status: EvaluationRunStatus
  repetitions: number
  execution_policy?: EvaluationExecutionPolicy
  qualification_status: string | null
  overall_score: number | null
  pass_rate: number | null
  aggregate_result: Record<string, any> | null
  kpis?: EvaluationKpis | null
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

export interface EvaluationQualification {
  id: string
  target_type: EvaluationTargetType
  entity_id: string
  target_snapshot_hash: string
  agent_release_id: string | null
  network_version_id: string | null
  suite_version_id: string
  dataset_version_id: string
  evaluation_run_id: string
  status: 'qualified' | 'qualified_with_warnings' | 'not_qualified' | 'inconclusive'
  score: number | null
  pass_rate: number | null
  critical_failures: number
  summary: Record<string, unknown>
  created_at: string
}
