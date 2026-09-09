import { useState } from 'react'
import { BookOpen, Database, Search, Settings2, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { useCreateKnowledgeVersion, useKnowledgeVersions } from '@/features/agents/hooks'
import { SelectKnowledgeVersionModal } from '@/features/knowledge/components/SelectKnowledgeVersionModal'
import { useCollections } from '@/features/knowledge/hooks'
import { DEFAULT_RETRIEVAL_CONFIG, type RagRuntimeConfig } from '@/features/knowledge/ragConfigTypes'
import type { VectorSnapshot } from '@/features/knowledge/types'
import { ManageKnowledgeModal } from '@/features/playground/components/ManageKnowledgeModal'
import { RagRuntimeSettings } from '@/features/playground/components/RagRuntimeSettings'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function runtimeConfig(value: Record<string, unknown>): RagRuntimeConfig {
  const rag = record(value.rag)
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

export function AgentKnowledgeSettings({ projectId, agentId }: { projectId: string; agentId: string }) {
  const { data: versions = [] } = useKnowledgeVersions(agentId)
  const { data: collections = [] } = useCollections(projectId)
  const createKnowledgeVersion = useCreateKnowledgeVersion(agentId)
  const { state, setField } = useAgentEditor()
  const [selectorOpen, setSelectorOpen] = useState(false)
  const [managerOpen, setManagerOpen] = useState(false)
  const [runtimeOpen, setRuntimeOpen] = useState(false)

  const active = versions.find((item) => item.id === state.knowledgeVersionId) || null
  const metadata = active?.snapshot_metadata || {}
  const snapshotId = typeof metadata.vector_snapshot_id === 'string' ? metadata.vector_snapshot_id : null
  const collectionId = active?.collection_ids?.[0] || null
  const collectionName = collections.find((item) => item.id === collectionId)?.name || 'Versioned knowledge'
  const vectorVersion = typeof metadata.vector_snapshot_version === 'string' ? metadata.vector_snapshot_version : '—'
  const runtime = runtimeConfig(state.runtimeConfig)

  const applySnapshot = async (snapshot: VectorSnapshot): Promise<boolean> => {
    try {
      const created = await createKnowledgeVersion.mutateAsync({
        project_id: projectId,
        agent_id: agentId,
        snapshot_metadata: { vector_snapshot_id: snapshot.id },
      } as any)
      setField('knowledgeVersionId', created.id)
      setSelectorOpen(false)
      toast.success(`${snapshot.version} applied to the Agent Draft`)
      return true
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to apply knowledge')
      return false
    }
  }

  return (
    <div className="space-y-4 p-4">
      <section aria-label="Knowledge" className="rounded-xl border border-border bg-surface">
        <div className="flex items-center gap-3 p-4"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary-light"><BookOpen className="h-4 w-4" /></span><div><p className="text-sm font-semibold">Knowledge</p><p className="mt-0.5 text-[11px] text-muted">{active ? 'Snapshot selected' : 'No snapshot selected'}</p></div></div>
        <div className="border-t border-border p-4">
        <p className="text-xs leading-5 text-muted">Choose the knowledge available to this Agent and configure how it is retrieved.</p>
        <p className="mb-2.5 mt-5 text-xs font-semibold uppercase tracking-wider text-muted">Knowledge source</p>
        {active ? (
          <div className="rounded-lg border border-border bg-background/35 p-3">
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary-light"><BookOpen className="h-4 w-4 text-primary-light" /></div>
              <div className="min-w-0 flex-1">
                <p title={collectionName} className="truncate text-xs font-medium text-foreground">{collectionName}</p>
                <p className="mt-1 text-xs text-muted">Knowledge {active.version} · Vector {vectorVersion}</p>
                <p className="mt-1 text-[11px] uppercase text-muted/80">Immutable snapshot</p>
              </div>
              <button type="button" onClick={() => setField('knowledgeVersionId', null)} className="rounded-lg border border-border p-2 text-muted hover:border-red-500/30 hover:text-red-300" aria-label="Remove knowledge"><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 border-t border-border/75 pt-3">
              <Button size="sm" variant="outline" className="min-h-8 h-auto whitespace-normal px-2 py-1 text-[11px]" onClick={() => setSelectorOpen(true)}>Change version</Button>
              <Button size="sm" variant="ghost" className="h-8 text-[11px] text-primary-light" onClick={() => setManagerOpen(true)}>Manage</Button>
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-border bg-background/35 p-3">
            <div className="flex items-start gap-3"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary-light"><Database className="h-4 w-4" /></span><div><p className="text-sm font-semibold text-foreground">No knowledge selected</p><p className="mt-1 text-[11px] leading-4 text-muted">Link an immutable Vector Snapshot.</p></div></div>
            <div className="mt-3 grid grid-cols-2 gap-2 border-t border-border/75 pt-3">
              <Button size="sm" variant="outline" className="min-h-8 h-auto whitespace-normal px-2 py-1 text-[11px]" onClick={() => setSelectorOpen(true)}><Plus className="mr-1 h-3.5 w-3.5" />Select knowledge</Button>
              <Button size="sm" variant="ghost" className="h-8 text-[11px] text-primary-light" onClick={() => setManagerOpen(true)}>Manage</Button>
            </div>
          </div>
        )}
      <div className="mt-5 border-t border-border/80 pt-5">
        <p className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-muted">Retrieval</p>
        <div className="rounded-lg border border-border bg-background/35 p-3">
          <div className="flex items-start gap-3"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary-light"><Search className="h-4 w-4" /></span><div className="min-w-0">
            <p className="text-sm font-semibold text-foreground">Search behavior</p>
            <p className="mt-1 text-[11px] text-muted">Top {runtime.top_k} from {runtime.candidate_k} candidates</p>
            <p className="mt-2 text-[11px] text-muted">{runtime.query_mode === 'current_message' ? 'Current message' : 'Conversation context'}<br />{runtime.grounding_policy === 'required' ? 'Required grounding' : 'Optional grounding'}</p>
          </div></div>
          <div className="mt-3 grid grid-cols-2 gap-2 border-t border-border/75 pt-3"><Button size="sm" variant="outline" className="h-8 text-[11px]" onClick={() => setRuntimeOpen(true)}><Settings2 className="mr-1 h-3.5 w-3.5" />Configure</Button></div>
        </div>
        {!active ? <p className="mt-3 text-[11px] text-muted">Applied when knowledge is linked.</p> : null}
      </div>
      </div>
      </section>

      <SelectKnowledgeVersionModal open={selectorOpen} projectId={projectId} currentSnapshotId={snapshotId} onClose={() => setSelectorOpen(false)} onSelect={(snapshot) => { void applySnapshot(snapshot) }} />
      <ManageKnowledgeModal
        open={managerOpen}
        projectId={projectId}
        activeBinding={active ? { collectionId, collectionName, knowledgeVersion: active.version, vectorVersion } : null}
        currentSnapshotId={snapshotId}
        onClose={() => setManagerOpen(false)}
        onUseSnapshot={applySnapshot}
      />
      <RagRuntimeSettings open={runtimeOpen} value={runtime} onClose={() => setRuntimeOpen(false)} onApply={(value) => setField('runtimeConfig', { ...state.runtimeConfig, rag: value })} />
    </div>
  )
}
