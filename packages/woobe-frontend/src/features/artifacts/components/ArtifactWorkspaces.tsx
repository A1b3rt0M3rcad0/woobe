import { useMemo, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Building2, ChevronLeft, ChevronRight, Plus, Search } from 'lucide-react'
import { Button, Input } from '@woobe/ui'
import { ResourceEmptyState, ResourcePage, ResourceToolbar } from '@/components/common/ResourcePage'
import { ApiError } from '@/lib/api/errors'
import { useArtifactWorkspaces, useCreateArtifactWorkspace } from '../hooks'
import type { ArtifactEnvironment } from '../types'

const environments: ArtifactEnvironment[] = ['draft', 'staging', 'production']

function messageFor(error: unknown) {
  if (error instanceof ApiError && error.status === 403) {
    return 'Access is denied by the current Project grant or Artifact Workspace grant.'
  }
  return error instanceof Error ? error.message : 'Artifact Workspaces are unavailable.'
}

export function ArtifactWorkspaces({
  projectId,
  environment,
  onEnvironmentChange,
}: {
  projectId: string
  environment: ArtifactEnvironment
  onEnvironmentChange: (environment: ArtifactEnvironment) => void
}) {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const navigate = useNavigate()
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null])
  const [search, setSearch] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [created, setCreated] = useState<string | null>(null)
  const pageCursor = cursorStack[cursorStack.length - 1] ?? null
  const query = useArtifactWorkspaces(projectId, environment, pageCursor)
  const createWorkspace = useCreateArtifactWorkspace(projectId, environment)
  const normalizedSearch = search.trim().toLocaleLowerCase()
  const visibleItems = useMemo(() => (query.data?.items ?? []).filter(item =>
    [item.name, item.external_namespace, item.external_key].some(value =>
      value.toLocaleLowerCase().includes(normalizedSearch),
    ),
  ), [normalizedSearch, query.data?.items])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const name = String(form.get('name') ?? '').trim()
    const namespace = String(form.get('external_namespace') ?? '').trim()
    const externalKey = String(form.get('external_key') ?? '').trim()
    if (!name || !namespace || !externalKey) return
    setCreateError(null)
    try {
      const result = await createWorkspace.mutateAsync({
        schema_version: '1', environment, name,
        external_namespace: namespace, external_key: externalKey,
      })
      setCreating(false)
      setCreated(name)
      setCursorStack([null])
      navigate(`/workspaces/${workspaceId}/projects/${projectId}/artifacts/${encodeURIComponent(result.id)}?environment=${environment}`)
    } catch (error) {
      setCreateError(messageFor(error))
    }
  }

  const basePath = `/workspaces/${workspaceId}/projects/${projectId}/artifacts`

  return (
    <ResourcePage
      title="Artifact Workspaces"
      description="Browse files through the same Project and Environment authorization used by the Artifacts API and Runtime."
      action={(
        <Button type="button" onClick={() => { setCreating(value => !value); setCreateError(null) }}>
          <Plus className="h-icon w-icon" />
          {creating ? 'Close form' : 'Create Workspace'}
        </Button>
      )}
    >
      <section className="flex flex-wrap items-end justify-between gap-ui-md rounded-technical border border-border bg-card p-ui-md">
        <div className="min-w-0 flex-1">
          <label htmlFor="artifact-workspace-search" className="mb-ui-xs block text-product-small font-medium">Search this page</label>
          <div className="relative max-w-xl">
            <Search aria-hidden="true" className="absolute left-ui-sm top-1/2 h-icon w-icon -translate-y-1/2 text-muted-foreground" />
            <Input
              id="artifact-workspace-search"
              value={search}
              onChange={event => setSearch(event.target.value)}
              placeholder="Name, namespace or external key"
              className="pl-control-icon"
            />
          </div>
        </div>
        <label className="grid gap-ui-xs text-product-small font-medium" htmlFor="artifact-environment">
          Environment
          <select
            id="artifact-environment"
            value={environment}
            onChange={event => {
              onEnvironmentChange(event.target.value as ArtifactEnvironment)
              setCursorStack([null])
            }}
            className="h-control rounded-control border border-input bg-background px-ui-sm text-product-small"
          >
            {environments.map(value => <option key={value} value={value}>{value[0]?.toUpperCase()}{value.slice(1)}</option>)}
          </select>
        </label>
      </section>

      {creating && (
        <form onSubmit={event => void submit(event)} className="grid gap-ui-md rounded-technical border border-border bg-surface p-ui-md sm:grid-cols-2">
          <div className="sm:col-span-2">
            <h2 className="font-medium">Create an Artifact Workspace</h2>
            <p className="mt-ui-xs text-product-small text-muted-foreground">
              The server checks current Project authority for {environment} before creating or reusing this external identity.
            </p>
          </div>
          <label className="grid min-w-0 gap-ui-xs text-product-small font-medium">
            Display name
            <Input name="name" required maxLength={255} autoFocus />
          </label>
          <label className="grid min-w-0 gap-ui-xs text-product-small font-medium">
            External namespace
            <Input name="external_namespace" required maxLength={255} />
          </label>
          <label className="grid min-w-0 gap-ui-xs text-product-small font-medium">
            External key
            <Input name="external_key" required maxLength={255} />
          </label>
          <div className="flex flex-wrap items-end gap-ui-sm">
            <Button type="submit" disabled={createWorkspace.isPending}>
              {createWorkspace.isPending ? 'Creating…' : 'Create'}
            </Button>
            <Button type="button" variant="outline" onClick={() => setCreating(false)}>Cancel</Button>
          </div>
          {createError && <p role="alert" className="sm:col-span-2 text-product-small text-error">{createError}</p>}
        </form>
      )}

      {created && <p role="status" className="text-product-small text-muted-foreground">Workspace “{created}” created. Opening its files…</p>}

      {query.isPending ? (
        <p role="status" className="rounded-technical border border-border p-ui-lg">Loading Artifact Workspaces…</p>
      ) : query.isError ? (
        <div role="alert" className="grid gap-ui-sm rounded-technical border border-error/40 p-ui-lg">
          <p>{messageFor(query.error)}</p>
          <Button type="button" variant="outline" onClick={() => void query.refetch()}>Retry</Button>
        </div>
      ) : query.data.items.length === 0 ? (
        <ResourceEmptyState
          icon={<Building2 className="h-icon-lg w-icon-lg" />}
          title="No Artifact Workspaces on this page"
          description={search ? 'Clear the search or move to another page.' : `No ${environment} Artifact Workspaces are available to this account.`}
          action={!search ? <Button type="button" onClick={() => setCreating(true)}>Create Workspace</Button> : undefined}
        />
      ) : visibleItems.length === 0 ? (
        <ResourceEmptyState
          icon={<Search className="h-icon-lg w-icon-lg" />}
          title="No Workspaces match this search"
          description="Search is limited to the loaded page. Clear it or browse another page."
          action={<Button type="button" variant="outline" onClick={() => setSearch('')}>Clear search</Button>}
        />
      ) : (
        <section aria-label="Artifact Workspaces" className="grid min-w-0 gap-ui-sm">
          <p className="text-product-small text-muted-foreground">
            {query.data.truncated ? 'This result is partial. ' : ''}
            {visibleItems.length} shown · environment {environment}
          </p>
          {visibleItems.map(item => (
            <article key={item.id} className="grid min-w-0 gap-ui-md rounded-container border border-border bg-card p-ui-md sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
              <div className="min-w-0">
                <h2 className="truncate font-medium" title={item.name}>{item.name}</h2>
                <p className="mt-ui-xs text-product-small text-muted-foreground">
                  {item.environment[0]?.toUpperCase()}{item.environment.slice(1)} · {item.status} · {item.used_bytes.toLocaleString()} / {item.quota_bytes.toLocaleString()} bytes
                </p>
                <details className="mt-ui-sm text-product-small">
                  <summary className="w-fit cursor-pointer text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">External identity</summary>
                  <dl className="mt-ui-xs grid min-w-0 gap-x-ui-lg gap-y-ui-xs sm:grid-cols-2">
                    <div className="min-w-0"><dt className="text-muted-foreground">Namespace</dt><dd className="break-all font-mono">{item.external_namespace}</dd></div>
                    <div className="min-w-0"><dt className="text-muted-foreground">Key</dt><dd className="break-all font-mono">{item.external_key}</dd></div>
                  </dl>
                </details>
              </div>
              <Button type="button" variant="outline" className="w-full sm:w-auto" onClick={() => navigate(`${basePath}/${encodeURIComponent(item.id)}?environment=${environment}`)}>
                Browse files
              </Button>
            </article>
          ))}
        </section>
      )}

      {query.data?.truncated && <p role="status" className="text-product-small text-warning">The server marked this catalog as truncated; not all Workspaces are represented.</p>}
      {query.data && (cursorStack.length > 1 || query.data.has_more) && (
        <ResourceToolbar className="justify-end">
          <Button type="button" variant="outline" disabled={cursorStack.length <= 1 || query.isFetching} onClick={() => setCursorStack(stack => stack.slice(0, -1))}>
            <ChevronLeft className="h-icon w-icon" /> Previous
          </Button>
          <Button type="button" variant="outline" disabled={!query.data.has_more || !query.data.next_cursor || query.isFetching} onClick={() => {
            if (query.data?.next_cursor) setCursorStack(stack => [...stack, query.data!.next_cursor])
          }}>
            Next <ChevronRight className="h-icon w-icon" />
          </Button>
        </ResourceToolbar>
      )}
    </ResourcePage>
  )
}
