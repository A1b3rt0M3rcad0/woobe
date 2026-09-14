import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft,
  Ban,
  Bot,
  Clock3,
  Key,
  Layers3,
  Network,
  Pencil,
  Plus,
  RotateCcw,
  ShieldCheck,
  Zap,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button, Input, Select, Textarea } from '@woobe/ui'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ResourceCard, ResourcePill } from '@/components/common/OperationalResourceCard'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSearch,
  ResourceSectionHeader,
  ResourceTabs,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Dialog } from '@/components/ui/Dialog'
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

function TargetCard({ target, credentials, onClick }: { target: TargetDescriptor; credentials: CredentialGroup[]; onClick: () => void }) {
  const Icon = target.type === 'network' ? Network : Bot
  const active = credentials.filter((item) => item.current.status === 'active').length
  const production = credentials.filter((item) => item.current.status === 'active' && item.current.environment === 'production').length
  const staging = credentials.filter((item) => item.current.status === 'active' && item.current.environment === 'staging').length
  const lastUsed = credentials.reduce<string | null>((latest, item) => {
    const candidate = item.revisions.reduce<string | null>((revisionLatest, revision) => (
      timestamp(revision.last_used_at) > timestamp(revisionLatest) ? revision.last_used_at ?? null : revisionLatest
    ), null)
    return timestamp(candidate) > timestamp(latest) ? candidate : latest
  }, null)

  return (
    <ResourceCard
      onClick={onClick}
      icon={<Icon className="h-4 w-4" />}
      title={target.name}
      subtitle={target.unavailable ? 'Target unavailable' : `${active} active · ${credentials.length} total`}
      metadata={(
        <>
          <ResourcePill tone={production > 0 ? 'primary' : 'default'}>Production · {production}</ResourcePill>
          <ResourcePill tone={staging > 0 ? 'primary' : 'default'}>Staging · {staging}</ResourcePill>
          {credentials.length === 0 ? <ResourcePill>No keys</ResourcePill> : null}
        </>
      )}
      footer={`Last used · ${formatDate(lastUsed)}`}
    />
  )
}

function CredentialRow({ group, onClick }: { group: CredentialGroup; onClick: () => void }) {
  return (
    <ResourceCard
      onClick={onClick}
      className="min-h-[142px]"
      icon={<Key className="h-4 w-4" />}
      title={group.current.name}
      subtitle={group.current.description || 'No purpose documented.'}
      status={<StatusBadge status={group.current.status} size="compact" />}
      metadata={(
        <>
          <ResourcePill tone="primary">{environmentLabel(group.current.environment)}</ResourcePill>
          {group.current.interfaces.map((item) => <ResourcePill key={item}>{item}</ResourcePill>)}
          {group.revisions.length > 1 ? <ResourcePill>{group.revisions.length - 1} rotations</ResourcePill> : null}
        </>
      )}
      footer={`${group.current.key_prefix}... · Last used · ${formatDate(group.current.last_used_at)}`}
    />
  )
}

function DetailField({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div className="min-w-0 border border-border bg-control/45 p-3">
      <div className="flex items-center gap-1.5 font-mono text-[8px] font-semibold uppercase tracking-[0.11em] text-muted-foreground">{icon}{label}</div>
      <p className="mt-1 truncate font-mono text-[10px] text-slate-100" title={value}>{value}</p>
    </div>
  )
}

