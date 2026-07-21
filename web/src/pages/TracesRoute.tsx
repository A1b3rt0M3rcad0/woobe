import { Navigate, useParams, useSearchParams } from 'react-router-dom'

import TracesPage from '@/pages/TracesPage'

export default function TracesRoute() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  const [params] = useSearchParams()
  const traceId = params.get('trace_id')

  if (traceId && organizationId && projectId) {
    return (
      <Navigate
        to={`/organizations/${organizationId}/projects/${projectId}/traces/${traceId}`}
        replace
      />
    )
  }

  return <TracesPage />
}
