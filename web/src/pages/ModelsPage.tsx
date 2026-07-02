import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Cpu, DollarSign, Key, Plus, Search, ServerCog } from 'lucide-react'
import { toast } from 'sonner'

import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { AddProviderCredentialModal } from '@/features/provider-credentials/components/AddProviderCredentialModal'
import { useCredentials } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { useAvailableProviderModels, useCreateProviderModel, useProviderModels, useUpdateProviderModel } from '@/features/provider-models/hooks'
import type { AvailableProviderModel, ProviderModel } from '@/features/provider-models/types'

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  custom: 'OpenAI Compatible',
  openrouter: 'OpenRouter',
}

type Section = 'models' | 'credentials'

type PricingInfo = {
  input: number | null
  output: number | null
  currency: string
  configured: boolean
}

interface ModelFormState {
  name: string
  credentialId: string
  model: string
  selectedCatalogModelId: string
  manualMode: boolean
  status: string
  inputCostPer1M: string
  outputCostPer1M: string
  currency: string
}

function providerLabel(provider?: string | null) {
  return provider ? providerLabels[provider] || provider : 'Unknown provider'
}

function metadataOf(item?: { metadata?: Record<string, unknown> | Record<string, string> | null } | null): Record<string, unknown> {
  return (item?.metadata || {}) as Record<string, unknown>
}

