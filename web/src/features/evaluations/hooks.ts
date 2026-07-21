import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  cancelEvaluationRun,
  createComposedEvaluatorSuite,
  createEvaluationDataset,
  createEvaluationDatasetVersion,
  createEvaluationRun,
  createEvaluationSuite,
  createEvaluationSuiteVersion,
  generateEvaluatorSuiteDraft,
  getEvaluationDataset,
  getEvaluationDatasets,
  getEvaluationQualifications,
  getEvaluationRun,
  getEvaluationRuns,
  getEvaluationSuites,
  previewEvaluationRun,
  previewSuiteAuthoringContext,
  validateEvaluatorSuiteDraft,
} from './api'
import type {
  CreateComposedSuiteInput,
  CreateEvaluationDatasetInput,
  CreateEvaluationRunInput,
  CreateEvaluationSuiteInput,
  EvaluationTargetType,
  EvaluatorSuiteDraft,
  GenerateSuiteDraftInput,
} from './types'

const activeStatuses = new Set([
  'queued',
  'snapshotting',
  'executing',
  'judging',
  'aggregating',
  'cancel_requested',
])

export function useEvaluationDatasets(projectId?: string) {
  return useQuery({
    queryKey: ['evaluation-datasets', projectId],
    queryFn: () => getEvaluationDatasets(projectId as string),
    enabled: Boolean(projectId),
  })
}

export function useEvaluationDataset(projectId?: string, datasetId?: string | null) {
  return useQuery({
    queryKey: ['evaluation-dataset', projectId, datasetId],
    queryFn: () => getEvaluationDataset(projectId as string, datasetId as string),
    enabled: Boolean(projectId && datasetId),
  })
}

export function useEvaluationSuites(projectId?: string) {
  return useQuery({
    queryKey: ['evaluation-suites', projectId],
    queryFn: () => getEvaluationSuites(projectId as string),
    enabled: Boolean(projectId),
  })
}

export function useEvaluationQualifications(
  projectId?: string,
  targetType?: EvaluationTargetType,
  entityId?: string,
) {
  return useQuery({
    queryKey: ['evaluation-qualifications', projectId, targetType, entityId],
    queryFn: () => getEvaluationQualifications(projectId as string, targetType, entityId),
    enabled: Boolean(projectId && targetType && entityId),
  })
}

export function useEvaluationRuns(projectId?: string) {
  return useQuery({
    queryKey: ['evaluation-runs', projectId],
    queryFn: () => getEvaluationRuns(projectId as string),
    enabled: Boolean(projectId),
    refetchInterval: (query) => {
      const values = query.state.data ?? []
      return values.some((item) => activeStatuses.has(item.status)) ? 2500 : false
    },
  })
}

export function useEvaluationRun(projectId?: string, runId?: string | null) {
  return useQuery({
    queryKey: ['evaluation-run', projectId, runId],
    queryFn: () => getEvaluationRun(projectId as string, runId as string),
    enabled: Boolean(projectId && runId),
    refetchInterval: (query) => (
      query.state.data && activeStatuses.has(query.state.data.status) ? 1800 : false
    ),
  })
}

export function useCreateEvaluationDataset(projectId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateEvaluationDatasetInput) => createEvaluationDataset(projectId as string, input),
    onSuccess: () => client.invalidateQueries({ queryKey: ['evaluation-datasets', projectId] }),
  })
}

export function useCreateEvaluationDatasetVersion(projectId?: string, datasetId?: string | null) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: Pick<CreateEvaluationDatasetInput, 'change_description' | 'cases'>) =>
      createEvaluationDatasetVersion(projectId as string, datasetId as string, input),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['evaluation-datasets', projectId] })
      client.invalidateQueries({ queryKey: ['evaluation-dataset', projectId, datasetId] })
    },
  })
}

export function useCreateEvaluationSuite(projectId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateEvaluationSuiteInput) => createEvaluationSuite(projectId as string, input),
    onSuccess: () => client.invalidateQueries({ queryKey: ['evaluation-suites', projectId] }),
  })
}

export function useCreateEvaluationSuiteVersion(projectId?: string, suiteId?: string | null) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: Omit<CreateEvaluationSuiteInput, 'name' | 'description' | 'target_type'>) =>
      createEvaluationSuiteVersion(projectId as string, suiteId as string, input),
    onSuccess: () => client.invalidateQueries({ queryKey: ['evaluation-suites', projectId] }),
  })
}

export function usePreviewSuiteAuthoringContext(projectId?: string) {
  return useMutation({
    mutationFn: (input: Pick<GenerateSuiteDraftInput, 'target' | 'generator_provider_model_id' | 'objective' | 'case_count' | 'maximum_input_tokens'>) =>
      previewSuiteAuthoringContext(projectId as string, input),
  })
}

export function useGenerateEvaluatorSuite(projectId?: string) {
  return useMutation({
    mutationFn: (input: GenerateSuiteDraftInput) => generateEvaluatorSuiteDraft(projectId as string, input),
  })
}

export function useValidateEvaluatorSuite(projectId?: string) {
  return useMutation({
    mutationFn: (draft: EvaluatorSuiteDraft) => validateEvaluatorSuiteDraft(projectId as string, draft),
  })
}

export function useCreateComposedEvaluatorSuite(projectId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateComposedSuiteInput) => createComposedEvaluatorSuite(projectId as string, input),
    onSuccess: (suite) => {
      client.invalidateQueries({ queryKey: ['evaluation-suites', projectId] })
      client.invalidateQueries({ queryKey: ['evaluation-datasets', projectId] })
      if (suite.id) client.setQueryData(['evaluation-suite', projectId, suite.id], suite)
    },
  })
}

export function usePreviewEvaluationRun(projectId?: string) {
  return useMutation({
    mutationFn: (input: CreateEvaluationRunInput) => previewEvaluationRun(projectId as string, input),
  })
}

export function useCreateEvaluationRun(projectId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateEvaluationRunInput) => createEvaluationRun(projectId as string, input),
    onSuccess: (run) => {
      client.setQueryData(['evaluation-run', projectId, run.id], run)
      client.invalidateQueries({ queryKey: ['evaluation-runs', projectId] })
      client.invalidateQueries({ queryKey: ['evaluation-qualifications', projectId] })
    },
  })
}

export function useCancelEvaluationRun(projectId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (runId: string) => cancelEvaluationRun(projectId as string, runId),
    onSuccess: (run) => {
      client.setQueryData(['evaluation-run', projectId, run.id], run)
      client.invalidateQueries({ queryKey: ['evaluation-runs', projectId] })
    },
  })
}
