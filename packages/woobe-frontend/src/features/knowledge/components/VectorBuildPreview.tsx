import { Eye } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import type { VectorBuildPreview as VectorBuildPreviewData } from '@/features/knowledge/types'

interface VectorBuildPreviewProps {
  preview?: VectorBuildPreviewData
  loading: boolean
  error?: string | null
  onPreview: () => void
}

export function VectorBuildPreview({ preview, loading, error, onPreview }: VectorBuildPreviewProps) {
  return (
    <section className="rounded-xl border border-border bg-background/60 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-white">Estimated result</p>
          <p className="mt-1 text-xs leading-5 text-muted">Runs parsing and chunking only. No embeddings are created.</p>
        </div>
        <Button type="button" size="sm" variant="outline" loading={loading} onClick={onPreview}>
          <Eye className="mr-2 h-3.5 w-3.5" /> Preview chunks
        </Button>
      </div>

      {error && <p className="mt-3 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-200">{error}</p>}

      {preview ? (
        <>
          <div className="mt-4 grid grid-cols-3 gap-3">
            <div className="rounded-lg border border-border/70 bg-surface/60 p-3"><p className="text-[11px] uppercase tracking-wider text-muted">Documents</p><p className="mt-1 text-sm font-medium text-white">{preview.document_count.toLocaleString()}</p></div>
            <div className="rounded-lg border border-border/70 bg-surface/60 p-3"><p className="text-[11px] uppercase tracking-wider text-muted">Chunks</p><p className="mt-1 text-sm font-medium text-white">~{preview.estimated_chunk_count.toLocaleString()}</p></div>
            <div className="rounded-lg border border-border/70 bg-surface/60 p-3"><p className="text-[11px] uppercase tracking-wider text-muted">Vectors</p><p className="mt-1 text-sm font-medium text-white">~{preview.estimated_vector_count.toLocaleString()}</p></div>
          </div>

          {preview.sample_chunks.length > 0 && (
            <div className="mt-4 space-y-2">
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted">Sample chunks</p>
              {preview.sample_chunks.slice(0, 4).map((chunk) => (
                <div key={`${chunk.document_id}-${chunk.chunk_index}`} className="rounded-lg border border-border/70 bg-surface/50 p-3">
                  <div className="flex items-center justify-between gap-3 text-[11px] text-muted">
                    <span className="truncate">{chunk.document_title} · Chunk {chunk.chunk_index + 1}</span>
                    <span className="shrink-0">{chunk.character_count.toLocaleString()} chars</span>
                  </div>
                  <p className="mt-2 line-clamp-3 whitespace-pre-wrap text-xs leading-5 text-white/75">{chunk.preview}</p>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <p className="mt-4 text-xs text-muted">Preview the current configuration to see the estimated chunk count before building.</p>
      )}
    </section>
  )
}
