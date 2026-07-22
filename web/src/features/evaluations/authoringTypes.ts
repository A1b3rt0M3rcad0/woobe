import type {
  CreateComposedSuiteInput,
  EvaluationTargetInput,
  EvaluatorSuiteDraft,
  SuiteContextPreview,
  SuiteValidationIssue,
  SuiteValidationResult,
} from './types'

export type EvaluationAuthoringStatus =
  | 'queued'
  | 'running'
  | 'partial'
  | 'cancel_requested'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface EvaluationAuthoringAttempt {
  attempt?: number | null
  worker_attempt?: number | null
  returned_case_count?: number
  valid_case_count?: number
  invalid_case_count?: number
  input_tokens?: number | null
  output_tokens?: number | null
  cost_usd?: number | null
  latency_ms?: number | null
  completed_at?: string | null
}

export interface EvaluationAuthoringBatch {
  id: string
  batch_index: number
  requested_case_count: number
  coverage: Record<string, number>
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  attempt: number
  input_tokens: number | null
  output_tokens: number | null
  cost_usd: number | null
  error?: string | null
  case_count: number
  returned_case_count?: number
  valid_case_count?: number
  invalid_case_count?: number
  failure_category?: string | null
  retryable?: boolean
  recommended_action?: string | null
  validation_errors?: SuiteValidationIssue[]
  normalization_warnings?: SuiteValidationIssue[]
  attempts?: EvaluationAuthoringAttempt[]
  started_at?: string | null
  completed_at?: string | null
}

export interface EvaluationAuthoringCall {
  authoring_call_id: string
  authoring_source: 'ai_generated'
  status: EvaluationAuthoringStatus
  phase?: string
  source_snapshot_hash: string
  source_context_hash: string
  requested_case_count: number
  completed_batch_count: number
  processed_batch_count?: number
  total_batch_count: number
  progress_percent: number
  processed_percent?: number
  created_at?: string | null
  elapsed_seconds?: number | null
  target?: {
    target_type: string
    source_type: string
    entity_id: string
    version_id?: string | null
    snapshot_hash: string
  }
  generator: {
    provider_model_id: string
    provider: string
    model: string
    input_tokens: number | null
    output_tokens: number | null
    cost_usd: number | null
    error?: string | null
  }
  context_budget: SuiteContextPreview['context_budget'] & {
    estimated_total_cost_usd?: number | null
    context_window?: number
  }
  validation: SuiteValidationResult | null
  draft: EvaluatorSuiteDraft | null
  cancel_requested_at?: string | null
  completed_at?: string | null
  batches: EvaluationAuthoringBatch[]
}

export interface ValidateSuiteDraftInput {
  draft: EvaluatorSuiteDraft
  reference_target?: EvaluationTargetInput
}

export interface CreateComposedSuiteVersionInput
  extends Omit<CreateComposedSuiteInput, 'name' | 'description' | 'target_type'> {
  change_description: string
}
