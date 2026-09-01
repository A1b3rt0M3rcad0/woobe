import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Check, Database, FileStack, Layers3, Search } from 'lucide-react'
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
  const selectingVersion = Boolean(collectionId)

  const chooseCollection = (collection: Collection) => {
    setCollectionId(collection.id)
    setSnapshotId(null)
  }

  const changeCollection = () => {
    setCollectionId(null)
    setSnapshotId(null)
  }

  return (
    <Dialog open={open} onClose={onClose} title="Select knowledge" className="max-h-[calc(100svh-2rem)] max-w-5xl overflow-hidden">
      <div className="scrollbar-thin max-h-[calc(100svh-8rem)] overflow-y-auto pr-1">
        <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="space-y-4 lg:sticky lg:top-0 lg:self-start">
            <section className="rounded-xl border border-border/90 bg-surface/70 p-4">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-background text-primary-light">
                <Layers3 className="h-5 w-5" />
              </div>
              <div className="mt-5">
                <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Knowledge binding</p>
                <h3 className="mt-2 text-base font-semibold text-white">Choose the exact knowledge version</h3>
                <p className="mt-2 text-xs leading-5 text-muted">Select the Collection first, then bind one immutable READY vector version to the Agent Draft.</p>
              </div>

              <div className="mt-5 border-t border-border/70 pt-4">
                <div className="space-y-1">
                  <div className="flex items-start gap-3 rounded-lg bg-background/45 p-3">
                    <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${selectingVersion ? 'border-emerald-500/35 bg-emerald-500/10 text-emerald-300' : 'border-primary/45 bg-primary/10 text-primary-light'}`}>
                      {selectingVersion ? <Check className="h-3.5 w-3.5" /> : '1'}
                    </span>
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-white">Collection</p>
                      <p className="mt-1 text-[11px] leading-4 text-muted">Choose the knowledge source.</p>
                    </div>
                  </div>

                  <div className="ml-[13px] h-3 w-px bg-border" />

                  <div className={`flex items-start gap-3 rounded-lg p-3 ${selectingVersion ? 'bg-background/45' : ''}`}>
                    <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${selectingVersion ? 'border-primary/45 bg-primary/10 text-primary-light' : 'border-border bg-background text-muted'}`}>2</span>
                    <div className="min-w-0">
                      <p className={`text-xs font-medium ${selectingVersion ? 'text-white' : 'text-muted'}`}>Version</p>
                      <p className="mt-1 text-[11px] leading-4 text-muted">Select one immutable snapshot.</p>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {selectedCollection ? (
              <section className="rounded-xl border border-border/90 bg-background/60 p-4">
                <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted/75">Selected Collection</p>
                <div className="mt-3 flex items-start gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface text-primary-light">
                    <Database className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-white">{selectedCollection.name}</p>
                    <p className="mt-1 text-xs text-muted">{selectedCollection.documents_count ?? 0} documents</p>
                  </div>
                </div>
                <Button type="button" size="sm" variant="outline" className="mt-4 w-full" onClick={changeCollection}>Change collection</Button>
              </section>
            ) : (
              <section className="rounded-xl border border-border/90 bg-background/60 p-4">
                <p className="text-sm font-semibold text-white">Immutable by design</p>
                <p className="mt-1 text-xs leading-5 text-muted">The Agent stores the exact selected vector version. Later Collection changes do not mutate Staging or Production.</p>
              </section>
            )}
          </aside>

          <main className="min-w-0">
            {!selectingVersion ? (
              <div className="space-y-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-primary-light">Step 1 of 2</p>
                    <h3 className="mt-2 text-lg font-semibold text-white">Choose a Collection</h3>
                    <p className="mt-1 text-xs leading-5 text-muted">Collections organize the source documents used to build immutable vector versions.</p>
                  </div>
                  <span className="text-xs text-muted">{collections.length} available</span>
                </div>

                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
                  <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search collections..." className="pl-9" />
                </div>

                {collectionsLoading ? <LoadingState variant="panel" layout="list" message="Loading collections..." /> : (
                  <div className="grid max-h-[440px] gap-3 overflow-y-auto pr-1 sm:grid-cols-2">
                    {visibleCollections.map((collection) => (
                      <button key={collection.id} type="button" onClick={() => chooseCollection(collection)} className="group flex min-h-[132px] flex-col rounded-xl border border-border bg-background/60 p-4 text-left transition-colors hover:border-primary/35 hover:bg-surface/70">
                        <div className="flex items-start justify-between gap-3">
                          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-border bg-background text-primary-light">
                            <Database className="h-4 w-4" />
                          </span>
                          <ArrowRight className="h-4 w-4 text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-primary-light" />
                        </div>
                        <div className="mt-4 min-w-0">
                          <p className="truncate text-sm font-medium text-white">{collection.name}</p>
                          <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{collection.description || 'No description provided'}</p>
                        </div>
                        <div className="mt-auto flex items-center gap-2 pt-4 text-[11px] text-muted">
                          <FileStack className="h-3.5 w-3.5" />
                          <span>{collection.documents_count ?? 0} documents</span>
                        </div>
                      </button>
                    ))}
                    {visibleCollections.length === 0 && <div className="rounded-xl border border-border bg-background/50 p-8 text-center text-sm text-muted sm:col-span-2">No collections found.</div>}
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-primary-light">Step 2 of 2</p>
                    <h3 className="mt-2 text-lg font-semibold text-white">Choose an immutable version</h3>
                    <p className="mt-1 text-xs leading-5 text-muted">Only READY vector snapshots can be bound to the Agent.</p>
                  </div>
                  <span className="text-xs text-muted">{readySnapshots.length} ready</span>
                </div>

                <section className="rounded-xl border border-border/80 bg-surface/65 p-4">
                  <div className="flex items-start gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-border bg-background text-primary-light">
                      <Database className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted/75">Collection</p>
                      <p className="mt-1 truncate text-sm font-medium text-white">{selectedCollection?.name || 'Collection'}</p>
                      <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{selectedCollection?.description || 'No description provided'}</p>
                    </div>
                  </div>
                </section>

                {snapshotsLoading ? <LoadingState variant="panel" layout="list" message="Loading vector versions..." /> : (
                  <div className="grid max-h-[440px] gap-3 overflow-y-auto pr-1 sm:grid-cols-2">
                    {readySnapshots.map((snapshot) => {
                      const selected = snapshot.id === snapshotId
                      return (
                        <button key={snapshot.id} type="button" onClick={() => setSnapshotId(snapshot.id)} className={`relative min-h-[184px] rounded-xl border p-4 text-left transition-colors ${selected ? 'border-primary/55 bg-primary/10' : 'border-border bg-background/60 hover:border-primary/30 hover:bg-surface/70'}`}>
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex min-w-0 items-center gap-2">
                              <span className="font-mono text-sm font-semibold text-white">{snapshot.version}</span>
                              <StatusBadge status={snapshot.status} />
                            </div>
                            <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border ${selected ? 'border-primary/50 bg-primary/15 text-primary-light' : 'border-border bg-background text-transparent'}`}>
                              <Check className="h-3.5 w-3.5" />
                            </span>
                          </div>

                          <p className="mt-3 line-clamp-2 text-xs leading-5 text-muted">{snapshot.description || 'Immutable vector snapshot ready for Agent runtime.'}</p>

                          <div className="mt-4 grid grid-cols-2 gap-3 border-t border-border/70 pt-4 text-xs">
                            <div>
                              <p className="text-[10px] uppercase tracking-[0.14em] text-muted/70">Documents</p>
                              <p className="mt-1 text-white/90">{snapshot.document_count}</p>
                            </div>
                            <div>
                              <p className="text-[10px] uppercase tracking-[0.14em] text-muted/70">Chunks</p>
                              <p className="mt-1 text-white/90">{snapshot.chunk_count.toLocaleString()}</p>
                            </div>
                          </div>

                          <div className="mt-4 min-w-0 text-[11px] text-muted">
                            <p className="truncate">{snapshot.embedding_provider} · {snapshot.embedding_model}</p>
                            <p className="mt-1">Built {formatDate(snapshot.completed_at || snapshot.created_at)}</p>
                          </div>
                        </button>
                      )
                    })}
                    {readySnapshots.length === 0 && <div className="rounded-xl border border-border bg-background/50 p-8 text-center sm:col-span-2"><p className="text-sm font-medium text-white">No READY vector versions</p><p className="mt-1 text-xs leading-5 text-muted">Build vectors for this Collection in Knowledge before binding it to the Agent.</p></div>}
                  </div>
                )}
              </div>
            )}
          </main>
        </div>

        <div className="sticky bottom-0 -mx-1 mt-6 flex flex-col-reverse gap-2 border-t border-border bg-surface/95 px-1 py-4 backdrop-blur sm:flex-row sm:justify-between">
          <div>{selectingVersion && <Button type="button" variant="ghost" onClick={changeCollection}>Back to collections</Button>}</div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="button" disabled={!selectedSnapshot} onClick={() => selectedSnapshot && onSelect(selectedSnapshot)}>Apply knowledge</Button>
          </div>
        </div>
      </div>
    </Dialog>
  )
}
