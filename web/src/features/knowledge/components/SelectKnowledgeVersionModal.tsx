import { useEffect, useMemo, useState } from 'react'
import { Check, Database, Search } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { LoadingState } from '@/components/common/LoadingState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { useCollections } from '@/features/knowledge/hooks'
import { useVectorSnapshots } from '@/features/knowledge/vectorHooks'
import type { Collection, VectorSnapshot } from '@/features/knowledge/types'

interface SelectKnowledgeVersionModalProps {
  open: boolean
  projectId: string
  currentSnapshotId?: string | null
  onClose: () => void
  onSelect: (snapshot: VectorSnapshot) => void
}

function formatDate(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date).replace(',', '')
}

export function SelectKnowledgeVersionModal({ open, projectId, currentSnapshotId, onClose, onSelect }: SelectKnowledgeVersionModalProps) {
  const { data: collections = [], isLoading: collectionsLoading } = useCollections(projectId)
  const [query, setQuery] = useState('')
  const [collectionId, setCollectionId] = useState<string | null>(null)
  const [snapshotId, setSnapshotId] = useState<string | null>(null)
  const { data: snapshots = [], isLoading: snapshotsLoading } = useVectorSnapshots(collectionId || undefined, projectId)

  useEffect(() => {
    if (!open) return
    setQuery('')
    setCollectionId(null)
    setSnapshotId(currentSnapshotId || null)
  }, [open, currentSnapshotId])

  const normalizedQuery = query.trim().toLowerCase()
  const visibleCollections = useMemo(() => {
    if (!normalizedQuery) return collections
    return collections.filter((collection) => `${collection.name} ${collection.description || ''}`.toLowerCase().includes(normalizedQuery))
  }, [collections, normalizedQuery])
  const readySnapshots = useMemo(
    () => snapshots.filter((snapshot) => snapshot.status === 'READY'),
    [snapshots],
  )
  const selectedSnapshot = readySnapshots.find((snapshot) => snapshot.id === snapshotId) || null
  const selectedCollection = collections.find((collection) => collection.id === collectionId) || null

  const chooseCollection = (collection: Collection) => {
    setCollectionId(collection.id)
    setSnapshotId(null)
  }

  return (
    <Dialog open={open} onClose={onClose} title="Select knowledge" className="max-w-3xl">
      <div className="space-y-5">
        {!collectionId ? (
          <>
            <div>
              <p className="text-sm font-medium text-white">Collections</p>
              <p className="mt-1 text-xs leading-5 text-muted">Choose the knowledge source, then select one immutable vector version.</p>
            </div>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
              <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search collections..." className="pl-9" />
            </div>
            {collectionsLoading ? <LoadingState variant="panel" layout="list" message="Loading collections..." /> : (
              <div className="max-h-[360px] space-y-2 overflow-y-auto pr-1">
                {visibleCollections.map((collection) => (
                  <button key={collection.id} type="button" onClick={() => chooseCollection(collection)} className="flex w-full items-center gap-3 rounded-xl border border-border bg-background/60 p-4 text-left transition-colors hover:border-primary/35 hover:bg-surface/70">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-border bg-background text-primary-light"><Database className="h-4 w-4" /></span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-white">{collection.name}</span>
                      <span className="mt-1 block truncate text-xs text-muted">{collection.description || 'No description provided'}</span>
                    </span>
                  </button>
                ))}
                {visibleCollections.length === 0 && <div className="rounded-xl border border-border bg-background/50 p-6 text-center text-sm text-muted">No collections found.</div>}
              </div>
            )}
          </>
        ) : (
          <>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-white">{selectedCollection?.name || 'Collection'}</p>
                <p className="mt-1 text-xs leading-5 text-muted">Only READY vector snapshots can be applied to an Agent.</p>
              </div>
              <Button type="button" variant="ghost" size="sm" onClick={() => { setCollectionId(null); setSnapshotId(null) }}>Change collection</Button>
            </div>

            {snapshotsLoading ? <LoadingState variant="panel" layout="list" message="Loading vector versions..." /> : (
              <div className="max-h-[380px] space-y-2 overflow-y-auto pr-1">
                {readySnapshots.map((snapshot) => {
                  const selected = snapshot.id === snapshotId
                  return (
                    <button key={snapshot.id} type="button" onClick={() => setSnapshotId(snapshot.id)} className={`w-full rounded-xl border p-4 text-left transition-colors ${selected ? 'border-primary/50 bg-primary/10' : 'border-border bg-background/60 hover:border-primary/30 hover:bg-surface/70'}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-mono text-sm font-medium text-white">{snapshot.version}</span>
                            <StatusBadge status={snapshot.status} />
                          </div>
                          <p className="mt-2 text-xs text-muted">{snapshot.document_count} documents · {snapshot.chunk_count.toLocaleString()} chunks</p>
                          <p className="mt-1 truncate text-xs text-muted">{snapshot.embedding_provider} · {snapshot.embedding_model}</p>
                          <p className="mt-1 text-[11px] text-muted">Built {formatDate(snapshot.completed_at || snapshot.created_at)}</p>
                        </div>
                        {selected && <Check className="h-4 w-4 shrink-0 text-primary-light" />}
                      </div>
                    </button>
                  )
                })}
                {readySnapshots.length === 0 && <div className="rounded-xl border border-border bg-background/50 p-6 text-center text-sm text-muted">This Collection has no READY vector snapshot yet. Build vectors in Knowledge first.</div>}
              </div>
            )}
          </>
        )}

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="button" disabled={!selectedSnapshot} onClick={() => selectedSnapshot && onSelect(selectedSnapshot)}>Apply</Button>
        </div>
      </div>
    </Dialog>
  )
}
