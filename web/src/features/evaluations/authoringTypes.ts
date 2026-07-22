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
  | 'partially_ready'
  | 'repairing'
  | 'paused_requires_action'
  | 'cancel_requested'
  | 'completed'
  | 'failed'
  | 'failed_internal'
  | 'cancelled'

export type EvaluationAuthoringCaseStatus =
  | 'planned'
  | 'generating'
  | 'validating'
  | 'ready'
  | 'paused'
  | 'needs_attention'
  | 'cancelled'

export type EvaluationAuthoringUsageStatus =
  | 'pending'
  | 'partial'
  | 'available'
  | 'not_reported'

export interface EvaluationAuthoringAttempt {
  id?: string
  batch_id?: string | null
  attempt?: number | null
  worker_attempt?: number | null
  provider_model_id?: string
  provider?: string
  model?: string
  status?: string
  requested_slot_ids?: string[]
  returned_case_count?: number
  valid_case_count?: number
  invalid_case_count?: number
  input_tokens?: number | null
  output_tokens?: number | null
  cost_usd?: number | null
  latency_ms?: number | null
  error_category?: string | null
  error_detail?: string | null
  started_at?: string | null
  completed_at?: string | null
}

export interface EvaluationAuthoringCaseSlot {
  id: string
  position: number
  coverage_category: string
  status: EvaluationAuthoringCaseStatus
  name?: string | null
  generated_case?: Record<string, unknown> | null
  validation?: {
    valid?: boolean
    errors?: SuiteValidationIssue[]
    warnings?: SuiteValidationIssue[]
  } | null
  failure_category?: string | null
  recommended_action?: string | null
  source_attempt_id?: string | null
}

export interface EvaluationToolCatalog {
  status: 'complete' | 'empty' | 'complete_with_live_fallback' | 'incomplete'
  source: string
  target_source_type: string
  target_snapshot_hash: string
  allowed_names: string[]
  tools: Array<{
    id: string
    name: string
    description?: string | null
    type?: string | null
    risk_level?: string
  }>
  missing_snapshot_tool_ids: string[]
  immutable: boolean
}

export interface EvaluationAuthoringBatch {
  id: string
  batch_index: number
  requested_case_count: number
  coverage: Record<string, number>
  status: 'pending' | 'running' | 'completed' | 'failed' | 'paused' | 'cancelled'
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
  ready_case_count?: number
  attention_case_count?: number
  pending_case_count?: number
  completed_batch_count: number
  processed_batch_count?: number
  total_batch_count: number
  progress_percent: number
  case_progress_percent?: number
  processed_percent?: number
  usage_status?: EvaluationAuthoringUsageStatus
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
    tool_catalog?: {
      status: string
      source: string
      tool_count: number
      immutable: boolean
    }
  }
  tool_catalog?: EvaluationToolCatalog | null
  validation: SuiteValidationResult | null
  draft: EvaluatorSuiteDraft | null
  cancel_requested_at?: string | null
  completed_at?: string | null
  case_slots?: EvaluationAuthoringCaseSlot[]
  attempts?: EvaluationAuthoringAttempt[]
  batches: EvaluationAuthoringBatch[]
}

export type ResumeAuthoringStrategy =
  | 'retry_failed_and_missing'
  | 'repair_tool_references'
  | 'retry_provider_call'
  | 'continue_with_new_model'
  | 'retry_with_larger_output_budget'

export interface ResumeAuthoringInput {
  provider_model_id?: string | null
  strategy?: ResumeAuthoringStrategy
}

export interface ValidateSuiteDraftInput {
  draft: EvaluatorSuiteDraft
  reference_target?: EvaluationTargetInput
}

export interface CreateComposedSuiteVersionInput
  extends Omit<CreateComposedSuiteInput, 'name' | 'description' | 'target_type'> {
  change_description: string
}
