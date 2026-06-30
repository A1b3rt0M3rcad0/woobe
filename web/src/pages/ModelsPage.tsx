import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { Archive, Cpu, DollarSign, Key, Plus, Search, ServerCog } from 'lucide-react'
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
import { useCreateProviderModel, useProviderModels, useUpdateProviderModel } from '@/features/provider-models/hooks'
import type { ProviderModel } from '@/features/provider-models/types'

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  openrouter: 'OpenRouter',
  anthropic: 'Anthropic',
  google: 'Google',
  custom: 'Custom',
}

const commonModelSuggestions: Record<string, string[]> = {
  openai: ['gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini', 'gpt-4.1'],
  openrouter: ['openai/gpt-4o-mini', 'anthropic/claude-3.5-sonnet', 'google/gemini-pro', 'deepseek/deepseek-r1'],
  anthropic: ['claude-3-5-haiku-latest', 'claude-3-5-sonnet-latest', 'claude-3-opus-latest'],
  google: ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash'],
  custom: ['my-model-name'],
}

type PricingInfo = {
  input: number | null
  output: number | null
  currency: string
  configured: boolean
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : 'Never'
}

function providerLabel(provider?: string | null) {
  if (!provider) return 'Unknown provider'
  return providerLabels[provider] || provider
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
  const metadata = model?.metadata || {}
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
  const output = numberOrNull(
    raw.output_cost_per_1m_tokens
    ?? raw.output_cost_usd_per_1m_tokens
    ?? raw.completion_cost_per_1m_tokens
    ?? raw.completion_cost_usd_per_1m_tokens
    ?? raw.output
    ?? raw.completion,
  )
  const currency = typeof raw.currency === 'string' && raw.currency.trim()
    ? raw.currency.trim().toUpperCase()
    : 'USD'
  return { input, output, currency, configured: input !== null && output !== null }
}

function priceText(value: number | null, currency: string) {
  if (value === null) return 'not set'
  return `${currency} ${value.toLocaleString(undefined, { maximumFractionDigits: 8 })}`
}

function MinimalShell({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">{title}</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">{description}</p>
      </div>
      {children}
    </div>
  )
}

function Pill({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'primary' | 'warning' }) {
  const toneClass = tone === 'primary'
    ? 'border-primary/30 bg-primary/10 text-primary-light'
    : tone === 'warning'
      ? 'border-amber-400/30 bg-amber-400/10 text-amber-200'
      : 'border-border/80 bg-background/70 text-muted'
  return <span className={`rounded-full border px-2.5 py-1 text-xs ${toneClass}`}>{children}</span>
}

function getCredentialLabel(credential?: ProviderCredential | null) {
  if (!credential) return 'Credential missing'
  return `${credential.name} · ${providerLabel(credential.provider)}`
}

function CreateCard({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex min-h-[270px] flex-col items-center justify-center rounded-xl border border-dashed border-primary/40 bg-surface/35 p-6 text-center transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/60 hover:bg-primary/5 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <span className="flex h-14 w-14 items-center justify-center rounded-full border border-primary/50 bg-primary/10 text-primary-light transition-colors duration-200 group-hover:bg-primary/15">
        <Plus className="h-6 w-6" />
      </span>
      <span className="mt-5 text-base font-semibold text-white">New model</span>
      <span className="mt-2 max-w-[240px] text-sm leading-6 text-muted">Create a reusable model from an existing provider credential</span>
    </button>
  )
}

function NoResults({ query, hasCredentials, onAddCredential }: { query: string; hasCredentials: boolean; onAddCredential: () => void }) {
  return (
    <div className="rounded-xl border border-border/80 bg-surface/50 px-5 py-4">
      <h2 className="text-sm font-semibold text-white">No models found</h2>
      <p className="mt-1 text-sm text-muted">
        {query.trim()
          ? 'Adjust the search term or create a new model.'
          : hasCredentials
            ? 'Create reusable models from your provider credentials.'
            : 'Create a provider credential first, then attach models to it.'}
      </p>
      {!hasCredentials && (
        <Button size="sm" variant="outline" className="mt-4" onClick={onAddCredential}>
          <Key className="mr-2 h-4 w-4" />
          Add credential
        </Button>
      )}
    </div>
  )
}

