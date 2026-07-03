import { useState } from 'react'
import { Cpu, RefreshCw, Upload } from 'lucide-react'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Tabs } from '@/components/ui/Tabs'
import { BuildVectorSnapshotModal } from '@/features/knowledge/components/BuildVectorSnapshotModal'
import { VectorSnapshotDetailsModal } from '@/features/knowledge/components/VectorSnapshotDetailsModal'
import { useCollectionOverview, useVectorSnapshots } from '@/features/knowledge/vectorHooks'
import { formatDate } from '@/lib/formatters/date'
import type { Collection, VectorSnapshot } from '@/features/knowledge/types'

interface CollectionVectorWorkspaceProps {
  projectId: string
  collection: Collection
  documentCount: number
  readyDocumentCount: number
  onUploadDocument: () => void
}

function numberLabel(value?: number | null) {
  return typeof value === 'number' ? value.toLocaleString() : '0'
}

function statusLabel(status?: string) {
  return (status || 'UNKNOWN').replace(/_/g, ' ')
}

function StatCard({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-xl border border-border/80 bg-background/60 p-4">
      <p className="text-[11px] font-medium uppercase tracking-wider text-muted">{label}</p>
      <p className="mt-2 text-base font-semibold text-white">{value}</p>
      {detail && <p className="mt-1 text-xs leading-5 text-muted">{detail}</p>}
    </div>
  )
}

export function CollectionVectorWorkspace({ projectId, collection, documentCount, readyDocumentCount, onUploadDocument }: CollectionVectorWorkspaceProps) {
  const [buildOpen, setBuildOpen] = useState(false)
  const [selectedSnapshot, setSelectedSnapshot] = useState<VectorSnapshot | null>(null)
  const { data: overview, refetch: refetchOverview } = useCollectionOverview(collection.id, projectId)
  const { data: snapshots, refetch: refetchSnapshots } = useVectorSnapshots(collection.id, projectId)
  const items = snapshots ?? []
  const hasRunningBuild = overview?.rag_status === 'BUILDING' || items.some((snapshot) => snapshot.status === 'BUILDING')

  const refresh = () => {
    void refetchOverview()
    void refetchSnapshots()
  }

  const overviewContent = (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white">RAG overview</h3>
          <p className="mt-1 text-xs leading-5 text-muted">Documents, processing state and vector readiness for this Collection.</p>
        </div>
        <StatusBadge status={overview?.rag_status || 'UNKNOWN'} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Status" value={statusLabel(overview?.rag_status)} detail={overview?.warnings?.[0] || 'Current operational RAG state.'} />
        <StatCard label="Files" value={`${overview?.documents.active ?? documentCount} active`} detail={`${overview?.documents.ready ?? readyDocumentCount} ready · ${overview?.documents.pending ?? 0} pending`} />
        <StatCard label="Vectors" value={overview?.latest_ready_snapshot ? `${overview.latest_ready_snapshot.version} ready` : 'Not built'} detail={`${numberLabel(overview?.latest_ready_snapshot?.chunk_count)} chunks · ${numberLabel(overview?.latest_ready_snapshot?.vector_count)} vectors`} />
        <StatCard label="Embedding" value={overview?.technology.embedding_model || 'Not selected'} detail={overview?.technology.embedding_provider || 'Configured when vectors are built.'} />
      </div>
      {overview?.processing.has_running_job && (
        <div className="rounded-xl border border-primary/25 bg-primary/10 p-3 text-sm leading-6 text-primary-light">
          Building vectors · {overview.processing.stage || 'QUEUED'} · {overview.processing.embedded_chunks}/{overview.processing.total_chunks || 0} chunks embedded
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {documentCount === 0 ? (
          <Button type="button" onClick={onUploadDocument}><Upload className="mr-2 h-4 w-4" />Upload document</Button>
        ) : (
          <Button type="button" onClick={() => setBuildOpen(true)} disabled={hasRunningBuild}><Cpu className="mr-2 h-4 w-4" />{overview?.rag_status === 'OUTDATED' ? 'Rebuild vectors' : 'Build vectors'}</Button>
        )}
        <Button type="button" variant="outline" onClick={refresh}><RefreshCw className="mr-2 h-4 w-4" />Refresh</Button>
      </div>
    </div>
  )

  const vectorsContent = (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-white">Vector snapshots</h3>
          <p className="mt-1 text-xs leading-5 text-muted">Immutable versions generated from this Collection.</p>
        </div>
        <Button type="button" size="sm" onClick={() => setBuildOpen(true)} disabled={documentCount === 0 || hasRunningBuild}>Build new snapshot</Button>
      </div>
      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-background/50 p-6 text-center text-sm text-muted">No vector snapshot built yet.</div>
      ) : (
        <div className="space-y-2">
          {items.map((snapshot) => (
            <button key={snapshot.id} type="button" onClick={() => setSelectedSnapshot(snapshot)} className="grid w-full gap-3 rounded-lg border border-border/70 bg-background/55 p-3 text-left hover:border-primary/30 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
              <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="text-sm font-medium text-white">{snapshot.version}</p><StatusBadge status={snapshot.status} /></div><p className="mt-1 text-xs text-muted">{snapshot.embedding_model} · {numberLabel(snapshot.chunk_count)} chunks · {numberLabel(snapshot.vector_count ?? snapshot.chunk_count)} vectors</p></div>
              <p className="text-xs text-muted">{snapshot.completed_at ? formatDate(snapshot.completed_at) : snapshot.build_stage || 'Queued'}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  )

  const technologyContent = (
    <div className="grid gap-3 sm:grid-cols-2">
      <StatCard label="Embedding" value={overview?.technology.embedding_model || 'Not selected'} detail={overview?.technology.embedding_provider || 'BYOK provider model'} />
      <StatCard label="Chunking" value={overview?.technology.chunking_strategy || 'recursive_text'} detail={`${overview?.technology.chunk_size ?? 800} size · ${overview?.technology.chunk_overlap ?? 120} overlap`} />
      <StatCard label="Retrieval" value={`Top K ${overview?.technology.retrieval_top_k ?? 5}`} detail={`Threshold ${overview?.technology.retrieval_score_threshold ?? 0.7}`} />
      <StatCard label="Vector store" value={overview?.technology.vector_store || 'pgvector'} detail={overview?.technology.distance_metric || 'cosine'} />
    </div>
  )

  return (
    <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
      <Tabs defaultTab="overview" tabs={[{ id: 'overview', label: 'Overview', content: overviewContent }, { id: 'vectors', label: 'Vectors', content: vectorsContent }, { id: 'technology', label: 'Technology', content: technologyContent }]} />
      <BuildVectorSnapshotModal open={buildOpen} projectId={projectId} collection={{ id: collection.id, name: collection.name }} onClose={() => setBuildOpen(false)} onCreated={() => { setBuildOpen(false); refresh() }} />
      <VectorSnapshotDetailsModal snapshot={selectedSnapshot} onClose={() => setSelectedSnapshot(null)} />
    </section>
  )
}