function CredentialDetail({ group, targetName, projectId, onBack, onRotate, onRevoke }: { group: CredentialGroup; targetName?: string | null; projectId: string; onBack: () => void; onRotate: (apiKey: ApiKey) => void; onRevoke: (apiKey: ApiKey) => void }) {
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
      await updateCredential.mutateAsync({ apiKeyId: group.current.id, data: { name: normalizedName, description: description.trim() || null } })
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
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <Button type="button" size="sm" variant="ghost" onClick={onBack}><ArrowLeft className="h-3.5 w-3.5" />Back to keys</Button>
        {!editing ? <Button type="button" size="sm" variant="outline" onClick={() => setEditing(true)}><Pencil className="h-3.5 w-3.5" />Edit details</Button> : null}
      </div>

      <section className="border border-border bg-surface/[0.88] p-4">
        {editing ? (
          <div className="space-y-4">
            <label className="grid gap-1.5 font-mono text-[9px] font-medium text-muted-foreground">Name<Input value={name} onChange={(event) => setName(event.target.value)} maxLength={255} autoFocus /></label>
            <label className="grid gap-1.5 font-mono text-[9px] font-medium text-muted-foreground">Description<Textarea value={description} onChange={(event) => setDescription(event.target.value)} maxLength={500} rows={4} /></label>
            <div className="flex justify-end gap-2 border-t border-border pt-3"><Button type="button" variant="secondary" onClick={() => { setEditing(false); setName(current.name); setDescription(current.description ?? '') }}>Cancel</Button><Button type="button" onClick={() => void save()} loading={updateCredential.isPending}>Save changes</Button></div>
          </div>
        ) : (
          <div>
            <div className="flex items-start justify-between gap-4"><div className="min-w-0"><h3 className="font-mono text-[12px] font-bold text-slate-50">{current.name}</h3><p className="mt-1.5 font-sans text-[11px] leading-5 text-muted-foreground">{current.description || 'No purpose documented for this credential.'}</p></div><StatusBadge status={current.status} size="compact" /></div>
            <div className="mt-4 grid gap-2.5 sm:grid-cols-2">{current.kind === 'runtime' ? <DetailField label={targetLabel} value={targetName || `${targetLabel} unavailable`} icon={<TargetIcon className="h-3 w-3" />} /> : null}<DetailField label="Environment" value={environmentLabel(current.environment)} /><DetailField label="Active prefix" value={`${current.key_prefix}...`} /><DetailField label="Last used" value={formatDate(current.last_used_at)} /></div>
          </div>
        )}
      </section>

      <section className="border border-border bg-surface/[0.88] p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><h3 className="font-mono text-[10px] font-bold text-slate-50">Credential actions</h3><p className="mt-1 font-sans text-[10px] leading-4 text-muted-foreground">Rotation changes only the secret. Target, environment and metadata remain stable.</p></div><div className="flex gap-2"><Button type="button" size="sm" variant="outline" onClick={() => onRotate(current)} disabled={current.status !== 'active'}><RotateCcw className="h-3.5 w-3.5" />Rotate</Button><Button type="button" size="sm" variant="destructive" onClick={() => onRevoke(current)} disabled={current.status !== 'active'}><Ban className="h-3.5 w-3.5" />Revoke</Button></div></div></section>

      <section className="overflow-hidden border border-border bg-surface/[0.88]"><div className="border-b border-border px-4 py-3"><div className="flex items-center gap-2"><Layers3 className="h-3.5 w-3.5 text-primary-light" /><h3 className="font-mono text-[10px] font-bold text-slate-50">Rotation history</h3></div><p className="mt-1 font-sans text-[10px] text-muted-foreground">Secret revisions remain available for audit, but the secret value is never recoverable.</p></div><div className="divide-y divide-border/70">{group.revisions.map((revision, index) => <div key={revision.id} className="grid gap-3 px-4 py-3 font-mono text-[9px] sm:grid-cols-[minmax(0,1fr)_90px_180px] sm:items-center"><div className="min-w-0"><div className="flex items-center gap-2"><code className="truncate text-slate-100">{revision.key_prefix}...</code>{index === 0 ? <ResourcePill tone="primary">Latest</ResourcePill> : null}</div><p className="mt-1 text-[8px] text-muted-foreground">Created · {formatDate(revision.created_at)}</p></div><StatusBadge status={revision.status} size="compact" /><div className="text-[8px] leading-4 text-muted-foreground"><p>Last used · {formatDate(revision.last_used_at)}</p>{revision.revoked_at ? <p>Revoked · {formatDate(revision.revoked_at)}</p> : null}</div></div>)}</div></section>
    </div>
  )
}

