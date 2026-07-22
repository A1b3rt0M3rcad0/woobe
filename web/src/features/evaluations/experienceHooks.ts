import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  getEvaluationRunProgress,
  retryEvaluationJudgments,
} from './experienceApi'
import type { RetryEvaluationJudgmentsInput } from './experienceTypes'

const activeStatuses = new Set([
  'queued',
  'snapshotting',
  'executing',
  'judging',
  'aggregating',
  'cancel_requested',
])

export function useEvaluationRunProgress(projectId?: string, runId?: string | null) {
  return useQuery({
    queryKey: ['evaluation-run-progress', projectId, runId],
    queryFn: () => getEvaluationRunProgress(projectId as string, runId as string),
    enabled: Boolean(projectId && runId),
    refetchInterval: (query) => (
      query.state.data && activeStatuses.has(query.state.data.status) ? 1200 : false
    ),
  })
}

export function useRetryEvaluationJudgments(projectId?: string, runId?: string | null) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: RetryEvaluationJudgmentsInput = {}) =>
      retryEvaluationJudgments(projectId as string, runId as string, input),
    onSuccess: (run) => {
      client.setQueryData(['evaluation-run', projectId, run.id], run)
      client.invalidateQueries({ queryKey: ['evaluation-run-progress', projectId, run.id] })
      client.invalidateQueries({ queryKey: ['evaluation-runs', projectId] })
    },
  })
}
