import { useMemo, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import {
  useApiKeys,
  useCreateApiKey,
  useRevokeApiKey,
  useRotateApiKey,
} from '@/features/api-keys/hooks'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { StatusBadge } from '@/components/common/StatusBadge'
import { CopyButton } from '@/components/common/CopyButton'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  createApiKeySchema,
  type CreateApiKeyFormData,
} from '@/features/api-keys/schemas'
import { AlertTriangle, Ban, Key, Plus, RotateCcw, Search, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import type { ApiKey, ApiKeyScope } from '@/features/api-keys/types'

const SCOPE_OPTIONS: Array<{ value: ApiKeyScope; label: string; description: string }> = [
  { value: 'runtime:execute', label: 'Runtime execute', description: 'Execute legacy project runtime requests' },
  { value: 'traces:read', label: 'Traces read', description: 'Read execution traces' },
  { value: 'usage:read', label: 'Usage read', description: 'Read usage and cost data' },
]

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : 'Never'
}

function MinimalShell({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">{title}</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">{description}</p>
      </div>
      {children}
    </div>
  )
}

function Pill({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'primary' | 'danger' }) {
  const toneClass = tone === 'primary'
    ? 'border-primary/30 bg-primary/10 text-primary-light'
    : tone === 'danger'
      ? 'border-red-500/30 bg-red-500/10 text-red-200'
      : 'border-border/80 bg-background/70 text-muted'
  return <span className={`rounded-full border px-2.5 py-1 text-xs ${toneClass}`}>{children}</span>
}

function CreateCard({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex min-h-[240px] flex-col items-center justify-center rounded-xl border border-dashed border-primary/40 bg-surface/35 p-6 text-center transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/60 hover:bg-primary/5 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <span className="flex h-14 w-14 items-center justify-center rounded-full border border-primary/50 bg-primary/10 text-primary-light transition-colors duration-200 group-hover:bg-primary/15">
        <Plus className="h-6 w-6" />
      </span>
      <span className="mt-5 text-base font-semibold text-white">New Project API key</span>
      <span className="mt-2 max-w-[240px] text-sm leading-6 text-muted">Create a project-scoped credential for operational APIs.</span>
    </button>
  )
}

function NoResults({ query }: { query: string }) {
  return (
    <div className="rounded-xl border border-border/80 bg-surface/50 px-5 py-4">
      <h2 className="text-sm font-semibold text-white">No API keys found</h2>
      <p className="mt-1 text-sm text-muted">
        {query.trim() ? 'Adjust the search term.' : 'Create a Project API key or create a Runtime Key from an Agent API Reference.'}
      </p>
    </div>
  )
}

