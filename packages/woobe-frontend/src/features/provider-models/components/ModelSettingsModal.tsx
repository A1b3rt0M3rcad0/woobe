import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Archive,
  Check,
  Copy,
  Cpu,
  DollarSign,
  Gauge,
  Info,
  KeyRound,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  EmptyStatePanel,
  Field,
  FieldDescription,
  FieldLabel,
  SectionBlock,
  SegmentedControl,
  TechnicalListItem,
} from '@woobe/ui'

import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { ProviderCredentialCreateForm } from '@/features/provider-credentials/components/ProviderCredentialCreateForm'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import {
  useAvailableProviderModels,
  useCreateProviderModel,
  useUpdateProviderModel,
} from '@/features/provider-models/hooks'
import type { AvailableProviderModel, ProviderModel } from '@/features/provider-models/types'
import { get } from '@/lib/api/client'

const SEARCH_THRESHOLD = 6
type CapabilityChoice = 'unknown' | 'true' | 'false'
type ModelSection = 'overview' | 'provider' | 'capabilities' | 'pricing' | 'lifecycle'
type ProviderStep = 'model' | 'credential'

type AgentSummary = {
  id: string
  name: string
  status?: string
  provider_model_id?: string | null
  fallback_provider_model_id?: string | null
}

type ReleaseSummary = {
  id: string
  name?: string | null
  version?: string
  status?: string
  provider_model_id?: string | null
  fallback_provider_model_id?: string | null
}

type UsageItem = {
  type: string
  id: string
  name?: string | null
  status?: string
  version?: string
}

interface ModelSettingsModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  credentials: ProviderCredential[]
  selectedModel: ProviderModel | null
  onSaved: () => void | Promise<void>
}

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  custom: 'OpenAI Compatible',
  openrouter: 'OpenRouter',
}

const capabilityOptions = [
  { value: 'unknown', label: 'Unknown / not declared' },
  { value: 'true', label: 'Supported' },
  { value: 'false', label: 'Not supported' },
]

function providerLabel(provider?: string | null) {
  return provider ? providerLabels[provider] || provider : 'Unknown provider'
}

function metadataOf(item?: { metadata?: Record<string, unknown> | null } | null): Record<string, unknown> {
  return (item?.metadata || {}) as Record<string, unknown>
}

