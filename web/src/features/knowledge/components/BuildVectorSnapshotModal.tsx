import { useState, type FormEvent } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { useCreateVectorSnapshot } from '@/features/knowledge/vectorHooks'

interface BuildVectorSnapshotModalProps {
  open: boolean
  projectId: string
  collection: { id: string; name: string } | null
  onClose: () => void
  onCreated: () => void
}

export function BuildVectorSnapshotModal({ open, projectId, collection, onClose, onCreated }: BuildVectorSnapshotModalProps) {
  const createSnapshot = useCreateVectorSnapshot(collection?.id, projectId)
  const [modelId, setModelId] = useState('')
  const [description, setDescription] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [chunkSize, setChunkSize] = useState(800)
  const [chunkOverlap, setChunkOverlap] = useState(120)
  const [topK, setTopK] = useState(5)
  const [scoreThreshold, setScoreThreshold] = useState(0.7)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!collection) return
    if (!modelId.trim()) {
      toast.error('Embedding model id is required')
      return
    }
    if (chunkOverlap >= chunkSize) {
      toast.error('Chunk overlap must be lower than chunk size')
      return
    }

    try {
      await createSnapshot.mutateAsync({
        project_id: projectId,
        embedding_provider_model_id: modelId.trim(),
        description: description.trim() || undefined,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
        chunking_strategy: 'recursive_text',
        build_config: {
          chunking: { strategy: 'recursive_text', chunk_size: chunkSize, chunk_overlap: chunkOverlap, min_chars: 100, max_chars: Math.max(chunkSize, 1200) },
          parser: { strategy: 'default', normalize_whitespace: true, extract_metadata: true },
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
    <Dialog open={open && Boolean(collection)} onClose={onClose} title="Build vectors" className="max-w-2xl">
      {collection && (
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="rounded-xl border border-border bg-background/70 p-3">
            <p className="text-[11px] font-medium uppercase tracking-wider text-muted">Collection</p>
            <p className="mt-1 truncate text-sm font-medium text-white">{collection.name}</p>
            <p className="mt-1 text-xs text-muted">This creates an immutable vector snapshot from the current active documents.</p>
          </div>

          <div>
            <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Embedding model ID</label>
            <Input value={modelId} onChange={(event) => setModelId(event.target.value)} placeholder="Provider model UUID configured for embeddings" />
            <p className="mt-2 text-xs leading-5 text-muted">MVP note: use the project embedding provider model id. A selectable model picker can reuse this modal later.</p>
          </div>

          <div>
            <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Description</label>
            <Textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Optional note for this snapshot." className="min-h-[84px]" />
          </div>

          <button type="button" className="flex items-center gap-2 text-sm font-medium text-white" onClick={() => setShowAdvanced((value) => !value)}>
            {showAdvanced ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            Advanced settings
          </button>

          {showAdvanced && (
            <div className="grid gap-4 rounded-xl border border-border bg-background/60 p-4 sm:grid-cols-2">
              <div><label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Chunk size</label><Input type="number" min={200} max={4000} value={chunkSize} onChange={(event) => setChunkSize(Number(event.target.value))} /></div>
              <div><label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Chunk overlap</label><Input type="number" min={0} max={1000} value={chunkOverlap} onChange={(event) => setChunkOverlap(Number(event.target.value))} /></div>
              <div><label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Retrieval top K</label><Input type="number" min={1} max={20} value={topK} onChange={(event) => setTopK(Number(event.target.value))} /></div>
              <div><label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-muted">Score threshold</label><Input type="number" min={0} max={1} step="0.05" value={scoreThreshold} onChange={(event) => setScoreThreshold(Number(event.target.value))} /></div>
            </div>
          )}

          <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" onClick={onClose} disabled={createSnapshot.isPending}>Cancel</Button>
            <Button type="submit" loading={createSnapshot.isPending}>Build vectors</Button>
          </div>
        </form>
      )}
    </Dialog>
  )
}
