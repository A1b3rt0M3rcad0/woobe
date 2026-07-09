import { useMemo, useState } from 'react'
import { Plus, Search } from 'lucide-react'

import { CreateResourceCard } from '@/components/common/CreateResourceCard'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useCredentials } from '@/features/provider-credentials/hooks'
import { useProviderModels } from '@/features/provider-models/hooks'
import type { ProviderModel } from '@/features/provider-models/types'
import { CreateEmbeddingModelModal } from '@/features/knowledge/components/CreateEmbeddingModelModal'
import { EmbeddingModelCard } from '@/features/knowledge/components/EmbeddingModelCard'

interface KnowledgeEmbeddingPanelProps {
  projectId: string
}

function isEmbeddingModel(model: ProviderModel) {
  const metadata = model.metadata || {}
  const capability = String(metadata.capability || metadata.type || '').toLowerCase()
  return capability === 'embedding' || capability === 'embeddings' || model.model.toLowerCase().includes('embed')
}

export function KnowledgeEmbeddingPanel({ projectId }: KnowledgeEmbeddingPanelProps) {
  const credentialsQuery = useCredentials(projectId)
  const modelsQuery = useProviderModels(projectId)
  const credentials = credentialsQuery.data ?? []
  const models = modelsQuery.data ?? []

  const [query, setQuery] = useState('')
  const [modelModalOpen, setModelModalOpen] = useState(false)
  const [selectedModel, setSelectedModel] = useState<ProviderModel | null>(null)

  const embeddingModels = useMemo(
    () => models.filter((model) => isEmbeddingModel(model) && model.status !== 'archived'),
    [models],
  )
  const normalizedQuery = query.trim().toLowerCase()
  const visibleModels = useMemo(() => {
    if (!normalizedQuery) return embeddingModels
    return embeddingModels.filter((model) => `${model.name} ${model.model} ${model.provider || ''}`.toLowerCase().includes(normalizedQuery))
  }, [embeddingModels, normalizedQuery])

  const openNewModel = () => {
    setSelectedModel(null)
    setModelModalOpen(true)
  }

  if (credentialsQuery.isLoading || modelsQuery.isLoading) return <LoadingState />
  if (credentialsQuery.isError || modelsQuery.isError) {
    return <ErrorState onRetry={() => { void credentialsQuery.refetch(); void modelsQuery.refetch() }} />
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Embedding models</h2>
          <p className="mt-1 max-w-3xl text-sm text-muted">Create and manage reusable embedding models for vector snapshots and retrieval.</p>
        </div>
        <Button type="button" onClick={openNewModel}>
          <Plus className="mr-2 h-4 w-4" />
          Add embedding model
        </Button>
      </div>

      <div className="relative max-w-3xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search embedding models..." className="h-11 pl-9" />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <CreateResourceCard
          title="Add embedding model"
          description="Create a reusable embedding model from a provider connection"
          minHeight="sm"
          onClick={openNewModel}
        />

        {visibleModels.map((model) => (
          <EmbeddingModelCard
            key={model.id}
            model={model}
            credential={credentials.find((credential) => credential.id === model.provider_credential_id)}
            onClick={() => {
              setSelectedModel(model)
              setModelModalOpen(true)
            }}
          />
        ))}

        {visibleModels.length === 0 && (
          <div className="flex min-h-[220px] flex-col rounded-xl border border-border/80 bg-surface/50 p-6">
            <p className="text-base font-semibold text-white">{normalizedQuery ? 'No embedding models found' : 'No embedding models yet'}</p>
            <p className="mt-2 text-sm leading-6 text-muted">{normalizedQuery ? 'Adjust the search term.' : 'Add an embedding model. If no provider connection exists, the creation flow will ask for one.'}</p>
          </div>
        )}
      </div>

      <CreateEmbeddingModelModal
        open={modelModalOpen}
        projectId={projectId}
        model={selectedModel}
        onClose={() => {
          setModelModalOpen(false)
          setSelectedModel(null)
        }}
        onCreated={() => {
          setModelModalOpen(false)
          setSelectedModel(null)
        }}
      />
    </div>
  )
}
