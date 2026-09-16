import { useEffect, useState, type ReactNode } from 'react'
import { SlidersHorizontal } from 'lucide-react'
import { Checkbox } from '@woobe/ui'
import { Button } from '@/components/ui/Button'
import { Dialog, DialogFooter } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { DEFAULT_RETRIEVAL_CONFIG, type RagGroundingPolicy, type RagQueryMode, type RagRuntimeConfig } from '@/features/knowledge/ragConfigTypes'

interface RagRuntimeSettingsProps {
  open: boolean
  value?: RagRuntimeConfig
  onClose: () => void
  onApply: (value: RagRuntimeConfig) => void
}

function Label({ children }: { children: ReactNode }) {
  return <span className="mb-ui-xs block font-mono text-product-caption font-medium uppercase tracking-[0.08em] text-muted-foreground">{children}</span>
}

function PanelHeader({ title, description }: { title: string; description: string }) {
  return (
    <div className="mb-ui-md">
      <h3 className="font-sans text-system-control font-semibold text-slate-50">{title}</h3>
      <p className="mt-ui-xs font-sans text-product-small leading-5 text-muted-foreground">{description}</p>
    </div>
  )
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
    if (open) loadConfig(value ?? DEFAULT_RETRIEVAL_CONFIG)
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
    <Dialog
      open={open}
      onClose={onClose}
      title="Runtime retrieval"
      className="flex h-[min(760px,calc(100svh-2rem))] max-w-[min(74rem,calc(100vw-2rem))] flex-col overflow-hidden"
      contentClassName="min-h-0 flex-1 p-0"
    >
      <div className="flex h-full min-h-0 flex-col">
        <div className="grid min-h-0 flex-1 md:grid-cols-[16rem_minmax(0,1fr)]">
          <aside className="border-b border-border bg-background/25 p-ui-md md:border-b-0 md:border-r">
            <section className="rounded-container border border-border bg-background/30 p-ui-md">
              <span className="flex h-9 w-9 items-center justify-center rounded-control border border-border bg-control text-primary-light">
                <SlidersHorizontal className="h-icon w-icon" />
              </span>
              <p className="mt-ui-md font-mono text-product-caption uppercase tracking-[0.08em] text-muted-foreground">Draft configuration</p>
              <h3 className="mt-ui-xs font-sans text-system-control font-semibold text-slate-50">Runtime retrieval</h3>
              <p className="mt-ui-xs font-sans text-product-small leading-5 text-muted-foreground">
                Controls how the Agent searches the selected immutable Knowledge version. Staging freezes these values.
              </p>

              <div className="mt-ui-lg divide-y divide-border/60 border-y border-border/60">
                {[
                  ['Strategy', 'Similarity'],
                  ['Candidates', candidateK],
                  ['Top K', topK],
                  ['Context chunks', maxContextChunks],
                ].map(([label, current]) => (
                  <div key={String(label)} className="flex min-h-control items-center justify-between gap-ui-md py-ui-sm">
                    <span className="font-sans text-product-caption text-muted-foreground">{label}</span>
                    <span className="font-mono text-product-caption text-slate-200">{current}</span>
                  </div>
                ))}
              </div>

              <Button type="button" size="sm" variant="outline" className="mt-ui-md w-full" onClick={resetDefaults}>
                Reset defaults
              </Button>
            </section>
          </aside>

          <main className="scrollbar-thin min-h-0 min-w-0 overflow-y-auto p-ui-lg">
            <div className="grid gap-ui-md lg:grid-cols-2">
              <section className="rounded-container border border-border bg-surface/[0.72] p-ui-md">
                <PanelHeader title="Search" description="Candidate retrieval and similarity filtering." />
                <div className="grid gap-ui-md sm:grid-cols-2">
                  <label>
                    <Label>Strategy</Label>
                    <Select value="similarity" disabled options={[{ value: 'similarity', label: 'Similarity' }]} />
                  </label>
                  <label>
                    <Label>Candidates</Label>
                    <Input type="number" min={1} max={100} value={candidateK} onChange={(event) => setCandidateK(Number(event.target.value))} />
                  </label>
                  <label>
                    <Label>Top K</Label>
                    <Input type="number" min={1} max={20} value={topK} onChange={(event) => setTopK(Number(event.target.value))} />
                  </label>
                  <label>
                    <Label>Minimum score</Label>
                    <Input type="number" min={0} max={1} step="0.05" disabled={!minScoreEnabled} value={minScore} onChange={(event) => setMinScore(Number(event.target.value))} />
                  </label>
                </div>
                <label className="mt-ui-md flex items-start gap-ui-sm rounded-container border border-border bg-background/20 p-ui-md">
                  <Checkbox checked={minScoreEnabled} onChange={(event) => setMinScoreEnabled(event.target.checked)} className="mt-0.5" />
                  <span>
                    <span className="block font-sans text-product-small font-medium text-slate-100">Enable minimum similarity</span>
                    <span className="mt-ui-xs block font-sans text-product-caption leading-5 text-muted-foreground">Discard candidates below the configured score before context selection.</span>
                  </span>
                </label>
              </section>

              <section className="rounded-container border border-border bg-surface/[0.72] p-ui-md">
                <PanelHeader title="Context" description="Limits the Knowledge context passed to the model." />
                <div className="grid gap-ui-md sm:grid-cols-2">
                  <label>
                    <Label>Max context chunks</Label>
                    <Input type="number" min={1} max={20} value={maxContextChunks} onChange={(event) => setMaxContextChunks(Number(event.target.value))} />
                  </label>
                  <label>
                    <Label>Max per document</Label>
                    <Input type="number" min={1} max={20} value={maxChunksPerDocument} onChange={(event) => setMaxChunksPerDocument(Number(event.target.value))} />
                  </label>
                  <label className="sm:col-span-2">
                    <Label>Max context · characters</Label>
                    <Input type="number" min={1000} max={100000} step={1000} value={maxContextChars} onChange={(event) => setMaxContextChars(Number(event.target.value))} />
                  </label>
                </div>
              </section>

              <section className="rounded-container border border-border bg-surface/[0.72] p-ui-md">
                <PanelHeader title="Query" description="How conversational context contributes to retrieval." />
                <div className="space-y-ui-md">
                  <label>
                    <Label>Query mode</Label>
                    <Select
                      value={queryMode}
                      onChange={(event) => setQueryMode(event.target.value as RagQueryMode)}
                      options={[
                        { value: 'conversation_context', label: 'Conversation aware' },
                        { value: 'current_message', label: 'Current message only' },
                      ]}
                    />
                  </label>
                  {queryMode === 'conversation_context' ? (
                    <label>
                      <Label>History turns</Label>
                      <Input type="number" min={1} max={10} value={historyTurns} onChange={(event) => setHistoryTurns(Number(event.target.value))} />
                    </label>
                  ) : null}
                </div>
              </section>

              <section className="rounded-container border border-border bg-surface/[0.72] p-ui-md">
                <PanelHeader title="Grounding" description="Behavior when retrieval finds no relevant Knowledge." />
                <label>
                  <Label>When no knowledge is found</Label>
                  <Select
                    value={groundingPolicy}
                    onChange={(event) => setGroundingPolicy(event.target.value as RagGroundingPolicy)}
                    options={[
                      { value: 'optional', label: 'Allow model answer' },
                      { value: 'required', label: 'Require knowledge' },
                    ]}
                  />
                </label>
              </section>
            </div>

            {error ? (
              <p className="mt-ui-md border-l-2 border-l-red-400 bg-red-500/[0.05] px-ui-md py-ui-sm font-sans text-product-small text-red-200">
                {error}
              </p>
            ) : null}
          </main>
        </div>

        <DialogFooter
          actions={(
            <>
              <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
              <Button type="button" onClick={apply}>Apply to Draft</Button>
            </>
          )}
        />
      </div>
    </Dialog>
  )
}
