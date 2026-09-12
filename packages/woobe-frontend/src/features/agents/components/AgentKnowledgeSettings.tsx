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

function PanelHeader({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="flex items-start gap-2.5 border-b border-border p-3">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light">{icon}</span>
      <div className="min-w-0"><p className="font-mono text-[9px] font-bold text-slate-50">{title}</p><p className="mt-0.5 font-sans text-[9px] leading-4 text-muted-foreground">{description}</p></div>
    </div>
  )
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
      const created = await createKnowledgeVersion.mutateAsync({ project_id: projectId, agent_id: agentId, snapshot_metadata: { vector_snapshot_id: snapshot.id } } as any)
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
    <div className="p-3">
      <section aria-label="Knowledge" className="rounded-container border border-border bg-surface/[0.72]">
        <PanelHeader icon={<BookOpen className="h-3.5 w-3.5" />} title="Knowledge" description={active ? 'Immutable snapshot selected for this Draft.' : 'No immutable snapshot selected.'} />
        <div className="p-3">
          <p className="font-sans text-[9px] leading-4 text-muted-foreground">Choose the knowledge available to this Agent and configure how it is retrieved.</p>
          <p className="mb-2 mt-4 font-mono text-[8px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">Knowledge source</p>
          {active ? (
            <div className="rounded-container border border-border bg-background/20 p-3">
              <div className="flex items-start gap-2.5">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light"><BookOpen className="h-3.5 w-3.5" /></span>
                <div className="min-w-0 flex-1">
                  <p title={collectionName} className="truncate font-mono text-[9px] font-semibold text-slate-100">{collectionName}</p>
                  <p className="mt-1 font-mono text-[8px] text-muted-foreground">Knowledge {active.version} · Vector {vectorVersion}</p>
                  <p className="mt-1 font-mono text-[8px] uppercase tracking-[0.08em] text-muted-foreground">Immutable snapshot</p>
                </div>
                <button type="button" onClick={() => setField('knowledgeVersionId', null)} className="flex h-7 w-7 items-center justify-center rounded-control border border-border text-muted-foreground transition-colors hover:border-red-500/30 hover:text-red-300" aria-label="Remove knowledge"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 border-t border-border/70 pt-3">
                <Button size="sm" variant="outline" className="min-h-[30px] h-auto whitespace-normal px-2 py-1" onClick={() => setSelectorOpen(true)}>Change version</Button>
                <Button size="sm" variant="ghost" className="text-primary-light" onClick={() => setManagerOpen(true)}>Manage</Button>
              </div>
            </div>
          ) : (
            <div className="rounded-container border border-dashed border-border bg-background/20 p-3">
              <div className="flex items-start gap-2.5"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light"><Database className="h-3.5 w-3.5" /></span><div><p className="font-mono text-[9px] font-semibold text-slate-100">No knowledge selected</p><p className="mt-1 font-sans text-[9px] leading-4 text-muted-foreground">Link an immutable Vector Snapshot.</p></div></div>
              <div className="mt-3 grid grid-cols-2 gap-2 border-t border-border/70 pt-3">
                <Button size="sm" variant="outline" className="min-h-[30px] h-auto whitespace-normal px-2 py-1" onClick={() => setSelectorOpen(true)}><Plus className="h-3.5 w-3.5" />Select knowledge</Button>
                <Button size="sm" variant="ghost" className="text-primary-light" onClick={() => setManagerOpen(true)}>Manage</Button>
              </div>
            </div>
          )}

          <div className="mt-4 border-t border-border pt-4">
            <p className="mb-2 font-mono text-[8px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">Retrieval</p>
            <div className="rounded-container border border-border bg-background/20 p-3">
              <div className="flex items-start gap-2.5"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light"><Search className="h-3.5 w-3.5" /></span><div className="min-w-0"><p className="font-mono text-[9px] font-semibold text-slate-100">Search behavior</p><p className="mt-1 font-mono text-[8px] text-muted-foreground">Top {runtime.top_k} from {runtime.candidate_k} candidates</p><p className="mt-1.5 font-sans text-[9px] leading-4 text-muted-foreground">{runtime.query_mode === 'current_message' ? 'Current message' : 'Conversation context'} · {runtime.grounding_policy === 'required' ? 'Required grounding' : 'Optional grounding'}</p></div></div>
              <div className="mt-3 border-t border-border/70 pt-3"><Button size="sm" variant="outline" onClick={() => setRuntimeOpen(true)}><Settings2 className="h-3.5 w-3.5" />Configure</Button></div>
            </div>
            {!active ? <p className="mt-2 font-sans text-[8px] text-muted-foreground">Applied when knowledge is linked.</p> : null}
          </div>
        </div>
      </section>

      <SelectKnowledgeVersionModal open={selectorOpen} projectId={projectId} currentSnapshotId={snapshotId} onClose={() => setSelectorOpen(false)} onSelect={(snapshot) => { void applySnapshot(snapshot) }} />
      <ManageKnowledgeModal open={managerOpen} projectId={projectId} activeBinding={active ? { collectionId, collectionName, knowledgeVersion: active.version, vectorVersion } : null} currentSnapshotId={snapshotId} onClose={() => setManagerOpen(false)} onUseSnapshot={applySnapshot} />
      <RagRuntimeSettings open={runtimeOpen} value={runtime} onClose={() => setRuntimeOpen(false)} onApply={(value) => setField('runtimeConfig', { ...state.runtimeConfig, rag: value })} />
    </div>
  )
}
