import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { ChevronDown, ChevronRight, Plus } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { CreateEmbeddingModelModal } from '@/features/knowledge/components/CreateEmbeddingModelModal'
import { useCreateVectorSnapshot } from '@/features/knowledge/vectorHooks'
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

export function BuildVectorSnapshotModalV2({ open, projectId, collection, onClose, onCreated }: BuildVectorSnapshotModalV2Props) {
  const createSnapshot = useCreateVectorSnapshot(collection?.id, projectId)
  const modelsQuery = useProviderModels(projectId)
  const availableModels = useMemo(() => (modelsQuery.data ?? []).filter(isEmbeddingModel), [modelsQuery.data])
  const [selectedModelId, setSelectedModelId] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [createModelOpen, setCreateModelOpen] = useState(false)
  const [description, setDescription] = useState('')
  const [chunkSize, setChunkSize] = useState(800)
  const [chunkOverlap, setChunkOverlap] = useState(120)
  const [topK, setTopK] = useState(5)
  const [scoreThreshold, setScoreThreshold] = useState(0.7)

  useEffect(() => {
    if (!open) return
    if (!availableModels.some((model) => model.id === selectedModelId)) setSelectedModelId(availableModels[0]?.id || '')
  }, [open, availableModels, selectedModelId])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!collection || !selectedModelId) return
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
      setShowAdvanced(false)
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
                <label className="block text-sm font-medium text-muted">Embedding model</label>
                <Button type="button" size="sm" variant="ghost" className="h-auto px-0 py-0 text-xs" onClick={() => setCreateModelOpen(true)}>
                  <Plus className="mr-1 h-3.5 w-3.5" /> Add model
                </Button>
              </div>
              {availableModels.length === 0 ? (
                <div className="rounded-xl border border-border bg-background/60 p-4">
                  <p className="text-sm font-medium text-white">No embedding model configured.</p>
                  <p className="mt-1 text-sm leading-6 text-muted">Add an embedding model to build vectors for this Collection.</p>
                  <Button type="button" size="sm" variant="outline" className="mt-4" onClick={() => setCreateModelOpen(true)}>Add embedding model</Button>
                </div>
              ) : (
                <Select
                  value={selectedModelId}
                  onChange={(event) => setSelectedModelId(event.target.value)}
                  options={availableModels.map((model) => ({ value: model.id, label: `${model.name} · ${model.model}` }))}
                />
              )}
            </div>

            <button type="button" className="flex items-center gap-2 text-sm font-medium text-white" onClick={() => setShowAdvanced((value) => !value)}>
              {showAdvanced ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              Advanced settings
            </button>

            {showAdvanced && (
              <div className="space-y-4 rounded-xl border border-border bg-background/60 p-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div><label className="mb-1.5 block text-sm font-medium text-muted">Chunk size</label><Input type="number" min={200} max={4000} value={chunkSize} onChange={(event) => setChunkSize(Number(event.target.value))} /></div>
                  <div><label className="mb-1.5 block text-sm font-medium text-muted">Chunk overlap</label><Input type="number" min={0} max={1000} value={chunkOverlap} onChange={(event) => setChunkOverlap(Number(event.target.value))} /></div>
                  <div><label className="mb-1.5 block text-sm font-medium text-muted">Retrieval top K</label><Input type="number" min={1} max={20} value={topK} onChange={(event) => setTopK(Number(event.target.value))} /></div>
                  <div><label className="mb-1.5 block text-sm font-medium text-muted">Score threshold</label><Input type="number" min={0} max={1} step="0.05" value={scoreThreshold} onChange={(event) => setScoreThreshold(Number(event.target.value))} /></div>
                </div>
                <div><label className="mb-1.5 block text-sm font-medium text-muted">Description</label><Textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Optional note for this snapshot." className="min-h-[76px]" /></div>
              </div>
            )}

            <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" onClick={onClose} disabled={createSnapshot.isPending}>Cancel</Button>
              <Button type="submit" loading={createSnapshot.isPending} disabled={!selectedModelId || availableModels.length === 0}>Build vectors</Button>
            </div>
          </form>
        )}
      </Dialog>

      <CreateEmbeddingModelModal
        open={createModelOpen}
        projectId={projectId}
        onClose={() => setCreateModelOpen(false)}
        onCreated={(modelId) => { setSelectedModelId(modelId); setCreateModelOpen(false); void modelsQuery.refetch() }}
      />
    </>
  )
}
