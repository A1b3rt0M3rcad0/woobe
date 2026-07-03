import { useEffect, useState, type FormEvent } from 'react'
import { ChevronDown, ChevronRight, Plus } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { CreateEmbeddingModelModal } from '@/features/knowledge/components/CreateEmbeddingModelModal'
import { useCreateVectorSnapshot, useKnowledgeProviderModels } from '@/features/knowledge/vectorHooks'

interface BuildVectorSnapshotModalV2Props {
  open: boolean
  projectId: string
  collection: { id: string; name: string } | null
  onClose: () => void
  onCreated: () => void
}

export function BuildVectorSnapshotModalV2({ open, projectId, collection, onClose, onCreated }: BuildVectorSnapshotModalV2Props) {
  const createSnapshot = useCreateVectorSnapshot(collection?.id, projectId)
  const { data: models, refetch: refetchModels } = useKnowledgeProviderModels(projectId)
  const availableModels = models ?? []
  const [selectedModelId, setSelectedModelId] = useState('')
  const [description, setDescription] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [createModelOpen, setCreateModelOpen] = useState(false)
  const [chunkSize, setChunkSize] = useState(800)
  const [chunkOverlap, setChunkOverlap] = useState(120)
  const [topK, setTopK] = useState(5)
  const [scoreThreshold, setScoreThreshold] = useState(0.7)

  useEffect(() => {
    if (!open) return
    if (!selectedModelId && availableModels[0]?.id) setSelectedModelId(String(availableModels[0].id))
  }, [open, availableModels, selectedModelId])

  const handleModelCreated = (modelId: string) => {
    setCreateModelOpen(false)
    setSelectedModelId(modelId)
    void refetchModels()
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!collection) return
    if (!selectedModelId) {
      toast.error('Select an embedding model')
      return
    }
    if (chunkOverlap >= chunkSize) {
      toast.error('Chunk overlap must be lower than chunk size')
      return
    }

    try {
      await createSnapshot.mutateAsync({
        project_id: projectId,
        embedding_provider_model_id: selectedModelId,
        description: description.trim() || undefined,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
        chunking_strategy: 'recursive_text',
        build_config: {
          chunking: { strategy: 'recursive_text', chunk_size: chunkSize, chunk_overlap: chunkOverlap, min_chars: 100, max_chars: Math.max(chunkSize, 1200) },
          parser: { strategy: 'default', normalize_whitespace: true },
          retrieval: { top_k: topK, score_threshold: scoreThreshold },
        },
      })
      toast.success('Vector build queued')
      setDescription('')
      onCreated()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to build vectors')
    }
  }

  return (
    <>
      <Dialog open={open && Boolean(collection)} onClose={onClose} title="Build vectors" className="max-w-xl">
        {collection && (
          <form onSubmit={submit} className="space-y-5">
            <div>
              <div className="mb-1.5 flex items-center justify-between gap-3">
                <label className="block text-[11px] font-medium uppercase tracking-wider text-muted">Embedding model</label>
                <button type="button" onClick={() => setCreateModelOpen(true)} className="inline-flex items-center gap-1 text-xs font-medium text-primary-light hover:text-primary">
                  <Plus className="h-3.5 w-3.5" /> Add model
                </button>
              </div>
              {availableModels.length === 0 ? (
                <div className="rounded-xl border border-border bg-background/60 p-3 text-sm leading-6 text-muted">
                  No embedding model configured. Add one to build vectors.
                </div>
              ) : (
                <select value={selectedModelId} onChange={(event) => setSelectedModelId(event.target.value)} className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-white outline-none focus:border-primary">
                  {availableModels.map((model) => <option key={String(model.id)} value={String(model.id)}>{String(model.name || model.model || 'Model')}</option>)}
                </select>
              )}
            </div>

            <div>
              <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Description</label>
              <Textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Optional note for this snapshot." className="min-h-[84px]" />
            </div>

            <button type="button" className="flex items-center gap-2 text-sm font-medium text-white" onClick={() => setShowAdvanced((value) => !value)}>
              {showAdvanced ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              Advanced settings
            </button>

            {showAdvanced && <div className="grid gap-4 rounded-xl border border-border bg-background/60 p-4 sm:grid-cols-2"><div><label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Chunk size</label><Input type="number" min={200} max={4000} value={chunkSize} onChange={(event) => setChunkSize(Number(event.target.value))} /></div><div><label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Chunk overlap</label><Input type="number" min={0} max={1000} value={chunkOverlap} onChange={(event) => setChunkOverlap(Number(event.target.value))} /></div><div><label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Retrieval top K</label><Input type="number" min={1} max={20} value={topK} onChange={(event) => setTopK(Number(event.target.value))} /></div><div><label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Score threshold</label><Input type="number" min={0} max={1} step="0.05" value={scoreThreshold} onChange={(event) => setScoreThreshold(Number(event.target.value))} /></div></div>}

            <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" onClick={onClose} disabled={createSnapshot.isPending}>Cancel</Button>
              <Button type="submit" loading={createSnapshot.isPending} disabled={!selectedModelId || availableModels.length === 0}>Build vectors</Button>
            </div>
          </form>
        )}
      </Dialog>
      <CreateEmbeddingModelModal open={createModelOpen} projectId={projectId} onClose={() => setCreateModelOpen(false)} onCreated={handleModelCreated} />
    </>
  )
}
