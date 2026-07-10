import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Activity, Bot, Check, KeyRound, Search, ShieldCheck, Zap } from 'lucide-react'
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
  lockedEnvironment?: RuntimeEnvironment
  layer?: DialogLayer
  onCreated?: (apiKey: CreateApiKeyResponse) => void
}

const AGENT_SEARCH_THRESHOLD = 5

const PROJECT_PERMISSIONS: Array<{ value: ApiKeyScope; label: string; description: string }> = [
  { value: 'traces:read', label: 'Traces', description: 'Read execution traces across this Project.' },
  { value: 'usage:read', label: 'Usage & cost', description: 'Read metering, usage and cost data.' },
]

const RUNTIME_INTERFACES: Array<{ value: RuntimeInterface; label: string; description: string }> = [
  { value: 'http', label: 'HTTP', description: 'Synchronous execution through POST /v1/run.' },
  { value: 'stream', label: 'Streaming', description: 'Server-Sent Events through POST /v1/run/stream.' },
  { value: 'jobs', label: 'Jobs', description: 'Asynchronous execution and job polling.' },
]

function environmentLabel(environment: RuntimeEnvironment): string {
  return environment === 'production' ? 'Production' : 'Staging'
}

function defaultRuntimeName(agentName: string, environment: RuntimeEnvironment): string {
  return `${agentName} · ${environmentLabel(environment)}`
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

      <div className="scrollbar-thin max-h-52 space-y-2 overflow-y-auto pr-1">
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
  lockedEnvironment,
  layer = 'modal',
  onCreated,
}: CreateApiKeyDialogProps) {
  const { data: agents = [], isLoading: agentsLoading } = useAgents(projectId)
  const createProjectKey = useCreateApiKey(projectId)
  const createRuntimeKey = useCreateRuntimeApiKey(projectId)
  const [kind, setKind] = useState<ApiKeyKind>(initialKind ?? 'runtime')
  const [name, setName] = useState('')
  const [agentId, setAgentId] = useState(lockedAgentId ?? '')
  const [environment, setEnvironment] = useState<RuntimeEnvironment>(lockedEnvironment ?? 'production')
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
  const environmentLocked = Boolean(lockedEnvironment)
  const isPending = createProjectKey.isPending || createRuntimeKey.isPending

  useEffect(() => {
    if (!open) return
    const nextKind = initialKind ?? 'runtime'
    const nextEnvironment = lockedEnvironment ?? 'production'
    setKind(nextKind)
    setAgentId(lockedAgentId ?? '')
    setEnvironment(nextEnvironment)
    setInterfaces(['http', 'stream', 'jobs'])
    setPermissions(['traces:read', 'usage:read'])
    setExpiration(DEFAULT_API_KEY_EXPIRATION)
    setError(null)
    setExpirationError(null)
    setCreatedKey(null)
    setName('')
  }, [open, initialKind, lockedAgentId, lockedEnvironment])

  useEffect(() => {
    if (!open || kind !== 'runtime' || !selectedAgent || name) return
    if (agentLocked || environmentLocked) {
      setName(defaultRuntimeName(selectedAgent.name, environment))
    }
  }, [open, kind, selectedAgent, name, agentLocked, environmentLocked, environment])

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

    const trimmedName = name.trim()
    if (!trimmedName) {
      setError('Name is required')
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
        if (!agentId) {
          setError('Select an Agent')
          return
        }
        if (interfaces.length === 0) {
          setError('Select at least one runtime interface')
          return
        }
        result = await createRuntimeKey.mutateAsync({
          name: trimmedName,
          agent_id: agentId,
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
          name: trimmedName,
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

  return (
    <Dialog open={open} onClose={close} title={title} className="max-w-[720px]" layer={layer}>
      {createdKey ? (
        <div>
          <ApiKeySecretReveal apiKey={createdKey} agentName={selectedAgent?.name} />
          <div className="mt-5 flex justify-end border-t border-border/80 pt-4">
            <Button onClick={close}>Done</Button>
          </div>
        </div>
      ) : (
        <form className="space-y-6" onSubmit={handleSubmit}>
          {!kindLocked && (
            <section>
              <p className="text-xs font-medium text-muted">What will this key be used for?</p>
              <div className="mt-2 grid items-stretch gap-3 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => { setKind('runtime'); setError(null) }}
                  className={`flex min-h-[118px] flex-col rounded-xl border p-4 text-left transition-colors ${kind === 'runtime' ? 'border-primary/40 bg-primary/10' : 'border-border/80 bg-background/45 hover:border-primary/25'}`}
                >
                  <div className="flex items-center gap-2.5">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary-light">
                      <Zap className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-white">Runtime Key</p>
                      <p className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.12em] text-primary-light">Agent + Environment</p>
                    </div>
                  </div>
                  <p className="mt-auto pt-3 text-xs leading-5 text-muted">Execute a deployed Agent from your application through HTTP, Streaming or Jobs.</p>
                </button>

                <button
                  type="button"
                  onClick={() => { setKind('project'); setError(null) }}
                  className={`flex min-h-[118px] flex-col rounded-xl border p-4 text-left transition-colors ${kind === 'project' ? 'border-primary/40 bg-primary/10' : 'border-border/80 bg-background/45 hover:border-primary/25'}`}
                >
                  <div className="flex items-center gap-2.5">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background text-primary-light">
                      <ShieldCheck className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-white">Project Key</p>
                      <p className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.12em] text-muted">Project operations</p>
                    </div>
                  </div>
                  <p className="mt-auto pt-3 text-xs leading-5 text-muted">Read operational data across the Project, such as traces, usage and cost.</p>
                </button>
              </div>
            </section>
          )}

          <section>
            <label className="mb-2 block text-xs font-medium text-muted" htmlFor="api-key-name">Name</label>
            <Input
              id="api-key-name"
              value={name}
              onChange={(event) => { setName(event.target.value); setError(null) }}
              placeholder={kind === 'runtime' ? 'Customer support production' : 'Analytics backend'}
            />
          </section>

          {kind === 'runtime' ? (
            <>
              <section>
                <p className="mb-2 text-xs font-medium text-muted">Agent</p>
                <AgentSelectionList
                  agents={agents}
                  selectedAgentId={agentId}
                  loading={agentsLoading}
                  locked={agentLocked}
                  onSelect={(nextAgentId) => {
                    setAgentId(nextAgentId)
                    setName('')
                    setError(null)
                  }}
                />
              </section>

              <section>
                <p className="mb-2 text-xs font-medium text-muted">Environment</p>
                <div className="grid grid-cols-2 gap-2">
                  {(['staging', 'production'] as RuntimeEnvironment[]).map((item) => (
                    <button
                      key={item}
                      type="button"
                      disabled={environmentLocked}
                      onClick={() => { setEnvironment(item); setName(''); setError(null) }}
                      className={`h-10 rounded-lg border text-xs font-medium transition-colors ${environment === item ? 'border-primary/40 bg-primary/10 text-primary-light' : 'border-border bg-background/45 text-muted hover:text-white'} disabled:cursor-not-allowed`}
                    >
                      {environmentLabel(item)}
                    </button>
                  ))}
                </div>
              </section>

              {selectedAgent && (
                <div className={`rounded-xl border p-4 ${releasesLoading || currentRelease ? 'border-border/80 bg-background/45' : 'border-yellow-500/25 bg-yellow-500/5'}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-3">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background text-primary-light">
                        <Bot className="h-4 w-4" />
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-white">{selectedAgent.name}</p>
                        <p className="mt-0.5 truncate text-[11px] text-muted">{selectedAgent.provider}/{selectedAgent.model}</p>
                      </div>
                    </div>
                    <span className="rounded-full border border-border/80 bg-background/60 px-2.5 py-1 text-[10px] capitalize text-muted">{environment}</span>
                  </div>
                  <div className="mt-3 border-t border-border/70 pt-3">
                    {releasesLoading ? (
                      <p className="text-xs text-muted">Checking current deployment…</p>
                    ) : currentRelease ? (
                      <p className="text-xs text-muted">Current {environmentLabel(environment)} release · <span className="font-medium text-white">{currentRelease.version}</span></p>
                    ) : (
                      <p className="text-xs leading-5 text-yellow-200">No {environmentLabel(environment)} release is deployed. The key can be created now, but requests will return 409 until a release is deployed.</p>
                    )}
                  </div>
                </div>
              )}

              <section>
                <p className="text-xs font-medium text-muted">Allowed interfaces</p>
                <div className="mt-2 grid auto-rows-fr gap-2 sm:grid-cols-3">
                  {RUNTIME_INTERFACES.map((item) => {
                    const selected = interfaces.includes(item.value)
                    return (
                      <button
                        key={item.value}
                        type="button"
                        onClick={() => toggleInterface(item.value)}
                        className={`min-h-[88px] rounded-xl border p-3 text-left transition-colors ${selected ? 'border-primary/35 bg-primary/10' : 'border-border/80 bg-background/45 hover:border-primary/25'}`}
                      >
                        <p className="text-sm font-medium text-white">{item.label}</p>
                        <p className="mt-1 text-[11px] leading-4 text-muted">{item.description}</p>
                      </button>
                    )
                  })}
                </div>
              </section>
            </>
          ) : (
            <section>
              <p className="text-xs font-medium text-muted">Permissions</p>
              <div className="mt-2 grid auto-rows-fr gap-2 sm:grid-cols-2">
                {PROJECT_PERMISSIONS.map((item) => {
                  const selected = permissions.includes(item.value)
                  return (
                    <button
                      key={item.value}
                      type="button"
                      onClick={() => togglePermission(item.value)}
                      className={`min-h-[104px] rounded-xl border p-4 text-left transition-colors ${selected ? 'border-primary/35 bg-primary/10' : 'border-border/80 bg-background/45 hover:border-primary/25'}`}
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
          )}

          <ApiKeyExpirationField
            value={expiration}
            onChange={(nextValue) => { setExpiration(nextValue); setExpirationError(null) }}
            error={expirationError}
          />

          <div className="rounded-xl border border-border/80 bg-background/35 px-4 py-3.5">
            <div className="flex items-start gap-3">
              <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-primary-light" />
              <div className="min-w-0">
                {kind === 'runtime' ? (
                  <>
                    <p className="text-xs leading-5 text-white">
                      This key will execute <span className="font-medium">{selectedAgent?.name || 'the selected Agent'}</span> in <span className="font-medium">{environmentLabel(environment)}</span> through {interfaces.length ? interfaces.join(', ') : 'no interfaces'}.
                    </p>
                    <p className="mt-1 text-[11px] leading-5 text-muted">It always resolves the current {environmentLabel(environment)} release. Deploys and rollbacks do not require changing the key.</p>
                    <code className="mt-2 block text-[10px] text-primary-light">woobe_{environment}_...</code>
                  </>
                ) : (
                  <>
                    <p className="text-xs leading-5 text-white">This key can access {permissions.length ? permissions.map((scope) => scope === 'traces:read' ? 'traces' : 'usage and cost data').join(' and ') : 'no Project APIs'}.</p>
                    <p className="mt-1 text-[11px] leading-5 text-muted">It cannot execute Agents. New runtime integrations should use a Runtime Key.</p>
                    <code className="mt-2 block text-[10px] text-primary-light">woobe_project_...</code>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="flex min-h-10 items-center justify-between gap-4 border-t border-border/80 pt-4">
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
