import { get, post } from '@/lib/api/client'
import type {
  CreateComposedSuiteInput,
  CreateEvaluationDatasetInput,
  CreateEvaluationRunInput,
  CreateEvaluationSuiteInput,
  EvaluationCaseInput,
  EvaluationDataset,
  EvaluationPreview,
  EvaluationQualification,
  EvaluationRun,
  EvaluationSuite,
  EvaluationTargetInput,
  EvaluationTargetType,
  GenerateSuiteDraftInput,
  GeneratedSuiteDraft,
  SuiteContextPreview,
  SuiteValidationResult,
  EvaluatorSuiteDraft,
} from './types'

function base(projectId: string) {
  return `/evaluation/projects/${projectId}`
}

function normalizeAuthoredCase(value: any): EvaluationCaseInput {
  const type = value?.case_type || value?.expected_outcome?.type || value?.expected_contract?.expected_outcome?.type || 'success'
  return {
    ...value,
    case_type: type,
    message: String(value?.message || value?.input_payload?.message || ''),
    expected_outcome: value?.expected_outcome || value?.expected_contract?.expected_outcome || { type },
    expected_contract: value?.expected_contract || {},
  }
}

function normalizeValidation(value: SuiteValidationResult): SuiteValidationResult {
  return {
    ...value,
    cases: (value.cases || []).map(normalizeAuthoredCase),
  }
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

export function previewSuiteAuthoringContext(
  projectId: string,
  input: Pick<GenerateSuiteDraftInput, 'target' | 'generator_provider_model_id' | 'objective' | 'case_count' | 'maximum_input_tokens'>,
) {
  return post<SuiteContextPreview>(`${base(projectId)}/suite-authoring/context-preview`, input)
}

export async function generateEvaluatorSuiteDraft(projectId: string, input: GenerateSuiteDraftInput) {
  const result = await post<GeneratedSuiteDraft>(`${base(projectId)}/suite-authoring/generate`, input)
  const validation = normalizeValidation(result.validation)
  return {
    ...result,
    validation,
    draft: {
      ...result.draft,
      cases: validation.cases,
    },
  }
}

export async function validateEvaluatorSuiteDraft(projectId: string, draft: EvaluatorSuiteDraft) {
  const result = await post<SuiteValidationResult>(`${base(projectId)}/suite-authoring/validate`, { draft })
  return normalizeValidation(result)
}

export function createComposedEvaluatorSuite(projectId: string, input: CreateComposedSuiteInput) {
  return post<EvaluationSuite>(`${base(projectId)}/suites/composed`, input)
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

export type { EvaluationTargetInput }
