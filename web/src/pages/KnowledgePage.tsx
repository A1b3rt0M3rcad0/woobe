import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Database, Plus } from 'lucide-react'

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
import { Button } from '@/components/ui/Button'
import { CollectionDetailsModal } from '@/features/knowledge/components/CollectionDetailsModalV2'
import { KnowledgeEmbeddingPanel } from '@/features/knowledge/components/CollectionVectorWorkspace'
import { CreateCollectionModal } from '@/features/knowledge/components/CreateCollectionModal'
import { useCollections } from '@/features/knowledge/hooks'
import type { Collection } from '@/features/knowledge/types'

type Section = 'collections' | 'embedding'

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : 'Not recorded'
}

export default function KnowledgePage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: collections, isLoading, isError, error, refetch } = useCollections(projectId)
  const [section, setSection] = useState<Section>('collections')
  const [showCreateCollection, setShowCreateCollection] = useState(false)
  const [showCreateEmbeddingModel, setShowCreateEmbeddingModel] = useState(false)
  const [collectionQuery, setCollectionQuery] = useState('')
  const [embeddingQuery, setEmbeddingQuery] = useState('')
  const [embeddingCount, setEmbeddingCount] = useState(0)
  const [selectedCollectionId, setSelectedCollectionId] = useState<string | null>(null)

  const items = collections ?? []
  const selectedCollection = items.find((collection) => collection.id === selectedCollectionId) ?? null
  const normalizedQuery = collectionQuery.trim().toLowerCase()
  const visibleCollections = useMemo(() => {
    if (!normalizedQuery) return items
    return items.filter((collection) => [
      collection.name,
      collection.description ?? '',
      collection.status ?? '',
    ].some((value) => value.toLowerCase().includes(normalizedQuery)))
  }, [items, normalizedQuery])

  if (!projectId) return <ErrorState message="Project not found" />

  const activeQuery = section === 'collections' ? collectionQuery : embeddingQuery
  const collectionCount = normalizedQuery ? `${visibleCollections.length} of ${items.length}` : items.length

  return (
    <ResourcePage
      title="Knowledge"
      description="Create Collections, add Documents and build versioned vector snapshots."
      action={(
        <Button
          type="button"
          onClick={() => {
            if (section === 'collections') setShowCreateCollection(true)
            else setShowCreateEmbeddingModel(true)
          }}
        >
          <Plus className="mr-2 h-4 w-4" />
          {section === 'collections' ? 'New Collection' : 'Add Embedding Model'}
        </Button>
      )}
    >
      <ResourceToolbar>
        <ResourceTabs
          value={section}
          onChange={setSection}
          label="Knowledge resource type"
          tabs={[
            { value: 'collections', label: 'Collections', count: items.length },
            { value: 'embedding', label: 'Embedding models', count: embeddingCount },
          ]}
        />
        <ResourceSearch
          value={activeQuery}
          onChange={section === 'collections' ? setCollectionQuery : setEmbeddingQuery}
          placeholder={section === 'collections' ? 'Search Collections...' : 'Search Embedding models...'}
          label={section === 'collections' ? 'Search Collections' : 'Search Embedding models'}
        />
      </ResourceToolbar>

      {section === 'collections' ? (
        <section>
          <ResourceSectionHeader
            title="Collections"
            description="Open a Collection to manage Documents, vector readiness and snapshots."
            count={collectionCount}
          />

          {isLoading ? (
            <LoadingState message="Loading Collections" variant="panel" layout="compact-cards" />
          ) : isError ? (
            <ErrorState error={error} onRetry={refetch} className="rounded-xl border border-border/80 bg-surface/40 py-10" />
          ) : visibleCollections.length > 0 ? (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {visibleCollections.map((collection: Collection) => (
                <ResourceCard
                  key={collection.id}
                  aria-label={`Open Collection ${collection.name}`}
                  onClick={() => setSelectedCollectionId(collection.id)}
                  icon={<Database className="h-4 w-4" />}
                  title={collection.name}
                  subtitle={collection.description || 'No description provided'}
                  status={collection.status ? <StatusBadge status={collection.status} size="compact" /> : undefined}
                  metadata={(
                    <>
                      <ResourcePill>{collection.documents_count ?? 0} Documents</ResourcePill>
                      <ResourcePill tone={(collection.indexed_documents_count ?? 0) > 0 ? 'primary' : 'default'}>
                        {collection.indexed_documents_count ?? 0} indexed
                      </ResourcePill>
                    </>
                  )}
                  footer={`Updated · ${formatDate(collection.updated_at || collection.created_at)}`}
                />
              ))}
            </div>
          ) : (
            <ResourceEmptyState
              icon={<Database className="h-4 w-4" />}
              title={items.length === 0 ? 'No Collections yet' : 'No Collections found'}
              description={items.length === 0
                ? 'Create the first Collection, then add Documents inside it.'
                : 'Adjust the search or clear it to see every Collection.'}
              action={collectionQuery ? (
                <Button type="button" size="sm" variant="outline" onClick={() => setCollectionQuery('')}>
                  Clear search
                </Button>
              ) : undefined}
            />
          )}
        </section>
      ) : (
        <KnowledgeEmbeddingPanel
          projectId={projectId}
          query={embeddingQuery}
          onQueryChange={setEmbeddingQuery}
          createOpen={showCreateEmbeddingModel}
          onCreateOpenChange={setShowCreateEmbeddingModel}
          onCountChange={setEmbeddingCount}
        />
      )}

      <CreateCollectionModal
        open={showCreateCollection}
        onClose={() => setShowCreateCollection(false)}
        projectId={projectId}
      />

      <CollectionDetailsModal
        open={Boolean(selectedCollection)}
        onClose={() => setSelectedCollectionId(null)}
        collection={selectedCollection}
        projectId={projectId}
      />
    </ResourcePage>
  )
}
