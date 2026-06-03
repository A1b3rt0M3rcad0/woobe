import { useState } from 'react'
import { useAgentCollections, useDetachCollection } from '@/features/knowledge/hooks'
import { useCollections } from '@/features/knowledge/hooks'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { LoadingState } from '@/components/common/LoadingState'
import { EmptyState } from '@/components/common/EmptyState'
import { CreateCollectionModal } from '@/features/knowledge/components/CreateCollectionModal'
import { AttachCollectionModal } from '@/features/knowledge/components/AttachCollectionModal'
import { UploadDocumentModal } from '@/features/knowledge/components/UploadDocumentModal'
import { DocumentsDrawer } from '@/features/knowledge/components/DocumentsDrawer'
import { BookOpen, Plus, Link2, Upload, Eye, X, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import type { AgentCollection } from '@/features/knowledge/types'

const collectionStatusVariant: Record<string, 'default' | 'secondary' | 'success' | 'warning' | 'destructive'> = {
  active: 'success',
  archived: 'secondary',
}

interface KnowledgePanelProps {
  projectId: string
  agentId: string
  organizationId?: string
}

export function KnowledgePanel({ projectId, agentId }: KnowledgePanelProps) {
  const { data: agentCollections, isLoading, refetch } = useAgentCollections(agentId)
  const { data: allCollections } = useCollections(projectId)
  const detachCollection = useDetachCollection()

  const [showCreateCol, setShowCreateCol] = useState(false)
  const [showAttachCol, setShowAttachCol] = useState(false)
  const [showUpload, setShowUpload] = useState(false)
  const [drawerCollection, setDrawerCollection] = useState<{ id: string; name: string } | null>(null)

  const existingCollectionIds = (agentCollections || []).map((ac: AgentCollection) => ac.collection_id)

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

  if (isLoading) return <LoadingState />

  return (
    <div className="space-y-4">
      {!agentCollections || agentCollections.length === 0 ? (
        <Card>
          <CardContent className="p-6">
            <EmptyState
              icon={<BookOpen className="h-10 w-10" />}
              title="No knowledge connected"
              description="Create or attach a collection to let this agent answer from your documents."
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
                  <Button size="sm" variant="outline" onClick={() => setShowUpload(true)} disabled>
                    <Upload className="mr-1 h-4 w-4" />
                    Upload Document
                  </Button>
                </div>
              }
            />
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs font-medium text-muted uppercase tracking-wider">Attached Collections</p>
            <Button variant="ghost" size="sm" onClick={() => refetch()}>
              <RefreshCw className="h-3 w-3" />
            </Button>
          </div>
          <div className="space-y-2">
            {agentCollections.map((ac: AgentCollection) => {
              const colName = collectionNames[ac.collection_id] || ac.collection_id.slice(0, 8)
              return (
                <div key={ac.id} className="rounded-lg border border-border p-3 space-y-2">
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
                      View Documents
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setShowUpload(true)
                      }}
                    >
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

          <div className="flex gap-2 pt-1">
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
