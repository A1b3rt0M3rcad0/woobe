import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import {
  AlertTriangle,
  Cpu,
  DollarSign,
  HelpCircle,
  Key,
  Plus,
  RefreshCw,
  Search,
  ServerCog,
  ShieldOff,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'

import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { AddProviderCredentialModal } from '@/features/provider-credentials/components/AddProviderCredentialModal'
import { useCredentials, useUpdateCredential } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { useAvailableProviderModels, useCreateProviderModel, useProviderModels, useUpdateProviderModel } from '@/features/provider-models/hooks'
import type { AvailableProviderModel, ProviderModel } from '@/features/provider-models/types'
import { get } from '@/lib/api/client'

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  custom: 'OpenAI Compatible',
  openrouter: 'OpenRouter',
}

type Section = 'models' | 'credentials'

type AgentSummary = {
  id: string
  name: string
  status?: string
  provider_model_id?: string | null
  fallback_provider_model_id?: string | null
  provider_credential_id?: string | null
  fallback_credential_id?: string | null
}

type ReleaseSummary = {
  id: string
  name?: string | null
  version?: string
  status?: string
  provider_model_id?: string | null
  fallback_provider_model_id?: string | null
  provider_credential_id?: string | null
  fallback_credential_id?: string | null
}

type UsageItem = {
  type: string
  id: string
  name?: string | null
  field?: string
  status?: string
  version?: string
}

type ConfirmState =
  | null
  | {
      kind: 'archive-model' | 'archive-credential' | 'revoke-credential'
      targetId: string
      targetName: string
      blocking: UsageItem[]
      allowWithBlocking?: boolean
      description: string
    }

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

function stringMetadata(value: Record<string, unknown>): Record<string, string> {
  const output: Record<string, string> = {}

  for (const [key, item] of Object.entries(value)) {
    if (item === undefined || item === null || item === '') continue
    output[key] = String(item)
  }

  return output
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

function Pill({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'primary' | 'warning' | 'danger' }) {
  const toneClass = tone === 'primary'
    ? 'border-primary/25 bg-primary/5 text-primary-light'
    : tone === 'warning'
      ? 'border-amber-500/25 bg-transparent text-amber-200'
      : tone === 'danger'
        ? 'border-red-500/25 bg-transparent text-red-200'
        : 'border-border/80 bg-background/70 text-muted'

  return <span className={`rounded-full border px-2.5 py-1 text-xs ${toneClass}`}>{children}</span>
}

function InfoRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 px-4 py-3 sm:grid-cols-[140px_minmax(0,1fr)] sm:gap-4">
      <dt className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">{label}</dt>
      <dd className="min-w-0 text-sm text-white/90">{children}</dd>
    </div>
  )
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

function EmptyCredentialCard({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="group flex min-h-[220px] flex-col items-center justify-center rounded-xl border border-dashed border-primary/40 bg-surface/35 p-6 text-center transition-colors hover:border-primary/60 hover:bg-primary/5">
      <span className="flex h-14 w-14 items-center justify-center rounded-full border border-primary/50 bg-primary/10 text-primary-light"><Plus className="h-6 w-6" /></span>
      <span className="mt-5 text-base font-semibold text-white">Add credential</span>
      <span className="mt-2 max-w-[260px] text-sm leading-6 text-muted">Connect OpenAI, an OpenAI-compatible endpoint or OpenRouter.</span>
    </button>
  )
}

