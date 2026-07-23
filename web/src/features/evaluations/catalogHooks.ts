import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  archiveCatalogEvaluation,
  createCatalogEvaluationRun,
  createPairedEvaluationComparison,
  createPostHocEvaluationComparison,
  decideEvaluationComparison,
  getCatalogEvaluation,
  getEvaluationCatalog,
  getEvaluationComparison,
  getEvaluationComparisons,
  getEvidenceRichEvaluationRun,
  previewCatalogEvaluation,
  previewEvaluationComparison,
  previewPairedEvaluationComparison,
  restoreCatalogEvaluation,
} from './catalogApi'
import type {
  CreateCatalogEvaluationInput,
  CreatePairedComparisonInput,
  CreatePostHocComparisonInput,
} from './catalogTypes'

const activeComparisonStatuses = new Set(['waiting', 'running'])
const activeRunStatuses = new Set([
  'queued',
  'snapshotting',
  'executing',
  'judging',
  'aggregating',
  'cancel_requested',
])

export function useEvaluationCatalog(
  projectId?: string,
  entityId?: string,
  includeArchived = false,
) {
  return useQuery({
    queryKey: ['evaluation-catalog', projectId, entityId, includeArchived],
    queryFn: () => getEvaluationCatalog(projectId as string, entityId, includeArchived),
    enabled: Boolean(projectId),
    refetchInterval: (query) => (
      query.state.data?.some((item) => (
        item.latest_run ? activeRunStatuses.has(item.latest_run.status) : false
      ))
        ? 2200
        : false
    ),
  })
}

export function useCatalogEvaluation(projectId?: string, evaluationId?: string | null) {
  return useQuery({
    queryKey: ['catalog-evaluation', projectId, evaluationId],
    queryFn: () => getCatalogEvaluation(projectId as string, evaluationId as string),
    enabled: Boolean(projectId && evaluationId),
    refetchInterval: (query) => (
      query.state.data?.runs?.some((run) => activeRunStatuses.has(run.status))
        ? 2200
        : false
    ),
  })
}

export function useEvidenceRichEvaluationRun(projectId?: string, runId?: string | null) {
  return useQuery({
    queryKey: ['evaluation-evidence-run', projectId, runId],
    queryFn: () => getEvidenceRichEvaluationRun(projectId as string, runId as string),
    enabled: Boolean(projectId && runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && activeRunStatuses.has(status) ? 1800 : false
    },
  })
}

export function usePreviewCatalogEvaluation(projectId?: string) {
  return useMutation({
    mutationFn: (input: Omit<CreateCatalogEvaluationInput, 'idempotency_key'>) =>
      previewCatalogEvaluation(projectId as string, input),
  })
}

export function usePreviewPairedEvaluationComparison(projectId?: string) {
  return useMutation({
    mutationFn: (input: CreatePairedComparisonInput) =>
      previewPairedEvaluationComparison(projectId as string, input),
  })
}

export function useCreateCatalogEvaluationRun(projectId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateCatalogEvaluationInput) =>
      createCatalogEvaluationRun(projectId as string, input),
    onSuccess: (run) => {
      client.setQueryData(['evaluation-evidence-run', projectId, run.id], run)
      client.invalidateQueries({ queryKey: ['evaluation-catalog', projectId] })
      client.invalidateQueries({ queryKey: ['evaluation-runs', projectId] })
    },
  })
}

export function useArchiveCatalogEvaluation(projectId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (evaluationId: string) =>
      archiveCatalogEvaluation(projectId as string, evaluationId),
    onSuccess: () => client.invalidateQueries({ queryKey: ['evaluation-catalog', projectId] }),
  })
}

export function useRestoreCatalogEvaluation(projectId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (evaluationId: string) =>
      restoreCatalogEvaluation(projectId as string, evaluationId),
    onSuccess: () => client.invalidateQueries({ queryKey: ['evaluation-catalog', projectId] }),
  })
}

export function useEvaluationComparisons(projectId?: string, entityId?: string) {
  return useQuery({
    queryKey: ['evaluation-comparisons', projectId, entityId],
    queryFn: () => getEvaluationComparisons(projectId as string, entityId),
    enabled: Boolean(projectId),
    refetchInterval: (query) => (
      query.state.data?.some((item) => activeComparisonStatuses.has(item.status))
        ? 2200
        : false
    ),
  })
}

export function useEvaluationComparison(
  projectId?: string,
  comparisonId?: string | null,
) {
  return useQuery({
    queryKey: ['evaluation-comparison', projectId, comparisonId],
    queryFn: () => getEvaluationComparison(projectId as string, comparisonId as string),
    enabled: Boolean(projectId && comparisonId),
    refetchInterval: (query) => (
      query.state.data && activeComparisonStatuses.has(query.state.data.status)
        ? 1800
        : false
    ),
  })
}

export function usePreviewEvaluationComparison(projectId?: string) {
  return useMutation({
    mutationFn: (input: Pick<CreatePostHocComparisonInput, 'candidate_run_id' | 'reference_run_id'>) =>
      previewEvaluationComparison(projectId as string, input),
  })
}

export function useCreatePostHocEvaluationComparison(projectId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: CreatePostHocComparisonInput) =>
      createPostHocEvaluationComparison(projectId as string, input),
    onSuccess: (comparison) => {
      client.setQueryData(
        ['evaluation-comparison', projectId, comparison.id],
        comparison,
      )
      client.invalidateQueries({ queryKey: ['evaluation-comparisons', projectId] })
    },
  })
}

export function useCreatePairedEvaluationComparison(projectId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: CreatePairedComparisonInput) =>
      createPairedEvaluationComparison(projectId as string, input),
    onSuccess: (comparison) => {
      client.setQueryData(
        ['evaluation-comparison', projectId, comparison.id],
        comparison,
      )
      client.invalidateQueries({ queryKey: ['evaluation-comparisons', projectId] })
      client.invalidateQueries({ queryKey: ['evaluation-catalog', projectId] })
      client.invalidateQueries({ queryKey: ['evaluation-runs', projectId] })
    },
  })
}

export function useDecideEvaluationComparison(
  projectId?: string,
  comparisonId?: string | null,
) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: {
      decision: 'select_candidate' | 'keep_reference' | 'no_preference'
      decision_basis?: 'evidence' | 'manual_override'
      note?: string
    }) => decideEvaluationComparison(
      projectId as string,
      comparisonId as string,
      input,
    ),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['evaluation-comparison', projectId, comparisonId] })
      client.invalidateQueries({ queryKey: ['evaluation-comparisons', projectId] })
    },
  })
}
