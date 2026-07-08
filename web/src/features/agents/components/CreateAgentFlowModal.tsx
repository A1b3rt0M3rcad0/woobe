import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, Bot, Check, CheckCircle2, Cpu, Key, Search, ServerCog, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { StatusBadge } from '@/components/common/StatusBadge'
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

const providerOptions = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'custom', label: 'OpenAI Compatible' },
  { value: 'openrouter', label: 'OpenRouter' },
]

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  custom: 'OpenAI Compatible',
  openrouter: 'OpenRouter',
}

const defaultCredentialNames: Record<string, string> = {
  openai: 'OpenAI',
  custom: 'OpenAI Compatible Provider',
  openrouter: 'OpenRouter',
}

type Step = 'details' | 'model' | 'review'
type ModelMode = 'existing' | 'create'
type ModelView = 'setup' | 'credential'

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

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 text-xs">
      <span className="text-muted">{label}</span>
      <span className="min-w-0 truncate text-right text-white/90">{value}</span>
    </div>
  )
}

function ExistingModelPicker({
  models,
  selectedModelId,
  onSelect,
}: {
  models: ProviderModel[]
  selectedModelId: string
  onSelect: (modelId: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const selectedModel = models.find((item) => item.id === selectedModelId) || null
  const filteredModels = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return models
    return models.filter((item) => `${item.name} ${item.model} ${providerLabel(item.provider)}`.toLowerCase().includes(normalized))
  }, [models, query])

  return (
    <div
      className="relative"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false)
      }}
    >
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex min-h-14 w-full items-center justify-between gap-3 rounded-xl border border-border bg-background/70 px-4 py-3 text-left transition-colors hover:border-primary/40 focus:border-primary/60 focus:outline-none focus:ring-1 focus:ring-primary/40"
      >
        <span className="min-w-0">
          {selectedModel ? (
            <>
              <span className="block truncate text-sm font-medium text-white">{selectedModel.name}</span>
              <span className="mt-1 block truncate text-xs text-muted">{providerLabel(selectedModel.provider)} · {selectedModel.model}</span>
            </>
          ) : (
            <span className="text-sm text-muted">Search or select an existing model</span>
          )}
        </span>
        <Search className="h-4 w-4 shrink-0 text-muted" />
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-50 overflow-hidden rounded-xl border border-border bg-background shadow-2xl">
          <div className="border-b border-border/70 p-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Escape') setOpen(false)
                }}
                placeholder="Search models"
                className="h-9 w-full rounded-lg border border-border bg-transparent pl-9 pr-3 text-sm text-white outline-none placeholder:text-muted focus:border-primary/60 focus:ring-1 focus:ring-primary/40"
                autoFocus
              />
            </div>
          </div>
          <div className="scrollbar-thin max-h-72 overflow-y-auto">
            {filteredModels.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-muted">No active models found.</div>
            ) : filteredModels.map((model) => {
              const selected = model.id === selectedModelId
              return (
                <button
                  key={model.id}
                  type="button"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => {
                    onSelect(model.id)
                    setOpen(false)
                    setQuery('')
                  }}
                  className={`grid w-full gap-1 border-b border-border/60 px-4 py-3 text-left transition-colors last:border-b-0 ${selected ? 'bg-primary/5' : 'hover:bg-surface/70'}`}
                >
                  <span className="flex min-w-0 items-center justify-between gap-3">
                    <span className="truncate text-sm font-medium text-white">{model.name}</span>
                    {selected && <Check className="h-4 w-4 shrink-0 text-primary-light" />}
                  </span>
                  <span className="truncate text-xs text-muted">{providerLabel(model.provider)} · {model.model}</span>
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function CatalogPicker({
  models,
  selectedModelId,
  loading,
  error,
  onSelect,
  onManualMode,
}: {
  models: AvailableProviderModel[]
  selectedModelId: string
  loading: boolean
  error: boolean
  onSelect: (model: AvailableProviderModel) => void
  onManualMode: () => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const selectedModel = models.find((item) => item.id === selectedModelId) || null
  const filteredModels = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return models
    return models.filter((item) => `${item.label} ${item.id} ${item.provider} ${item.owned_by || ''}`.toLowerCase().includes(normalized))
  }, [models, query])
  const visibleModels = filteredModels.slice(0, 80)

  return (
    <div
      className="relative"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false)
      }}
    >
      <div className="mb-1 flex items-center justify-between gap-3">
        <label className="block text-sm font-medium text-muted">Provider model</label>
        <Button type="button" size="sm" variant="ghost" className="h-auto px-0 py-0 text-xs" onClick={onManualMode}>Enter manually</Button>
      </div>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-10 w-full items-center justify-between gap-3 rounded-lg border border-border bg-transparent px-3 text-left text-sm shadow-sm transition-colors hover:border-primary/40 focus:border-primary/60 focus:outline-none focus:ring-1 focus:ring-primary/40"
      >
        <span className="min-w-0 truncate text-white">{selectedModel?.label || 'Search or select provider model'}</span>
        <Search className="h-4 w-4 shrink-0 text-muted" />
      </button>
      {selectedModel && <code className="mt-1 block truncate text-xs text-muted">{selectedModel.id}</code>}

      {open && (
        <div className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-50 overflow-hidden rounded-xl border border-border bg-background shadow-2xl">
          <div className="border-b border-border/70 p-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Escape') setOpen(false)
                }}
                placeholder="Search provider models"
                className="h-9 w-full rounded-lg border border-border bg-transparent pl-9 pr-3 text-sm text-white outline-none placeholder:text-muted focus:border-primary/60 focus:ring-1 focus:ring-primary/40"
                autoFocus
              />
            </div>
          </div>
          <div className="scrollbar-thin max-h-72 overflow-y-auto">
            {loading ? (
              <div className="px-4 py-8 text-center text-sm text-muted">Loading provider models...</div>
            ) : error ? (
              <div className="px-4 py-8 text-center text-sm text-muted">Could not load provider models. Use manual entry.</div>
            ) : visibleModels.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-muted">No models found.</div>
            ) : visibleModels.map((model) => {
              const selected = model.id === selectedModelId
              return (
                <button
                  key={model.id}
                  type="button"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => {
                    onSelect(model)
                    setOpen(false)
                    setQuery('')
                  }}
                  className={`grid w-full gap-1 border-b border-border/60 px-4 py-3 text-left transition-colors last:border-b-0 ${selected ? 'bg-primary/5' : 'hover:bg-surface/70'}`}
                >
                  <span className="flex min-w-0 items-center justify-between gap-3">
                    <span className="truncate text-sm font-medium text-white">{model.label}</span>
                    {selected && <Check className="h-4 w-4 shrink-0 text-primary-light" />}
                  </span>
                  <code className="block truncate text-xs text-muted">{model.id}</code>
                </button>
              )
            })}
          </div>
        </div>
      )}
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
  const [modelMode, setModelMode] = useState<ModelMode>('existing')
  const [modelView, setModelView] = useState<ModelView>('setup')
  const [createdCredential, setCreatedCredential] = useState<ProviderCredential | null>(null)
  const [createdModel, setCreatedModel] = useState<ProviderModel | null>(null)

  const [credentialProvider, setCredentialProvider] = useState('openai')
  const [credentialName, setCredentialName] = useState(defaultCredentialNames.openai)
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

  const models = useMemo(() => {
    const source = modelsQuery.data ?? []
    if (!createdModel || source.some((item) => item.id === createdModel.id)) return source
    return [...source, createdModel]
  }, [modelsQuery.data, createdModel])

  const activeCredentials = useMemo(
    () => credentials.filter((credential) => credential.status !== 'archived' && credential.status !== 'revoked' && ['openai', 'custom', 'openrouter'].includes(credential.provider)),
    [credentials],
  )
  const activeModels = useMemo(() => models.filter((model) => model.status === 'active'), [models])
  const selectedModel = activeModels.find((model) => model.id === selectedModelId) || createdModel || null
  const selectedCredential = activeCredentials.find((credential) => credential.id === selectedCredentialId) || createdCredential || null
  const canUseCatalog = supportsModelCatalog(selectedCredential)
  const shouldUseCatalog = canUseCatalog && !manualMode
  const availableModelsQuery = useAvailableProviderModels(projectId, shouldUseCatalog ? selectedCredentialId : undefined)
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
    setModelMode('existing')
    setModelView('setup')
    setCreatedCredential(null)
    setCreatedModel(null)
    setCredentialProvider('openai')
    setCredentialName(defaultCredentialNames.openai)
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
    setModelName((current) => current.trim() ? current : selectedCatalogModel.label || selectedCatalogModel.id)
  }, [selectedCatalogModel?.id])

  useEffect(() => {
    setCredentialName(defaultCredentialNames[credentialProvider] || '')
    if (credentialProvider !== 'custom') setCredentialBaseUrl('')
  }, [credentialProvider])

  const stepIndex = step === 'details' ? 1 : step === 'model' ? 2 : 3
  const dependenciesError = modelsQuery.isError || credentialsQuery.isError
  const busy = createCredential.isPending || createModel.isPending || createAgent.isPending

  const startModelStep = () => {
    if (!agentName.trim()) {
      toast.error('Agent name is required')
      return
    }
    setStep('model')
    if (activeModels.length === 0) {
      setModelMode('create')
      setModelView(activeCredentials.length === 0 ? 'credential' : 'setup')
    }
  }

  const startCreateModel = () => {
    setModelMode('create')
    setModelView(activeCredentials.length === 0 ? 'credential' : 'setup')
    if (!selectedCredentialId && activeCredentials[0]) setSelectedCredentialId(activeCredentials[0].id)
  }

  const handleCredentialSubmit = async () => {
    if (!credentialName.trim()) return toast.error('Credential name is required')
    if (!credentialSecret.trim()) return toast.error('API key is required')
    if (credentialProvider === 'custom' && !credentialBaseUrl.trim()) return toast.error('Base URL is required for OpenAI Compatible providers')

    try {
      const credential = await createCredential.mutateAsync({
        project_id: projectId,
        provider: credentialProvider,
        name: credentialName.trim(),
        secret: credentialSecret.trim(),
        metadata: buildCredentialMetadata(credentialProvider, credentialBaseUrl),
      })
      setCreatedCredential(credential)
      setSelectedCredentialId(credential.id)
      setCredentialSecret('')
      setModelView('setup')
      toast.success('Credential added')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save credential')
    }
  }

  const handleCatalogSelect = (model: AvailableProviderModel) => {
    setSelectedCatalogModelId(model.id)
    setModelIdentifier(model.id)
    setModelName((current) => current.trim() ? current : model.label || model.id)
  }

  const handleCreateModel = async () => {
    if (!selectedCredential) return toast.error('Select or create a provider credential')
    const resolvedModel = modelIdentifier.trim()
    const resolvedName = modelName.trim() || selectedCatalogModel?.label || resolvedModel
    if (!resolvedModel) return toast.error('Model is required')
    if (!resolvedName) return toast.error('Model name is required')

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
      setModelMode('existing')
      setStep('review')
      toast.success('Model created')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create model')
    }
  }

  const continueWithExistingModel = () => {
    if (!selectedModel) {
      toast.error('Select an active model')
      return
    }
    setStep('review')
  }

  const handleCreateAgent = async () => {
    if (!agentName.trim()) return toast.error('Agent name is required')
    if (!selectedModel) return toast.error('Select a reusable model')

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
      setStep('model')
      return
    }
    if (step === 'model' && modelMode === 'create' && modelView === 'credential' && activeCredentials.length > 0) {
      setModelView('setup')
      return
    }
    if (step === 'model' && modelMode === 'create' && modelView === 'setup' && activeModels.length > 0) {
      setModelMode('existing')
      return
    }
    if (step === 'model') setStep('details')
  }

  const footerPrimary = () => {
    if (step === 'details') {
      return (
        <Button type="button" onClick={startModelStep}>
          Continue
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      )
    }
    if (step === 'model' && modelMode === 'existing') {
      return <Button type="button" onClick={continueWithExistingModel} disabled={!selectedModel}>Continue</Button>
    }
    if (step === 'model' && modelView === 'credential') {
      return <Button type="button" onClick={handleCredentialSubmit} loading={createCredential.isPending}>Connect provider</Button>
    }
    if (step === 'model') {
      return <Button type="button" onClick={handleCreateModel} loading={createModel.isPending}>Create model</Button>
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
        <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="space-y-4 lg:sticky lg:top-0 lg:self-start">
            <section className="rounded-xl border border-border/90 bg-surface/70 p-4">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-background text-primary-light">
                <Bot className="h-5 w-5" />
              </div>
              <div className="mt-5 min-w-0">
                <h3 className="truncate text-base font-semibold text-white">{agentName.trim() || 'New agent'}</h3>
                <p className="mt-1 text-xs leading-5 text-muted">Set up the minimum dependencies, then continue configuration in the Playground.</p>
              </div>
            </section>

            <section className="rounded-xl border border-border/90 bg-background/60 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Progress</p>
              <div className="mt-4 space-y-4">
                <StepItem index={1} label="Agent details" active={step === 'details'} completed={stepIndex > 1} />
                <StepItem index={2} label="Model setup" active={step === 'model'} completed={stepIndex > 2} />
                <StepItem index={3} label="Review" active={step === 'review'} completed={false} />
              </div>
            </section>

            <section className="rounded-xl border border-border/90 bg-background/60 p-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Current setup</p>
              <div className="mt-4 space-y-3">
                <SummaryRow label="Agent" value={agentName.trim() || 'Not named'} />
                <SummaryRow label="Model" value={selectedModel?.name || 'Not selected'} />
                <SummaryRow label="Provider" value={selectedModel ? providerLabel(selectedModel.provider) : 'Not selected'} />
              </div>
            </section>
          </aside>

          <main className="space-y-5">
            {step === 'details' && (
              <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
                <div className="mb-5">
                  <h3 className="text-sm font-semibold text-white">Agent details</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">Start with identity only. Prompt, tools, knowledge and output configuration stay in the Playground.</p>
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

            {step === 'model' && (modelsQuery.isLoading || credentialsQuery.isLoading) && (
              <section className="rounded-xl border border-border/80 bg-surface/65 p-8 text-center text-sm text-muted">Loading project model setup...</section>
            )}

            {step === 'model' && !modelsQuery.isLoading && !credentialsQuery.isLoading && dependenciesError && (
              <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
                <h3 className="text-sm font-semibold text-white">Could not load project model setup</h3>
                <p className="mt-1 text-sm text-muted">Retry before selecting or creating the model used by this agent.</p>
                <Button type="button" size="sm" variant="outline" className="mt-4" onClick={() => { void modelsQuery.refetch(); void credentialsQuery.refetch() }}>Retry</Button>
              </section>
            )}

            {step === 'model' && !modelsQuery.isLoading && !credentialsQuery.isLoading && !dependenciesError && modelMode === 'existing' && (
              <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
                <div className="mb-5">
                  <h3 className="text-sm font-semibold text-white">Choose a reusable model</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">Agents reference active provider models instead of raw credentials or model strings.</p>
                </div>
                {activeModels.length > 0 ? (
                  <div className="space-y-4">
                    <ExistingModelPicker models={activeModels} selectedModelId={selectedModelId} onSelect={setSelectedModelId} />
                    {selectedModel && (
                      <div className="rounded-xl border border-border/80 bg-background/60 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-white">{selectedModel.name}</p>
                            <p className="mt-1 truncate text-xs text-muted">{providerLabel(selectedModel.provider)} · {selectedModel.model}</p>
                          </div>
                          <StatusBadge status={selectedModel.status} />
                        </div>
                      </div>
                    )}
                    <div className="border-t border-border/70 pt-4">
                      <Button type="button" variant="outline" onClick={startCreateModel}>
                        <ServerCog className="mr-2 h-4 w-4" />
                        Create new model
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-xl border border-border/80 bg-background/60 p-5">
                    <div className="flex items-start gap-3">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-surface text-primary-light">
                        <Cpu className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-white">No active model is configured yet</p>
                        <p className="mt-1 text-sm leading-6 text-muted">Set up a provider credential and reusable model without leaving this flow.</p>
                        <Button type="button" size="sm" className="mt-4" onClick={startCreateModel}>Set up first model</Button>
                      </div>
                    </div>
                  </div>
                )}
              </section>
            )}

            {step === 'model' && !modelsQuery.isLoading && !credentialsQuery.isLoading && !dependenciesError && modelMode === 'create' && modelView === 'credential' && (
              <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
                <div className="mb-5">
                  <div className="flex items-center gap-2 text-xs text-primary-light"><Key className="h-3.5 w-3.5" />Provider connection</div>
                  <h3 className="mt-2 text-sm font-semibold text-white">Connect your AI provider</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">The credential is saved to this Project and selected automatically for the new model.</p>
                </div>
                <div className="space-y-4">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-muted">Provider</label>
                    <Select value={credentialProvider} onChange={(event) => setCredentialProvider(event.target.value)} options={providerOptions} />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-muted">Credential name</label>
                    <Input value={credentialName} onChange={(event) => setCredentialName(event.target.value)} placeholder="Production OpenAI" />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-muted">API key</label>
                    <Input type="password" value={credentialSecret} onChange={(event) => setCredentialSecret(event.target.value)} placeholder="Paste your API key" autoComplete="new-password" />
                  </div>
                  {credentialProvider === 'custom' && (
                    <div>
                      <label className="mb-1 block text-sm font-medium text-muted">Base URL</label>
                      <Input value={credentialBaseUrl} onChange={(event) => setCredentialBaseUrl(event.target.value)} placeholder="https://api.example.com/v1" />
                      <p className="mt-1 text-xs text-muted">OpenAI-compatible providers use a manual model identifier in the next step.</p>
                    </div>
                  )}
                  {credentialProvider === 'openrouter' && (
                    <p className="rounded-lg border border-border bg-background p-3 text-xs text-muted">OpenRouter uses <code>{OPENROUTER_BASE_URL}</code> automatically.</p>
                  )}
                </div>
              </section>
            )}

            {step === 'model' && !modelsQuery.isLoading && !credentialsQuery.isLoading && !dependenciesError && modelMode === 'create' && modelView === 'setup' && (
              <>
                <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
                  <div className="mb-5">
                    <h3 className="text-sm font-semibold text-white">Provider credential</h3>
                    <p className="mt-1 text-xs leading-5 text-muted">Choose the connection this reusable model will use.</p>
                  </div>
                  {activeCredentials.length > 0 ? (
                    <div className="space-y-3">
                      <Select
                        value={selectedCredentialId}
                        onChange={(event) => setSelectedCredentialId(event.target.value)}
                        options={activeCredentials.map((credential) => ({ value: credential.id, label: `${credential.name} (${providerLabel(credential.provider)})` }))}
                        placeholder="Select a credential"
                      />
                      <Button type="button" size="sm" variant="outline" onClick={() => setModelView('credential')}>
                        <Key className="mr-2 h-4 w-4" />
                        Add another credential
                      </Button>
                    </div>
                  ) : (
                    <div className="rounded-xl border border-border/80 bg-background/60 p-4">
                      <p className="text-sm text-muted">No active provider credential is available.</p>
                      <Button type="button" size="sm" className="mt-3" onClick={() => setModelView('credential')}>Connect provider</Button>
                    </div>
                  )}
                </section>

                {selectedCredential && (
                  <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
                    <div className="mb-5 flex items-start justify-between gap-3">
                      <div>
                        <h3 className="text-sm font-semibold text-white">Model</h3>
                        <p className="mt-1 text-xs leading-5 text-muted">Choose from the provider catalog when available, or enter the identifier manually.</p>
                      </div>
                      <span className="rounded-full border border-border bg-background px-2.5 py-1 text-xs text-muted">{providerLabel(selectedCredential.provider)}</span>
                    </div>
                    <div className="space-y-4">
                      {shouldUseCatalog && (
                        <CatalogPicker
                          models={availableModels}
                          selectedModelId={selectedCatalogModelId}
                          loading={availableModelsQuery.isLoading}
                          error={availableModelsQuery.isError}
                          onSelect={handleCatalogSelect}
                          onManualMode={() => {
                            setManualMode(true)
                            setSelectedCatalogModelId('')
                            setModelIdentifier('')
                            setModelName('')
                          }}
                        />
                      )}

                      {(manualMode || !canUseCatalog) && (
                        <div>
                          <label className="mb-1 block text-sm font-medium text-muted">Model identifier</label>
                          <Input value={modelIdentifier} onChange={(event) => setModelIdentifier(event.target.value)} placeholder={selectedCredential.provider === 'openrouter' ? 'openai/gpt-4o-mini' : 'deepseek-v4-flash'} />
                          {canUseCatalog && (
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              className="mt-2"
                              onClick={() => {
                                setManualMode(false)
                                setSelectedCatalogModelId('')
                                setModelIdentifier('')
                                setModelName('')
                              }}
                            >
                              Use provider catalog
                            </Button>
                          )}
                        </div>
                      )}

                      <div>
                        <label className="mb-1 block text-sm font-medium text-muted">Display name</label>
                        <Input value={modelName} onChange={(event) => setModelName(event.target.value)} placeholder={selectedCatalogModel?.label || 'GPT-4.1 Mini'} />
                      </div>
                    </div>
                  </section>
                )}
              </>
            )}

            {step === 'review' && selectedModel && (
              <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
                <div className="mb-5">
                  <div className="flex items-center gap-2 text-xs text-primary-light"><CheckCircle2 className="h-3.5 w-3.5" />Ready to create</div>
                  <h3 className="mt-2 text-sm font-semibold text-white">Review</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">The agent will be created with a stable reusable model binding and then opened in the Playground.</p>
                </div>
                <dl className="divide-y divide-border/70 rounded-xl border border-border/70 bg-background/55">
                  <div className="grid gap-1 px-4 py-3 sm:grid-cols-[140px_minmax(0,1fr)] sm:gap-4"><dt className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Agent</dt><dd className="text-sm text-white/90">{agentName.trim()}</dd></div>
                  <div className="grid gap-1 px-4 py-3 sm:grid-cols-[140px_minmax(0,1fr)] sm:gap-4"><dt className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Description</dt><dd className="text-sm text-white/90">{agentDescription.trim() || 'No description'}</dd></div>
                  <div className="grid gap-1 px-4 py-3 sm:grid-cols-[140px_minmax(0,1fr)] sm:gap-4"><dt className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Model</dt><dd className="text-sm text-white/90">{selectedModel.name}</dd></div>
                  <div className="grid gap-1 px-4 py-3 sm:grid-cols-[140px_minmax(0,1fr)] sm:gap-4"><dt className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Identifier</dt><dd><code className="text-xs text-muted">{selectedModel.model}</code></dd></div>
                  <div className="grid gap-1 px-4 py-3 sm:grid-cols-[140px_minmax(0,1fr)] sm:gap-4"><dt className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Provider</dt><dd className="text-sm text-white/90">{providerLabel(selectedModel.provider)}</dd></div>
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
