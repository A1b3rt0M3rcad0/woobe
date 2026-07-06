import { useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { DEFAULT_RETRIEVAL_CONFIG, type RagGroundingPolicy, type RagQueryMode, type RagRuntimeConfig } from '@/features/knowledge/ragConfigTypes'

interface RagRuntimeSettingsProps {
  open: boolean
  snapshotDefaults?: Record<string, unknown> | null
  value?: RagRuntimeConfig
  onClose: () => void
  onApply: (value: RagRuntimeConfig) => void
}

function numberValue(value: unknown, fallback: number) {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function normalizeDefaults(raw?: Record<string, unknown> | null) {
  const minScore = typeof raw?.min_score === 'number'
    ? raw.min_score
    : typeof raw?.score_threshold === 'number'
      ? raw.score_threshold
      : null
  return {
    candidate_k: numberValue(raw?.candidate_k, DEFAULT_RETRIEVAL_CONFIG.candidate_k),
    top_k: numberValue(raw?.top_k, DEFAULT_RETRIEVAL_CONFIG.top_k),
    min_score: minScore,
    max_context_chunks: numberValue(raw?.max_context_chunks, DEFAULT_RETRIEVAL_CONFIG.max_context_chunks),
    max_chunks_per_document: numberValue(raw?.max_chunks_per_document, DEFAULT_RETRIEVAL_CONFIG.max_chunks_per_document),
    max_context_chars: numberValue(raw?.max_context_chars, DEFAULT_RETRIEVAL_CONFIG.max_context_chars),
    query_mode: (raw?.query_mode === 'current_message' ? 'current_message' : DEFAULT_RETRIEVAL_CONFIG.query_mode) as RagQueryMode,
    history_turns: numberValue(raw?.history_turns, DEFAULT_RETRIEVAL_CONFIG.history_turns),
    grounding_policy: (raw?.grounding_policy === 'required' ? 'required' : DEFAULT_RETRIEVAL_CONFIG.grounding_policy) as RagGroundingPolicy,
  }
}

export function RagRuntimeSettings({ open, snapshotDefaults, value, onClose, onApply }: RagRuntimeSettingsProps) {
  const defaults = useMemo(() => normalizeDefaults(snapshotDefaults), [snapshotDefaults])
  const [inheritDefaults, setInheritDefaults] = useState(true)
  const [candidateK, setCandidateK] = useState(defaults.candidate_k)
  const [topK, setTopK] = useState(defaults.top_k)
  const [minScoreEnabled, setMinScoreEnabled] = useState(defaults.min_score != null)
  const [minScore, setMinScore] = useState(defaults.min_score ?? 0.5)
  const [maxContextChunks, setMaxContextChunks] = useState(defaults.max_context_chunks)
  const [maxChunksPerDocument, setMaxChunksPerDocument] = useState(defaults.max_chunks_per_document)
  const [maxContextChars, setMaxContextChars] = useState(defaults.max_context_chars)
  const [queryMode, setQueryMode] = useState<RagQueryMode>(defaults.query_mode)
  const [historyTurns, setHistoryTurns] = useState(defaults.history_turns)
  const [groundingPolicy, setGroundingPolicy] = useState<RagGroundingPolicy>(defaults.grounding_policy)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    const inherit = value?.inherit_snapshot_defaults !== false
    setInheritDefaults(inherit)
    setCandidateK(value?.candidate_k ?? defaults.candidate_k)
    setTopK(value?.top_k ?? defaults.top_k)
    setMinScoreEnabled(value?.min_score_enabled ?? (value?.min_score != null ? true : defaults.min_score != null))
    setMinScore(value?.min_score ?? defaults.min_score ?? 0.5)
    setMaxContextChunks(value?.max_context_chunks ?? defaults.max_context_chunks)
    setMaxChunksPerDocument(value?.max_chunks_per_document ?? defaults.max_chunks_per_document)
    setMaxContextChars(value?.max_context_chars ?? defaults.max_context_chars)
    setQueryMode(value?.query_mode ?? defaults.query_mode)
    setHistoryTurns(value?.history_turns ?? defaults.history_turns)
    setGroundingPolicy(value?.grounding_policy ?? defaults.grounding_policy)
    setError(null)
  }, [open, value, defaults])

  const apply = () => {
    if (inheritDefaults) {
      onApply({ inherit_snapshot_defaults: true })
      onClose()
      return
    }
    if (topK > candidateK) {
      setError('Top K cannot be greater than Candidates.')
      return
    }
    if (maxContextChunks > topK) {
      setError('Max context chunks cannot be greater than Top K.')
      return
    }
    onApply({
      inherit_snapshot_defaults: false,
      search_strategy: 'similarity',
      candidate_k: candidateK,
      top_k: topK,
      min_score_enabled: minScoreEnabled,
      min_score: minScoreEnabled ? minScore : null,
      max_context_chunks: maxContextChunks,
      max_chunks_per_document: maxChunksPerDocument,
      max_context_chars: maxContextChars,
      query_mode: queryMode,
      history_turns: historyTurns,
      grounding_policy: groundingPolicy,
    })
    onClose()
  }

  return (
    <Dialog open={open} onClose={onClose} title="Runtime retrieval" className="max-h-[calc(100svh-2rem)] max-w-2xl overflow-hidden">
      <div className="max-h-[calc(100svh-8rem)] space-y-5 overflow-y-auto pr-1">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-muted">Configuration source</label>
          <Select value={inheritDefaults ? 'inherit' : 'custom'} onChange={(event) => setInheritDefaults(event.target.value === 'inherit')} options={[{ value: 'inherit', label: 'Inherit Vector Snapshot defaults' }, { value: 'custom', label: 'Custom for this Agent' }]} />
          <p className="mt-2 text-xs leading-5 text-muted">Runtime settings do not rebuild vectors. They control how this Agent searches the selected immutable snapshot.</p>
        </div>

        {!inheritDefaults && (
          <>
            <section className="rounded-xl border border-border bg-background/60 p-4">
              <p className="text-sm font-medium text-white">Candidate search</p>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div><label className="mb-1.5 block text-xs font-medium text-muted">Candidates</label><Input type="number" min={1} max={100} value={candidateK} onChange={(event) => setCandidateK(Number(event.target.value))} /></div>
                <div><label className="mb-1.5 block text-xs font-medium text-muted">Top K</label><Input type="number" min={1} max={20} value={topK} onChange={(event) => setTopK(Number(event.target.value))} /></div>
                <label className="flex items-center gap-3 rounded-lg border border-border/70 bg-surface/50 p-3 text-xs text-white"><input type="checkbox" checked={minScoreEnabled} onChange={(event) => setMinScoreEnabled(event.target.checked)} className="h-4 w-4" />Minimum similarity</label>
                <div><label className="mb-1.5 block text-xs font-medium text-muted">Minimum score</label><Input type="number" min={0} max={1} step="0.05" disabled={!minScoreEnabled} value={minScore} onChange={(event) => setMinScore(Number(event.target.value))} /></div>
              </div>
            </section>

            <section className="rounded-xl border border-border bg-background/60 p-4">
              <p className="text-sm font-medium text-white">Context selection</p>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div><label className="mb-1.5 block text-xs font-medium text-muted">Max context chunks</label><Input type="number" min={1} max={20} value={maxContextChunks} onChange={(event) => setMaxContextChunks(Number(event.target.value))} /></div>
                <div><label className="mb-1.5 block text-xs font-medium text-muted">Max chunks per document</label><Input type="number" min={1} max={20} value={maxChunksPerDocument} onChange={(event) => setMaxChunksPerDocument(Number(event.target.value))} /></div>
                <div><label className="mb-1.5 block text-xs font-medium text-muted">Max context · characters</label><Input type="number" min={1000} max={100000} step={1000} value={maxContextChars} onChange={(event) => setMaxContextChars(Number(event.target.value))} /></div>
              </div>
            </section>

            <section className="rounded-xl border border-border bg-background/60 p-4">
              <p className="text-sm font-medium text-white">Query and grounding</p>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div><label className="mb-1.5 block text-xs font-medium text-muted">Query mode</label><Select value={queryMode} onChange={(event) => setQueryMode(event.target.value as RagQueryMode)} options={[{ value: 'conversation_context', label: 'Conversation aware' }, { value: 'current_message', label: 'Current message only' }]} /></div>
                {queryMode === 'conversation_context' && <div><label className="mb-1.5 block text-xs font-medium text-muted">History turns</label><Input type="number" min={1} max={10} value={historyTurns} onChange={(event) => setHistoryTurns(Number(event.target.value))} /></div>}
                <div><label className="mb-1.5 block text-xs font-medium text-muted">When no knowledge is found</label><Select value={groundingPolicy} onChange={(event) => setGroundingPolicy(event.target.value as RagGroundingPolicy)} options={[{ value: 'optional', label: 'Allow model answer' }, { value: 'required', label: 'Require knowledge' }]} /></div>
              </div>
            </section>
          </>
        )}

        {error && <p className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-200">{error}</p>}
        <div className="flex justify-end gap-2 border-t border-border pt-4"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="button" onClick={apply}>Apply</Button></div>
      </div>
    </Dialog>
  )
}
