import { useInfiniteQuery } from '@tanstack/react-query'

import {
  getEvaluationDatasetsPage,
  getEvaluationSuitesPage,
} from './paginationApi'

export function useEvaluationSuitesIncludingArchived(
  projectId?: string,
  enabled = true,
) {
  return useInfiniteQuery({
    queryKey: ['evaluation-suites', projectId, 'including-archived'],
    queryFn: ({ pageParam }) => getEvaluationSuitesPage(
      projectId as string,
      pageParam,
      true,
    ),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    select: (data) => data.pages.flatMap((page) => page.items),
    enabled: Boolean(projectId && enabled),
  })
}

export function useEvaluationDatasetsIncludingArchived(
  projectId?: string,
  enabled = true,
) {
  return useInfiniteQuery({
    queryKey: ['evaluation-datasets', projectId, 'including-archived'],
    queryFn: ({ pageParam }) => getEvaluationDatasetsPage(
      projectId as string,
      pageParam,
      true,
    ),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    select: (data) => data.pages.flatMap((page) => page.items),
    enabled: Boolean(projectId && enabled),
  })
}
