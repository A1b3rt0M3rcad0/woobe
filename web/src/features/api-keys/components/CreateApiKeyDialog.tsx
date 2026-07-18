import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, Bot, Check, KeyRound, Network, Search, ShieldCheck, Zap } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { useAgents, useReleases } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'
import { useCreateApiKey, useCreateRuntimeApiKey } from '@/features/api-keys/hooks'
import type {
  ApiKeyKind,
  ApiKeyScope,
  CreateApiKeyResponse,
  RuntimeEnvironment,
  RuntimeInterface,
  RuntimeTargetType,
} from '@/features/api-keys/types'
import { listNetworks } from '@/features/network/api'
import type { NetworkResource } from '@/features/network/types'
import type { DialogLayer } from '@/lib/ui-layers'
import {
  ApiKeyExpirationField,
  DEFAULT_API_KEY_EXPIRATION,
  resolveApiKeyExpiration,
  type ApiKeyExpirationValue,
} from './ApiKeyExpirationField'
import { ApiKeySecretReveal } from './ApiKeySecretReveal'

interface CreateApiKeyDialogProps {
  open: boolean
  onClose: () => void
  projectId: string
  initialKind?: ApiKeyKind
  initialTargetType?: RuntimeTargetType
  lockedTargetType?: RuntimeTargetType
  lockedTargetId?: string
  lockedAgentId?: string
  initialEnvironment?: RuntimeEnvironment
  layer?: DialogLayer
  onCreated?: (apiKey: CreateApiKeyResponse) => void
}

const PROJECT_PERMISSIONS: Array<{ value: ApiKeyScope; label: string; description: string }> = [
  { value: 'traces:read', label: 'Traces', description: 'Read execution traces across this Project.' },
  { value: 'usage:read', label: 'Usage & cost', description: 'Read metering, usage and cost data.' },
]

const AVAILABLE_RUNTIME_INTERFACES: Array<{ value: RuntimeInterface; label: string; description: string }> = [
  { value: 'http', label: 'HTTP', description: 'Synchronous Runtime API requests.' },
  { value: 'stream', label: 'Streaming', description: 'Server-Sent Events while the Run executes.' },
]

function environmentLabel(environment: RuntimeEnvironment): string {
  return environment === 'production' ? 'Production' : 'Staging'
}

function targetTypeLabel(targetType: RuntimeTargetType): string {
  return targetType === 'network' ? 'Network' : 'Agent'
}

