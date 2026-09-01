import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Database, Eye, Plus, SlidersHorizontal } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { CreateEmbeddingModelModal } from '@/features/knowledge/components/CreateEmbeddingModelModal'
import { VectorBuildPreview } from '@/features/knowledge/components/VectorBuildPreview'
import { CHUNKING_PRESETS, type RagChunkingPreset, type RagChunkingStrategy } from '@/features/knowledge/ragConfigTypes'
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

type ModalSection = 'preview' | 'advanced'

function isEmbeddingModel(model: ProviderModel) {
  const metadata = model.metadata || {}
  const capability = String(metadata.capability || metadata.type || '').toLowerCase()
  return (capability === 'embedding' || capability === 'embeddings' || model.model.toLowerCase().includes('embed')) && model.status === 'active'
}

function CheckField({ checked, label, detail, onChange }: { checked: boolean; label: string; detail?: string; onChange: (checked: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-border/70 bg-background/55 p-3">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="mt-0.5 h-4 w-4 rounded border-border bg-background" />
      <span><span className="block text-xs font-medium text-white">{label}</span>{detail && <span className="mt-1 block text-[11px] leading-5 text-muted">{detail}</span>}</span>
    </label>
  )
}

function SectionButton({ active, icon, children, onClick }: { active: boolean; icon: React.ReactNode; children: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${active ? 'bg-surface text-white shadow-sm' : 'text-muted hover:text-white'}`}
    >
      {icon}
      {children}
    </button>
  )
}

export function BuildVectorSnapshotModalV2({ open, projectId, collection, onClose, onCreated }: BuildVectorSnapshotModalV2Props) {
  const createSnapshot = useCreateVectorSnapshot(collection?.id, projectId)
  const previewSnapshot = usePreviewVectorSnapshot(collection?.id)
  const modelsQuery = useProviderModels(projectId)
  const availableModels = useMemo(() => (modelsQuery.data ?? []).filter(isEmbeddingModel), [modelsQuery.data])
  const [selectedModelId, setSelectedModelId] = useState('')
  const [section, setSection] = useState<ModalSection>('preview')
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

  const selectedModel = availableModels.find((model) => model.id === selectedModelId) || null

  useEffect(() => {
    if (!open) return
    if (!availableModels.some((model) => model.id === selectedModelId)) setSelectedModelId(availableModels[0]?.id || '')
  }, [open, availableModels, selectedModelId])

  useEffect(() => {
    if (!open) return
    setSection('preview')
  }, [open, collection?.id])

  const parserConfig = useMemo(() => ({ normalize_whitespace: normalizeWhitespace, preserve_page_boundaries: preservePageBoundaries }), [normalizeWhitespace, preservePageBoundaries])
  const chunkingConfig = useMemo(() => ({ preset, strategy, chunk_size: chunkSize, chunk_overlap: chunkOverlap, min_chunk_size: minChunkSize, preserve_paragraphs: preserveParagraphs, preserve_headings: preserveHeadings, preserve_page_boundaries: preservePageBoundaries }), [preset, strategy, chunkSize, chunkOverlap, minChunkSize, preserveParagraphs, preserveHeadings, preservePageBoundaries])

  const validate = () => {
    if (chunkOverlap >= chunkSize) return 'Chunk overlap must be lower than chunk size'
    if (minChunkSize > chunkSize) return 'Minimum chunk size cannot be greater than chunk size'
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
        build_config: { parser: parserConfig, chunking: chunkingConfig },
      })
      toast.success('Vector build queued')
      setDescription('')
      setSection('preview')
      previewSnapshot.reset()
      onCreated()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to build vectors')
    }
  }

  return (
    <>
      <Dialog open={open && Boolean(collection)} onClose={onClose} title="Build vectors" className="max-h-[calc(100svh-2rem)] max-w-6xl overflow-hidden">
        {collection && (
          <form onSubmit={submit}>
            <div className="scrollbar-thin max-h-[calc(100svh-8rem)] overflow-y-auto pr-1">
              <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
                <aside className="space-y-4 lg:sticky lg:top-0 lg:self-start">
                  <section className="rounded-xl border border-border/90 bg-surface/70 p-4">
                    <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-background text-primary-light">
                      <Database className="h-5 w-5" />
                    </div>
                    <div className="mt-5 min-w-0">
                      <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Collection</p>
                      <h3 className="mt-2 truncate text-base font-semibold text-white">{collection.name}</h3>
                      <p className="mt-2 text-xs leading-5 text-muted">Build an immutable vector snapshot from the Collection&apos;s active documents.</p>
                    </div>
                    <div className="mt-5 border-t border-border/70 pt-4">
                      <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Current setup</p>
                      <div className="mt-3 space-y-2 text-xs">
                        <div className="flex items-start justify-between gap-3"><span className="text-muted">Model</span><span className="min-w-0 truncate text-right text-white/90">{selectedModel?.name || 'Not selected'}</span></div>
                        <div className="flex items-center justify-between gap-3"><span className="text-muted">Preset</span><span className="capitalize text-white/90">{preset}</span></div>
                      </div>
                    </div>
                  </section>

                  <section className="rounded-xl border border-border/90 bg-background/60 p-4">
                    <div>
                      <div className="mb-1.5 flex items-center justify-between gap-3">
                        <label className="block text-sm font-medium text-muted">Embedding model</label>
                        <Button type="button" size="sm" variant="ghost" className="h-auto px-0 py-0 text-xs" onClick={() => setCreateModelOpen(true)}><Plus className="mr-1 h-3.5 w-3.5" /> Add model</Button>
                      </div>
                      {availableModels.length === 0 ? (
                        <div className="rounded-lg border border-border bg-surface/50 p-3">
                          <p className="text-xs font-medium text-white">No embedding model configured.</p>
                          <p className="mt-1 text-xs leading-5 text-muted">Add a model before building vectors.</p>
                          <Button type="button" size="sm" variant="outline" className="mt-3 w-full" onClick={() => setCreateModelOpen(true)}>Add embedding model</Button>
                        </div>
                      ) : (
                        <Select value={selectedModelId} onChange={(event) => setSelectedModelId(event.target.value)} options={availableModels.map((model) => ({ value: model.id, label: `${model.name} · ${model.model}` }))} />
                      )}
                    </div>

                    <div className="mt-4 border-t border-border/70 pt-4">
                      <label className="mb-1.5 block text-sm font-medium text-muted">Chunking preset</label>
                      <Select value={preset} onChange={(event) => applyPreset(event.target.value as RagChunkingPreset)} options={[{ value: 'precise', label: 'Precise · smaller focused chunks' }, { value: 'balanced', label: 'Balanced · recommended' }, { value: 'broad', label: 'Broad context · larger chunks' }, { value: 'custom', label: 'Custom' }]} />
                    </div>
                  </section>
                </aside>

                <main className="min-w-0 space-y-5">
                  <div className="inline-flex rounded-lg border border-border bg-background/60 p-1">
                    <SectionButton active={section === 'preview'} icon={<Eye className="h-4 w-4" />} onClick={() => setSection('preview')}>Preview</SectionButton>
                    <SectionButton active={section === 'advanced'} icon={<SlidersHorizontal className="h-4 w-4" />} onClick={() => setSection('advanced')}>Advanced settings</SectionButton>
                  </div>

                  {section === 'preview' ? (
                    <VectorBuildPreview preview={previewSnapshot.data} loading={previewSnapshot.isPending} error={previewSnapshot.error instanceof Error ? previewSnapshot.error.message : null} onPreview={runPreview} />
                  ) : (
                    <div className="space-y-5">
                      <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                        <h3 className="text-sm font-semibold text-white">Chunking</h3>
                        <p className="mt-1 text-xs leading-5 text-muted">Controls how source documents are split before embedding. Retrieval behavior is configured on the Agent Draft.</p>
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

                      <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                        <label className="mb-1.5 block text-sm font-medium text-muted">Description</label>
                        <p className="mb-3 text-xs leading-5 text-muted">Optional release note describing what changed in this snapshot.</p>
                        <Textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Optional note for this snapshot." className="min-h-[76px]" />
                      </section>
                    </div>
                  )}
                </main>
              </div>

              <div className="sticky bottom-0 -mx-1 mt-6 flex flex-col-reverse gap-2 border-t border-border bg-surface/95 px-1 py-4 backdrop-blur sm:flex-row sm:justify-end">
                <Button type="button" variant="outline" onClick={onClose} disabled={createSnapshot.isPending}>Cancel</Button>
                <Button type="submit" loading={createSnapshot.isPending} disabled={!selectedModelId || availableModels.length === 0}>Build vectors</Button>
              </div>
            </div>
          </form>
        )}
      </Dialog>

      <CreateEmbeddingModelModal open={createModelOpen} projectId={projectId} onClose={() => setCreateModelOpen(false)} onCreated={(modelId) => { setSelectedModelId(modelId); setCreateModelOpen(false); void modelsQuery.refetch() }} />
    </>
  )
}
