import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Check, Cpu, Plus, Search } from 'lucide-react'
import { toast } from 'sonner'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { AddProviderCredentialModal } from '@/features/provider-credentials/components/AddProviderCredentialModal'
import { useCredentials } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { useAvailableProviderModels, useCreateProviderModel, useUpdateProviderModel } from '@/features/provider-models/hooks'
import type { AvailableProviderModel, ProviderModel } from '@/features/provider-models/types'

interface CreateEmbeddingModelModalProps {
  open: boolean
  projectId: string
  onClose: () => void
  onCreated: (modelId: string) => void
  model?: ProviderModel | null
}

interface EmbeddingModelFormState {
  name: string
  credentialId: string
  model: string
  selectedCatalogModelId: string
  manualMode: boolean
  status: string
  inputCostPer1M: string
  currency: string
}

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  custom: 'OpenAI Compatible',
  openrouter: 'OpenRouter',
}

function providerLabel(provider?: string | null) {
  return provider ? providerLabels[provider] || provider : 'Unknown provider'
}

function supportsModelCatalog(credential?: ProviderCredential | null) {
  return credential?.provider === 'openai' || credential?.provider === 'openrouter'
}

function metadataOf(item?: { metadata?: Record<string, unknown> | null } | null): Record<string, unknown> {
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

function parsePrice(value: string): number | null {
  if (!value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function priceText(value: number | null, currency: string) {
  return value === null ? 'not set' : `${currency} ${value.toLocaleString(undefined, { maximumFractionDigits: 8 })}`
}

function pricingOf(model?: ProviderModel | null) {
  const metadata = metadataOf(model)
  const raw = typeof metadata.pricing === 'object' && metadata.pricing !== null
    ? metadata.pricing as Record<string, unknown>
    : metadata
  const input = numberOrNull(
    raw.input_cost_per_1m_tokens
    ?? raw.input_cost_usd_per_1m_tokens
    ?? raw.prompt_cost_per_1m_tokens
    ?? raw.prompt_cost_usd_per_1m_tokens
    ?? raw.input
    ?? raw.prompt,
  )
  const currency = typeof raw.currency === 'string' && raw.currency.trim()
    ? raw.currency.trim().toUpperCase()
    : 'USD'
  return { input, currency }
}

function catalogPricing(model?: AvailableProviderModel | null): number | null {
  return numberOrNull(model?.input_cost_per_1m_tokens)
}

function modelToForm(model: ProviderModel | null, credentials: ProviderCredential[]): EmbeddingModelFormState {
  const pricing = pricingOf(model)
  const credential = model
    ? credentials.find((item) => item.id === model.provider_credential_id)
    : credentials[0]

  return {
    name: model?.name || '',
    credentialId: model?.provider_credential_id || credential?.id || '',
    model: model?.model || '',
    selectedCatalogModelId: '',
    manualMode: Boolean(model) || !supportsModelCatalog(credential),
    status: model?.status || 'active',
    inputCostPer1M: pricing.input !== null ? String(pricing.input) : '',
    currency: pricing.currency || 'USD',
  }
}

function getCredentialLabel(credential?: ProviderCredential | null) {
  return credential ? `${credential.name} · ${providerLabel(credential.provider)}` : 'Credential missing'
}

function Pill({ children }: { children: ReactNode }) {
  return <span className="rounded-full border border-border/80 bg-background/70 px-2.5 py-1 text-xs text-muted">{children}</span>
}

function EmbeddingModelCatalogPicker({
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
  const normalizedQuery = query.trim().toLowerCase()
  const filteredModels = useMemo(() => {
    if (!normalizedQuery) return models
    return models.filter((item) => `${item.label} ${item.id} ${item.provider} ${item.owned_by || ''}`.toLowerCase().includes(normalizedQuery))
  }, [models, normalizedQuery])
  const visibleModels = filteredModels.slice(0, 80)
  const hiddenCount = Math.max(filteredModels.length - visibleModels.length, 0)

  const handleSelect = (selected: AvailableProviderModel) => {
    onSelect(selected)
    setOpen(false)
    setQuery('')
  }

  return (
    <div
      className="relative"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false)
      }}
    >
      <div className="mb-1 flex items-center justify-between gap-3">
        <label className="block text-sm font-medium text-muted">Model catalog</label>
        <Button type="button" size="sm" variant="ghost" className="h-auto px-0 py-0 text-xs" onClick={onManualMode}>Enter manually</Button>
      </div>

      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-9 w-full items-center justify-between gap-3 rounded-lg border border-border bg-transparent px-3 py-1 text-left text-sm shadow-sm transition-colors hover:border-primary/40 focus:border-primary/60 focus:outline-none focus:ring-1 focus:ring-primary/40"
      >
        <span className="min-w-0">
          {selectedModel ? (
            <span className="block truncate text-white">{selectedModel.label}</span>
          ) : (
            <span className="block truncate text-muted">Search or select embedding model</span>
          )}
        </span>
        <Search className="h-4 w-4 shrink-0 text-muted" />
      </button>

      {selectedModel && <code className="mt-1 block truncate text-xs text-muted">{selectedModel.id}</code>}

      {open && (
        <div className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-50 rounded-xl border border-border bg-background shadow-2xl">
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
                placeholder="Search embedding models"
                className="h-9 w-full rounded-lg border border-border bg-transparent px-9 py-1 text-sm text-white outline-none transition-colors placeholder:text-muted focus:border-primary/60 focus:ring-1 focus:ring-primary/40"
                autoFocus
              />
            </div>
          </div>

          <div className="scrollbar-thin max-h-72 overflow-y-auto">
            {loading ? (
              <div className="px-4 py-8 text-center text-sm text-muted">Loading embedding models...</div>
            ) : error ? (
              <div className="px-4 py-8 text-center text-sm text-muted">Could not load embedding models. Use manual entry.</div>
            ) : visibleModels.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-muted">No embedding models found.</div>
            ) : visibleModels.map((availableModel) => {
              const selected = availableModel.id === selectedModelId
              return (
                <button
                  key={availableModel.id}
                  type="button"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => handleSelect(availableModel)}
                  className={`grid w-full gap-1 border-b border-border/60 px-4 py-3 text-left transition-colors last:border-b-0 ${selected ? 'bg-primary/5' : 'hover:bg-surface/70'}`}
                >
                  <span className="flex min-w-0 items-center justify-between gap-3">
                    <span className="truncate text-sm font-medium text-white">{availableModel.label}</span>
                    {selected && <Check className="h-4 w-4 shrink-0 text-primary-light" />}
                  </span>
                  <code className="block truncate text-xs text-muted">{availableModel.id}</code>
                </button>
              )
            })}
          </div>

          {hiddenCount > 0 && (
            <div className="border-t border-border/70 px-4 py-2 text-xs text-muted">+{hiddenCount} more model(s). Refine the search.</div>
          )}
        </div>
      )}
    </div>
  )
}

