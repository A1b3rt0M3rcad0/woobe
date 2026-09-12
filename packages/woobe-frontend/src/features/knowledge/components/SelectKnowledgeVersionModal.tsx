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

interface SelectKnowledgeVersionModalProps { open: boolean; projectId: string; currentSnapshotId?: string | null; onClose: () => void; onSelect: (snapshot: VectorSnapshot) => void }

function formatDate(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date).replace(',', '')
}

export function SelectKnowledgeVersionModal({ open, projectId, currentSnapshotId, onClose, onSelect }: SelectKnowledgeVersionModalProps) {
  const { data: collections = [], isLoading: collectionsLoading } = useCollections(projectId)
  const [query, setQuery] = useState('')
  const [collectionId, setCollectionId] = useState<string | null>(null)
  const [snapshotId, setSnapshotId] = useState<string | null>(null)
  const { data: snapshots = [], isLoading: snapshotsLoading } = useVectorSnapshots(collectionId || undefined, projectId)

  useEffect(() => { if (open) { setQuery(''); setCollectionId(null); setSnapshotId(currentSnapshotId || null) } }, [open, currentSnapshotId])
  const normalizedQuery = query.trim().toLowerCase()
  const visibleCollections = useMemo(() => !normalizedQuery ? collections : collections.filter((collection) => `${collection.name} ${collection.description || ''}`.toLowerCase().includes(normalizedQuery)), [collections, normalizedQuery])
  const readySnapshots = useMemo(() => snapshots.filter((snapshot) => snapshot.status === 'READY'), [snapshots])
  const selectedSnapshot = readySnapshots.find((snapshot) => snapshot.id === snapshotId) || null
  const selectedCollection = collections.find((collection) => collection.id === collectionId) || null
  const selectingVersion = Boolean(collectionId)
  const chooseCollection = (collection: Collection) => { setCollectionId(collection.id); setSnapshotId(null) }
  const changeCollection = () => { setCollectionId(null); setSnapshotId(null) }

  return <Dialog open={open} onClose={onClose} title="Select knowledge" className="flex h-[min(760px,calc(100svh-2rem))] max-w-5xl flex-col overflow-hidden" contentClassName="min-h-0 flex-1 p-0">
    <div className="grid h-full min-h-0 grid-rows-[minmax(0,1fr)_58px]">
      <div className="grid min-h-0 lg:grid-cols-[240px_minmax(0,1fr)]">
        <aside className="border-b border-border bg-background/25 p-4 lg:border-b-0 lg:border-r">
          <section className="rounded-container border border-border bg-background/25 p-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-control border border-border bg-control text-primary-light"><Layers3 className="h-3.5 w-3.5" /></span>
            <p className="mt-3 font-mono text-[8px] uppercase tracking-[0.1em] text-muted-foreground">Knowledge binding</p>
            <h3 className="mt-1.5 font-mono text-[10px] font-bold text-slate-50">Choose exact version</h3>
            <p className="mt-1.5 font-sans text-[9px] leading-4 text-muted-foreground">Select a Collection, then bind one immutable READY vector version to the Agent Draft.</p>
            <div className="mt-4 divide-y divide-border/60 border-y border-border/60">
              <div className="flex min-h-[38px] items-center gap-2.5 py-2"><span className={`flex h-5 w-5 items-center justify-center rounded-technical border font-mono text-[8px] ${selectingVersion ? 'border-emerald-500/35 bg-emerald-500/[0.08] text-emerald-300' : 'border-primary/40 bg-primary/[0.08] text-primary-light'}`}>{selectingVersion ? <Check className="h-3 w-3" /> : '1'}</span><div><p className="font-mono text-[8px] font-semibold text-slate-100">Collection</p><p className="font-sans text-[8px] text-muted-foreground">Choose source.</p></div></div>
              <div className="flex min-h-[38px] items-center gap-2.5 py-2"><span className={`flex h-5 w-5 items-center justify-center rounded-technical border font-mono text-[8px] ${selectingVersion ? 'border-primary/40 bg-primary/[0.08] text-primary-light' : 'border-border bg-control text-muted-foreground'}`}>2</span><div><p className={`font-mono text-[8px] font-semibold ${selectingVersion ? 'text-slate-100' : 'text-muted-foreground'}`}>Version</p><p className="font-sans text-[8px] text-muted-foreground">Bind snapshot.</p></div></div>
            </div>
          </section>
          {selectedCollection ? <section className="mt-3 rounded-container border border-border bg-background/25 p-3"><p className="font-mono text-[8px] uppercase tracking-[0.1em] text-muted-foreground">Selected Collection</p><div className="mt-2.5 flex items-start gap-2.5"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control border border-border bg-control text-primary-light"><Database className="h-3.5 w-3.5" /></span><div className="min-w-0"><p className="truncate font-mono text-[9px] font-semibold text-slate-100">{selectedCollection.name}</p><p className="mt-1 font-mono text-[8px] text-muted-foreground">{selectedCollection.documents_count ?? 0} documents</p></div></div><Button type="button" size="sm" variant="outline" className="mt-3 w-full" onClick={changeCollection}>Change collection</Button></section> : null}
        </aside>

        <main className="scrollbar-thin min-h-0 overflow-y-auto p-4">
          {!selectingVersion ? <div className="space-y-4"><div><p className="font-mono text-[8px] uppercase tracking-[0.1em] text-primary-light">Step 1 / 2</p><h3 className="mt-1.5 font-mono text-[10px] font-bold text-slate-50">Choose a Collection</h3><p className="mt-1 font-sans text-[9px] leading-4 text-muted-foreground">Collections organize source documents used to build immutable vector versions.</p></div><div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search collections..." className="pl-9" /></div>{collectionsLoading ? <LoadingState variant="panel" layout="list" message="Loading collections..." /> : <div className="grid gap-2.5 sm:grid-cols-2">{visibleCollections.map((collection) => <button key={collection.id} type="button" onClick={() => chooseCollection(collection)} className="group min-h-[104px] rounded-container border border-border bg-background/25 p-3 text-left transition-colors hover:border-primary/35 hover:bg-control/25"><div className="flex items-start justify-between gap-3"><span className="flex h-7 w-7 items-center justify-center rounded-control border border-border bg-control text-primary-light"><Database className="h-3.5 w-3.5" /></span><ArrowRight className="h-3.5 w-3.5 text-muted-foreground group-hover:text-primary-light" /></div><p className="mt-2.5 truncate font-mono text-[9px] font-semibold text-slate-100">{collection.name}</p><p className="mt-1 line-clamp-2 font-sans text-[9px] leading-4 text-muted-foreground">{collection.description || 'No description provided'}</p><p className="mt-2 flex items-center gap-1 font-mono text-[8px] text-muted-foreground"><FileStack className="h-3 w-3" />{collection.documents_count ?? 0} documents</p></button>)}{visibleCollections.length === 0 ? <div className="rounded-container border border-dashed border-border bg-background/20 p-8 text-center font-sans text-[9px] text-muted-foreground sm:col-span-2">No collections found.</div> : null}</div>}</div>
          : <div className="space-y-4"><div><p className="font-mono text-[8px] uppercase tracking-[0.1em] text-primary-light">Step 2 / 2</p><h3 className="mt-1.5 font-mono text-[10px] font-bold text-slate-50">Choose immutable version</h3><p className="mt-1 font-sans text-[9px] leading-4 text-muted-foreground">Only READY vector snapshots can be bound to the Agent.</p></div>{snapshotsLoading ? <LoadingState variant="panel" layout="list" message="Loading vector versions..." /> : <div className="grid gap-2.5 sm:grid-cols-2">{readySnapshots.map((snapshot) => { const selected = snapshot.id === snapshotId; return <button key={snapshot.id} type="button" onClick={() => setSnapshotId(snapshot.id)} className={`min-h-[142px] rounded-container border p-3 text-left transition-colors ${selected ? 'border-primary/45 bg-primary/[0.07]' : 'border-border bg-background/25 hover:border-primary/30 hover:bg-control/25'}`}><div className="flex items-start justify-between gap-3"><div className="flex min-w-0 items-center gap-2"><span className="font-mono text-[9px] font-semibold text-slate-100">{snapshot.version}</span><StatusBadge status={snapshot.status} size="compact" /></div><span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-technical border ${selected ? 'border-primary/50 bg-primary/[0.10] text-primary-light' : 'border-border bg-control text-transparent'}`}><Check className="h-3 w-3" /></span></div><p className="mt-2 line-clamp-2 font-sans text-[9px] leading-4 text-muted-foreground">{snapshot.description || 'Immutable vector snapshot ready for Agent runtime.'}</p><div className="mt-3 grid grid-cols-2 gap-2 border-t border-border/60 pt-2.5"><div><p className="font-mono text-[7px] uppercase text-muted-foreground">Documents</p><p className="mt-1 font-mono text-[8px] text-slate-200">{snapshot.document_count}</p></div><div><p className="font-mono text-[7px] uppercase text-muted-foreground">Chunks</p><p className="mt-1 font-mono text-[8px] text-slate-200">{snapshot.chunk_count.toLocaleString()}</p></div></div><p className="mt-2 truncate font-mono text-[8px] text-muted-foreground">{snapshot.embedding_provider} · {snapshot.embedding_model}</p><p className="mt-1 font-mono text-[8px] text-muted-foreground">Built {formatDate(snapshot.completed_at || snapshot.created_at)}</p></button> })}{readySnapshots.length === 0 ? <div className="rounded-container border border-dashed border-border bg-background/20 p-8 text-center sm:col-span-2"><p className="font-mono text-[9px] font-semibold text-slate-100">No READY vector versions</p><p className="mt-1 font-sans text-[9px] leading-4 text-muted-foreground">Build vectors for this Collection before binding it to the Agent.</p></div> : null}</div>}</div>}
        </main>
      </div>
      <footer className="flex min-h-[58px] items-center justify-between gap-2 border-t border-border bg-surface/[0.98] px-4 py-3"><div>{selectingVersion ? <Button type="button" variant="ghost" onClick={changeCollection}>Back to collections</Button> : null}</div><div className="flex gap-2"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="button" disabled={!selectedSnapshot} onClick={() => selectedSnapshot && onSelect(selectedSnapshot)}>Apply knowledge</Button></div></footer>
    </div>
  </Dialog>
}
