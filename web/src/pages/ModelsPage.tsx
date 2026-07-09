import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useParams } from 'react-router-dom'
import { AlertTriangle, Check, Cpu, DollarSign, Plus, RefreshCw, Search, ServerCog, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { CreateResourceCard } from '@/components/common/CreateResourceCard'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { ProviderCredentialCreateForm } from '@/features/provider-credentials/components/ProviderCredentialCreateForm'
import { useCredentials } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import {
  useAvailableProviderModels,
  useCreateProviderModel,
  useProviderModels,
  useUpdateProviderModel,
} from '@/features/provider-models/hooks'
import type { AvailableProviderModel, ProviderModel } from '@/features/provider-models/types'
import { get } from '@/lib/api/client'

const SEARCH_THRESHOLD = 6

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  custom: 'OpenAI Compatible',
  openrouter: 'OpenRouter',
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

function providerLabel(provider?: string | null) {
  return provider ? providerLabels[provider] || provider : 'Unknown provider'
}

function metadataOf(item?: { metadata?: Record<string, unknown> | null } | null): Record<string, unknown> {
  return (item?.metadata || {}) as Record<string, unknown>
}

function isEmbeddingModel(model: ProviderModel) {
  const metadata = metadataOf(model)
  const capability = String(metadata.capability || metadata.type || '').trim().toLowerCase()
  if (capability) return capability === 'embedding' || capability === 'embeddings'
  return `${model.name} ${model.model}`.toLowerCase().includes('embed')
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

function priceText(value: number | null, currency: string) {
  return value === null ? 'not set' : `${currency} ${value.toLocaleString(undefined, { maximumFractionDigits: 8 })}`
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : 'Never'
}

function buildModelMetadata(
  selectedModel: ProviderModel | null,
  catalogModel: AvailableProviderModel | null,
  inputCost: string,
  outputCost: string,
  currency: string,
) {
  const base = metadataOf(selectedModel)
  const input = inputCost.trim() ? Number(inputCost) : null
  const output = outputCost.trim() ? Number(outputCost) : null

  return {
    ...base,
    capability: 'generation',
    source: catalogModel ? 'remote' : 'manual',
    catalog: catalogModel ? {
      provider: catalogModel.provider,
      model_id: catalogModel.id,
      label: catalogModel.label,
      owned_by: catalogModel.owned_by ?? null,
      context_window: catalogModel.context_window ?? null,
    } : base.catalog,
    capabilities: catalogModel ? {
      supports_tools: catalogModel.supports_tools ?? null,
      supports_json: catalogModel.supports_json ?? null,
      supports_streaming: catalogModel.supports_streaming ?? null,
    } : base.capabilities,
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

function ModelCard({
  model,
  credential,
  onClick,
}: {
  model: ProviderModel
  credential?: ProviderCredential | null
  onClick: () => void
}) {
  const pricing = pricingOf(model)
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex min-h-[250px] flex-col rounded-xl border border-border/90 bg-surface/70 p-6 text-left transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/35 hover:bg-surface/85 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <span className="flex items-start justify-between gap-3">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background text-primary-light"><Cpu className="h-5 w-5" /></span>
        <StatusBadge status={model.status || 'active'} />
      </span>
      <span className="mt-6 block min-w-0">
        <span className="block truncate text-base font-semibold text-white">{model.name}</span>
        <code className="mt-2 block truncate text-xs text-muted">{model.model}</code>
      </span>
      <span className="my-5 block h-px bg-border/80" />
      <span className="grid gap-2 text-xs text-muted">
        <span className="truncate">{credential ? `${credential.name} · ${providerLabel(credential.provider)}` : 'Credential missing'}</span>
        <span className="flex min-w-0 items-center gap-2"><DollarSign className="h-3.5 w-3.5 shrink-0" /><span className="truncate">In {priceText(pricing.input, pricing.currency)} / 1M · Out {priceText(pricing.output, pricing.currency)} / 1M</span></span>
        <span>Created · {formatDate(model.created_at)}</span>
      </span>
    </button>
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
      className={`flex w-full items-start justify-between gap-4 rounded-xl border px-4 py-3 text-left transition-colors ${selected ? 'border-primary/55 bg-primary/8' : 'border-border/85 bg-background/55 hover:border-primary/30 hover:bg-background/80'}`}
    >
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium text-white">{title}</span>
        <span className="mt-1 block truncate text-xs text-muted">{subtitle}</span>
      </span>
      <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${selected ? 'border-primary bg-primary text-white' : 'border-border bg-background'}`}>
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

  if (loading) return <div className="rounded-xl border border-border/80 bg-background/55 px-4 py-8 text-center text-sm text-muted">Loading generation models...</div>

  if (error) {
    return (
      <div className="rounded-xl border border-border/80 bg-background/55 p-4">
        <p className="text-sm font-medium text-white">We couldn't load models from this provider.</p>
        <p className="mt-1 text-sm text-muted">Retry discovery or enter the model ID manually.</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="outline" onClick={onRetry}><RefreshCw className="mr-2 h-4 w-4" />Retry</Button>
          <Button type="button" size="sm" variant="ghost" onClick={onManual}>Enter model ID manually</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-muted">Choose a generation model.</span>
        <Button type="button" size="sm" variant="ghost" className="h-auto px-0 py-0 text-xs" onClick={onManual}>Enter model ID manually</Button>
      </div>
      {models.length > SEARCH_THRESHOLD && (
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search models" className="pl-9" />
        </div>
      )}
      <div className="scrollbar-thin max-h-80 space-y-2 overflow-y-auto pr-1">
        {visible.length === 0 ? (
          <div className="rounded-xl border border-border/80 bg-background/55 px-4 py-8 text-center text-sm text-muted">No generation models found.</div>
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

function ModelSetupDialog({
  open,
  onClose,
  projectId,
  credentials,
  selectedModel,
  onSaved,
  onArchive,
}: {
  open: boolean
  onClose: () => void
  projectId: string
  credentials: ProviderCredential[]
  selectedModel: ProviderModel | null
  onSaved: () => void
  onArchive: (model: ProviderModel) => void
}) {
  const createModel = useCreateProviderModel()
  const updateModel = useUpdateProviderModel()

  const [createdCredential, setCreatedCredential] = useState<ProviderCredential | null>(null)
  const [step, setStep] = useState<'credential' | 'model'>('model')
  const [credentialId, setCredentialId] = useState('')
  const [catalogModelId, setCatalogModelId] = useState('')
  const [manualMode, setManualMode] = useState(false)
  const [modelId, setModelId] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [status, setStatus] = useState('active')
  const [inputCost, setInputCost] = useState('')
  const [outputCost, setOutputCost] = useState('')
  const [currency, setCurrency] = useState('USD')

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
  const busy = createModel.isPending || updateModel.isPending

  useEffect(() => {
    if (!open) return
    setCreatedCredential(null)
    setCatalogModelId('')
    if (selectedModel) {
      const pricing = pricingOf(selectedModel)
      setStep('model')
      setCredentialId(selectedModel.provider_credential_id)
      setManualMode(true)
      setModelId(selectedModel.model)
      setDisplayName(selectedModel.name)
      setStatus(selectedModel.status || 'active')
      setInputCost(pricing.input === null ? '' : String(pricing.input))
      setOutputCost(pricing.output === null ? '' : String(pricing.output))
      setCurrency(pricing.currency)
      return
    }

    setStep(usableCredentials.length === 0 ? 'credential' : 'model')
    setCredentialId(usableCredentials.length === 1 ? usableCredentials[0].id : '')
    setManualMode(false)
    setModelId('')
    setDisplayName('')
    setStatus('active')
    setInputCost('')
    setOutputCost('')
    setCurrency('USD')
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
  }, [credential?.id])

  useEffect(() => {
    if (!catalogModel) return
    setModelId(catalogModel.id)
    setDisplayName(catalogModel.label || catalogModel.id)
    setInputCost(catalogModel.input_cost_per_1m_tokens == null ? '' : String(catalogModel.input_cost_per_1m_tokens))
    setOutputCost(catalogModel.output_cost_per_1m_tokens == null ? '' : String(catalogModel.output_cost_per_1m_tokens))
  }, [catalogModel?.id])

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!credential) return toast.error('Select or connect a provider')
    const resolvedModel = modelId.trim()
    const resolvedName = displayName.trim() || catalogModel?.label || resolvedModel
    if (!resolvedModel) return toast.error('Select or enter a model')
    if (inputCost.trim() && (!Number.isFinite(Number(inputCost)) || Number(inputCost) < 0)) return toast.error('Input pricing must be a non-negative number')
    if (outputCost.trim() && (!Number.isFinite(Number(outputCost)) || Number(outputCost) < 0)) return toast.error('Output pricing must be a non-negative number')

    const metadata = buildModelMetadata(selectedModel, catalogModel, inputCost, outputCost, currency)
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
      onSaved()
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save model')
    }
  }

  return (
    <Dialog open={open} onClose={busy ? () => undefined : onClose} title={selectedModel ? 'Edit model' : step === 'credential' ? 'Connect provider' : 'New model'} className="max-h-[calc(100svh-2rem)] max-w-4xl overflow-hidden">
      {step === 'credential' && !selectedModel ? (
        <ProviderCredentialCreateForm
          projectId={projectId}
          existingCredentials={allCredentials}
          onCreated={(created) => {
            setCreatedCredential(created)
            setCredentialId(created.id)
            setStep('model')
            toast.success('Provider connected')
          }}
          onCancel={onClose}
          submitLabel="Connect and continue"
        />
      ) : (
        <form onSubmit={handleSubmit}>
          <div className="scrollbar-thin max-h-[calc(100svh-8rem)] space-y-5 overflow-y-auto pr-1">
            <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
              <div className="mb-5">
                <h3 className="text-sm font-semibold text-white">Provider connection</h3>
                <p className="mt-1 text-xs leading-5 text-muted">Choose the Project connection this generation model will use.</p>
              </div>

              {usableCredentials.length === 0 ? (
                <div className="rounded-xl border border-border/80 bg-background/55 p-4">
                  <p className="text-sm text-muted">No active provider connection is available.</p>
                  <Button type="button" size="sm" className="mt-3" onClick={() => setStep('credential')}>Connect provider</Button>
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
                <div className="space-y-2">
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

              {!selectedModel && usableCredentials.length > 0 && (
                <Button type="button" size="sm" variant="ghost" className="mt-3 px-0" onClick={() => setStep('credential')}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add another connection
                </Button>
              )}
            </section>

            {credential && (
              <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
                <div className="mb-5">
                  <h3 className="text-sm font-semibold text-white">Model</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">{selectedModel ? 'Edit the reusable generation model binding.' : `Choose a generation model from ${providerLabel(credential.provider)}.`}</p>
                </div>

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
                    }}
                  />
                ) : (
                  <div className="space-y-4">
                    <div>
                      <label className="mb-1 block text-sm font-medium text-muted">Model ID</label>
                      <Input value={modelId} onChange={(event) => setModelId(event.target.value)} placeholder="gpt-4.1-mini" />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-muted">Display name <span className="font-normal text-muted/70">(optional)</span></label>
                      <Input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Defaults to the model ID" />
                    </div>
                    {!selectedModel && canUseCatalog && (
                      <Button type="button" size="sm" variant="ghost" className="px-0" onClick={() => {
                        setManualMode(false)
                        setModelId('')
                        setDisplayName('')
                      }}>Browse provider models</Button>
                    )}
                  </div>
                )}
              </section>
            )}

            {credential && modelId.trim() && (
              <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
                <div className="mb-5">
                  <h3 className="text-sm font-semibold text-white">Pricing metadata</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">Optional costs used for estimation and trace analysis.</p>
                </div>
                <div className="grid gap-4 sm:grid-cols-3">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-muted">Input / 1M</label>
                    <Input value={inputCost} onChange={(event) => setInputCost(event.target.value)} inputMode="decimal" placeholder="Optional" />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-muted">Output / 1M</label>
                    <Input value={outputCost} onChange={(event) => setOutputCost(event.target.value)} inputMode="decimal" placeholder="Optional" />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-muted">Currency</label>
                    <Input value={currency} onChange={(event) => setCurrency(event.target.value)} placeholder="USD" />
                  </div>
                </div>
                {selectedModel && (
                  <div className="mt-4">
                    <label className="mb-1 block text-sm font-medium text-muted">Status</label>
                    <Select value={status} onChange={(event) => setStatus(event.target.value)} options={[{ value: 'active', label: 'Active' }, { value: 'inactive', label: 'Inactive' }]} />
                  </div>
                )}
              </section>
            )}

            {selectedModel && (
              <section className="rounded-xl border border-border/80 bg-surface/65 p-5">
                <h3 className="text-sm font-semibold text-white">Lifecycle</h3>
                <p className="mt-1 text-xs leading-5 text-muted">Archive is blocked while agents or active releases reference this model.</p>
                <Button type="button" variant="outline" size="sm" className="mt-4 text-red-200 hover:text-red-100" onClick={() => onArchive(selectedModel)}>
                  <Trash2 className="mr-2 h-4 w-4" />
                  Archive model
                </Button>
              </section>
            )}
          </div>

          <div className="mt-5 flex justify-end gap-2 border-t border-border pt-4">
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>Cancel</Button>
            <Button type="submit" loading={busy} disabled={!credential || !modelId.trim()}>{selectedModel ? 'Save changes' : 'Create model'}</Button>
          </div>
        </form>
      )}
    </Dialog>
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
    <Dialog open={Boolean(model)} onClose={onClose} title="Archive model" className="max-w-2xl">
      <div className="space-y-4">
        <div className="rounded-xl border border-border/80 bg-background/60 p-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-amber-400/30 bg-amber-400/10 text-amber-200"><AlertTriangle className="h-4 w-4" /></div>
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

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="button" onClick={onConfirm} disabled={blocked} loading={loading}>Archive</Button>
        </div>
      </div>
    </Dialog>
  )
}

export default function ModelsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const credentialsQuery = useCredentials(projectId)
  const modelsQuery = useProviderModels(projectId)
  const updateModel = useUpdateProviderModel()

  const [query, setQuery] = useState('')
  const [showModelDialog, setShowModelDialog] = useState(false)
  const [selectedModel, setSelectedModel] = useState<ProviderModel | null>(null)
  const [archiveModel, setArchiveModel] = useState<ProviderModel | null>(null)
  const [archiveUsage, setArchiveUsage] = useState<UsageItem[]>([])
  const [impactLoading, setImpactLoading] = useState(false)

  const credentials = credentialsQuery.data ?? []
  const models = modelsQuery.data ?? []
  const credentialsById = useMemo(() => new Map(credentials.map((credential) => [credential.id, credential])), [credentials])
  const generationModels = useMemo(
    () => models.filter((model) => model.status !== 'archived' && !isEmbeddingModel(model)),
    [models],
  )
  const normalizedQuery = query.trim().toLowerCase()
  const visibleModels = useMemo(() => {
    if (!normalizedQuery) return generationModels
    return generationModels.filter((model) => {
      const credential = credentialsById.get(model.provider_credential_id)
      return `${model.name} ${model.model} ${providerLabel(model.provider || credential?.provider)} ${credential?.name || ''}`.toLowerCase().includes(normalizedQuery)
    })
  }, [generationModels, credentialsById, normalizedQuery])

  const openNewModel = () => {
    setSelectedModel(null)
    setShowModelDialog(true)
  }

  const openExistingModel = (model: ProviderModel) => {
    setSelectedModel(model)
    setShowModelDialog(true)
  }

  const prepareArchive = async (model: ProviderModel) => {
    if (!projectId) return
    setImpactLoading(true)
    try {
      const usage = await loadUsage(projectId)
      setArchiveUsage(usageForModel(model, usage.agents, usage.releases))
      setArchiveModel(model)
      setShowModelDialog(false)
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
      setSelectedModel(null)
      await modelsQuery.refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to archive model')
    }
  }

  if (!projectId) return <ErrorState message="Project not found" />
  if (credentialsQuery.isLoading || modelsQuery.isLoading) return <LoadingState message="Loading models" />
  if (credentialsQuery.isError || modelsQuery.isError) return <ErrorState message="Failed to load provider models" onRetry={() => { void credentialsQuery.refetch(); void modelsQuery.refetch() }} />

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Models</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted">Create and manage reusable generation models. Provider connections are managed centrally in Credentials.</p>
        </div>
        <Button type="button" onClick={openNewModel}>
          <Plus className="mr-2 h-4 w-4" />
          New model
        </Button>
      </div>

      <div className="relative max-w-3xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search models..." className="h-11 pl-9" />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <CreateResourceCard title="New model" description="Create a reusable generation model" onClick={openNewModel} />

        {visibleModels.map((model) => (
          <ModelCard
            key={model.id}
            model={model}
            credential={credentialsById.get(model.provider_credential_id)}
            onClick={() => openExistingModel(model)}
          />
        ))}

        {visibleModels.length === 0 && (
          <div className="flex min-h-[240px] flex-col rounded-xl border border-border/80 bg-surface/50 p-6">
            <ServerCog className="h-5 w-5 text-primary-light" />
            <p className="mt-5 text-base font-semibold text-white">{normalizedQuery ? 'No models found' : 'No generation models yet'}</p>
            <p className="mt-2 text-sm leading-6 text-muted">{normalizedQuery ? 'Adjust the search term.' : 'Create a model. If no provider connection exists, the creation flow will ask for one.'}</p>
          </div>
        )}
      </div>

      <ModelSetupDialog
        open={showModelDialog}
        onClose={() => {
          setShowModelDialog(false)
          setSelectedModel(null)
        }}
        projectId={projectId}
        credentials={credentials}
        selectedModel={selectedModel}
        onSaved={() => { void Promise.all([modelsQuery.refetch(), credentialsQuery.refetch()]) }}
        onArchive={(model) => { void prepareArchive(model) }}
      />

      <ArchiveDialog
        model={archiveModel}
        usage={archiveUsage}
        loading={impactLoading || updateModel.isPending}
        onClose={() => setArchiveModel(null)}
        onConfirm={confirmArchive}
      />
    </div>
  )
}
