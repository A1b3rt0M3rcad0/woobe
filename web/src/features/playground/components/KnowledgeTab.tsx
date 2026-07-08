import { useState } from 'react'
import { ChevronRight, Plus, X } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { LoadingState } from '@/components/common/LoadingState'
import { useCreateKnowledgeVersion, useKnowledgeVersions } from '@/features/agents/hooks'
import { CollectionDetailsModal } from '@/features/knowledge/components/CollectionDetailsModalV2'
import { CreateCollectionModal } from '@/features/knowledge/components/CreateCollectionModal'
import { SelectKnowledgeVersionModal } from '@/features/knowledge/components/SelectKnowledgeVersionModal'
import { DEFAULT_RETRIEVAL_CONFIG, type RagRuntimeConfig } from '@/features/knowledge/ragConfigTypes'
import { useCollections } from '@/features/knowledge/hooks'
import type { Collection, VectorSnapshot } from '@/features/knowledge/types'
import { useAgentEditor } from '../AgentEditorContext'
import { RagRuntimeSettings } from './RagRuntimeSettings'

interface KnowledgeTabProps {
  projectId: string
  agentId: string
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function ragRuntimeConfig(runtimeConfig: Record<string, unknown>): RagRuntimeConfig {
  const rag = recordValue(runtimeConfig.rag)
  return {
    search_strategy: 'similarity',
    candidate_k: typeof rag.candidate_k === 'number' ? rag.candidate_k : DEFAULT_RETRIEVAL_CONFIG.candidate_k,
    top_k: typeof rag.top_k === 'number' ? rag.top_k : DEFAULT_RETRIEVAL_CONFIG.top_k,
    min_score: typeof rag.min_score === 'number' ? rag.min_score : null,
    max_context_chunks: typeof rag.max_context_chunks === 'number' ? rag.max_context_chunks : DEFAULT_RETRIEVAL_CONFIG.max_context_chunks,
    max_chunks_per_document: typeof rag.max_chunks_per_document === 'number' ? rag.max_chunks_per_document : DEFAULT_RETRIEVAL_CONFIG.max_chunks_per_document,
    max_context_chars: typeof rag.max_context_chars === 'number' ? rag.max_context_chars : DEFAULT_RETRIEVAL_CONFIG.max_context_chars,
    query_mode: rag.query_mode === 'current_message' ? 'current_message' : 'conversation_context',
    history_turns: typeof rag.history_turns === 'number' ? rag.history_turns : DEFAULT_RETRIEVAL_CONFIG.history_turns,
    grounding_policy: rag.grounding_policy === 'required' ? 'required' : 'optional',
  }
}

export function KnowledgeTab({ projectId, agentId }: KnowledgeTabProps) {
  const { data: versions = [], isLoading } = useKnowledgeVersions(agentId)
  const { data: collections = [] } = useCollections(projectId)
  const createKnowledgeVersion = useCreateKnowledgeVersion(agentId)
  const { state, setField } = useAgentEditor()
  const [selectorOpen, setSelectorOpen] = useState(false)
  const [runtimeSettingsOpen, setRuntimeSettingsOpen] = useState(false)
  const [createCollectionOpen, setCreateCollectionOpen] = useState(false)
  const [createdCollection, setCreatedCollection] = useState<Collection | null>(null)

  const activeVersion = versions.find((version) => version.id === state.knowledgeVersionId) || null
  const metadata = activeVersion?.snapshot_metadata || {}
  const activeSnapshotId = typeof metadata.vector_snapshot_id === 'string' ? metadata.vector_snapshot_id : null
  const collectionId = activeVersion?.collection_ids?.[0] || null
  const collectionName = collections.find((collection) => collection.id === collectionId)?.name || 'Versioned knowledge'
  const snapshotVersion = typeof metadata.vector_snapshot_version === 'string' ? metadata.vector_snapshot_version : '—'
  const ragConfig = ragRuntimeConfig(state.runtimeConfig)

  const applySnapshot = async (snapshot: VectorSnapshot): Promise<boolean> => {
    try {
      const created = await createKnowledgeVersion.mutateAsync({
        project_id: projectId,
        agent_id: agentId,
        snapshot_metadata: { vector_snapshot_id: snapshot.id },
      } as any)
      setField('knowledgeVersionId', created.id)
      setSelectorOpen(false)
      toast.success(`${snapshot.version} applied to the Agent draft`)
      return true
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to apply knowledge')
      return false
    }
  }

  const useCreatedSnapshot = async (snapshot: VectorSnapshot) => {
    const applied = await applySnapshot(snapshot)
    if (applied) setCreatedCollection(null)
  }

  const applyRuntimeConfig = (value: RagRuntimeConfig) => {
    setField('runtimeConfig', { ...state.runtimeConfig, rag: value })
  }

  if (isLoading) return <LoadingState variant="panel" layout="list" message="Loading knowledge..." />

  return (
    <div className="space-y-3 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium text-white">Knowledge</h2>
          <p className="mt-1 text-[11px] leading-5 text-muted">Knowledge used by this Agent Draft.</p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-8 w-8 p-0"
          onClick={() => setCreateCollectionOpen(true)}
          aria-label="Create knowledge"
          title="Create knowledge"
        >
          <Plus className="h-4 w-4" />
        </Button>
      </div>

      {!activeVersion ? (
        <div className="rounded-xl border border-border bg-surface/50 p-4">
          <p className="text-sm font-medium text-white">No Knowledge selected</p>
          <p className="mt-1 text-[11px] leading-5 text-muted">Choose an immutable version for this Agent Draft.</p>
          <Button type="button" size="sm" className="mt-3" onClick={() => setSelectorOpen(true)}>Select knowledge</Button>
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-surface/50 p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-white">{collectionName}</p>
              <p className="mt-1 text-[11px] text-muted">Knowledge {activeVersion.version} · Vector {snapshotVersion}</p>
            </div>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 w-7 shrink-0 p-0 text-muted hover:text-red-300"
              onClick={() => setField('knowledgeVersionId', null)}
              aria-label="Remove knowledge"
              title="Remove knowledge"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
          <button type="button" className="mt-3 text-xs font-medium text-primary-light transition-colors hover:text-white" onClick={() => setSelectorOpen(true)}>Change version</button>
        </div>
      )}

      <button
        type="button"
        onClick={() => setRuntimeSettingsOpen(true)}
        className="group flex w-full items-center justify-between gap-3 rounded-xl border border-border bg-surface/50 p-3 text-left transition-colors hover:border-primary/30 hover:bg-surface/70"
      >
        <div>
          <p className="text-sm font-medium text-white">Runtime retrieval</p>
          <p className="mt-1 text-[11px] text-muted">Configure search behavior</p>
        </div>
        <ChevronRight className="h-4 w-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-primary-light" />
      </button>

      <SelectKnowledgeVersionModal open={selectorOpen} projectId={projectId} currentSnapshotId={activeSnapshotId} onClose={() => setSelectorOpen(false)} onSelect={(snapshot) => void applySnapshot(snapshot)} />
      <RagRuntimeSettings open={runtimeSettingsOpen} value={ragConfig} onClose={() => setRuntimeSettingsOpen(false)} onApply={applyRuntimeConfig} />
      <CreateCollectionModal open={createCollectionOpen} projectId={projectId} onClose={() => setCreateCollectionOpen(false)} onCreated={setCreatedCollection} />
      <CollectionDetailsModal open={Boolean(createdCollection)} projectId={projectId} collection={createdCollection} onClose={() => setCreatedCollection(null)} onUseSnapshot={useCreatedSnapshot} />
    </div>
  )
}
