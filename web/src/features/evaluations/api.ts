import { get, post } from '@/lib/api/client'
import type {
  CreateEvaluationDatasetInput,
  CreateEvaluationRunInput,
  CreateEvaluationSuiteInput,
  EvaluationDataset,
  EvaluationPreview,
  EvaluationQualification,
  EvaluationRun,
  EvaluationSuite,
  EvaluationTargetType,
} from './types'

function base(projectId: string) {
  return `/evaluation/projects/${projectId}`
}

export function getEvaluationDatasets(projectId: string) {
  return get<EvaluationDataset[]>(`${base(projectId)}/datasets`)
}

export function getEvaluationDataset(projectId: string, datasetId: string) {
  return get<EvaluationDataset>(`${base(projectId)}/datasets/${datasetId}`)
}

export function createEvaluationDataset(projectId: string, input: CreateEvaluationDatasetInput) {
  return post<EvaluationDataset>(`${base(projectId)}/datasets`, input)
}

export function createEvaluationDatasetVersion(
  projectId: string,
  datasetId: string,
  input: Pick<CreateEvaluationDatasetInput, 'change_description' | 'cases'>,
) {
  return post<EvaluationDataset>(`${base(projectId)}/datasets/${datasetId}/versions`, input)
}

export function getEvaluationSuites(projectId: string) {
  return get<EvaluationSuite[]>(`${base(projectId)}/suites`)
}

export function createEvaluationSuite(projectId: string, input: CreateEvaluationSuiteInput) {
  return post<EvaluationSuite>(`${base(projectId)}/suites`, input)
}

export function createEvaluationSuiteVersion(
  projectId: string,
  suiteId: string,
  input: Omit<CreateEvaluationSuiteInput, 'name' | 'description' | 'target_type'>,
) {
  return post<EvaluationSuite>(`${base(projectId)}/suites/${suiteId}/versions`, input)
}

export function getEvaluationRuns(projectId: string) {
  return get<EvaluationRun[]>(`${base(projectId)}/runs`)
}

export function getEvaluationRun(projectId: string, runId: string) {
  return get<EvaluationRun>(`${base(projectId)}/runs/${runId}`)
}

export function previewEvaluationRun(projectId: string, input: CreateEvaluationRunInput) {
  return post<EvaluationPreview>(`${base(projectId)}/runs/preview`, input)
}

export function createEvaluationRun(projectId: string, input: CreateEvaluationRunInput) {
  return post<EvaluationRun>(`${base(projectId)}/runs`, input)
}

export function cancelEvaluationRun(projectId: string, runId: string) {
  return post<EvaluationRun>(`${base(projectId)}/runs/${runId}/cancel`)
}

export function getEvaluationQualifications(
  projectId: string,
  targetType?: EvaluationTargetType,
  entityId?: string,
) {
  const query = new URLSearchParams()
  if (targetType) query.set('target_type', targetType)
  if (entityId) query.set('entity_id', entityId)
  const queryString = query.toString()
  const suffix = queryString ? `?${queryString}` : ''
  return get<EvaluationQualification[]>(`${base(projectId)}/qualifications${suffix}`)
}
