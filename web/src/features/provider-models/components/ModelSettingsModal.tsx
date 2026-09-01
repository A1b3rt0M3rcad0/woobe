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
  type LucideIcon,
} from 'lucide-react'
import { toast } from 'sonner'

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
import { cn } from '@/lib/utils'

const SEARCH_THRESHOLD = 6
type CapabilityChoice = 'unknown' | 'true' | 'false'
type ModelSection = 'overview' | 'provider' | 'capabilities' | 'pricing' | 'lifecycle'
type ProviderStep = 'model' | 'credential'

type SidebarItem = {
  id: ModelSection
  label: string
  icon: LucideIcon
  disabled?: boolean
}

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

function SidebarSectionTitle({ children }: { children: string }) {
  return (
    <p className="hidden px-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted/80 md:block">
      {children}
    </p>
  )
}

function SidebarNavButton({
  item,
  active,
  onClick,
}: {
  item: SidebarItem
  active: boolean
  onClick: () => void
}) {
  const Icon = item.icon
  return (
    <button
      type="button"
      disabled={item.disabled}
      onClick={onClick}
      className={cn(
        'group flex shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-[border-color,background-color,color] md:w-full md:text-sm',
        item.disabled && 'cursor-not-allowed opacity-45',
        active
          ? 'border-primary/35 bg-primary/10 text-primary-light'
          : 'border-transparent text-muted hover:border-primary/20 hover:bg-background/70 hover:text-white',
      )}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" />
      <span className="whitespace-nowrap md:truncate">{item.label}</span>
    </button>
  )
}

function ReadOnlyField({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0 rounded-xl border border-border/80 bg-background/55 p-4">
      <p className="text-[11px] uppercase tracking-wider text-muted">{label}</p>
      <p className={cn('mt-1 break-words text-sm font-medium text-white', mono && 'font-mono text-xs')}>{value}</p>
    </div>
  )
}

