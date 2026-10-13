import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@woobe/ui'
import { ApiError } from '@/lib/api/errors'
import { workspaceProjectPath } from '@/lib/constants/routes'
import { getConfigurationSummary } from '../configuration'
import type { ProjectEnvironment } from '../types'

export function ProjectConfigurationNotice({ projectId, workspaceId, environment: selected }: {
  projectId: string; workspaceId?: string; environment?: ProjectEnvironment
}) {
  const preference = 'woobe:configuration-environment:' + projectId
  const [local, setLocal] = useState<ProjectEnvironment>(() => {
    try {
      const saved = sessionStorage.getItem(preference)
      if (saved === 'draft' || saved === 'staging' || saved === 'production') return saved
    } catch { /* The default remains usable without browser storage. */ }
    return 'draft'
  })
  const environment = selected ?? local
  const query = useQuery({ queryKey: ['configuration-readiness', projectId, 'summary', environment],
    queryFn: () => getConfigurationSummary(projectId, environment), retry: false, staleTime: 15_000,
    refetchInterval: 30_000, refetchOnWindowFocus: 'always' })
  const forbidden = query.error instanceof ApiError && query.error.status === 403
  const data = query.isError ? undefined : query.data
  const message = query.isFetching ? 'Checking configuration…'
    : forbidden ? 'Configuration status requires permission.'
    : !data || data.state === 'unknown' ? 'Configuration status is incomplete. Review the exact target before execution.'
    : data.state === 'blocked' ? `${data.blocked_key_count} keys need attention · ${data.affected_target_count} affected targets`
    : data.inspected_target_count === data.unselected_target_count ? 'No active selections in this environment.'
    : data.state === 'ready_with_notices' ? 'Values available · connection checks or legacy review remain'
    : 'Required configuration is ready.'
  const params = new URLSearchParams({ environment })
  params.set('returnTo', window.location.pathname + window.location.search)
  const href = workspaceProjectPath(workspaceId, projectId, 'environments') + '?' + params
  return <aside aria-label="Project configuration" className="flex flex-wrap items-center gap-ui-sm rounded-md border border-border bg-surface px-ui-md py-ui-sm text-product-small">
    <span className="font-medium">Configuration</span>
    {selected ? <span className="capitalize">{environment}</span> : <label className="flex items-center gap-ui-xs">
      <span className="sr-only">Configuration environment</span>
      <select value={local} className="rounded border border-border bg-background px-ui-xs py-1 text-foreground"
        onChange={event => { const value = event.target.value as ProjectEnvironment; setLocal(value); try { sessionStorage.setItem(preference, value) } catch { /* Optional preference. */ } }}>
        <option value="draft">Draft</option><option value="staging">Staging</option><option value="production">Production</option>
      </select>
    </label>}
    <span role="status" className="text-muted-foreground">{message}</span>
    {!forbidden && <a href={href} className="ml-auto text-primary underline underline-offset-2">Configure now</a>}
    <Button variant="ghost" size="sm" disabled={query.isFetching} onClick={() => { void query.refetch() }}>Refresh status</Button>
  </aside>
}