export function CreateEmbeddingModelModal({ open, projectId, onClose, onCreated, model = null }: CreateEmbeddingModelModalProps) {
  const { data: credentials = [], refetch: refetchCredentials } = useCredentials(projectId)
  const createModel = useCreateProviderModel()
  const updateModel = useUpdateProviderModel()
  const wasOpen = useRef(false)

  const usableCredentials = useMemo(
    () => credentials.filter((credential) => (
      (!credential.status || credential.status === 'active')
      && ['openai', 'custom', 'openrouter'].includes(credential.provider)
    )),
    [credentials],
  )

  const [form, setForm] = useState<EmbeddingModelFormState>(() => modelToForm(model, usableCredentials))
  const [credentialModalOpen, setCredentialModalOpen] = useState(false)

  const credential = usableCredentials.find((item) => item.id === form.credentialId) || null
  const supportsCatalog = supportsModelCatalog(credential)
  const shouldUseCatalog = supportsCatalog && !form.manualMode
  const catalogQuery = useAvailableProviderModels(
    projectId,
    shouldUseCatalog ? form.credentialId : undefined,
    'embedding',
  )
  const embeddingCatalog = catalogQuery.data ?? []
  const selectedCatalogModel = shouldUseCatalog
    ? embeddingCatalog.find((item) => item.id === form.selectedCatalogModelId) || null
    : null
  const previewPricing = {
    input: parsePrice(form.inputCostPer1M),
    currency: (form.currency || 'USD').trim().toUpperCase(),
  }

  useEffect(() => {
    const justOpened = open && !wasOpen.current
    wasOpen.current = open
    if (!justOpened) return
    setForm(modelToForm(model, usableCredentials))
  }, [open, model, usableCredentials])

  useEffect(() => {
    if (!open || model || form.credentialId || usableCredentials.length === 0) return
    setForm(modelToForm(null, usableCredentials))
  }, [open, model, form.credentialId, usableCredentials])

  useEffect(() => {
    if (!selectedCatalogModel) return
    const inputPricing = catalogPricing(selectedCatalogModel)
    setForm((previous) => ({
      ...previous,
      name: previous.name.trim() ? previous.name : selectedCatalogModel.label || selectedCatalogModel.id,
      model: selectedCatalogModel.id,
      inputCostPer1M: inputPricing !== null ? String(inputPricing) : previous.inputCostPer1M,
      currency: previous.currency || 'USD',
    }))
  }, [selectedCatalogModel?.id])

  const setField = <K extends keyof EmbeddingModelFormState>(key: K, value: EmbeddingModelFormState[K]) => {
    setForm((previous) => ({ ...previous, [key]: value }))
  }

  const handleCredentialChange = (credentialId: string) => {
    const nextCredential = usableCredentials.find((item) => item.id === credentialId) || null
    const nextSupportsCatalog = supportsModelCatalog(nextCredential)
    setForm((previous) => ({
      ...previous,
      credentialId,
      selectedCatalogModelId: '',
      manualMode: !nextSupportsCatalog ? true : model ? previous.manualMode : false,
      model: model ? previous.model : '',
      name: model ? previous.name : '',
      inputCostPer1M: model ? previous.inputCostPer1M : '',
    }))
  }

  const handleCatalogSelect = (selected: AvailableProviderModel) => {
    setForm((previous) => ({
      ...previous,
      selectedCatalogModelId: selected.id,
      model: selected.id,
      name: previous.name.trim() ? previous.name : selected.label || selected.id,
    }))
  }

  const handleManualMode = () => {
    setForm((previous) => ({ ...previous, manualMode: true, selectedCatalogModelId: '' }))
  }

  const handleCredentialCreated = (createdCredentialId: string) => {
    setCredentialModalOpen(false)
    setForm((previous) => ({
      ...previous,
      credentialId: createdCredentialId,
      selectedCatalogModelId: '',
      manualMode: false,
      model: '',
      name: '',
      inputCostPer1M: '',
    }))
    void refetchCredentials()
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const resolvedModel = form.model.trim()
    const resolvedName = form.name.trim() || selectedCatalogModel?.label || resolvedModel
    if (!form.credentialId) return toast.error('Credential is required')
    if (!resolvedModel) return toast.error('Model is required')
    if (!resolvedName) return toast.error('Model name is required')

    const inputPrice = parsePrice(form.inputCostPer1M)
    if (form.inputCostPer1M.trim() && inputPrice === null) return toast.error('Pricing must be a valid number')
    if (inputPrice !== null && inputPrice < 0) return toast.error('Pricing cannot be negative')

    const baseMetadata = metadataOf(model)
    const metadata = {
      ...baseMetadata,
      capability: 'embedding',
      dimensions: 1536,
      source: selectedCatalogModel ? 'remote' : 'manual',
      catalog: selectedCatalogModel ? {
        provider: selectedCatalogModel.provider,
        model_id: selectedCatalogModel.id,
        label: selectedCatalogModel.label,
        owned_by: selectedCatalogModel.owned_by ?? null,
        context_window: selectedCatalogModel.context_window ?? null,
      } : baseMetadata.catalog,
      pricing: {
        input_cost_per_1m_tokens: inputPrice,
        output_cost_per_1m_tokens: null,
        currency: (form.currency || 'USD').trim().toUpperCase(),
        billing_unit: 'per_1m_tokens',
        source: selectedCatalogModel ? 'provider_catalog' : 'manual',
      },
      provider_model_raw: selectedCatalogModel?.raw ?? baseMetadata.provider_model_raw,
    }

    try {
      if (model) {
        const updated = await updateModel.mutateAsync({
          id: model.id,
          data: {
            provider_credential_id: form.credentialId,
            name: resolvedName,
            model: resolvedModel,
            status: form.status,
            metadata,
          },
        })
        toast.success('Embedding model updated')
        onCreated(updated.id)
        return
      }

      const created = await createModel.mutateAsync({
        project_id: projectId,
        provider_credential_id: form.credentialId,
        name: resolvedName,
        model: resolvedModel,
        metadata,
      })
      toast.success('Embedding model created')
      onCreated(created.id)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save embedding model')
    }
  }

  const pending = createModel.isPending || updateModel.isPending

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        title={model ? 'Edit Embedding Model' : 'New Embedding Model'}
        className="max-h-[calc(100svh-2rem)] max-w-5xl overflow-hidden"
      >
        <form onSubmit={submit}>
          <div className="scrollbar-thin max-h-[calc(100svh-8rem)] overflow-y-auto pr-1">
            <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
              <aside className="space-y-4 lg:sticky lg:top-0 lg:self-start">
                <div className="rounded-xl border border-border/90 bg-surface/70 p-4">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-background text-primary-light">
                    <Cpu className="h-5 w-5" />
                  </div>
                  <div className="mt-5 min-w-0">
                    <h3 className="truncate text-base font-semibold text-white">{form.name.trim() || model?.name || 'New embedding model'}</h3>
                    <code className="mt-1 block truncate text-xs text-muted">{form.model.trim() || model?.model || 'Select or enter a model identifier'}</code>
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
                  <p className="mt-1 text-xs leading-5 text-muted">Embedding costs are stored as metadata for estimation and trace analysis.</p>
                  <div className="mt-4 space-y-2 text-xs text-muted">
                    <div className="flex items-center justify-between gap-3">
                      <span>Input / 1M</span>
                      <span className="text-white/90">{priceText(previewPricing.input, previewPricing.currency)}</span>
                    </div>
                  </div>
                </section>
              </aside>

              <main className="space-y-5">
                <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                  <div className="mb-4">
                    <h3 className="text-sm font-semibold text-white">Provider binding</h3>
                    <p className="mt-1 text-xs leading-5 text-muted">Bind this reusable embedding model to a credential and provider model identifier.</p>
                  </div>

                  {usableCredentials.length === 0 ? (
                    <div className="rounded-xl border border-border bg-background/60 p-4">
                      <p className="text-sm font-medium text-white">A provider credential is required.</p>
                      <p className="mt-1 text-sm leading-6 text-muted">Add a BYOK credential before creating the embedding model.</p>
                      <Button type="button" size="sm" variant="outline" className="mt-4" onClick={() => setCredentialModalOpen(true)}>
                        <Plus className="mr-2 h-4 w-4" /> Add credential
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div>
                        <label className="mb-1 block text-sm font-medium text-muted">Credential</label>
                        <Select
                          value={form.credentialId}
                          onChange={(event) => handleCredentialChange(event.target.value)}
                          options={usableCredentials.map((item) => ({ value: item.id, label: `${item.name} (${providerLabel(item.provider)})` }))}
                          disabled={Boolean(model)}
                        />
                        {credential?.metadata?.base_url && (
                          <p className="mt-1 truncate text-xs text-muted">Base URL: <code>{credential.metadata.base_url}</code></p>
                        )}
                      </div>

                      {shouldUseCatalog && (
                        <EmbeddingModelCatalogPicker
                          models={embeddingCatalog}
                          selectedModelId={form.selectedCatalogModelId}
                          loading={catalogQuery.isLoading}
                          error={catalogQuery.isError}
                          onSelect={handleCatalogSelect}
                          onManualMode={handleManualMode}
                        />
                      )}

                      {(form.manualMode || !supportsCatalog) && (
                        <div>
                          <label className="mb-1 block text-sm font-medium text-muted">Model identifier</label>
                          <Input
                            value={form.model}
                            onChange={(event) => setField('model', event.target.value)}
                            placeholder={credential?.provider === 'openrouter' ? 'openai/text-embedding-3-small' : 'text-embedding-3-small'}
                          />
                          {!model && supportsCatalog && (
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              className="mt-2"
                              onClick={() => setForm((previous) => ({ ...previous, manualMode: false, model: '', selectedCatalogModelId: '' }))}
                            >
                              Use provider catalog
                            </Button>
                          )}
                          {!supportsCatalog && <p className="mt-1 text-xs text-muted">OpenAI-compatible credentials use manual model identifiers.</p>}
                        </div>
                      )}
                    </div>
                  )}
                </section>

                <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                  <div className="mb-4">
                    <h3 className="text-sm font-semibold text-white">Model details</h3>
                    <p className="mt-1 text-xs leading-5 text-muted">Display name, operational status and pricing metadata.</p>
                  </div>
                  <div className="space-y-4">
                    <div>
                      <label className="mb-1 block text-sm font-medium text-muted">Display name</label>
                      <Input
                        value={form.name}
                        onChange={(event) => setField('name', event.target.value)}
                        placeholder={selectedCatalogModel?.label || 'Production embeddings'}
                      />
                    </div>

                    {model && (
                      <div>
                        <label className="mb-1 block text-sm font-medium text-muted">Status</label>
                        <Select
                          value={form.status}
                          onChange={(event) => setField('status', event.target.value)}
                          options={[
                            { value: 'active', label: 'Active' },
                            { value: 'inactive', label: 'Inactive' },
                            { value: 'archived', label: 'Archived' },
                          ]}
                        />
                      </div>
                    )}

                    <div className="grid gap-4 md:grid-cols-3">
                      <div>
                        <label className="mb-1 block text-sm font-medium text-muted">Input / 1M</label>
                        <Input value={form.inputCostPer1M} onChange={(event) => setField('inputCostPer1M', event.target.value)} placeholder="0.02" />
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium text-muted">Currency</label>
                        <Input value={form.currency} onChange={(event) => setField('currency', event.target.value.toUpperCase())} placeholder="USD" />
                      </div>
                      <div>
                        <label className="mb-1 block text-sm font-medium text-muted">Dimensions</label>
                        <Input value="1536" disabled />
                      </div>
                    </div>
                  </div>
                </section>
              </main>
            </div>

            <div className="sticky bottom-0 -mx-1 mt-6 flex justify-end gap-2 border-t border-border bg-surface/95 px-1 py-4 backdrop-blur">
              <Button type="button" variant="outline" onClick={onClose} disabled={pending}>Cancel</Button>
              <Button type="submit" loading={pending} disabled={usableCredentials.length === 0}>
                {model ? 'Save changes' : 'Create model'}
              </Button>
            </div>
          </div>
        </form>
      </Dialog>

      <AddProviderCredentialModal
        open={credentialModalOpen}
        onClose={() => setCredentialModalOpen(false)}
        projectId={projectId}
        onCredentialCreated={handleCredentialCreated}
      />
    </>
  )
}
