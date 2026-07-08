import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { DEFAULT_RETRIEVAL_CONFIG, type RagGroundingPolicy, type RagQueryMode, type RagRuntimeConfig } from '@/features/knowledge/ragConfigTypes'

interface RagRuntimeSettingsProps {
  open: boolean
  value?: RagRuntimeConfig
  onClose: () => void
  onApply: (value: RagRuntimeConfig) => void
}

export function RagRuntimeSettings({ open, value, onClose, onApply }: RagRuntimeSettingsProps) {
  const [candidateK, setCandidateK] = useState(DEFAULT_RETRIEVAL_CONFIG.candidate_k)
  const [topK, setTopK] = useState(DEFAULT_RETRIEVAL_CONFIG.top_k)
  const [minScoreEnabled, setMinScoreEnabled] = useState(false)
  const [minScore, setMinScore] = useState(0.5)
  const [maxContextChunks, setMaxContextChunks] = useState(DEFAULT_RETRIEVAL_CONFIG.max_context_chunks)
  const [maxChunksPerDocument, setMaxChunksPerDocument] = useState(DEFAULT_RETRIEVAL_CONFIG.max_chunks_per_document)
  const [maxContextChars, setMaxContextChars] = useState(DEFAULT_RETRIEVAL_CONFIG.max_context_chars)
  const [queryMode, setQueryMode] = useState<RagQueryMode>(DEFAULT_RETRIEVAL_CONFIG.query_mode)
  const [historyTurns, setHistoryTurns] = useState(DEFAULT_RETRIEVAL_CONFIG.history_turns)
  const [groundingPolicy, setGroundingPolicy] = useState<RagGroundingPolicy>(DEFAULT_RETRIEVAL_CONFIG.grounding_policy)
  const [error, setError] = useState<string | null>(null)

  const loadConfig = (config: RagRuntimeConfig) => {
    setCandidateK(config.candidate_k)
    setTopK(config.top_k)
    setMinScoreEnabled(config.min_score != null)
    setMinScore(config.min_score ?? 0.5)
    setMaxContextChunks(config.max_context_chunks)
    setMaxChunksPerDocument(config.max_chunks_per_document)
    setMaxContextChars(config.max_context_chars)
    setQueryMode(config.query_mode)
    setHistoryTurns(config.history_turns)
    setGroundingPolicy(config.grounding_policy)
    setError(null)
  }

  useEffect(() => {
    if (!open) return
    loadConfig(value ?? DEFAULT_RETRIEVAL_CONFIG)
  }, [open, value])

  const resetDefaults = () => loadConfig(DEFAULT_RETRIEVAL_CONFIG)

  const apply = () => {
    if (topK > candidateK) {
      setError('Top K cannot be greater than Candidates.')
      return
    }
    if (maxContextChunks > topK) {
      setError('Max context chunks cannot be greater than Top K.')
      return
    }
    onApply({
      search_strategy: 'similarity',
      candidate_k: candidateK,
      top_k: topK,
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
        <div className="flex items-start justify-between gap-4 rounded-xl border border-border bg-background/60 p-4">
          <div>
            <p className="text-sm font-medium text-white">Draft runtime configuration</p>
            <p className="mt-1 text-xs leading-5 text-muted">These values control how the Agent searches the selected immutable Knowledge version. Saving the Draft persists the full configuration; promoting the Draft freezes it in Staging.</p>
          </div>
          <Button type="button" size="sm" variant="outline" className="shrink-0" onClick={resetDefaults}>Reset defaults</Button>
        </div>

        <section className="rounded-xl border border-border bg-background/60 p-4">
          <p className="text-sm font-medium text-white">Search</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div><label className="mb-1.5 block text-xs font-medium text-muted">Strategy</label><Select value="similarity" disabled options={[{ value: 'similarity', label: 'Similarity' }]} /></div>
            <div><label className="mb-1.5 block text-xs font-medium text-muted">Candidates</label><Input type="number" min={1} max={100} value={candidateK} onChange={(event) => setCandidateK(Number(event.target.value))} /></div>
            <div><label className="mb-1.5 block text-xs font-medium text-muted">Top K</label><Input type="number" min={1} max={20} value={topK} onChange={(event) => setTopK(Number(event.target.value))} /></div>
            <label className="flex items-center gap-3 rounded-lg border border-border/70 bg-surface/50 p-3 text-xs text-white"><input type="checkbox" checked={minScoreEnabled} onChange={(event) => setMinScoreEnabled(event.target.checked)} className="h-4 w-4" />Minimum similarity</label>
            <div><label className="mb-1.5 block text-xs font-medium text-muted">Minimum score</label><Input type="number" min={0} max={1} step="0.05" disabled={!minScoreEnabled} value={minScore} onChange={(event) => setMinScore(Number(event.target.value))} /></div>
          </div>
        </section>

        <section className="rounded-xl border border-border bg-background/60 p-4">
          <p className="text-sm font-medium text-white">Context</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div><label className="mb-1.5 block text-xs font-medium text-muted">Max context chunks</label><Input type="number" min={1} max={20} value={maxContextChunks} onChange={(event) => setMaxContextChunks(Number(event.target.value))} /></div>
            <div><label className="mb-1.5 block text-xs font-medium text-muted">Max chunks per document</label><Input type="number" min={1} max={20} value={maxChunksPerDocument} onChange={(event) => setMaxChunksPerDocument(Number(event.target.value))} /></div>
            <div><label className="mb-1.5 block text-xs font-medium text-muted">Max context · characters</label><Input type="number" min={1000} max={100000} step={1000} value={maxContextChars} onChange={(event) => setMaxContextChars(Number(event.target.value))} /></div>
          </div>
        </section>

        <section className="rounded-xl border border-border bg-background/60 p-4">
          <p className="text-sm font-medium text-white">Query</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div><label className="mb-1.5 block text-xs font-medium text-muted">Query mode</label><Select value={queryMode} onChange={(event) => setQueryMode(event.target.value as RagQueryMode)} options={[{ value: 'conversation_context', label: 'Conversation aware' }, { value: 'current_message', label: 'Current message only' }]} /></div>
            {queryMode === 'conversation_context' && <div><label className="mb-1.5 block text-xs font-medium text-muted">History turns</label><Input type="number" min={1} max={10} value={historyTurns} onChange={(event) => setHistoryTurns(Number(event.target.value))} /></div>}
          </div>
        </section>

        <section className="rounded-xl border border-border bg-background/60 p-4">
          <p className="text-sm font-medium text-white">Grounding</p>
          <div className="mt-4"><label className="mb-1.5 block text-xs font-medium text-muted">When no knowledge is found</label><Select value={groundingPolicy} onChange={(event) => setGroundingPolicy(event.target.value as RagGroundingPolicy)} options={[{ value: 'optional', label: 'Allow model answer' }, { value: 'required', label: 'Require knowledge' }]} /></div>
        </section>

        {error && <p className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-200">{error}</p>}
        <div className="flex justify-end gap-2 border-t border-border pt-4"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="button" onClick={apply}>Apply to Draft</Button></div>
      </div>
    </Dialog>
  )
}
