import type {
  EvaluationKpis,
  EvaluationPreflight,
  EvaluationRun,
  EvaluationTargetInput,
  EvaluationTargetType,
} from './types'

export interface EvaluationRunJudgeSummary {
  provider_model_id: string
  display_name: string
  provider?: string | null
  model?: string | null
  credential_name?: string | null
  response_strategy?: string | null
  snapshot_hash?: string | null
  source?: 'suite_default' | 'run_override' | string
}

export interface EvaluationCatalogRunSummary {
  id: string
  suite_version_id: string
  status: string
  mode: string
  repetitions: number
  evidence_revision: number
  assessment_status: string
  overall_score: number | null
  pass_rate: number | null
  measured_total_cost: number | null
  failure_code: string | null
  failure_detail: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  judge?: EvaluationRunJudgeSummary | null
  kpis?: EvaluationKpis | null
}

export interface EvaluationFreshness {
  status: 'current' | 'superseded' | 'immutable' | 'unknown' | 'target_unavailable'
  evaluated_snapshot_hash: string | null
  current_snapshot_hash: string | null
  current_display_version?: string | null
}

export interface EvaluationCatalogItem {
  id: string
  project_id: string
  suite_version_id: string
  suite_id?: string | null
  suite_name?: string | null
  suite_version?: string | null
  dataset_version_id?: string | null
  judge_provider_model_id?: string | null
  target_type: EvaluationTargetType
  entity_id: string
  source_type: 'draft' | 'staging' | 'release'
  target_version_id: string | null
  target_snapshot_hash: string
  target_identity_hash: string
  display_name: string
  display_version: string
  status: string
  latest_run_id: string | null
  run_count: number | null
  evaluation_protocol_hash: string | null
  freshness?: EvaluationFreshness
  latest_run?: EvaluationCatalogRunSummary | null
  runs?: EvaluationCatalogRunSummary[]
  archived_at?: string | null
  created_at: string
  updated_at: string
}

export interface CreateCatalogEvaluationInput {
  suite_version_id: string
  repetitions: number
  target: EvaluationTargetInput
  judge_provider_model_id?: string
  acknowledge_tool_side_effects?: boolean
  approved_high_risk_tool_ids?: string[]
  idempotency_key: string
}

export interface CatalogEvaluationPreview {
  mode: 'single_snapshot'
  target: Record<string, any>
  case_count: number
  repetitions: number
  target_run_count: number
  judge_call_count: number
  judge_provider_model_id: string
  judge_override?: boolean
  judge_preflight?: Record<string, any>
  evaluation_protocol_hash: string
  preflight: EvaluationPreflight
  requires_confirmation: boolean
  can_execute: boolean
  operations: {
    evaluation_runs: 1
    comparisons: 0
  }
}

export interface ComparisonSideSummary {
  run: EvaluationCatalogRunSummary
  target: {
    id: string
    target_type: EvaluationTargetType
    source_type: string
    entity_id: string
    environment: string
    snapshot_hash: string
    display_name: string
    display_version: string
    agent_release_id: string | null
    network_version_id: string | null
  } | null
  summary: Record<string, any>
  kpis?: EvaluationKpis | Record<string, any>
  runtime: {
    runtime_cost_usd: number | null
    latency_median_ms: number | null
    pricing_coverage: number
    latency_sample_size: number
  }
  failures: EvaluationFailureSummary
}

export interface EvaluationFailureGroup {
  stage: string
  kind: 'judge' | 'execution' | 'inconclusive' | string
  code: string
  recoverability: string
  recommended_action: string
  summary: string
  count: number
  trial_ids: string[]
}

export interface EvaluationFailureSummary {
  affected_trial_count: number
  groups: EvaluationFailureGroup[]
  primary: EvaluationFailureGroup | null
}

export interface EvaluationComparisonCase {
  test_case_id: string
  name: string
  case_type: string | null
  candidate: {
    score: number | null
    passed: number
    total: number
    conclusive: number
  }
  reference: {
    score: number | null
    passed: number
    total: number
    conclusive: number
  }
  score_delta: number | null
  winner: 'candidate' | 'reference' | 'tie' | null
}

