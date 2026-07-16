import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Activity, Check, KeyRound, Search, ShieldCheck, Zap } from 'lucide-react'
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
} from '@/features/api-keys/types'
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
  lockedAgentId?: string
  initialEnvironment?: RuntimeEnvironment
  layer?: DialogLayer
  onCreated?: (apiKey: CreateApiKeyResponse) => void
}

const AGENT_SEARCH_THRESHOLD = 5

const PROJECT_PERMISSIONS: Array<{ value: ApiKeyScope; label: string; description: string }> = [
  { value: 'traces:read', label: 'Traces', description: 'Read execution traces across this Project.' },
  { value: 'usage:read', label: 'Usage & cost', description: 'Read metering, usage and cost data.' },
]

const RUNTIME_INTERFACES: Array<{ value: RuntimeInterface; label: string; description: string }> = [
  { value: 'http', label: 'HTTP', description: 'Sync requests' },
  { value: 'stream', label: 'Streaming', description: 'Server-Sent Events' },
  { value: 'jobs', label: 'Jobs', description: 'Async execution' },
]

function environmentLabel(environment: RuntimeEnvironment): string {
  return environment === 'production' ? 'Production' : 'Staging'
}

function AgentSelectionList({
  agents,
  selectedAgentId,
  loading,
  locked,
  onSelect,
}: {
  agents: Agent[]
  selectedAgentId: string
  loading: boolean
  locked: boolean
  onSelect: (agentId: string) => void
}) {
  const [query, setQuery] = useState('')
  const candidates = useMemo(
    () => locked && selectedAgentId
      ? agents.filter((agent) => agent.id === selectedAgentId)
      : agents,
    [agents, locked, selectedAgentId],
  )
  const visibleAgents = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return candidates
    return candidates.filter((agent) => (
      `${agent.name} ${agent.provider} ${agent.model}`.toLowerCase().includes(normalized)
    ))
  }, [candidates, query])
  const showSearch = !locked && agents.length > AGENT_SEARCH_THRESHOLD

  if (loading) {
    return (
      <div className="rounded-xl border border-border/80 bg-background/55 px-4 py-6 text-center text-sm text-muted">
        Loading Agents...
      </div>
    )
  }

  if (agents.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border/80 bg-background/35 px-4 py-6 text-center">
        <p className="text-sm font-medium text-white">No Agents available</p>
        <p className="mt-1 text-xs leading-5 text-muted">Create an Agent before creating a Runtime Key.</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {showSearch && (
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search Agents"
            className="pl-9"
          />
        </div>
      )}

      <div className="scrollbar-thin max-h-[240px] space-y-2 overflow-y-auto pr-1">
        {visibleAgents.length === 0 ? (
          <div className="rounded-xl border border-border/80 bg-background/55 px-4 py-6 text-center text-sm text-muted">
            No Agents found.
          </div>
        ) : visibleAgents.map((agent) => {
          const selected = agent.id === selectedAgentId
          return (
            <button
              key={agent.id}
              type="button"
              aria-pressed={selected}
              aria-disabled={locked}
              onClick={() => { if (!locked) onSelect(agent.id) }}
              className={`flex w-full items-start justify-between gap-4 rounded-xl border px-4 py-3 text-left transition-colors ${
                selected
                  ? 'border-primary/55 bg-primary/8'
                  : 'border-border/85 bg-background/55 hover:border-primary/30 hover:bg-background/80'
              } ${locked ? 'cursor-default' : ''}`}
            >
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-white">{agent.name}</span>
                <span className="mt-1 block truncate text-xs text-muted">{agent.provider} · {agent.model}</span>
              </span>
              <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${
                selected ? 'border-primary bg-primary text-white' : 'border-border bg-background'
              }`}>
                {selected && <Check className="h-3 w-3" />}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function CreateApiKeyDialog({
  open,
  onClose,
  projectId,
  initialKind,
  lockedAgentId,
  initialEnvironment,
  layer = 'modal',
  onCreated,
}: CreateApiKeyDialogProps) {
  const { data: agents = [], isLoading: agentsLoading } = useAgents(projectId)
  const createProjectKey = useCreateApiKey(projectId)
  const createRuntimeKey = useCreateRuntimeApiKey(projectId)
  const [kind, setKind] = useState<ApiKeyKind>(initialKind ?? 'runtime')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [agentId, setAgentId] = useState(lockedAgentId ?? '')
  const [environment, setEnvironment] = useState<RuntimeEnvironment>(initialEnvironment ?? 'production')
  const [environmentTouched, setEnvironmentTouched] = useState(false)
  const [interfaces, setInterfaces] = useState<RuntimeInterface[]>(['http', 'stream', 'jobs'])
  const [permissions, setPermissions] = useState<ApiKeyScope[]>(['traces:read', 'usage:read'])
  const [expiration, setExpiration] = useState<ApiKeyExpirationValue>(DEFAULT_API_KEY_EXPIRATION)
  const [error, setError] = useState<string | null>(null)
  const [expirationError, setExpirationError] = useState<string | null>(null)
  const [createdKey, setCreatedKey] = useState<CreateApiKeyResponse | null>(null)

  const selectedAgent = agents.find((agent) => agent.id === agentId) ?? null
  const { data: releases = [], isLoading: releasesLoading } = useReleases(kind === 'runtime' && agentId ? agentId : undefined)
  const currentRelease = useMemo(
    () => releases.find((release) => release.status === environment) ?? null,
    [releases, environment],
  )
  const kindLocked = initialKind !== undefined
  const agentLocked = Boolean(lockedAgentId)
  const isPending = createProjectKey.isPending || createRuntimeKey.isPending
  const visibleKeyTypes: ApiKeyKind[] = kindLocked ? [kind] : ['runtime', 'project']

  useEffect(() => {
    if (!open) return
    const nextKind = initialKind ?? 'runtime'
    const nextEnvironment = initialEnvironment ?? 'production'
    setKind(nextKind)
    setName('')
    setDescription('')
    setAgentId(lockedAgentId ?? '')
    setEnvironment(nextEnvironment)
    setEnvironmentTouched(false)
    setInterfaces(['http', 'stream', 'jobs'])
    setPermissions(['traces:read', 'usage:read'])
    setExpiration(DEFAULT_API_KEY_EXPIRATION)
    setError(null)
    setExpirationError(null)
    setCreatedKey(null)
  }, [open, initialKind, lockedAgentId, initialEnvironment])

  useEffect(() => {
    if (!open || kind !== 'runtime' || !selectedAgent || releasesLoading || environmentTouched) return
    if (releases.some((release) => release.status === environment)) return
    if (releases.some((release) => release.status === 'staging')) {
      setEnvironment('staging')
    } else if (releases.some((release) => release.status === 'production')) {
      setEnvironment('production')
    }
  }, [open, kind, selectedAgent, releases, releasesLoading, environment, environmentTouched])

  const close = () => {
    setCreatedKey(null)
    setError(null)
    setExpirationError(null)
    onClose()
  }

  const togglePermission = (scope: ApiKeyScope) => {
    setPermissions((current) => (
      current.includes(scope)
        ? current.filter((item) => item !== scope)
        : [...current, scope]
    ))
    setError(null)
  }

  const toggleInterface = (runtimeInterface: RuntimeInterface) => {
    setInterfaces((current) => (
      current.includes(runtimeInterface)
        ? current.filter((item) => item !== runtimeInterface)
        : [...current, runtimeInterface]
    ))
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
        if (!selectedAgent) {
          setError('Select an Agent')
          return
        }
        if (interfaces.length === 0) {
          setError('Select at least one runtime interface')
          return
        }
        result = await createRuntimeKey.mutateAsync({
          name: normalizedName,
          description: description.trim() || null,
          agent_id: selectedAgent.id,
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
    : 'Create API Key'

  const identitySection = (
    <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-white">Key identity</h3>
          <p className="mt-1 text-xs leading-5 text-muted">Name the integration and document its purpose.</p>
        </div>
        <span className="shrink-0 rounded-full border border-primary/25 bg-primary/10 px-2.5 py-1 text-[10px] font-medium text-primary-light">
          {kind === 'runtime' ? 'Runtime Key' : 'Project Key'}
        </span>
      </div>
      <div className="mt-4 grid gap-3">
        <label className="grid gap-1.5 text-xs font-medium text-muted">
          Name
          <Input
            value={name}
            onChange={(event) => { setName(event.target.value); setError(null) }}
            placeholder={kind === 'runtime' ? 'Checkout backend' : 'Operations dashboard'}
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
            rows={2}
            className="w-full resize-none rounded-lg border border-border/80 bg-background/70 px-3 py-2.5 text-sm text-white outline-none transition-colors placeholder:text-muted/60 focus:border-primary/40"
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
      className={createdKey ? 'max-w-2xl' : 'max-h-[calc(100svh-2rem)] max-w-[1120px] overflow-hidden'}
      layer={layer}
    >
      {createdKey ? (
        <div>
          <ApiKeySecretReveal apiKey={createdKey} agentName={selectedAgent?.name} />
          <div className="mt-5 flex justify-end border-t border-border/80 pt-4">
            <Button onClick={close}>Done</Button>
          </div>
        </div>
      ) : (
        <form className="flex max-h-[calc(100svh-10rem)] min-h-0 flex-col" onSubmit={handleSubmit}>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto pr-1">
            <div className={kindLocked ? '' : 'grid gap-4 lg:grid-cols-[190px_minmax(0,1fr)]'}>
              {!kindLocked && <aside className="space-y-3 lg:sticky lg:top-0 lg:self-start">
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted/75">Key type</p>
                {visibleKeyTypes.map((keyType) => {
                  const runtime = keyType === 'runtime'
                  const selected = kind === keyType
                  const Icon = runtime ? Zap : ShieldCheck
                  return (
                    <button
                      key={keyType}
                      type="button"
                      disabled={kindLocked}
                      onClick={() => { setKind(keyType); setError(null) }}
                      className={`w-full rounded-xl border p-4 text-left transition-colors ${
                        selected
                          ? 'border-primary/45 bg-primary/10'
                          : 'border-border/85 bg-background/50 hover:border-primary/30'
                      } disabled:cursor-default`}
                    >
                      <span className="flex items-center gap-3">
                        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${
                          selected ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-border bg-background text-muted'
                        }`}>
                          <Icon className="h-4 w-4" />
                        </span>
                        <span className="min-w-0">
                          <span className="block text-sm font-semibold text-white">{runtime ? 'Runtime Key' : 'Project Key'}</span>
                          <span className={`mt-0.5 block text-[10px] font-medium uppercase tracking-[0.12em] ${selected ? 'text-primary-light' : 'text-muted'}`}>
                            {runtime ? 'Agent + Environment' : 'Project operations'}
                          </span>
                        </span>
                      </span>
                    </button>
                  )
                })}
                <div className="rounded-xl border border-border/80 bg-background/35 p-4">
                  <p className="text-xs leading-5 text-muted">
                    {kind === 'runtime'
                      ? 'Use a Runtime Key to call one Agent deployment from your application.'
                      : 'Use a Project Key for operational APIs such as traces, usage and cost.'}
                  </p>
                </div>
              </aside>}

              <main className="min-w-0">
                {kind === 'runtime' ? (
                  <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(420px,1fr)]">
                    <div className="space-y-4">
                      {identitySection}
                      <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                      <div className="mb-4">
                        <h3 className="text-sm font-semibold text-white">Agent</h3>
                        <p className="mt-1 text-xs leading-5 text-muted">Choose which Agent deployment this credential can execute.</p>
                      </div>
                      <AgentSelectionList
                        agents={agents}
                        selectedAgentId={agentId}
                        loading={agentsLoading}
                        locked={agentLocked}
                        onSelect={(nextAgentId) => {
                          setAgentId(nextAgentId)
                          setEnvironmentTouched(false)
                          setError(null)
                        }}
                      />
                      </section>
                    </div>

                    <div className="space-y-4">
                      <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                        <p className="text-xs font-medium text-muted">Environment</p>
                        <div className="mt-2 grid grid-cols-2 gap-2">
                          {(['staging', 'production'] as RuntimeEnvironment[]).map((item) => (
                            <button
                              key={item}
                              type="button"
                              onClick={() => { setEnvironment(item); setEnvironmentTouched(true); setError(null) }}
                              className={`h-10 rounded-lg border text-xs font-medium transition-colors ${environment === item ? 'border-primary/40 bg-primary/10 text-primary-light' : 'border-border bg-background/45 text-muted hover:text-white'}`}
                            >
                              {environmentLabel(item)}
                            </button>
                          ))}
                        </div>

                        <div className={`mt-3 rounded-lg border px-3 py-2.5 ${
                          releasesLoading || currentRelease || !selectedAgent
                            ? 'border-border/75 bg-background/45'
                            : 'border-yellow-500/25 bg-yellow-500/5'
                        }`}>
                          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Current deployment</p>
                          {!selectedAgent ? (
                            <p className="mt-1.5 text-xs text-muted">Select an Agent to inspect this environment.</p>
                          ) : releasesLoading ? (
                            <p className="mt-1.5 text-xs text-muted">Checking current deployment…</p>
                          ) : currentRelease ? (
                            <p className="mt-1.5 text-xs text-white">{environmentLabel(environment)} · <span className="font-medium">{currentRelease.version}</span></p>
                          ) : (
                            <p className="mt-1.5 text-xs leading-5 text-yellow-200">{environmentLabel(environment)} · Not deployed. Requests return 409 until deployment.</p>
                          )}
                        </div>
                      </section>

                      <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                        <p className="text-xs font-medium text-muted">Allowed interfaces</p>
                        <div className="mt-2 grid auto-rows-fr grid-cols-3 gap-2">
                          {RUNTIME_INTERFACES.map((item) => {
                            const selected = interfaces.includes(item.value)
                            return (
                              <button
                                key={item.value}
                                type="button"
                                onClick={() => toggleInterface(item.value)}
                                className={`min-h-[64px] rounded-lg border p-2.5 text-left transition-colors ${selected ? 'border-primary/35 bg-primary/10' : 'border-border/80 bg-background/45 hover:border-primary/25'}`}
                              >
                                <p className="text-xs font-medium text-white">{item.label}</p>
                                <p className="mt-1 text-[10px] leading-4 text-muted">{item.description}</p>
                              </button>
                            )
                          })}
                        </div>
                      </section>

                      <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                        <ApiKeyExpirationField
                          value={expiration}
                          onChange={(nextValue) => { setExpiration(nextValue); setExpirationError(null) }}
                          error={expirationError}
                        />
                      </section>
                    </div>
                  </div>
                ) : (
                  <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(420px,1fr)]">
                    <div className="space-y-4">
                      {identitySection}
                      <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                      <div className="mb-4">
                        <h3 className="text-sm font-semibold text-white">Permissions</h3>
                        <p className="mt-1 text-xs leading-5 text-muted">Choose which Project operations this key can access.</p>
                      </div>
                      <div className="grid auto-rows-fr gap-2 sm:grid-cols-2 xl:grid-cols-1">
                        {PROJECT_PERMISSIONS.map((item) => {
                          const selected = permissions.includes(item.value)
                          return (
                            <button
                              key={item.value}
                              type="button"
                              onClick={() => togglePermission(item.value)}
                              className={`min-h-[88px] rounded-xl border p-4 text-left transition-colors ${selected ? 'border-primary/35 bg-primary/10' : 'border-border/80 bg-background/45 hover:border-primary/25'}`}
                            >
                              <div className="flex items-center gap-2">
                                <Activity className={`h-4 w-4 ${selected ? 'text-primary-light' : 'text-muted'}`} />
                                <p className="text-sm font-medium text-white">{item.label}</p>
                              </div>
                              <p className="mt-2 text-xs leading-5 text-muted">{item.description}</p>
                            </button>
                          )
                        })}
                      </div>
                      </section>
                    </div>

                    <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                      <ApiKeyExpirationField
                        value={expiration}
                        onChange={(nextValue) => { setExpiration(nextValue); setExpirationError(null) }}
                        error={expirationError}
                      />
                    </section>
                  </div>
                )}

                <div className="mt-5 rounded-xl border border-border/80 bg-background/35 px-4 py-3">
                  <div className="flex items-start gap-3">
                    <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" />
                    <div className="min-w-0 flex-1 lg:flex lg:items-start lg:justify-between lg:gap-4">
                      {kind === 'runtime' ? (
                        <div>
                          <p className="text-xs leading-5 text-white">
                            <span className="font-medium">{selectedAgent?.name || 'Selected Agent'}</span> · {environmentLabel(environment)} · {interfaces.length ? interfaces.join(', ') : 'No interfaces'}
                          </p>
                          <p className="mt-0.5 text-[11px] leading-5 text-muted">Always resolves the current {environmentLabel(environment)} release. Deploys and rollbacks keep the same key.</p>
                        </div>
                      ) : (
                        <div>
                          <p className="text-xs leading-5 text-white">Project operations · {permissions.length ? permissions.map((scope) => scope === 'traces:read' ? 'Traces' : 'Usage & cost').join(', ') : 'No permissions'}</p>
                          <p className="mt-0.5 text-[11px] leading-5 text-muted">Project Keys cannot execute Agents. Use a Runtime Key for runtime integrations.</p>
                        </div>
                      )}
                      <code className="mt-2 block shrink-0 text-[10px] text-primary-light lg:mt-0">
                        {kind === 'runtime' ? `woobe_${environment}_...` : 'woobe_project_...'}
                      </code>
                    </div>
                  </div>
                </div>
              </main>
            </div>
          </div>

          <div className="mt-5 flex min-h-12 shrink-0 items-center justify-between gap-4 border-t border-border/80 pt-4">
            <div className="min-w-0 flex-1">
              {error && <p className="text-xs text-red-300">{error}</p>}
            </div>
            <div className="flex shrink-0 gap-2">
              <Button type="button" variant="secondary" onClick={close}>Cancel</Button>
              <Button type="submit" loading={isPending} disabled={kind === 'runtime' && agents.length === 0 && !agentsLoading}>
                Create {kind === 'runtime' ? 'Runtime' : 'Project'} Key
              </Button>
            </div>
          </div>
        </form>
      )}
    </Dialog>
  )
}
