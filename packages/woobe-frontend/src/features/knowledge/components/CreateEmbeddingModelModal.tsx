import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Check, Cpu, Plus, Search } from 'lucide-react'
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
  Select,
  TechnicalListItem,
} from '@woobe/ui'

import { StatusBadge } from '@/components/common/StatusBadge'
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
  const [query, setQuery] = useState('')
  const normalizedQuery = query.trim().toLowerCase()
  const filteredModels = useMemo(() => {
    if (!normalizedQuery) return models
    return models.filter((item) => `${item.label} ${item.id} ${item.provider} ${item.owned_by || ''}`.toLowerCase().includes(normalizedQuery))
  }, [models, normalizedQuery])
  const visibleModels = filteredModels.slice(0, 80)
  const hiddenCount = Math.max(filteredModels.length - visibleModels.length, 0)

  return (
    <Field>
      <div className="flex items-center justify-between gap-ui-sm">
        <FieldLabel>Model catalog</FieldLabel>
        <Button type="button" size="sm" variant="ghost" onClick={onManualMode}>Enter manually</Button>
      </div>

      {models.length > 6 ? (
        <div className="relative">
          <Search className="pointer-events-none absolute left-ui-md top-1/2 h-icon w-icon -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search embedding models"
            className="pl-9"
          />
        </div>
      ) : null}

      {loading ? (
        <EmptyStatePanel compact title="Loading embedding models" description="Reading the provider model catalog." />
      ) : error ? (
        <Alert variant="warning">
          <AlertDescription>Could not load embedding models. Use manual model entry.</AlertDescription>
        </Alert>
      ) : visibleModels.length === 0 ? (
        <EmptyStatePanel compact title="No embedding models found" description="Change the search or enter the model identifier manually." />
      ) : (
        <div className="scrollbar-thin grid max-h-72 gap-ui-xs overflow-y-auto pr-ui-xs">
          {visibleModels.map((availableModel) => {
            const selected = availableModel.id === selectedModelId
            return (
              <TechnicalListItem
                key={availableModel.id}
                label={availableModel.label}
                description={availableModel.id}
                meta={providerLabel(availableModel.provider)}
                selected={selected}
                trailing={selected ? <Check className="h-icon w-icon text-primary-light" /> : null}
                onClick={() => onSelect(availableModel)}
              />
            )
          })}
        </div>
      )}

      {hiddenCount > 0 ? <FieldDescription>+{hiddenCount} more model(s). Refine the search.</FieldDescription> : null}
    </Field>
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
        className="flex max-h-dialog max-w-dialog-wide flex-col overflow-hidden"
        contentClassName="min-h-0 flex-1 p-0"
      >
        <form onSubmit={submit} className="flex h-full min-h-0 flex-col">
          <div className="shrink-0 border-b border-border bg-background/20 px-ui-lg py-ui-md">
            <TechnicalListItem
              label={form.name.trim() || model?.name || 'New embedding model'}
              description={form.model.trim() || model?.model || 'Select or enter a model identifier'}
              leading={(
                <span className="flex h-control-nav w-control-nav items-center justify-center rounded-control border border-primary/25 bg-primary/[0.08] text-primary-light">
                  <Cpu className="h-icon w-icon" />
                </span>
              )}
              meta={(
                <>
                  <StatusBadge status={form.status || 'active'} size="compact" />
                  <Badge variant="outline" size="compact">{credential ? providerLabel(credential.provider) : 'No credential'}</Badge>
                </>
              )}
            />
          </div>

          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-ui-lg">
            <div className="grid gap-ui-md lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
              <aside className="grid content-start gap-ui-md">
                <SectionBlock title="Binding summary" description="Current provider binding for this embedding model." density="compact">
                  <div className="grid gap-ui-xs">
                    <TechnicalListItem label="Credential" description={getCredentialLabel(credential)} />
                    <TechnicalListItem label="Provider model" description={form.model.trim() || 'Not selected'} />
                  </div>
                </SectionBlock>

                <SectionBlock title="Pricing" description="Embedding costs are stored as metadata for estimation and trace analysis." density="compact">
                  <TechnicalListItem label="Input / 1M" description={priceText(previewPricing.input, previewPricing.currency)} />
                </SectionBlock>
              </aside>

              <main className="grid content-start gap-ui-md">
                <SectionBlock
                  title="Provider binding"
                  description="Bind this reusable embedding model to a credential and provider model identifier."
                >
                  {usableCredentials.length === 0 ? (
                    <EmptyStatePanel
                      title="A provider credential is required"
                      description="Add a BYOK credential before creating the embedding model."
                      action={(
                        <Button type="button" size="sm" variant="outline" onClick={() => setCredentialModalOpen(true)}>
                          <Plus className="h-icon w-icon" />Add credential
                        </Button>
                      )}
                    />
                  ) : (
                    <div className="grid gap-ui-md">
                      <Field>
                        <div className="flex items-center justify-between gap-ui-sm">
                          <FieldLabel>Credential</FieldLabel>
                          {!model ? (
                            <Button type="button" size="sm" variant="ghost" onClick={() => setCredentialModalOpen(true)}>
                              <Plus className="h-icon-sm w-icon-sm" />Add credential
                            </Button>
                          ) : null}
                        </div>
                        <Select
                          value={form.credentialId}
                          onChange={(event) => handleCredentialChange(event.target.value)}
                          options={usableCredentials.map((item) => ({ value: item.id, label: `${item.name} (${providerLabel(item.provider)})` }))}
                          disabled={Boolean(model)}
                        />
                        {credential?.metadata?.base_url ? <FieldDescription>Base URL: <span className="font-mono">{credential.metadata.base_url}</span></FieldDescription> : null}
                      </Field>

                      {shouldUseCatalog ? (
                        <EmbeddingModelCatalogPicker
                          models={embeddingCatalog}
                          selectedModelId={form.selectedCatalogModelId}
                          loading={catalogQuery.isLoading}
                          error={catalogQuery.isError}
                          onSelect={handleCatalogSelect}
                          onManualMode={handleManualMode}
                        />
                      ) : null}

                      {(form.manualMode || !supportsCatalog) ? (
                        <Field>
                          <FieldLabel>Model identifier</FieldLabel>
                          <Input
                            value={form.model}
                            onChange={(event) => setField('model', event.target.value)}
                            placeholder={credential?.provider === 'openrouter' ? 'openai/text-embedding-3-small' : 'text-embedding-3-small'}
                            className="font-mono"
                          />
                          {!model && supportsCatalog ? (
                            <div>
                              <Button
                                type="button"
                                size="sm"
                                variant="ghost"
                                onClick={() => setForm((previous) => ({ ...previous, manualMode: false, model: '', selectedCatalogModelId: '' }))}
                              >
                                Use provider catalog
                              </Button>
                            </div>
                          ) : null}
                          {!supportsCatalog ? <FieldDescription>OpenAI-compatible credentials use manual model identifiers.</FieldDescription> : null}
                        </Field>
                      ) : null}
                    </div>
                  )}
                </SectionBlock>

                <SectionBlock title="Model details" description="Display name, operational status and pricing metadata.">
                  <div className="grid gap-ui-md">
                    <Field>
                      <FieldLabel>Display name</FieldLabel>
                      <Input
                        value={form.name}
                        onChange={(event) => setField('name', event.target.value)}
                        placeholder={selectedCatalogModel?.label || 'Production embeddings'}
                      />
                    </Field>

                    {model ? (
                      <Field>
                        <FieldLabel>Status</FieldLabel>
                        <Select
                          value={form.status}
                          onChange={(event) => setField('status', event.target.value)}
                          options={[
                            { value: 'active', label: 'Active' },
                            { value: 'inactive', label: 'Inactive' },
                            { value: 'archived', label: 'Archived' },
                          ]}
                        />
                      </Field>
                    ) : null}

                    <div className="grid gap-ui-md md:grid-cols-3">
                      <Field>
                        <FieldLabel>Input / 1M</FieldLabel>
                        <Input value={form.inputCostPer1M} onChange={(event) => setField('inputCostPer1M', event.target.value)} placeholder="0.02" />
                      </Field>
                      <Field>
                        <FieldLabel>Currency</FieldLabel>
                        <Input value={form.currency} onChange={(event) => setField('currency', event.target.value.toUpperCase())} placeholder="USD" />
                      </Field>
                      <Field>
                        <FieldLabel>Dimensions</FieldLabel>
                        <Input value="1536" disabled className="font-mono" />
                      </Field>
                    </div>
                  </div>
                </SectionBlock>
              </main>
            </div>
          </div>

          <div className="flex shrink-0 justify-end gap-ui-sm border-t border-border bg-surface/95 px-ui-lg py-ui-md backdrop-blur">
            <Button type="button" variant="outline" onClick={onClose} disabled={pending}>Cancel</Button>
            <Button type="submit" loading={pending} disabled={usableCredentials.length === 0}>
              {model ? 'Save changes' : 'Create model'}
            </Button>
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