export interface ComparisonWinnerKpi {
  key: string
  direction: 'maximize' | 'minimize'
  weight: number
  candidate: number | null
  reference: number | null
  delta: number | null
  winner: 'candidate' | 'reference' | 'tie' | null
}

export interface EvaluationComparisonWinner {
  schema_version: string
  side: 'candidate' | 'reference' | 'tie' | null
  candidate_score: number | null
  reference_score: number | null
  available_weight: number
  authoritative: boolean
  confidence: 'authoritative' | 'indicative'
  kpis: ComparisonWinnerKpi[]
  policy: Record<string, { weight: number; direction: 'maximize' | 'minimize' }>
}

export interface EvaluationComparisonAggregate {
  comparison_available: boolean
  comparison_kind?: string
  compatibility?: Record<string, any>
  candidate?: ComparisonSideSummary
  reference?: ComparisonSideSummary
  winner?: EvaluationComparisonWinner
  delta?: {
    score: number | null
    pass_rate_percentage_points: number | null
    runtime_cost_usd: number | null
    latency_median_ms: number | null
  }
  case_outcomes?: {
    candidate_wins: number
    reference_wins: number
    ties: number
    unavailable: number
  }
  cases?: EvaluationComparisonCase[]
  reason?: string | null
}

export interface EvaluationComparisonDecision {
  id: string
  comparison_id: string
  candidate_evidence_revision: number
  reference_evidence_revision: number
  decision: 'select_candidate' | 'keep_reference' | 'no_preference'
  decision_basis: 'evidence' | 'manual_override'
  note: string | null
  decided_by: string
  decided_at: string
}

export interface EvaluationComparison {
  id: string
  project_id: string
  suite_version_id: string
  protocol_hash: string
  comparison_mode: 'paired' | 'post_hoc' | 'legacy'
  status: 'waiting' | 'running' | 'ready' | 'partial' | 'blocked' | 'incompatible' | 'failed' | 'cancelled'
  candidate_run_id: string
  candidate_evidence_revision: number
  reference_run_id: string
  reference_evidence_revision: number
  aggregate_result: EvaluationComparisonAggregate | null
  failure_code: string | null
  failure_detail: string | null
  decision: EvaluationComparisonDecision | null
  candidate_run?: EvaluationRun
  reference_run?: EvaluationRun
  created_runs?: {
    candidate: EvaluationRun
    reference: EvaluationRun
  }
  created_at: string
  updated_at: string
  completed_at: string | null
}

export interface CreatePairedComparisonInput {
  suite_version_id: string
  repetitions: number
  candidate: EvaluationTargetInput
  reference: EvaluationTargetInput
  judge_provider_model_id?: string
  acknowledge_tool_side_effects?: boolean
  approved_high_risk_tool_ids?: string[]
  idempotency_key: string
}

export interface CreatePostHocComparisonInput {
  candidate_run_id: string
  reference_run_id: string
  candidate_evidence_revision?: number
  reference_evidence_revision?: number
  idempotency_key?: string
}

type EnrichedEvaluationTrial = NonNullable<EvaluationRun['trials']>[number] & {
  failure_classification?: {
    stage?: string
    kind?: string
    code?: string
    recoverability?: string
    recommended_action?: string
    summary?: string
  } | null
}

export interface EvidenceRichRun extends EvaluationRun {
  evaluation_id?: string | null
  evaluation_protocol_hash?: string | null
  evidence_revision?: number
  trials?: EnrichedEvaluationTrial[]
  evidence_status?: 'complete' | 'partial' | 'unavailable'
  evidence_completeness?: {
    total_trials: number
    runtime_completed: number
    judge_completed: number
    conclusive_trials: number
    inconclusive_trials: number
  }
  failure_summary?: EvaluationFailureSummary
  cost_breakdown?: {
    target_runtime_cost_usd: number | null
    judge_cost_usd: number | null
    total_evaluation_cost_usd: number | null
    target_pricing_coverage_percent: number
    judge_pricing_coverage_percent: number
  }
  knowledge_evidence?: Record<string, any>
  output_contract_coverage?: Record<string, any>
  provenance_warnings?: Array<{
    code: string
    message: string
    severity: string
    recommended_action?: string
  }>
  legacy_comparison?: boolean
}
