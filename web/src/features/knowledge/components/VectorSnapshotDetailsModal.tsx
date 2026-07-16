import { Dialog } from '@/components/ui/Dialog'
import { StatusBadge } from '@/components/common/StatusBadge'
import { formatDate } from '@/lib/formatters/date'
import type { VectorSnapshot } from '@/features/knowledge/types'

interface VectorSnapshotDetailsModalProps {
  snapshot: VectorSnapshot | null
  onClose: () => void
}

function shortHash(value?: string | null) {
  return value ? value.slice(0, 12) : '-'
}

function Detail({ label, value }: { label: string; value: string | number | null | undefined }) {
  return <div><dt className="text-muted">{label}</dt><dd className="mt-1 break-words text-white/85">{value ?? '-'}</dd></div>
}

export function VectorSnapshotDetailsModal({ snapshot, onClose }: VectorSnapshotDetailsModalProps) {
  return (
    <Dialog open={Boolean(snapshot)} onClose={onClose} title="Vector snapshot details" className="max-w-2xl">
      {snapshot && (
        <div className="space-y-5 text-sm">
          <div className="flex items-start justify-between gap-3 rounded-xl border border-border bg-background/70 p-4">
            <div>
              <p className="text-base font-semibold text-white">{snapshot.version}</p>
              <p className="mt-1 text-xs text-muted">Immutable vector build for this Collection.</p>
            </div>
            <StatusBadge status={snapshot.status} />
          </div>

          {snapshot.error_message && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm leading-6 text-red-200">
              {snapshot.error_message}
            </div>
          )}

          <dl className="grid gap-4 rounded-xl border border-border bg-background/60 p-4 sm:grid-cols-2">
            <Detail label="Documents" value={snapshot.document_count} />
            <Detail label="Chunks" value={snapshot.chunk_count} />
            <Detail label="Vectors" value={snapshot.vector_count ?? snapshot.chunk_count} />
            <Detail label="Stage" value={snapshot.build_stage} />
            <Detail label="Embedding" value={`${snapshot.embedding_provider} / ${snapshot.embedding_model}`} />
            <Detail label="Dimensions" value={snapshot.embedding_dimensions} />
            <Detail label="Chunking" value={`${snapshot.chunking_strategy} · ${snapshot.chunk_size}/${snapshot.chunk_overlap}`} />
            <Detail label="Snapshot hash" value={shortHash(snapshot.snapshot_hash)} />
            <Detail label="Build config hash" value={shortHash(snapshot.build_config_hash)} />
            <Detail label="Created" value={snapshot.created_at ? formatDate(snapshot.created_at) : '-'} />
            <Detail label="Started" value={snapshot.started_at ? formatDate(snapshot.started_at) : '-'} />
            <Detail label="Completed" value={snapshot.completed_at ? formatDate(snapshot.completed_at) : '-'} />
          </dl>
        </div>
      )}
    </Dialog>
  )
}
