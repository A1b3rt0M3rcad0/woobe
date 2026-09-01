import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft,
  Ban,
  Bot,
  ChevronRight,
  Clock3,
  Key,
  Layers3,
  Network,
  Pencil,
  Plus,
  RotateCcw,
  Search,
  ShieldCheck,
  Zap,
} from 'lucide-react'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { useAgents } from '@/features/agents/hooks'
import { ApiKeySecretReveal } from '@/features/api-keys/components/ApiKeySecretReveal'
import { CreateApiKeyDialog } from '@/features/api-keys/components/CreateApiKeyDialog'
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
  RuntimeTargetType,
} from '@/features/api-keys/types'
import { listNetworks } from '@/features/network/api'

interface CredentialGroup {
  id: string
  current: ApiKey
  revisions: ApiKey[]
}

interface TargetDescriptor {
  id: string
  name: string
  type: RuntimeTargetType
  unavailable?: boolean
}

type KeyTab = ApiKeyKind
type EnvironmentFilter = 'all' | RuntimeEnvironment
type StatusFilter = 'all' | ApiKey['status']

function timestamp(value?: string | null): number {
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

function keyTargetType(key: ApiKey): RuntimeTargetType | null {
  if (key.target_type === 'agent' || key.target_type === 'network') return key.target_type
  return key.agent_id ? 'agent' : null
}

function keyTargetId(key: ApiKey): string | null {
  return key.target_id ?? key.agent_id ?? null
}

function groupCredentials(keys: ApiKey[]): CredentialGroup[] {
  const grouped = new Map<string, ApiKey[]>()
  for (const key of keys) {
    const credentialId = key.credential_id || key.id
    grouped.set(credentialId, [...(grouped.get(credentialId) ?? []), key])
  }
  return Array.from(grouped, ([id, values]) => {
    const revisions = [...values].sort((left, right) => timestamp(right.created_at) - timestamp(left.created_at))
    const current = revisions.find((item) => item.status === 'active') ?? revisions[0]!
    return { id, current, revisions }
  }).sort((left, right) => {
    if (left.current.status === 'active' && right.current.status !== 'active') return -1
    if (left.current.status !== 'active' && right.current.status === 'active') return 1
    return timestamp(right.current.created_at) - timestamp(left.current.created_at)
  })
}

function Pill({ children, active = false }: { children: ReactNode; active?: boolean }) {
  return (
    <span className={`rounded-full border px-2.5 py-1 text-[10px] font-medium ${
      active
        ? 'border-primary/30 bg-primary/10 text-primary-light'
        : 'border-border/80 bg-background/55 text-muted'
    }`}>
      {children}
    </span>
  )
}

function TargetCard({
  target,
  credentials,
  onClick,
}: {
  target: TargetDescriptor
  credentials: CredentialGroup[]
  onClick: () => void
}) {
  const Icon = target.type === 'network' ? Network : Bot
  const active = credentials.filter((item) => item.current.status === 'active').length
  const production = credentials.filter((item) => item.current.status === 'active' && item.current.environment === 'production').length
  const staging = credentials.filter((item) => item.current.status === 'active' && item.current.environment === 'staging').length
  const lastUsed = credentials.reduce<string | null>((latest, item) => {
    const candidate = item.revisions.reduce<string | null>((revisionLatest, revision) => (
      timestamp(revision.last_used_at) > timestamp(revisionLatest)
        ? revision.last_used_at ?? null
        : revisionLatest
    ), null)
    return timestamp(candidate) > timestamp(latest) ? candidate : latest
  }, null)

  return (
    <button
      type="button"
      onClick={onClick}
      className="group rounded-xl border border-border/90 bg-surface/70 p-4 text-left transition-colors hover:border-primary/35 hover:bg-surface/85"
    >
      <span className="flex items-start justify-between gap-4">
        <span className="flex min-w-0 items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light">
            <Icon className="h-4 w-4" />
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold text-white">{target.name}</span>
            <span className="mt-1 block text-[11px] text-muted">
              {target.unavailable ? 'Target unavailable' : `${active} active · ${credentials.length} total`}
            </span>
          </span>
        </span>
        <ChevronRight className="mt-2 h-4 w-4 text-muted group-hover:text-primary-light" />
      </span>
      <span className="mt-4 flex flex-wrap gap-2">
        <Pill active={production > 0}>Production {production}</Pill>
        <Pill active={staging > 0}>Staging {staging}</Pill>
        {credentials.length === 0 && <Pill>No keys</Pill>}
      </span>
      <span className="mt-4 block text-[10px] text-muted">Last used · {formatDate(lastUsed)}</span>
    </button>
  )
}

function CredentialRow({ group, onClick }: { group: CredentialGroup; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group w-full rounded-xl border border-border/85 bg-surface/60 p-4 text-left transition-colors hover:border-primary/30 hover:bg-surface/80"
    >
      <span className="flex items-start justify-between gap-4">
        <span className="min-w-0">
          <span className="block truncate text-sm font-semibold text-white">{group.current.name}</span>
          <span className="mt-1 block line-clamp-2 text-xs leading-5 text-muted">
            {group.current.description || 'No purpose documented.'}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-3">
          <StatusBadge status={group.current.status} />
          <ChevronRight className="h-4 w-4 text-muted group-hover:text-primary-light" />
        </span>
      </span>
      <span className="mt-4 flex flex-wrap gap-2">
        <Pill active>{environmentLabel(group.current.environment)}</Pill>
        {group.current.interfaces.map((item) => <Pill key={item}>{item}</Pill>)}
        {group.revisions.length > 1 && <Pill>{group.revisions.length - 1} rotations</Pill>}
      </span>
      <span className="mt-4 flex flex-col gap-1 text-[10px] text-muted sm:flex-row sm:items-center sm:justify-between">
        <code>{group.current.key_prefix}...</code>
        <span>Last used · {formatDate(group.current.last_used_at)}</span>
      </span>
    </button>
  )
}

function CredentialDetail({
  group,
  targetName,
  projectId,
  onBack,
  onRotate,
  onRevoke,
}: {
  group: CredentialGroup
  targetName?: string | null
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
  }, [group.current.description, group.current.name, group.id])

  const save = async () => {
    const normalizedName = name.trim()
    if (!normalizedName) {
      toast.error('Key name is required')
      return
    }
    try {
      await updateCredential.mutateAsync({
        apiKeyId: group.current.id,
        data: { name: normalizedName, description: description.trim() || null },
      })
      setEditing(false)
      toast.success('Key details updated')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update key')
    }
  }

  const current = group.current
  const targetType = keyTargetType(current)
  const targetLabel = targetType === 'network' ? 'Network' : 'Agent'
  const TargetIcon = targetType === 'network' ? Network : Bot

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
              <Button onClick={() => void save()} loading={updateCredential.isPending}>Save changes</Button>
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
                  <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
                    <TargetIcon className="h-3.5 w-3.5" /> {targetLabel}
                  </div>
                  <p className="mt-1 truncate text-sm text-white">{targetName || `${targetLabel} unavailable`}</p>
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
            <p className="mt-1 text-xs leading-5 text-muted">Rotation changes only the secret. Target, environment and metadata remain stable.</p>
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
          <div className="flex items-center gap-2"><Layers3 className="h-4 w-4 text-primary-light" /><h3 className="text-sm font-semibold text-white">Rotation history</h3></div>
          <p className="mt-1 text-xs text-muted">Secret revisions remain available for audit, but the secret value is never recoverable.</p>
        </div>
        <div className="divide-y divide-border/70">
          {group.revisions.map((revision, index) => (
            <div key={revision.id} className="grid gap-3 px-5 py-4 text-xs sm:grid-cols-[minmax(0,1fr)_100px_170px] sm:items-center">
              <div className="min-w-0">
                <div className="flex items-center gap-2"><code className="truncate text-white">{revision.key_prefix}...</code>{index === 0 && <Pill active>Latest</Pill>}</div>
                <p className="mt-1 text-[10px] text-muted">Created · {formatDate(revision.created_at)}</p>
              </div>
              <StatusBadge status={revision.status} />
              <div className="text-[10px] text-muted"><p>Last used · {formatDate(revision.last_used_at)}</p>{revision.revoked_at && <p className="mt-1">Revoked · {formatDate(revision.revoked_at)}</p>}</div>
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
  const keysQuery = useApiKeys(projectId)
  const agentsQuery = useAgents(projectId)
  const networksQuery = useQuery({
    queryKey: ['networks', projectId, 'api-keys'],
    queryFn: () => listNetworks(projectId!),
    enabled: Boolean(projectId),
  })
  const revokeKey = useRevokeApiKey(projectId)
  const rotateKey = useRotateApiKey(projectId)

  const [query, setQuery] = useState('')
  const [modalQuery, setModalQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [showCreate, setShowCreate] = useState(false)
  const [createTargetType, setCreateTargetType] = useState<RuntimeTargetType | undefined>()
  const [createTargetId, setCreateTargetId] = useState<string | undefined>()
  const [createEnvironment, setCreateEnvironment] = useState<RuntimeEnvironment | undefined>()
  const [rotateTarget, setRotateTarget] = useState<ApiKey | null>(null)
  const [revokeTarget, setRevokeTarget] = useState<ApiKey | null>(null)
  const [revealedKey, setRevealedKey] = useState<CreateApiKeyResponse | null>(null)

  const keys = keysQuery.data ?? []
  const agents = agentsQuery.data ?? []
  const networks = networksQuery.data ?? []
  const runtimeGroups = useMemo(() => groupCredentials(keys.filter((key) => key.kind === 'runtime')), [keys])
  const projectGroups = useMemo(() => groupCredentials(keys.filter((key) => key.kind === 'project')), [keys])

  const activeTab: KeyTab = searchParams.get('type') === 'project' ? 'project' : 'runtime'
  const activeTargetType: RuntimeTargetType = searchParams.get('targetType') === 'network' ? 'network' : 'agent'
  const selectedTargetId = searchParams.get('target') ?? searchParams.get('agent')
  const selectedCredentialId = searchParams.get('credential')
  const environmentFilter = (searchParams.get('environment') ?? 'all') as EnvironmentFilter

  const targetNames = useMemo(() => new Map<string, string>([
    ...agents.map((agent) => [agent.id, agent.name] as [string, string]),
    ...networks.map((network) => [network.id, network.name] as [string, string]),
  ]), [agents, networks])

  const targets = useMemo<TargetDescriptor[]>(() => {
    const result: TargetDescriptor[] = activeTargetType === 'agent'
      ? agents.map((agent) => ({ id: agent.id, name: agent.name, type: 'agent' }))
      : networks.map((network) => ({ id: network.id, name: network.name, type: 'network' }))
    const known = new Set(result.map((item) => item.id))
    for (const group of runtimeGroups) {
      if (keyTargetType(group.current) !== activeTargetType) continue
      const id = keyTargetId(group.current)
      if (!id || known.has(id)) continue
      result.push({
        id,
        name: `Unavailable ${activeTargetType === 'network' ? 'Network' : 'Agent'}`,
        type: activeTargetType,
        unavailable: true,
      })
      known.add(id)
    }
    return result.sort((left, right) => left.name.localeCompare(right.name))
  }, [activeTargetType, agents, networks, runtimeGroups])

  const updateParams = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(updates)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    setSearchParams(next)
  }

  const selectKeyTab = (tab: KeyTab) => {
    updateParams({ type: tab, targetType: null, target: null, agent: null, credential: null, environment: null })
    setQuery('')
  }

  const selectTargetType = (targetType: RuntimeTargetType) => {
    updateParams({ type: 'runtime', targetType, target: null, agent: null, credential: null, environment: null })
    setQuery('')
  }

  const openCreate = (targetType?: RuntimeTargetType, targetId?: string, environment?: RuntimeEnvironment) => {
    setCreateTargetType(targetType)
    setCreateTargetId(targetId)
    setCreateEnvironment(environment)
    setShowCreate(true)
  }

  const selectedTarget = targets.find((target) => target.id === selectedTargetId) ?? null
  const selectedTargetGroups = runtimeGroups.filter((group) => (
    keyTargetType(group.current) === activeTargetType
    && keyTargetId(group.current) === selectedTargetId
    && (environmentFilter === 'all' || group.current.environment === environmentFilter)
  ))
  const selectedGroups = activeTab === 'runtime' ? selectedTargetGroups : projectGroups
  const selectedCredential = selectedGroups.find((group) => group.id === selectedCredentialId) ?? null

  const visibleTargets = targets.filter((target) => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return true
    const credentialText = runtimeGroups
      .filter((group) => keyTargetType(group.current) === target.type && keyTargetId(group.current) === target.id)
      .map((group) => `${group.current.name} ${group.current.description ?? ''}`)
      .join(' ')
    return `${target.name} ${credentialText}`.toLowerCase().includes(normalized)
  })
  const visibleProjectGroups = projectGroups.filter((group) => {
    const normalized = query.trim().toLowerCase()
    return !normalized || `${group.current.name} ${group.current.description ?? ''} ${group.current.key_prefix}`.toLowerCase().includes(normalized)
  })
  const visibleModalGroups = selectedGroups.filter((group) => {
    const normalized = modalQuery.trim().toLowerCase()
    const matchesStatus = statusFilter === 'all' || group.current.status === statusFilter
    const matchesQuery = !normalized || `${group.current.name} ${group.current.description ?? ''} ${group.current.key_prefix}`.toLowerCase().includes(normalized)
    return matchesStatus && matchesQuery
  })

  const closeManagement = () => {
    updateParams({ target: null, agent: null, credential: null, environment: null })
    setModalQuery('')
    setStatusFilter('all')
  }

  const rotate = async () => {
    if (!rotateTarget) return
    try {
      const result = await rotateKey.mutateAsync({ apiKeyId: rotateTarget.id })
      setRotateTarget(null)
      await keysQuery.refetch()
      updateParams({ credential: result.credential_id })
      setRevealedKey(result)
      toast.success('API key rotated')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to rotate key')
    }
  }

  const revoke = async () => {
    if (!revokeTarget) return
    try {
      await revokeKey.mutateAsync(revokeTarget.id)
      setRevokeTarget(null)
      await keysQuery.refetch()
      toast.success('API key revoked')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to revoke key')
    }
  }

  if (keysQuery.isLoading || agentsQuery.isLoading || networksQuery.isLoading) return <LoadingState />
  if (keysQuery.isError) return <ErrorState error={keysQuery.error} onRetry={keysQuery.refetch} />

  const selectedTargetAllGroups = runtimeGroups.filter((group) => keyTargetType(group.current) === activeTargetType && keyTargetId(group.current) === selectedTargetId)
  const productionCount = selectedTargetAllGroups.filter((group) => group.current.environment === 'production').length
  const stagingCount = selectedTargetAllGroups.filter((group) => group.current.environment === 'staging').length
  const managementOpen = activeTab === 'runtime' ? Boolean(selectedTarget) : Boolean(selectedCredentialId)
  const rotateTargetName = rotateTarget ? targetNames.get(keyTargetId(rotateTarget) ?? '') ?? null : null
  const revealedTargetName = revealedKey ? targetNames.get(keyTargetId(revealedKey) ?? '') ?? null : null

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">API Keys</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted">Manage stable credentials and Runtime Keys bound to one Agent or Network deployment.</p>
        </div>
        <Button onClick={() => openCreate(activeTab === 'runtime' ? activeTargetType : undefined)}>
          <Plus className="mr-2 h-4 w-4" /> Create {activeTab === 'runtime' ? `${activeTargetType === 'network' ? 'Network' : 'Agent'} Runtime` : 'Project'} Key
        </Button>
      </div>

      <div className="flex flex-col gap-4 rounded-xl border border-border/80 bg-surface/45 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="inline-flex rounded-xl border border-border/80 bg-surface/55 p-1">
            {(['runtime', 'project'] as KeyTab[]).map((tab) => (
              <button key={tab} type="button" onClick={() => selectKeyTab(tab)} className={`rounded-lg px-3 py-2 text-xs font-medium ${activeTab === tab ? 'bg-primary/12 text-primary-light' : 'text-muted hover:bg-background/60 hover:text-white'}`}>
                {tab === 'runtime' ? 'Runtime' : 'Project'} <span className="ml-1 text-[10px] opacity-70">{tab === 'runtime' ? runtimeGroups.length : projectGroups.length}</span>
              </button>
            ))}
          </div>
          {activeTab === 'runtime' && (
            <div className="inline-flex rounded-xl border border-border/80 bg-surface/55 p-1">
              {(['agent', 'network'] as RuntimeTargetType[]).map((targetType) => {
                const Icon = targetType === 'network' ? Network : Bot
                return (
                  <button key={targetType} type="button" onClick={() => selectTargetType(targetType)} className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium ${activeTargetType === targetType ? 'bg-primary/12 text-primary-light' : 'text-muted hover:bg-background/60 hover:text-white'}`}>
                    <Icon className="h-3.5 w-3.5" /> {targetType === 'network' ? 'Networks' : 'Agents'}
                  </button>
                )
              })}
            </div>
          )}
        </div>
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={activeTab === 'runtime' ? `Search ${activeTargetType === 'network' ? 'Networks' : 'Agents'} or key purpose...` : 'Search Project Keys...'} className="h-10 pl-9" />
        </div>
      </div>

      {activeTab === 'runtime' ? (
        visibleTargets.length > 0 ? (
          <section>
            <div className="mb-3 flex items-end justify-between gap-4"><div><h2 className="text-sm font-semibold text-white">{activeTargetType === 'network' ? 'Networks' : 'Agents'}</h2><p className="mt-1 text-xs text-muted">Open a target to manage its Runtime Keys and rotation history.</p></div><span className="text-xs text-muted">{visibleTargets.length}</span></div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {visibleTargets.map((target) => (
                <TargetCard
                  key={target.id}
                  target={target}
                  credentials={runtimeGroups.filter((group) => keyTargetType(group.current) === target.type && keyTargetId(group.current) === target.id)}
                  onClick={() => updateParams({ type: 'runtime', targetType: target.type, target: target.id, agent: null, credential: null, environment: null })}
                />
              ))}
            </div>
          </section>
        ) : (
          <div className="rounded-xl border border-dashed border-border/80 bg-surface/40 px-6 py-10 text-center"><Zap className="mx-auto h-5 w-5 text-muted" /><h2 className="mt-3 text-sm font-semibold text-white">No {activeTargetType === 'network' ? 'Networks' : 'Agents'} found</h2><p className="mt-1 text-sm text-muted">Adjust the search or create the target first.</p></div>
        )
      ) : visibleProjectGroups.length > 0 ? (
        <section className="space-y-3">
          <div className="flex items-end justify-between gap-4"><div><h2 className="text-sm font-semibold text-white">Project Keys</h2><p className="mt-1 text-xs text-muted">Operational credentials for traces, usage and Project APIs.</p></div><span className="text-xs text-muted">{visibleProjectGroups.length}</span></div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">{visibleProjectGroups.map((group) => <CredentialRow key={group.id} group={group} onClick={() => updateParams({ credential: group.id })} />)}</div>
        </section>
      ) : (
        <div className="rounded-xl border border-dashed border-border/80 bg-surface/40 px-6 py-10 text-center"><Key className="mx-auto h-5 w-5 text-muted" /><h2 className="mt-3 text-sm font-semibold text-white">No Project Keys found</h2><p className="mt-1 text-sm text-muted">Create a key or adjust the search.</p></div>
      )}

      <Dialog open={managementOpen} onClose={closeManagement} title={activeTab === 'runtime' ? `Runtime Keys · ${selectedTarget?.name ?? ''}` : 'Project Key'} className="max-h-[90vh] max-w-[1180px] overflow-hidden">
        <div className="grid h-[calc(90vh-96px)] min-h-0 lg:grid-cols-[300px_minmax(0,1fr)]">
          <aside className="min-h-0 border-b border-border/90 bg-background/20 p-4 lg:border-b-0 lg:border-r">
            <div className="scrollbar-thin h-full space-y-4 overflow-y-auto pr-1">
              <div className="rounded-xl border border-border/85 bg-surface/65 p-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light">
                  {activeTab === 'runtime' ? activeTargetType === 'network' ? <Network className="h-4 w-4" /> : <Bot className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
                </div>
                <p className="mt-4 truncate text-sm font-semibold text-white">{activeTab === 'runtime' ? selectedTarget?.name : selectedCredential?.current.name}</p>
                <p className="mt-1 break-all text-[10px] text-muted">{activeTab === 'runtime' ? selectedTarget?.id : selectedCredential?.id}</p>
              </div>

              {activeTab === 'runtime' && (
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Environment</p>
                  <div className="mt-2 grid gap-2">
                    {([
                      ['all', 'All environments', selectedTargetAllGroups.length],
                      ['production', 'Production', productionCount],
                      ['staging', 'Staging', stagingCount],
                    ] as Array<[EnvironmentFilter, string, number]>).map(([value, label, count]) => (
                      <button key={value} type="button" onClick={() => updateParams({ environment: value === 'all' ? null : value, credential: null })} className={`flex items-center justify-between rounded-xl border px-3 py-2.5 text-left text-xs ${environmentFilter === value ? 'border-primary/35 bg-primary/10 text-white' : 'border-border/80 bg-background/45 text-muted hover:text-white'}`}>
                        <span>{label}</span><span className="text-[10px]">{count}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="rounded-xl border border-border/80 bg-background/45 p-4">
                <div className="flex items-center gap-2"><Clock3 className="h-4 w-4 text-muted" /><p className="text-sm font-semibold text-white">Credential summary</p></div>
                <div className="mt-3 space-y-2 text-xs text-muted"><p>Active · {selectedGroups.filter((group) => group.current.status === 'active').length}</p><p>Revoked · {selectedGroups.filter((group) => group.current.status === 'revoked').length}</p><p>Expired · {selectedGroups.filter((group) => group.current.status === 'expired').length}</p></div>
              </div>

              {activeTab === 'runtime' && selectedTarget && !selectedTarget.unavailable && (
                <Button className="w-full" onClick={() => openCreate(selectedTarget.type, selectedTarget.id, environmentFilter === 'all' ? undefined : environmentFilter)}>
                  <Plus className="mr-2 h-4 w-4" /> Create Runtime Key
                </Button>
              )}
            </div>
          </aside>

          <main className="min-h-0 overflow-y-auto p-5">
            {selectedCredential ? (
              <CredentialDetail
                group={selectedCredential}
                targetName={selectedCredential.current.kind === 'runtime' ? targetNames.get(keyTargetId(selectedCredential.current) ?? '') : null}
                projectId={projectId!}
                onBack={() => updateParams({ credential: null })}
                onRotate={setRotateTarget}
                onRevoke={setRevokeTarget}
              />
            ) : (
              <div className="space-y-4">
                <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
                  <div className="relative min-w-0 flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" /><Input value={modalQuery} onChange={(event) => setModalQuery(event.target.value)} placeholder="Search by name, purpose or prefix..." className="pl-9" /></div>
                  <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)} className="h-10 rounded-lg border border-border/80 bg-surface/65 px-3 text-xs text-white outline-none"><option value="all">All statuses</option><option value="active">Active</option><option value="revoked">Revoked</option><option value="expired">Expired</option></select>
                </div>
                {visibleModalGroups.length > 0 ? <div className="space-y-3">{visibleModalGroups.map((group) => <CredentialRow key={group.id} group={group} onClick={() => updateParams({ credential: group.id })} />)}</div> : <div className="rounded-xl border border-dashed border-border/80 bg-surface/35 px-5 py-10 text-center"><Zap className="mx-auto h-5 w-5 text-muted" /><p className="mt-3 text-sm font-semibold text-white">No keys in this view</p><p className="mt-1 text-xs text-muted">Adjust the filters or create a credential.</p></div>}
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
        initialTargetType={createTargetType ?? activeTargetType}
        lockedTargetType={createTargetId ? createTargetType : undefined}
        lockedTargetId={createTargetId}
        initialEnvironment={createEnvironment}
        layer={managementOpen ? 'nestedModal' : 'modal'}
      />

      <RotateApiKeyDialog
        open={Boolean(rotateTarget)}
        apiKey={rotateTarget}
        targetName={rotateTargetName}
        loading={rotateKey.isPending}
        onClose={() => setRotateTarget(null)}
        onConfirm={() => void rotate()}
      />

      <Dialog open={Boolean(revokeTarget)} onClose={() => { if (!revokeKey.isPending) setRevokeTarget(null) }} title="Revoke API key" className="max-w-xl" layer="nestedModal">
        {revokeTarget && (
          <div className="space-y-5">
            <div className="rounded-xl border border-red-500/25 bg-red-500/5 p-4"><p className="text-sm font-semibold text-red-100">{revokeTarget.name}</p><code className="mt-1 block text-xs text-red-100/70">{revokeTarget.key_prefix}...</code><p className="mt-3 text-xs leading-5 text-red-100/75">Requests signed with this secret will stop working immediately. Rotation history and metadata remain available.</p></div>
            <div className="flex justify-end gap-2 border-t border-border/80 pt-4"><Button variant="secondary" onClick={() => setRevokeTarget(null)} disabled={revokeKey.isPending}>Cancel</Button><Button variant="destructive" onClick={() => void revoke()} loading={revokeKey.isPending}>Revoke key</Button></div>
          </div>
        )}
      </Dialog>

      <Dialog open={Boolean(revealedKey)} onClose={() => setRevealedKey(null)} title="New API key secret" className="max-w-2xl" layer="nestedModal">
        {revealedKey && (
          <div>
            <ApiKeySecretReveal apiKey={revealedKey} targetName={revealedTargetName} />
            <div className="mt-5 flex justify-end border-t border-border/80 pt-4"><Button onClick={() => setRevealedKey(null)}>Done</Button></div>
          </div>
        )}
      </Dialog>
    </div>
  )
}
