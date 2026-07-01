import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { AlertTriangle, Database, Plus, Search, Trash2, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Table } from '@/components/ui/Table'
import { Tabs } from '@/components/ui/Tabs'
import { Textarea } from '@/components/ui/Textarea'
import { CollectionDetailsModal } from '@/features/knowledge/components/CollectionDetailsModal'
import { UploadDocumentModal } from '@/features/knowledge/components/UploadDocumentModal'
import { createCollectionSchema, type CreateCollectionFormData } from '@/features/knowledge/schemas'
import { useCollections, useCreateCollection, useDeleteDocument, useDocuments } from '@/features/knowledge/hooks'
import { formatBytes } from '@/lib/formatters/bytes'
import { formatDate } from '@/lib/formatters/date'
import type { Collection, Document } from '@/features/knowledge/types'

export default function KnowledgePageWithCollectionDetails() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: collections, isLoading: colsLoading, isError: colsError, refetch: refetchCols } = useCollections(projectId)
  const { data: documents, isLoading: docsLoading } = useDocuments(projectId)
  const createCollection = useCreateCollection()
  const deleteDocument = useDeleteDocument()
  const [showCreateCol, setShowCreateCol] = useState(false)
  const [showUpload, setShowUpload] = useState(false)
  const [documentToDelete, setDocumentToDelete] = useState<Document | null>(null)
  const [query, setQuery] = useState('')
  const [selectedCollectionId, setSelectedCollectionId] = useState<string | null>(null)

  const colForm = useForm<CreateCollectionFormData>({ resolver: zodResolver(createCollectionSchema) })

  const collectionItems = collections ?? []
  const documentItems = documents ?? []
  const collectionNames = useMemo(() => {
    return collectionItems.reduce<Record<string, string>>((acc, collection) => {
      acc[collection.id] = collection.name
      return acc
    }, {})
  }, [collectionItems])

  const getDocumentCollectionName = (document: Document) => collectionNames[document.collection_id] || document.collection_id.slice(0, 8)

  const selectedCollection = collectionItems.find((collection) => collection.id === selectedCollectionId) ?? null

  const closeDeleteModal = () => {
    if (deleteDocument.isPending) return
    setDocumentToDelete(null)
  }

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

  const handleConfirmDeleteDocument = async () => {
    if (!documentToDelete) return

    try {
      await deleteDocument.mutateAsync(documentToDelete.id)
      toast.success('Document deleted')
      setDocumentToDelete(null)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete document')
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

  const visibleDocuments = useMemo(() => {
    if (!normalizedQuery) return documentItems
    return documentItems.filter((document) => {
      const collectionName = collectionNames[document.collection_id] || ''
      return (
        document.title.toLowerCase().includes(normalizedQuery)
        || document.file_name.toLowerCase().includes(normalizedQuery)
        || document.content_type.toLowerCase().includes(normalizedQuery)
        || document.status?.toLowerCase().includes(normalizedQuery)
        || collectionName.toLowerCase().includes(normalizedQuery)
      )
    })
  }, [documentItems, collectionNames, normalizedQuery])

  if (colsLoading || docsLoading) return <LoadingState />
  if (colsError) return <ErrorState onRetry={refetchCols} />

  const docColumns = [
    { key: 'title', header: 'Title', className: 'min-w-[220px]' },
    {
      key: 'collection_id',
      header: 'Collection',
      render: (d: Document) => getDocumentCollectionName(d),
      className: 'min-w-[160px]',
    },
    { key: 'file_name', header: 'File', className: 'min-w-[220px]' },
    { key: 'content_type', header: 'Type', className: 'min-w-[140px]' },
    { key: 'size_bytes', header: 'Size', render: (d: Document) => formatBytes(d.size_bytes), className: 'min-w-[100px]' },
    { key: 'status', header: 'Status', render: (d: Document) => <StatusBadge status={d.status} />, className: 'min-w-[110px]' },
    { key: 'created_at', header: 'Created', render: (d: Document) => d.created_at ? formatDate(d.created_at) : '-', className: 'min-w-[120px]' },
    {
      key: 'actions',
      header: '',
      className: 'w-[72px] text-right',
      render: (d: Document) => (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-red-400 hover:text-red-300"
          disabled={deleteDocument.isPending}
          onClick={(event) => {
            event.stopPropagation()
            setDocumentToDelete(d)
          }}
          aria-label={`Delete ${d.title}`}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      ),
    },
  ]

  const tabs = [
    {
      id: 'collections',
      label: 'Collections',
      content: (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
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
          <button
            type="button"
            onClick={() => setShowCreateCol(true)}
            className="group flex min-h-[220px] flex-col items-center justify-center rounded-xl border border-dashed border-primary/40 bg-surface/35 p-6 text-center transition-colors hover:border-primary/60 hover:bg-primary/5"
          >
            <Plus className="h-6 w-6 text-primary-light" />
            <span className="mt-4 text-base font-semibold text-white">New collection</span>
            <span className="mt-2 text-sm text-muted">Group documents for retrieval</span>
          </button>
        </div>
      ),
    },
    {
      id: 'documents',
      label: 'Documents',
      content: (
        <div className="space-y-4">
          <button
            type="button"
            onClick={() => setShowUpload(true)}
            className="group flex min-h-[160px] w-full flex-col items-center justify-center rounded-xl border border-dashed border-primary/40 bg-surface/35 p-6 text-center transition-colors hover:border-primary/60 hover:bg-primary/5"
          >
            <Upload className="h-6 w-6 text-primary-light" />
            <span className="mt-4 text-base font-semibold text-white">Upload document</span>
            <span className="mt-2 text-sm text-muted">Add TXT, MD or PDF source material</span>
          </button>
          {visibleDocuments.length > 0 && (
            <Card className="border-border/90 bg-surface/70">
              <CardContent className="p-0">
                <Table columns={docColumns} data={visibleDocuments} keyExtractor={(d) => d.id} />
              </CardContent>
            </Card>
          )}
        </div>
      ),
    },
  ]

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">Knowledge</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">Upload and organize documents your agents can retrieve from during runtime.</p>
      </div>

      <div className="relative max-w-3xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search knowledge..." className="h-11 pl-9" />
      </div>

      <Tabs tabs={tabs} />

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

      <Dialog
        open={Boolean(documentToDelete)}
        onClose={closeDeleteModal}
        title="Delete document"
        className="max-w-[460px]"
      >
        {documentToDelete && (
          <div className="space-y-5">
            <div className="flex gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-red-500/20 bg-red-500/10 text-red-400">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div className="min-w-0 space-y-1">
                <p className="text-sm font-medium text-white">Remove this document?</p>
                <p className="text-sm leading-6 text-muted">
                  This action deletes the document record, stored file and generated chunks. It cannot be undone.
                </p>
              </div>
            </div>

            <div className="rounded-xl border border-border bg-background/70 p-3">
              <p className="truncate text-sm font-medium text-white">{documentToDelete.title}</p>
              <p className="mt-1 truncate text-xs text-muted">{documentToDelete.file_name}</p>
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                <span>{getDocumentCollectionName(documentToDelete)}</span>
                <span>{formatBytes(documentToDelete.size_bytes)}</span>
                <span>{documentToDelete.content_type}</span>
              </div>
            </div>

            <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" onClick={closeDeleteModal} disabled={deleteDocument.isPending}>
                Cancel
              </Button>
              <Button
                type="button"
                variant="destructive"
                loading={deleteDocument.isPending}
                onClick={handleConfirmDeleteDocument}
              >
                Delete document
              </Button>
            </div>
          </div>
        )}
      </Dialog>

      <CollectionDetailsModal
        open={Boolean(selectedCollection)}
        onClose={() => setSelectedCollectionId(null)}
        collection={selectedCollection}
        projectId={projectId || ''}
      />

      <UploadDocumentModal
        open={showUpload}
        onClose={() => setShowUpload(false)}
        projectId={projectId || ''}
        collectionIds={collectionItems.map((collection: Collection) => ({ id: collection.id, name: collection.name }))}
      />
    </div>
  )
}
