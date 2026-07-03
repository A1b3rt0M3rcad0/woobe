import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Database, Plus, Search } from 'lucide-react'
import { toast } from 'sonner'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { CreateResourceCard } from '@/components/common/CreateResourceCard'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { CollectionDetailsModal } from '@/features/knowledge/components/CollectionDetailsModal'
import { createCollectionSchema, type CreateCollectionFormData } from '@/features/knowledge/schemas'
import { useCollections, useCreateCollection } from '@/features/knowledge/hooks'
import type { Collection } from '@/features/knowledge/types'

export default function KnowledgePage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: collections, isLoading: colsLoading, isError: colsError, refetch: refetchCols } = useCollections(projectId)
  const createCollection = useCreateCollection()
  const [showCreateCol, setShowCreateCol] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedCollectionId, setSelectedCollectionId] = useState<string | null>(null)

  const colForm = useForm<CreateCollectionFormData>({ resolver: zodResolver(createCollectionSchema) })

  const collectionItems = collections ?? []
  const selectedCollection = collectionItems.find((collection) => collection.id === selectedCollectionId) ?? null

  const handleCreateCollection = async (data: CreateCollectionFormData) => {
    if (!projectId) return
    try {
      await createCollection.mutateAsync({
        project_id: projectId,
        name: data.name,
        description: data.description,
      })
      toast.success('Collection created')
      setShowCreateCol(false)
      colForm.reset()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create collection')
    }
  }

  const normalizedQuery = query.trim().toLowerCase()
  const visibleCollections = useMemo(() => {
    if (!normalizedQuery) return collectionItems
    return collectionItems.filter((collection) => (
      collection.name.toLowerCase().includes(normalizedQuery)
      || collection.description?.toLowerCase().includes(normalizedQuery)
    ))
  }, [collectionItems, normalizedQuery])

  if (colsLoading) return <LoadingState />
  if (colsError) return <ErrorState onRetry={refetchCols} />

  const hasNoCollections = collectionItems.length === 0
  const hasSearchMiss = normalizedQuery.length > 0 && visibleCollections.length === 0

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Knowledge</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted">
            Create collections and manage the documents in each collection directly from its details panel.
          </p>
        </div>
        <Button type="button" onClick={() => setShowCreateCol(true)} className="lg:mt-1">
          <Plus className="mr-2 h-4 w-4" />
          New collection
        </Button>
      </div>

      <div className="relative max-w-3xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search collections..." className="h-11 pl-9" />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <CreateResourceCard
          title="New collection"
          description="Group documents for retrieval"
          minHeight="sm"
          onClick={() => setShowCreateCol(true)}
        />

        {(hasNoCollections || hasSearchMiss) && (
          <div className="flex min-h-[220px] flex-col rounded-xl border border-border/80 bg-surface/50 p-6 text-left">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background text-primary-light">
              <Database className="h-5 w-5" />
            </div>
            <p className="mt-5 text-base font-semibold text-white">
              {hasSearchMiss ? 'No collections found' : 'No collections yet'}
            </p>
            <p className="mt-2 max-w-md text-sm leading-6 text-muted">
              {hasSearchMiss
                ? 'Adjust the search term or clear the filter to see all collections.'
                : 'Create a collection first. Documents are managed inside each collection.'}
            </p>
          </div>
        )}

        {visibleCollections.map((collection: Collection) => (
          <button
            key={collection.id}
            type="button"
            aria-label={`Open collection ${collection.name}`}
            onClick={() => setSelectedCollectionId(collection.id)}
            className="group flex min-h-[220px] flex-col rounded-xl border border-border/90 bg-surface/70 p-6 text-left transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/35 hover:bg-surface/85 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <span className="flex items-start justify-between gap-3">
              <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background text-primary-light shadow-sm transition-colors duration-200 group-hover:border-primary/30 group-hover:bg-primary/10">
                <Database className="h-5 w-5" />
              </span>
              {collection.status && <StatusBadge status={collection.status} />}
            </span>

            <span className="mt-6 block min-w-0">
              <span className="block truncate text-base font-semibold text-white">{collection.name}</span>
              <span className="mt-2 block line-clamp-3 text-sm leading-6 text-muted">
                {collection.description || 'No description provided'}
              </span>
            </span>
          </button>
        ))}
      </div>

      <Dialog open={showCreateCol} onClose={() => setShowCreateCol(false)} title="Create Collection">
        <form onSubmit={colForm.handleSubmit(handleCreateCollection)} className="space-y-4">
          <Input {...colForm.register('name')} error={colForm.formState.errors.name?.message} placeholder="Collection name" />
          <Textarea {...colForm.register('description')} placeholder="Description (optional)" />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setShowCreateCol(false)}>Cancel</Button>
            <Button type="submit" loading={createCollection.isPending}>Create</Button>
          </div>
        </form>
      </Dialog>

      <CollectionDetailsModal
        open={Boolean(selectedCollection)}
        onClose={() => setSelectedCollectionId(null)}
        collection={selectedCollection}
        projectId={projectId || ''}
      />
    </div>
  )
}
