import { useMemo, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { useCollections, useCreateCollection, useDocuments, useUploadDocument } from '@/features/knowledge/hooks'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Table } from '@/components/ui/Table'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Tabs } from '@/components/ui/Tabs'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { createCollectionSchema, type CreateCollectionFormData } from '@/features/knowledge/schemas'
import { Database, FileText, Plus, Search, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { formatBytes } from '@/lib/formatters/bytes'
import { formatDate } from '@/lib/formatters/date'
import type { Collection, Document } from '@/features/knowledge/types'

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

function CreateCard({ title, description, icon, compact = false, onClick }: { title: string; description: string; icon: ReactNode; compact?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`${compact ? 'min-h-[160px]' : 'min-h-[240px]'} group flex flex-col items-center justify-center rounded-xl border border-dashed border-primary/40 bg-surface/35 p-6 text-center transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/60 hover:bg-primary/5 hover:shadow-lg hover:shadow-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 focus-visible:ring-offset-background`}
    >
      <span className="flex h-14 w-14 items-center justify-center rounded-full border border-primary/50 bg-primary/10 text-primary-light transition-colors duration-200 group-hover:bg-primary/15">
        {icon}
      </span>
      <span className="mt-5 text-base font-semibold text-white">{title}</span>
      <span className="mt-2 max-w-[220px] text-sm leading-6 text-muted">{description}</span>
    </button>
  )
}

function NoResults({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-xl border border-border/80 bg-surface/50 px-5 py-4">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <p className="mt-1 text-sm text-muted">{description}</p>
    </div>
  )
}

export default function KnowledgePage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: collections, isLoading: colsLoading, isError: colsError, refetch: refetchCols } = useCollections(projectId)
  const { data: documents, isLoading: docsLoading } = useDocuments(projectId)
  const createCollection = useCreateCollection()
  const uploadDocument = useUploadDocument()
  const [showCreateCol, setShowCreateCol] = useState(false)
  const [showUpload, setShowUpload] = useState(false)
  const [query, setQuery] = useState('')

  const colForm = useForm<CreateCollectionFormData>({
    resolver: zodResolver(createCollectionSchema),
  })

  const [uploadColId, setUploadColId] = useState('')
  const [uploadTitle, setUploadTitle] = useState('')

  const handleCreateCollection = async (data: CreateCollectionFormData) => {
    try {
      await createCollection.mutateAsync({ project_id: projectId!, name: data.name, description: data.description })
      toast.success('Collection created')
      setShowCreateCol(false)
      colForm.reset()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create collection')
    }
  }

  const handleUpload = async () => {
    if (!uploadColId) {
      toast.error('Select a collection')
      return
    }
    try {
      await uploadDocument.mutateAsync({
        project_id: projectId!,
        collection_id: uploadColId,
        title: uploadTitle || 'Untitled',
        file_name: 'sample.pdf',
        content_type: 'application/pdf',
        size_bytes: 0,
      })
      toast.success('Document uploaded')
      setShowUpload(false)
      setUploadTitle('')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to upload document')
    }
  }

  const docColumns = [
    { key: 'title', header: 'Title' },
    { key: 'file_name', header: 'File' },
    { key: 'content_type', header: 'Type' },
    { key: 'size_bytes', header: 'Size', render: (d: Document) => formatBytes(d.size_bytes) },
    { key: 'status', header: 'Status', render: (d: Document) => <StatusBadge status={d.status} /> },
    { key: 'created_at', header: 'Created', render: (d: Document) => d.created_at ? formatDate(d.created_at) : '—' },
  ]

  const collectionItems = collections ?? []
  const documentItems = documents ?? []

  const visibleCollections = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) return collectionItems

    return collectionItems.filter((collection) => (
      collection.name.toLowerCase().includes(normalizedQuery)
      || collection.description?.toLowerCase().includes(normalizedQuery)
    ))
  }, [collectionItems, query])

  const visibleDocuments = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) return documentItems

    return documentItems.filter((document) => (
      document.title.toLowerCase().includes(normalizedQuery)
      || document.file_name.toLowerCase().includes(normalizedQuery)
      || document.content_type.toLowerCase().includes(normalizedQuery)
      || document.status?.toLowerCase().includes(normalizedQuery)
    ))
  }, [documentItems, query])

  if (colsLoading || docsLoading) return <LoadingState />
  if (colsError) return <ErrorState onRetry={refetchCols} />

  const hasCollectionSearchMiss = query.trim().length > 0 && visibleCollections.length === 0
  const hasDocumentSearchMiss = query.trim().length > 0 && visibleDocuments.length === 0

  const tabs = [
    {
      id: 'collections',
      label: 'Collections',
      content: (
        <div className="space-y-4">
          {hasCollectionSearchMiss && (
            <NoResults title="No collections found" description="Create a new collection or adjust the search term." />
          )}

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {visibleCollections.map((col: Collection) => (
              <article
                key={col.id}
                className="flex min-h-[240px] flex-col rounded-xl border border-border/90 bg-surface/70 p-6 transition-[border-color,background-color,box-shadow] duration-200 hover:border-primary/35 hover:bg-surface/85 hover:shadow-lg hover:shadow-primary/5"
              >
                <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-background text-primary-light shadow-sm">
                  <Database className="h-5 w-5" />
                </div>
                <div className="mt-6 min-w-0">
                  <h2 className="truncate text-base font-semibold text-white">{col.name}</h2>
                  <p className="mt-2 line-clamp-3 text-sm leading-6 text-muted">{col.description || 'No description provided'}</p>
                </div>
                <div className="my-5 h-px bg-border/80" />
                <p className="mt-auto text-sm leading-6 text-muted">Retrievable documents grouped for agent runtime use.</p>
              </article>
            ))}

            <CreateCard
              title="New collection"
              description="Group documents for retrieval"
              icon={<Plus className="h-6 w-6" />}
              onClick={() => setShowCreateCol(true)}
            />
          </div>
        </div>
      ),
    },
    {
      id: 'documents',
      label: 'Documents',
      content: (
        <div className="space-y-4">
          {hasDocumentSearchMiss && (
            <NoResults title="No documents found" description="Upload a new document or adjust the search term." />
          )}

          <CreateCard
            title="Upload document"
            description="Add source material for retrieval"
            icon={<Upload className="h-6 w-6" />}
            compact
            onClick={() => setShowUpload(true)}
          />

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
    <MinimalShell
      title="Knowledge"
      description="Upload and organize documents your agents can retrieve from during runtime."
    >
      <div className="relative max-w-3xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search knowledge..."
          className="h-11 pl-9"
        />
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

      <Dialog open={showUpload} onClose={() => setShowUpload(false)} title="Upload Document">
        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-muted">Collection</label>
            <select
              value={uploadColId}
              onChange={(e) => setUploadColId(e.target.value)}
              className="flex h-9 w-full rounded-lg border border-border bg-transparent px-3 py-1 text-sm"
            >
              <option value="">Select collection</option>
              {collectionItems.map((c: Collection) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <Input
            value={uploadTitle}
            onChange={(e) => setUploadTitle(e.target.value)}
            placeholder="Document title"
          />
          <div className="rounded-lg border-2 border-dashed border-border p-8 text-center">
            <Upload className="mx-auto mb-2 h-8 w-8 text-muted" />
            <p className="text-sm text-muted">Drop file here or click to browse</p>
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setShowUpload(false)}>Cancel</Button>
            <Button onClick={handleUpload} loading={uploadDocument.isPending}>Upload</Button>
          </div>
        </div>
      </Dialog>
    </MinimalShell>
  )
}