function numberOrNull(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function pricingOf(model?: ProviderModel | null): PricingInfo {
  const metadata = metadataOf(model)
  const raw = typeof metadata.pricing === 'object' && metadata.pricing !== null ? metadata.pricing as Record<string, unknown> : metadata
  const input = numberOrNull(raw.input_cost_per_1m_tokens ?? raw.input_cost_usd_per_1m_tokens ?? raw.prompt_cost_per_1m_tokens ?? raw.prompt_cost_usd_per_1m_tokens ?? raw.input ?? raw.prompt)
  const output = numberOrNull(raw.output_cost_per_1m_tokens ?? raw.output_cost_usd_per_1m_tokens ?? raw.completion_cost_per_1m_tokens ?? raw.completion_cost_usd_per_1m_tokens ?? raw.output ?? raw.completion)
  const currency = typeof raw.currency === 'string' && raw.currency.trim() ? raw.currency.trim().toUpperCase() : 'USD'
  return { input, output, currency, configured: input !== null && output !== null }
}

function priceText(value: number | null, currency: string) {
  return value === null ? 'not set' : `${currency} ${value.toLocaleString(undefined, { maximumFractionDigits: 8 })}`
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : 'Never'
}

function isArchived(item?: { status?: string | null } | null) {
  return item?.status === 'archived'
}

function parsePrice(value: string): number | null {
  if (!value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function modelToForm(model: ProviderModel | null, credentials: ProviderCredential[]): ModelFormState {
  const pricing = pricingOf(model)
  return {
    name: model?.name || '',
    credentialId: model?.provider_credential_id || credentials[0]?.id || '',
    model: model?.model || '',
    selectedCatalogModelId: '',
    manualMode: Boolean(model),
    status: model?.status || 'active',
    inputCostPer1M: pricing.input !== null ? String(pricing.input) : '',
    outputCostPer1M: pricing.output !== null ? String(pricing.output) : '',
    currency: pricing.currency || 'USD',
  }
}

function catalogPricing(model: AvailableProviderModel | null): { input: number | null; output: number | null } {
  return {
    input: numberOrNull(model?.input_cost_per_1m_tokens),
    output: numberOrNull(model?.output_cost_per_1m_tokens),
  }
}

function buildModelMetadata(selectedModel: ProviderModel | null, form: ModelFormState, catalogModel: AvailableProviderModel | null) {
  const input = parsePrice(form.inputCostPer1M)
  const output = parsePrice(form.outputCostPer1M)
  const base = metadataOf(selectedModel)
  return {
    ...base,
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
      currency: (form.currency || 'USD').trim().toUpperCase(),
      billing_unit: 'per_1m_tokens',
      source: catalogModel ? 'provider_catalog' : 'manual',
    },
    provider_model_raw: catalogModel?.raw ?? base.provider_model_raw,
  }
}

function getCredentialLabel(credential?: ProviderCredential | null) {
  return credential ? `${credential.name} · ${providerLabel(credential.provider)}` : 'Credential missing'
}

function ModelCard({ model, credential, onClick }: { model: ProviderModel; credential?: ProviderCredential | null; onClick: () => void }) {
  const pricing = pricingOf(model)
  return (
    <button type="button" onClick={onClick} className="group flex min-h-[250px] flex-col rounded-xl border border-border/90 bg-surface/70 p-6 text-left transition-colors hover:border-primary/35 hover:bg-surface/85">
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
        <span className="flex min-w-0 items-center gap-2"><Key className="h-3.5 w-3.5 shrink-0" /><span className="truncate">{getCredentialLabel(credential)}</span></span>
        <span className="flex min-w-0 items-center gap-2"><DollarSign className="h-3.5 w-3.5 shrink-0" /><span className="truncate">In {priceText(pricing.input, pricing.currency)} / 1M · Out {priceText(pricing.output, pricing.currency)} / 1M</span></span>
        <span>Created · {formatDate(model.created_at)}</span>
      </span>
    </button>
  )
}

function CredentialCard({ credential, modelCount, onClick }: { credential: ProviderCredential; modelCount: number; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="group flex min-h-[220px] flex-col rounded-xl border border-border/90 bg-surface/70 p-6 text-left transition-colors hover:border-primary/35 hover:bg-surface/85">
      <span className="flex items-start justify-between gap-3">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background text-primary-light"><Key className="h-5 w-5" /></span>
        <StatusBadge status={credential.status || 'active'} />
      </span>
      <span className="mt-6 block min-w-0">
        <span className="block truncate text-base font-semibold text-white">{credential.name}</span>
        <span className="mt-2 block truncate text-xs text-muted">{providerLabel(credential.provider)}</span>
      </span>
      <span className="my-5 block h-px bg-border/80" />
      <span className="grid gap-2 text-xs text-muted">
        <span>Models attached · {modelCount}</span>
        <span>Base URL · {String(metadataOf(credential).base_url || 'default provider endpoint')}</span>
        <span>Created · {formatDate(credential.created_at)}</span>
      </span>
    </button>
  )
}

function EmptyCreateCard({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  return (
    <button type="button" disabled={disabled} onClick={onClick} className="group flex min-h-[250px] flex-col items-center justify-center rounded-xl border border-dashed border-primary/40 bg-surface/35 p-6 text-center transition-colors hover:border-primary/60 hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-50">
      <span className="flex h-14 w-14 items-center justify-center rounded-full border border-primary/50 bg-primary/10 text-primary-light"><Plus className="h-6 w-6" /></span>
      <span className="mt-5 text-base font-semibold text-white">New model</span>
      <span className="mt-2 max-w-[260px] text-sm leading-6 text-muted">Create a reusable model from an OpenAI, OpenAI-compatible or OpenRouter credential.</span>
    </button>
  )
}

function ModelDialog({ open, onClose, projectId, credentials, selectedModel }: { open: boolean; onClose: () => void; projectId: string; credentials: ProviderCredential[]; selectedModel: ProviderModel | null }) {
  const createModel = useCreateProviderModel()
  const updateModel = useUpdateProviderModel()
  const usableCredentials = credentials.filter((item) => !isArchived(item) && ['openai', 'custom', 'openrouter'].includes(item.provider))
  const [form, setForm] = useState<ModelFormState>(() => modelToForm(selectedModel, usableCredentials))
  const credential = usableCredentials.find((item) => item.id === form.credentialId) || null
  const availableModelsQuery = useAvailableProviderModels(projectId, !form.manualMode ? form.credentialId : undefined)
  const availableModels = availableModelsQuery.data ?? []
  const selectedCatalogModel = availableModels.find((item) => item.id === form.selectedCatalogModelId) || null

  useEffect(() => {
    if (open) setForm(modelToForm(selectedModel, usableCredentials))
  }, [open, selectedModel, credentials.length])

  useEffect(() => {
    if (!selectedCatalogModel) return
    const pricing = catalogPricing(selectedCatalogModel)
    setForm((previous) => ({
      ...previous,
      name: previous.name.trim() ? previous.name : selectedCatalogModel.label || selectedCatalogModel.id,
      model: selectedCatalogModel.id,
      inputCostPer1M: pricing.input !== null ? String(pricing.input) : previous.inputCostPer1M,
      outputCostPer1M: pricing.output !== null ? String(pricing.output) : previous.outputCostPer1M,
      currency: previous.currency || 'USD',
    }))
  }, [selectedCatalogModel?.id])

  const setField = <K extends keyof ModelFormState>(key: K, value: ModelFormState[K]) => setForm((previous) => ({ ...previous, [key]: value }))

  const handleCredentialChange = (credentialId: string) => {
    setForm((previous) => ({ ...previous, credentialId, selectedCatalogModelId: '', model: selectedModel ? previous.model : '', name: selectedModel ? previous.name : '' }))
  }

  const handleManualMode = () => {
    setForm((previous) => ({ ...previous, manualMode: true, selectedCatalogModelId: '' }))
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    const resolvedModel = form.model.trim()
    const resolvedName = form.name.trim() || selectedCatalogModel?.label || resolvedModel
    if (!form.credentialId) return toast.error('Credential is required')
    if (!resolvedModel) return toast.error('Model is required')
    if (!resolvedName) return toast.error('Model name is required')
    const inputPrice = parsePrice(form.inputCostPer1M)
    const outputPrice = parsePrice(form.outputCostPer1M)
    if ((form.inputCostPer1M.trim() && inputPrice === null) || (form.outputCostPer1M.trim() && outputPrice === null)) return toast.error('Pricing must be a valid number')
    if ((inputPrice !== null && inputPrice < 0) || (outputPrice !== null && outputPrice < 0)) return toast.error('Pricing cannot be negative')

    const metadata = buildModelMetadata(selectedModel, { ...form, name: resolvedName, model: resolvedModel }, selectedCatalogModel)
    try {
      if (selectedModel) {
        await updateModel.mutateAsync({ id: selectedModel.id, data: { name: resolvedName, provider_credential_id: form.credentialId, model: resolvedModel, status: form.status, metadata } })
        toast.success('Model updated')
      } else {
        await createModel.mutateAsync({ project_id: projectId, provider_credential_id: form.credentialId, name: resolvedName, model: resolvedModel, metadata })
        toast.success('Model created')
      }
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save model')
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title={selectedModel ? 'Edit Model' : 'New Model'} className="max-w-2xl">
      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="rounded-xl border border-border/80 bg-background/60 p-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-surface text-primary-light"><ServerCog className="h-4 w-4" /></div>
            <div>
              <p className="text-sm font-semibold text-white">Reusable provider model</p>
              <p className="mt-1 text-xs leading-5 text-muted">Choose a credential, load the provider catalog when available, then create a reusable ProviderModel binding.</p>
            </div>
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-muted">Credential</label>
          <Select value={form.credentialId} onChange={(event) => handleCredentialChange(event.target.value)} options={usableCredentials.map((item) => ({ value: item.id, label: `${item.name} (${providerLabel(item.provider)})` }))} disabled={usableCredentials.length === 0 || Boolean(selectedModel)} />
          {credential?.metadata?.base_url && <p className="mt-1 truncate text-xs text-muted">Base URL: <code>{credential.metadata.base_url}</code></p>}
        </div>

        {!form.manualMode && (
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Model catalog</label>
            <Select
              value={form.selectedCatalogModelId}
              onChange={(event) => setField('selectedCatalogModelId', event.target.value)}
              options={[{ value: '', label: availableModelsQuery.isLoading ? 'Loading models...' : 'Select a provider model' }, ...availableModels.map((item) => ({ value: item.id, label: `${item.label} · ${item.id}` }))]}
              disabled={!form.credentialId || availableModelsQuery.isLoading || availableModels.length === 0}
            />
            {availableModelsQuery.isError && <p className="mt-2 text-xs text-amber-200">Could not load the model catalog for this credential. Use manual model entry.</p>}
            {!availableModelsQuery.isLoading && !availableModelsQuery.isError && form.credentialId && availableModels.length === 0 && <p className="mt-2 text-xs text-muted">No remote models returned for this credential.</p>}
            <Button type="button" size="sm" variant="ghost" className="mt-2" onClick={handleManualMode}>Enter model manually</Button>
          </div>
        )}

        {form.manualMode && (
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Model identifier</label>
            <Input value={form.model} onChange={(event) => setField('model', event.target.value)} placeholder={credential?.provider === 'openrouter' ? 'openai/gpt-4o-mini' : 'gpt-4o-mini'} />
            {!selectedModel && <Button type="button" size="sm" variant="ghost" className="mt-2" onClick={() => setForm((previous) => ({ ...previous, manualMode: false, model: '', selectedCatalogModelId: '' }))}>Use provider catalog</Button>}
          </div>
        )}

        <div>
          <label className="mb-1 block text-sm font-medium text-muted">Display name</label>
          <Input value={form.name} onChange={(event) => setField('name', event.target.value)} placeholder={selectedCatalogModel?.label || 'GPT-4o Mini'} />
        </div>

        <div className="rounded-xl border border-border/80 bg-background/60 p-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-surface text-primary-light"><DollarSign className="h-4 w-4" /></div>
            <div>
              <p className="text-sm font-semibold text-white">Token pricing</p>
              <p className="mt-1 text-xs leading-5 text-muted">OpenRouter catalog pricing is prefilled when available. You can override it manually.</p>
            </div>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <div><label className="mb-1 block text-sm font-medium text-muted">Input / 1M</label><Input value={form.inputCostPer1M} onChange={(event) => setField('inputCostPer1M', event.target.value)} placeholder="0.15" /></div>
            <div><label className="mb-1 block text-sm font-medium text-muted">Output / 1M</label><Input value={form.outputCostPer1M} onChange={(event) => setField('outputCostPer1M', event.target.value)} placeholder="0.60" /></div>
            <div><label className="mb-1 block text-sm font-medium text-muted">Currency</label><Input value={form.currency} onChange={(event) => setField('currency', event.target.value.toUpperCase())} placeholder="USD" /></div>
          </div>
        </div>

        {selectedModel && <div><label className="mb-1 block text-sm font-medium text-muted">Status</label><Select value={form.status} onChange={(event) => setField('status', event.target.value)} options={[{ value: 'active', label: 'Active' }, { value: 'inactive', label: 'Inactive' }, { value: 'archived', label: 'Archived' }]} /></div>}

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={createModel.isPending || updateModel.isPending} disabled={usableCredentials.length === 0}>{selectedModel ? 'Save changes' : 'Create model'}</Button>
        </div>
      </form>
    </Dialog>
  )
}

function CredentialDialog({ open, onClose, credential }: { open: boolean; onClose: () => void; credential: ProviderCredential | null }) {
  if (!credential) return null
  return (
    <Dialog open={open} onClose={onClose} title="Provider Credential" className="max-w-xl">
      <div className="space-y-4">
        <div className="rounded-xl border border-border/80 bg-background/60 p-4">
          <p className="text-sm font-semibold text-white">{credential.name}</p>
          <p className="mt-1 text-sm text-muted">{providerLabel(credential.provider)}</p>
          <p className="mt-3 truncate text-xs text-muted">Base URL: <code>{String(metadataOf(credential).base_url || 'default provider endpoint')}</code></p>
        </div>
        <p className="text-sm text-muted">Credential editing and rotation remain available through the add/edit credential modal in the playground flow. This view is intentionally read-only for now.</p>
        <div className="flex justify-end"><Button type="button" variant="outline" onClick={onClose}>Close</Button></div>
      </div>
    </Dialog>
  )
}

export default function ModelsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [section, setSection] = useState<Section>('models')
  const [query, setQuery] = useState('')
  const [showModelDialog, setShowModelDialog] = useState(false)
  const [selectedModel, setSelectedModel] = useState<ProviderModel | null>(null)
  const [showAddCredential, setShowAddCredential] = useState(false)
  const [selectedCredential, setSelectedCredential] = useState<ProviderCredential | null>(null)

  const credentialsQuery = useCredentials(projectId)
  const modelsQuery = useProviderModels(projectId)
  const credentials = credentialsQuery.data ?? []
  const models = modelsQuery.data ?? []
  const credentialsById = useMemo(() => new Map(credentials.map((item) => [item.id, item])), [credentials])
  const modelCountByCredential = useMemo(() => {
    const counts = new Map<string, number>()
    for (const model of models) {
      if (isArchived(model)) continue
      counts.set(model.provider_credential_id, (counts.get(model.provider_credential_id) || 0) + 1)
    }
    return counts
  }, [models])

  const filteredModels = models.filter((model) => {
    if (isArchived(model)) return false
    const credential = credentialsById.get(model.provider_credential_id)
    const search = `${model.name} ${model.model} ${credential?.name || ''} ${providerLabel(model.provider || credential?.provider)}`.toLowerCase()
    return search.includes(query.trim().toLowerCase())
  })

  const filteredCredentials = credentials.filter((credential) => {
    if (!['openai', 'custom', 'openrouter'].includes(credential.provider)) return false
    const search = `${credential.name} ${providerLabel(credential.provider)} ${String(metadataOf(credential).base_url || '')}`.toLowerCase()
    return search.includes(query.trim().toLowerCase())
  })

  const isLoading = credentialsQuery.isLoading || modelsQuery.isLoading
  const isError = credentialsQuery.isError || modelsQuery.isError

  const openNewModel = () => {
    setSelectedModel(null)
    setShowModelDialog(true)
  }

  const openExistingModel = (model: ProviderModel) => {
    setSelectedModel(model)
    setShowModelDialog(true)
  }

  if (!projectId) return <ErrorState message="Project not found" />
  if (isLoading) return <LoadingState message="Loading models" />
  if (isError) return <ErrorState message="Failed to load provider models" />

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">Models</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">Create reusable model bindings from OpenAI, OpenAI-compatible gateways and OpenRouter. Agents reference these bindings instead of raw model strings.</p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2">
          <button type="button" onClick={() => setSection('models')} className={`rounded-lg border px-4 py-2 text-sm ${section === 'models' ? 'border-primary/40 bg-primary/10 text-primary-light' : 'border-border bg-surface/50 text-muted hover:text-white'}`}>Models</button>
          <button type="button" onClick={() => setSection('credentials')} className={`rounded-lg border px-4 py-2 text-sm ${section === 'credentials' ? 'border-primary/40 bg-primary/10 text-primary-light' : 'border-border bg-surface/50 text-muted hover:text-white'}`}>Credentials</button>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setShowAddCredential(true)}><Key className="mr-2 h-4 w-4" />Add credential</Button>
          <Button onClick={openNewModel} disabled={credentials.length === 0}><Plus className="mr-2 h-4 w-4" />New model</Button>
        </div>
      </div>

      <div className="relative max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search models or credentials" className="pl-9" />
      </div>

      {section === 'models' ? (
        filteredModels.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <EmptyCreateCard onClick={openNewModel} disabled={credentials.length === 0} />
            {filteredModels.map((model) => <ModelCard key={model.id} model={model} credential={credentialsById.get(model.provider_credential_id)} onClick={() => openExistingModel(model)} />)}
          </div>
        ) : (
          <div className="rounded-xl border border-border/80 bg-surface/50 p-6">
            <h2 className="text-sm font-semibold text-white">No models found</h2>
            <p className="mt-1 text-sm text-muted">{credentials.length > 0 ? 'Create a model from an existing credential.' : 'Create a provider credential first, then attach models to it.'}</p>
            <div className="mt-4 flex gap-2">
              {credentials.length === 0 ? <Button variant="outline" onClick={() => setShowAddCredential(true)}>Add credential</Button> : <Button onClick={openNewModel}>New model</Button>}
            </div>
          </div>
        )
      ) : (
        filteredCredentials.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filteredCredentials.map((credential) => <CredentialCard key={credential.id} credential={credential} modelCount={modelCountByCredential.get(credential.id) || 0} onClick={() => setSelectedCredential(credential)} />)}
          </div>
        ) : (
          <div className="rounded-xl border border-border/80 bg-surface/50 p-6">
            <h2 className="text-sm font-semibold text-white">No credentials found</h2>
            <p className="mt-1 text-sm text-muted">Add an OpenAI, OpenAI-compatible or OpenRouter credential.</p>
            <Button className="mt-4" variant="outline" onClick={() => setShowAddCredential(true)}>Add credential</Button>
          </div>
        )
      )}

      <ModelDialog open={showModelDialog} onClose={() => setShowModelDialog(false)} projectId={projectId} credentials={credentials} selectedModel={selectedModel} />
      <CredentialDialog open={Boolean(selectedCredential)} onClose={() => setSelectedCredential(null)} credential={selectedCredential} />
      <AddProviderCredentialModal open={showAddCredential} onClose={() => setShowAddCredential(false)} projectId={projectId} onCredentialCreated={() => setShowAddCredential(false)} />
    </div>
  )
}
