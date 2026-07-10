import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft,
  Ban,
  Bot,
  ChevronRight,
  Clock3,
  Key,
  Layers3,
  Pencil,
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
import { useAgents } from '@/features/agents/hooks'
import { CreateApiKeyDialog } from '@/features/api-keys/components/CreateApiKeyDialog'
import { ApiKeySecretReveal } from '@/features/api-keys/components/ApiKeySecretReveal'
import { RotateApiKeyDialog } from '@/features/api-keys/components/RotateApiKeyDialog'
import {
  useApiKeys,
  useRevokeApiKey,
  useRotateApiKey,
  useUpdateApiKeyCredential,
} from '@/features/api-keys/hooks'
import type {
  ApiKey,
  ApiKeyKind,
  CreateApiKeyResponse,
  RuntimeEnvironment,
} from '@/features/api-keys/types'

type KeyTab = ApiKeyKind
type EnvironmentFilter = 'all' | RuntimeEnvironment
type StatusFilter = 'all' | ApiKey['status']

interface CredentialGroup {
  id: string
  current: ApiKey
  revisions: ApiKey[]
}

interface AgentDescriptor {
  id: string
  name: string
  unavailable?: boolean
}

function dateValue(value?: string | null): number {
  return value ? new Date(value).getTime() : 0
}

function formatDate(value?: string | null): string {
  return value ? new Date(value).toLocaleString() : 'Never'
}

function environmentLabel(environment?: RuntimeEnvironment | null): string {
  if (environment === 'production') return 'Production'
  if (environment === 'staging') return 'Staging'
  return 'Project'
}

function groupCredentials(keys: ApiKey[]): CredentialGroup[] {
  const groups = new Map<string, ApiKey[]>()
  for (const key of keys) {
    const credentialId = key.credential_id || key.id
    groups.set(credentialId, [...(groups.get(credentialId) ?? []), key])
  }

  return Array.from(groups, ([id, group]) => {
    const revisions = [...group].sort((left, right) => (
      dateValue(right.created_at) - dateValue(left.created_at)
    ))
    const current = revisions.find((key) => key.status === 'active') ?? revisions[0]!
    return { id, current, revisions }
  }).sort((left, right) => {
    if (left.current.status === 'active' && right.current.status !== 'active') return -1
    if (left.current.status !== 'active' && right.current.status === 'active') return 1
    return dateValue(right.current.created_at) - dateValue(left.current.created_at)
  })
}

function Pill({ children, active = false }: { children: ReactNode; active?: boolean }) {
  return (
    <span className={`rounded-full border px-2.5 py-1 text-[10px] font-medium ${active ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-border/80 bg-background/55 text-muted'}`}>
      {children}
    </span>
  )
}

function PageHeader({ action }: { action: ReactNode }) {
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">API Keys</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">Manage stable credentials and their secret rotation history.</p>
      </div>
      {action}
    </div>
  )
}

function KeyTabs({ active, counts, onChange }: { active: KeyTab; counts: Record<KeyTab, number>; onChange: (value: KeyTab) => void }) {
  return (
    <div className="inline-flex rounded-xl border border-border/80 bg-surface/55 p-1">
      {(['runtime', 'project'] as KeyTab[]).map((tab) => (
        <button
          key={tab}
          type="button"
          onClick={() => onChange(tab)}
          className={`rounded-lg px-3 py-2 text-xs font-medium transition-colors ${active === tab ? 'bg-primary/12 text-primary-light' : 'text-muted hover:bg-background/60 hover:text-white'}`}
        >
          {tab === 'runtime' ? 'Runtime' : 'Project'} <span className="ml-1 text-[10px] opacity-70">{counts[tab]}</span>
        </button>
      ))}
    </div>
  )
}

