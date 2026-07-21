import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  cancelEvaluationRun,
  createEvaluationDataset,
  createEvaluationRun,
  createEvaluationSuite,
  getEvaluationDatasets,
  getEvaluationRun,
  getEvaluationRuns,
  getEvaluationSuites,
  previewEvaluationRun,
} from './api'
import type {
  CreateEvaluationDatasetInput,
  CreateEvaluationRunInput,
  CreateEvaluationSuiteInput,
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

export function useEvaluationSuites(projectId?: string) {
  return useQuery({
    queryKey: ['evaluation-suites', projectId],
    queryFn: () => getEvaluationSuites(projectId as string),
    enabled: Boolean(projectId),
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

export function useCreateEvaluationSuite(projectId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateEvaluationSuiteInput) => createEvaluationSuite(projectId as string, input),
    onSuccess: () => client.invalidateQueries({ queryKey: ['evaluation-suites', projectId] }),
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
