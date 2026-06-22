import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useCollections, useCreateCollection, useDocuments, useUploadDocument } from '@/features/knowledge/hooks'
import { ProjectPageShell } from '@/components/common/ProjectPageShell'
import { GuidedEmptyState } from '@/components/common/GuidedEmptyState'
import { ResourceCard } from '@/components/common/ResourceCard'
import { ResourceSummaryCard } from '@/components/common/ResourceSummaryCard'
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
import { BookOpen, Database, FileText, Plus, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { formatBytes } from '@/lib/formatters/bytes'
import { formatDate } from '@/lib/formatters/date'
import type { Collection, Document } from '@/features/knowledge/types'

export default function KnowledgePage() {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: collections, isLoading: colsLoading, isError: colsError, refetch: refetchCols } = useCollections(projectId)
  const { data: documents, isLoading: docsLoading } = useDocuments(projectId)
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

  if (colsLoading || docsLoading) return <LoadingState />
  if (colsError) return <ErrorState onRetry={refetchCols} />

  const collectionItems = collections ?? []
  const documentItems = documents ?? []

  const tabs = [
    {
      id: 'collections',
      label: 'Collections',
      content: collectionItems.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {collectionItems.map((col: Collection) => (
            <ResourceCard
              key={col.id}
              icon={<Database className="h-5 w-5" />}
              title={col.name}
              description={col.description || 'No description provided'}
              metadata={<p className="rounded-lg border border-border/70 bg-background/70 p-3 text-sm text-muted">Use this collection to group retrievable documents for agents.</p>}
            />
          ))}
        </div>
      ) : (
        <GuidedEmptyState
          icon={<BookOpen className="h-6 w-6" />}
          title="No collections"
          description="Create a collection to group documents that agents can retrieve from."
          actionLabel="Create collection"
          onAction={() => setShowCreateCol(true)}
          next={["Create a collection", "Upload documents", "Attach knowledge to an agent"]}
        />
      ),
    },
    {
      id: 'documents',
      label: 'Documents',
      content: documentItems.length > 0 ? (
        <Card>
          <CardContent className="p-0">
            <Table columns={docColumns} data={documentItems} keyExtractor={(d) => d.id} />
          </CardContent>
        </Card>
      ) : (
        <GuidedEmptyState
          icon={<FileText className="h-6 w-6" />}
          title="No documents"
          description="Upload documents to make project knowledge available for retrieval."
          actionLabel="Upload document"
          onAction={() => setShowUpload(true)}
          next={["Choose a collection", "Upload content", "Review processing status"]}
        />
      ),
    },
  ]

  return (
    <ProjectPageShell
      eyebrow="Knowledge"
      title="Knowledge"
      description="Upload documents your agents can retrieve from during runtime."
      actions={
        <>
          <Button variant="outline" onClick={() => setShowUpload(true)}>
            <Upload className="mr-2 h-4 w-4" />
            Upload document
          </Button>
          <Button onClick={() => setShowCreateCol(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Create collection
          </Button>
        </>
      }
    >
      <div className="grid gap-4 md:grid-cols-3">
        <ResourceSummaryCard label="Collections" value={collectionItems.length} detail="Document groups" icon={<Database className="h-5 w-5" />} />
        <ResourceSummaryCard label="Documents" value={documentItems.length} detail="Uploaded sources" icon={<FileText className="h-5 w-5" />} />
        <ResourceSummaryCard label="Workflow" value="3 steps" detail="Create, upload, attach" icon={<BookOpen className="h-5 w-5" />} />
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
            <label className="block text-sm font-medium text-muted mb-1">Collection</label>
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
            <Upload className="mx-auto h-8 w-8 text-muted mb-2" />
            <p className="text-sm text-muted">Drop file here or click to browse</p>
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setShowUpload(false)}>Cancel</Button>
            <Button onClick={handleUpload} loading={uploadDocument.isPending}>Upload</Button>
          </div>
        </div>
      </Dialog>
    </ProjectPageShell>
  )
}
