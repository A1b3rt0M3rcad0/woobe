import { useMutation, useQueryClient } from '@tanstack/react-query'

import { createComposedEvaluationSuiteVersion } from './api'
import type { CreateComposedSuiteVersionInput } from './authoringTypes'

export function useCreateComposedEvaluationSuiteVersion(
  projectId?: string,
  suiteId?: string | null,
) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateComposedSuiteVersionInput) =>
      createComposedEvaluationSuiteVersion(
        projectId as string,
        suiteId as string,
        input,
      ),
    onSuccess: (suite) => {
      client.invalidateQueries({ queryKey: ['evaluation-suites', projectId] })
      client.invalidateQueries({ queryKey: ['evaluation-datasets', projectId] })
      client.setQueryData(['evaluation-suite', projectId, suite.id], suite)
    },
  })
}
