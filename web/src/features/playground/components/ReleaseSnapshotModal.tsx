import { FileText, X, Package } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Textarea } from '@/components/ui/Textarea'
import { useKnowledgeVersions } from '@/features/agents/hooks'
import type { AgentRelease } from '@/features/agents/types'

type ReleaseSnapshotModalProps = {
  open: boolean
  title: string
  description?: string
  release: AgentRelease | null
  confirmLabel?: string
  isConfirming?: boolean
  onConfirm?: () => void
  onClose: () => void
  releaseDescription?: string
  onReleaseDescriptionChange?: (value: string) => void
}

function formatJson(value: unknown) {
  if (!value) return '—'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return formatJson(value)
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function row(label: string, value: unknown) {
  return <div className="grid grid-cols-[110px_1fr] gap-3 text-xs"><span className="text-muted">{label}</span><span className="min-w-0 break-words text-slate-200">{formatValue(value)}</span></div>
}

export function ReleaseSnapshotModal({ open, title, description, release, confirmLabel, isConfirming, onConfirm, onClose, releaseDescription, onReleaseDescriptionChange }: ReleaseSnapshotModalProps) {
  const { data: knowledgeVersions = [] } = useKnowledgeVersions(release?.agent_id)
  if (!open || !release) return null
  const canEditDescription = Boolean(onConfirm && onReleaseDescriptionChange)
  const runtimeConfig = recordValue(release.runtime_config)
  const ragConfig = recordValue(runtimeConfig.rag)
  const knowledgeVersion = knowledgeVersions.find((item) => item.id === release.knowledge_version_id) || null
  const knowledgeMetadata = recordValue(knowledgeVersion?.snapshot_metadata)

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div className="flex max-h-[86vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-border/90 bg-surface/95 shadow-2xl shadow-black/40">
      <div className="flex items-start justify-between gap-4 border-b border-border/90 bg-background/20 p-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2"><h2 className="text-base font-semibold text-white">{title}</h2><Badge variant="secondary">{release.version}</Badge></div>
          {description && <p className="text-xs text-muted">{description}</p>}
        </div>
        <button className="rounded-lg border border-transparent p-1 text-muted transition-colors hover:border-border/80 hover:bg-background/60 hover:text-white" onClick={onClose}><X className="h-4 w-4" /></button>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[300px_1fr] overflow-hidden">
        <aside className="border-r border-border/90 bg-background/25 p-5">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary-light"><Package className="h-4 w-4" /></span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-white">{release.version}</p>
              <p className="text-[11px] capitalize text-muted">{release.status}</p>
            </div>
          </div>
          <section className="mt-4 space-y-2 rounded-xl border border-border/80 bg-background/45 p-4">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-300"><FileText className="h-3.5 w-3.5" />Snapshot</div>
            {row('Name', release.name)}
            {row('Model', `${release.provider ?? '—'}/${release.model ?? '—'}`)}
            {row('Temp', release.temperature)}
            {row('Tokens', release.max_output_tokens)}
            {row('Knowledge', knowledgeVersion?.version ?? release.knowledge_version_id)}
            {row('Collections', release.collection_ids?.length ? `${release.collection_ids.length}` : '—')}
          </section>
        </aside>

        <div className="min-h-0 space-y-5 overflow-y-auto p-5">
          {canEditDescription && <section className="space-y-2 rounded-xl border border-border/80 bg-background/45 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Release description</p>
            <Textarea value={releaseDescription ?? ''} onChange={(event) => onReleaseDescriptionChange?.(event.target.value)} placeholder="Describe what changed in this release." className="min-h-24 text-sm" />
          </section>}

          {!canEditDescription && release.release_notes && <section className="space-y-2 rounded-xl border border-border/80 bg-background/45 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Release description</p>
            <p className="whitespace-pre-wrap text-xs text-slate-200">{release.release_notes}</p>
          </section>}

          <section className="space-y-3 rounded-xl border border-border/80 bg-background/45 p-4">
            <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Knowledge binding</p><p className="mt-1 text-[11px] leading-5 text-muted">Exact immutable Knowledge and VectorSnapshot used by this Agent snapshot.</p></div>
            {row('Knowledge', knowledgeVersion?.version)}
            {row('Version ID', release.knowledge_version_id)}
            {row('Vector', knowledgeMetadata.vector_snapshot_version)}
            {row('Vector ID', knowledgeMetadata.vector_snapshot_id)}
            {row('Snapshot hash', knowledgeMetadata.snapshot_hash)}
            {row('Embedding', knowledgeMetadata.embedding_model)}
          </section>

          <section className="space-y-3 rounded-xl border border-border/80 bg-background/45 p-4">
            <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-300">RAG runtime config</p><p className="mt-1 text-[11px] leading-5 text-muted">Exact retrieval behavior frozen in this Agent snapshot.</p></div>
            {row('Strategy', ragConfig.search_strategy)}
            {row('Candidates', ragConfig.candidate_k)}
            {row('Top K', ragConfig.top_k)}
            {row('Min score', ragConfig.min_score)}
            {row('Context chunks', ragConfig.max_context_chunks)}
            {row('Chunks / doc', ragConfig.max_chunks_per_document)}
            {row('Context chars', ragConfig.max_context_chars)}
            {row('Query mode', ragConfig.query_mode)}
            {row('History turns', ragConfig.history_turns)}
            {row('Grounding', ragConfig.grounding_policy)}
          </section>

          <section className="space-y-2 rounded-xl border border-border/80 bg-background/45 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Instructions</p>
            <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg border border-border/60 bg-black/20 p-3 text-xs text-slate-200">{release.system_prompt || '—'}</pre>
          </section>

          <section className="space-y-2 rounded-xl border border-border/80 bg-background/45 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Output / schema</p>
            <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg border border-border/60 bg-black/20 p-3 text-xs text-slate-200">{formatJson(release.output_schema ?? release.response_format)}</pre>
          </section>

          <section className="space-y-2 rounded-xl border border-border/80 bg-background/45 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Complete runtime config</p>
            <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg border border-border/60 bg-black/20 p-3 text-xs text-slate-200">{formatJson(release.runtime_config)}</pre>
          </section>
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-border/90 bg-background/20 p-4">
        <Button size="sm" variant="outline" onClick={onClose}>Close</Button>
        {onConfirm && confirmLabel && <Button size="sm" onClick={onConfirm} loading={isConfirming}>{confirmLabel}</Button>}
      </div>
    </div>
  </div>
}
