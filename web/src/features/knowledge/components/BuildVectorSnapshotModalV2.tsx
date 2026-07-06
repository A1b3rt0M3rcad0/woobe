import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { ChevronDown, ChevronRight, Plus } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { CreateEmbeddingModelModal } from '@/features/knowledge/components/CreateEmbeddingModelModal'
import { VectorBuildPreview } from '@/features/knowledge/components/VectorBuildPreview'
import { CHUNKING_PRESETS, DEFAULT_RETRIEVAL_CONFIG, type RagChunkingPreset, type RagChunkingStrategy, type RagGroundingPolicy, type RagQueryMode } from '@/features/knowledge/ragConfigTypes'
import { useCreateVectorSnapshot, usePreviewVectorSnapshot } from '@/features/knowledge/vectorHooks'
import { useProviderModels } from '@/features/provider-models/hooks'
import type { ProviderModel } from '@/features/provider-models/types'

interface BuildVectorSnapshotModalV2Props {
  open: boolean
  projectId: string
  collection: { id: string; name: string } | null
  onClose: () => void
  onCreated: () => void
}

function isEmbeddingModel(model: ProviderModel) {
  const metadata = model.metadata || {}
  const capability = String(metadata.capability || metadata.type || '').toLowerCase()
  return (capability === 'embedding' || capability === 'embeddings' || model.model.toLowerCase().includes('embed')) && model.status === 'active'
}