function ModelDialog({ open, onClose, projectId, credentials, selectedModel, onArchive }: {
  open: boolean
  onClose: () => void
  projectId: string
  credentials: ProviderCredential[]
  selectedModel: ProviderModel | null
  onArchive: (model: ProviderModel) => void
}) {
  const createModel = useCreateProviderModel()
  const updateModel = useUpdateProviderModel()
  const usableCredentials = credentials.filter((item) => !isArchived(item) && item.status !== 'revoked' && ['openai', 'custom', 'openrouter'].includes(item.provider))
  const [form, setForm] = useState<ModelFormState>(() => modelToForm(selectedModel, usableCredentials))
  const credential = usableCredentials.find((item) => item.id === form.credentialId) || null
  const availableModelsQuery = useAvailableProviderModels(projectId, !form.manualMode ? form.credentialId : undefined)
  const availableModels = availableModelsQuery.data ?? []
  const selectedCatalogModel = availableModels.find((item) => item.id === form.selectedCatalogModelId) || null
  const previewPricing = {
    input: parsePrice(form.inputCostPer1M),
    output: parsePrice(form.outputCostPer1M),
    currency: (form.currency || 'USD').trim().toUpperCase(),
  }

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

  const handleSubmit = async (event: FormEvent) => {
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
    <Dialog open={open} onClose={onClose} title={selectedModel ? 'Edit Model' : 'New Model'} className="max-h-[calc(100svh-2rem)] max-w-5xl overflow-hidden">
      <form onSubmit={handleSubmit}>
        <div className="scrollbar-thin max-h-[calc(100svh-8rem)] overflow-y-auto pr-1">
          <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
            <aside className="space-y-4 lg:sticky lg:top-0 lg:self-start">
              <div className="rounded-xl border border-border/90 bg-surface/70 p-4">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-background text-primary-light">
                  <ServerCog className="h-5 w-5" />
                </div>
                <div className="mt-5 min-w-0">
                  <h3 className="truncate text-base font-semibold text-white">{form.name.trim() || selectedModel?.name || 'New provider model'}</h3>
                  <code className="mt-1 block truncate text-xs text-muted">{form.model.trim() || selectedModel?.model || 'Select or enter a model identifier'}</code>
                </div>
                <div className="mt-5 flex flex-wrap gap-2">
                  <StatusBadge status={form.status || 'active'} />
                  <Pill>{credential ? providerLabel(credential.provider) : 'No credential'}</Pill>
                </div>
                <div className="mt-5 border-t border-border/70 pt-4">
                  <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Credential</p>
                  <p className="mt-2 truncate text-xs text-muted">{getCredentialLabel(credential)}</p>
                </div>
              </div>

              <section className="rounded-xl border border-border/90 bg-background/60 p-4">
                <h3 className="text-sm font-semibold text-white">Pricing</h3>
                <p className="mt-1 text-xs leading-5 text-muted">Costs are stored as metadata for estimation and trace analysis.</p>
                <div className="mt-4 space-y-2 text-xs text-muted">
                  <div className="flex items-center justify-between gap-3"><span>Input / 1M</span><span className="text-white/90">{priceText(previewPricing.input, previewPricing.currency)}</span></div>
                  <div className="flex items-center justify-between gap-3"><span>Output / 1M</span><span className="text-white/90">{priceText(previewPricing.output, previewPricing.currency)}</span></div>
                </div>
              </section>

              {selectedModel && (
                <section className="rounded-xl border border-border/90 bg-background/60 p-4">
                  <h3 className="text-sm font-semibold text-white">Lifecycle</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">Archive is blocked while agents or active releases reference this model.</p>
                  <Button type="button" variant="outline" size="sm" className="mt-4 w-full justify-start text-red-200 hover:text-red-100" onClick={() => onArchive(selectedModel)}>
                    <Trash2 className="mr-2 h-3.5 w-3.5" />
                    Archive
                  </Button>
                </section>
              )}
            </aside>

            <main className="space-y-5">
              <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-white">Provider binding</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">Bind this reusable model to a credential and provider model identifier.</p>
                </div>
                <div className="space-y-4">
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
                </div>
              </section>

              <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-white">Model details</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">Display name, operational status and pricing metadata.</p>
                </div>
                <div className="space-y-4">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-muted">Display name</label>
                    <Input value={form.name} onChange={(event) => setField('name', event.target.value)} placeholder={selectedCatalogModel?.label || 'GPT-4o Mini'} />
                  </div>

                  {selectedModel && (
                    <div>
                      <label className="mb-1 block text-sm font-medium text-muted">Status</label>
                      <Select value={form.status} onChange={(event) => setField('status', event.target.value)} options={[{ value: 'active', label: 'Active' }, { value: 'inactive', label: 'Inactive' }, { value: 'archived', label: 'Archived' }]} />
                    </div>
                  )}

                  <div className="grid gap-4 md:grid-cols-3">
                    <div><label className="mb-1 block text-sm font-medium text-muted">Input / 1M</label><Input value={form.inputCostPer1M} onChange={(event) => setField('inputCostPer1M', event.target.value)} placeholder="0.15" /></div>
                    <div><label className="mb-1 block text-sm font-medium text-muted">Output / 1M</label><Input value={form.outputCostPer1M} onChange={(event) => setField('outputCostPer1M', event.target.value)} placeholder="0.60" /></div>
                    <div><label className="mb-1 block text-sm font-medium text-muted">Currency</label><Input value={form.currency} onChange={(event) => setField('currency', event.target.value.toUpperCase())} placeholder="USD" /></div>
                  </div>
                </div>
              </section>
            </main>
          </div>

          <div className="sticky bottom-0 -mx-1 mt-6 flex justify-end gap-2 border-t border-border bg-surface/95 px-1 py-4 backdrop-blur">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" loading={createModel.isPending || updateModel.isPending} disabled={usableCredentials.length === 0}>{selectedModel ? 'Save changes' : 'Create model'}</Button>
          </div>
        </div>
      </form>
    </Dialog>
  )
}

