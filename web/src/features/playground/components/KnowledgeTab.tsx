import { useState } from 'react'
import { ChevronRight, Database, X } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { LoadingState } from '@/components/common/LoadingState'
import { useCreateKnowledgeVersion, useKnowledgeVersions } from '@/features/agents/hooks'
import { SelectKnowledgeVersionModal } from '@/features/knowledge/components/SelectKnowledgeVersionModal'
import { DEFAULT_RETRIEVAL_CONFIG, type RagRuntimeConfig } from '@/features/knowledge/ragConfigTypes'
import { useCollections } from '@/features/knowledge/hooks'
import type { VectorSnapshot } from '@/features/knowledge/types'
import { useAgentEditor } from '../AgentEditorContext'
import { ManageKnowledgeModal } from './ManageKnowledgeModal'
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
  const [manageKnowledgeOpen, setManageKnowledgeOpen] = useState(false)

  const activeVersion = versions.find((version) => version.id === state.knowledgeVersionId) || null
  const metadata = activeVersion?.snapshot_metadata || {}
  const activeSnapshotId = typeof metadata.vector_snapshot_id === 'string' ? metadata.vector_snapshot_id : null
  const collectionId = activeVersion?.collection_ids?.[0] || null
  const collectionName = collections.find((collection) => collection.id === collectionId)?.name || 'Versioned knowledge'
  const snapshotVersion = typeof metadata.vector_snapshot_version === 'string' ? metadata.vector_snapshot_version : '—'
  const ragConfig = ragRuntimeConfig(state.runtimeConfig)
  const queryModeLabel = ragConfig.query_mode === 'current_message' ? 'Current message' : 'Conversation context'
  const groundingLabel = ragConfig.grounding_policy === 'required' ? 'Required grounding' : 'Optional grounding'

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

  const applyRuntimeConfig = (value: RagRuntimeConfig) => {
    setField('runtimeConfig', { ...state.runtimeConfig, rag: value })
  }

  if (isLoading) return <LoadingState variant="panel" layout="list" message="Loading knowledge..." />

  return (
    <div className="space-y-4 p-4">
      <section className="rounded-xl border border-border bg-surface">
        <div className="space-y-3 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">Knowledge</p>

          {!activeVersion ? (
            <div className="rounded-lg border border-border bg-background p-3">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface text-primary-light">
                  <Database className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-white">No knowledge selected</p>
                  <p className="mt-1 text-xs leading-5 text-muted">Choose an immutable vector version for this Agent Draft.</p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 border-t border-border/80 pt-3">
                <Button type="button" size="sm" onClick={() => setSelectorOpen(true)}>
                  Select knowledge
                </Button>
                <Button type="button" size="sm" variant="outline" onClick={() => setManageKnowledgeOpen(true)}>
                  <Database className="mr-2 h-3.5 w-3.5" />
                  Manage knowledge
                </Button>
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-background p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface text-primary-light">
                    <Database className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-white">{collectionName}</p>
                    <p className="mt-1 text-xs text-muted">Knowledge {activeVersion.version} · Vector {snapshotVersion}</p>
                    <p className="mt-1 text-[10px] uppercase tracking-wider text-muted/80">Immutable snapshot</p>
                  </div>
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
              <div className="mt-3 flex flex-wrap gap-2 border-t border-border/80 pt-3">
                <Button type="button" size="sm" variant="outline" onClick={() => setSelectorOpen(true)}>
                  Change version
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => setManageKnowledgeOpen(true)}>
                  <Database className="mr-2 h-3.5 w-3.5" />
                  Manage knowledge
                </Button>
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="rounded-xl border border-border bg-surface">
        <div className="space-y-3 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">Runtime Retrieval</p>
          <button
            type="button"
            onClick={() => setRuntimeSettingsOpen(true)}
            className="group flex w-full items-center justify-between gap-3 rounded-lg border border-border bg-background p-3 text-left transition-colors hover:border-primary/30 hover:bg-background/80"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium text-white">Search behavior</p>
              <p className="mt-1 text-xs text-muted">Top {ragConfig.top_k} from {ragConfig.candidate_k} candidates</p>
              <p className="mt-1 truncate text-[10px] text-muted/80">{queryModeLabel} · {groundingLabel}</p>
            </div>
            <ChevronRight className="h-4 w-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-primary-light" />
          </button>
        </div>
      </section>

      <SelectKnowledgeVersionModal open={selectorOpen} projectId={projectId} currentSnapshotId={activeSnapshotId} onClose={() => setSelectorOpen(false)} onSelect={(snapshot) => void applySnapshot(snapshot)} />
      <RagRuntimeSettings open={runtimeSettingsOpen} value={ragConfig} onClose={() => setRuntimeSettingsOpen(false)} onApply={applyRuntimeConfig} />
      <ManageKnowledgeModal
        open={manageKnowledgeOpen}
        projectId={projectId}
        activeBinding={activeVersion ? {
          collectionId,
          collectionName,
          knowledgeVersion: activeVersion.version,
          vectorVersion: snapshotVersion,
        } : null}
        currentSnapshotId={activeSnapshotId}
        onClose={() => setManageKnowledgeOpen(false)}
        onUseSnapshot={applySnapshot}
      />
    </div>
  )
}