function recordOf(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function isCredentialUsable(credential: ProviderCredential) {
  return (!credential.status || credential.status === 'active') && ['openai', 'custom', 'openrouter'].includes(credential.provider)
}

function supportsCatalog(credential?: ProviderCredential | null) {
  return credential?.provider === 'openai' || credential?.provider === 'openrouter'
}

function numberOrNull(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function positiveIntegerOrNull(value: unknown): number | null {
  const parsed = numberOrNull(value)
  return parsed != null && Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function capabilityChoice(value: unknown): CapabilityChoice {
  if (value === true) return 'true'
  if (value === false) return 'false'
  return 'unknown'
}

function capabilityValue(value: CapabilityChoice): boolean | null {
  if (value === 'true') return true
  if (value === 'false') return false
  return null
}

function capabilitiesOf(model?: ProviderModel | null) {
  const metadata = metadataOf(model)
  const catalog = recordOf(metadata.catalog)
  const capabilities = recordOf(metadata.capabilities)
  const contextWindow = positiveIntegerOrNull(metadata.context_window ?? catalog.context_window)
  const maxOutputTokens = positiveIntegerOrNull(
    metadata.max_output_tokens ?? capabilities.max_output_tokens ?? catalog.max_output_tokens,
  )
  return {
    contextWindow,
    maxOutputTokens,
    supportsTools: capabilityChoice(capabilities.supports_tools),
    supportsJson: capabilityChoice(capabilities.supports_json),
    supportsStreaming: capabilityChoice(capabilities.supports_streaming),
    source: typeof metadata.capability_source === 'string'
      ? metadata.capability_source
      : catalog.context_window != null ? 'provider_catalog' : 'manual',
  }
}

function pricingOf(model?: ProviderModel | null) {
  const metadata = metadataOf(model)
  const raw = typeof metadata.pricing === 'object' && metadata.pricing !== null
    ? metadata.pricing as Record<string, unknown>
    : metadata
  return {
    input: numberOrNull(raw.input_cost_per_1m_tokens),
    output: numberOrNull(raw.output_cost_per_1m_tokens),
    currency: typeof raw.currency === 'string' && raw.currency.trim() ? raw.currency.trim().toUpperCase() : 'USD',
  }
}

function buildModelMetadata(
  selectedModel: ProviderModel | null,
  catalogModel: AvailableProviderModel | null,
  inputCost: string,
  outputCost: string,
  currency: string,
  contextWindow: string,
  maxOutputTokens: string,
  supportsTools: CapabilityChoice,
  supportsJson: CapabilityChoice,
  supportsStreaming: CapabilityChoice,
  capabilitiesChanged: boolean,
) {
  const base = metadataOf(selectedModel)
  const input = inputCost.trim() ? Number(inputCost) : null
  const output = outputCost.trim() ? Number(outputCost) : null
  const context = contextWindow.trim() ? Number(contextWindow) : null
  const maxOutput = maxOutputTokens.trim() ? Number(maxOutputTokens) : null
  const catalog = recordOf(base.catalog)
  const preservedCapabilitySource = typeof base.capability_source === 'string'
    ? base.capability_source
    : catalog.context_window != null ? 'provider_catalog' : 'manual'
  const capabilitySource = catalogModel
    ? 'provider_catalog'
    : selectedModel && !capabilitiesChanged
      ? preservedCapabilitySource
      : 'manual'
  const source = catalogModel
    ? 'remote'
    : selectedModel && typeof base.source === 'string'
      ? base.source
      : 'manual'

  return {
    ...base,
    capability: 'generation',
    source,
    capability_source: capabilitySource,
    context_window: context,
    max_output_tokens: maxOutput,
    catalog: catalogModel ? {
      provider: catalogModel.provider,
      model_id: catalogModel.id,
      label: catalogModel.label,
      owned_by: catalogModel.owned_by ?? null,
      context_window: catalogModel.context_window ?? null,
      max_output_tokens: catalogModel.max_output_tokens ?? null,
    } : base.catalog,
    capabilities: {
      ...recordOf(base.capabilities),
      max_output_tokens: maxOutput,
      supports_tools: capabilityValue(supportsTools),
      supports_json: capabilityValue(supportsJson),
      supports_streaming: capabilityValue(supportsStreaming),
    },
    pricing: {
      input_cost_per_1m_tokens: input,
      output_cost_per_1m_tokens: output,
      currency: (currency || 'USD').trim().toUpperCase(),
      billing_unit: 'per_1m_tokens',
      source: catalogModel ? 'provider_catalog' : 'manual',
    },
    provider_model_raw: catalogModel?.raw ?? base.provider_model_raw,
  }
}

async function loadUsage(projectId: string) {
  const baseAgents = await get<AgentSummary[]>('/ai/agents', { params: { project_id: projectId } })
  const agents = await Promise.all(
    baseAgents.map(async (agent) => get<AgentSummary>(`/ai/agents/${agent.id}`).catch(() => agent)),
  )
  const releaseGroups = await Promise.all(
    agents.map(async (agent) => get<ReleaseSummary[]>(`/ai/agents/${agent.id}/releases`).catch(() => [])),
  )
  return { agents, releases: releaseGroups.flat() }
}

function usageForModel(model: ProviderModel, agents: AgentSummary[], releases: ReleaseSummary[]): UsageItem[] {
  const items: UsageItem[] = []
  for (const agent of agents) {
    if (agent.status === 'archived') continue
    if (agent.provider_model_id === model.id || agent.fallback_provider_model_id === model.id) {
      items.push({ type: 'agent', id: agent.id, name: agent.name, status: agent.status })
    }
  }
  for (const release of releases) {
    if (!['draft', 'staging', 'production'].includes(release.status || '')) continue
    if (release.provider_model_id === model.id || release.fallback_provider_model_id === model.id) {
      items.push({ type: 'release', id: release.id, name: release.name, version: release.version, status: release.status })
    }
  }
  return items
}

function shortId(value: string): string {
  return value.length > 18 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value
}

function ReadOnlyValue({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <Field className="rounded-container border border-border/75 bg-background/25 px-ui-md py-ui-sm">
      <FieldLabel>{label}</FieldLabel>
      <div className={mono ? 'break-words font-mono text-system-control text-accent-foreground' : 'break-words font-sans text-product-body font-medium text-accent-foreground'}>
        {value}
      </div>
    </Field>
  )
}

function CatalogList({
  models,
  selectedId,
  loading,
  error,
  onSelect,
  onRetry,
  onManual,
}: {
  models: AvailableProviderModel[]
  selectedId: string
  loading: boolean
  error: boolean
  onSelect: (model: AvailableProviderModel) => void
  onRetry: () => void
  onManual: () => void
}) {
  const [query, setQuery] = useState('')
  const normalized = query.trim().toLowerCase()
  const filtered = normalized
    ? models.filter((model) => `${model.label} ${model.id} ${model.provider}`.toLowerCase().includes(normalized))
    : models
  const visible = filtered.slice(0, 80)

  if (loading) {
    return (
      <EmptyStatePanel
        compact
        title="Loading generation models"
        description="Reading the generation catalog exposed by this provider connection."
      />
    )
  }

  if (error) {
    return (
      <Alert variant="warning">
        <AlertTitle>Provider catalog unavailable</AlertTitle>
        <AlertDescription>Retry discovery or enter the model ID manually.</AlertDescription>
        <div className="mt-ui-md flex flex-wrap gap-ui-sm">
          <Button type="button" size="sm" variant="outline" onClick={onRetry}>
            <RefreshCw className="mr-2 h-icon w-icon" />Retry
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={onManual}>Enter model ID manually</Button>
        </div>
      </Alert>
    )
  }

  return (
    <div className="grid gap-ui-md">
      <div className="flex flex-wrap items-center justify-between gap-ui-sm">
        <span className="font-sans text-product-caption text-muted-foreground">Choose a generation model from the provider catalog.</span>
        <Button type="button" size="sm" variant="ghost" onClick={onManual}>Enter model ID manually</Button>
      </div>

      {models.length > SEARCH_THRESHOLD ? (
        <div className="relative">
          <Search className="pointer-events-none absolute left-ui-md top-1/2 h-icon w-icon -translate-y-1/2 text-muted-foreground" />
          <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search models" className="pl-9" />
        </div>
      ) : null}

      {visible.length === 0 ? (
        <EmptyStatePanel compact title="No generation models found" description="Change the search or enter the provider model ID manually." />
      ) : (
        <div className="scrollbar-thin grid max-h-72 gap-ui-xs overflow-y-auto pr-ui-xs">
          {visible.map((model) => (
            <TechnicalListItem
              key={model.id}
              label={model.label}
              description={`${providerLabel(model.provider)} · ${model.id}`}
              selected={model.id === selectedId}
              trailing={model.id === selectedId ? <Check className="h-icon w-icon text-primary-light" /> : null}
              onClick={() => onSelect(model)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function ArchiveDialog({
  model,
  usage,
  loading,
  onClose,
  onConfirm,
}: {
  model: ProviderModel | null
  usage: UsageItem[]
  loading: boolean
  onClose: () => void
  onConfirm: () => void
}) {
  if (!model) return null
  const blocked = usage.length > 0

  return (
    <Dialog open onClose={onClose} title="Archive model" className="max-w-dialog" layer="nestedModal">
      <div className="grid gap-ui-lg">
        <Alert variant="warning">
          <div className="flex items-start gap-ui-md">
            <AlertTriangle className="mt-ui-hairline h-icon w-icon shrink-0" />
            <div>
              <AlertTitle>{model.name}</AlertTitle>
              <AlertDescription>Archive is blocked while this model is referenced by Agent Drafts or active Release snapshots.</AlertDescription>
            </div>
          </div>
        </Alert>

        {usage.length > 0 ? (
          <SectionBlock title="Current usage" description="References that must be removed before the Model can be archived." density="compact">
            <div className="scrollbar-thin grid max-h-72 gap-ui-xs overflow-auto">
              {usage.map((item, index) => (
                <TechnicalListItem
                  key={`${item.type}-${item.id}-${index}`}
                  label={item.name || item.version || item.id}
                  description={`${item.type} · ${item.status || 'unknown'}`}
                  meta={item.version ? `version ${item.version}` : shortId(item.id)}
                />
              ))}
            </div>
          </SectionBlock>
        ) : null}

        {blocked ? (
          <Alert variant="warning">
            <AlertTitle>Archive blocked</AlertTitle>
            <AlertDescription>Remove these references before archiving the Model.</AlertDescription>
          </Alert>
        ) : null}

        <div className="flex justify-end gap-ui-sm border-t border-border pt-ui-lg">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="button" variant="destructive" onClick={onConfirm} disabled={blocked} loading={loading}>Archive</Button>
        </div>
      </div>
    </Dialog>
  )
}

export function ModelSettingsModal({
  open,
  onClose,
  projectId,
  credentials,
  selectedModel,
  onSaved,
}: ModelSettingsModalProps) {
  const createModel = useCreateProviderModel()
  const updateModel = useUpdateProviderModel()

  const [activeSection, setActiveSection] = useState<ModelSection>('provider')
  const [step, setStep] = useState<ProviderStep>('model')
  const [createdCredential, setCreatedCredential] = useState<ProviderCredential | null>(null)
  const [credentialPending, setCredentialPending] = useState(false)
  const [credentialId, setCredentialId] = useState('')
  const [catalogModelId, setCatalogModelId] = useState('')
  const [manualMode, setManualMode] = useState(false)
  const [modelId, setModelId] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [status, setStatus] = useState('active')
  const [inputCost, setInputCost] = useState('')
  const [outputCost, setOutputCost] = useState('')
  const [currency, setCurrency] = useState('USD')
  const [contextWindow, setContextWindow] = useState('')
  const [maxOutputTokens, setMaxOutputTokens] = useState('')
  const [supportsTools, setSupportsTools] = useState<CapabilityChoice>('unknown')
  const [supportsJson, setSupportsJson] = useState<CapabilityChoice>('unknown')
  const [supportsStreaming, setSupportsStreaming] = useState<CapabilityChoice>('unknown')
  const [archiveModel, setArchiveModel] = useState<ProviderModel | null>(null)
  const [archiveUsage, setArchiveUsage] = useState<UsageItem[]>([])
  const [impactLoading, setImpactLoading] = useState(false)

  const allCredentials = useMemo(() => {
    if (!createdCredential || credentials.some((credential) => credential.id === createdCredential.id)) return credentials
    return [...credentials, createdCredential]
  }, [credentials, createdCredential])
  const usableCredentials = useMemo(() => allCredentials.filter(isCredentialUsable), [allCredentials])
  const credential = usableCredentials.find((item) => item.id === credentialId) || null
  const canUseCatalog = supportsCatalog(credential)
  const shouldUseCatalog = canUseCatalog && !manualMode && !selectedModel
  const availableModelsQuery = useAvailableProviderModels(projectId, shouldUseCatalog ? credentialId : undefined, 'generation')
  const availableModels = availableModelsQuery.data ?? []
  const catalogModel = shouldUseCatalog ? availableModels.find((model) => model.id === catalogModelId) || null : null
  const busy = createModel.isPending || updateModel.isPending || credentialPending || impactLoading
  const canSave = step === 'model' && Boolean(credential && modelId.trim())
  const capabilitySource = catalogModel
    ? 'Provider catalog'
    : selectedModel
      ? capabilitiesOf(selectedModel).source === 'provider_catalog' ? 'Provider catalog / saved' : 'Manual'
      : 'Manual'
  const technicalName = displayName.trim() || modelId.trim() || selectedModel?.name || 'New model'
  const modelProvider = credential?.provider || selectedModel?.provider || null
  const providerName = providerLabel(modelProvider)

  useEffect(() => {
    if (!open) return
    setCreatedCredential(null)
    setCredentialPending(false)
    setCatalogModelId('')
    setArchiveModel(null)
    setArchiveUsage([])

    if (selectedModel) {
      const pricing = pricingOf(selectedModel)
      const capabilities = capabilitiesOf(selectedModel)
      setActiveSection('overview')
      setStep('model')
      setCredentialId(selectedModel.provider_credential_id)
      setManualMode(true)
      setModelId(selectedModel.model)
      setDisplayName(selectedModel.name)
      setStatus(selectedModel.status || 'active')
      setInputCost(pricing.input === null ? '' : String(pricing.input))
      setOutputCost(pricing.output === null ? '' : String(pricing.output))
      setCurrency(pricing.currency)
      setContextWindow(capabilities.contextWindow === null ? '' : String(capabilities.contextWindow))
      setMaxOutputTokens(capabilities.maxOutputTokens === null ? '' : String(capabilities.maxOutputTokens))
      setSupportsTools(capabilities.supportsTools)
      setSupportsJson(capabilities.supportsJson)
      setSupportsStreaming(capabilities.supportsStreaming)
      return
    }

    setActiveSection('provider')
    setStep(usableCredentials.length === 0 ? 'credential' : 'model')
    setCredentialId(usableCredentials.length === 1 ? usableCredentials[0].id : '')
    setManualMode(false)
    setModelId('')
    setDisplayName('')
    setStatus('active')
    setInputCost('')
    setOutputCost('')
    setCurrency('USD')
    setContextWindow('')
    setMaxOutputTokens('')
    setSupportsTools('unknown')
    setSupportsJson('unknown')
    setSupportsStreaming('unknown')
  }, [open, selectedModel])

  useEffect(() => {
    if (!credential || selectedModel) return
    setManualMode(!supportsCatalog(credential))
    setCatalogModelId('')
    setModelId('')
    setDisplayName('')
    setInputCost('')
    setOutputCost('')
    setCurrency('USD')
    setContextWindow('')
    setMaxOutputTokens('')
    setSupportsTools('unknown')
    setSupportsJson('unknown')
    setSupportsStreaming('unknown')
  }, [credential?.id])

  useEffect(() => {
    if (!catalogModel) return
    setModelId(catalogModel.id)
    setDisplayName(catalogModel.label || catalogModel.id)
    setInputCost(catalogModel.input_cost_per_1m_tokens == null ? '' : String(catalogModel.input_cost_per_1m_tokens))
    setOutputCost(catalogModel.output_cost_per_1m_tokens == null ? '' : String(catalogModel.output_cost_per_1m_tokens))
    setContextWindow(catalogModel.context_window == null ? '' : String(catalogModel.context_window))
    setMaxOutputTokens(catalogModel.max_output_tokens == null ? '' : String(catalogModel.max_output_tokens))
    setSupportsTools(capabilityChoice(catalogModel.supports_tools))
    setSupportsJson(capabilityChoice(catalogModel.supports_json))
    setSupportsStreaming(capabilityChoice(catalogModel.supports_streaming))
  }, [catalogModel?.id])

  const refreshParent = () => {
    void Promise.resolve(onSaved()).catch(() => undefined)
  }

  const saveModel = async () => {
    if (!credential) return toast.error('Select or connect a provider')
    const resolvedModel = modelId.trim()
    const resolvedName = displayName.trim() || catalogModel?.label || resolvedModel
    if (!resolvedModel) return toast.error('Select or enter a model')
    if (inputCost.trim() && (!Number.isFinite(Number(inputCost)) || Number(inputCost) < 0)) return toast.error('Input pricing must be a non-negative number')
    if (outputCost.trim() && (!Number.isFinite(Number(outputCost)) || Number(outputCost) < 0)) return toast.error('Output pricing must be a non-negative number')
    if (contextWindow.trim() && positiveIntegerOrNull(contextWindow) == null) return toast.error('Context Window must be a positive whole number')
    if (maxOutputTokens.trim() && positiveIntegerOrNull(maxOutputTokens) == null) return toast.error('Maximum output must be a positive whole number')
    if (contextWindow.trim() && maxOutputTokens.trim() && Number(maxOutputTokens) > Number(contextWindow)) return toast.error('Maximum output cannot exceed the model Context Window')

    const originalCapabilities = selectedModel ? capabilitiesOf(selectedModel) : null
    const nextContextWindow = contextWindow.trim() ? Number(contextWindow) : null
    const nextMaxOutputTokens = maxOutputTokens.trim() ? Number(maxOutputTokens) : null
    const capabilitiesChanged = Boolean(originalCapabilities && (
      originalCapabilities.contextWindow !== nextContextWindow
      || originalCapabilities.maxOutputTokens !== nextMaxOutputTokens
      || originalCapabilities.supportsTools !== supportsTools
      || originalCapabilities.supportsJson !== supportsJson
      || originalCapabilities.supportsStreaming !== supportsStreaming
    ))

    const metadata = buildModelMetadata(
      selectedModel,
      catalogModel,
      inputCost,
      outputCost,
      currency,
      contextWindow,
      maxOutputTokens,
      supportsTools,
      supportsJson,
      supportsStreaming,
      capabilitiesChanged,
    )

    try {
      if (selectedModel) {
        await updateModel.mutateAsync({
          id: selectedModel.id,
          data: {
            provider_credential_id: credential.id,
            name: resolvedName,
            model: resolvedModel,
            status,
            metadata,
          },
        })
        toast.success('Model updated')
      } else {
        await createModel.mutateAsync({
          project_id: projectId,
          provider_credential_id: credential.id,
          name: resolvedName,
          model: resolvedModel,
          metadata,
        })
        toast.success('Model created')
      }
      refreshParent()
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save model')
    }
  }

  const prepareArchive = async () => {
    if (!selectedModel) return
    setImpactLoading(true)
    try {
      const usage = await loadUsage(projectId)
      setArchiveUsage(usageForModel(selectedModel, usage.agents, usage.releases))
      setArchiveModel(selectedModel)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to inspect model usage')
    } finally {
      setImpactLoading(false)
    }
  }

  const confirmArchive = async () => {
    if (!archiveModel) return
    try {
      await updateModel.mutateAsync({
        id: archiveModel.id,
        data: {
          status: 'archived',
          metadata: {
            ...metadataOf(archiveModel),
            archived_at: new Date().toISOString(),
            archive_mode: 'soft',
          },
        },
      })
      toast.success('Model archived')
      setArchiveModel(null)
      refreshParent()
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to archive model')
    }
  }

  const navigationItems = [
    { value: 'overview', label: 'Overview', icon: <Info className="h-icon w-icon" /> },
    { value: 'provider', label: 'Provider & model', icon: <KeyRound className="h-icon w-icon" /> },
    { value: 'capabilities', label: 'Capabilities', icon: <Gauge className="h-icon w-icon" />, disabled: !credential || !modelId.trim() },
    { value: 'pricing', label: 'Pricing', icon: <DollarSign className="h-icon w-icon" />, disabled: !credential || !modelId.trim() },
    ...(selectedModel ? [{ value: 'lifecycle', label: 'Lifecycle', icon: <Archive className="h-icon w-icon" /> }] : []),
  ]

  const overviewContent = (
    <div className="grid gap-ui-md">
      <SectionBlock
        title="Model identity"
        description="Reusable generation model identity used by Agent Drafts and frozen into Release snapshots."
      >
        <div className="grid gap-ui-md sm:grid-cols-2">
          <Field className="sm:col-span-2">
            <FieldLabel>Display name</FieldLabel>
            <Input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder={modelId || 'Defaults to the model ID'}
            />
          </Field>

          <ReadOnlyValue label="Model ID" value={modelId || 'Select a provider model first'} mono />
          <ReadOnlyValue label="Provider" value={providerName} />
          {selectedModel ? <ReadOnlyValue label="Woobe Model ID" value={selectedModel.id} mono /> : null}
          {selectedModel ? (
            <Field>
              <FieldLabel>Status</FieldLabel>
              <Select
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                options={[
                  { value: 'active', label: 'Active' },
                  { value: 'inactive', label: 'Inactive' },
                ]}
              />
            </Field>
          ) : null}
        </div>
      </SectionBlock>

      <SectionBlock
        title="Binding"
        description="The Model references a Project provider credential. Runtime secrets remain inside the credential boundary."
        density="compact"
      >
        <div className="grid gap-ui-md sm:grid-cols-2">
          <ReadOnlyValue label="Connection" value={credential?.name || 'Not selected'} />
          <ReadOnlyValue label="Provider" value={providerName} />
        </div>
      </SectionBlock>
    </div>
  )

  const providerContent = (
    <div className="grid gap-ui-md">
      {step === 'credential' ? (
        <SectionBlock
          title="Connect provider"
          description="Create a Project credential, then continue configuring this Model without leaving the modal."
        >
          <ProviderCredentialCreateForm
            projectId={projectId}
            existingCredentials={allCredentials}
            formId="model-provider-credential-form"
            showActions={false}
            onPendingChange={setCredentialPending}
            onCreated={(created) => {
              setCreatedCredential(created)
              setCredentialId(created.id)
              setStep('model')
              toast.success('Provider connected')
            }}
          />
        </SectionBlock>
      ) : (
        <>
          <SectionBlock
            title="Provider connection"
            description="Choose the Project credential this generation model will use."
            actions={!selectedModel ? (
              <Button type="button" size="sm" variant="outline" onClick={() => setStep('credential')}>
                <Plus className="mr-2 h-icon w-icon" />Add connection
              </Button>
            ) : undefined}
          >
            {usableCredentials.length === 0 ? (
              <EmptyStatePanel
                icon={<KeyRound className="h-icon-lg w-icon-lg" />}
                title="No active provider connection"
                description="Connect a provider before selecting a generation model."
                action={<Button type="button" size="sm" onClick={() => setStep('credential')}>Connect provider</Button>}
              />
            ) : usableCredentials.length === 1 ? (
              <TechnicalListItem
                label={usableCredentials[0].name}
                description={providerLabel(usableCredentials[0].provider)}
                meta="Project provider credential"
                selected
                trailing={<Check className="h-icon w-icon text-primary-light" />}
              />
            ) : (
              <div className="grid gap-ui-xs lg:grid-cols-2">
                {usableCredentials.map((item) => (
                  <TechnicalListItem
                    key={item.id}
                    label={item.name}
                    description={providerLabel(item.provider)}
                    meta="Project provider credential"
                    selected={item.id === credentialId}
                    trailing={item.id === credentialId ? <Check className="h-icon w-icon text-primary-light" /> : null}
                    onClick={() => setCredentialId(item.id)}
                  />
                ))}
              </div>
            )}
          </SectionBlock>

          {credential ? (
            <SectionBlock
              title="Generation model"
              description={selectedModel
                ? 'Edit the provider model identifier bound to this reusable Model.'
                : `Choose a generation model from ${providerLabel(credential.provider)}.`}
            >
              {shouldUseCatalog ? (
                <CatalogList
                  models={availableModels}
                  selectedId={catalogModelId}
                  loading={availableModelsQuery.isLoading}
                  error={availableModelsQuery.isError}
                  onSelect={(model) => setCatalogModelId(model.id)}
                  onRetry={() => { void availableModelsQuery.refetch() }}
                  onManual={() => {
                    setManualMode(true)
                    setCatalogModelId('')
                    setModelId('')
                    setDisplayName('')
                    setContextWindow('')
                    setMaxOutputTokens('')
                    setSupportsTools('unknown')
                    setSupportsJson('unknown')
                    setSupportsStreaming('unknown')
                  }}
                />
              ) : (
                <div className="grid gap-ui-md">
                  <Field>
                    <FieldLabel>Model ID</FieldLabel>
                    <Input value={modelId} onChange={(event) => setModelId(event.target.value)} placeholder="gpt-4.1-mini" className="font-mono" />
                  </Field>
                  {!selectedModel && canUseCatalog ? (
                    <div>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setManualMode(false)
                          setModelId('')
                          setDisplayName('')
                        }}
                      >
                        Browse provider models
                      </Button>
                    </div>
                  ) : null}
                </div>
              )}
            </SectionBlock>
          ) : null}
        </>
      )}
    </div>
  )

  const capabilitiesContent = (
    <SectionBlock
      title="Model capabilities"
      description="Used by Context budgeting and runtime compatibility checks. Unknown values remain unknown; Woobe does not infer them from the model name."
      actions={<Badge variant="outline" size="compact">{capabilitySource}</Badge>}
    >
      <div className="grid gap-ui-lg">
        <div className="grid gap-ui-md sm:grid-cols-2">
          <Field>
            <FieldLabel>Context Window</FieldLabel>
            <Input value={contextWindow} onChange={(event) => setContextWindow(event.target.value)} inputMode="numeric" placeholder="e.g. 128000" />
            <FieldDescription>Maximum total context capacity reported or configured for this model.</FieldDescription>
          </Field>
          <Field>
            <FieldLabel>Maximum output</FieldLabel>
            <Input value={maxOutputTokens} onChange={(event) => setMaxOutputTokens(event.target.value)} inputMode="numeric" placeholder="Optional" />
            <FieldDescription>Provider/model output ceiling. This is not treated as Context Window.</FieldDescription>
          </Field>
        </div>

        <div className="grid gap-ui-md border-t border-border pt-ui-lg lg:grid-cols-3">
          <Field>
            <FieldLabel>Tool calling</FieldLabel>
            <Select value={supportsTools} onChange={(event) => setSupportsTools(event.target.value as CapabilityChoice)} options={capabilityOptions} />
          </Field>
          <Field>
            <FieldLabel>Structured output</FieldLabel>
            <Select value={supportsJson} onChange={(event) => setSupportsJson(event.target.value as CapabilityChoice)} options={capabilityOptions} />
          </Field>
          <Field>
            <FieldLabel>Streaming</FieldLabel>
            <Select value={supportsStreaming} onChange={(event) => setSupportsStreaming(event.target.value as CapabilityChoice)} options={capabilityOptions} />
          </Field>
        </div>
      </div>
    </SectionBlock>
  )

  const pricingContent = (
    <SectionBlock
      title="Pricing metadata"
      description="Optional costs used for estimation and trace analysis. Pricing metadata does not control provider billing."
    >
      <div className="grid gap-ui-md sm:grid-cols-2">
        <Field>
          <FieldLabel>Input / 1M tokens</FieldLabel>
          <Input value={inputCost} onChange={(event) => setInputCost(event.target.value)} inputMode="decimal" placeholder="Optional" />
        </Field>
        <Field>
          <FieldLabel>Output / 1M tokens</FieldLabel>
          <Input value={outputCost} onChange={(event) => setOutputCost(event.target.value)} inputMode="decimal" placeholder="Optional" />
        </Field>
        <Field className="sm:col-span-2 sm:max-w-xs">
          <FieldLabel>Currency</FieldLabel>
          <Input value={currency} onChange={(event) => setCurrency(event.target.value)} placeholder="USD" />
        </Field>
      </div>
    </SectionBlock>
  )

  const lifecycleContent = selectedModel ? (
    <SectionBlock
      title="Lifecycle"
      description="Archive is blocked while Agent Drafts or active Release snapshots reference this Model."
    >
      <Alert variant="destructive">
        <AlertTitle>Archive Model</AlertTitle>
        <AlertDescription>Woobe checks active Agent and Release references before allowing the soft archive.</AlertDescription>
        <Button
          type="button"
          variant="destructive"
          size="sm"
          className="mt-ui-md"
          loading={impactLoading}
          onClick={() => { void prepareArchive() }}
        >
          <Archive className="mr-2 h-icon w-icon" />Review archive
        </Button>
      </Alert>
    </SectionBlock>
  ) : null

  const currentContent = activeSection === 'overview'
    ? overviewContent
    : activeSection === 'provider'
      ? providerContent
      : activeSection === 'capabilities'
        ? capabilitiesContent
        : activeSection === 'pricing'
          ? pricingContent
          : lifecycleContent

  const footerHint = step === 'credential'
    ? 'Provider credentials belong to the Project and stay separate from Model metadata.'
    : selectedModel
      ? `${providerName} · ${modelId || selectedModel.model}`
      : canSave
        ? `${providerName} · ready to create`
        : 'Choose a provider connection and generation model.'

  return (
    <>
      <Dialog
        open={open}
        onClose={busy ? () => undefined : onClose}
        title={selectedModel ? 'Model settings' : 'New model'}
        className="flex max-h-dialog max-w-dialog-wide flex-col overflow-hidden"
        contentClassName="min-h-0 flex-1 p-0"
      >
        <div className="flex h-full min-h-0 min-w-0 flex-col">
          <div className="shrink-0 border-b border-border bg-background/20 px-ui-lg py-ui-md">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-ui-md">
              <div className="flex min-w-0 items-start gap-ui-md">
                <div className="flex h-control-nav w-control-nav shrink-0 items-center justify-center rounded-control border border-primary/25 bg-primary/[0.08] text-primary-light">
                  <Cpu className="h-icon w-icon" />
                </div>
                <div className="min-w-0">
                  <div className="flex min-w-0 flex-wrap items-center gap-ui-sm">
                    <h3 className="truncate font-mono text-system-heading font-semibold text-accent-foreground">{technicalName}</h3>
                    <StatusBadge status={selectedModel ? status : 'draft'} size="compact" />
                  </div>
                  <div className="mt-ui-xs flex min-w-0 flex-wrap items-center gap-x-ui-md gap-y-ui-xs font-mono text-system-meta text-muted-foreground">
                    <span>{providerName}</span>
                    <span>{credential?.name || 'No connection'}</span>
                    {selectedModel ? <span title={selectedModel.id}>{shortId(selectedModel.id)}</span> : <span>Generation</span>}
                  </div>
                  {modelId ? (
                    <button
                      type="button"
                      className="mt-ui-xs flex max-w-full items-center gap-ui-xs font-mono text-system-meta text-muted-foreground transition-colors hover:text-accent-foreground"
                      onClick={() => {
                        void navigator.clipboard.writeText(modelId)
                        toast.success('Model ID copied')
                      }}
                    >
                      <span className="truncate">{modelId}</span>
                      <Copy className="h-icon-sm w-icon-sm shrink-0" />
                    </button>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="mt-ui-md overflow-x-auto">
              <SegmentedControl
                items={navigationItems}
                value={activeSection}
                onValueChange={(value) => setActiveSection(value as ModelSection)}
                ariaLabel="Model settings sections"
                size="compact"
              />
            </div>
          </div>

          <main className="min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain p-ui-lg lg:p-ui-xl">
            {currentContent}
          </main>

          <div className="flex shrink-0 flex-col-reverse gap-ui-sm border-t border-border bg-surface/95 px-ui-lg py-ui-md backdrop-blur sm:flex-row sm:items-center sm:justify-between lg:px-ui-xl">
            <p className="max-w-2xl font-sans text-product-caption text-muted-foreground">{footerHint}</p>
            <div className="flex flex-wrap justify-end gap-ui-sm">
              {step === 'credential' && usableCredentials.length > 0 ? (
                <Button type="button" variant="outline" disabled={busy} onClick={() => setStep('model')}>Back</Button>
              ) : (
                <Button type="button" variant="outline" disabled={busy} onClick={onClose}>Close</Button>
              )}
              {step === 'credential' ? (
                <Button type="submit" form="model-provider-credential-form" loading={credentialPending}>
                  Connect and continue
                </Button>
              ) : (
                <Button type="button" loading={createModel.isPending || updateModel.isPending} disabled={!canSave} onClick={() => { void saveModel() }}>
                  <ShieldCheck className="mr-2 h-icon w-icon" />
                  {selectedModel ? 'Save changes' : 'Create model'}
                </Button>
              )}
            </div>
          </div>
        </div>
      </Dialog>

      <ArchiveDialog
        model={archiveModel}
        usage={archiveUsage}
        loading={impactLoading || updateModel.isPending}
        onClose={() => setArchiveModel(null)}
        onConfirm={() => { void confirmArchive() }}
      />
    </>
  )
}
