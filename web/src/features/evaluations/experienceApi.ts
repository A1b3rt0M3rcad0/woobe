import { get, post } from '@/lib/api/client'
import type { EvaluationRun } from './types'
import type {
  EvaluationRunProgress,
  RetryEvaluationJudgmentsInput,
} from './experienceTypes'

function base(projectId: string) {
  return `/evaluation/projects/${projectId}`
}

export function getEvaluationRunProgress(projectId: string, runId: string) {
  return get<EvaluationRunProgress>(`${base(projectId)}/runs/${runId}/progress`)
}

export function retryEvaluationJudgments(
  projectId: string,
  runId: string,
  input: RetryEvaluationJudgmentsInput = {},
) {
  return post<EvaluationRun>(`${base(projectId)}/runs/${runId}/retry-judgments`, input)
}