function CheckField({ checked, label, detail, onChange }: { checked: boolean; label: string; detail?: string; onChange: (checked: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-border/70 bg-surface/40 p-3">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="mt-0.5 h-4 w-4 rounded border-border bg-background" />
      <span><span className="block text-xs font-medium text-white">{label}</span>{detail && <span className="mt-1 block text-[11px] leading-5 text-muted">{detail}</span>}</span>
    </label>
  )
}

export function BuildVectorSnapshotModalV2({ open, projectId, collection, onClose, onCreated }: BuildVectorSnapshotModalV2Props) {
  const createSnapshot = useCreateVectorSnapshot(collection?.id, projectId)
  const previewSnapshot = usePreviewVectorSnapshot(collection?.id)
  const modelsQuery = useProviderModels(projectId)
  const availableModels = useMemo(() => (modelsQuery.data ?? []).filter(isEmbeddingModel), [modelsQuery.data])
  const [selectedModelId, setSelectedModelId] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [createModelOpen, setCreateModelOpen] = useState(false)
  const [description, setDescription] = useState('')

  const [preset, setPreset] = useState<RagChunkingPreset>('balanced')
  const [strategy, setStrategy] = useState<RagChunkingStrategy>('recursive_text')
  const [chunkSize, setChunkSize] = useState(800)
  const [chunkOverlap, setChunkOverlap] = useState(120)
  const [minChunkSize, setMinChunkSize] = useState(100)
  const [preserveParagraphs, setPreserveParagraphs] = useState(true)
  const [preserveHeadings, setPreserveHeadings] = useState(true)
  const [preservePageBoundaries, setPreservePageBoundaries] = useState(true)
  const [normalizeWhitespace, setNormalizeWhitespace] = useState(true)

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

  useEffect(() => {
    if (!open) return
    if (!availableModels.some((model) => model.id === selectedModelId)) setSelectedModelId(availableModels[0]?.id || '')
  }, [open, availableModels, selectedModelId])

  const parserConfig = useMemo(() => ({ normalize_whitespace: normalizeWhitespace, preserve_page_boundaries: preservePageBoundaries }), [normalizeWhitespace, preservePageBoundaries])
  const chunkingConfig = useMemo(() => ({ preset, strategy, chunk_size: chunkSize, chunk_overlap: chunkOverlap, min_chunk_size: minChunkSize, preserve_paragraphs: preserveParagraphs, preserve_headings: preserveHeadings, preserve_page_boundaries: preservePageBoundaries }), [preset, strategy, chunkSize, chunkOverlap, minChunkSize, preserveParagraphs, preserveHeadings, preservePageBoundaries])
  const retrievalConfig = useMemo(() => ({ search_strategy: 'similarity' as const, candidate_k: candidateK, top_k: topK, min_score: minScoreEnabled ? minScore : null, max_context_chunks: maxContextChunks, max_chunks_per_document: maxChunksPerDocument, max_context_chars: maxContextChars, query_mode: queryMode, history_turns: historyTurns, grounding_policy: groundingPolicy }), [candidateK, topK, minScoreEnabled, minScore, maxContextChunks, maxChunksPerDocument, maxContextChars, queryMode, historyTurns, groundingPolicy])

  const validate = () => {
    if (chunkOverlap >= chunkSize) return 'Chunk overlap must be lower than chunk size'
    if (minChunkSize > chunkSize) return 'Minimum chunk size cannot be greater than chunk size'
    if (topK > candidateK) return 'Top K cannot be greater than Candidates'
    if (maxContextChunks > topK) return 'Max context chunks cannot be greater than Top K'
    return null
  }

  const applyPreset = (nextPreset: RagChunkingPreset) => {
    setPreset(nextPreset)
    if (nextPreset === 'custom') return
    const config = CHUNKING_PRESETS[nextPreset]
    setStrategy(config.strategy)
    setChunkSize(config.chunk_size)
    setChunkOverlap(config.chunk_overlap)
    setMinChunkSize(config.min_chunk_size)
    setPreserveParagraphs(config.preserve_paragraphs)
    setPreserveHeadings(config.preserve_headings)
    setPreservePageBoundaries(config.preserve_page_boundaries)
  }

  const customNumber = (setter: (value: number) => void, value: number) => {
    setPreset('custom')
    setter(value)
  }

  const runPreview = async () => {
    if (!collection) return
    const error = validate()
    if (error) {
      toast.error(error)
      return
    }
    try {
      await previewSnapshot.mutateAsync({ project_id: projectId, parser: parserConfig, chunking: chunkingConfig })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to preview chunks')
    }
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!collection || !selectedModelId) return
    const error = validate()
    if (error) {
      toast.error(error)
      return
    }
    try {
      await createSnapshot.mutateAsync({
        project_id: projectId,
        embedding_provider_model_id: selectedModelId,
        description: description.trim() || undefined,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
        chunking_strategy: strategy,
        parser_config: parserConfig,
        retrieval_defaults: retrievalConfig,
        build_config: { parser: parserConfig, chunking: chunkingConfig, retrieval: retrievalConfig },
      })
      toast.success('Vector build queued')
      setDescription('')
      setShowAdvanced(false)
      previewSnapshot.reset()
      onCreated()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to build vectors')
    }
  }

  return (
    <>
      <Dialog open={open && Boolean(collection)} onClose={onClose} title="Build vectors" className="max-h-[calc(100svh-2rem)] max-w-3xl overflow-hidden">
        {collection && (
          <form onSubmit={submit} className="max-h-[calc(100svh-8rem)] space-y-5 overflow-y-auto pr-1">
            <div>
              <div className="mb-1.5 flex items-center justify-between gap-3">
                <label className="block text-sm font-medium text-muted">Embedding model</label>
                <Button type="button" size="sm" variant="ghost" className="h-auto px-0 py-0 text-xs" onClick={() => setCreateModelOpen(true)}><Plus className="mr-1 h-3.5 w-3.5" /> Add model</Button>
              </div>
              {availableModels.length === 0 ? (
                <div className="rounded-xl border border-border bg-background/60 p-4">
                  <p className="text-sm font-medium text-white">No embedding model configured.</p>
                  <p className="mt-1 text-sm leading-6 text-muted">Add an embedding model to build vectors for this Collection.</p>
                  <Button type="button" size="sm" variant="outline" className="mt-4" onClick={() => setCreateModelOpen(true)}>Add embedding model</Button>
                </div>
              ) : <Select value={selectedModelId} onChange={(event) => setSelectedModelId(event.target.value)} options={availableModels.map((model) => ({ value: model.id, label: `${model.name} · ${model.model}` }))} />}
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-muted">Chunking preset</label>
              <Select value={preset} onChange={(event) => applyPreset(event.target.value as RagChunkingPreset)} options={[{ value: 'precise', label: 'Precise · smaller focused chunks' }, { value: 'balanced', label: 'Balanced · recommended' }, { value: 'broad', label: 'Broad context · larger chunks' }, { value: 'custom', label: 'Custom' }]} />
            </div>

            <VectorBuildPreview preview={previewSnapshot.data} loading={previewSnapshot.isPending} error={previewSnapshot.error instanceof Error ? previewSnapshot.error.message : null} onPreview={runPreview} />

            <button type="button" className="flex items-center gap-2 text-sm font-medium text-white" onClick={() => setShowAdvanced((value) => !value)}>
              {showAdvanced ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />} Advanced settings
            </button>

            {showAdvanced && (
              <div className="space-y-5 rounded-xl border border-border bg-background/60 p-4">
                <section>
                  <p className="text-sm font-medium text-white">Chunking</p>
                  <p className="mt-1 text-xs text-muted">Controls how source documents are split before embedding.</p>
                  <div className="mt-4 grid gap-4 sm:grid-cols-2">
                    <div><label className="mb-1.5 block text-xs font-medium text-muted">Strategy</label><Select value={strategy} onChange={(event) => { setPreset('custom'); setStrategy(event.target.value as RagChunkingStrategy) }} options={[{ value: 'recursive_text', label: 'Recursive text' }, { value: 'paragraph', label: 'Paragraph' }, { value: 'markdown_headings', label: 'Markdown headings' }]} /></div>
                    <div><label className="mb-1.5 block text-xs font-medium text-muted">Chunk size · characters</label><Input type="number" min={200} max={4000} value={chunkSize} onChange={(event) => customNumber(setChunkSize, Number(event.target.value))} /></div>
                    <div><label className="mb-1.5 block text-xs font-medium text-muted">Chunk overlap · characters</label><Input type="number" min={0} max={1000} value={chunkOverlap} onChange={(event) => customNumber(setChunkOverlap, Number(event.target.value))} /></div>
                    <div><label className="mb-1.5 block text-xs font-medium text-muted">Minimum chunk size</label><Input type="number" min={20} max={1000} value={minChunkSize} onChange={(event) => customNumber(setMinChunkSize, Number(event.target.value))} /></div>
                  </div>
                  <div className="mt-4 grid gap-2 sm:grid-cols-2">
                    <CheckField checked={preserveParagraphs} label="Preserve paragraphs" onChange={(value) => { setPreset('custom'); setPreserveParagraphs(value) }} />
                    <CheckField checked={preserveHeadings} label="Preserve headings" onChange={(value) => { setPreset('custom'); setPreserveHeadings(value) }} />
                    <CheckField checked={preservePageBoundaries} label="Preserve PDF pages" onChange={(value) => { setPreset('custom'); setPreservePageBoundaries(value) }} />
                    <CheckField checked={normalizeWhitespace} label="Normalize whitespace" onChange={setNormalizeWhitespace} />
                  </div>
                </section>

                <section className="border-t border-border pt-5">
                  <p className="text-sm font-medium text-white">Default runtime retrieval</p>
                  <p className="mt-1 text-xs text-muted">Saved with this Vector Snapshot. Agents can inherit or override these defaults.</p>
                  <div className="mt-4 grid gap-4 sm:grid-cols-2">
                    <div><label className="mb-1.5 block text-xs font-medium text-muted">Candidates</label><Input type="number" min={1} max={100} value={candidateK} onChange={(event) => setCandidateK(Number(event.target.value))} /></div>
                    <div><label className="mb-1.5 block text-xs font-medium text-muted">Top K</label><Input type="number" min={1} max={20} value={topK} onChange={(event) => setTopK(Number(event.target.value))} /></div>
                    <div><label className="mb-1.5 block text-xs font-medium text-muted">Max context chunks</label><Input type="number" min={1} max={20} value={maxContextChunks} onChange={(event) => setMaxContextChunks(Number(event.target.value))} /></div>
                    <div><label className="mb-1.5 block text-xs font-medium text-muted">Max chunks per document</label><Input type="number" min={1} max={20} value={maxChunksPerDocument} onChange={(event) => setMaxChunksPerDocument(Number(event.target.value))} /></div>
                    <div><label className="mb-1.5 block text-xs font-medium text-muted">Max context · characters</label><Input type="number" min={1000} max={100000} step={1000} value={maxContextChars} onChange={(event) => setMaxContextChars(Number(event.target.value))} /></div>
                    <div><label className="mb-1.5 block text-xs font-medium text-muted">Query mode</label><Select value={queryMode} onChange={(event) => setQueryMode(event.target.value as RagQueryMode)} options={[{ value: 'conversation_context', label: 'Conversation aware' }, { value: 'current_message', label: 'Current message only' }]} /></div>
                    {queryMode === 'conversation_context' && <div><label className="mb-1.5 block text-xs font-medium text-muted">History turns</label><Input type="number" min={1} max={10} value={historyTurns} onChange={(event) => setHistoryTurns(Number(event.target.value))} /></div>}
                    <div><label className="mb-1.5 block text-xs font-medium text-muted">Grounding policy</label><Select value={groundingPolicy} onChange={(event) => setGroundingPolicy(event.target.value as RagGroundingPolicy)} options={[{ value: 'optional', label: 'Allow model answer' }, { value: 'required', label: 'Require knowledge' }]} /></div>
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-[auto_1fr] sm:items-end">
                    <CheckField checked={minScoreEnabled} label="Minimum similarity" detail="Disabled by default so candidates remain observable." onChange={setMinScoreEnabled} />
                    <div><label className="mb-1.5 block text-xs font-medium text-muted">Minimum score</label><Input type="number" min={0} max={1} step="0.05" disabled={!minScoreEnabled} value={minScore} onChange={(event) => setMinScore(Number(event.target.value))} /></div>
                  </div>
                </section>

                <section className="border-t border-border pt-5"><label className="mb-1.5 block text-sm font-medium text-muted">Description</label><Textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Optional note for this snapshot." className="min-h-[76px]" /></section>
              </div>
            )}

            <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" onClick={onClose} disabled={createSnapshot.isPending}>Cancel</Button>
              <Button type="submit" loading={createSnapshot.isPending} disabled={!selectedModelId || availableModels.length === 0}>Build vectors</Button>
            </div>
          </form>
        )}
      </Dialog>

      <CreateEmbeddingModelModal open={createModelOpen} projectId={projectId} onClose={() => setCreateModelOpen(false)} onCreated={(modelId) => { setSelectedModelId(modelId); setCreateModelOpen(false); void modelsQuery.refetch() }} />
    </>
  )
}
