import { get } from '@/lib/api/client'
import type { EvaluationDataset, EvaluationRun, EvaluationSuite } from './types'

export interface EvaluationPage<T> {
  items: T[]
  next_cursor: string | null
  has_more: boolean
}

function base(projectId: string) {
  return `/evaluation/projects/${projectId}`
}

function query(cursor?: string | null, includeArchived = false) {
  const params = new URLSearchParams({ limit: '50' })
  if (cursor) params.set('cursor', cursor)
  if (includeArchived) params.set('include_archived', 'true')
  return params.toString()
}

export function getEvaluationRunsPage(projectId: string, cursor?: string | null) {
  return get<EvaluationPage<EvaluationRun>>(`${base(projectId)}/runs/page?${query(cursor)}`)
}

export function getEvaluationSuitesPage(
  projectId: string,
  cursor?: string | null,
  includeArchived = false,
) {
  return get<EvaluationPage<EvaluationSuite>>(
    `${base(projectId)}/suites/page?${query(cursor, includeArchived)}`,
  )
}

export function getEvaluationDatasetsPage(
  projectId: string,
  cursor?: string | null,
  includeArchived = false,
) {
  return get<EvaluationPage<EvaluationDataset>>(
    `${base(projectId)}/datasets/page?${query(cursor, includeArchived)}`,
  )
}
