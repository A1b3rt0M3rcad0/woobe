import type {
  EvaluationRun,
  EvaluationTarget,
  EvaluationTargetInput,
} from './types'

export interface EvaluationModelVariantInput {
  type: 'model_override'
  provider_model_id: string
  temperature?: number
  max_output_tokens?: number
}

export interface EvaluationTargetWithVariant extends EvaluationTargetInput {
  variant?: EvaluationModelVariantInput
}

export interface EvaluationExperienceRunInput {
  suite_version_id: string
  repetitions: number
  candidate: EvaluationTargetWithVariant
  baseline?: EvaluationTargetWithVariant
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
  measured_cost_usd: number | null
  targets: EvaluationTarget[]
  failure_code?: string | null
  failure_detail?: string | null
}

export interface RetryEvaluationJudgmentsInput {
  trial_ids?: string[]
  failure_codes?: string[]
}
