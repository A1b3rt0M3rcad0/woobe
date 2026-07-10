import { useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  Bot,
  Check,
  CheckCircle2,
  Key,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
} from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { useCreateAgent } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'
import { useCreateCredential, useCredentials } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import {
  useAvailableProviderModels,
  useCreateProviderModel,
  useProviderModels,
} from '@/features/provider-models/hooks'
import type { AvailableProviderModel, ProviderModel } from '@/features/provider-models/types'

const OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'
const SEARCH_THRESHOLD = 6

const providerOptions = [
  { value: 'openai', label: 'OpenAI', description: 'Use models available from your OpenAI account.' },
  { value: 'openrouter', label: 'OpenRouter', description: 'Access generation models through one OpenRouter connection.' },
  { value: 'custom', label: 'OpenAI Compatible', description: 'Connect a provider or gateway that exposes an OpenAI-compatible API.' },
]

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  custom: 'OpenAI Compatible',
  openrouter: 'OpenRouter',
}

const defaultCredentialNames: Record<string, string> = {
  openai: 'OpenAI',
  custom: 'OpenAI Compatible',
  openrouter: 'OpenRouter',
}

type Step = 'details' | 'connect-provider' | 'select-model' | 'create-model' | 'review'
type CredentialEntrySource = 'details' | 'select-model' | 'create-model'
type ProgressKey = 'details' | 'connect-provider' | 'model' | 'review'

interface CreateAgentFlowModalProps {
  open: boolean
  onClose: () => void
  projectId: string
  onCreated: (agent: Agent) => void
}

function providerLabel(provider?: string | null) {
  if (!provider) return 'Provider'
  return providerLabels[provider] || provider
}

function supportsModelCatalog(credential?: ProviderCredential | null) {
  return credential?.provider === 'openai' || credential?.provider === 'openrouter'
}

function isCredentialActive(credential: ProviderCredential) {
  return !credential.status || credential.status === 'active'
}

function isEmbeddingProviderModel(model: ProviderModel) {
  const metadata = model.metadata || {}
  const capability = String(metadata.capability || metadata.type || '').trim().toLowerCase()
  if (capability) return capability === 'embedding' || capability === 'embeddings'
  return `${model.name} ${model.model}`.toLowerCase().includes('embed')
}

function buildCredentialMetadata(provider: string, baseUrl: string): Record<string, string> {
  if (provider === 'custom') {
    return {
      provider_family: 'openai',
      compatibility: 'compatible',
      base_url: baseUrl.trim(),
      model_discovery_strategy: 'openai_compatible_models',
    }
  }
  if (provider === 'openrouter') {
    return {
      provider_family: 'openrouter',
      compatibility: 'native',
      base_url: OPENROUTER_BASE_URL,
      model_discovery_strategy: 'openrouter_models',
    }
  }
  return {
    provider_family: 'openai',
    compatibility: 'native',
    model_discovery_strategy: 'openai_models',
  }
}

function buildModelMetadata(catalogModel: AvailableProviderModel | null) {
  if (!catalogModel) {
    return {
      capability: 'generation',
      source: 'manual',
      pricing: {
        input_cost_per_1m_tokens: null,
        output_cost_per_1m_tokens: null,
        currency: 'USD',
        billing_unit: 'per_1m_tokens',
        source: 'manual',
      },
    }
  }

  return {
    capability: 'generation',
    source: 'remote',
    catalog: {
      provider: catalogModel.provider,
      model_id: catalogModel.id,
      label: catalogModel.label,
      owned_by: catalogModel.owned_by ?? null,
      context_window: catalogModel.context_window ?? null,
    },
    capabilities: {
      supports_tools: catalogModel.supports_tools ?? null,
      supports_json: catalogModel.supports_json ?? null,
      supports_streaming: catalogModel.supports_streaming ?? null,
    },
    pricing: {
      input_cost_per_1m_tokens: catalogModel.input_cost_per_1m_tokens ?? null,
      output_cost_per_1m_tokens: catalogModel.output_cost_per_1m_tokens ?? null,
      currency: 'USD',
      billing_unit: 'per_1m_tokens',
      source: 'provider_catalog',
    },
    provider_model_raw: catalogModel.raw,
  }
}

