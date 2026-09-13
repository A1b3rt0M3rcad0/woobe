import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, Bot, Check, KeyRound, Network, Search, ShieldCheck, Zap } from 'lucide-react'
import { toast } from 'sonner'
import {
  Alert,
  AlertDescription,
  Badge,
  Button,
  Dialog,
  EmptyStatePanel,
  Field,
  FieldDescription,
  FieldLabel,
  Input,
  SectionBlock,
  SegmentedControl,
  Skeleton,
  TechnicalListItem,
  Textarea,
} from '@woobe/ui'

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
    return (
      <div className="grid gap-ui-xs">
        <Skeleton className="h-control-row w-full" />
        <Skeleton className="h-control-row w-full" />
        <Skeleton className="h-control-row w-full" />
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <EmptyStatePanel
        compact
        title={`No ${targetTypeLabel(targetType)}s available`}
        description={`Create a ${targetTypeLabel(targetType)} before creating this Runtime Key.`}
      />
    )
  }

  return (
    <div className="grid gap-ui-sm">
      {!locked && items.length > 5 ? (
        <div className="relative">
          <Search className="pointer-events-none absolute left-ui-md top-1/2 h-icon w-icon -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={`Search ${targetTypeLabel(targetType)}s`}
            className="pl-9"
          />
        </div>
      ) : null}

      <div className="scrollbar-thin grid max-h-72 gap-ui-xs overflow-y-auto pr-ui-xs">
        {visibleItems.map((item) => {
          const selected = item.id === selectedTargetId
          return (
            <TechnicalListItem
              key={item.id}
              label={item.name}
              description={item.description}
              selected={selected}
              disabled={locked}
              trailing={selected ? <Check className="h-icon w-icon text-primary-light" /> : null}
              onClick={() => onSelect(item.id)}
            />
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
    <SectionBlock
      title="Allowed interfaces"
      description="Choose how this Runtime Key can invoke the deployment."
      density="compact"
      actions={<Badge variant="outline" size="compact">Jobs · coming soon</Badge>}
    >
      <div className="grid gap-ui-xs sm:grid-cols-2">
        {AVAILABLE_RUNTIME_INTERFACES.map((item) => {
          const selected = interfaces.includes(item.value)
          return (
            <TechnicalListItem
              key={item.value}
              label={item.label}
              description={item.description}
              selected={selected}
              trailing={selected ? <Check className="h-icon w-icon text-primary-light" /> : null}
              onClick={() => onToggle(item.value)}
            />
          )
        })}
      </div>
    </SectionBlock>
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

  const summary = kind === 'runtime'
    ? `${selectedTargetName || `Select ${targetTypeLabel(targetType)}`} · ${environmentLabel(environment)} · ${interfaces.length ? interfaces.map((item) => item.toUpperCase()).join(' + ') : 'No interfaces'}`
    : `Project operations · ${permissions.length ? permissions.join(' + ') : 'No permissions'}`

  const identitySection = (
    <SectionBlock
      title="Key identity"
      description="Name the integration and document its purpose."
      density="compact"
      actions={!contextualRuntime ? <Badge variant="default" size="compact">{kind === 'runtime' ? 'Runtime Key' : 'Project Key'}</Badge> : undefined}
    >
      <div className="grid gap-ui-md">
        <Field>
          <FieldLabel>Name</FieldLabel>
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
        </Field>
        <Field>
          <div className="flex items-center justify-between gap-ui-sm">
            <FieldLabel>Description <span className="font-normal text-muted-foreground">Optional</span></FieldLabel>
            <span className="font-mono text-system-meta text-muted-foreground">{description.length}/500</span>
          </div>
          <Textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Which service or integration uses this key?"
            maxLength={500}
            rows={contextualRuntime ? 3 : 2}
          />
        </Field>
      </div>
    </SectionBlock>
  )

  return (
    <Dialog
      open={open}
      onClose={close}
      title={title}
      className={createdKey ? 'max-w-dialog' : 'flex max-h-dialog max-w-dialog-wide flex-col overflow-hidden'}
      contentClassName={createdKey ? undefined : 'min-h-0 flex-1 p-0'}
      layer={layer}
    >
      {createdKey ? (
        <div>
          <ApiKeySecretReveal apiKey={createdKey} targetName={selectedTargetName} />
          <div className="mt-ui-lg flex justify-end border-t border-border pt-ui-md">
            <Button onClick={close}>Done</Button>
          </div>
        </div>
      ) : (
        <form className="flex h-full min-h-0 flex-col" onSubmit={handleSubmit}>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-ui-lg">
            <div className="grid gap-ui-md">
              {contextualRuntime ? (
                <TechnicalListItem
                  label={selectedTargetName ?? `Loading ${targetTypeLabel(targetType)}…`}
                  description={`${targetTypeLabel(targetType)} · ${environmentLabel(environment)} · Runtime Key`}
                  leading={(
                    <span className="flex h-control-nav w-control-nav items-center justify-center rounded-control border border-border bg-control text-primary-light">
                      <TargetIcon className="h-icon w-icon" />
                    </span>
                  )}
                  trailing={(
                    <Badge variant={deploymentAvailable ? 'success' : 'outline'} size="compact">
                      {targetsLoading || (targetType === 'agent' && releasesLoading)
                        ? 'Checking deployment'
                        : deploymentAvailable
                          ? 'Deployment available'
                          : 'Not deployed'}
                    </Badge>
                  )}
                />
              ) : null}

              {!kindLocked ? (
                <SectionBlock
                  title="Key type"
                  description="Choose whether this credential executes Runtime or reads Project operations."
                  density="compact"
                >
                  <SegmentedControl
                    items={[
                      { value: 'runtime', label: 'Runtime Key', icon: <Zap className="h-icon-sm w-icon-sm" /> },
                      { value: 'project', label: 'Project Key', icon: <ShieldCheck className="h-icon-sm w-icon-sm" /> },
                    ]}
                    value={kind}
                    onValueChange={(value) => {
                      setKind(value as ApiKeyKind)
                      setError(null)
                    }}
                    ariaLabel="API key type"
                    stretch
                  />
                  <FieldDescription className="mt-ui-sm">
                    {kind === 'runtime' ? 'Execute one Agent or Network deployment.' : 'Read operational Project APIs.'}
                  </FieldDescription>
                </SectionBlock>
              ) : null}

              <div className="grid gap-ui-md lg:grid-cols-2">
                <div className="grid content-start gap-ui-md">
                  {identitySection}

                  {kind === 'runtime' && !contextualRuntime ? (
                    <SectionBlock
                      title="Runtime target"
                      description="A Runtime Key executes exactly one target in one environment."
                      density="compact"
                    >
                      <SegmentedControl
                        items={[
                          { value: 'agent', label: 'Agent', icon: <Bot className="h-icon-sm w-icon-sm" />, disabled: Boolean(effectiveLockedType) },
                          { value: 'network', label: 'Network', icon: <Network className="h-icon-sm w-icon-sm" />, disabled: Boolean(effectiveLockedType) },
                        ]}
                        value={targetType}
                        onValueChange={(value) => {
                          setTargetType(value as RuntimeTargetType)
                          setTargetId('')
                          setEnvironmentTouched(false)
                          setError(null)
                        }}
                        ariaLabel="Runtime target type"
                        stretch
                      />
                      <FieldDescription className="mt-ui-sm">
                        {targetType === 'agent' ? 'Creates one Agent Run per request.' : 'Creates one Network Run composed of Agent Runs.'}
                      </FieldDescription>
                    </SectionBlock>
                  ) : null}

                  {kind === 'runtime' && !contextualRuntime ? (
                    <SectionBlock
                      title={targetTypeLabel(targetType)}
                      description={`Choose which ${targetTypeLabel(targetType)} deployment this credential can execute.`}
                      density="compact"
                    >
                      <TargetList
                        targetType={targetType}
                        agents={agents}
                        networks={networks}
                        selectedTargetId={targetId}
                        loading={targetsLoading}
                        locked={targetLocked}
                        onSelect={(nextTargetId) => {
                          setTargetId(nextTargetId)
                          setEnvironmentTouched(false)
                          setError(null)
                        }}
                      />
                    </SectionBlock>
                  ) : null}

                  {kind === 'project' ? (
                    <SectionBlock
                      title="Permissions"
                      description="Choose which Project operations this key can access."
                      density="compact"
                    >
                      <div className="grid gap-ui-xs">
                        {PROJECT_PERMISSIONS.map((item) => {
                          const selected = permissions.includes(item.value)
                          return (
                            <TechnicalListItem
                              key={item.value}
                              label={item.label}
                              description={item.description}
                              leading={<Activity className="h-icon w-icon text-primary-light" />}
                              selected={selected}
                              trailing={selected ? <Check className="h-icon w-icon text-primary-light" /> : null}
                              onClick={() => togglePermission(item.value)}
                            />
                          )
                        })}
                      </div>
                    </SectionBlock>
                  ) : null}
                </div>

                <div className="grid content-start gap-ui-md lg:border-l lg:border-border lg:pl-ui-md">
                  {kind === 'runtime' && !contextualRuntime ? (
                    <SectionBlock
                      title="Environment"
                      description="Bind this key to one deployable environment."
                      density="compact"
                    >
                      <SegmentedControl
                        items={[
                          { value: 'staging', label: 'Staging' },
                          { value: 'production', label: 'Production' },
                        ]}
                        value={environment}
                        onValueChange={(value) => {
                          setEnvironment(value as RuntimeEnvironment)
                          setEnvironmentTouched(true)
                          setError(null)
                        }}
                        ariaLabel="Runtime environment"
                        stretch
                      />

                      <TechnicalListItem
                        className="mt-ui-md"
                        label="Current deployment"
                        description={!targetId
                          ? 'Select a target to inspect this environment.'
                          : releasesLoading && targetType === 'agent'
                            ? 'Checking current deployment…'
                            : deploymentAvailable
                              ? `${environmentLabel(environment)} · Available`
                              : `${environmentLabel(environment)} · Not deployed. Deploy a release to enable Runtime requests.`}
                        trailing={targetId && !(releasesLoading && targetType === 'agent') ? (
                          <Badge variant={deploymentAvailable ? 'success' : 'warning'} size="compact">
                            {deploymentAvailable ? 'Available' : 'Unavailable'}
                          </Badge>
                        ) : undefined}
                      />
                    </SectionBlock>
                  ) : null}

                  {kind === 'runtime' ? <RuntimeInterfaces interfaces={interfaces} onToggle={toggleInterface} /> : null}

                  <SectionBlock title="Expiration" description="Limit how long this credential remains valid." density="compact">
                    <ApiKeyExpirationField
                      value={expiration}
                      onChange={(nextValue) => {
                        setExpiration(nextValue)
                        setExpirationError(null)
                      }}
                      error={expirationError}
                    />
                  </SectionBlock>

                  <SectionBlock
                    title="Key contract"
                    description="Review exactly what this credential will be allowed to do."
                    density="compact"
                  >
                    <Alert variant="info">
                      <KeyRound className="h-icon w-icon" />
                      <AlertDescription>
                        <span className="block font-mono text-system-control text-accent-foreground">{summary}</span>
                        <span className="mt-ui-xs block">
                          {kind === 'runtime'
                            ? `Target type: ${targetType}. Deploys and rollbacks keep the same key.`
                            : 'Project Keys cannot execute Agents or Networks.'}
                        </span>
                      </AlertDescription>
                    </Alert>
                  </SectionBlock>
                </div>
              </div>
            </div>
          </div>

          <div className="flex shrink-0 flex-col-reverse gap-ui-sm border-t border-border bg-surface/95 px-ui-lg py-ui-md sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0 flex-1">
              {error ? (
                <p className="font-mono text-system-label text-error">{error}</p>
              ) : (
                <p className="truncate font-mono text-system-meta text-muted-foreground">{summary}</p>
              )}
            </div>
            <div className="flex shrink-0 gap-ui-sm">
              <Button type="button" variant="outline" onClick={close}>Cancel</Button>
              <Button type="submit" loading={isPending}>Create {kind === 'runtime' ? 'Runtime' : 'Project'} Key</Button>
            </div>
          </div>
        </form>
      )}
    </Dialog>
  )
}