function SelectionCard({
  title,
  subtitle,
  selected,
  onClick,
}: {
  title: string
  subtitle: string
  selected: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex w-full items-start justify-between gap-4 rounded-xl border px-4 py-3 text-left transition-colors',
        selected
          ? 'border-primary/55 bg-primary/8'
          : 'border-border/85 bg-background/55 hover:border-primary/30 hover:bg-background/80',
      )}
    >
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium text-white">{title}</span>
        <span className="mt-1 block truncate text-xs text-muted">{subtitle}</span>
      </span>
      <span className={cn(
        'mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border',
        selected ? 'border-primary bg-primary text-white' : 'border-border bg-background',
      )}>
        {selected && <Check className="h-3 w-3" />}
      </span>
    </button>
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
    return <div className="rounded-xl border border-border/80 bg-background/55 px-4 py-10 text-center text-sm text-muted">Loading generation models...</div>
  }

  if (error) {
    return (
      <div className="rounded-xl border border-border/80 bg-background/55 p-4">
        <p className="text-sm font-medium text-white">We couldn't load models from this provider.</p>
        <p className="mt-1 text-sm text-muted">Retry discovery or enter the model ID manually.</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="outline" onClick={onRetry}>
            <RefreshCw className="mr-2 h-4 w-4" />Retry
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={onManual}>Enter model ID manually</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-muted">Choose a generation model from the provider catalog.</span>
        <Button type="button" size="sm" variant="ghost" className="h-auto px-0 py-0 text-xs" onClick={onManual}>Enter model ID manually</Button>
      </div>
      {models.length > SEARCH_THRESHOLD && (
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search models" className="pl-9" />
        </div>
      )}
      <div className="scrollbar-thin max-h-[360px] space-y-2 overflow-y-auto pr-1">
        {visible.length === 0 ? (
          <div className="rounded-xl border border-border/80 bg-background/55 px-4 py-10 text-center text-sm text-muted">No generation models found.</div>
        ) : visible.map((model) => (
          <SelectionCard
            key={model.id}
            title={model.label}
            subtitle={`${providerLabel(model.provider)} · ${model.id}`}
            selected={model.id === selectedId}
            onClick={() => onSelect(model)}
          />
        ))}
      </div>
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
    <Dialog open onClose={onClose} title="Archive model" className="max-w-2xl">
      <div className="space-y-4">
        <div className="rounded-xl border border-border/80 bg-background/60 p-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-amber-400/30 bg-amber-400/10 text-amber-200">
              <AlertTriangle className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">{model.name}</p>
              <p className="mt-1 text-sm leading-6 text-muted">Archive is blocked while this model is referenced by agents or active releases.</p>
            </div>
          </div>
        </div>

        {usage.length > 0 && (
          <div className="rounded-xl border border-border/80 bg-surface/50 p-4">
            <p className="text-sm font-semibold text-white">Current usage</p>
            <div className="scrollbar-thin mt-3 max-h-72 space-y-2 overflow-auto">
              {usage.map((item, index) => (
                <div key={`${item.type}-${item.id}-${index}`} className="rounded-lg border border-border/70 bg-background/60 p-3 text-xs text-muted">
                  <p className="font-medium text-white">{item.type} · {item.name || item.version || item.id}</p>
                  <p className="mt-1">status: {item.status || 'unknown'}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {blocked && <p className="text-sm text-amber-200">Remove these references before archiving the model.</p>}

        <div className="flex justify-end gap-2 border-t border-border pt-4">
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

  const configurationItems: SidebarItem[] = [
    { id: 'overview', label: 'Overview', icon: Info },
    { id: 'provider', label: 'Provider & model', icon: KeyRound },
    { id: 'capabilities', label: 'Capabilities', icon: Gauge, disabled: !credential || !modelId.trim() },
    { id: 'pricing', label: 'Pricing', icon: DollarSign, disabled: !credential || !modelId.trim() },
  ]
  const operationItems: SidebarItem[] = selectedModel
    ? [{ id: 'lifecycle', label: 'Lifecycle', icon: Archive }]
    : []

  const overviewContent = (
    <div className="space-y-5">
      <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
        <h3 className="text-sm font-semibold text-white">Model identity</h3>
        <p className="mt-1 text-xs leading-5 text-muted">Reusable generation model identity used by Agent Drafts and frozen into Release snapshots.</p>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <label className="block sm:col-span-2">
            <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Display name</span>
            <Input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder={modelId || 'Defaults to the model ID'}
            />
          </label>
          <ReadOnlyField label="Model ID" value={modelId || 'Select a provider model first'} mono />
          <ReadOnlyField label="Provider" value={providerName} />
          {selectedModel ? <ReadOnlyField label="Woobe Model ID" value={selectedModel.id} mono /> : null}
          {selectedModel ? (
            <label className="block">
              <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Status</span>
              <Select
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                options={[
                  { value: 'active', label: 'Active' },
                  { value: 'inactive', label: 'Inactive' },
                ]}
              />
            </label>
          ) : null}
        </div>
      </section>

      <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
        <h3 className="text-sm font-semibold text-white">Binding</h3>
        <p className="mt-1 text-xs leading-5 text-muted">The Model references a Project provider credential. Runtime secrets remain in the credential boundary.</p>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <ReadOnlyField label="Connection" value={credential?.name || 'Not selected'} />
          <ReadOnlyField label="Provider" value={providerName} />
        </div>
      </section>
    </div>
  )

  const providerContent = (
    <div className="space-y-5">
      {step === 'credential' ? (
        <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
          <h3 className="text-sm font-semibold text-white">Connect provider</h3>
          <p className="mt-1 text-xs leading-5 text-muted">Create a Project credential, then continue configuring this Model without leaving the modal.</p>
          <div className="mt-5">
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
          </div>
        </section>
      ) : (
        <>
          <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white">Provider connection</h3>
                <p className="mt-1 text-xs leading-5 text-muted">Choose the Project credential this generation model will use.</p>
              </div>
              {!selectedModel ? (
                <Button type="button" size="sm" variant="outline" onClick={() => setStep('credential')}>
                  <Plus className="mr-2 h-3.5 w-3.5" />Add connection
                </Button>
              ) : null}
            </div>

            <div className="mt-5">
              {usableCredentials.length === 0 ? (
                <div className="rounded-xl border border-dashed border-border bg-background/45 px-4 py-10 text-center">
                  <KeyRound className="mx-auto h-5 w-5 text-muted" />
                  <p className="mt-3 text-sm font-medium text-white">No active provider connection</p>
                  <p className="mt-1 text-xs text-muted">Connect a provider before selecting a generation model.</p>
                  <Button type="button" size="sm" className="mt-4" onClick={() => setStep('credential')}>Connect provider</Button>
                </div>
              ) : usableCredentials.length === 1 ? (
                <div className="flex items-center justify-between gap-4 rounded-xl border border-border/85 bg-background/55 px-4 py-3">
                  <div>
                    <p className="text-xs text-muted">Connected with</p>
                    <p className="mt-1 text-sm font-medium text-white">{usableCredentials[0].name}</p>
                    <p className="mt-1 text-xs text-muted">{providerLabel(usableCredentials[0].provider)}</p>
                  </div>
                  <Check className="h-5 w-5 text-primary-light" />
                </div>
              ) : (
                <div className="grid gap-2 lg:grid-cols-2">
                  {usableCredentials.map((item) => (
                    <SelectionCard
                      key={item.id}
                      title={item.name}
                      subtitle={providerLabel(item.provider)}
                      selected={item.id === credentialId}
                      onClick={() => setCredentialId(item.id)}
                    />
                  ))}
                </div>
              )}
            </div>
          </section>

          {credential ? (
            <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
              <h3 className="text-sm font-semibold text-white">Generation model</h3>
              <p className="mt-1 text-xs leading-5 text-muted">
                {selectedModel ? 'Edit the provider model identifier bound to this reusable Model.' : `Choose a generation model from ${providerLabel(credential.provider)}.`}
              </p>
              <div className="mt-5">
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
                  <div className="space-y-4">
                    <div>
                      <label className="mb-1 block text-sm font-medium text-muted">Model ID</label>
                      <Input value={modelId} onChange={(event) => setModelId(event.target.value)} placeholder="gpt-4.1-mini" className="font-mono text-xs" />
                    </div>
                    {!selectedModel && canUseCatalog ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="px-0"
                        onClick={() => {
                          setManualMode(false)
                          setModelId('')
                          setDisplayName('')
                        }}
                      >
                        Browse provider models
                      </Button>
                    ) : null}
                  </div>
                )}
              </div>
            </section>
          ) : null}
        </>
      )}
    </div>
  )

  const capabilitiesContent = (
    <div className="space-y-5">
      <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">Model capabilities</h3>
            <p className="mt-1 max-w-2xl text-xs leading-5 text-muted">Used by Context budgeting and runtime compatibility checks. Unknown values remain unknown; Woobe does not infer them from the model name.</p>
          </div>
          <span className="shrink-0 rounded-full border border-border bg-background px-2 py-1 text-[10px] text-muted">{capabilitySource}</span>
        </div>

        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Context Window</label>
            <Input value={contextWindow} onChange={(event) => setContextWindow(event.target.value)} inputMode="numeric" placeholder="e.g. 128000" />
            <p className="mt-1 text-[10px] leading-4 text-muted">Maximum total context capacity reported or configured for this model.</p>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Maximum output</label>
            <Input value={maxOutputTokens} onChange={(event) => setMaxOutputTokens(event.target.value)} inputMode="numeric" placeholder="Optional" />
            <p className="mt-1 text-[10px] leading-4 text-muted">Provider/model output ceiling. This is not treated as Context Window.</p>
          </div>
        </div>

        <div className="mt-5 grid gap-4 border-t border-border/70 pt-5 lg:grid-cols-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Tool calling</label>
            <Select value={supportsTools} onChange={(event) => setSupportsTools(event.target.value as CapabilityChoice)} options={capabilityOptions} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Structured output</label>
            <Select value={supportsJson} onChange={(event) => setSupportsJson(event.target.value as CapabilityChoice)} options={capabilityOptions} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Streaming</label>
            <Select value={supportsStreaming} onChange={(event) => setSupportsStreaming(event.target.value as CapabilityChoice)} options={capabilityOptions} />
          </div>
        </div>
      </section>
    </div>
  )

  const pricingContent = (
    <div className="space-y-5">
      <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
        <h3 className="text-sm font-semibold text-white">Pricing metadata</h3>
        <p className="mt-1 text-xs leading-5 text-muted">Optional costs used for estimation and trace analysis. Pricing metadata does not control provider billing.</p>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Input / 1M tokens</label>
            <Input value={inputCost} onChange={(event) => setInputCost(event.target.value)} inputMode="decimal" placeholder="Optional" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Output / 1M tokens</label>
            <Input value={outputCost} onChange={(event) => setOutputCost(event.target.value)} inputMode="decimal" placeholder="Optional" />
          </div>
          <div className="sm:col-span-2 sm:max-w-xs">
            <label className="mb-1 block text-sm font-medium text-muted">Currency</label>
            <Input value={currency} onChange={(event) => setCurrency(event.target.value)} placeholder="USD" />
          </div>
        </div>
      </section>
    </div>
  )

  const lifecycleContent = selectedModel ? (
    <div className="space-y-5">
      <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
        <h3 className="text-sm font-semibold text-white">Lifecycle</h3>
        <p className="mt-1 text-xs leading-5 text-muted">Archive is blocked while Agent Drafts or active Release snapshots reference this Model.</p>
        <div className="mt-5 rounded-xl border border-red-500/20 bg-red-500/5 p-4">
          <p className="text-sm font-medium text-white">Archive Model</p>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-muted">Woobe checks active Agent and Release references before allowing the soft archive.</p>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            className="mt-4"
            loading={impactLoading}
            onClick={() => { void prepareArchive() }}
          >
            <Archive className="mr-2 h-3.5 w-3.5" />Review archive
          </Button>
        </div>
      </section>
    </div>
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
        className="flex h-[min(900px,calc(100svh-2rem))] max-w-7xl flex-col overflow-hidden"
        contentClassName="min-h-0 flex-1 p-0"
      >
        <div className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)] md:grid-cols-[230px_minmax(0,1fr)] md:grid-rows-1">
          <aside className="flex min-h-0 min-w-0 flex-col border-b border-border bg-background/35 md:border-b-0 md:border-r">
            <div className="hidden border-b border-border p-4 md:block">
              <div className="flex min-w-0 items-start gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary-light">
                  <Cpu className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex min-w-0 items-center gap-2">
                    <h3 className="min-w-0 flex-1 truncate text-sm font-semibold text-white">{technicalName}</h3>
                    <StatusBadge status={selectedModel ? status : 'draft'} size="compact" />
                  </div>
                  <p className="mt-1 truncate text-xs text-muted">{providerName}</p>
                  {modelId ? (
                    <button
                      type="button"
                      className="mt-2 flex max-w-full items-center gap-1.5 font-mono text-[11px] text-muted hover:text-white"
                      onClick={() => {
                        void navigator.clipboard.writeText(modelId)
                        toast.success('Model ID copied')
                      }}
                    >
                      <span className="truncate">{modelId}</span>
                      <Copy className="h-3 w-3 shrink-0" />
                    </button>
                  ) : (
                    <p className="mt-2 text-[11px] text-muted">Provider model not selected</p>
                  )}
                </div>
              </div>
              <div className="mt-3 flex items-center justify-between border-t border-border/70 pt-3 text-[11px] text-muted">
                <span>{credential?.name || 'No connection'}</span>
                {selectedModel ? <span className="font-mono" title={selectedModel.id}>{shortId(selectedModel.id)}</span> : <span>Generation</span>}
              </div>
            </div>

            <nav className="flex min-w-0 gap-1 overflow-x-auto p-2 md:block md:flex-1 md:space-y-5 md:overflow-y-auto md:p-3">
              <div className="contents md:block md:space-y-2">
                <SidebarSectionTitle>Configuration</SidebarSectionTitle>
                <div className="contents md:block md:space-y-1">
                  {configurationItems.map((item) => (
                    <SidebarNavButton
                      key={item.id}
                      item={item}
                      active={activeSection === item.id}
                      onClick={() => setActiveSection(item.id)}
                    />
                  ))}
                </div>
              </div>

              {operationItems.length > 0 ? (
                <div className="contents md:block md:space-y-2">
                  <SidebarSectionTitle>Operate</SidebarSectionTitle>
                  <div className="contents md:block md:space-y-1">
                    {operationItems.map((item) => (
                      <SidebarNavButton
                        key={item.id}
                        item={item}
                        active={activeSection === item.id}
                        onClick={() => setActiveSection(item.id)}
                      />
                    ))}
                  </div>
                </div>
              ) : null}
            </nav>
          </aside>

          <main className="flex min-h-0 min-w-0 flex-col overflow-hidden">
            <div className="min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain p-4 sm:p-5 lg:p-6">
              {currentContent}
            </div>
            <div className="flex shrink-0 flex-col-reverse gap-2 border-t border-border bg-surface/95 px-4 py-3 backdrop-blur sm:flex-row sm:items-center sm:justify-between lg:px-6">
              <p className="max-w-2xl text-[11px] text-muted">{footerHint}</p>
              <div className="flex flex-wrap justify-end gap-2">
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
                    <ShieldCheck className="mr-2 h-4 w-4" />
                    {selectedModel ? 'Save changes' : 'Create model'}
                  </Button>
                )}
              </div>
            </div>
          </main>
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
