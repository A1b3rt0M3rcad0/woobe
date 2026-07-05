import { useState } from 'react'
import { BookOpen, Database, RefreshCw, X } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { LoadingState } from '@/components/common/LoadingState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { useCreateKnowledgeVersion, useKnowledgeVersions } from '@/features/agents/hooks'
import { SelectKnowledgeVersionModal } from '@/features/knowledge/components/SelectKnowledgeVersionModal'
import { useCollections } from '@/features/knowledge/hooks'
import type { VectorSnapshot } from '@/features/knowledge/types'
import { useAgentEditor } from '../AgentEditorContext'

interface KnowledgeTabProps {
  projectId: string
  agentId: string
}

export function KnowledgeTab({ projectId, agentId }: KnowledgeTabProps) {
  const { data: versions = [], isLoading, refetch } = useKnowledgeVersions(agentId)
  const { data: collections = [] } = useCollections(projectId)
  const createKnowledgeVersion = useCreateKnowledgeVersion(agentId)
  const { state, setField } = useAgentEditor()
  const [selectorOpen, setSelectorOpen] = useState(false)

  const activeVersion = versions.find((version) => version.id === state.knowledgeVersionId) || null
  const metadata = activeVersion?.snapshot_metadata || {}
  const activeSnapshotId = typeof metadata.vector_snapshot_id === 'string' ? metadata.vector_snapshot_id : null
  const collectionId = activeVersion?.collection_ids?.[0] || null
  const collectionName = collections.find((collection) => collection.id === collectionId)?.name || 'Versioned knowledge'
  const snapshotVersion = typeof metadata.vector_snapshot_version === 'string' ? metadata.vector_snapshot_version : '—'
  const embeddingModel = typeof metadata.embedding_model === 'string' ? metadata.embedding_model : '—'
  const embeddingProvider = typeof metadata.embedding_provider === 'string' ? metadata.embedding_provider : '—'
  const documentCount = typeof metadata.document_count === 'number' ? metadata.document_count : 0
  const chunkCount = typeof metadata.chunk_count === 'number' ? metadata.chunk_count : 0

  const applySnapshot = async (snapshot: VectorSnapshot) => {
    try {
      const created = await createKnowledgeVersion.mutateAsync({
        project_id: projectId,
        agent_id: agentId,
        snapshot_metadata: { vector_snapshot_id: snapshot.id },
      } as any)
      setField('knowledgeVersionId', created.id)
      setSelectorOpen(false)
      toast.success(`${snapshot.version} applied to the Agent draft`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to apply knowledge')
    }
  }

  if (isLoading) return <LoadingState variant="panel" layout="list" message="Loading knowledge..." />

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium text-white">Knowledge</h2>
          <p className="mt-1 text-xs leading-5 text-muted">Apply one immutable vector version to this Agent draft.</p>
        </div>
        <Button type="button" size="sm" variant="ghost" onClick={() => refetch()}><RefreshCw className="h-3.5 w-3.5" /></Button>
      </div>

      {!activeVersion ? (
        <div className="rounded-xl border border-border bg-surface/50 p-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-background text-primary-light"><BookOpen className="h-4 w-4" /></div>
          <p className="mt-4 text-sm font-medium text-white">No knowledge version applied</p>
          <p className="mt-1 text-xs leading-5 text-muted">Build a vector version in Knowledge, then select the exact READY snapshot this Agent should use.</p>
          <Button type="button" size="sm" className="mt-4" onClick={() => setSelectorOpen(true)}><Database className="mr-2 h-3.5 w-3.5" />Select knowledge</Button>
        </div>
      ) : (
        <div className="rounded-xl border border-primary/25 bg-primary/[0.04] p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="truncate text-sm font-medium text-white">{collectionName}</p>
                <StatusBadge status={activeVersion.status} />
              </div>
              <p className="mt-1 text-xs text-muted">Knowledge {activeVersion.version} · Vector {snapshotVersion}</p>
            </div>
            <Button type="button" size="sm" variant="ghost" className="text-muted hover:text-red-300" onClick={() => setField('knowledgeVersionId', null)}><X className="h-3.5 w-3.5" /></Button>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
            <div className="rounded-lg border border-border/70 bg-background/50 p-3"><p className="text-muted">Documents</p><p className="mt-1 font-medium text-white">{documentCount.toLocaleString()}</p></div>
            <div className="rounded-lg border border-border/70 bg-background/50 p-3"><p className="text-muted">Chunks</p><p className="mt-1 font-medium text-white">{chunkCount.toLocaleString()}</p></div>
          </div>

          <div className="mt-3 rounded-lg border border-border/70 bg-background/50 p-3">
            <p className="text-[11px] uppercase tracking-wider text-muted">Embedding</p>
            <p className="mt-1 truncate text-xs text-white">{embeddingProvider} · {embeddingModel}</p>
          </div>

          <div className="mt-4 flex gap-2">
            <Button type="button" size="sm" onClick={() => setSelectorOpen(true)}>Change version</Button>
            <Button type="button" size="sm" variant="outline" onClick={() => setField('knowledgeVersionId', null)}>Remove</Button>
          </div>
        </div>
      )}

      <SelectKnowledgeVersionModal open={selectorOpen} projectId={projectId} currentSnapshotId={activeSnapshotId} onClose={() => setSelectorOpen(false)} onSelect={applySnapshot} />
    </div>
  )
}
