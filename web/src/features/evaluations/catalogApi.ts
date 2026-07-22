import { get, post } from '@/lib/api/client'

import type {
  CatalogEvaluationPreview,
  CreateCatalogEvaluationInput,
  CreatePairedComparisonInput,
  CreatePostHocComparisonInput,
  EvaluationCatalogItem,
  EvaluationComparison,
  EvidenceRichRun,
} from './catalogTypes'

function base(projectId: string) {
  return `/evaluation/projects/${projectId}`
}

export function previewCatalogEvaluation(
  projectId: string,
  input: Omit<CreateCatalogEvaluationInput, 'idempotency_key'>,
) {
  return post<CatalogEvaluationPreview>(`${base(projectId)}/evaluations/preview`, input)
}

export function createCatalogEvaluationRun(
  projectId: string,
  input: CreateCatalogEvaluationInput,
) {
  return post<EvidenceRichRun>(`${base(projectId)}/evaluations/runs`, input)
}

export function getEvaluationCatalog(
  projectId: string,
  entityId?: string,
  includeArchived = false,
) {
  const query = new URLSearchParams()
  if (entityId) query.set('entity_id', entityId)
  if (includeArchived) query.set('include_archived', 'true')
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return get<EvaluationCatalogItem[]>(`${base(projectId)}/evaluations${suffix}`)
}

export function getCatalogEvaluation(projectId: string, evaluationId: string) {
  return get<EvaluationCatalogItem>(`${base(projectId)}/evaluations/${evaluationId}`)
}

export function archiveCatalogEvaluation(projectId: string, evaluationId: string) {
  return post<EvaluationCatalogItem>(`${base(projectId)}/evaluations/${evaluationId}/archive`)
}

export function restoreCatalogEvaluation(projectId: string, evaluationId: string) {
  return post<EvaluationCatalogItem>(`${base(projectId)}/evaluations/${evaluationId}/restore`)
}

export function getEvidenceRichEvaluationRun(projectId: string, runId: string) {
  return get<EvidenceRichRun>(`${base(projectId)}/evaluations/runs/${runId}`)
}

export function getEvaluationComparisons(projectId: string, entityId?: string) {
  const suffix = entityId ? `?entity_id=${encodeURIComponent(entityId)}` : ''
  return get<EvaluationComparison[]>(`${base(projectId)}/comparisons${suffix}`)
}

export function getEvaluationComparison(projectId: string, comparisonId: string) {
  return get<EvaluationComparison>(`${base(projectId)}/comparisons/${comparisonId}`)
}

export function previewEvaluationComparison(
  projectId: string,
  input: Pick<CreatePostHocComparisonInput, 'candidate_run_id' | 'reference_run_id'>,
) {
  return post<Record<string, any>>(`${base(projectId)}/comparisons/preview`, input)
}

export function createPostHocEvaluationComparison(
  projectId: string,
  input: CreatePostHocComparisonInput,
) {
  return post<EvaluationComparison>(`${base(projectId)}/comparisons/from-runs`, input)
}

export function createPairedEvaluationComparison(
  projectId: string,
  input: CreatePairedComparisonInput,
) {
  return post<EvaluationComparison>(`${base(projectId)}/comparisons/paired`, input)
}

export function decideEvaluationComparison(
  projectId: string,
  comparisonId: string,
  input: {
    decision: 'select_candidate' | 'keep_reference' | 'no_preference'
    decision_basis?: 'evidence' | 'manual_override'
    note?: string
  },
) {
  return post<Record<string, any>>(
    `${base(projectId)}/comparisons/${comparisonId}/decision`,
    input,
  )
}
