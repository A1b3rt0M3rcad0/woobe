import type { EvaluationTargetType } from './types'

/**
 * Payload accepted by the non-composed Evaluation Suite endpoints.
 * Keep this aligned with CreateSuiteRequest in the backend.
 */
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
