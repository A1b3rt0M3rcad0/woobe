import { useQuery } from '@tanstack/react-query'
import { Button } from '@woobe/ui'
import { ApiError } from '@/lib/api/errors'
import { workspaceProjectPath } from '@/lib/constants/routes'
import { getConfigurationReadiness } from '../configuration'
import type { ProjectEnvironment } from '../types'

interface Props {
  projectId: string; targetKind: 'agent' | 'network'; targetId: string
  environment: ProjectEnvironment; versionId?: string; workspaceId?: string; unsaved?: boolean
}

/** Metadata-only advisory. Acceptance authorizes the exact submitted definition. */
export function ConfigurationReadinessNotice({ projectId, targetKind, targetId, environment, versionId, workspaceId, unsaved }: Props) {
  const query = useQuery({ queryKey: ['configuration-readiness', projectId, targetKind, targetId, environment, versionId],
    queryFn: () => getConfigurationReadiness(projectId, targetKind, targetId, environment, versionId),
    retry: false, staleTime: 15_000, refetchInterval: 30_000, refetchOnWindowFocus: 'always' })
  const forbidden = query.error instanceof ApiError && query.error.status === 403
  const data = query.isError ? undefined : query.data
  if (!query.isFetching && !query.isError && data?.state === 'ready' && !unsaved) return null
  const message = query.isFetching ? 'Checking configuration…'
    : forbidden ? 'Configuration status requires permission.'
    : query.isError || !data || data.state === 'unknown' ? 'Configuration status is unavailable or incomplete.'
    : data.state === 'blocked' ? data.missing_key_count > 0
      ? `${data.missing_key_count} missing keys · ${data.affected_consumer_count} affected connections`
      : `Configuration required · ${data.affected_consumer_count} blocked connections`
    : data.state === 'ready_with_notices' ? 'Configuration is present; connection checks or legacy review remain.'
    : 'Saved configuration is ready.'
  const params = new URLSearchParams({ environment })
  const returnTo = window.location.pathname + window.location.search
  if (returnTo.startsWith('/projects/') || returnTo.startsWith('/workspaces/')) params.set('returnTo', returnTo)
  const href = workspaceProjectPath(workspaceId, projectId, 'environments') + '?' + params.toString()
  return <aside className="shrink-0 border-b border-border bg-surface px-ui-md py-ui-xs text-product-small" aria-label="Configuration readiness">
    <div className="flex flex-wrap items-center gap-ui-sm">
      <span className="font-medium capitalize">{environment}</span>
      <span role="status" className="text-muted-foreground">{message}</span>
      {unsaved && <span className="text-muted-foreground">Saved definition only; unsaved changes are checked when sent.</span>}
      {!forbidden && <a href={href} className="ml-auto text-primary underline underline-offset-2">{data?.state === 'blocked' ? 'Configure to run' : 'Review configuration'}</a>}
      <Button variant="ghost" size="sm" disabled={query.isFetching} onClick={() => { void query.refetch() }}>Refresh status</Button>
    </div>
    {!!data?.dependencies.some(item => item.code) && <details className="mt-ui-xs">
      <summary className="cursor-pointer text-muted-foreground">Show configuration issues</summary>
      <ul className="mt-ui-xs space-y-ui-xs">{data.dependencies.filter(item => item.code).slice(0, 10).map((item, index) =>
        <li key={index}><code>{item.key}</code> — {item.material.replaceAll('_', ' ')} <span className="text-muted-foreground">({item.code})</span></li>)}
      </ul>
      {data.dependencies.filter(item => item.code).length > 10 && <p>Open Environments for all affected keys.</p>}
    </details>}
  </aside>
}
