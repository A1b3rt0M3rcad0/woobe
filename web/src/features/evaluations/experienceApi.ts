import { get, post } from '@/lib/api/client'
import type { EvaluationRun, EvaluationSuite } from './types'
import type {
  EvaluationJudgeModel,
  EvaluationRunDiagnostics,
  EvaluationRunProgress,
  RetryEvaluationJudgmentsInput,
} from './experienceTypes'

function base(projectId: string) {
  return `/evaluation/projects/${projectId}`
}

export function getEvaluationJudgeModels(projectId: string) {
  return get<EvaluationJudgeModel[]>(`${base(projectId)}/judge-models`)
}

export function changeEvaluationSuiteJudgeModel(
  projectId: string,
  suiteId: string,
  input: { judge_model_id: string; change_description: string },
) {
  return post<EvaluationSuite>(`${base(projectId)}/suites/${suiteId}/judge-model`, input)
}

export function getEvaluationRunProgress(projectId: string, runId: string) {
  return get<EvaluationRunProgress>(`${base(projectId)}/runs/${runId}/progress`)
}

export function getEvaluationRunDiagnostics(projectId: string, runId: string) {
  return get<EvaluationRunDiagnostics>(`${base(projectId)}/runs/${runId}/diagnostics`)
}

export function retryEvaluationJudgments(
  projectId: string,
  runId: string,
  input: RetryEvaluationJudgmentsInput = {},
) {
  return post<EvaluationRun>(`${base(projectId)}/runs/${runId}/retry-judgments`, input)
}