function ApiKeyCard({ apiKey, onClick }: { apiKey: ApiKey; onClick: () => void }) {
  const runtime = apiKey.kind === 'runtime'
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Open API key settings for ${apiKey.name}`}
      className="group flex min-h-[240px] flex-col rounded-xl border border-border/90 bg-surface/70 p-6 text-left transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/35 hover:bg-surface/85 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <span className="flex items-start justify-between gap-3">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background text-primary-light shadow-sm transition-colors duration-200 group-hover:border-primary/30 group-hover:bg-primary/10">
          <Key className="h-5 w-5" />
        </span>
        <StatusBadge status={apiKey.status} />
      </span>

      <span className="mt-6 block min-w-0">
        <span className="block truncate text-base font-semibold text-white">{apiKey.name}</span>
        <code className="mt-2 block truncate text-xs text-muted">{apiKey.key_prefix}...</code>
      </span>

      <span className="my-5 block h-px bg-border/80" />

      <span className="grid gap-2 text-xs text-muted">
        <span>Type · {runtime ? 'Runtime Key' : 'Project Key'}</span>
        {runtime && <span>Environment · <span className="capitalize">{apiKey.environment}</span></span>}
        <span>Expires · {apiKey.expires_at ? formatDate(apiKey.expires_at) : 'Never'}</span>
      </span>

      <span className="mt-auto flex flex-wrap gap-2 pt-5">
        {runtime
          ? apiKey.interfaces.map((item) => <Pill key={item} tone="primary">{item}</Pill>)
          : apiKey.scopes.map((scope) => <Pill key={scope}>{scope}</Pill>)}
      </span>
    </button>
  )
}

function ScopeList({ scopes }: { scopes: ApiKeyScope[] }) {
  return (
    <div className="grid gap-2 md:grid-cols-3">
      {SCOPE_OPTIONS.map((scope) => {
        const enabled = scopes.includes(scope.value)
        return (
          <div key={scope.value} className={`rounded-xl border p-3 ${enabled ? 'border-primary/35 bg-primary/10' : 'border-border/80 bg-background/60 opacity-60'}`}>
            <div className="flex items-center gap-2">
              <ShieldCheck className={`h-4 w-4 ${enabled ? 'text-primary-light' : 'text-muted'}`} />
              <p className="text-sm font-medium text-white">{scope.label}</p>
            </div>
            <p className="mt-1 text-xs leading-5 text-muted">{scope.description}</p>
          </div>
        )
      })}
    </div>
  )
}

function RuntimeBinding({ apiKey }: { apiKey: ApiKey }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <div className="rounded-xl border border-border/80 bg-background/60 p-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Agent ID</p>
        <code className="mt-2 block break-all text-xs text-white">{apiKey.agent_id}</code>
      </div>
      <div className="rounded-xl border border-border/80 bg-background/60 p-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Environment</p>
        <p className="mt-2 text-sm font-medium capitalize text-white">{apiKey.environment}</p>
      </div>
      <div className="rounded-xl border border-border/80 bg-background/60 p-4 md:col-span-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Allowed interfaces</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {apiKey.interfaces.map((item) => <Pill key={item} tone="primary">{item}</Pill>)}
        </div>
      </div>
    </div>
  )
}

export default function ApiKeysPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: keys, isLoading, isError, error, refetch } = useApiKeys(projectId)
  const createKey = useCreateApiKey(projectId)
  const revokeKey = useRevokeApiKey(projectId)
  const rotateKey = useRotateApiKey(projectId)
  const [showCreate, setShowCreate] = useState(false)
  const [newKey, setNewKey] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [selectedKeyId, setSelectedKeyId] = useState<string | null>(null)

  const form = useForm<CreateApiKeyFormData>({
    resolver: zodResolver(createApiKeySchema),
    defaultValues: {
      name: '',
      scopes: ['runtime:execute'],
      expires_at: '',
    },
  })

  const items = keys ?? []
  const selectedKey = items.find((key) => key.id === selectedKeyId) ?? null

  const visibleKeys = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) return items

    return items.filter((key) => (
      key.name.toLowerCase().includes(normalizedQuery)
      || key.key_prefix.toLowerCase().includes(normalizedQuery)
      || key.status.toLowerCase().includes(normalizedQuery)
      || key.kind.toLowerCase().includes(normalizedQuery)
      || (key.environment ?? '').toLowerCase().includes(normalizedQuery)
      || key.scopes.some((scope) => scope.toLowerCase().includes(normalizedQuery))
      || key.interfaces.some((item) => item.toLowerCase().includes(normalizedQuery))
    ))
  }, [items, query])

  const openCreateDialog = () => {
    setNewKey(null)
    setShowCreate(true)
  }

  const handleCreate = async (data: CreateApiKeyFormData) => {
    try {
      const result = await createKey.mutateAsync({
        name: data.name,
        scopes: data.scopes,
        expires_at: data.expires_at ? new Date(data.expires_at).toISOString() : null,
      })
      setNewKey(result.key)
      toast.success('API key created')
      form.reset({ name: '', scopes: ['runtime:execute'], expires_at: '' })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create key')
    }
  }

  const handleRevoke = async (apiKey: ApiKey) => {
    if (!window.confirm(`Revoke API key “${apiKey.name}”?`)) return
    try {
      await revokeKey.mutateAsync(apiKey.id)
      await refetch()
      setSelectedKeyId(null)
      toast.success('API key revoked')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to revoke key')
    }
  }

  const handleRotate = async (apiKey: ApiKey) => {
    if (!window.confirm(`Rotate API key “${apiKey.name}”? The current key will stop working immediately.`)) return
    try {
      const result = await rotateKey.mutateAsync({ apiKeyId: apiKey.id })
      await refetch()
      setSelectedKeyId(null)
      setNewKey(result.key)
      setShowCreate(true)
      toast.success('API key rotated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to rotate key')
    }
  }

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  const hasNoKeys = items.length === 0
  const hasSearchMiss = query.trim().length > 0 && visibleKeys.length === 0

  return (
    <MinimalShell
      title="API Keys"
      description="Operate project-scoped credentials and Agent-bound Runtime Keys. Runtime Keys are created from an Agent API Reference so target and environment stay explicit."
    >
      <div className="relative max-w-3xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search API keys..."
          className="h-11 pl-9"
        />
      </div>

      {(hasNoKeys || hasSearchMiss) && <NoResults query={query} />}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <CreateCard onClick={openCreateDialog} />
        {visibleKeys.map((apiKey) => (
          <ApiKeyCard key={apiKey.id} apiKey={apiKey} onClick={() => setSelectedKeyId(apiKey.id)} />
        ))}
      </div>

      <Dialog
        open={Boolean(selectedKey)}
        onClose={() => setSelectedKeyId(null)}
        title="API key settings"
        className="max-h-[90vh] max-w-4xl overflow-hidden"
      >
        {selectedKey && (
          <div className="max-h-[calc(90vh-96px)] overflow-y-auto pr-1">
            <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
              <aside className="space-y-4 lg:sticky lg:top-0 lg:self-start">
                <div className="rounded-xl border border-border/90 bg-surface/70 p-4">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-background text-primary-light">
                    <Key className="h-5 w-5" />
                  </div>
                  <div className="mt-5 min-w-0">
                    <h2 className="truncate text-base font-semibold text-white">{selectedKey.name}</h2>
                    <code className="mt-1 block truncate text-xs text-muted">{selectedKey.key_prefix}...</code>
                  </div>
                  <div className="mt-5 flex flex-wrap gap-2">
                    <StatusBadge status={selectedKey.status} />
                    <Pill tone={selectedKey.kind === 'runtime' ? 'primary' : 'default'}>{selectedKey.kind === 'runtime' ? 'Runtime Key' : 'Project Key'}</Pill>
                  </div>
                </div>

                <div className="rounded-xl border border-border/90 bg-background/60 p-4">
                  <p className="text-sm font-semibold text-white">Usage state</p>
                  <div className="mt-3 space-y-2 text-xs leading-5 text-muted">
                    <p>Last used · {formatDate(selectedKey.last_used_at)}</p>
                    <p>Created · {formatDate(selectedKey.created_at)}</p>
                    <p>Expires · {selectedKey.expires_at ? formatDate(selectedKey.expires_at) : 'Never'}</p>
                  </div>
                </div>

                <section className="rounded-xl border border-red-500/25 bg-red-500/5 p-4">
                  <h3 className="text-sm font-semibold text-red-100">Danger zone</h3>
                  <p className="mt-1 text-xs leading-5 text-red-200/80">Revoke this key permanently.</p>
                  <Button className="mt-4 w-full" variant="destructive" size="sm" onClick={() => void handleRevoke(selectedKey)} loading={revokeKey.isPending} disabled={selectedKey.status !== 'active'}>
                    <Ban className="mr-2 h-4 w-4" />
                    Revoke key
                  </Button>
                </section>
              </aside>

              <main className="space-y-5">
                <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                  <div className="mb-4">
                    <h3 className="text-sm font-semibold text-white">{selectedKey.kind === 'runtime' ? 'Runtime binding' : 'Scopes'}</h3>
                    <p className="mt-1 text-xs leading-5 text-muted">
                      {selectedKey.kind === 'runtime'
                        ? 'Target, environment and interfaces are preserved when this key is rotated.'
                        : 'Permissions granted to requests signed with this key.'}
                    </p>
                  </div>
                  {selectedKey.kind === 'runtime'
                    ? <RuntimeBinding apiKey={selectedKey} />
                    : <ScopeList scopes={selectedKey.scopes} />}
                </section>

                <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                  <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-white">Rotate key</h3>
                      <p className="mt-1 text-xs leading-5 text-muted">Generate a replacement secret. The current key stops working immediately.</p>
                    </div>
                    <Button variant="outline" onClick={() => void handleRotate(selectedKey)} loading={rotateKey.isPending} disabled={selectedKey.status !== 'active'}>
                      <RotateCcw className="mr-2 h-4 w-4" />
                      Rotate
                    </Button>
                  </div>
                </section>
              </main>
            </div>
          </div>
        )}
      </Dialog>

      <Dialog
        open={showCreate}
        onClose={() => { setShowCreate(false); setNewKey(null) }}
        title={newKey ? 'API Key Ready' : 'Create Project API Key'}
        className="max-w-2xl"
      >
        {newKey ? (
          <div className="space-y-4">
            <div className="rounded-xl border border-yellow-500/50 bg-yellow-500/10 p-4">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-yellow-400" />
                <div>
                  <p className="text-sm font-medium text-yellow-400">Copy this key now</p>
                  <p className="text-xs text-yellow-400/70">It is shown once and cannot be recovered later.</p>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 rounded-xl border border-border bg-background p-3">
              <code className="flex-1 break-all text-sm">{newKey}</code>
              <CopyButton text={newKey} />
            </div>
            <Button className="w-full" onClick={() => { setShowCreate(false); setNewKey(null) }}>
              Done
            </Button>
          </div>
        ) : (
          <form onSubmit={form.handleSubmit(handleCreate)} className="space-y-4">
            <Input
              {...form.register('name')}
              error={form.formState.errors.name?.message}
              placeholder="Key name"
            />
            <div className="space-y-2">
              <p className="text-sm font-medium">Scopes</p>
              <div className="grid gap-2 md:grid-cols-3">
                {SCOPE_OPTIONS.map((scope) => (
                  <label key={scope.value} className="rounded-xl border border-border/80 bg-background/60 p-3 text-sm text-muted">
                    <span className="flex items-center gap-2 text-white">
                      <input type="checkbox" value={scope.value} {...form.register('scopes')} />
                      {scope.label}
                    </span>
                    <span className="mt-1 block text-xs leading-5 text-muted">{scope.description}</span>
                  </label>
                ))}
              </div>
              {form.formState.errors.scopes?.message && (
                <p className="text-xs text-red-400">{form.formState.errors.scopes.message}</p>
              )}
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium" htmlFor="api-key-expires-at">Expiration (optional)</label>
              <Input id="api-key-expires-at" type="datetime-local" {...form.register('expires_at')} />
            </div>
            <div className="flex justify-end gap-2 border-t border-border pt-4">
              <Button type="button" variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button type="submit" loading={createKey.isPending}>Create</Button>
            </div>
          </form>
        )}
      </Dialog>
    </MinimalShell>
  )
}