function CredentialDialog({ open, onClose, credential, attachedModels, onArchive, onRevoke }: {
  open: boolean
  onClose: () => void
  credential: ProviderCredential | null
  attachedModels: ProviderModel[]
  onArchive: (credential: ProviderCredential) => void
  onRevoke: (credential: ProviderCredential) => void
}) {
  const rotateCredential = useUpdateCredential()
  const [rotateSecret, setRotateSecret] = useState('')
  const [showRotateConfirm, setShowRotateConfirm] = useState(false)
  const credentialId = credential?.id

  useEffect(() => {
    if (!open) return
    setRotateSecret('')
    setShowRotateConfirm(false)
  }, [open, credentialId])

  if (!credential) return null

  const metadata = metadataOf(credential)
  const endpoint = String(metadata.base_url || 'default provider endpoint')
  const visibleModels = attachedModels.slice(0, 5)
  const hiddenModelCount = Math.max(attachedModels.length - visibleModels.length, 0)

  const handleRotateSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!rotateSecret.trim()) {
      toast.error('New credential value is required')
      return
    }
    setShowRotateConfirm(true)
  }

  const confirmRotate = async () => {
    if (!rotateSecret.trim()) return

    try {
      await rotateCredential.mutateAsync({
        id: credential.id,
        data: {
          secret: rotateSecret.trim(),
          metadata: stringMetadata({
            ...metadata,
            rotated_at: new Date().toISOString(),
          }),
        },
      })
      toast.success('Credential rotated')
      setRotateSecret('')
      setShowRotateConfirm(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to rotate credential')
    }
  }

  return (
    <>
      <Dialog open={open} onClose={onClose} title="Manage Credential" className="max-h-[calc(100svh-2rem)] max-w-5xl overflow-hidden">
        <div className="scrollbar-thin max-h-[calc(100svh-8rem)] overflow-y-auto pr-1">
          <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
            <aside className="space-y-4 lg:sticky lg:top-0 lg:self-start">
              <div className="rounded-xl border border-border/90 bg-surface/70 p-4">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-background text-primary-light">
                  <Key className="h-5 w-5" />
                </div>
                <div className="mt-5 min-w-0">
                  <h3 className="truncate text-base font-semibold text-white">{credential.name}</h3>
                  <p className="mt-1 truncate text-sm text-muted">{providerLabel(credential.provider)}</p>
                </div>
                <div className="mt-5 flex flex-wrap gap-2">
                  <StatusBadge status={credential.status || 'active'} />
                  <Pill>{attachedModels.length} models</Pill>
                </div>
                <div className="mt-5 border-t border-border/70 pt-4">
                  <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Endpoint</p>
                  <code className="mt-2 block truncate text-xs text-muted">{endpoint}</code>
                </div>
              </div>

              <form onSubmit={handleRotateSubmit} className="rounded-xl border border-border/90 bg-background/60 p-4">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-white">Rotate credential</p>
                  <div className="group relative">
                    <button
                      type="button"
                      aria-label="What does rotate credential mean?"
                      className="inline-flex h-5 w-5 items-center justify-center rounded-full text-muted transition-colors hover:bg-accent hover:text-white focus:bg-accent focus:text-white focus:outline-none"
                    >
                      <HelpCircle className="h-3.5 w-3.5" />
                    </button>
                    <div className="pointer-events-none absolute left-0 top-full z-20 mt-2 hidden w-64 rounded-lg border border-border bg-background px-3 py-2 text-xs leading-5 text-muted shadow-xl group-hover:block group-focus-within:block">
                      Rotation replaces the stored secret while preserving this credential ID. Models, agents and releases keep using the same reference.
                    </div>
                  </div>
                </div>
                <p className="mt-1 text-xs leading-5 text-muted">Paste a new secret and confirm the rotation.</p>
                <div className="mt-4 space-y-2">
                  <Input
                    type="password"
                    value={rotateSecret}
                    onChange={(event) => setRotateSecret(event.target.value)}
                    placeholder="New credential secret"
                    autoComplete="new-password"
                  />
                  <Button type="submit" className="w-full justify-start" variant="outline" size="sm" disabled={!rotateSecret.trim()}>
                    <RefreshCw className="mr-2 h-3.5 w-3.5" />
                    Rotate
                  </Button>
                </div>
              </form>

              <section className="rounded-xl border border-border/90 bg-background/60 p-4">
                <h3 className="text-sm font-semibold text-white">Lifecycle</h3>
                <p className="mt-1 text-xs leading-5 text-muted">Sensitive actions require impact confirmation.</p>
                <div className="mt-4 grid gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="justify-start text-amber-200 hover:text-amber-100"
                    onClick={() => onRevoke(credential)}
                  >
                    <ShieldOff className="mr-2 h-3.5 w-3.5" />
                    Revoke
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="justify-start text-red-200 hover:text-red-100"
                    onClick={() => onArchive(credential)}
                  >
                    <Trash2 className="mr-2 h-3.5 w-3.5" />
                    Archive
                  </Button>
                </div>
              </section>
            </aside>

            <main className="space-y-5">
              <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-white">Credential details</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">Provider identity and endpoint context used by provider models.</p>
                </div>
                <dl className="divide-y divide-border/70 rounded-xl border border-border/70 bg-background/55">
                  <InfoRow label="Name"><span className="block truncate">{credential.name}</span></InfoRow>
                  <InfoRow label="Provider"><span>{providerLabel(credential.provider)}</span></InfoRow>
                  <InfoRow label="Endpoint"><code className="block truncate text-xs text-muted">{endpoint}</code></InfoRow>
                </dl>
              </section>

              <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-white">Attached models</h3>
                    <p className="mt-1 text-xs leading-5 text-muted">Models currently using this credential.</p>
                  </div>
                  <Pill>{attachedModels.length} attached</Pill>
                </div>

                {visibleModels.length === 0 ? (
                  <div className="flex min-h-[220px] items-center justify-center rounded-xl border border-dashed border-border/80 bg-background/50 p-5 text-sm text-muted">No active models are attached to this credential.</div>
                ) : (
                  <div className="min-h-[220px] divide-y divide-border/70 rounded-xl border border-border/70 bg-background/55">
                    {visibleModels.map((model) => (
                      <div key={model.id} className="grid gap-3 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="truncate text-sm font-medium text-white">{model.name}</p>
                            <StatusBadge status={model.status || 'active'} />
                          </div>
                          <code className="mt-1 block truncate text-xs text-muted">{model.model}</code>
                        </div>
                        <span className="text-xs text-muted">{providerLabel(model.provider || credential.provider)}</span>
                      </div>
                    ))}
                  </div>
                )}
                {hiddenModelCount > 0 && <p className="mt-3 text-xs text-muted">+{hiddenModelCount} more model(s)</p>}
              </section>
            </main>
          </div>

          <div className="sticky bottom-0 -mx-1 mt-6 flex justify-end gap-2 border-t border-border bg-surface/95 px-1 py-4 backdrop-blur">
            <Button type="button" variant="outline" onClick={onClose}>Close</Button>
          </div>
        </div>
      </Dialog>

      <Dialog open={showRotateConfirm} onClose={() => setShowRotateConfirm(false)} title="Rotate credential" className="max-w-md">
        <div className="space-y-4">
          <div className="rounded-xl border border-border/80 bg-background/60 p-4">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-surface text-primary-light">
                <RefreshCw className="h-4 w-4" />
              </div>
              <div>
                <p className="text-sm font-semibold text-white">Confirm credential rotation</p>
                <p className="mt-1 text-sm leading-6 text-muted">
                  This will replace the stored secret for {credential.name}. Existing model references keep using this credential ID.
                </p>
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setShowRotateConfirm(false)}>Cancel</Button>
            <Button type="button" onClick={confirmRotate} loading={rotateCredential.isPending}>Confirm rotation</Button>
          </div>
        </div>
      </Dialog>
    </>
  )
}