function AgentCard({
  agent,
  credentials,
  onClick,
}: {
  agent: AgentDescriptor
  credentials: CredentialGroup[]
  onClick: () => void
}) {
  const active = credentials.filter((credential) => credential.current.status === 'active').length
  const production = credentials.filter((credential) => credential.current.environment === 'production' && credential.current.status === 'active').length
  const staging = credentials.filter((credential) => credential.current.environment === 'staging' && credential.current.status === 'active').length
  const lastUsedAt = credentials.reduce<string | null>((latest, credential) => {
    const candidate = credential.revisions.reduce<string | null>((revisionLatest, revision) => (
      dateValue(revision.last_used_at) > dateValue(revisionLatest) ? revision.last_used_at ?? null : revisionLatest
    ), null)
    return dateValue(candidate) > dateValue(latest) ? candidate : latest
  }, null)

  return (
    <button
      type="button"
      onClick={onClick}
      className="group rounded-xl border border-border/90 bg-surface/70 p-4 text-left transition-colors hover:border-primary/35 hover:bg-surface/85 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
    >
      <span className="flex items-start justify-between gap-4">
        <span className="flex min-w-0 items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light">
            <Bot className="h-4 w-4" />
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold text-white">{agent.name}</span>
            <span className="mt-1 block text-[11px] text-muted">{agent.unavailable ? 'Agent unavailable' : `${active} active · ${credentials.length} total`}</span>
          </span>
        </span>
        <ChevronRight className="mt-2 h-4 w-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-primary-light" />
      </span>

      <span className="mt-4 flex flex-wrap gap-2">
        <Pill active={production > 0}>Production {production}</Pill>
        <Pill active={staging > 0}>Staging {staging}</Pill>
        {credentials.length === 0 && <Pill>No keys</Pill>}
      </span>
      <span className="mt-4 block text-[10px] text-muted">Last used · {formatDate(lastUsedAt)}</span>
    </button>
  )
}

function CredentialRow({ group, onClick }: { group: CredentialGroup; onClick: () => void }) {
  const { current, revisions } = group
  return (
    <button
      type="button"
      onClick={onClick}
      className="group w-full rounded-xl border border-border/85 bg-surface/60 p-4 text-left transition-colors hover:border-primary/30 hover:bg-surface/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
    >
      <span className="flex items-start justify-between gap-4">
        <span className="min-w-0">
          <span className="block truncate text-sm font-semibold text-white">{current.name}</span>
          <span className="mt-1 block line-clamp-2 text-xs leading-5 text-muted">{current.description || 'No purpose documented.'}</span>
        </span>
        <span className="flex shrink-0 items-center gap-3">
          <StatusBadge status={current.status} />
          <ChevronRight className="h-4 w-4 text-muted group-hover:text-primary-light" />
        </span>
      </span>
      <span className="mt-4 flex flex-wrap items-center gap-2">
        <Pill active>{environmentLabel(current.environment)}</Pill>
        {current.interfaces.map((item) => <Pill key={item}>{item}</Pill>)}
        {revisions.length > 1 && <Pill>{revisions.length - 1} rotations</Pill>}
      </span>
      <span className="mt-4 flex flex-col gap-1 text-[10px] text-muted sm:flex-row sm:items-center sm:justify-between">
        <code>{current.key_prefix}...</code>
        <span>Last used · {formatDate(current.last_used_at)}</span>
      </span>
    </button>
  )
}