export default function ApiKeysPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const keysQuery = useApiKeys(projectId)
  const agentsQuery = useAgents(projectId)
  const networksQuery = useQuery({ queryKey: ['networks', projectId, 'api-keys'], queryFn: () => listNetworks(projectId!), enabled: Boolean(projectId) })
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

  const targetNames = useMemo(() => new Map<string, string>([...agents.map((agent) => [agent.id, agent.name] as [string, string]), ...networks.map((network) => [network.id, network.name] as [string, string])]), [agents, networks])

  const targets = useMemo<TargetDescriptor[]>(() => {
    const result: TargetDescriptor[] = activeTargetType === 'agent' ? agents.map((agent) => ({ id: agent.id, name: agent.name, type: 'agent' })) : networks.map((network) => ({ id: network.id, name: network.name, type: 'network' }))
    const known = new Set(result.map((item) => item.id))
    for (const group of runtimeGroups) {
      if (keyTargetType(group.current) !== activeTargetType) continue
      const id = keyTargetId(group.current)
      if (!id || known.has(id)) continue
      result.push({ id, name: `Unavailable ${activeTargetType === 'network' ? 'Network' : 'Agent'}`, type: activeTargetType, unavailable: true })
      known.add(id)
    }
    return result.sort((left, right) => left.name.localeCompare(right.name))
  }, [activeTargetType, agents, networks, runtimeGroups])

  const updateParams = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(updates)) value ? next.set(key, value) : next.delete(key)
    setSearchParams(next)
  }

  const selectKeyTab = (tab: KeyTab) => { updateParams({ type: tab, targetType: null, target: null, agent: null, credential: null, environment: null }); setQuery('') }
  const selectTargetType = (targetType: RuntimeTargetType) => { updateParams({ type: 'runtime', targetType, target: null, agent: null, credential: null, environment: null }); setQuery('') }
  const openCreate = (targetType?: RuntimeTargetType, targetId?: string, environment?: RuntimeEnvironment) => { setCreateTargetType(targetType); setCreateTargetId(targetId); setCreateEnvironment(environment); setShowCreate(true) }

  const selectedTarget = targets.find((target) => target.id === selectedTargetId) ?? null
  const selectedTargetGroups = runtimeGroups.filter((group) => keyTargetType(group.current) === activeTargetType && keyTargetId(group.current) === selectedTargetId && (environmentFilter === 'all' || group.current.environment === environmentFilter))
  const selectedGroups = activeTab === 'runtime' ? selectedTargetGroups : projectGroups
  const selectedCredential = selectedGroups.find((group) => group.id === selectedCredentialId) ?? null

  const visibleTargets = targets.filter((target) => { const normalized = query.trim().toLowerCase(); if (!normalized) return true; const credentialText = runtimeGroups.filter((group) => keyTargetType(group.current) === target.type && keyTargetId(group.current) === target.id).map((group) => `${group.current.name} ${group.current.description ?? ''}`).join(' '); return `${target.name} ${credentialText}`.toLowerCase().includes(normalized) })
  const visibleProjectGroups = projectGroups.filter((group) => { const normalized = query.trim().toLowerCase(); return !normalized || `${group.current.name} ${group.current.description ?? ''} ${group.current.key_prefix}`.toLowerCase().includes(normalized) })
  const visibleModalGroups = selectedGroups.filter((group) => { const normalized = modalQuery.trim().toLowerCase(); const matchesStatus = statusFilter === 'all' || group.current.status === statusFilter; const matchesQuery = !normalized || `${group.current.name} ${group.current.description ?? ''} ${group.current.key_prefix}`.toLowerCase().includes(normalized); return matchesStatus && matchesQuery })

  const closeManagement = () => { updateParams({ target: null, agent: null, credential: null, environment: null }); setModalQuery(''); setStatusFilter('all') }

  const rotate = async () => { if (!rotateTarget) return; try { const result = await rotateKey.mutateAsync({ apiKeyId: rotateTarget.id }); setRotateTarget(null); await keysQuery.refetch(); updateParams({ credential: result.credential_id }); setRevealedKey(result); toast.success('API key rotated') } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to rotate key') } }
  const revoke = async () => { if (!revokeTarget) return; try { await revokeKey.mutateAsync(revokeTarget.id); setRevokeTarget(null); await keysQuery.refetch(); toast.success('API key revoked') } catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to revoke key') } }

  if (!projectId) return <ErrorState message="Project not found" />

  const pageAction = <Button type="button" onClick={() => openCreate(activeTab === 'runtime' ? activeTargetType : undefined)}><Plus className="h-3.5 w-3.5" />Create {activeTab === 'runtime' ? `${activeTargetType === 'network' ? 'Network' : 'Agent'} Runtime` : 'Project'} Key</Button>

  if (keysQuery.isLoading || agentsQuery.isLoading || networksQuery.isLoading) return <ResourcePage title="API Keys" description="Manage stable credentials and Runtime Keys bound to one Agent or Network deployment." action={pageAction}><LoadingState message="Loading API Keys" variant="panel" layout="compact-cards" /></ResourcePage>
  if (keysQuery.isError) return <ResourcePage title="API Keys" description="Manage stable credentials and Runtime Keys bound to one Agent or Network deployment." action={pageAction}><ErrorState error={keysQuery.error} onRetry={keysQuery.refetch} className="rounded-container border border-border bg-surface/70 py-10" /></ResourcePage>

  const selectedTargetAllGroups = runtimeGroups.filter((group) => keyTargetType(group.current) === activeTargetType && keyTargetId(group.current) === selectedTargetId)
  const productionCount = selectedTargetAllGroups.filter((group) => group.current.environment === 'production').length
  const stagingCount = selectedTargetAllGroups.filter((group) => group.current.environment === 'staging').length
  const managementOpen = activeTab === 'runtime' ? Boolean(selectedTarget) : Boolean(selectedCredentialId)
  const rotateTargetName = rotateTarget ? targetNames.get(keyTargetId(rotateTarget) ?? '') ?? null : null
  const revealedTargetName = revealedKey ? targetNames.get(keyTargetId(revealedKey) ?? '') ?? null : null
  const hasPageSearch = Boolean(query.trim())
  const pageCount = activeTab === 'runtime' ? visibleTargets.length : visibleProjectGroups.length

  return (
    <ResourcePage title="API Keys" description="Manage stable credentials and Runtime Keys bound to one Agent or Network deployment." action={pageAction}>
      <ResourceToolbar className={activeTab === 'runtime' ? 'gap-2.5 p-2.5 lg:grid lg:grid-cols-[auto_auto_minmax(280px,1fr)] lg:items-center lg:gap-3' : 'gap-2.5 p-2.5 lg:grid lg:grid-cols-[auto_minmax(280px,1fr)] lg:items-center lg:gap-3'}>
        <ResourceTabs value={activeTab} onChange={selectKeyTab} label="API Key type" tabs={[{ value: 'runtime', label: 'Runtime', count: runtimeGroups.length }, { value: 'project', label: 'Project', count: projectGroups.length }]} />
        {activeTab === 'runtime' ? <div className="lg:border-l lg:border-border lg:pl-3"><ResourceTabs value={activeTargetType} onChange={selectTargetType} label="Runtime target type" tabs={[{ value: 'agent', label: 'Agents', count: agents.length }, { value: 'network', label: 'Networks', count: networks.length }]} /></div> : null}
        <ResourceSearch value={query} onChange={setQuery} placeholder={activeTab === 'runtime' ? `Search ${activeTargetType === 'network' ? 'Networks' : 'Agents'} or key purpose...` : 'Search Project Keys...'} label="Search API Keys" />
      </ResourceToolbar>

      <section>
        <ResourceSectionHeader title={activeTab === 'runtime' ? (activeTargetType === 'network' ? 'Networks' : 'Agents') : 'Project Keys'} description={activeTab === 'runtime' ? 'Open a target to manage Runtime Keys, environments and rotation history.' : 'Operational credentials for traces, usage and Project APIs.'} count={pageCount} />
        {activeTab === 'runtime' ? visibleTargets.length > 0 ? <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">{visibleTargets.map((target) => <TargetCard key={target.id} target={target} credentials={runtimeGroups.filter((group) => keyTargetType(group.current) === target.type && keyTargetId(group.current) === target.id)} onClick={() => updateParams({ type: 'runtime', targetType: target.type, target: target.id, agent: null, credential: null, environment: null })} />)}</div> : <ResourceEmptyState icon={<Zap className="h-4 w-4" />} title={`No ${activeTargetType === 'network' ? 'Networks' : 'Agents'} found`} description={hasPageSearch ? 'Adjust or clear the current search.' : 'Create the target first, then issue its Runtime Key.'} action={hasPageSearch ? <Button type="button" size="sm" variant="outline" onClick={() => setQuery('')}>Clear search</Button> : undefined} /> : visibleProjectGroups.length > 0 ? <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">{visibleProjectGroups.map((group) => <CredentialRow key={group.id} group={group} onClick={() => updateParams({ credential: group.id })} />)}</div> : <ResourceEmptyState icon={<Key className="h-4 w-4" />} title="No Project Keys found" description={hasPageSearch ? 'Adjust or clear the current search.' : 'Create a Project Key for traces, usage or Project APIs.'} action={hasPageSearch ? <Button type="button" size="sm" variant="outline" onClick={() => setQuery('')}>Clear search</Button> : undefined} />}
      </section>

      <Dialog open={managementOpen} onClose={closeManagement} title={activeTab === 'runtime' ? `Runtime Keys · ${selectedTarget?.name ?? ''}` : 'Project Key'} className="flex h-[min(780px,calc(100svh-2rem))] max-w-[1180px] flex-col overflow-hidden" contentClassName="min-h-0 flex-1 p-0">
        <div className="grid h-full min-h-0 lg:grid-cols-[250px_minmax(0,1fr)]">
          <aside className="flex min-h-0 flex-col border-b border-border bg-background/35 lg:border-b-0 lg:border-r">
            <div className="border-b border-border p-4"><div className="flex items-start gap-2.5"><div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light">{activeTab === 'runtime' ? activeTargetType === 'network' ? <Network className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" /> : <ShieldCheck className="h-3.5 w-3.5" />}</div><div className="min-w-0"><p className="truncate font-mono text-[10px] font-bold text-slate-50">{activeTab === 'runtime' ? selectedTarget?.name : selectedCredential?.current.name}</p><p className="mt-1 break-all font-mono text-[8px] leading-4 text-muted-foreground">{activeTab === 'runtime' ? selectedTarget?.id : selectedCredential?.id}</p></div></div></div>
            <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-3">
              {activeTab === 'runtime' ? <section className="border-b border-border pb-3"><p className="px-1 font-mono text-[8px] font-semibold uppercase tracking-[0.13em] text-muted-foreground">Environment</p><div className="mt-2 grid gap-1">{([['all', 'All environments', selectedTargetAllGroups.length], ['production', 'Production', productionCount], ['staging', 'Staging', stagingCount]] as Array<[EnvironmentFilter, string, number]>).map(([value, label, count]) => <button key={value} type="button" onClick={() => updateParams({ environment: value === 'all' ? null : value, credential: null })} className={`flex h-[32px] items-center justify-between rounded-technical border px-2.5 font-mono text-[9px] transition-colors ${environmentFilter === value ? 'border-primary/35 bg-primary/[0.10] text-slate-50' : 'border-transparent text-muted-foreground hover:border-border hover:bg-control hover:text-slate-200'}`}><span>{label}</span><span className="text-[8px] tabular-nums">{count}</span></button>)}</div></section> : null}
              <section className="border-b border-border py-3"><div className="flex items-center gap-1.5"><Clock3 className="h-3.5 w-3.5 text-muted-foreground" /><p className="font-mono text-[9px] font-semibold text-slate-100">Credential summary</p></div><div className="mt-2 grid gap-1 font-mono text-[8px] text-muted-foreground"><p>Active · {selectedGroups.filter((group) => group.current.status === 'active').length}</p><p>Revoked · {selectedGroups.filter((group) => group.current.status === 'revoked').length}</p><p>Expired · {selectedGroups.filter((group) => group.current.status === 'expired').length}</p></div></section>
            </div>
            {activeTab === 'runtime' && selectedTarget && !selectedTarget.unavailable ? <div className="shrink-0 border-t border-border p-3"><Button type="button" className="w-full" onClick={() => openCreate(selectedTarget.type, selectedTarget.id, environmentFilter === 'all' ? undefined : environmentFilter)}><Plus className="h-3.5 w-3.5" />Create Runtime Key</Button></div> : null}
          </aside>

          <main className="min-h-0 overflow-y-auto p-4">
            {selectedCredential ? <CredentialDetail group={selectedCredential} targetName={selectedCredential.current.kind === 'runtime' ? targetNames.get(keyTargetId(selectedCredential.current) ?? '') : null} projectId={projectId} onBack={() => updateParams({ credential: null })} onRotate={setRotateTarget} onRevoke={setRevokeTarget} /> : <div className="space-y-3"><div className="grid gap-2.5 md:grid-cols-[minmax(0,1fr)_170px]"><ResourceSearch value={modalQuery} onChange={setModalQuery} placeholder="Search by name, purpose or prefix..." label="Search credentials" /><Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)} options={[{ value: 'all', label: 'All statuses' }, { value: 'active', label: 'Active' }, { value: 'revoked', label: 'Revoked' }, { value: 'expired', label: 'Expired' }]} /></div>{visibleModalGroups.length > 0 ? <div className="grid gap-3 xl:grid-cols-2">{visibleModalGroups.map((group) => <CredentialRow key={group.id} group={group} onClick={() => updateParams({ credential: group.id })} />)}</div> : <ResourceEmptyState icon={<Zap className="h-4 w-4" />} title="No keys in this view" description="Adjust the filters or create a credential." />}</div>}
          </main>
        </div>
      </Dialog>

      <CreateApiKeyDialog open={showCreate} onClose={() => setShowCreate(false)} projectId={projectId} initialKind={activeTab} initialTargetType={createTargetType ?? activeTargetType} lockedTargetType={createTargetId ? createTargetType : undefined} lockedTargetId={createTargetId} initialEnvironment={createEnvironment} layer={managementOpen ? 'nestedModal' : 'modal'} />
      <RotateApiKeyDialog open={Boolean(rotateTarget)} apiKey={rotateTarget} targetName={rotateTargetName} loading={rotateKey.isPending} onClose={() => setRotateTarget(null)} onConfirm={() => void rotate()} />

      <Dialog open={Boolean(revokeTarget)} onClose={() => { if (!revokeKey.isPending) setRevokeTarget(null) }} title="Revoke API key" className="max-w-xl" layer="nestedModal">
        {revokeTarget ? <div className="space-y-4"><div className="border border-red-500/25 bg-red-500/[0.05] p-4"><p className="font-mono text-[10px] font-semibold text-red-100">{revokeTarget.name}</p><code className="mt-1 block font-mono text-[9px] text-red-100/70">{revokeTarget.key_prefix}...</code><p className="mt-3 font-sans text-[11px] leading-5 text-red-100/75">Requests signed with this secret will stop working immediately. Rotation history and metadata remain available.</p></div><div className="flex justify-end gap-2 border-t border-border pt-3"><Button type="button" variant="secondary" onClick={() => setRevokeTarget(null)} disabled={revokeKey.isPending}>Cancel</Button><Button type="button" variant="destructive" onClick={() => void revoke()} loading={revokeKey.isPending}>Revoke key</Button></div></div> : null}
      </Dialog>

      <Dialog open={Boolean(revealedKey)} onClose={() => setRevealedKey(null)} title="New API key secret" className="max-w-2xl" layer="nestedModal">
        {revealedKey ? <div><ApiKeySecretReveal apiKey={revealedKey} targetName={revealedTargetName} /><div className="mt-4 flex justify-end border-t border-border pt-3"><Button type="button" onClick={() => setRevealedKey(null)}>Done</Button></div></div> : null}
      </Dialog>
    </ResourcePage>
  )
}