function nextCredentialName(provider: string, credentials: ProviderCredential[]) {
  const base = defaultCredentialNames[provider] || providerLabel(provider)
  const count = credentials.filter((item) => item.provider === provider).length
  return count === 0 ? base : `${base} ${count + 1}`
}

function StepItem({
  index,
  label,
  active,
  completed,
}: {
  index: number
  label: string
  active: boolean
  completed: boolean
}) {
  return (
    <div className="flex items-center gap-3">
      <span
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${
          completed
            ? 'border-primary/50 bg-primary/15 text-primary-light'
            : active
              ? 'border-primary bg-primary/10 text-white'
              : 'border-border bg-background text-muted'
        }`}
      >
        {completed ? <Check className="h-3.5 w-3.5" /> : index}
      </span>
      <span className={`text-sm ${active ? 'font-medium text-white' : completed ? 'text-white/85' : 'text-muted'}`}>{label}</span>
    </div>
  )
}

function ModelCard({
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
      aria-pressed={selected}
      className={`flex w-full items-start justify-between gap-4 rounded-xl border px-4 py-3 text-left transition-colors ${
        selected
          ? 'border-primary/55 bg-primary/8'
          : 'border-border/85 bg-background/55 hover:border-primary/30 hover:bg-background/80'
      }`}
    >
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium text-white">{title}</span>
        <span className="mt-1 block truncate text-xs text-muted">{subtitle}</span>
      </span>
      <span
        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${
          selected ? 'border-primary bg-primary text-white' : 'border-border bg-background'
        }`}
      >
        {selected && <Check className="h-3 w-3" />}
      </span>
    </button>
  )
}

function ExistingModelList({
  models,
  selectedModelId,
  onSelect,
}: {
  models: ProviderModel[]
  selectedModelId: string
  onSelect: (modelId: string) => void
}) {
  const [query, setQuery] = useState('')
  const filteredModels = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return models
    return models.filter((item) => `${item.name} ${item.model} ${providerLabel(item.provider)}`.toLowerCase().includes(normalized))
  }, [models, query])
  const showSearch = models.length > SEARCH_THRESHOLD

  return (
    <div className="space-y-3">
      {showSearch && (
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search models" className="pl-9" />
        </div>
      )}
      <div className="scrollbar-thin max-h-80 space-y-2 overflow-y-auto pr-1">
        {filteredModels.length === 0 ? (
          <div className="rounded-xl border border-border/80 bg-background/55 px-4 py-8 text-center text-sm text-muted">No generation models found.</div>
        ) : filteredModels.map((model) => (
          <ModelCard
            key={model.id}
            title={model.name}
            subtitle={`${providerLabel(model.provider)} · ${model.model}`}
            selected={model.id === selectedModelId}
            onClick={() => onSelect(model.id)}
          />
        ))}
      </div>
    </div>
  )
}

function CredentialList({
  credentials,
  selectedCredentialId,
  onSelect,
}: {
  credentials: ProviderCredential[]
  selectedCredentialId: string
  onSelect: (credentialId: string) => void
}) {
  return (
    <div className="space-y-2">
      {credentials.map((credential) => (
        <ModelCard
          key={credential.id}
          title={credential.name}
          subtitle={providerLabel(credential.provider)}
          selected={credential.id === selectedCredentialId}
          onClick={() => onSelect(credential.id)}
        />
      ))}
    </div>
  )
}