function ImpactDialog({
  state,
  loading,
  onClose,
  onConfirm,
}: {
  state: ConfirmState
  loading: boolean
  onClose: () => void
  onConfirm: () => void
}) {
  if (!state) return null

  const blocked = state.blocking.length > 0 && !state.allowWithBlocking
  const isRevoke = state.kind === 'revoke-credential'

  return (
    <Dialog open={Boolean(state)} onClose={onClose} title={isRevoke ? 'Revoke credential' : 'Archive'} className="max-w-2xl">
      <div className="space-y-4">
        <div className="rounded-xl border border-border/80 bg-background/60 p-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-amber-400/30 bg-amber-400/10 text-amber-200">
              <AlertTriangle className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">{state.targetName}</p>
              <p className="mt-1 text-sm leading-6 text-muted">{state.description}</p>
            </div>
          </div>
        </div>

        {state.blocking.length > 0 && (
          <div className="rounded-xl border border-border/80 bg-surface/50 p-4">
            <p className="text-sm font-semibold text-white">Current usage</p>
            <div className="mt-3 max-h-72 space-y-2 overflow-auto scrollbar-thin">
              {state.blocking.map((item, index) => (
                <div
                  key={`${item.type}-${item.id}-${item.field}-${index}`}
                  className="rounded-lg border border-border/70 bg-background/60 p-3 text-xs text-muted"
                >
                  <p className="font-medium text-white">
                    {item.type} · {item.name || item.version || item.id}
                  </p>
                  <p className="mt-1">
                    field: {item.field || 'reference'} · status: {item.status || 'unknown'}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {blocked && (
          <p className="text-sm text-amber-200">
            Archive is blocked. Remove these references first.
          </p>
        )}

        {isRevoke && (
          <p className="text-sm text-red-200">
            Revoking will stop runtime calls that depend on this credential.
          </p>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Close</Button>
          <Button
            onClick={onConfirm}
            disabled={blocked}
            loading={loading}
            variant={isRevoke ? 'destructive' : 'default'}
          >
            {isRevoke ? 'Confirm revoke' : 'Confirm archive'}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}

async function loadUsage(projectId: string) {
  const baseAgents = await get<AgentSummary[]>('/ai/agents', {
    params: { project_id: projectId },
  })

  const agents = await Promise.all(
    baseAgents.map(async (agent) =>
      get<AgentSummary>(`/ai/agents/${agent.id}`).catch(() => agent),
    ),
  )

  const releaseGroups = await Promise.all(
    agents.map(async (agent) =>
      get<ReleaseSummary[]>(`/ai/agents/${agent.id}/releases`).catch(() => []),
    ),
  )

  return {
    agents,
    releases: releaseGroups.flat(),
  }
}

function blockingForModel(
  model: ProviderModel,
  agents: AgentSummary[],
  releases: ReleaseSummary[],
): UsageItem[] {
  const items: UsageItem[] = []

  for (const agent of agents) {
    if (agent.status === 'archived') continue

    if (agent.provider_model_id === model.id) {
      items.push({
        type: 'agent',
        id: agent.id,
        name: agent.name,
        field: 'provider_model_id',
        status: agent.status,
      })
    }

    if (agent.fallback_provider_model_id === model.id) {
      items.push({
        type: 'agent',
        id: agent.id,
        name: agent.name,
        field: 'fallback_provider_model_id',
        status: agent.status,
      })
    }
  }

  for (const release of releases) {
    if (!['draft', 'staging', 'production'].includes(release.status || '')) continue

    if (release.provider_model_id === model.id) {
      items.push({
        type: 'release',
        id: release.id,
        name: release.name,
        field: 'provider_model_id',
        status: release.status,
        version: release.version,
      })
    }

    if (release.fallback_provider_model_id === model.id) {
      items.push({
        type: 'release',
        id: release.id,
        name: release.name,
        field: 'fallback_provider_model_id',
        status: release.status,
        version: release.version,
      })
    }
  }

  return items
}

function blockingForCredential(
  credential: ProviderCredential,
  models: ProviderModel[],
  agents: AgentSummary[],
  releases: ReleaseSummary[],
): UsageItem[] {
  const items: UsageItem[] = []

  const modelIds = new Set(
    models
      .filter((model) => model.provider_credential_id === credential.id && !isArchived(model))
      .map((model) => model.id),
  )

  for (const model of models) {
    if (model.provider_credential_id === credential.id && !isArchived(model)) {
      items.push({
        type: 'provider_model',
        id: model.id,
        name: model.name,
        field: 'provider_credential_id',
        status: model.status,
      })
    }
  }

  for (const agent of agents) {
    if (agent.status === 'archived') continue

    if (agent.provider_credential_id === credential.id) {
      items.push({
        type: 'agent',
        id: agent.id,
        name: agent.name,
        field: 'provider_credential_id',
        status: agent.status,
      })
    }

    if (agent.fallback_credential_id === credential.id) {
      items.push({
        type: 'agent',
        id: agent.id,
        name: agent.name,
        field: 'fallback_credential_id',
        status: agent.status,
      })
    }

    if (agent.provider_model_id && modelIds.has(agent.provider_model_id)) {
      items.push({
        type: 'agent',
        id: agent.id,
        name: agent.name,
        field: 'provider_model_id',
        status: agent.status,
      })
    }

    if (agent.fallback_provider_model_id && modelIds.has(agent.fallback_provider_model_id)) {
      items.push({
        type: 'agent',
        id: agent.id,
        name: agent.name,
        field: 'fallback_provider_model_id',
        status: agent.status,
      })
    }
  }

  for (const release of releases) {
    if (!['draft', 'staging', 'production'].includes(release.status || '')) continue

    if (release.provider_credential_id === credential.id) {
      items.push({
        type: 'release',
        id: release.id,
        name: release.name,
        field: 'provider_credential_id',
        status: release.status,
        version: release.version,
      })
    }

    if (release.fallback_credential_id === credential.id) {
      items.push({
        type: 'release',
        id: release.id,
        name: release.name,
        field: 'fallback_credential_id',
        status: release.status,
        version: release.version,
      })
    }

    if (release.provider_model_id && modelIds.has(release.provider_model_id)) {
      items.push({
        type: 'release',
        id: release.id,
        name: release.name,
        field: 'provider_model_id',
        status: release.status,
        version: release.version,
      })
    }

    if (release.fallback_provider_model_id && modelIds.has(release.fallback_provider_model_id)) {
      items.push({
        type: 'release',
        id: release.id,
        name: release.name,
        field: 'fallback_provider_model_id',
        status: release.status,
        version: release.version,
      })
    }
  }

  return items
}

export default function ModelsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [section, setSection] = useState<Section>('models')
  const [query, setQuery] = useState('')
  const [showModelDialog, setShowModelDialog] = useState(false)
  const [selectedModel, setSelectedModel] = useState<ProviderModel | null>(null)
  const [showAddCredential, setShowAddCredential] = useState(false)
  const [selectedCredential, setSelectedCredential] = useState<ProviderCredential | null>(null)
  const [credentialToEdit, setCredentialToEdit] = useState<ProviderCredential | null>(null)
  const [confirm, setConfirm] = useState<ConfirmState>(null)
  const [impactLoading, setImpactLoading] = useState(false)

  const credentialsQuery = useCredentials(projectId)
  const modelsQuery = useProviderModels(projectId)
  const updateModel = useUpdateProviderModel()
  const updateCredential = useUpdateCredential()
  const credentials = credentialsQuery.data ?? []
  const models = modelsQuery.data ?? []
  const activeModels = useMemo(() => models.filter((model) => !isArchived(model)), [models])
  const activeCredentials = useMemo(
    () => credentials.filter((credential) => !isArchived(credential) && credential.status !== 'revoked' && ['openai', 'custom', 'openrouter'].includes(credential.provider)),
    [credentials],
  )
  const credentialsById = useMemo(() => new Map(credentials.map((item) => [item.id, item])), [credentials])
  const modelsByCredential = useMemo(() => {
    const grouped = new Map<string, ProviderModel[]>()

    for (const model of activeModels) {
      const current = grouped.get(model.provider_credential_id) || []
      current.push(model)
      grouped.set(model.provider_credential_id, current)
    }

    return grouped
  }, [activeModels])
  const modelCountByCredential = useMemo(() => {
    const counts = new Map<string, number>()

    for (const [credentialId, credentialModels] of modelsByCredential.entries()) {
      counts.set(credentialId, credentialModels.length)
    }

    return counts
  }, [modelsByCredential])

  const filteredModels = activeModels.filter((model) => {
    const credential = credentialsById.get(model.provider_credential_id)
    const search = `${model.name} ${model.model} ${credential?.name || ''} ${providerLabel(model.provider || credential?.provider)}`.toLowerCase()
    return search.includes(query.trim().toLowerCase())
  })

  const filteredCredentials = activeCredentials.filter((credential) => {
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

  const openCreateCredential = () => {
    setCredentialToEdit(null)
    setShowAddCredential(true)
  }

  const closeCredentialForm = () => {
    setShowAddCredential(false)
    setCredentialToEdit(null)
  }

  const handleCredentialSaved = async () => {
    closeCredentialForm()
    await credentialsQuery.refetch()
  }

  const prepareArchiveModel = async (model: ProviderModel) => {
    if (!projectId) return

    setImpactLoading(true)

    try {
      const usage = await loadUsage(projectId)

      setConfirm({
        kind: 'archive-model',
        targetId: model.id,
        targetName: model.name,
        description: 'Archive is blocked while this model is referenced by agents or active releases.',
        blocking: blockingForModel(model, usage.agents, usage.releases),
      })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to inspect usage')
    } finally {
      setImpactLoading(false)
    }
  }

  const prepareArchiveCredential = async (credential: ProviderCredential) => {
    if (!projectId) return

    setImpactLoading(true)

    try {
      const usage = await loadUsage(projectId)

      setConfirm({
        kind: 'archive-credential',
        targetId: credential.id,
        targetName: credential.name,
        description: 'Archive is blocked while this credential is referenced by models, agents or active releases.',
        blocking: blockingForCredential(credential, activeModels, usage.agents, usage.releases),
      })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to inspect usage')
    } finally {
      setImpactLoading(false)
    }
  }

  const prepareRevokeCredential = async (credential: ProviderCredential) => {
    if (!projectId) return

    setImpactLoading(true)

    try {
      const usage = await loadUsage(projectId)

      setConfirm({
        kind: 'revoke-credential',
        targetId: credential.id,
        targetName: credential.name,
        description: 'Revoking is allowed even while in use. Runtime calls using this credential will stop.',
        blocking: blockingForCredential(credential, activeModels, usage.agents, usage.releases),
        allowWithBlocking: true,
      })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to inspect usage')
    } finally {
      setImpactLoading(false)
    }
  }

  const confirmAction = async () => {
    if (!confirm) return

    try {
      if (confirm.kind === 'archive-model') {
        const model = activeModels.find((item) => item.id === confirm.targetId)
        if (!model) return

        await updateModel.mutateAsync({
          id: model.id,
          data: {
            status: 'archived',
            metadata: {
              ...metadataOf(model),
              archived_at: new Date().toISOString(),
              archive_mode: 'soft',
            },
          },
        })

        toast.success('Model archived')
        setShowModelDialog(false)
        setSelectedModel(null)
      }

      if (confirm.kind === 'archive-credential') {
        const credential = credentials.find((item) => item.id === confirm.targetId)
        if (!credential) return

        await updateCredential.mutateAsync({
          id: credential.id,
          data: {
            status: 'archived',
            metadata: stringMetadata({
              ...metadataOf(credential),
              archived_at: new Date().toISOString(),
              archive_mode: 'soft',
            }),
          },
        })

        toast.success('Credential archived')
        setSelectedCredential(null)
      }

      if (confirm.kind === 'revoke-credential') {
        const credential = credentials.find((item) => item.id === confirm.targetId)
        if (!credential) return

        await updateCredential.mutateAsync({
          id: credential.id,
          data: {
            status: 'revoked',
            metadata: stringMetadata({
              ...metadataOf(credential),
              revoked_at: new Date().toISOString(),
            }),
          },
        })

        toast.success('Credential revoked')
        setSelectedCredential(null)
      }

      setConfirm(null)
      await Promise.all([modelsQuery.refetch(), credentialsQuery.refetch()])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Action failed')
    }
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
          <Button variant="outline" onClick={openCreateCredential}><Key className="mr-2 h-4 w-4" />Add credential</Button>
          <Button onClick={openNewModel} disabled={activeCredentials.length === 0}><Plus className="mr-2 h-4 w-4" />New model</Button>
        </div>
      </div>

      <div className="relative max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search models or credentials" className="pl-9" />
      </div>

      {section === 'models' ? (
        filteredModels.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <EmptyCreateCard onClick={openNewModel} disabled={activeCredentials.length === 0} />
            {filteredModels.map((model) => <ModelCard key={model.id} model={model} credential={credentialsById.get(model.provider_credential_id)} onClick={() => openExistingModel(model)} />)}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <EmptyCreateCard onClick={openNewModel} disabled={activeCredentials.length === 0} />
            <div className="rounded-xl border border-border/80 bg-surface/50 p-6">
              <h2 className="text-sm font-semibold text-white">No models found</h2>
              <p className="mt-1 text-sm text-muted">{activeCredentials.length > 0 ? 'Create a model from an existing credential.' : 'Create a provider credential first, then attach models to it.'}</p>
              {activeCredentials.length === 0 && <Button className="mt-4" variant="outline" onClick={openCreateCredential}>Add credential</Button>}
            </div>
          </div>
        )
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <EmptyCredentialCard onClick={openCreateCredential} />
          {filteredCredentials.map((credential) => <CredentialCard key={credential.id} credential={credential} modelCount={modelCountByCredential.get(credential.id) || 0} onClick={() => setSelectedCredential(credential)} />)}
          {filteredCredentials.length === 0 && (
            <div className="rounded-xl border border-border/80 bg-surface/50 p-6">
              <h2 className="text-sm font-semibold text-white">No credentials found</h2>
              <p className="mt-1 text-sm text-muted">Add an OpenAI, OpenAI-compatible or OpenRouter credential.</p>
            </div>
          )}
        </div>
      )}

      <ModelDialog open={showModelDialog} onClose={() => setShowModelDialog(false)} projectId={projectId} credentials={credentials} selectedModel={selectedModel} onArchive={prepareArchiveModel} />
      <CredentialDialog
        open={Boolean(selectedCredential)}
        onClose={() => setSelectedCredential(null)}
        credential={selectedCredential}
        attachedModels={selectedCredential ? modelsByCredential.get(selectedCredential.id) || [] : []}
        onArchive={prepareArchiveCredential}
        onRevoke={prepareRevokeCredential}
      />
      <ImpactDialog
        state={confirm}
        loading={updateModel.isPending || updateCredential.isPending || impactLoading}
        onClose={() => setConfirm(null)}
        onConfirm={confirmAction}
      />
      <AddProviderCredentialModal open={showAddCredential} onClose={closeCredentialForm} projectId={projectId} onCredentialCreated={handleCredentialSaved} credential={credentialToEdit} />
    </div>
  )
}
