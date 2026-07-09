import { useMemo, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import {
  Activity,
  AlertTriangle,
  Ban,
  Bot,
  Clock3,
  Key,
  Plus,
  RotateCcw,
  Search,
  ShieldCheck,
  Zap,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { useAgents, useReleases } from '@/features/agents/hooks'
import { CreateApiKeyDialog } from '@/features/api-keys/components/CreateApiKeyDialog'
import { ApiKeySecretReveal } from '@/features/api-keys/components/ApiKeySecretReveal'
import {
  useApiKeys,
  useRevokeApiKey,
  useRotateApiKey,
} from '@/features/api-keys/hooks'
import type {
  ApiKey,
  ApiKeyKind,
  ApiKeyScope,
  CreateApiKeyResponse,
  RuntimeEnvironment,
} from '@/features/api-keys/types'

type KeyTab = 'all' | ApiKeyKind
type StatusFilter = 'all' | ApiKey['status']
type EnvironmentFilter = 'all' | RuntimeEnvironment

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : 'Never'
}

function MinimalShell({
  title,
  description,
  action,
  children,
}: {
  title: string
  description: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">{title}</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted">{description}</p>
        </div>
        {action}
      </div>
      {children}
    </div>
  )
}

function Pill({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'primary' | 'danger' | 'warning' }) {
  const toneClass = tone === 'primary'
    ? 'border-primary/30 bg-primary/10 text-primary-light'
    : tone === 'danger'
      ? 'border-red-500/30 bg-red-500/10 text-red-200'
      : tone === 'warning'
        ? 'border-yellow-500/30 bg-yellow-500/10 text-yellow-200'
        : 'border-border/80 bg-background/70 text-muted'
  return <span className={`rounded-full border px-2.5 py-1 text-[11px] ${toneClass}`}>{children}</span>
}

function permissionLabel(scope: string): string {
  if (scope === 'traces:read') return 'Traces'
  if (scope === 'usage:read') return 'Usage & cost'
  if (scope === 'runtime:execute') return 'Legacy runtime access'
  return scope
}

function FilterSelect({
  value,
  onChange,
  children,
  label,
}: {
  value: string
  onChange: (value: string) => void
  children: ReactNode
  label: string
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="h-10 rounded-lg border border-border/80 bg-surface/65 px-3 text-xs text-white outline-none transition-colors focus:border-primary/40"
    >
      {children}
    </select>
  )
}

function KeyTypeTabs({
  active,
  onChange,
  counts,
}: {
  active: KeyTab
  onChange: (tab: KeyTab) => void
  counts: Record<KeyTab, number>
}) {
  const tabs: Array<{ value: KeyTab; label: string }> = [
    { value: 'all', label: 'All' },
    { value: 'runtime', label: 'Runtime' },
    { value: 'project', label: 'Project' },
  ]
  return (
    <div className="inline-flex rounded-xl border border-border/80 bg-surface/55 p-1">
      {tabs.map((tab) => (
        <button
          key={tab.value}
          type="button"
          onClick={() => onChange(tab.value)}
          className={`rounded-lg px-3 py-2 text-xs font-medium transition-colors ${active === tab.value ? 'bg-primary/12 text-primary-light' : 'text-muted hover:bg-background/60 hover:text-white'}`}
        >
          {tab.label} <span className="ml-1 text-[10px] opacity-70">{counts[tab.value]}</span>
        </button>
      ))}
    </div>
  )
}

function ApiKeyCard({
  apiKey,
  agentName,
  onClick,
}: {
  apiKey: ApiKey
  agentName?: string | null
  onClick: () => void
}) {
  const runtime = apiKey.kind === 'runtime'
  const legacyRuntime = !runtime && apiKey.scopes.includes('runtime:execute')

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Open API key settings for ${apiKey.name}`}
      className="group flex min-h-[280px] flex-col rounded-xl border border-border/90 bg-surface/70 p-5 text-left transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/35 hover:bg-surface/85 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <span className="flex items-start justify-between gap-3">
        <span className="flex items-center gap-3">
          <span className={`flex h-10 w-10 items-center justify-center rounded-xl border ${runtime ? 'border-primary/25 bg-primary/10 text-primary-light' : 'border-border bg-background text-primary-light'}`}>
            {runtime ? <Zap className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
          </span>
          <span>
            <span className="block text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">{runtime ? 'Runtime Key' : 'Project Key'}</span>
            <span className="mt-0.5 block text-[11px] text-muted">{runtime ? 'Agent deployment' : 'Project operations'}</span>
          </span>
        </span>
        <StatusBadge status={apiKey.status} />
      </span>

      <span className="mt-5 block min-w-0">
        <span className="block truncate text-base font-semibold text-white">{apiKey.name}</span>
        <code className="mt-2 block truncate text-xs text-muted">{apiKey.key_prefix}...</code>
      </span>

      <span className="my-4 block h-px bg-border/80" />

      {runtime ? (
        <span className="grid gap-2 text-xs text-muted">
          <span className="flex items-center gap-2">
            <Bot className="h-3.5 w-3.5 text-primary-light" />
            <span className="truncate text-white">{agentName || 'Agent unavailable'}</span>
          </span>
          <span>Environment · <span className="capitalize text-white">{apiKey.environment}</span></span>
        </span>
      ) : (
        <span className="grid gap-2 text-xs text-muted">
          <span>Access · <span className="text-white">Project operations</span></span>
          {legacyRuntime && <span className="text-yellow-200">Includes legacy runtime access</span>}
        </span>
      )}

      <span className="mt-4 flex flex-wrap gap-2">
        {runtime
          ? apiKey.interfaces.map((item) => <Pill key={item} tone="primary">{item}</Pill>)
          : apiKey.scopes.map((scope) => <Pill key={scope} tone={scope === 'runtime:execute' ? 'warning' : 'default'}>{permissionLabel(scope)}</Pill>)}
      </span>

      <span className="mt-auto grid gap-1.5 pt-5 text-[11px] text-muted">
        <span>Last used · {formatDate(apiKey.last_used_at)}</span>
        <span>Expires · {apiKey.expires_at ? formatDate(apiKey.expires_at) : 'Never'}</span>
      </span>
    </button>
  )
}

function ProjectKeyDetails({ apiKey }: { apiKey: ApiKey }) {
  const legacyRuntime = apiKey.scopes.includes('runtime:execute')
  const permissions: Array<{ scope: ApiKeyScope; label: string; description: string }> = [
    { scope: 'traces:read', label: 'Traces', description: 'Read execution traces across this Project.' },
    { scope: 'usage:read', label: 'Usage & cost', description: 'Read metering, usage and cost data.' },
  ]

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
        <div>
          <h3 className="text-sm font-semibold text-white">Project access</h3>
          <p className="mt-1 text-xs leading-5 text-muted">Permissions granted to requests signed with this Project Key.</p>
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          {permissions.map((permission) => {
            const enabled = apiKey.scopes.includes(permission.scope)
            return (
              <div key={permission.scope} className={`rounded-xl border p-3 ${enabled ? 'border-primary/35 bg-primary/10' : 'border-border/80 bg-background/50 opacity-55'}`}>
                <div className="flex items-center gap-2">
                  <Activity className={`h-4 w-4 ${enabled ? 'text-primary-light' : 'text-muted'}`} />
                  <p className="text-sm font-medium text-white">{permission.label}</p>
                </div>
                <p className="mt-1 text-xs leading-5 text-muted">{permission.description}</p>
              </div>
            )
          })}
        </div>
      </section>

      {legacyRuntime && (
        <section className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-300" />
            <div>
              <h3 className="text-sm font-semibold text-yellow-100">Legacy runtime access</h3>
              <p className="mt-1 text-xs leading-5 text-yellow-100/70">This Project Key can execute legacy runtime routes. New integrations should use an Agent-bound Runtime Key.</p>
            </div>
          </div>
        </section>
      )}
    </div>
  )
}

function RuntimeKeyDetails({ apiKey, agentName }: { apiKey: ApiKey; agentName?: string | null }) {
  const { data: releases = [], isLoading: releasesLoading } = useReleases(apiKey.agent_id ?? undefined)
  const currentRelease = releases.find((release) => release.status === apiKey.environment) ?? null

  return (
    <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
      <div>
        <h3 className="text-sm font-semibold text-white">Runtime deployment</h3>
        <p className="mt-1 text-xs leading-5 text-muted">This key represents one logical Agent deployment. Deploys and rollbacks do not require changing the key.</p>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-border/80 bg-background/55 p-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Agent</p>
          <p className="mt-2 text-sm font-medium text-white">{agentName || 'Agent unavailable'}</p>
          {apiKey.agent_id && <code className="mt-1 block break-all text-[10px] text-muted">{apiKey.agent_id}</code>}
        </div>
        <div className="rounded-xl border border-border/80 bg-background/55 p-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Environment</p>
          <p className="mt-2 text-sm font-medium capitalize text-white">{apiKey.environment}</p>
          <code className="mt-1 block text-[10px] text-primary-light">woobe_{apiKey.environment}_...</code>
        </div>
        <div className={`rounded-xl border p-4 sm:col-span-2 ${releasesLoading || currentRelease ? 'border-border/80 bg-background/55' : 'border-yellow-500/25 bg-yellow-500/5'}`}>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Current release</p>
          {releasesLoading ? (
            <p className="mt-2 text-xs text-muted">Checking current deployment…</p>
          ) : currentRelease ? (
            <p className="mt-2 text-sm text-white">{currentRelease.version}</p>
          ) : (
            <p className="mt-2 text-xs leading-5 text-yellow-200">No {apiKey.environment} release is deployed. Requests currently return 409.</p>
          )}
        </div>
        <div className="rounded-xl border border-border/80 bg-background/55 p-4 sm:col-span-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Allowed interfaces</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {apiKey.interfaces.map((item) => <Pill key={item} tone="primary">{item}</Pill>)}
          </div>
        </div>
      </div>
    </section>
  )
}

function KeyGroup({
  title,
  description,
  keys,
  agentNames,
  onSelect,
}: {
  title: string
  description: string
  keys: ApiKey[]
  agentNames: Map<string, string>
  onSelect: (keyId: string) => void
}) {
  if (keys.length === 0) return null
  return (
    <section className="space-y-3">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-white">{title}</h2>
          <p className="mt-1 text-xs text-muted">{description}</p>
        </div>
        <span className="text-xs text-muted">{keys.length}</span>
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {keys.map((apiKey) => (
          <ApiKeyCard
            key={apiKey.id}
            apiKey={apiKey}
            agentName={apiKey.agent_id ? agentNames.get(apiKey.agent_id) : null}
            onClick={() => onSelect(apiKey.id)}
          />
        ))}
      </div>
    </section>
  )
}

export default function ApiKeysPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: keys, isLoading, isError, error, refetch } = useApiKeys(projectId)
  const { data: agents = [] } = useAgents(projectId)
  const revokeKey = useRevokeApiKey(projectId)
  const rotateKey = useRotateApiKey(projectId)
  const [showCreate, setShowCreate] = useState(false)
  const [revealedKey, setRevealedKey] = useState<CreateApiKeyResponse | null>(null)
  const [query, setQuery] = useState('')
  const [activeTab, setActiveTab] = useState<KeyTab>('all')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [environmentFilter, setEnvironmentFilter] = useState<EnvironmentFilter>('all')
  const [agentFilter, setAgentFilter] = useState('all')
  const [selectedKeyId, setSelectedKeyId] = useState<string | null>(null)

  const items = keys ?? []
  const selectedKey = items.find((key) => key.id === selectedKeyId) ?? null
  const agentNames = useMemo(
    () => new Map(agents.map((agent) => [agent.id, agent.name])),
    [agents],
  )

  const counts: Record<KeyTab, number> = {
    all: items.length,
    runtime: items.filter((key) => key.kind === 'runtime').length,
    project: items.filter((key) => key.kind === 'project').length,
  }

  const visibleKeys = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return items.filter((key) => {
      const agentName = key.agent_id ? agentNames.get(key.agent_id) ?? '' : ''
      const matchesTab = activeTab === 'all' || key.kind === activeTab
      const matchesStatus = statusFilter === 'all' || key.status === statusFilter
      const matchesEnvironment = environmentFilter === 'all' || key.environment === environmentFilter
      const matchesAgent = agentFilter === 'all' || key.agent_id === agentFilter
      const matchesQuery = !normalizedQuery || (
        key.name.toLowerCase().includes(normalizedQuery)
        || key.key_prefix.toLowerCase().includes(normalizedQuery)
        || key.status.toLowerCase().includes(normalizedQuery)
        || key.kind.toLowerCase().includes(normalizedQuery)
        || (key.environment ?? '').toLowerCase().includes(normalizedQuery)
        || agentName.toLowerCase().includes(normalizedQuery)
        || key.scopes.some((scope) => scope.toLowerCase().includes(normalizedQuery))
        || key.interfaces.some((item) => item.toLowerCase().includes(normalizedQuery))
      )
      return matchesTab && matchesStatus && matchesEnvironment && matchesAgent && matchesQuery
    })
  }, [items, agentNames, activeTab, statusFilter, environmentFilter, agentFilter, query])

  const runtimeKeys = visibleKeys.filter((key) => key.kind === 'runtime')
  const projectKeys = visibleKeys.filter((key) => key.kind === 'project')
  const selectedAgentName = selectedKey?.agent_id ? agentNames.get(selectedKey.agent_id) : null
  const revealedAgentName = revealedKey?.agent_id ? agentNames.get(revealedKey.agent_id) : null

  const handleRevoke = async (apiKey: ApiKey) => {
    if (!window.confirm(`Revoke API key “${apiKey.name}”?`)) return
    try {
      await revokeKey.mutateAsync(apiKey.id)
      await refetch()
      setSelectedKeyId(null)
      toast.success('API key revoked')
    } catch (revokeError) {
      toast.error(revokeError instanceof Error ? revokeError.message : 'Failed to revoke key')
    }
  }

  const handleRotate = async (apiKey: ApiKey) => {
    if (!window.confirm(`Rotate API key “${apiKey.name}”? The current key will stop working immediately.`)) return
    try {
      const result = await rotateKey.mutateAsync({ apiKeyId: apiKey.id })
      await refetch()
      setSelectedKeyId(null)
      setRevealedKey(result)
      toast.success('API key rotated')
    } catch (rotateError) {
      toast.error(rotateError instanceof Error ? rotateError.message : 'Failed to rotate key')
    }
  }

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  const hasFilters = query.trim() || activeTab !== 'all' || statusFilter !== 'all' || environmentFilter !== 'all' || agentFilter !== 'all'

  return (
    <MinimalShell
      title="API Keys"
      description="Create and manage credentials for Agent runtime execution and Project operations."
      action={(
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create key
        </Button>
      )}
    >
      <div className="flex flex-col gap-4 rounded-xl border border-border/80 bg-surface/45 p-4">
        <KeyTypeTabs active={activeTab} onChange={setActiveTab} counts={counts} />

        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by name, prefix, Agent or environment..."
              className="h-10 pl-9"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <FilterSelect label="Status filter" value={statusFilter} onChange={(value) => setStatusFilter(value as StatusFilter)}>
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="expired">Expired</option>
              <option value="revoked">Revoked</option>
            </FilterSelect>
            <FilterSelect label="Environment filter" value={environmentFilter} onChange={(value) => setEnvironmentFilter(value as EnvironmentFilter)}>
              <option value="all">All environments</option>
              <option value="staging">Staging</option>
              <option value="production">Production</option>
            </FilterSelect>
            <FilterSelect label="Agent filter" value={agentFilter} onChange={setAgentFilter}>
              <option value="all">All Agents</option>
              {agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
            </FilterSelect>
          </div>
        </div>
      </div>

      {visibleKeys.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border/80 bg-surface/40 px-6 py-10 text-center">
          <Key className="mx-auto h-5 w-5 text-muted" />
          <h2 className="mt-3 text-sm font-semibold text-white">{items.length === 0 ? 'No API keys yet' : 'No API keys found'}</h2>
          <p className="mt-1 text-sm text-muted">{hasFilters ? 'Adjust the search or filters.' : 'Create a Runtime Key or Project Key for this Project.'}</p>
          {items.length === 0 && (
            <Button className="mt-4" size="sm" onClick={() => setShowCreate(true)}>
              <Plus className="mr-2 h-4 w-4" /> Create key
            </Button>
          )}
        </div>
      ) : activeTab === 'all' ? (
        <div className="space-y-8">
          <KeyGroup
            title="Runtime Keys"
            description="Credentials bound to an Agent and environment."
            keys={runtimeKeys}
            agentNames={agentNames}
            onSelect={setSelectedKeyId}
          />
          <KeyGroup
            title="Project Keys"
            description="Credentials for traces, usage and other Project operations."
            keys={projectKeys}
            agentNames={agentNames}
            onSelect={setSelectedKeyId}
          />
        </div>
      ) : (
        <KeyGroup
          title={activeTab === 'runtime' ? 'Runtime Keys' : 'Project Keys'}
          description={activeTab === 'runtime' ? 'Credentials bound to an Agent and environment.' : 'Credentials for traces, usage and other Project operations.'}
          keys={visibleKeys}
          agentNames={agentNames}
          onSelect={setSelectedKeyId}
        />
      )}

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
                  <div className={`flex h-11 w-11 items-center justify-center rounded-xl border ${selectedKey.kind === 'runtime' ? 'border-primary/25 bg-primary/10 text-primary-light' : 'border-border bg-background text-primary-light'}`}>
                    {selectedKey.kind === 'runtime' ? <Zap className="h-5 w-5" /> : <ShieldCheck className="h-5 w-5" />}
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
                  <div className="flex items-center gap-2">
                    <Clock3 className="h-4 w-4 text-muted" />
                    <p className="text-sm font-semibold text-white">Usage state</p>
                  </div>
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
                {selectedKey.kind === 'runtime'
                  ? <RuntimeKeyDetails apiKey={selectedKey} agentName={selectedAgentName} />
                  : <ProjectKeyDetails apiKey={selectedKey} />}

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

      <CreateApiKeyDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        projectId={projectId!}
      />

      <Dialog
        open={Boolean(revealedKey)}
        onClose={() => setRevealedKey(null)}
        title="New API key secret"
        className="max-w-2xl"
      >
        {revealedKey && (
          <div>
            <ApiKeySecretReveal apiKey={revealedKey} agentName={revealedAgentName} />
            <div className="mt-5 flex justify-end border-t border-border/80 pt-4">
              <Button onClick={() => setRevealedKey(null)}>Done</Button>
            </div>
          </div>
        )}
      </Dialog>
    </MinimalShell>
  )
}
