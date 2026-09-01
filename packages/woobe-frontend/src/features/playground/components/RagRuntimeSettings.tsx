import { useEffect, useState } from 'react'
import { SlidersHorizontal } from 'lucide-react'
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
    <Dialog open={open} onClose={onClose} title="Runtime retrieval" className="max-h-[calc(100svh-2rem)] max-w-5xl overflow-hidden">
      <div className="scrollbar-thin max-h-[calc(100svh-8rem)] overflow-y-auto pr-1">
        <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="space-y-4 lg:sticky lg:top-0 lg:self-start">
            <section className="rounded-xl border border-border/90 bg-surface/70 p-4">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-background text-primary-light">
                <SlidersHorizontal className="h-5 w-5" />
              </div>
              <div className="mt-5">
                <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Draft configuration</p>
                <h3 className="mt-2 text-base font-semibold text-white">Runtime retrieval</h3>
                <p className="mt-2 text-xs leading-5 text-muted">Controls how the Agent searches the selected immutable Knowledge version. Promoting the Draft freezes these values in Staging.</p>
              </div>

              <div className="mt-5 border-t border-border/70 pt-4">
                <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Current setup</p>
                <div className="mt-3 space-y-2 text-xs">
                  <div className="flex items-center justify-between gap-3"><span className="text-muted">Strategy</span><span className="text-white/90">Similarity</span></div>
                  <div className="flex items-center justify-between gap-3"><span className="text-muted">Candidates</span><span className="text-white/90">{candidateK}</span></div>
                  <div className="flex items-center justify-between gap-3"><span className="text-muted">Top K</span><span className="text-white/90">{topK}</span></div>
                  <div className="flex items-center justify-between gap-3"><span className="text-muted">Context chunks</span><span className="text-white/90">{maxContextChunks}</span></div>
                </div>
              </div>
            </section>

            <section className="rounded-xl border border-border/90 bg-background/60 p-4">
              <h3 className="text-sm font-semibold text-white">Platform defaults</h3>
              <p className="mt-1 text-xs leading-5 text-muted">Restore the recommended retrieval values without changing the selected Knowledge version.</p>
              <Button type="button" size="sm" variant="outline" className="mt-4 w-full" onClick={resetDefaults}>Reset defaults</Button>
            </section>
          </aside>

          <main className="min-w-0">
            <div className="grid gap-5 xl:grid-cols-2">
              <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-white">Search</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">Controls candidate retrieval and similarity filtering.</p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-muted">Strategy</label>
                    <Select value="similarity" disabled options={[{ value: 'similarity', label: 'Similarity' }]} />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-muted">Candidates</label>
                    <Input type="number" min={1} max={100} value={candidateK} onChange={(event) => setCandidateK(Number(event.target.value))} />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-muted">Top K</label>
                    <Input type="number" min={1} max={20} value={topK} onChange={(event) => setTopK(Number(event.target.value))} />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-muted">Minimum score</label>
                    <Input type="number" min={0} max={1} step="0.05" disabled={!minScoreEnabled} value={minScore} onChange={(event) => setMinScore(Number(event.target.value))} />
                  </div>
                </div>
                <label className="mt-4 flex items-start gap-3 rounded-lg border border-border/70 bg-background/50 p-3 text-xs text-white">
                  <input type="checkbox" checked={minScoreEnabled} onChange={(event) => setMinScoreEnabled(event.target.checked)} className="mt-0.5 h-4 w-4" />
                  <span><span className="block font-medium">Enable minimum similarity</span><span className="mt-1 block leading-5 text-muted">Discard candidates below the configured score before context selection.</span></span>
                </label>
              </section>

              <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-white">Context</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">Limits the Knowledge context passed to the model.</p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-muted">Max context chunks</label>
                    <Input type="number" min={1} max={20} value={maxContextChunks} onChange={(event) => setMaxContextChunks(Number(event.target.value))} />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-muted">Max per document</label>
                    <Input type="number" min={1} max={20} value={maxChunksPerDocument} onChange={(event) => setMaxChunksPerDocument(Number(event.target.value))} />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="mb-1.5 block text-xs font-medium text-muted">Max context · characters</label>
                    <Input type="number" min={1000} max={100000} step={1000} value={maxContextChars} onChange={(event) => setMaxContextChars(Number(event.target.value))} />
                  </div>
                </div>
              </section>

              <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-white">Query</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">Defines how conversational context contributes to retrieval.</p>
                </div>
                <div className="space-y-4">
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-muted">Query mode</label>
                    <Select value={queryMode} onChange={(event) => setQueryMode(event.target.value as RagQueryMode)} options={[{ value: 'conversation_context', label: 'Conversation aware' }, { value: 'current_message', label: 'Current message only' }]} />
                  </div>
                  {queryMode === 'conversation_context' && (
                    <div>
                      <label className="mb-1.5 block text-xs font-medium text-muted">History turns</label>
                      <Input type="number" min={1} max={10} value={historyTurns} onChange={(event) => setHistoryTurns(Number(event.target.value))} />
                    </div>
                  )}
                </div>
              </section>

              <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-white">Grounding</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">Controls what happens when retrieval finds no relevant Knowledge.</p>
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-muted">When no knowledge is found</label>
                  <Select value={groundingPolicy} onChange={(event) => setGroundingPolicy(event.target.value as RagGroundingPolicy)} options={[{ value: 'optional', label: 'Allow model answer' }, { value: 'required', label: 'Require knowledge' }]} />
                </div>
              </section>
            </div>

            {error && <p className="mt-5 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-200">{error}</p>}
          </main>
        </div>

        <div className="sticky bottom-0 -mx-1 mt-6 flex flex-col-reverse gap-2 border-t border-border bg-surface/95 px-1 py-4 backdrop-blur sm:flex-row sm:justify-end">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="button" onClick={apply}>Apply to Draft</Button>
        </div>
      </div>
    </Dialog>
  )
}
