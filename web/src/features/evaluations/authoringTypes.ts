import type {
  EvaluationTargetInput,
  EvaluatorSuiteDraft,
  SuiteContextPreview,
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
}

export interface EvaluationAuthoringCall {
  authoring_call_id: string
  authoring_source: 'ai_generated'
  status: EvaluationAuthoringStatus
  source_snapshot_hash: string
  source_context_hash: string
  requested_case_count: number
  completed_batch_count: number
  total_batch_count: number
  progress_percent: number
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
