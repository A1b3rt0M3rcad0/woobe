import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Cpu, Plus } from 'lucide-react'
import { Button, Select } from '@woobe/ui'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ResourceCard, ResourcePill } from '@/components/common/OperationalResourceCard'
import {
  ResourceEmptyState,
  ResourcePage,
  ResourceSearch,
  ResourceSectionHeader,
  ResourceTabs,
  ResourceToolbar,
} from '@/components/common/ResourcePage'
import { StatusBadge } from '@/components/common/StatusBadge'
import { useCredentials } from '@/features/provider-credentials/hooks'
import type { ProviderCredential } from '@/features/provider-credentials/types'
import { ModelSettingsModal } from '@/features/provider-models/components/ModelSettingsModal'
import { providerModelCapabilities } from '@/features/provider-models/capabilities'
import { useProviderModels } from '@/features/provider-models/hooks'
import type { ProviderModel } from '@/features/provider-models/types'

type ModelStatusFilter = 'all' | 'active' | 'inactive'

const providerLabels: Record<string, string> = {
  openai: 'OpenAI',
  custom: 'OpenAI Compatible',
  openrouter: 'OpenRouter',
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

function capacityText(value: number | null) {
  return value == null ? 'Context unknown' : `${value.toLocaleString()} context`
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : 'Never'
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
  const capabilities = providerModelCapabilities(model)
  return (
    <ResourceCard
      onClick={onClick}
      aria-label={`Open Model ${model.name}`}
      icon={<Cpu className="h-icon-lg w-icon-lg" />}
      title={model.name}
      subtitle={model.model}
      status={<StatusBadge status={model.status || 'active'} size="compact" />}
      metadata={(
        <>
          <ResourcePill tone="primary">{providerLabel(model.provider || credential?.provider)}</ResourcePill>
          {credential?.name && <ResourcePill>{credential.name}</ResourcePill>}
          <ResourcePill>{capacityText(capabilities.contextWindow)}</ResourcePill>
          <ResourcePill>In · {priceText(pricing.input, pricing.currency)}</ResourcePill>
          <ResourcePill>Out · {priceText(pricing.output, pricing.currency)}</ResourcePill>
        </>
      )}
      footer={`Updated · ${formatDate(model.updated_at || model.created_at)}`}
    />
  )
}

export default function ModelsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const credentialsQuery = useCredentials(projectId)
  const modelsQuery = useProviderModels(projectId)

  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<ModelStatusFilter>('all')
  const [providerFilter, setProviderFilter] = useState('all')
  const [showModelDialog, setShowModelDialog] = useState(false)
  const [selectedModel, setSelectedModel] = useState<ProviderModel | null>(null)

  const credentials = credentialsQuery.data ?? []
  const models = modelsQuery.data ?? []
  const credentialsById = useMemo(() => new Map(credentials.map((credential) => [credential.id, credential])), [credentials])
  const generationModels = useMemo(
    () => models.filter((model) => model.status !== 'archived' && !isEmbeddingModel(model)),
    [models],
  )
  const statusCounts = useMemo(() => ({
    all: generationModels.length,
    active: generationModels.filter((model) => model.status?.toLowerCase() === 'active').length,
    inactive: generationModels.filter((model) => model.status?.toLowerCase() === 'inactive').length,
  }), [generationModels])
  const providerOptions = useMemo(() => Array.from(new Set(generationModels.map((model) => {
    const credential = credentialsById.get(model.provider_credential_id)
    return model.provider || credential?.provider
  }).filter((value): value is string => Boolean(value)))).sort(), [credentialsById, generationModels])
  const normalizedQuery = query.trim().toLowerCase()
  const visibleModels = useMemo(() => {
    return generationModels.filter((model) => {
      const credential = credentialsById.get(model.provider_credential_id)
      const provider = model.provider || credential?.provider || ''
      const matchesStatus = statusFilter === 'all' || model.status?.toLowerCase() === statusFilter
      const matchesProvider = providerFilter === 'all' || provider === providerFilter
      const matchesQuery = !normalizedQuery || `${model.name} ${model.model} ${providerLabel(provider)} ${credential?.name || ''}`.toLowerCase().includes(normalizedQuery)
      return matchesStatus && matchesProvider && matchesQuery
    })
  }, [generationModels, credentialsById, normalizedQuery, providerFilter, statusFilter])

  const openNewModel = () => {
    setSelectedModel(null)
    setShowModelDialog(true)
  }

  const openExistingModel = (model: ProviderModel) => {
    setSelectedModel(model)
    setShowModelDialog(true)
  }

  if (!projectId) return <ErrorState message="Project not found" />
  const isLoading = credentialsQuery.isLoading || modelsQuery.isLoading
  const isError = credentialsQuery.isError || modelsQuery.isError
  const hasFilters = Boolean(normalizedQuery) || statusFilter !== 'all' || providerFilter !== 'all'
  const resultCount = hasFilters ? `${visibleModels.length} of ${generationModels.length}` : generationModels.length

  return (
    <ResourcePage
      title="Models"
      description="Create and manage reusable generation models bound to provider connections."
      action={(
        <Button type="button" onClick={openNewModel}>
          <Plus className="h-icon w-icon" />
          New Model
        </Button>
      )}
    >
      <ResourceToolbar>
        <ResourceTabs
          value={statusFilter}
          onChange={setStatusFilter}
          label="Filter Models by status"
          tabs={[
            { value: 'all', label: 'All', count: statusCounts.all },
            { value: 'active', label: 'Active', count: statusCounts.active },
            { value: 'inactive', label: 'Inactive', count: statusCounts.inactive },
          ]}
        />
        <div className="grid gap-ui-sm lg:grid-cols-[minmax(0,1fr)_220px]">
          <ResourceSearch value={query} onChange={setQuery} placeholder="Search Models, providers or credentials..." label="Search Models" />
          <Select
            value={providerFilter}
            onChange={(event) => setProviderFilter(event.target.value)}
            options={[
              { value: 'all', label: 'All providers' },
              ...providerOptions.map((provider) => ({ value: provider, label: providerLabel(provider) })),
            ]}
          />
        </div>
      </ResourceToolbar>

      <section>
        <ResourceSectionHeader
          title="Generation models"
          description="Open a Model to review its binding, capabilities, pricing and lifecycle."
          count={resultCount}
        />

        {isLoading ? (
          <LoadingState message="Loading Models" variant="panel" layout="compact-cards" />
        ) : isError ? (
          <ErrorState
            message="Failed to load provider Models"
            onRetry={() => { void credentialsQuery.refetch(); void modelsQuery.refetch() }}
            className="rounded-container border border-border bg-surface/70 py-10"
          />
        ) : visibleModels.length > 0 ? (
          <div className="grid grid-cols-1 gap-ui-md md:grid-cols-2 xl:grid-cols-3">
            {visibleModels.map((model) => (
              <ModelCard
                key={model.id}
                model={model}
                credential={credentialsById.get(model.provider_credential_id)}
                onClick={() => openExistingModel(model)}
              />
            ))}
          </div>
        ) : (
          <ResourceEmptyState
            icon={<Cpu className="h-icon-lg w-icon-lg" />}
            title={generationModels.length === 0 ? 'No Generation models yet' : 'No Models found'}
            description={generationModels.length === 0
              ? 'Create a Model. The flow will request a provider connection when necessary.'
              : 'Adjust the search or clear the active filters.'}
            action={hasFilters ? (
              <Button type="button" size="sm" variant="outline" onClick={() => { setQuery(''); setStatusFilter('all'); setProviderFilter('all') }}>
                Clear filters
              </Button>
            ) : undefined}
          />
        )}
      </section>

      <ModelSettingsModal
        open={showModelDialog}
        onClose={() => {
          setShowModelDialog(false)
          setSelectedModel(null)
        }}
        projectId={projectId}
        credentials={credentials}
        selectedModel={selectedModel}
        onSaved={() => { void Promise.all([modelsQuery.refetch(), credentialsQuery.refetch()]) }}
      />
    </ResourcePage>
  )
}
