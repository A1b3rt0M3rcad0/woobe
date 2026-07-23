import type {
  EvaluationRun,
  EvaluationTarget,
  EvaluationTargetInput,
} from './types'

export type EvaluationTargetWithVariant = EvaluationTargetInput

export interface EvaluationExperienceRunInput {
  suite_version_id: string
  repetitions: number
  candidate: EvaluationTargetInput
  baseline?: EvaluationTargetInput
  acknowledge_tool_side_effects?: boolean
  approved_high_risk_tool_ids?: string[]
  idempotency_key?: string
}

export interface EvaluationRunProgress {
  run_id: string
  status: EvaluationRun['status']
  phase: string
  mode: EvaluationRun['mode']
  qualification_eligible?: boolean
  decision_required?: boolean
  evidence_revision?: number
  retry_attempt?: number
  retry_trial_count?: number
  total_trials: number
  runtime_completed: number
  runtime_pending: number
  judge_completed: number
  judge_running: number
  judge_pending: number
  completed_trials: number
  inconclusive_trials: number
  failed_trials: number
  elapsed_seconds: number | null
  phase_elapsed_seconds?: number | null
  processing_elapsed_seconds?: number | null
  started_at?: string | null
  measured_cost_usd: number | null
  targets: EvaluationTarget[]
  failure_code?: string | null
  failure_detail?: string | null
}

export interface RetryEvaluationJudgmentsInput {
  trial_ids?: string[]
  failure_codes?: string[]
}

export interface EvaluationDiagnosticSignal {
  severity: 'info' | 'warning' | 'error' | string
  code: string
  message: string
}

export interface EvaluationDiagnosticTimelineEvent {
  at: string
  stage: string
  status: 'info' | 'warning' | 'error' | string
  message: string
  trial_id: string | null
  details: Record<string, any>
}

export interface EvaluationDiagnosticJudgeCall {
  id: string
  trial_id: string
  status: string
  provider_model_id: string
  provider: string
  model: string
  judge_config_hash: string
  rubric_hash: string
  input_tokens: number | null
  output_tokens: number | null
  cost_usd: number | null
  cost_status: string | null
  cost_reason: string | null
  latency_ms: number | null
  started_at: string | null
  completed_at: string | null
  created_at: string | null
  canonical_failure_code: string | null
  error: string | null
  error_fingerprint: string | null
  structured_result: Record<string, any> | null
  diagnostics: Record<string, any>
  pricing: Record<string, any>
}

export interface EvaluationDiagnosticTrial {
  id: string
  execution_order: number
  repetition: number
  pair_key: string
  attempt: number
  status: string
  target: Record<string, any>
  case: Record<string, any> | null
  timestamps: Record<string, string | null>
  runtime: Record<string, any>
  judgment: Record<string, any>
  checks: Array<Record<string, any>>
}

export interface EvaluationRunDiagnostics {
  schema_version: string
  generated_at: string
  security: {
    redacted: boolean
    policy: string
  }
  summary: {
    run_id: string
    run_status: string
    assessment_status: string | null
    total_trials: number
    runtime_completed: number
    judge_started: number
    judge_calls: number
    judge_calls_completed: number
    judge_calls_failed: number
    judge_diagnostics_present: number
    adaptive_gateway_markers: number
    resilient_repair_markers: number
    conclusive_trials: number
    inconclusive_trials: number
    measured_total_cost: number | null
  }
  signals: EvaluationDiagnosticSignal[]
  failure_groups: Array<{ code: string; count: number }>
  repeated_errors: Array<{ signature: string; count: number }>
  run: Record<string, any>
  suite: Record<string, any>
  targets: Array<Record<string, any>>
  timeline: EvaluationDiagnosticTimelineEvent[]
  judge_calls: EvaluationDiagnosticJudgeCall[]
  trials: EvaluationDiagnosticTrial[]
}
