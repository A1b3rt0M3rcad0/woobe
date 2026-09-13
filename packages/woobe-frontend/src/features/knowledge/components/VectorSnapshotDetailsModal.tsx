import { Alert, AlertDescription, Dialog, SectionBlock, TechnicalListItem } from '@woobe/ui'

import { StatusBadge } from '@/components/common/StatusBadge'
import type { VectorSnapshot } from '@/features/knowledge/types'
import { formatDate } from '@/lib/formatters/date'

interface VectorSnapshotDetailsModalProps {
  snapshot: VectorSnapshot | null
  onClose: () => void
}

function shortHash(value?: string | null) {
  return value ? value.slice(0, 12) : '-'
}

function Detail({ label, value }: { label: string; value: string | number | null | undefined }) {
  return <TechnicalListItem label={label} description={value ?? '-'} />
}

export function VectorSnapshotDetailsModal({ snapshot, onClose }: VectorSnapshotDetailsModalProps) {
  return (
    <Dialog open={Boolean(snapshot)} onClose={onClose} title="Vector snapshot details" className="max-w-dialog">
      {snapshot ? (
        <div className="grid gap-ui-md">
          <TechnicalListItem
            label={snapshot.version}
            description="Immutable vector build for this Collection."
            trailing={<StatusBadge status={snapshot.status} size="compact" />}
          />

          {snapshot.error_message ? (
            <Alert variant="destructive">
              <AlertDescription>{snapshot.error_message}</AlertDescription>
            </Alert>
          ) : null}

          <SectionBlock title="Build metadata" density="compact">
            <div className="grid gap-ui-xs sm:grid-cols-2">
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
            </div>
          </SectionBlock>
        </div>
      ) : null}
    </Dialog>
  )
}
