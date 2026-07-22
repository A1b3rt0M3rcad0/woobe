import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import {
  archiveEvaluationDataset,
  archiveEvaluationSuite,
  cancelEvaluationRun,
  cancelEvaluatorSuiteAuthoringCall,
  createComposedEvaluatorSuite,
  createEvaluationDataset,
  createEvaluationDatasetVersion,
  createEvaluationEstimate,
  createEvaluationRun,
  createEvaluationSuite,
  createEvaluationSuiteVersion,
  generateEvaluatorSuiteDraft,
  getEvaluationDataset,
  getEvaluationQualifications,
  getEvaluationRun,
  getEvaluatorSuiteAuthoringCall,
  previewEvaluationRun,
  previewSuiteAuthoringContext,
  restoreEvaluationDataset,
  restoreEvaluationSuite,
  retryEvaluatorSuiteAuthoringCall,
  validateEvaluatorSuiteDraft,
} from './api'
import type { ValidateSuiteDraftInput } from './authoringTypes'
import {
  getEvaluationDatasetsPage,
  getEvaluationRunsPage,
  getEvaluationSuitesPage,
} from './paginationApi'
import type {
  CreateComposedSuiteInput,
  CreateEvaluationDatasetInput,
  CreateEvaluationRunInput,
  CreateEvaluationSuiteInput,
  EvaluationRun,
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

const activeAuthoringStatuses = new Set([
  'queued',
  'running',
  'partial',
  'cancel_requested',
])

function runValues(value: unknown): EvaluationRun[] {
  if (Array.isArray(value)) return value as EvaluationRun[]
  const pages = (value as any)?.pages
  return Array.isArray(pages)
    ? pages.flatMap((page: any) => Array.isArray(page?.items) ? page.items : [])
    : []
}

export function useEvaluationDatasets(projectId?: string) {
  return useInfiniteQuery({
    queryKey: ['evaluation-datasets', projectId],
    queryFn: ({ pageParam }) => getEvaluationDatasetsPage(projectId as string, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    select: (data) => data.pages.flatMap((page) => page.items),
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
  return useInfiniteQuery({
    queryKey: ['evaluation-suites', projectId],
    queryFn: ({ pageParam }) => getEvaluationSuitesPage(projectId as string, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    select: (data) => data.pages.flatMap((page) => page.items),
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
  return useInfiniteQuery({
    queryKey: ['evaluation-runs', projectId],
    queryFn: ({ pageParam }) => getEvaluationRunsPage(projectId as string, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    select: (data) => data.pages.flatMap((page) => page.items),
    enabled: Boolean(projectId),
    refetchInterval: (query) => (
      runValues(query.state.data).some((item) => activeStatuses.has(item.status))
        ? 2500
        : false
    ),
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

export function useEvaluationAuthoringCall(projectId?: string, callId?: string | null) {
  return useQuery({
    queryKey: ['evaluation-authoring-call', projectId, callId],
    queryFn: () => getEvaluatorSuiteAuthoringCall(projectId as string, callId as string),
    enabled: Boolean(projectId && callId),
    refetchInterval: (query) => (
      query.state.data && activeAuthoringStatuses.has(query.state.data.status) ? 1200 : false
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

export function useArchiveEvaluationDataset(projectId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (datasetId: string) => archiveEvaluationDataset(projectId as string, datasetId),
    onSuccess: () => client.invalidateQueries({ queryKey: ['evaluation-datasets', projectId] }),
  })
}

export function useRestoreEvaluationDataset(projectId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (datasetId: string) => restoreEvaluationDataset(projectId as string, datasetId),
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

export function useCreateEvaluationSuiteVersion(projectId?: string, suiteId?: string | null) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: Omit<CreateEvaluationSuiteInput, 'name' | 'description' | 'target_type'>) =>
      createEvaluationSuiteVersion(projectId as string, suiteId as string, input),
    onSuccess: () => client.invalidateQueries({ queryKey: ['evaluation-suites', projectId] }),
  })
}

export function useArchiveEvaluationSuite(projectId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (suiteId: string) => archiveEvaluationSuite(projectId as string, suiteId),
    onSuccess: () => client.invalidateQueries({ queryKey: ['evaluation-suites', projectId] }),
  })
}

export function useRestoreEvaluationSuite(projectId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (suiteId: string) => restoreEvaluationSuite(projectId as string, suiteId),
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
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: GenerateSuiteDraftInput) => generateEvaluatorSuiteDraft(projectId as string, input),
    onSuccess: (call) => {
      client.setQueryData(
        ['evaluation-authoring-call', projectId, call.authoring_call_id],
        call,
      )
    },
  })
}

export function useCancelEvaluatorSuiteAuthoring(projectId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (callId: string) => cancelEvaluatorSuiteAuthoringCall(projectId as string, callId),
    onSuccess: (call) => client.setQueryData(
      ['evaluation-authoring-call', projectId, call.authoring_call_id],
      call,
    ),
  })
}

export function useRetryEvaluatorSuiteAuthoring(projectId?: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (callId: string) => retryEvaluatorSuiteAuthoringCall(projectId as string, callId),
    onSuccess: (call) => client.setQueryData(
      ['evaluation-authoring-call', projectId, call.authoring_call_id],
      call,
    ),
  })
}

export function useValidateEvaluatorSuite(projectId?: string) {
  return useMutation({
    mutationFn: (input: EvaluatorSuiteDraft | ValidateSuiteDraftInput) =>
      validateEvaluatorSuiteDraft(
        projectId as string,
        'draft' in input ? input : { draft: input },
      ),
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

export function useCreateEvaluationEstimate(projectId?: string, runId?: string | null) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ volume, volumeUnit }: { volume: number; volumeUnit?: string }) =>
      createEvaluationEstimate(projectId as string, runId as string, volume, volumeUnit),
    onSuccess: () => client.invalidateQueries({ queryKey: ['evaluation-run', projectId, runId] }),
  })
}