function ModelCard({ model, credential, onClick }: { model: ProviderModel; credential?: ProviderCredential | null; onClick: () => void }) {
  const pricing = pricingOf(model)
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Open model settings for ${model.name}`}
      className="group flex min-h-[270px] flex-col rounded-xl border border-border/90 bg-surface/70 p-6 text-left transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/35 hover:bg-surface/85 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <span className="flex items-start justify-between gap-3">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background text-primary-light shadow-sm transition-colors duration-200 group-hover:border-primary/30 group-hover:bg-primary/10">
          <Cpu className="h-5 w-5" />
        </span>
        <StatusBadge status={model.status || 'active'} />
      </span>

      <span className="mt-6 block min-w-0">
        <span className="block truncate text-base font-semibold text-white">{model.name}</span>
        <code className="mt-2 block truncate text-xs text-muted">{model.model}</code>
      </span>

      <span className="my-5 block h-px bg-border/80" />

      <span className="grid gap-2 text-xs text-muted">
        <span className="flex min-w-0 items-center gap-2">
          <Key className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">{getCredentialLabel(credential)}</span>
        </span>
        <span className="flex min-w-0 items-center gap-2">
          <DollarSign className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">In {priceText(pricing.input, pricing.currency)} / 1M · Out {priceText(pricing.output, pricing.currency)} / 1M</span>
        </span>
        <span>Created · {formatDate(model.created_at)}</span>
      </span>

      <span className="mt-auto flex flex-wrap gap-2 pt-5">
        <Pill tone="primary">{providerLabel(model.provider || credential?.provider)}</Pill>
        <Pill tone={pricing.configured ? 'default' : 'warning'}>{pricing.configured ? 'cost configured' : 'cost unknown'}</Pill>
      </span>
    </button>
  )
}

interface ModelFormState {
  name: string
  credentialId: string
  model: string
  status: string
  inputCostPer1M: string
  outputCostPer1M: string
  currency: string
}

function modelToForm(model: ProviderModel | null, credentials: ProviderCredential[]): ModelFormState {
  const pricing = pricingOf(model)
  return {
    name: model?.name || '',
    credentialId: model?.provider_credential_id || credentials[0]?.id || '',
    model: model?.model || '',
    status: model?.status || 'active',
    inputCostPer1M: pricing.input !== null ? String(pricing.input) : '',
    outputCostPer1M: pricing.output !== null ? String(pricing.output) : '',
    currency: pricing.currency || 'USD',
  }
}

function parsePrice(value: string): number | null {
  if (!value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function buildMetadata(model: ProviderModel | null, form: ModelFormState) {
  const input = parsePrice(form.inputCostPer1M)
  const output = parsePrice(form.outputCostPer1M)
  return {
    ...(model?.metadata || {}),
    pricing: {
      input_cost_per_1m_tokens: input,
      output_cost_per_1m_tokens: output,
      currency: (form.currency || 'USD').trim().toUpperCase(),
      billing_unit: 'per_1m_tokens',
      source: 'manual',
    },
  }
}

function ModelDialog({
  open,
  onClose,
  projectId,
  credentials,
  selectedModel,
}: {
  open: boolean
  onClose: () => void
  projectId: string
  credentials: ProviderCredential[]
  selectedModel: ProviderModel | null
}) {
  const createModel = useCreateProviderModel()
  const updateModel = useUpdateProviderModel()
  const [form, setForm] = useState<ModelFormState>(() => modelToForm(selectedModel, credentials))

  const credential = credentials.find((item) => item.id === form.credentialId) || null
  const suggestions = credential ? commonModelSuggestions[credential.provider] || [] : []

  useEffect(() => {
    if (!open) return
    setForm(modelToForm(selectedModel, credentials))
  }, [open, selectedModel, credentials])

  const setField = <K extends keyof ModelFormState>(key: K, value: ModelFormState[K]) => {
    setForm((previous) => ({ ...previous, [key]: value }))
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!form.name.trim()) {
      toast.error('Model name is required')
      return
    }
    if (!form.credentialId) {
      toast.error('Credential is required')
      return
    }
    if (!form.model.trim()) {
      toast.error('Model identifier is required')
      return
    }

    const inputPrice = parsePrice(form.inputCostPer1M)
    const outputPrice = parsePrice(form.outputCostPer1M)
    if ((form.inputCostPer1M.trim() && inputPrice === null) || (form.outputCostPer1M.trim() && outputPrice === null)) {
      toast.error('Pricing must be a valid number')
      return
    }
    if ((inputPrice !== null && inputPrice < 0) || (outputPrice !== null && outputPrice < 0)) {
      toast.error('Pricing cannot be negative')
      return
    }

    const metadata = buildMetadata(selectedModel, form)
    try {
      if (selectedModel) {
        await updateModel.mutateAsync({
          id: selectedModel.id,
          data: {
            name: form.name.trim(),
            provider_credential_id: form.credentialId,
            model: form.model.trim(),
            status: form.status,
            metadata,
          },
        })
        toast.success('Model updated')
      } else {
        await createModel.mutateAsync({
          project_id: projectId,
          provider_credential_id: form.credentialId,
          name: form.name.trim(),
          model: form.model.trim(),
          metadata,
        })
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
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-surface text-primary-light">
              <ServerCog className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Reusable provider model</p>
              <p className="mt-1 text-xs leading-5 text-muted">The model stores a credential reference, model identifier and token pricing. Runtime behavior stays on the agent.</p>
            </div>
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-muted">Credential</label>
          <Select
            value={form.credentialId}
            onChange={(event) => setField('credentialId', event.target.value)}
            options={credentials.map((item) => ({
              value: item.id,
              label: `${item.name} (${providerLabel(item.provider)})`,
            }))}
            disabled={credentials.length === 0}
          />
          {credential?.metadata?.base_url && (
            <p className="mt-1 truncate text-xs text-muted">Base URL: <code>{credential.metadata.base_url}</code></p>
          )}
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-muted">Display name</label>
          <Input value={form.name} onChange={(event) => setField('name', event.target.value)} placeholder="Claude Sonnet via OpenRouter" />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-muted">Model identifier</label>
          <Input value={form.model} onChange={(event) => setField('model', event.target.value)} placeholder="openai/gpt-4o-mini" />
          {suggestions.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => {
                    setField('model', suggestion)
                    if (!form.name.trim()) setField('name', suggestion)
                  }}
                  className="rounded-full border border-border/80 bg-background/70 px-2.5 py-1 text-xs text-muted transition-colors hover:border-primary/30 hover:bg-primary/10 hover:text-primary-light"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-border/80 bg-background/60 p-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-surface text-primary-light">
              <DollarSign className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Token pricing</p>
              <p className="mt-1 text-xs leading-5 text-muted">Used by runtime cost calculation for this ProviderModel. Values are per 1M tokens.</p>
            </div>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-muted">Input / 1M</label>
              <Input value={form.inputCostPer1M} onChange={(event) => setField('inputCostPer1M', event.target.value)} placeholder="0.14" inputMode="decimal" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-muted">Output / 1M</label>
              <Input value={form.outputCostPer1M} onChange={(event) => setField('outputCostPer1M', event.target.value)} placeholder="0.28" inputMode="decimal" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-muted">Currency</label>
              <Input value={form.currency} onChange={(event) => setField('currency', event.target.value.toUpperCase())} placeholder="USD" />
            </div>
          </div>
        </div>

        {selectedModel && (
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

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={createModel.isPending || updateModel.isPending} disabled={credentials.length === 0}>
            {selectedModel ? 'Save changes' : 'Create model'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}

export default function ModelsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: credentials = [], isLoading: credentialsLoading, isError: credentialsError, error: credentialsErrorValue, refetch: refetchCredentials } = useCredentials(projectId)
  const { data: models = [], isLoading: modelsLoading, isError: modelsError, error: modelsErrorValue, refetch: refetchModels } = useProviderModels(projectId)
  const [query, setQuery] = useState('')
  const [showModelDialog, setShowModelDialog] = useState(false)
  const [showCredentialDialog, setShowCredentialDialog] = useState(false)
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null)

  const credentialsById = useMemo(() => {
    return new Map(credentials.map((credential) => [credential.id, credential]))
  }, [credentials])

  const selectedModel = models.find((model) => model.id === selectedModelId) || null
  const pricedModels = models.filter((model) => pricingOf(model).configured).length

  const visibleModels = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return models
    return models.filter((model) => {
      const credential = credentialsById.get(model.provider_credential_id)
      const pricing = pricingOf(model)
      return (
        model.name.toLowerCase().includes(normalized)
        || model.model.toLowerCase().includes(normalized)
        || (model.status || '').toLowerCase().includes(normalized)
        || (model.provider || credential?.provider || '').toLowerCase().includes(normalized)
        || (credential?.name || '').toLowerCase().includes(normalized)
        || pricing.currency.toLowerCase().includes(normalized)
        || (pricing.configured ? 'cost configured' : 'cost unknown').includes(normalized)
      )
    })
  }, [models, query, credentialsById])

  const openCreateModel = () => {
    setSelectedModelId(null)
    setShowModelDialog(true)
  }

  const openEditModel = (id: string) => {
    setSelectedModelId(id)
    setShowModelDialog(true)
  }

  const handleCloseModelDialog = () => {
    setShowModelDialog(false)
    setSelectedModelId(null)
  }

  const handleCredentialCreated = async () => {
    setShowCredentialDialog(false)
    await refetchCredentials()
  }

  if (credentialsLoading || modelsLoading) return <LoadingState />
  if (credentialsError) return <ErrorState error={credentialsErrorValue} onRetry={refetchCredentials} />
  if (modelsError) return <ErrorState error={modelsErrorValue} onRetry={refetchModels} />

  const hasCredentials = credentials.length > 0
  const hasNoModels = models.length === 0
  const hasSearchMiss = query.trim().length > 0 && visibleModels.length === 0

  return (
    <MinimalShell
      title="Models"
      description="Create reusable provider models from existing credentials, configure token pricing, then attach those models to multiple agents."
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="relative w-full max-w-3xl">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search models, providers, credentials or cost status..."
            className="h-11 pl-9"
          />
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowCredentialDialog(true)}>
            <Key className="mr-2 h-4 w-4" />
            Add credential
          </Button>
          <Button onClick={openCreateModel} disabled={!hasCredentials}>
            <Plus className="mr-2 h-4 w-4" />
            New model
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-border/80 bg-surface/50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted/80">Credentials</p>
          <p className="mt-3 text-2xl font-semibold text-white">{credentials.length}</p>
          <p className="mt-1 text-xs text-muted">Reusable provider connections</p>
        </div>
        <div className="rounded-xl border border-border/80 bg-surface/50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted/80">Models</p>
          <p className="mt-3 text-2xl font-semibold text-white">{models.length}</p>
          <p className="mt-1 text-xs text-muted">Configured model bindings</p>
        </div>
        <div className="rounded-xl border border-border/80 bg-surface/50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted/80">Pricing</p>
          <p className="mt-3 text-2xl font-semibold text-white">{pricedModels}/{models.length}</p>
          <p className="mt-1 text-xs text-muted">Models with known runtime cost</p>
        </div>
      </div>

      {(hasNoModels || hasSearchMiss) && <NoResults query={query} hasCredentials={hasCredentials} onAddCredential={() => setShowCredentialDialog(true)} />}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {visibleModels.map((model) => (
          <ModelCard
            key={model.id}
            model={model}
            credential={credentialsById.get(model.provider_credential_id)}
            onClick={() => openEditModel(model.id)}
          />
        ))}
        <CreateCard onClick={openCreateModel} />
      </div>

      <div className="rounded-xl border border-border/90 bg-surface/60 p-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-background text-primary-light">
            <Archive className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-semibold text-white">Runtime cost separation</p>
            <p className="mt-1 text-sm leading-6 text-muted">Credentials hold access. ProviderModels hold model identifiers and token pricing. Agents only reference ProviderModels, and runtime snapshots the pricing used by each LLM call.</p>
          </div>
        </div>
      </div>

      <ModelDialog
        open={showModelDialog}
        onClose={handleCloseModelDialog}
        projectId={projectId || ''}
        credentials={credentials}
        selectedModel={selectedModel}
      />

      <AddProviderCredentialModal
        open={showCredentialDialog}
        onClose={() => setShowCredentialDialog(false)}
        projectId={projectId || ''}
        onCredentialCreated={handleCredentialCreated}
      />
    </MinimalShell>
  )
}