function CatalogModelList({
  models,
  selectedModelId,
  loading,
  error,
  onSelect,
  onRetry,
  onManualMode,
}: {
  models: AvailableProviderModel[]
  selectedModelId: string
  loading: boolean
  error: boolean
  onSelect: (model: AvailableProviderModel) => void
  onRetry: () => void
  onManualMode: () => void
}) {
  const [query, setQuery] = useState('')
  const filteredModels = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return models
    return models.filter((item) => `${item.label} ${item.id} ${item.provider} ${item.owned_by || ''}`.toLowerCase().includes(normalized))
  }, [models, query])
  const visibleModels = filteredModels.slice(0, 80)
  const showSearch = models.length > SEARCH_THRESHOLD

  if (loading) {
    return <div className="rounded-xl border border-border/80 bg-background/55 px-4 py-8 text-center text-sm text-muted">Loading generation models...</div>
  }

  if (error) {
    return (
      <div className="rounded-xl border border-border/80 bg-background/55 p-4">
        <p className="text-sm font-medium text-white">We couldn't load models from this provider.</p>
        <p className="mt-1 text-sm leading-6 text-muted">Retry discovery or enter the model identifier manually.</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="outline" onClick={onRetry}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Retry
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={onManualMode}>Enter model ID manually</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-muted">Choose the model this agent will use.</span>
        <Button type="button" size="sm" variant="ghost" className="h-auto px-0 py-0 text-xs" onClick={onManualMode}>Enter model ID manually</Button>
      </div>
      {showSearch && (
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search models" className="pl-9" />
        </div>
      )}
      <div className="scrollbar-thin max-h-80 space-y-2 overflow-y-auto pr-1">
        {visibleModels.length === 0 ? (
          <div className="rounded-xl border border-border/80 bg-background/55 px-4 py-8 text-center">
            <p className="text-sm text-muted">No generation models found.</p>
            <Button type="button" size="sm" variant="ghost" className="mt-3" onClick={onManualMode}>Enter model ID manually</Button>
          </div>
        ) : visibleModels.map((model) => (
          <ModelCard
            key={model.id}
            title={model.label}
            subtitle={`${providerLabel(model.provider)} · ${model.id}`}
            selected={model.id === selectedModelId}
            onClick={() => onSelect(model)}
          />
        ))}
      </div>
    </div>
  )
}

