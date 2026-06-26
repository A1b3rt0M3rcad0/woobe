import { useState, useEffect } from 'react'
import { useAgentCollections, useDetachCollection } from '@/features/knowledge/hooks'
import { useCollections } from '@/features/knowledge/hooks'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { LoadingState } from '@/components/common/LoadingState'
import { EmptyState } from '@/components/common/EmptyState'
import { CreateCollectionModal } from '@/features/knowledge/components/CreateCollectionModal'
import { AttachCollectionModal } from '@/features/knowledge/components/AttachCollectionModal'
import { UploadDocumentModal } from '@/features/knowledge/components/UploadDocumentModal'
import { DocumentsDrawer } from '@/features/knowledge/components/DocumentsDrawer'
import { BookOpen, Plus, Link2, Upload, Eye, X, RefreshCw, AlertTriangle } from 'lucide-react'
import { toast } from 'sonner'
import { useAgentEditor } from '../AgentEditorContext'
import type { AgentCollection } from '@/features/knowledge/types'

interface KnowledgeTabProps {
  projectId: string
  agentId: string
}

export function KnowledgeTab({ projectId, agentId }: KnowledgeTabProps) {
  const { data: agentCollections, isLoading, refetch } = useAgentCollections(agentId)
  const { data: allCollections } = useCollections(projectId)
  const detachCollection = useDetachCollection()
  const { setField, updateBaseline } = useAgentEditor()

  const [showCreateCol, setShowCreateCol] = useState(false)
  const [showAttachCol, setShowAttachCol] = useState(false)
  const [showUpload, setShowUpload] = useState(false)
  const [drawerCollection, setDrawerCollection] = useState<{ id: string; name: string } | null>(null)

  const existingCollectionIds = (agentCollections || []).map((ac: AgentCollection) => ac.collection_id)

  useEffect(() => {
    if (existingCollectionIds.length > 0) {
      setField('collectionIds', existingCollectionIds)
      updateBaseline()
    }
  }, [existingCollectionIds.join(',')])

  const collectionNames = (allCollections || []).reduce<Record<string, string>>((acc, c) => {
    acc[c.id] = c.name
    return acc
  }, {})

  const handleDetach = async (ac: AgentCollection) => {
    try {
      await detachCollection.mutateAsync(ac.id)
      toast.success('Collection detached')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to detach')
    }
  }

  if (isLoading) return <LoadingState variant="panel" layout="list" message="Loading knowledge..." />

  return (
    <div className="p-4 space-y-4">
      {/* Async RAG Notice */}
      <div className="rounded-lg border border-blue-500/30 bg-blue-500/5 p-3">
        <div className="flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 text-blue-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-medium text-blue-300">Async-only Knowledge</p>
            <p className="text-xs text-muted mt-1">
              Knowledge is used by Async Ask jobs. Sync Ask does not use RAG.
            </p>
          </div>
        </div>
      </div>

      {!agentCollections || agentCollections.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface p-6">
          <EmptyState
            icon={<BookOpen className="h-10 w-10" />}
            title="No knowledge connected"
            description="Add documents to use Async Ask with RAG."
            action={
              <div className="flex gap-2 mt-2">
                <Button size="sm" onClick={() => setShowCreateCol(true)}>
                  <Plus className="mr-1 h-4 w-4" />
                  Create Collection
                </Button>
                <Button size="sm" variant="outline" onClick={() => setShowAttachCol(true)}>
                  <Link2 className="mr-1 h-4 w-4" />
                  Attach Existing
                </Button>
              </div>
            }
          />
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-muted uppercase tracking-wider">Attached Collections</p>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" onClick={() => refetch()}>
                <RefreshCw className="h-3 w-3" />
              </Button>
            </div>
          </div>
          <div className="space-y-2">
            {agentCollections.map((ac: AgentCollection) => {
              const colName = collectionNames[ac.collection_id] || ac.collection_id.slice(0, 8)
              return (
                <div key={ac.id} className="rounded-lg border border-border bg-background p-3 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">{colName}</p>
                    </div>
                    <Badge variant="success">active</Badge>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setDrawerCollection({ id: ac.collection_id, name: colName })}
                    >
                      <Eye className="mr-1 h-3 w-3" />
                      View
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setShowUpload(true)}>
                      <Upload className="mr-1 h-3 w-3" />
                      Upload
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-red-400 hover:text-red-300"
                      onClick={() => handleDetach(ac)}
                      loading={detachCollection.isPending}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              )
            })}
          </div>

          <div className="flex gap-2">
            <Button size="sm" onClick={() => setShowCreateCol(true)}>
              <Plus className="mr-1 h-4 w-4" />
              Create
            </Button>
            <Button size="sm" variant="outline" onClick={() => setShowAttachCol(true)}>
              <Link2 className="mr-1 h-4 w-4" />
              Attach
            </Button>
            <Button size="sm" variant="outline" onClick={() => setShowUpload(true)}>
              <Upload className="mr-1 h-4 w-4" />
              Upload
            </Button>
          </div>
        </>
      )}

      <CreateCollectionModal
        open={showCreateCol}
        onClose={() => setShowCreateCol(false)}
        projectId={projectId}
        agentId={agentId}
      />
      <AttachCollectionModal
        open={showAttachCol}
        onClose={() => setShowAttachCol(false)}
        projectId={projectId}
        agentId={agentId}
        existingCollectionIds={existingCollectionIds}
      />
      <UploadDocumentModal
        open={showUpload}
        onClose={() => setShowUpload(false)}
        projectId={projectId}
        collectionIds={(agentCollections || []).map((ac: AgentCollection) => ({
          id: ac.collection_id,
          name: collectionNames[ac.collection_id] || ac.collection_id.slice(0, 8),
        }))}
        defaultCollectionId={agentCollections?.[0]?.collection_id}
      />
      {drawerCollection && (
        <DocumentsDrawer
          open={true}
          onClose={() => setDrawerCollection(null)}
          collectionId={drawerCollection.id}
          collectionName={drawerCollection.name}
        />
      )}
    </div>
  )
}
