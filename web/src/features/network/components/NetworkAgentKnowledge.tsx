import { useState, type ReactNode } from 'react'
import { BookOpen, ChevronRight, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { useKnowledgeVersions } from '@/features/agents/hooks'
import { useCollections } from '@/features/knowledge/hooks'
import { DEFAULT_RETRIEVAL_CONFIG, type RagRuntimeConfig } from '@/features/knowledge/ragConfigTypes'
import { useAgentEditor } from '@/features/playground/AgentEditorContext'
import { NetworkKnowledgeManagerModal } from './NetworkKnowledgeManagerModal'
import { NetworkRagSettingsModal } from './NetworkRagSettingsModal'

function Section({ title, children }: { title: string; children: ReactNode }) {
  return <section className="rounded-xl border border-border bg-surface p-4"><p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">{title}</p>{children}</section>
}
function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}
function runtimeConfig(value: Record<string, unknown>): RagRuntimeConfig {
  const rag = record(value.rag)
  return { search_strategy: 'similarity', candidate_k: typeof rag.candidate_k === 'number' ? rag.candidate_k : DEFAULT_RETRIEVAL_CONFIG.candidate_k, top_k: typeof rag.top_k === 'number' ? rag.top_k : DEFAULT_RETRIEVAL_CONFIG.top_k, min_score: typeof rag.min_score === 'number' ? rag.min_score : null, max_context_chunks: typeof rag.max_context_chunks === 'number' ? rag.max_context_chunks : DEFAULT_RETRIEVAL_CONFIG.max_context_chunks, max_chunks_per_document: typeof rag.max_chunks_per_document === 'number' ? rag.max_chunks_per_document : DEFAULT_RETRIEVAL_CONFIG.max_chunks_per_document, max_context_chars: typeof rag.max_context_chars === 'number' ? rag.max_context_chars : DEFAULT_RETRIEVAL_CONFIG.max_context_chars, query_mode: rag.query_mode === 'current_message' ? 'current_message' : 'conversation_context', history_turns: typeof rag.history_turns === 'number' ? rag.history_turns : DEFAULT_RETRIEVAL_CONFIG.history_turns, grounding_policy: rag.grounding_policy === 'required' ? 'required' : 'optional' }
}

export function NetworkAgentKnowledge({ projectId, agentId }: { projectId: string; agentId: string }) {
  const { data: versions = [] } = useKnowledgeVersions(agentId)
  const { data: collections = [] } = useCollections(projectId)
  const { state, setField } = useAgentEditor()
  const [managerOpen, setManagerOpen] = useState(false)
  const [runtimeOpen, setRuntimeOpen] = useState(false)
  const active = versions.find((item) => item.id === state.knowledgeVersionId) || null
  const metadata = active?.snapshot_metadata || {}
  const snapshotId = typeof metadata.vector_snapshot_id === 'string' ? metadata.vector_snapshot_id : null
  const collectionName = collections.find((item) => item.id === active?.collection_ids?.[0])?.name || 'Versioned knowledge'
  const vectorVersion = typeof metadata.vector_snapshot_version === 'string' ? metadata.vector_snapshot_version : '—'
  const runtime = runtimeConfig(state.runtimeConfig)
  return <div className="space-y-4 p-4">
    <Section title="Knowledge">{active ? <div className="rounded-lg border border-border bg-background p-3"><div className="flex items-start gap-3"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface"><BookOpen className="h-4 w-4 text-primary-light" /></div><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-white">{collectionName}</p><p className="mt-1 text-xs text-muted">Knowledge {active.version} · Vector {vectorVersion}</p><p className="mt-1 text-[10px] uppercase text-muted/80">Immutable snapshot</p></div><button type="button" onClick={() => setField('knowledgeVersionId', null)} className="rounded-lg border border-border p-2 text-muted hover:border-red-500/30 hover:text-red-300"><Trash2 className="h-3.5 w-3.5" /></button></div><div className="mt-3 flex gap-2 border-t border-border/80 pt-3"><Button size="sm" variant="outline" onClick={() => setManagerOpen(true)}>Change version</Button><Button size="sm" variant="ghost" onClick={() => setManagerOpen(true)}>Manage</Button></div></div> : <div className="rounded-lg border border-dashed border-border bg-background/45 p-4"><p className="text-sm font-medium text-white">No knowledge selected</p><p className="mt-1 text-xs leading-5 text-muted">Choose an immutable Vector Snapshot for this Agent Draft.</p><div className="mt-3 flex gap-2"><Button size="sm" onClick={() => setManagerOpen(true)}>Select knowledge</Button><Button size="sm" variant="outline" onClick={() => setManagerOpen(true)}>Manage</Button></div></div>}</Section>
    <Section title="Runtime Retrieval"><button type="button" onClick={() => setRuntimeOpen(true)} className="group flex w-full items-center justify-between rounded-lg border border-border bg-background p-3 text-left hover:border-primary/30"><div><p className="text-sm font-medium text-white">Search behavior</p><p className="mt-1 text-xs text-muted">Top {runtime.top_k} from {runtime.candidate_k} candidates</p><p className="mt-1 text-[10px] text-muted/80">{runtime.query_mode === 'current_message' ? 'Current message' : 'Conversation context'} · {runtime.grounding_policy === 'required' ? 'Required grounding' : 'Optional grounding'}</p></div><ChevronRight className="h-4 w-4 text-muted group-hover:text-primary-light" /></button></Section>
    <NetworkKnowledgeManagerModal open={managerOpen} projectId={projectId} agentId={agentId} currentSnapshotId={snapshotId} onClose={() => setManagerOpen(false)} onApplied={(id) => setField('knowledgeVersionId', id)} />
    <NetworkRagSettingsModal open={runtimeOpen} value={runtime} onClose={() => setRuntimeOpen(false)} onApply={(value) => setField('runtimeConfig', { ...state.runtimeConfig, rag: value })} />
  </div>
}
