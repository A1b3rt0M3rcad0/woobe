import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useCollections, useCreateCollection, useDocuments, useUploadDocument } from '@/features/knowledge/hooks'
import { PageHeader } from '@/components/common/PageHeader'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card'
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
import { BookOpen, Plus, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { formatBytes } from '@/lib/formatters/bytes'
import { formatDate } from '@/lib/formatters/date'
import type { Collection, Document } from '@/features/knowledge/types'

export default function KnowledgePage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: collections, isLoading: colsLoading, isError: colsError, refetch: refetchCols } = useCollections(projectId)
  const { data: documents, isLoading: docsLoading, refetch: refetchDocs } = useDocuments(projectId)
  const createCollection = useCreateCollection()
  const uploadDocument = useUploadDocument()
  const [showCreateCol, setShowCreateCol] = useState(false)
  const [showUpload, setShowUpload] = useState(false)

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
      toast.error(err instanceof Error ? err.message : 'Failed')
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
      toast.error(err instanceof Error ? err.message : 'Failed')
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

  if (colsLoading || docsLoading) return <LoadingState />
  if (colsError) return <ErrorState onRetry={refetchCols} />

  const tabs = [
    {
      id: 'collections',
      label: 'Collections',
      content: (
        <div>
          <div className="flex justify-end mb-4">
            <Button size="sm" onClick={() => setShowCreateCol(true)}>
              <Plus className="mr-1 h-4 w-4" />
              New Collection
            </Button>
          </div>
          {collections && collections.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {collections.map((col: Collection) => (
                <Card key={col.id}>
                  <CardHeader>
                    <CardTitle className="text-sm">{col.name}</CardTitle>
                    <CardDescription>{col.description || 'No description'}</CardDescription>
                  </CardHeader>
                </Card>
              ))}
            </div>
          ) : (
            <EmptyState icon={<BookOpen className="h-12 w-12" />} title="No collections" description="Create a collection to organize your documents." />
          )}
        </div>
      ),
    },
    {
      id: 'documents',
      label: 'Documents',
      content: (
        <div>
          <div className="flex justify-end mb-4">
            <Button size="sm" onClick={() => setShowUpload(true)}>
              <Upload className="mr-1 h-4 w-4" />
              Upload Document
            </Button>
          </div>
          {documents && documents.length > 0 ? (
            <Card>
              <CardContent className="p-0">
                <Table columns={docColumns} data={documents} keyExtractor={(d) => d.id} />
              </CardContent>
            </Card>
          ) : (
            <EmptyState icon={<BookOpen className="h-12 w-12" />} title="No documents" description="Upload documents to add knowledge to your agents." />
          )}
        </div>
      ),
    },
  ]

  return (
    <div>
      <PageHeader title="Knowledge" description="Document collections and RAG management" />
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
            <label className="block text-sm font-medium text-muted mb-1">Collection</label>
            <select
              value={uploadColId}
              onChange={(e) => setUploadColId(e.target.value)}
              className="flex h-9 w-full rounded-lg border border-border bg-transparent px-3 py-1 text-sm"
            >
              <option value="">Select collection</option>
              {(collections || []).map((c: Collection) => (
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
            <Upload className="mx-auto h-8 w-8 text-muted mb-2" />
            <p className="text-sm text-muted">Drop file here or click to browse</p>
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setShowUpload(false)}>Cancel</Button>
            <Button onClick={handleUpload} loading={uploadDocument.isPending}>Upload</Button>
          </div>
        </div>
      </Dialog>
    </div>
  )
}