function CredentialDetail({
  group,
  agentName,
  projectId,
  onBack,
  onRotate,
  onRevoke,
}: {
  group: CredentialGroup
  agentName?: string | null
  projectId: string
  onBack: () => void
  onRotate: (apiKey: ApiKey) => void
  onRevoke: (apiKey: ApiKey) => void
}) {
  const updateCredential = useUpdateApiKeyCredential(projectId)
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(group.current.name)
  const [description, setDescription] = useState(group.current.description ?? '')

  useEffect(() => {
    setName(group.current.name)
    setDescription(group.current.description ?? '')
    setEditing(false)
  }, [group.id, group.current.name, group.current.description])

  const saveMetadata = async () => {
    const normalizedName = name.trim()
    if (!normalizedName) {
      toast.error('Key name is required')
      return
    }
    try {
      await updateCredential.mutateAsync({
        credentialId: group.id,
        data: { name: normalizedName, description: description.trim() || null },
      })
      setEditing(false)
      toast.success('Key details updated')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update key')
    }
  }

  const current = group.current
  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <button type="button" onClick={onBack} className="inline-flex items-center gap-2 text-xs font-medium text-muted hover:text-white">
          <ArrowLeft className="h-4 w-4" /> Back to keys
        </button>
        {!editing && (
          <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
            <Pencil className="mr-2 h-3.5 w-3.5" /> Edit details
          </Button>
        )}
      </div>

      <section className="rounded-xl border border-border/85 bg-surface/65 p-5">
        {editing ? (
          <div className="space-y-4">
            <label className="grid gap-2 text-xs font-medium text-muted">
              Name
              <Input value={name} onChange={(event) => setName(event.target.value)} maxLength={255} autoFocus />
            </label>
            <label className="grid gap-2 text-xs font-medium text-muted">
              Description
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                maxLength={500}
                rows={4}
                className="w-full resize-none rounded-lg border border-border/80 bg-background/70 px-3 py-2.5 text-sm text-white outline-none focus:border-primary/40"
              />
            </label>
            <div className="flex justify-end gap-2 border-t border-border/80 pt-4">
              <Button variant="secondary" onClick={() => { setEditing(false); setName(current.name); setDescription(current.description ?? '') }}>Cancel</Button>
              <Button onClick={() => void saveMetadata()} loading={updateCredential.isPending}>Save changes</Button>
            </div>
          </div>
        ) : (
          <div>
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <h3 className="text-lg font-semibold text-white">{current.name}</h3>
                <p className="mt-2 text-sm leading-6 text-muted">{current.description || 'No purpose documented for this credential.'}</p>
              </div>
              <StatusBadge status={current.status} />
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              {current.kind === 'runtime' && (
                <div className="rounded-xl border border-border/80 bg-background/50 p-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Agent</p>
                  <p className="mt-1 truncate text-sm text-white">{agentName || 'Agent unavailable'}</p>
                </div>
              )}
              <div className="rounded-xl border border-border/80 bg-background/50 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Environment</p>
                <p className="mt-1 text-sm text-white">{environmentLabel(current.environment)}</p>
              </div>
              <div className="rounded-xl border border-border/80 bg-background/50 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Active prefix</p>
                <code className="mt-1 block truncate text-xs text-white">{current.key_prefix}...</code>
              </div>
              <div className="rounded-xl border border-border/80 bg-background/50 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Last used</p>
                <p className="mt-1 text-xs text-white">{formatDate(current.last_used_at)}</p>
              </div>
            </div>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-border/85 bg-surface/65 p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">Credential actions</h3>
            <p className="mt-1 text-xs leading-5 text-muted">Rotation replaces only the secret. Name and purpose remain stable.</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onRotate(current)} disabled={current.status !== 'active'}>
              <RotateCcw className="mr-2 h-4 w-4" /> Rotate
            </Button>
            <Button variant="destructive" onClick={() => onRevoke(current)} disabled={current.status !== 'active'}>
              <Ban className="mr-2 h-4 w-4" /> Revoke
            </Button>
          </div>
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-border/85 bg-surface/65">
        <div className="border-b border-border/80 px-5 py-4">
          <div className="flex items-center gap-2">
            <Layers3 className="h-4 w-4 text-primary-light" />
            <h3 className="text-sm font-semibold text-white">Rotation history</h3>
          </div>
          <p className="mt-1 text-xs text-muted">Every secret revision remains visible for audit, but its value is never recoverable.</p>
        </div>
        <div className="divide-y divide-border/70">
          {group.revisions.map((revision, index) => (
            <div key={revision.id} className="grid gap-3 px-5 py-4 text-xs sm:grid-cols-[minmax(0,1fr)_100px_170px] sm:items-center">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <code className="truncate text-white">{revision.key_prefix}...</code>
                  {index === 0 && <Pill active>Latest</Pill>}
                </div>
                <p className="mt-1 text-[10px] text-muted">Created · {formatDate(revision.created_at)}</p>
              </div>
              <StatusBadge status={revision.status} />
              <div className="text-[10px] text-muted">
                <p>Last used · {formatDate(revision.last_used_at)}</p>
                {revision.revoked_at && <p className="mt-1">Revoked · {formatDate(revision.revoked_at)}</p>}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export default function ApiKeysPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: keys, isLoading, isError, error, refetch } = useApiKeys(projectId)
  const { data: agents = [] } = useAgents(projectId)
  const revokeKey = useRevokeApiKey(projectId)
  const rotateKey = useRotateApiKey(projectId)
  const [query, setQuery] = useState('')
  const [modalQuery, setModalQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [showCreate, setShowCreate] = useState(false)
  const [createAgentId, setCreateAgentId] = useState<string | undefined>()
  const [createEnvironment, setCreateEnvironment] = useState<RuntimeEnvironment | undefined>()
  const [rotateTarget, setRotateTarget] = useState<ApiKey | null>(null)
  const [revokeTarget, setRevokeTarget] = useState<ApiKey | null>(null)
  const [revealedKey, setRevealedKey] = useState<CreateApiKeyResponse | null>(null)

  const items = keys ?? []
  const runtimeGroups = useMemo(() => groupCredentials(items.filter((key) => key.kind === 'runtime')), [items])
  const projectGroups = useMemo(() => groupCredentials(items.filter((key) => key.kind === 'project')), [items])
  const agentNames = useMemo(() => new Map(agents.map((agent) => [agent.id, agent.name])), [agents])
  const activeTab: KeyTab = searchParams.get('type') === 'project' ? 'project' : 'runtime'
  const selectedAgentId = searchParams.get('agent')
  const selectedCredentialId = searchParams.get('credential')
  const environmentFilter = (searchParams.get('environment') ?? 'all') as EnvironmentFilter

  const agentDescriptors = useMemo(() => {
    const result: AgentDescriptor[] = agents.map((agent) => ({ id: agent.id, name: agent.name }))
    const known = new Set(result.map((agent) => agent.id))
    for (const credential of runtimeGroups) {
      const agentId = credential.current.agent_id
      if (agentId && !known.has(agentId)) {
        result.push({ id: agentId, name: 'Unavailable Agent', unavailable: true })
        known.add(agentId)
      }
    }
    return result.sort((left, right) => left.name.localeCompare(right.name))
  }, [agents, runtimeGroups])

  const updateSearchParams = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(updates)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    setSearchParams(next)
  }

  const selectTab = (tab: KeyTab) => {
    updateSearchParams({ type: tab, agent: null, credential: null, environment: null })
    setQuery('')
  }

  const openCreate = (agentId?: string, environment?: RuntimeEnvironment) => {
    setCreateAgentId(agentId)
    setCreateEnvironment(environment)
    setShowCreate(true)
  }

  const selectedAgent = agentDescriptors.find((agent) => agent.id === selectedAgentId) ?? null
  const agentCredentials = runtimeGroups.filter((credential) => (
    credential.current.agent_id === selectedAgentId
    && (environmentFilter === 'all' || credential.current.environment === environmentFilter)
  ))
  const selectedGroups = activeTab === 'runtime' ? agentCredentials : projectGroups
  const selectedCredential = selectedGroups.find((credential) => credential.id === selectedCredentialId) ?? null
  const visibleModalCredentials = selectedGroups.filter((credential) => {
    const normalized = modalQuery.trim().toLowerCase()
    const matchesStatus = statusFilter === 'all' || credential.current.status === statusFilter
    const matchesQuery = !normalized || [
      credential.current.name,
      credential.current.description ?? '',
      credential.current.key_prefix,
    ].some((value) => value.toLowerCase().includes(normalized))
    return matchesStatus && matchesQuery
  })

  const visibleAgents = agentDescriptors.filter((agent) => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return true
    const agentCredentialText = runtimeGroups
      .filter((credential) => credential.current.agent_id === agent.id)
      .map((credential) => `${credential.current.name} ${credential.current.description ?? ''}`)
      .join(' ')
    return `${agent.name} ${agentCredentialText}`.toLowerCase().includes(normalized)
  })

  const visibleProjectGroups = projectGroups.filter((credential) => {
    const normalized = query.trim().toLowerCase()
    return !normalized || `${credential.current.name} ${credential.current.description ?? ''} ${credential.current.key_prefix}`.toLowerCase().includes(normalized)
  })

  const closeManagementModal = () => {
    updateSearchParams({ agent: null, credential: null, environment: null })
    setModalQuery('')
    setStatusFilter('all')
  }

  const handleRotate = async () => {
    if (!rotateTarget) return
    try {
      const result = await rotateKey.mutateAsync({ apiKeyId: rotateTarget.id })
      setRotateTarget(null)
      await refetch()
      updateSearchParams({ credential: result.credential_id })
      setRevealedKey(result)
      toast.success('API key rotated')
    } catch (rotationError) {
      toast.error(rotationError instanceof Error ? rotationError.message : 'Failed to rotate key')
    }
  }

  const handleRevoke = async () => {
    if (!revokeTarget) return
    try {
      await revokeKey.mutateAsync(revokeTarget.id)
      setRevokeTarget(null)
      await refetch()
      toast.success('API key revoked')
    } catch (revokeError) {
      toast.error(revokeError instanceof Error ? revokeError.message : 'Failed to revoke key')
    }
  }

  if (isLoading) return <LoadingState />
  if (isError) return <ErrorState error={error} onRetry={refetch} />

  const counts: Record<KeyTab, number> = { runtime: runtimeGroups.length, project: projectGroups.length }
  const selectedAgentAllCredentials = runtimeGroups.filter((credential) => credential.current.agent_id === selectedAgentId)
  const productionCount = selectedAgentAllCredentials.filter((credential) => credential.current.environment === 'production').length
  const stagingCount = selectedAgentAllCredentials.filter((credential) => credential.current.environment === 'staging').length
  const modalOpen = activeTab === 'runtime' ? Boolean(selectedAgent) : Boolean(selectedCredentialId)

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6">
      <PageHeader
        action={(
          <Button onClick={() => openCreate()}>
            <Plus className="mr-2 h-4 w-4" /> Create {activeTab === 'runtime' ? 'Runtime' : 'Project'} Key
          </Button>
        )}
      />

      <div className="flex flex-col gap-4 rounded-xl border border-border/80 bg-surface/45 p-4">
        <KeyTabs active={activeTab} counts={counts} onChange={selectTab} />
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={activeTab === 'runtime' ? 'Search Agents or key purpose...' : 'Search Project Keys...'}
            className="h-10 pl-9"
          />
        </div>
      </div>

      {activeTab === 'runtime' ? (
        visibleAgents.length > 0 ? (
          <section>
            <div className="mb-3 flex items-end justify-between gap-4">
              <div>
                <h2 className="text-sm font-semibold text-white">Agents</h2>
                <p className="mt-1 text-xs text-muted">Open an Agent to manage its Runtime Keys and rotation history.</p>
              </div>
              <span className="text-xs text-muted">{visibleAgents.length}</span>
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {visibleAgents.map((agent) => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  credentials={runtimeGroups.filter((credential) => credential.current.agent_id === agent.id)}
                  onClick={() => updateSearchParams({ agent: agent.id, credential: null, environment: null })}
                />
              ))}
            </div>
          </section>
        ) : (
          <div className="rounded-xl border border-dashed border-border/80 bg-surface/40 px-6 py-10 text-center">
            <Bot className="mx-auto h-5 w-5 text-muted" />
            <h2 className="mt-3 text-sm font-semibold text-white">No Agents found</h2>
            <p className="mt-1 text-sm text-muted">Adjust the search or create an Agent first.</p>
          </div>
        )
      ) : visibleProjectGroups.length > 0 ? (
        <section className="space-y-3">
          <div className="flex items-end justify-between gap-4">
            <div>
              <h2 className="text-sm font-semibold text-white">Project Keys</h2>
              <p className="mt-1 text-xs text-muted">Operational credentials for traces, usage and Project APIs.</p>
            </div>
            <span className="text-xs text-muted">{visibleProjectGroups.length}</span>
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {visibleProjectGroups.map((credential) => (
              <CredentialRow key={credential.id} group={credential} onClick={() => updateSearchParams({ credential: credential.id })} />
            ))}
          </div>
        </section>
      ) : (
        <div className="rounded-xl border border-dashed border-border/80 bg-surface/40 px-6 py-10 text-center">
          <Key className="mx-auto h-5 w-5 text-muted" />
          <h2 className="mt-3 text-sm font-semibold text-white">No Project Keys found</h2>
          <p className="mt-1 text-sm text-muted">Create a key or adjust the search.</p>
        </div>
      )}

      <Dialog
        open={modalOpen}
        onClose={closeManagementModal}
        title={activeTab === 'runtime' ? `Runtime Keys · ${selectedAgent?.name ?? ''}` : 'Project Key'}
        className="max-h-[90vh] max-w-[1180px] overflow-hidden"
      >
        <div className="grid h-[calc(90vh-96px)] min-h-0 lg:grid-cols-[300px_minmax(0,1fr)]">
          <aside className="min-h-0 border-b border-border/90 bg-background/20 p-4 lg:border-b-0 lg:border-r">
            <div className="scrollbar-thin h-full space-y-4 overflow-y-auto pr-1">
              <div className="rounded-xl border border-border/85 bg-surface/65 p-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light">
                  {activeTab === 'runtime' ? <Bot className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
                </div>
                <p className="mt-4 truncate text-sm font-semibold text-white">{activeTab === 'runtime' ? selectedAgent?.name : selectedCredential?.current.name}</p>
                <p className="mt-1 break-all text-[10px] text-muted">{activeTab === 'runtime' ? selectedAgent?.id : selectedCredential?.id}</p>
              </div>

              {activeTab === 'runtime' && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Environment</p>
                  <div className="mt-2 grid gap-2">
                    {([
                      ['all', 'All environments', selectedAgentAllCredentials.length],
                      ['production', 'Production', productionCount],
                      ['staging', 'Staging', stagingCount],
                    ] as Array<[EnvironmentFilter, string, number]>).map(([value, label, count]) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => updateSearchParams({ environment: value === 'all' ? null : value, credential: null })}
                        className={`flex items-center justify-between rounded-xl border px-3 py-2.5 text-left text-xs transition-colors ${environmentFilter === value ? 'border-primary/35 bg-primary/10 text-white' : 'border-border/80 bg-background/45 text-muted hover:text-white'}`}
                      >
                        <span>{label}</span><span className="text-[10px]">{count}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="rounded-xl border border-border/80 bg-background/45 p-4">
                <div className="flex items-center gap-2">
                  <Clock3 className="h-4 w-4 text-muted" />
                  <p className="text-sm font-semibold text-white">Credential summary</p>
                </div>
                <div className="mt-3 space-y-2 text-xs text-muted">
                  <p>Active · {selectedGroups.filter((credential) => credential.current.status === 'active').length}</p>
                  <p>Revoked · {selectedGroups.filter((credential) => credential.current.status === 'revoked').length}</p>
                  <p>Expired · {selectedGroups.filter((credential) => credential.current.status === 'expired').length}</p>
                </div>
              </div>

              {activeTab === 'runtime' && selectedAgent && !selectedAgent.unavailable && (
                <Button className="w-full" onClick={() => openCreate(selectedAgent.id, environmentFilter === 'all' ? undefined : environmentFilter)}>
                  <Plus className="mr-2 h-4 w-4" /> Create Runtime Key
                </Button>
              )}
            </div>
          </aside>

          <main className="min-h-0 overflow-y-auto p-5">
            {selectedCredential ? (
              <CredentialDetail
                group={selectedCredential}
                agentName={selectedCredential.current.agent_id ? agentNames.get(selectedCredential.current.agent_id) : null}
                projectId={projectId!}
                onBack={() => updateSearchParams({ credential: null })}
                onRotate={setRotateTarget}
                onRevoke={setRevokeTarget}
              />
            ) : (
              <div className="space-y-4">
                <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
                  <div className="relative min-w-0 flex-1">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
                    <Input value={modalQuery} onChange={(event) => setModalQuery(event.target.value)} placeholder="Search by name, purpose or prefix..." className="pl-9" />
                  </div>
                  <select
                    value={statusFilter}
                    onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
                    className="h-10 rounded-lg border border-border/80 bg-surface/65 px-3 text-xs text-white outline-none"
                  >
                    <option value="all">All statuses</option>
                    <option value="active">Active</option>
                    <option value="revoked">Revoked</option>
                    <option value="expired">Expired</option>
                  </select>
                </div>

                {visibleModalCredentials.length > 0 ? (
                  <div className="space-y-3">
                    {visibleModalCredentials.map((credential) => (
                      <CredentialRow key={credential.id} group={credential} onClick={() => updateSearchParams({ credential: credential.id })} />
                    ))}
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed border-border/80 bg-surface/35 px-5 py-10 text-center">
                    <Zap className="mx-auto h-5 w-5 text-muted" />
                    <p className="mt-3 text-sm font-semibold text-white">No keys in this view</p>
                    <p className="mt-1 text-xs text-muted">Adjust the filters or create a credential.</p>
                  </div>
                )}
              </div>
            )}
          </main>
        </div>
      </Dialog>

      <CreateApiKeyDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        projectId={projectId!}
        initialKind={activeTab}
        lockedAgentId={createAgentId}
        initialEnvironment={createEnvironment}
        layer={modalOpen ? 'nestedModal' : 'modal'}
      />

      <RotateApiKeyDialog
        open={Boolean(rotateTarget)}
        apiKey={rotateTarget}
        agentName={rotateTarget?.agent_id ? agentNames.get(rotateTarget.agent_id) : null}
        loading={rotateKey.isPending}
        onClose={() => setRotateTarget(null)}
        onConfirm={() => void handleRotate()}
      />

      <Dialog open={Boolean(revokeTarget)} onClose={() => { if (!revokeKey.isPending) setRevokeTarget(null) }} title="Revoke API key" className="max-w-xl" layer="nestedModal">
        {revokeTarget && (
          <div className="space-y-5">
            <div className="rounded-xl border border-red-500/25 bg-red-500/5 p-4">
              <p className="text-sm font-semibold text-red-100">{revokeTarget.name}</p>
              <code className="mt-1 block text-xs text-red-100/70">{revokeTarget.key_prefix}...</code>
              <p className="mt-3 text-xs leading-5 text-red-100/75">Requests signed with this secret will stop working immediately. Rotation history and metadata remain available.</p>
            </div>
            <div className="flex justify-end gap-2 border-t border-border/80 pt-4">
              <Button variant="secondary" onClick={() => setRevokeTarget(null)} disabled={revokeKey.isPending}>Cancel</Button>
              <Button variant="destructive" onClick={() => void handleRevoke()} loading={revokeKey.isPending}>Revoke key</Button>
            </div>
          </div>
        )}
      </Dialog>

      <Dialog open={Boolean(revealedKey)} onClose={() => setRevealedKey(null)} title="New API key secret" className="max-w-2xl" layer="nestedModal">
        {revealedKey && (
          <div>
            <ApiKeySecretReveal apiKey={revealedKey} agentName={revealedKey.agent_id ? agentNames.get(revealedKey.agent_id) : null} />
            <div className="mt-5 flex justify-end border-t border-border/80 pt-4">
              <Button onClick={() => setRevealedKey(null)}>Done</Button>
            </div>
          </div>
        )}
      </Dialog>
    </div>
  )
}
