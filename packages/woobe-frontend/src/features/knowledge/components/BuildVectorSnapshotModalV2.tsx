import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Database, Eye, Plus, SlidersHorizontal } from 'lucide-react'
import { toast } from 'sonner'
import {
  Button,
  Checkbox,
  Dialog,
  EmptyStatePanel,
  Field,
  FieldDescription,
  FieldLabel,
  SectionBlock,
  SegmentedControl,
} from '@woobe/ui'

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
    <label className="flex cursor-pointer items-start gap-ui-sm rounded-container border border-border bg-background/25 p-ui-md">
      <Checkbox checked={checked} onChange={(event) => onChange(event.target.checked)} className="mt-ui-xs" />
      <span className="min-w-0">
        <span className="block font-mono text-system-label font-semibold text-accent-foreground">{label}</span>
        {detail ? <span className="mt-ui-xs block font-sans text-product-caption text-muted-foreground">{detail}</span> : null}
      </span>
    </label>
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
      <Dialog
        open={open && Boolean(collection)}
        onClose={onClose}
        title="Build vectors"
        className="max-w-dialog-wide"
        scrollMode="content"
        contentClassName="p-0"
      >
        {collection ? (
          <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
            <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-ui-lg">
              <div className="grid gap-ui-lg lg:grid-cols-3">
                <aside className="space-y-ui-md lg:col-span-1">
                  <SectionBlock
                    density="compact"
                    eyebrow="Collection"
                    title={collection.name}
                    description="Build an immutable vector snapshot from the Collection's active documents."
                    actions={<Database className="h-icon w-icon text-primary-light" />}
                  >
                    <div className="grid gap-ui-sm border-t border-border pt-ui-md font-mono text-system-meta text-muted-foreground">
                      <div className="flex items-center justify-between gap-ui-md"><span>Model</span><span className="truncate text-accent-foreground/85">{selectedModel?.name || 'Not selected'}</span></div>
                      <div className="flex items-center justify-between gap-ui-md"><span>Preset</span><span className="capitalize text-accent-foreground/85">{preset}</span></div>
                    </div>
                  </SectionBlock>

                  <SectionBlock density="compact" title="Build setup">
                    <div className="space-y-ui-md">
                      <Field>
                        <div className="flex items-center justify-between gap-ui-sm">
                          <FieldLabel>Embedding model</FieldLabel>
                          <Button type="button" size="sm" variant="ghost" onClick={() => setCreateModelOpen(true)}>
                            <Plus className="mr-ui-xs h-icon-sm w-icon-sm" />Add model
                          </Button>
                        </div>
                        {availableModels.length === 0 ? (
                          <EmptyStatePanel compact title="No embedding model configured" description="Add a model before building vectors." action={<Button type="button" size="sm" variant="outline" onClick={() => setCreateModelOpen(true)}>Add embedding model</Button>} />
                        ) : (
                          <Select value={selectedModelId} onChange={(event) => setSelectedModelId(event.target.value)} options={availableModels.map((model) => ({ value: model.id, label: `${model.name} · ${model.model}` }))} />
                        )}
                      </Field>

                      <Field>
                        <FieldLabel>Chunking preset</FieldLabel>
                        <Select value={preset} onChange={(event) => applyPreset(event.target.value as RagChunkingPreset)} options={[{ value: 'precise', label: 'Precise · smaller focused chunks' }, { value: 'balanced', label: 'Balanced · recommended' }, { value: 'broad', label: 'Broad context · larger chunks' }, { value: 'custom', label: 'Custom' }]} />
                      </Field>
                    </div>
                  </SectionBlock>
                </aside>

                <main className="min-w-0 space-y-ui-md lg:col-span-2">
                  <SegmentedControl
                    value={section}
                    onValueChange={(value) => setSection(value as ModalSection)}
                    ariaLabel="Vector build section"
                    items={[
                      { value: 'preview', label: 'Preview', icon: <Eye className="h-icon-sm w-icon-sm" /> },
                      { value: 'advanced', label: 'Advanced settings', icon: <SlidersHorizontal className="h-icon-sm w-icon-sm" /> },
                    ]}
                  />

                  {section === 'preview' ? (
                    <VectorBuildPreview preview={previewSnapshot.data} loading={previewSnapshot.isPending} error={previewSnapshot.error instanceof Error ? previewSnapshot.error.message : null} onPreview={runPreview} />
                  ) : (
                    <div className="space-y-ui-md">
                      <SectionBlock density="compact" title="Chunking" description="Controls how source documents are split before embedding. Retrieval behavior is configured on the Agent Draft.">
                        <div className="grid gap-ui-md sm:grid-cols-2">
                          <Field><FieldLabel>Strategy</FieldLabel><Select value={strategy} onChange={(event) => { setPreset('custom'); setStrategy(event.target.value as RagChunkingStrategy) }} options={[{ value: 'recursive_text', label: 'Recursive text' }, { value: 'paragraph', label: 'Paragraph' }, { value: 'markdown_headings', label: 'Markdown headings' }]} /></Field>
                          <Field><FieldLabel>Chunk size · characters</FieldLabel><Input type="number" min={200} max={4000} value={chunkSize} onChange={(event) => customNumber(setChunkSize, Number(event.target.value))} /></Field>
                          <Field><FieldLabel>Chunk overlap · characters</FieldLabel><Input type="number" min={0} max={1000} value={chunkOverlap} onChange={(event) => customNumber(setChunkOverlap, Number(event.target.value))} /></Field>
                          <Field><FieldLabel>Minimum chunk size</FieldLabel><Input type="number" min={20} max={1000} value={minChunkSize} onChange={(event) => customNumber(setMinChunkSize, Number(event.target.value))} /></Field>
                        </div>
                        <div className="mt-ui-md grid gap-ui-sm sm:grid-cols-2">
                          <CheckField checked={preserveParagraphs} label="Preserve paragraphs" onChange={(value) => { setPreset('custom'); setPreserveParagraphs(value) }} />
                          <CheckField checked={preserveHeadings} label="Preserve headings" onChange={(value) => { setPreset('custom'); setPreserveHeadings(value) }} />
                          <CheckField checked={preservePageBoundaries} label="Preserve PDF pages" onChange={(value) => { setPreset('custom'); setPreservePageBoundaries(value) }} />
                          <CheckField checked={normalizeWhitespace} label="Normalize whitespace" onChange={setNormalizeWhitespace} />
                        </div>
                      </SectionBlock>

                      <SectionBlock density="compact" title="Description">
                        <Field>
                          <FieldLabel>Snapshot note</FieldLabel>
                          <Textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Optional note for this snapshot." className="min-h-textarea-compact" />
                          <FieldDescription>Optional release note describing what changed in this snapshot.</FieldDescription>
                        </Field>
                      </SectionBlock>
                    </div>
                  )}
                </main>
              </div>
            </div>

            <div className="flex shrink-0 flex-col-reverse gap-ui-sm border-t border-border bg-surface/95 px-ui-lg py-ui-md sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" onClick={onClose} disabled={createSnapshot.isPending}>Cancel</Button>
              <Button type="submit" loading={createSnapshot.isPending} disabled={!selectedModelId || availableModels.length === 0}>Build vectors</Button>
            </div>
          </form>
        ) : null}
      </Dialog>

      <CreateEmbeddingModelModal open={createModelOpen} projectId={projectId} onClose={() => setCreateModelOpen(false)} onCreated={(modelId) => { setSelectedModelId(modelId); setCreateModelOpen(false); void modelsQuery.refetch() }} />
    </>
  )
}
