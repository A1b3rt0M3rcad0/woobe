import { useMemo, useState } from 'react'
import { Database, Upload } from 'lucide-react'
import { StatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { CollectionDocumentUploadModal } from '@/features/knowledge/components/CollectionDocumentUploadModal'
import { CollectionVectorWorkspace } from '@/features/knowledge/components/CollectionVectorWorkspace'
import { useDocumentsByCollection } from '@/features/knowledge/hooks'
import { formatBytes } from '@/lib/formatters/bytes'
import type { Collection } from '@/features/knowledge/types'

interface CollectionDetailsModalProps { open: boolean; onClose: () => void; collection: Collection | null; projectId: string }
function isReady(status?: string) { return ['indexed', 'ready'].includes(status?.toLowerCase() || '') }

export function CollectionDetailsModal({ open, onClose, collection, projectId }: CollectionDetailsModalProps) {
  const [uploadOpen, setUploadOpen] = useState(false)
  const { data: documents, refetch } = useDocumentsByCollection(collection?.id)
  const items = documents ?? []
  const readyCount = useMemo(() => items.filter((document) => isReady(document.status)).length, [items])
  const totalSize = useMemo(() => items.reduce((sum, document) => sum + document.size_bytes, 0), [items])
  const uploaded = () => { setUploadOpen(false); void refetch() }

  return <><Dialog open={open && Boolean(collection)} onClose={onClose} title="Collection details" className="max-h-[calc(100svh-2rem)] max-w-5xl overflow-hidden">{collection && <div className="max-h-[calc(100svh-8rem)] overflow-y-auto pr-1"><div className="grid gap-5 lg:grid-cols-[220px_minmax(0,1fr)]"><aside className="rounded-xl border border-border/80 bg-background/70 p-4 lg:self-start"><div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-surface text-primary-light"><Database className="h-4 w-4" /></div><div className="mt-4 flex items-start justify-between gap-3"><h3 className="truncate text-sm font-semibold text-white">{collection.name}</h3>{collection.status && <StatusBadge status={collection.status} />}</div><p className="mt-2 line-clamp-4 text-sm leading-6 text-muted">{collection.description || 'No description provided'}</p><div className="mt-4 space-y-2 text-xs text-muted"><p>{items.length} documents</p><p>{readyCount} ready</p><p>{formatBytes(totalSize)}</p></div><Button type="button" variant="outline" size="sm" className="mt-4 w-full" onClick={() => setUploadOpen(true)}><Upload className="mr-2 h-3.5 w-3.5" />Upload</Button></aside><main><CollectionVectorWorkspace projectId={projectId} collection={collection} documentCount={items.length} readyDocumentCount={readyCount} onUploadDocument={() => setUploadOpen(true)} /></main></div><div className="mt-5 flex justify-end border-t border-border pt-4"><Button type="button" variant="outline" onClick={onClose}>Close</Button></div></div>}</Dialog><CollectionDocumentUploadModal open={uploadOpen} projectId={projectId} collection={collection ? { id: collection.id, name: collection.name } : null} onClose={() => setUploadOpen(false)} onUploaded={uploaded} /></>
}