function SelectionCard({
  selected,
  title,
  description,
  icon,
  onClick,
  disabled = false,
}: {
  selected: boolean
  title: string
  description: string
  icon: ReactNode
  onClick: () => void
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`rounded-xl border p-4 text-left transition-colors ${
        selected
          ? 'border-primary/45 bg-primary/10'
          : 'border-border/85 bg-background/50 hover:border-primary/30'
      } disabled:cursor-default disabled:opacity-70`}
    >
      <span className="flex items-start gap-3">
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${
          selected ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-border bg-background text-muted'
        }`}>
          {icon}
        </span>
        <span className="min-w-0">
          <span className="block text-sm font-semibold text-white">{title}</span>
          <span className="mt-1 block text-[11px] leading-4 text-muted">{description}</span>
        </span>
      </span>
    </button>
  )
}

function TargetList({
  targetType,
  agents,
  networks,
  selectedTargetId,
  loading,
  locked,
  onSelect,
}: {
  targetType: RuntimeTargetType
  agents: Agent[]
  networks: NetworkResource[]
  selectedTargetId: string
  loading: boolean
  locked: boolean
  onSelect: (targetId: string) => void
}) {
  const [query, setQuery] = useState('')
  const items = targetType === 'agent'
    ? agents.map((agent) => ({
        id: agent.id,
        name: agent.name,
        description: `${agent.provider} · ${agent.model}`,
      }))
    : networks.map((network) => ({
        id: network.id,
        name: network.name,
        description: `${network.agent_count ?? network.draft_definition.nodes?.length ?? 0} Agents · ${network.description || 'No description'}`,
      }))
  const visibleItems = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    const candidates = locked && selectedTargetId
      ? items.filter((item) => item.id === selectedTargetId)
      : items
    if (!normalized) return candidates
    return candidates.filter((item) => `${item.name} ${item.description}`.toLowerCase().includes(normalized))
  }, [items, locked, query, selectedTargetId])

  if (loading) {
    return <div className="rounded-xl border border-border/80 bg-background/55 px-4 py-6 text-center text-sm text-muted">Loading {targetTypeLabel(targetType)}s...</div>
  }

  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border/80 bg-background/35 px-4 py-6 text-center">
        <p className="text-sm font-medium text-white">No {targetTypeLabel(targetType)}s available</p>
        <p className="mt-1 text-xs leading-5 text-muted">Create a {targetTypeLabel(targetType)} before creating this Runtime Key.</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {!locked && items.length > 5 && (
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${targetTypeLabel(targetType)}s`} className="pl-9" />
        </div>
      )}
      <div className="scrollbar-thin max-h-[260px] space-y-2 overflow-y-auto pr-1">
        {visibleItems.map((item) => {
          const selected = item.id === selectedTargetId
          return (
            <button
              key={item.id}
              type="button"
              aria-pressed={selected}
              onClick={() => { if (!locked) onSelect(item.id) }}
              className={`flex w-full items-start justify-between gap-4 rounded-xl border px-4 py-3 text-left transition-colors ${
                selected
                  ? 'border-primary/55 bg-primary/8'
                  : 'border-border/85 bg-background/55 hover:border-primary/30 hover:bg-background/80'
              } ${locked ? 'cursor-default' : ''}`}
            >
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-white">{item.name}</span>
                <span className="mt-1 block truncate text-xs text-muted">{item.description}</span>
              </span>
              <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${selected ? 'border-primary bg-primary text-white' : 'border-border bg-background'}`}>
                {selected && <Check className="h-3 w-3" />}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function RuntimeInterfaces({
  interfaces,
  onToggle,
}: {
  interfaces: RuntimeInterface[]
  onToggle: (runtimeInterface: RuntimeInterface) => void
}) {
  return (
    <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
      <p className="text-xs font-medium text-muted">Allowed interfaces</p>
      <div className="mt-2 grid auto-rows-fr grid-cols-2 gap-2">
        {AVAILABLE_RUNTIME_INTERFACES.map((item) => {
          const selected = interfaces.includes(item.value)
          return (
            <button
              key={item.value}
              type="button"
              onClick={() => onToggle(item.value)}
              className={`min-h-[72px] rounded-lg border p-3 text-left ${selected ? 'border-primary/35 bg-primary/10' : 'border-border/80 bg-background/45'}`}
            >
              <p className="text-xs font-medium text-white">{item.label}</p>
              <p className="mt-1 text-[10px] leading-4 text-muted">{item.description}</p>
            </button>
          )
        })}
      </div>
      <div className="mt-3 flex items-center justify-between border-t border-border/65 pt-3 text-[10px] text-muted/70">
        <span>Jobs</span>
        <span className="rounded-full border border-border/70 bg-background/35 px-2 py-0.5 uppercase tracking-wide">Coming soon</span>
      </div>
    </section>
  )
}

export function CreateApiKeyDialog({
  open,
  onClose,
  projectId,
  initialKind,
  initialTargetType,
  lockedTargetType,
  lockedTargetId,
  lockedAgentId,
  initialEnvironment,
  layer = 'modal',
  onCreated,
}: CreateApiKeyDialogProps) {
  const effectiveLockedType = lockedTargetType ?? (lockedAgentId ? 'agent' : undefined)
  const effectiveLockedId = lockedTargetId ?? lockedAgentId
  const { data: agents = [], isLoading: agentsLoading } = useAgents(projectId)
  const networksQuery = useQuery({
    queryKey: ['networks', projectId, 'runtime-key-dialog'],
    queryFn: () => listNetworks(projectId),
    enabled: Boolean(open && projectId),
  })
  const networks = networksQuery.data ?? []
  const createProjectKey = useCreateApiKey(projectId)
  const createRuntimeKey = useCreateRuntimeApiKey(projectId)

  const [kind, setKind] = useState<ApiKeyKind>(initialKind ?? 'runtime')
  const [targetType, setTargetType] = useState<RuntimeTargetType>(effectiveLockedType ?? initialTargetType ?? 'agent')
  const [targetId, setTargetId] = useState(effectiveLockedId ?? '')
  const [name, setName] = useState('')
  const [nameTouched, setNameTouched] = useState(false)
  const [description, setDescription] = useState('')
  const [environment, setEnvironment] = useState<RuntimeEnvironment>(initialEnvironment ?? 'production')
  const [environmentTouched, setEnvironmentTouched] = useState(false)
  const [interfaces, setInterfaces] = useState<RuntimeInterface[]>(['http', 'stream'])
  const [permissions, setPermissions] = useState<ApiKeyScope[]>(['traces:read', 'usage:read'])
  const [expiration, setExpiration] = useState<ApiKeyExpirationValue>(DEFAULT_API_KEY_EXPIRATION)
  const [error, setError] = useState<string | null>(null)
  const [expirationError, setExpirationError] = useState<string | null>(null)
  const [createdKey, setCreatedKey] = useState<CreateApiKeyResponse | null>(null)

  const selectedAgent = targetType === 'agent' ? agents.find((agent) => agent.id === targetId) ?? null : null
  const selectedNetwork = targetType === 'network' ? networks.find((network) => network.id === targetId) ?? null : null
  const selectedTargetName = selectedAgent?.name ?? selectedNetwork?.name ?? null
  const { data: releases = [], isLoading: releasesLoading } = useReleases(kind === 'runtime' && targetType === 'agent' && targetId ? targetId : undefined)
  const agentRelease = releases.find((release) => release.status === environment) ?? null
  const networkVersionId = selectedNetwork
    ? environment === 'production' ? selectedNetwork.production_version_id : selectedNetwork.staging_version_id
    : null
  const deploymentAvailable = targetType === 'agent' ? Boolean(agentRelease) : Boolean(networkVersionId)
  const targetsLoading = targetType === 'agent' ? agentsLoading : networksQuery.isLoading
  const kindLocked = initialKind !== undefined
  const targetLocked = Boolean(effectiveLockedType && effectiveLockedId)
  const contextualRuntime = Boolean(
    initialKind === 'runtime'
    && effectiveLockedType
    && effectiveLockedId
    && initialEnvironment,
  )
  const isPending = createProjectKey.isPending || createRuntimeKey.isPending
  const TargetIcon = targetType === 'network' ? Network : Bot

  useEffect(() => {
    if (!open) return
    const nextTargetType = effectiveLockedType ?? initialTargetType ?? 'agent'
    setKind(initialKind ?? 'runtime')
    setTargetType(nextTargetType)
    setTargetId(effectiveLockedId ?? '')
    setName('')
    setNameTouched(false)
    setDescription('')
    setEnvironment(initialEnvironment ?? 'production')
    setEnvironmentTouched(false)
    setInterfaces(['http', 'stream'])
    setPermissions(['traces:read', 'usage:read'])
    setExpiration(DEFAULT_API_KEY_EXPIRATION)
    setError(null)
    setExpirationError(null)
    setCreatedKey(null)
  }, [effectiveLockedId, effectiveLockedType, initialEnvironment, initialKind, initialTargetType, open])

  useEffect(() => {
    if (!open || !contextualRuntime || nameTouched || !selectedTargetName) return
    setName(`${selectedTargetName} · ${environmentLabel(environment)}`)
  }, [contextualRuntime, environment, nameTouched, open, selectedTargetName])

  useEffect(() => {
    if (!open || contextualRuntime || kind !== 'runtime' || !targetId || environmentTouched) return
    if (targetType === 'agent') {
      if (releasesLoading || releases.some((release) => release.status === environment)) return
      if (releases.some((release) => release.status === 'staging')) setEnvironment('staging')
      else if (releases.some((release) => release.status === 'production')) setEnvironment('production')
      return
    }
    if (!selectedNetwork || deploymentAvailable) return
    if (selectedNetwork.staging_version_id) setEnvironment('staging')
    else if (selectedNetwork.production_version_id) setEnvironment('production')
  }, [contextualRuntime, deploymentAvailable, environment, environmentTouched, kind, open, releases, releasesLoading, selectedNetwork, targetId, targetType])

  const close = () => {
    setCreatedKey(null)
    setError(null)
    setExpirationError(null)
    onClose()
  }

  const togglePermission = (scope: ApiKeyScope) => {
    setPermissions((current) => current.includes(scope) ? current.filter((item) => item !== scope) : [...current, scope])
    setError(null)
  }

  const toggleInterface = (runtimeInterface: RuntimeInterface) => {
    if (runtimeInterface === 'jobs') return
    setInterfaces((current) => current.includes(runtimeInterface) ? current.filter((item) => item !== runtimeInterface) : [...current, runtimeInterface])
    setError(null)
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setExpirationError(null)
    const normalizedName = name.trim()
    if (!normalizedName) {
      setError('Enter a name that identifies what this key is used for')
      return
    }
    const expiresAt = resolveApiKeyExpiration(expiration)
    if (expiration.preset === 'custom' && !expiresAt) {
      setExpirationError('Select a future expiration date and time')
      return
    }

    try {
      let result: CreateApiKeyResponse
      if (kind === 'runtime') {
        if (!targetId || !selectedTargetName) {
          setError(`Select a ${targetTypeLabel(targetType)}`)
          return
        }
        if (interfaces.length === 0) {
          setError('Select at least one runtime interface')
          return
        }
        result = await createRuntimeKey.mutateAsync({
          name: normalizedName,
          description: description.trim() || null,
          target_type: targetType,
          target_id: targetId,
          agent_id: targetType === 'agent' ? targetId : undefined,
          environment,
          interfaces,
          expires_at: expiresAt?.toISOString() ?? null,
        })
      } else {
        if (permissions.length === 0) {
          setError('Select at least one Project permission')
          return
        }
        result = await createProjectKey.mutateAsync({
          name: normalizedName,
          description: description.trim() || null,
          scopes: permissions,
          expires_at: expiresAt?.toISOString() ?? null,
        })
      }
      setCreatedKey(result)
      onCreated?.(result)
      toast.success(`${kind === 'runtime' ? 'Runtime' : 'Project'} Key created`)
    } catch (creationError) {
      setError(creationError instanceof Error ? creationError.message : 'Failed to create API Key')
    }
  }

  const title = createdKey
    ? `${createdKey.kind === 'runtime' ? 'Runtime' : 'Project'} Key created`
    : contextualRuntime
      ? 'Create Runtime Key'
      : 'Create API Key'

  const identitySection = (
    <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-white">Key identity</h3>
          <p className="mt-1 text-xs leading-5 text-muted">Name the integration and document its purpose.</p>
        </div>
        {!contextualRuntime && (
          <span className="rounded-full border border-primary/25 bg-primary/10 px-2.5 py-1 text-[10px] font-medium text-primary-light">{kind === 'runtime' ? 'Runtime Key' : 'Project Key'}</span>
        )}
      </div>
      <div className="mt-4 grid gap-3">
        <label className="grid gap-1.5 text-xs font-medium text-muted">
          Name
          <Input
            value={name}
            onChange={(event) => {
              setName(event.target.value)
              setNameTouched(true)
              setError(null)
            }}
            placeholder={kind === 'runtime' ? 'Production backend' : 'Operations dashboard'}
            maxLength={255}
            autoFocus
          />
        </label>
        <label className="grid gap-1.5 text-xs font-medium text-muted">
          <span className="flex items-center justify-between gap-3">
            <span>Description <span className="font-normal text-muted/70">Optional</span></span>
            <span className="text-[10px] font-normal text-muted/70">{description.length}/500</span>
          </span>
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Which service or integration uses this key?"
            maxLength={500}
            rows={contextualRuntime ? 3 : 2}
            className="w-full resize-none rounded-lg border border-border/80 bg-background/70 px-3 py-2.5 text-sm text-white outline-none placeholder:text-muted/60 focus:border-primary/40"
          />
        </label>
      </div>
    </section>
  )

  return (
    <Dialog
      open={open}
      onClose={close}
      title={title}
      className={createdKey
        ? 'max-w-2xl'
        : contextualRuntime
          ? 'max-h-[calc(100svh-2rem)] max-w-[880px] overflow-hidden'
          : 'max-h-[calc(100svh-2rem)] max-w-[1120px] overflow-hidden'}
      layer={layer}
    >
      {createdKey ? (
        <div>
          <ApiKeySecretReveal apiKey={createdKey} targetName={selectedTargetName} />
          <div className="mt-5 flex justify-end border-t border-border/80 pt-4"><Button onClick={close}>Done</Button></div>
        </div>
      ) : (
        <form className="flex max-h-[calc(100svh-10rem)] min-h-0 flex-col" onSubmit={handleSubmit}>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto pr-1">
            {contextualRuntime ? (
              <div className="space-y-4">
                <section className="flex flex-col gap-3 rounded-xl border border-border/80 bg-background/35 p-4 sm:flex-row sm:items-center">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary-light">
                    <TargetIcon className="h-4 w-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-white">{selectedTargetName ?? `Loading ${targetTypeLabel(targetType)}…`}</p>
                    <p className="mt-1 text-[11px] leading-4 text-muted">
                      {targetTypeLabel(targetType)} · {environmentLabel(environment)} · Runtime Key
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2 text-[10px] text-muted">
                    <span className={`h-1.5 w-1.5 rounded-full ${deploymentAvailable ? 'bg-emerald-400' : 'bg-muted'}`} />
                    <span>{targetsLoading || (targetType === 'agent' && releasesLoading) ? 'Checking deployment' : deploymentAvailable ? 'Deployment available' : 'Not deployed'}</span>
                  </div>
                </section>

                <div className="grid items-start gap-4 lg:grid-cols-2">
                  {identitySection}
                  <div className="space-y-4">
                    <RuntimeInterfaces interfaces={interfaces} onToggle={toggleInterface} />
                    <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                      <ApiKeyExpirationField value={expiration} onChange={(nextValue) => { setExpiration(nextValue); setExpirationError(null) }} error={expirationError} />
                    </section>
                  </div>
                </div>
              </div>
            ) : (
              <div className={kindLocked ? '' : 'grid gap-4 lg:grid-cols-[200px_minmax(0,1fr)]'}>
                {!kindLocked && (
                  <aside className="space-y-3 lg:sticky lg:top-0 lg:self-start">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted/75">Key type</p>
                    <SelectionCard selected={kind === 'runtime'} title="Runtime Key" description="Execute one Agent or Network deployment." icon={<Zap className="h-4 w-4" />} onClick={() => { setKind('runtime'); setError(null) }} />
                    <SelectionCard selected={kind === 'project'} title="Project Key" description="Read operational Project APIs." icon={<ShieldCheck className="h-4 w-4" />} onClick={() => { setKind('project'); setError(null) }} />
                  </aside>
                )}

                <main className="min-w-0">
                  <div className="grid items-start gap-4 lg:grid-cols-2">
                    <div className="space-y-4">
                      {identitySection}

                      {kind === 'runtime' ? (
                        <>
                          <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                            <div className="mb-3">
                              <h3 className="text-sm font-semibold text-white">Runtime target</h3>
                              <p className="mt-1 text-xs leading-5 text-muted">The key can execute exactly one target in one environment.</p>
                            </div>
                            <div className="grid gap-2 sm:grid-cols-2">
                              <SelectionCard selected={targetType === 'agent'} title="Agent" description="Creates one Agent Run per request." icon={<Bot className="h-4 w-4" />} disabled={Boolean(effectiveLockedType)} onClick={() => { setTargetType('agent'); setTargetId(''); setEnvironmentTouched(false); setError(null) }} />
                              <SelectionCard selected={targetType === 'network'} title="Network" description="Creates one Network Run composed of Agent Runs." icon={<Network className="h-4 w-4" />} disabled={Boolean(effectiveLockedType)} onClick={() => { setTargetType('network'); setTargetId(''); setEnvironmentTouched(false); setError(null) }} />
                            </div>
                          </section>

                          <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                            <div className="mb-4">
                              <h3 className="text-sm font-semibold text-white">{targetTypeLabel(targetType)}</h3>
                              <p className="mt-1 text-xs leading-5 text-muted">Choose which {targetTypeLabel(targetType)} deployment this credential can execute.</p>
                            </div>
                            <TargetList targetType={targetType} agents={agents} networks={networks} selectedTargetId={targetId} loading={targetsLoading} locked={targetLocked} onSelect={(nextTargetId) => { setTargetId(nextTargetId); setEnvironmentTouched(false); setError(null) }} />
                          </section>
                        </>
                      ) : (
                        <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                          <h3 className="text-sm font-semibold text-white">Permissions</h3>
                          <p className="mt-1 text-xs leading-5 text-muted">Choose which Project operations this key can access.</p>
                          <div className="mt-4 grid gap-2">
                            {PROJECT_PERMISSIONS.map((item) => {
                              const selected = permissions.includes(item.value)
                              return (
                                <button key={item.value} type="button" onClick={() => togglePermission(item.value)} className={`rounded-xl border p-4 text-left ${selected ? 'border-primary/35 bg-primary/10' : 'border-border/80 bg-background/45'}`}>
                                  <div className="flex items-center gap-2"><Activity className="h-4 w-4 text-primary-light" /><p className="text-sm font-medium text-white">{item.label}</p></div>
                                  <p className="mt-2 text-xs leading-5 text-muted">{item.description}</p>
                                </button>
                              )
                            })}
                          </div>
                        </section>
                      )}
                    </div>

                    <div className="space-y-4">
                      {kind === 'runtime' && (
                        <>
                          <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                            <p className="text-xs font-medium text-muted">Environment</p>
                            <div className="mt-2 grid grid-cols-2 gap-2">
                              {(['staging', 'production'] as RuntimeEnvironment[]).map((item) => (
                                <button
                                  key={item}
                                  type="button"
                                  onClick={() => { setEnvironment(item); setEnvironmentTouched(true); setError(null) }}
                                  className={`h-10 rounded-lg border text-xs font-medium ${environment === item ? 'border-primary/40 bg-primary/10 text-primary-light' : 'border-border bg-background/45 text-muted'}`}
                                >
                                  {environmentLabel(item)}
                                </button>
                              ))}
                            </div>
                            <div className="mt-3 rounded-lg border border-border/75 bg-background/45 px-3 py-2.5">
                              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Current deployment</p>
                              {!targetId
                                ? <p className="mt-1.5 text-xs text-muted">Select a target to inspect this environment.</p>
                                : releasesLoading && targetType === 'agent'
                                  ? <p className="mt-1.5 text-xs text-muted">Checking current deployment…</p>
                                  : deploymentAvailable
                                    ? <p className="mt-1.5 text-xs text-white">{environmentLabel(environment)} · <span className="font-medium">Available</span></p>
                                    : <p className="mt-1.5 text-xs leading-5 text-muted">{environmentLabel(environment)} · Not deployed. Deploy a release to enable Runtime requests.</p>}
                            </div>
                          </section>

                          <RuntimeInterfaces interfaces={interfaces} onToggle={toggleInterface} />
                        </>
                      )}

                      <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                        <ApiKeyExpirationField value={expiration} onChange={(nextValue) => { setExpiration(nextValue); setExpirationError(null) }} error={expirationError} />
                      </section>

                      <section className="rounded-xl border border-border/80 bg-background/35 px-4 py-3">
                        <div className="flex items-start gap-3">
                          <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" />
                          <div className="min-w-0 flex-1">
                            {kind === 'runtime' ? (
                              <>
                                <p className="text-xs leading-5 text-white"><span className="font-medium">{selectedTargetName || `Selected ${targetTypeLabel(targetType)}`}</span> · {environmentLabel(environment)} · {interfaces.length ? interfaces.join(', ') : 'No interfaces'}</p>
                                <p className="mt-0.5 text-[11px] leading-5 text-muted">Target type: {targetType}. Deploys and rollbacks keep the same key.</p>
                              </>
                            ) : (
                              <>
                                <p className="text-xs leading-5 text-white">Project operations · {permissions.length ? permissions.join(', ') : 'No permissions'}</p>
                                <p className="mt-0.5 text-[11px] leading-5 text-muted">Project Keys cannot execute Agents or Networks.</p>
                              </>
                            )}
                          </div>
                        </div>
                      </section>
                    </div>
                  </div>
                </main>
              </div>
            )}
          </div>

          <div className="mt-5 flex min-h-12 shrink-0 items-center justify-between gap-4 border-t border-border/80 pt-4">
            <div className="min-w-0 flex-1">{error && <p className="text-xs text-red-300">{error}</p>}</div>
            <div className="flex shrink-0 gap-2">
              <Button type="button" variant="secondary" onClick={close}>Cancel</Button>
              <Button type="submit" loading={isPending}>Create {kind === 'runtime' ? 'Runtime' : 'Project'} Key</Button>
            </div>
          </div>
        </form>
      )}
    </Dialog>
  )
}