export function CreateAgentFlowModal({ open, onClose, projectId, onCreated }: CreateAgentFlowModalProps) {
  const credentialsQuery = useCredentials(projectId)
  const modelsQuery = useProviderModels(projectId)
  const createCredential = useCreateCredential()
  const createModel = useCreateProviderModel()
  const createAgent = useCreateAgent(projectId)

  const [step, setStep] = useState<Step>('details')
  const [agentName, setAgentName] = useState('')
  const [agentDescription, setAgentDescription] = useState('')
  const [selectedModelId, setSelectedModelId] = useState('')
  const [createdCredential, setCreatedCredential] = useState<ProviderCredential | null>(null)
  const [createdModel, setCreatedModel] = useState<ProviderModel | null>(null)
  const [credentialStepUsed, setCredentialStepUsed] = useState(false)
  const [credentialEntrySource, setCredentialEntrySource] = useState<CredentialEntrySource>('details')

  const [credentialProvider, setCredentialProvider] = useState('openai')
  const [credentialSecret, setCredentialSecret] = useState('')
  const [credentialBaseUrl, setCredentialBaseUrl] = useState('')

  const [selectedCredentialId, setSelectedCredentialId] = useState('')
  const [modelName, setModelName] = useState('')
  const [modelIdentifier, setModelIdentifier] = useState('')
  const [selectedCatalogModelId, setSelectedCatalogModelId] = useState('')
  const [manualMode, setManualMode] = useState(false)

  const credentials = useMemo(() => {
    const source = credentialsQuery.data ?? []
    if (!createdCredential || source.some((item) => item.id === createdCredential.id)) return source
    return [...source, createdCredential]
  }, [credentialsQuery.data, createdCredential])

  const activeCredentials = useMemo(
    () => credentials.filter((credential) => isCredentialActive(credential) && ['openai', 'custom', 'openrouter'].includes(credential.provider)),
    [credentials],
  )
  const activeCredentialIds = useMemo(() => new Set(activeCredentials.map((credential) => credential.id)), [activeCredentials])

  const models = useMemo(() => {
    const source = modelsQuery.data ?? []
    if (!createdModel || source.some((item) => item.id === createdModel.id)) return source
    return [...source, createdModel]
  }, [modelsQuery.data, createdModel])

  const usableAgentModels = useMemo(
    () => models.filter((model) => (
      model.status === 'active'
      && activeCredentialIds.has(model.provider_credential_id)
      && !isEmbeddingProviderModel(model)
    )),
    [models, activeCredentialIds],
  )

  const selectedModel = usableAgentModels.find((model) => model.id === selectedModelId) || null
  const selectedCredential = activeCredentials.find((credential) => credential.id === selectedCredentialId) || null
  const canUseCatalog = supportsModelCatalog(selectedCredential)
  const shouldUseCatalog = canUseCatalog && !manualMode
  const availableModelsQuery = useAvailableProviderModels(
    projectId,
    shouldUseCatalog ? selectedCredentialId : undefined,
    'generation',
  )
  const availableModels = availableModelsQuery.data ?? []
  const selectedCatalogModel = shouldUseCatalog
    ? availableModels.find((item) => item.id === selectedCatalogModelId) || null
    : null

  useEffect(() => {
    if (!open) return
    setStep('details')
    setAgentName('')
    setAgentDescription('')
    setSelectedModelId('')
    setCreatedCredential(null)
    setCreatedModel(null)
    setCredentialStepUsed(false)
    setCredentialEntrySource('details')
    setCredentialProvider('openai')
    setCredentialSecret('')
    setCredentialBaseUrl('')
    setSelectedCredentialId('')
    setModelName('')
    setModelIdentifier('')
    setSelectedCatalogModelId('')
    setManualMode(false)
  }, [open])

  useEffect(() => {
    if (!open || selectedCredentialId || activeCredentials.length !== 1) return
    setSelectedCredentialId(activeCredentials[0].id)
  }, [open, activeCredentials, selectedCredentialId])

  useEffect(() => {
    if (!selectedCredential) return
    setManualMode(!supportsModelCatalog(selectedCredential))
    setSelectedCatalogModelId('')
    setModelIdentifier('')
    setModelName('')
  }, [selectedCredential?.id])

  useEffect(() => {
    if (!selectedCatalogModel) return
    setModelIdentifier(selectedCatalogModel.id)
    setModelName(selectedCatalogModel.label || selectedCatalogModel.id)
  }, [selectedCatalogModel?.id])

  useEffect(() => {
    if (credentialProvider !== 'custom') setCredentialBaseUrl('')
  }, [credentialProvider])

  const progressSteps = useMemo(() => {
    const items: Array<{ key: ProgressKey; label: string }> = [{ key: 'details', label: 'Agent details' }]
    if (credentialStepUsed) items.push({ key: 'connect-provider', label: 'Connect provider' })
    items.push({ key: 'model', label: 'Model' })
    items.push({ key: 'review', label: 'Review' })
    return items
  }, [credentialStepUsed])

  const currentProgressKey: ProgressKey = step === 'details'
    ? 'details'
    : step === 'connect-provider'
      ? 'connect-provider'
      : step === 'review'
        ? 'review'
        : 'model'
  const currentProgressIndex = progressSteps.findIndex((item) => item.key === currentProgressKey)

  const inventoryLoading = modelsQuery.isLoading || credentialsQuery.isLoading
  const dependenciesError = modelsQuery.isError || credentialsQuery.isError
  const busy = createCredential.isPending || createModel.isPending || createAgent.isPending

  const startAfterDetails = () => {
    if (!agentName.trim()) {
      toast.error('Agent name is required')
      return
    }
    if (usableAgentModels.length > 0) {
      setCredentialStepUsed(false)
      setStep('select-model')
      return
    }
    if (activeCredentials.length === 0) {
      setCredentialStepUsed(true)
      setCredentialEntrySource('details')
      setStep('connect-provider')
      return
    }
    setCredentialStepUsed(false)
    if (activeCredentials.length === 1) setSelectedCredentialId(activeCredentials[0].id)
    setStep('create-model')
  }

  const startCreateModel = () => {
    if (activeCredentials.length === 0) {
      setCredentialStepUsed(true)
      setCredentialEntrySource('select-model')
      setStep('connect-provider')
      return
    }
    if (activeCredentials.length === 1) setSelectedCredentialId(activeCredentials[0].id)
    setStep('create-model')
  }

  const startAddCredential = () => {
    setCredentialStepUsed(true)
    setCredentialEntrySource('create-model')
    setStep('connect-provider')
  }

  const handleCredentialSubmit = async () => {
    if (!credentialSecret.trim()) return toast.error('API key is required')
    if (credentialProvider === 'custom' && !credentialBaseUrl.trim()) return toast.error('Base URL is required for OpenAI Compatible providers')

    try {
      const credential = await createCredential.mutateAsync({
        project_id: projectId,
        provider: credentialProvider,
        name: nextCredentialName(credentialProvider, credentials),
        secret: credentialSecret.trim(),
        metadata: buildCredentialMetadata(credentialProvider, credentialBaseUrl),
      })
      setCreatedCredential(credential)
      setSelectedCredentialId(credential.id)
      setCredentialSecret('')
      setStep('create-model')
      toast.success('Provider connected')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to connect provider')
    }
  }

  const handleCatalogSelect = (model: AvailableProviderModel) => {
    setSelectedCatalogModelId(model.id)
    setModelIdentifier(model.id)
    setModelName(model.label || model.id)
  }

  const handleCreateModel = async () => {
    if (!selectedCredential) return toast.error('Select or connect a provider first')
    const resolvedModel = modelIdentifier.trim()
    const resolvedName = modelName.trim() || selectedCatalogModel?.label || resolvedModel
    if (!resolvedModel) return toast.error('Select or enter a model')

    try {
      const model = await createModel.mutateAsync({
        project_id: projectId,
        provider_credential_id: selectedCredential.id,
        name: resolvedName,
        model: resolvedModel,
        metadata: buildModelMetadata(selectedCatalogModel),
      })
      setCreatedModel(model)
      setSelectedModelId(model.id)
      setStep('review')
      toast.success('Model created')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create model')
    }
  }

  const continueWithExistingModel = () => {
    if (!selectedModel) {
      toast.error('Select a model')
      return
    }
    setStep('review')
  }

  const handleCreateAgent = async () => {
    if (!agentName.trim()) return toast.error('Agent name is required')
    if (!selectedModel) return toast.error('Select a generation model')

    try {
      const agent = await createAgent.mutateAsync({
        project_id: projectId,
        name: agentName.trim(),
        description: agentDescription.trim(),
        provider_model_id: selectedModel.id,
        provider: selectedModel.provider || 'openai',
        model: selectedModel.model,
        system_prompt: '',
        temperature: 0.7,
        max_output_tokens: 2048,
        provider_credential_id: selectedModel.provider_credential_id,
        session_mode: 'stateful',
      })
      toast.success('Agent created')
      onCreated(agent)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create agent')
    }
  }

  const goBack = () => {
    if (step === 'review') {
      setStep('select-model')
      return
    }
    if (step === 'select-model') {
      setStep('details')
      return
    }
    if (step === 'create-model') {
      setStep(usableAgentModels.length > 0 ? 'select-model' : 'details')
      return
    }
    if (step === 'connect-provider') {
      setStep(credentialEntrySource)
    }
  }

  const footerPrimary = () => {
    if (step === 'details') {
      return (
        <Button type="button" onClick={startAfterDetails} disabled={inventoryLoading}>
          Continue
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      )
    }
    if (step === 'connect-provider') {
      return <Button type="button" onClick={handleCredentialSubmit} loading={createCredential.isPending}>Connect provider</Button>
    }
    if (step === 'select-model') {
      return <Button type="button" onClick={continueWithExistingModel} disabled={!selectedModel}>Continue</Button>
    }
    if (step === 'create-model') {
      return (
        <Button
          type="button"
          onClick={handleCreateModel}
          loading={createModel.isPending}
          disabled={!selectedCredential || !modelIdentifier.trim()}
        >
          Create model and continue
        </Button>
      )
    }
    return (
      <Button type="button" onClick={handleCreateAgent} loading={createAgent.isPending}>
        <ShieldCheck className="mr-2 h-4 w-4" />
        Create agent
      </Button>
    )
  }

  return (
    <Dialog open={open} onClose={busy ? () => undefined : onClose} title="Create agent" className="max-h-[calc(100svh-2rem)] max-w-5xl overflow-hidden">
      <div className="scrollbar-thin max-h-[calc(100svh-8rem)] overflow-y-auto pr-1">
        <div className="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="space-y-4 lg:sticky lg:top-0 lg:self-start">
            <section className="rounded-xl border border-border/90 bg-surface/70 p-4">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-background text-primary-light">
                <Bot className="h-5 w-5" />
              </div>
              <div className="mt-5">
                <h3 className="text-base font-semibold text-white">New agent</h3>
                <p className="mt-1 text-xs leading-5 text-muted">Guided setup for the minimum configuration needed to start in the Playground.</p>
              </div>
            </section>

            <section className="rounded-xl border border-border/90 bg-background/60 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Progress</p>
              <div className="mt-4 space-y-4">
                {progressSteps.map((item, index) => (
                  <StepItem
                    key={item.key}
                    index={index + 1}
                    label={item.label}
                    active={index === currentProgressIndex}
                    completed={index < currentProgressIndex}
                  />
                ))}
              </div>
            </section>
          </aside>

          <main className="space-y-5">
            {step === 'details' && (
              <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                <div className="mb-5">
                  <h3 className="text-sm font-semibold text-white">Agent details</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">Give your agent a name. You can configure its behavior, tools and knowledge later in the Playground.</p>
                </div>
                <div className="space-y-4">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-muted">Name</label>
                    <Input value={agentName} onChange={(event) => setAgentName(event.target.value)} placeholder="Customer Support Agent" autoFocus />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-muted">Description</label>
                    <Input value={agentDescription} onChange={(event) => setAgentDescription(event.target.value)} placeholder="Optional description" />
                  </div>
                </div>
              </section>
            )}

            {step !== 'details' && step !== 'connect-provider' && (inventoryLoading || dependenciesError) && (
              <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                {inventoryLoading ? (
                  <p className="text-sm text-muted">Loading project setup...</p>
                ) : (
                  <>
                    <h3 className="text-sm font-semibold text-white">Could not load project setup</h3>
                    <p className="mt-1 text-sm text-muted">Retry before selecting or creating the model used by this agent.</p>
                    <Button type="button" size="sm" variant="outline" className="mt-4" onClick={() => { void modelsQuery.refetch(); void credentialsQuery.refetch() }}>Retry</Button>
                  </>
                )}
              </section>
            )}

            {step === 'connect-provider' && (
              <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                <div className="mb-5">
                  <div className="flex items-center gap-2 text-xs text-primary-light"><Key className="h-3.5 w-3.5" />Provider connection</div>
                  <h3 className="mt-2 text-sm font-semibold text-white">Connect your AI provider</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">Choose where the agent model will run, then add the API key for this Project.</p>
                </div>

                <div className="space-y-4">
                  <div className="grid gap-2 sm:grid-cols-3">
                    {providerOptions.map((option) => {
                      const selected = credentialProvider === option.value
                      return (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => setCredentialProvider(option.value)}
                          className={`rounded-xl border p-3 text-left transition-colors ${selected ? 'border-primary/55 bg-primary/8' : 'border-border/85 bg-background/55 hover:border-primary/30'}`}
                        >
                          <span className="flex items-center justify-between gap-2">
                            <span className="text-sm font-medium text-white">{option.label}</span>
                            {selected && <Check className="h-4 w-4 text-primary-light" />}
                          </span>
                          <span className="mt-2 block text-xs leading-5 text-muted">{option.description}</span>
                        </button>
                      )
                    })}
                  </div>

                  {credentialProvider === 'custom' && (
                    <div>
                      <label className="mb-1 block text-sm font-medium text-muted">Base URL</label>
                      <Input value={credentialBaseUrl} onChange={(event) => setCredentialBaseUrl(event.target.value)} placeholder="https://api.example.com/v1" />
                    </div>
                  )}

                  <div>
                    <label className="mb-1 block text-sm font-medium text-muted">API key</label>
                    <Input type="password" value={credentialSecret} onChange={(event) => setCredentialSecret(event.target.value)} placeholder="Paste your API key" autoComplete="new-password" />
                    <p className="mt-1 text-xs text-muted">The connection is saved to this Project and selected automatically for the next step.</p>
                  </div>
                </div>
              </section>
            )}

            {step === 'select-model' && !inventoryLoading && !dependenciesError && (
              <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                <div className="mb-5">
                  <h3 className="text-sm font-semibold text-white">Choose a model</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">Select the generation model this agent will use. Embedding models are not shown here.</p>
                </div>

                <ExistingModelList models={usableAgentModels} selectedModelId={selectedModelId} onSelect={setSelectedModelId} />

                <div className="mt-5 border-t border-border/70 pt-4">
                  <p className="text-xs text-muted">Need another model?</p>
                  <Button type="button" size="sm" variant="outline" className="mt-3" onClick={startCreateModel}>
                    <Plus className="mr-2 h-4 w-4" />
                    Set up a new model
                  </Button>
                </div>
              </section>
            )}

            {step === 'create-model' && !inventoryLoading && !dependenciesError && (
              <>
                <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                  <div className="mb-5">
                    <h3 className="text-sm font-semibold text-white">Provider connection</h3>
                    <p className="mt-1 text-xs leading-5 text-muted">The model must use an active provider connection from this Project.</p>
                  </div>

                  {activeCredentials.length === 0 ? (
                    <div className="rounded-xl border border-border/80 bg-background/55 p-4">
                      <p className="text-sm font-medium text-white">Connect a provider first</p>
                      <p className="mt-1 text-sm leading-6 text-muted">A provider connection is required before a model can be created.</p>
                      <Button type="button" size="sm" className="mt-4" onClick={startAddCredential}>Connect provider</Button>
                    </div>
                  ) : activeCredentials.length === 1 ? (
                    <div className="flex items-center justify-between gap-4 rounded-xl border border-border/85 bg-background/55 px-4 py-3">
                      <div className="min-w-0">
                        <p className="text-xs text-muted">Connected with</p>
                        <p className="mt-1 truncate text-sm font-medium text-white">{activeCredentials[0].name}</p>
                        <p className="mt-1 text-xs text-muted">{providerLabel(activeCredentials[0].provider)}</p>
                      </div>
                      <CheckCircle2 className="h-5 w-5 shrink-0 text-primary-light" />
                    </div>
                  ) : (
                    <CredentialList credentials={activeCredentials} selectedCredentialId={selectedCredentialId} onSelect={setSelectedCredentialId} />
                  )}

                  {activeCredentials.length > 0 && (
                    <Button type="button" size="sm" variant="ghost" className="mt-3 px-0" onClick={startAddCredential}>
                      <Plus className="mr-2 h-4 w-4" />
                      Add another connection
                    </Button>
                  )}
                </section>

                {selectedCredential && (
                  <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                    <div className="mb-5">
                      <h3 className="text-sm font-semibold text-white">Choose a model</h3>
                      <p className="mt-1 text-xs leading-5 text-muted">{providerLabel(selectedCredential.provider)} will be used for this reusable generation model.</p>
                    </div>

                    {shouldUseCatalog ? (
                      <CatalogModelList
                        models={availableModels}
                        selectedModelId={selectedCatalogModelId}
                        loading={availableModelsQuery.isLoading}
                        error={availableModelsQuery.isError}
                        onSelect={handleCatalogSelect}
                        onRetry={() => { void availableModelsQuery.refetch() }}
                        onManualMode={() => {
                          setManualMode(true)
                          setSelectedCatalogModelId('')
                          setModelIdentifier('')
                          setModelName('')
                        }}
                      />
                    ) : (
                      <div className="space-y-4">
                        <div>
                          <label className="mb-1 block text-sm font-medium text-muted">Model ID</label>
                          <Input value={modelIdentifier} onChange={(event) => setModelIdentifier(event.target.value)} placeholder={selectedCredential.provider === 'openrouter' ? 'openai/gpt-4o-mini' : 'deepseek-chat'} />
                        </div>
                        <div>
                          <label className="mb-1 block text-sm font-medium text-muted">Display name <span className="font-normal text-muted/70">(optional)</span></label>
                          <Input value={modelName} onChange={(event) => setModelName(event.target.value)} placeholder="Defaults to the model ID" />
                        </div>
                        {canUseCatalog && (
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            className="px-0"
                            onClick={() => {
                              setManualMode(false)
                              setSelectedCatalogModelId('')
                              setModelIdentifier('')
                              setModelName('')
                            }}
                          >
                            Browse provider models
                          </Button>
                        )}
                      </div>
                    )}
                  </section>
                )}
              </>
            )}

            {step === 'review' && selectedModel && (
              <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                <div className="mb-5">
                  <div className="flex items-center gap-2 text-xs text-primary-light"><CheckCircle2 className="h-3.5 w-3.5" />Ready to create</div>
                  <h3 className="mt-2 text-sm font-semibold text-white">Review your agent</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">Confirm the model binding. The remaining agent configuration continues in the Playground.</p>
                </div>
                <dl className="divide-y divide-border/70 rounded-xl border border-border/70 bg-background/55">
                  <div className="grid gap-1 px-4 py-3 sm:grid-cols-[140px_minmax(0,1fr)] sm:gap-4"><dt className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Agent</dt><dd className="text-sm text-white/90">{agentName.trim()}</dd></div>
                  <div className="grid gap-1 px-4 py-3 sm:grid-cols-[140px_minmax(0,1fr)] sm:gap-4"><dt className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Description</dt><dd className="text-sm text-white/90">{agentDescription.trim() || 'No description'}</dd></div>
                  <div className="grid gap-1 px-4 py-3 sm:grid-cols-[140px_minmax(0,1fr)] sm:gap-4"><dt className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Model</dt><dd className="text-sm text-white/90">{selectedModel.name}</dd></div>
                  <div className="grid gap-1 px-4 py-3 sm:grid-cols-[140px_minmax(0,1fr)] sm:gap-4"><dt className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Provider</dt><dd className="text-sm text-white/90">{providerLabel(selectedModel.provider)}</dd></div>
                  <div className="grid gap-1 px-4 py-3 sm:grid-cols-[140px_minmax(0,1fr)] sm:gap-4"><dt className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Model ID</dt><dd><code className="text-xs text-muted">{selectedModel.model}</code></dd></div>
                </dl>
                <div className="mt-5 rounded-xl border border-border/80 bg-background/60 p-4">
                  <p className="text-sm font-medium text-white">Next: Playground</p>
                  <p className="mt-1 text-xs leading-5 text-muted">Configure prompt, tools, knowledge, output contract and runtime settings after creation.</p>
                </div>
              </section>
            )}
          </main>
        </div>

        <div className="sticky bottom-0 -mx-1 mt-6 flex items-center justify-between gap-3 border-t border-border bg-surface/95 px-1 py-4 backdrop-blur">
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>Cancel</Button>
          <div className="flex gap-2">
            {step !== 'details' && (
              <Button type="button" variant="outline" onClick={goBack} disabled={busy}>
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
            )}
            {footerPrimary()}
          </div>
        </div>
      </div>
    </Dialog>
  )
}
