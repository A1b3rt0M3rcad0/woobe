import { toast } from 'sonner'

import { get, post } from '@/lib/api/client'
import { ApiError } from '@/lib/api/errors'
import type {
  CreateComposedSuiteVersionInput,
  EvaluationAuthoringCall,
  ValidateSuiteDraftInput,
} from './authoringTypes'
import type { CreateEvaluationSuiteInput } from './suiteTypes'
import type {
  CreateComposedSuiteInput,
  CreateEvaluationDatasetInput,
  CreateEvaluationRunInput,
  EvaluationCaseInput,
  EvaluationDataset,
  EvaluationEstimate,
  EvaluationPreview,
  EvaluationQualification,
  EvaluationRun,
  EvaluationSuite,
  EvaluationTargetInput,
  EvaluationTargetType,
  GenerateSuiteDraftInput,
  SuiteContextPreview,
  SuiteValidationResult,
} from './types'

function base(projectId: string) {
  return `/evaluation/projects/${projectId}`
}

function normalizeAuthoringResourceError(error: unknown): Error {
  if (error instanceof ApiError && error.status === 404) {
    return new ApiError(
      'The selected Agent, snapshot, or generator model is no longer available in this Project. Refresh the modal, confirm that the Agent Draft is saved, and choose an active model.',
      error.status,
      error.data,
    )
  }
  return error instanceof Error ? error : new Error('Unable to prepare Evaluator Suite generation')
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

function normalizeValidation(value: SuiteValidationResult | null): SuiteValidationResult | null {
  if (!value) return null
  return {
    ...value,
    cases: (value.cases || []).map(normalizeAuthoredCase),
  }
}

function normalizeAuthoringCall(value: EvaluationAuthoringCall): EvaluationAuthoringCall {
  const validation = normalizeValidation(value.validation)
  return {
    ...value,
    validation,
    draft: value.draft ? {
      ...value.draft,
      cases: (validation?.cases || value.draft.cases || []).map(normalizeAuthoredCase),
    } : null,
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

export function archiveEvaluationDataset(projectId: string, datasetId: string) {
  return post<EvaluationDataset>(`${base(projectId)}/datasets/${datasetId}/archive`)
}

export function restoreEvaluationDataset(projectId: string, datasetId: string) {
  return post<EvaluationDataset>(`${base(projectId)}/datasets/${datasetId}/restore`)
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

export function createComposedEvaluationSuiteVersion(
  projectId: string,
  suiteId: string,
  input: CreateComposedSuiteVersionInput,
) {
  return post<EvaluationSuite>(`${base(projectId)}/suites/${suiteId}/versions/composed`, input)
}

export function archiveEvaluationSuite(projectId: string, suiteId: string) {
  return post<EvaluationSuite>(`${base(projectId)}/suites/${suiteId}/archive`)
}

export function restoreEvaluationSuite(projectId: string, suiteId: string) {
  return post<EvaluationSuite>(`${base(projectId)}/suites/${suiteId}/restore`)
}

export async function previewSuiteAuthoringContext(
  projectId: string,
  input: Pick<GenerateSuiteDraftInput, 'target' | 'generator_provider_model_id' | 'objective' | 'case_count' | 'maximum_input_tokens'>,
) {
  try {
    return await post<SuiteContextPreview>(`${base(projectId)}/suite-authoring/context-preview`, input)
  } catch (error) {
    const normalized = normalizeAuthoringResourceError(error)
    toast.error(normalized.message, { id: 'evaluation-authoring-preview-error' })
    throw normalized
  }
}

export async function generateEvaluatorSuiteDraft(projectId: string, input: GenerateSuiteDraftInput) {
  try {
    const result = await post<EvaluationAuthoringCall>(`${base(projectId)}/suite-authoring/generate`, input)
    return normalizeAuthoringCall(result)
  } catch (error) {
    throw normalizeAuthoringResourceError(error)
  }
}

export async function getEvaluatorSuiteAuthoringCall(projectId: string, callId: string) {
  const result = await get<EvaluationAuthoringCall>(`${base(projectId)}/suite-authoring/calls/${callId}`)
  return normalizeAuthoringCall(result)
}

export async function cancelEvaluatorSuiteAuthoringCall(projectId: string, callId: string) {
  const result = await post<EvaluationAuthoringCall>(`${base(projectId)}/suite-authoring/calls/${callId}/cancel`)
  return normalizeAuthoringCall(result)
}

export async function retryEvaluatorSuiteAuthoringCall(projectId: string, callId: string) {
  const result = await post<EvaluationAuthoringCall>(`${base(projectId)}/suite-authoring/calls/${callId}/retry`)
  return normalizeAuthoringCall(result)
}

export async function validateEvaluatorSuiteDraft(projectId: string, input: ValidateSuiteDraftInput) {
  const result = await post<SuiteValidationResult>(`${base(projectId)}/suite-authoring/validate`, input)
  return normalizeValidation(result) as SuiteValidationResult
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

export function createEvaluationEstimate(
  projectId: string,
  runId: string,
  volume: number,
  volumeUnit = 'runs_per_month',
) {
  return post<EvaluationEstimate[]>(`${base(projectId)}/runs/${runId}/estimates`, {
    volume,
    volume_unit: volumeUnit,
  })
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
