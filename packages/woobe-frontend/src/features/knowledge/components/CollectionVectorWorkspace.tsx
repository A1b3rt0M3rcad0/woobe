import { useEffect, useMemo, useState } from 'react'
import { Cpu } from 'lucide-react'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { ResourceEmptyState, ResourceSectionHeader } from '@/components/common/ResourcePage'
import { Button } from '@/components/ui/Button'
import { CreateEmbeddingModelModal } from '@/features/knowledge/components/CreateEmbeddingModelModal'
import { EmbeddingModelCard } from '@/features/knowledge/components/EmbeddingModelCard'
import { useCredentials } from '@/features/provider-credentials/hooks'
import { useProviderModels } from '@/features/provider-models/hooks'
import type { ProviderModel } from '@/features/provider-models/types'

interface KnowledgeEmbeddingPanelProps {
  projectId: string
  query: string
  onQueryChange: (value: string) => void
  createOpen: boolean
  onCreateOpenChange: (open: boolean) => void
  onCountChange?: (count: number) => void
}

function isEmbeddingModel(model: ProviderModel) {
  const metadata = model.metadata || {}
  const capability = String(metadata.capability || metadata.type || '').toLowerCase()
  return capability === 'embedding' || capability === 'embeddings' || model.model.toLowerCase().includes('embed')
}

export function KnowledgeEmbeddingPanel({
  projectId,
  query,
  onQueryChange,
  createOpen,
  onCreateOpenChange,
  onCountChange,
}: KnowledgeEmbeddingPanelProps) {
  const credentialsQuery = useCredentials(projectId)
  const modelsQuery = useProviderModels(projectId)
  const credentials = credentialsQuery.data ?? []
  const models = modelsQuery.data ?? []
  const [selectedModel, setSelectedModel] = useState<ProviderModel | null>(null)

  const embeddingModels = useMemo(
    () => models.filter((model) => isEmbeddingModel(model) && model.status !== 'archived'),
    [models],
  )
  const normalizedQuery = query.trim().toLowerCase()
  const visibleModels = useMemo(() => {
    if (!normalizedQuery) return embeddingModels
    return embeddingModels.filter((model) => {
      const credential = credentials.find((item) => item.id === model.provider_credential_id)
      return [
        model.name,
        model.model,
        model.provider ?? '',
        model.status ?? '',
        credential?.name ?? '',
        credential?.provider ?? '',
      ].some((value) => value.toLowerCase().includes(normalizedQuery))
    })
  }, [credentials, embeddingModels, normalizedQuery])

  useEffect(() => {
    onCountChange?.(embeddingModels.length)
  }, [embeddingModels.length, onCountChange])

  const closeModal = () => {
    setSelectedModel(null)
    onCreateOpenChange(false)
  }
  const resultCount = normalizedQuery ? `${visibleModels.length} of ${embeddingModels.length}` : embeddingModels.length

  return (
    <section>
      <ResourceSectionHeader
        title="Embedding models"
        description="Reusable embedding bindings for vector snapshots and retrieval."
        count={resultCount}
      />

      {credentialsQuery.isLoading || modelsQuery.isLoading ? (
        <LoadingState message="Loading Embedding models" variant="panel" layout="compact-cards" />
      ) : credentialsQuery.isError || modelsQuery.isError ? (
        <ErrorState
          message="Failed to load Embedding models"
          onRetry={() => { void credentialsQuery.refetch(); void modelsQuery.refetch() }}
          className="rounded-xl border border-border/80 bg-surface/40 py-10"
        />
      ) : visibleModels.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visibleModels.map((model) => (
            <EmbeddingModelCard
              key={model.id}
              model={model}
              credential={credentials.find((credential) => credential.id === model.provider_credential_id)}
              onClick={() => setSelectedModel(model)}
            />
          ))}
        </div>
      ) : (
        <ResourceEmptyState
          icon={<Cpu className="h-4 w-4" />}
          title={embeddingModels.length === 0 ? 'No Embedding models yet' : 'No Embedding models found'}
          description={embeddingModels.length === 0
            ? 'Add an Embedding model from a provider connection.'
            : 'Adjust the search or clear it to see every Embedding model.'}
          action={query ? (
            <Button type="button" size="sm" variant="outline" onClick={() => onQueryChange('')}>
              Clear search
            </Button>
          ) : undefined}
        />
      )}

      <CreateEmbeddingModelModal
        open={createOpen || Boolean(selectedModel)}
        projectId={projectId}
        model={selectedModel}
        onClose={closeModal}
        onCreated={() => {
          closeModal()
          void modelsQuery.refetch()
        }}
      />
    </section>
  )
}

