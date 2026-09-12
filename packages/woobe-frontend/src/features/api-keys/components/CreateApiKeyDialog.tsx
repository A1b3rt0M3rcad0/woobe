import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, Bot, Check, KeyRound, Network, Search, ShieldCheck, Zap } from 'lucide-react'
import { toast } from 'sonner'
import { Button, Input, Textarea } from '@woobe/ui'

import { Dialog } from '@/components/ui/Dialog'
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

function SectionHeader({ title, description, trailing }: { title: string; description?: string; trailing?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <h3 className="font-mono text-[10px] font-bold text-slate-50">{title}</h3>
        {description ? <p className="mt-1 font-sans text-[10px] leading-4 text-muted-foreground">{description}</p> : null}
      </div>
      {trailing}
    </div>
  )
}

function CompactChoice({
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
      className={`flex min-h-[48px] items-center gap-2.5 rounded-control border px-3 text-left transition-colors ${
        selected
          ? 'border-primary/45 bg-primary/[0.10] text-slate-50'
          : 'border-border bg-control/35 text-muted-foreground hover:border-slate-600 hover:bg-control/60 hover:text-slate-200'
      } disabled:cursor-default disabled:opacity-60`}
    >
      <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-control border ${selected ? 'border-primary/35 bg-primary/[0.08] text-primary-light' : 'border-border bg-control text-muted-foreground'}`}>
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block font-mono text-[9px] font-semibold">{title}</span>
        <span className="mt-0.5 block truncate font-sans text-[9px] text-muted-foreground">{description}</span>
      </span>
      <span className={`ml-auto h-2 w-2 shrink-0 rounded-full border ${selected ? 'border-primary bg-primary' : 'border-border bg-background'}`} />
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
    return <div className="border border-border bg-control/25 px-3 py-5 text-center font-mono text-[9px] text-muted-foreground">Loading {targetTypeLabel(targetType)}s...</div>
  }

  if (items.length === 0) {
    return (
      <div className="border border-dashed border-border bg-control/20 px-4 py-6 text-center">
        <p className="font-mono text-[9px] font-medium text-slate-100">No {targetTypeLabel(targetType)}s available</p>
        <p className="mt-1 font-sans text-[10px] leading-4 text-muted-foreground">Create a {targetTypeLabel(targetType)} before creating this Runtime Key.</p>
      </div>
    )
  }

  return (
    <div className="space-y-2.5">
      {!locked && items.length > 5 ? (
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${targetTypeLabel(targetType)}s`} className="pl-8" />
        </div>
      ) : null}
      <div className="scrollbar-thin max-h-[250px] divide-y divide-border overflow-y-auto border border-border bg-background/25">
        {visibleItems.map((item) => {
          const selected = item.id === selectedTargetId
          return (
            <button
              key={item.id}
              type="button"
              aria-pressed={selected}
              onClick={() => { if (!locked) onSelect(item.id) }}
              className={`flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors ${
                selected ? 'bg-primary/[0.08]' : 'hover:bg-control/35'
              } ${locked ? 'cursor-default' : ''}`}
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate font-mono text-[9px] font-medium text-slate-100">{item.name}</span>
                <span className="mt-0.5 block truncate font-mono text-[8px] text-muted-foreground">{item.description}</span>
              </span>
              <span className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${selected ? 'border-primary bg-primary text-white' : 'border-border bg-background'}`}>
                {selected ? <Check className="h-2.5 w-2.5" /> : null}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function RuntimeInterfaces({ interfaces, onToggle }: { interfaces: RuntimeInterface[]; onToggle: (runtimeInterface: RuntimeInterface) => void }) {
  return (
    <section className="border-b border-border pb-4">
      <SectionHeader title="Allowed interfaces" description="Choose how this Runtime Key can invoke the deployment." />
      <div className="mt-3 grid grid-cols-2 gap-2">
        {AVAILABLE_RUNTIME_INTERFACES.map((item) => {
          const selected = interfaces.includes(item.value)
          return (
            <button
              key={item.value}
              type="button"
              onClick={() => onToggle(item.value)}
              className={`min-h-[46px] rounded-control border px-3 py-2 text-left transition-colors ${selected ? 'border-primary/40 bg-primary/[0.10]' : 'border-border bg-control/25 hover:bg-control/45'}`}
            >
              <p className="font-mono text-[9px] font-medium text-slate-100">{item.label}</p>
              <p className="mt-0.5 font-sans text-[9px] leading-4 text-muted-foreground">{item.description}</p>
            </button>
          )
        })}
      </div>
      <div className="mt-2.5 flex items-center justify-between font-mono text-[8px] text-muted-foreground">
        <span>Jobs</span>
        <span className="rounded-technical border border-border bg-control/40 px-2 py-0.5 uppercase tracking-[0.1em]">Coming soon</span>
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
  const contextualRuntime = Boolean(initialKind === 'runtime' && effectiveLockedType && effectiveLockedId && initialEnvironment)
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
    <section className="border-b border-border pb-4">
      <SectionHeader
        title="Key identity"
        description="Name the integration and document its purpose."
        trailing={!contextualRuntime ? <span className="rounded-technical border border-primary/30 bg-primary/[0.08] px-2 py-1 font-mono text-[8px] text-primary-light">{kind === 'runtime' ? 'Runtime Key' : 'Project Key'}</span> : undefined}
      />
      <div className="mt-3 grid gap-3">
        <label className="grid gap-1.5 font-mono text-[8px] font-medium text-muted-foreground">
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
        <label className="grid gap-1.5 font-mono text-[8px] font-medium text-muted-foreground">
          <span className="flex items-center justify-between gap-3">
            <span>Description <span className="font-sans font-normal text-muted-foreground/70">Optional</span></span>
            <span className="font-mono text-[8px] font-normal text-muted-foreground/70">{description.length}/500</span>
          </span>
          <Textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Which service or integration uses this key?"
            maxLength={500}
            rows={contextualRuntime ? 3 : 2}
          />
        </label>
      </div>
    </section>
  )

  const summary = kind === 'runtime'
    ? `${selectedTargetName || `Select ${targetTypeLabel(targetType)}`} · ${environmentLabel(environment)} · ${interfaces.length ? interfaces.map((item) => item.toUpperCase()).join(' + ') : 'No interfaces'}`
    : `Project operations · ${permissions.length ? permissions.join(' + ') : 'No permissions'}`

  return (
    <Dialog
      open={open}
      onClose={close}
      title={title}
      className={createdKey ? 'max-w-2xl' : 'flex h-[min(760px,calc(100svh-2rem))] max-w-[1080px] flex-col overflow-hidden'}
      contentClassName={createdKey ? undefined : 'min-h-0 flex-1 p-0'}
      layer={layer}
    >
      {createdKey ? (
        <div>
          <ApiKeySecretReveal apiKey={createdKey} targetName={selectedTargetName} />
          <div className="mt-5 flex justify-end border-t border-border pt-4"><Button onClick={close}>Done</Button></div>
        </div>
      ) : (
        <form className="flex h-full min-h-0 flex-col" onSubmit={handleSubmit}>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-5 py-4">
            {contextualRuntime ? (
              <div className="mb-4 flex items-center gap-3 border border-border bg-control/25 px-3 py-2.5">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light"><TargetIcon className="h-3.5 w-3.5" /></span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-mono text-[9px] font-semibold text-slate-100">{selectedTargetName ?? `Loading ${targetTypeLabel(targetType)}…`}</p>
                  <p className="mt-0.5 font-mono text-[8px] text-muted-foreground">{targetTypeLabel(targetType)} · {environmentLabel(environment)} · Runtime Key</p>
                </div>
                <div className="flex shrink-0 items-center gap-1.5 font-mono text-[8px] text-muted-foreground">
                  <span className={`h-1.5 w-1.5 rounded-full ${deploymentAvailable ? 'bg-emerald-400' : 'bg-muted-foreground'}`} />
                  {targetsLoading || (targetType === 'agent' && releasesLoading) ? 'Checking deployment' : deploymentAvailable ? 'Deployment available' : 'Not deployed'}
                </div>
              </div>
            ) : null}

            {!kindLocked ? (
              <section className="mb-4 border-b border-border pb-4">
                <SectionHeader title="Key type" description="Choose whether this credential executes Runtime or reads Project operations." />
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <CompactChoice selected={kind === 'runtime'} title="Runtime Key" description="Execute one Agent or Network deployment." icon={<Zap className="h-3.5 w-3.5" />} onClick={() => { setKind('runtime'); setError(null) }} />
                  <CompactChoice selected={kind === 'project'} title="Project Key" description="Read operational Project APIs." icon={<ShieldCheck className="h-3.5 w-3.5" />} onClick={() => { setKind('project'); setError(null) }} />
                </div>
              </section>
            ) : null}

            <div className="grid gap-5 lg:grid-cols-2">
              <div className="space-y-4 lg:pr-1">
                {identitySection}

                {kind === 'runtime' ? (
                  <>
                    {!contextualRuntime ? (
                      <section className="border-b border-border pb-4">
                        <SectionHeader title="Runtime target" description="A Runtime Key executes exactly one target in one environment." />
                        <div className="mt-3 grid gap-2 sm:grid-cols-2">
                          <CompactChoice selected={targetType === 'agent'} title="Agent" description="Creates one Agent Run per request." icon={<Bot className="h-3.5 w-3.5" />} disabled={Boolean(effectiveLockedType)} onClick={() => { setTargetType('agent'); setTargetId(''); setEnvironmentTouched(false); setError(null) }} />
                          <CompactChoice selected={targetType === 'network'} title="Network" description="Creates one Network Run composed of Agent Runs." icon={<Network className="h-3.5 w-3.5" />} disabled={Boolean(effectiveLockedType)} onClick={() => { setTargetType('network'); setTargetId(''); setEnvironmentTouched(false); setError(null) }} />
                        </div>
                      </section>
                    ) : null}

                    {!contextualRuntime ? (
                      <section>
                        <SectionHeader title={targetTypeLabel(targetType)} description={`Choose which ${targetTypeLabel(targetType)} deployment this credential can execute.`} />
                        <div className="mt-3">
                          <TargetList targetType={targetType} agents={agents} networks={networks} selectedTargetId={targetId} loading={targetsLoading} locked={targetLocked} onSelect={(nextTargetId) => { setTargetId(nextTargetId); setEnvironmentTouched(false); setError(null) }} />
                        </div>
                      </section>
                    ) : null}
                  </>
                ) : (
                  <section>
                    <SectionHeader title="Permissions" description="Choose which Project operations this key can access." />
                    <div className="mt-3 divide-y divide-border border border-border bg-background/25">
                      {PROJECT_PERMISSIONS.map((item) => {
                        const selected = permissions.includes(item.value)
                        return (
                          <button key={item.value} type="button" onClick={() => togglePermission(item.value)} className={`flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors ${selected ? 'bg-primary/[0.08]' : 'hover:bg-control/35'}`}>
                            <Activity className="h-3.5 w-3.5 text-primary-light" />
                            <span className="min-w-0 flex-1"><span className="block font-mono text-[9px] font-medium text-slate-100">{item.label}</span><span className="mt-0.5 block font-sans text-[9px] text-muted-foreground">{item.description}</span></span>
                            <span className={`flex h-4 w-4 items-center justify-center rounded-full border ${selected ? 'border-primary bg-primary text-white' : 'border-border'}`}>{selected ? <Check className="h-2.5 w-2.5" /> : null}</span>
                          </button>
                        )
                      })}
                    </div>
                  </section>
                )}
              </div>

              <div className="space-y-4 lg:border-l lg:border-border lg:pl-5">
                {kind === 'runtime' ? (
                  <>
                    {!contextualRuntime ? (
                      <section className="border-b border-border pb-4">
                        <SectionHeader title="Environment" description="Bind this key to one deployable environment." />
                        <div className="mt-3 grid grid-cols-2 gap-2">
                          {(['staging', 'production'] as RuntimeEnvironment[]).map((item) => (
                            <button key={item} type="button" onClick={() => { setEnvironment(item); setEnvironmentTouched(true); setError(null) }} className={`h-[34px] rounded-control border font-mono text-[9px] font-medium ${environment === item ? 'border-primary/40 bg-primary/[0.10] text-primary-light' : 'border-border bg-control/25 text-muted-foreground hover:bg-control/45'}`}>
                              {environmentLabel(item)}
                            </button>
                          ))}
                        </div>
                        <div className="mt-2.5 border border-border bg-control/20 px-3 py-2.5">
                          <p className="font-mono text-[8px] font-semibold uppercase tracking-[0.11em] text-muted-foreground">Current deployment</p>
                          {!targetId
                            ? <p className="mt-1 font-sans text-[9px] text-muted-foreground">Select a target to inspect this environment.</p>
                            : releasesLoading && targetType === 'agent'
                              ? <p className="mt-1 font-sans text-[9px] text-muted-foreground">Checking current deployment…</p>
                              : deploymentAvailable
                                ? <p className="mt-1 font-mono text-[9px] text-slate-100">{environmentLabel(environment)} · Available</p>
                                : <p className="mt-1 font-sans text-[9px] leading-4 text-muted-foreground">{environmentLabel(environment)} · Not deployed. Deploy a release to enable Runtime requests.</p>}
                        </div>
                      </section>
                    ) : null}
                    <RuntimeInterfaces interfaces={interfaces} onToggle={toggleInterface} />
                  </>
                ) : null}

                <section className="border-b border-border pb-4">
                  <ApiKeyExpirationField value={expiration} onChange={(nextValue) => { setExpiration(nextValue); setExpirationError(null) }} error={expirationError} />
                </section>

                <section>
                  <SectionHeader title="Key contract" description="Review exactly what this credential will be allowed to do." />
                  <div className="mt-3 flex items-start gap-2.5 border border-primary/25 bg-primary/[0.05] px-3 py-2.5">
                    <KeyRound className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary-light" />
                    <div className="min-w-0">
                      <p className="font-mono text-[9px] font-medium text-slate-100">{summary}</p>
                      <p className="mt-1 font-sans text-[9px] leading-4 text-muted-foreground">{kind === 'runtime' ? `Target type: ${targetType}. Deploys and rollbacks keep the same key.` : 'Project Keys cannot execute Agents or Networks.'}</p>
                    </div>
                  </div>
                </section>
              </div>
            </div>
          </div>

          <div className="flex min-h-[58px] shrink-0 items-center gap-4 border-t border-border bg-surface/[0.98] px-5 py-3">
            <div className="min-w-0 flex-1">{error ? <p className="font-mono text-[9px] text-red-300">{error}</p> : <p className="truncate font-mono text-[8px] text-muted-foreground">{summary}</p>}</div>
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
