import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Check, Database, FileStack, Layers3, Search } from 'lucide-react'
import {
  Badge,
  Button,
  Dialog,
  EmptyStatePanel,
  Input,
  SectionBlock,
  TechnicalListItem,
} from '@woobe/ui'

import { LoadingState } from '@/components/common/LoadingState'
import { StatusBadge } from '@/components/common/StatusBadge'
import { useCollections } from '@/features/knowledge/hooks'
import type { Collection, VectorSnapshot } from '@/features/knowledge/types'
import { useVectorSnapshots } from '@/features/knowledge/vectorHooks'

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

export function SelectKnowledgeVersionModal({
  open,
  projectId,
  currentSnapshotId,
  onClose,
  onSelect,
}: SelectKnowledgeVersionModalProps) {
  const { data: collections = [], isLoading: collectionsLoading } = useCollections(projectId)
  const [query, setQuery] = useState('')
  const [collectionId, setCollectionId] = useState<string | null>(null)
  const [snapshotId, setSnapshotId] = useState<string | null>(null)
  const { data: snapshots = [], isLoading: snapshotsLoading } = useVectorSnapshots(collectionId || undefined, projectId)

  useEffect(() => {
    if (open) {
      setQuery('')
      setCollectionId(null)
      setSnapshotId(currentSnapshotId || null)
    }
  }, [open, currentSnapshotId])

  const normalizedQuery = query.trim().toLowerCase()
  const visibleCollections = useMemo(
    () => !normalizedQuery
      ? collections
      : collections.filter((collection) => `${collection.name} ${collection.description || ''}`.toLowerCase().includes(normalizedQuery)),
    [collections, normalizedQuery],
  )
  const readySnapshots = useMemo(() => snapshots.filter((snapshot) => snapshot.status === 'READY'), [snapshots])
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
    <Dialog
      open={open}
      onClose={onClose}
      title="Select knowledge"
      className="flex max-h-dialog max-w-dialog-wide flex-col overflow-hidden"
      contentClassName="min-h-0 flex-1 p-0"
    >
      <div className="flex h-full min-h-0 flex-col">
        <div className="grid min-h-0 flex-1 lg:grid-cols-12">
          <aside className="border-b border-border bg-background/25 p-ui-md lg:col-span-4 lg:border-b-0 lg:border-r">
            <div className="grid gap-ui-md">
              <SectionBlock
                title="Choose exact version"
                eyebrow="Knowledge binding"
                description="Select a Collection, then bind one immutable READY vector version to the Agent Draft."
                density="compact"
                actions={<Layers3 className="h-icon w-icon text-primary-light" />}
              >
                <div className="grid gap-ui-xs">
                  <TechnicalListItem
                    label="1 · Collection"
                    description="Choose source."
                    selected={!selectingVersion}
                    trailing={selectingVersion ? <Badge variant="success" size="compact"><Check className="h-icon-sm w-icon-sm" />Done</Badge> : undefined}
                  />
                  <TechnicalListItem
                    label="2 · Version"
                    description="Bind snapshot."
                    selected={selectingVersion}
                    disabled={!selectingVersion}
                  />
                </div>
              </SectionBlock>

              {selectedCollection ? (
                <SectionBlock title="Selected Collection" density="compact">
                  <TechnicalListItem
                    label={selectedCollection.name}
                    description={`${selectedCollection.documents_count ?? 0} documents`}
                    leading={<Database className="h-icon w-icon text-primary-light" />}
                  />
                  <Button type="button" size="sm" variant="outline" className="mt-ui-sm w-full" onClick={changeCollection}>
                    Change collection
                  </Button>
                </SectionBlock>
              ) : null}
            </div>
          </aside>

          <main className="scrollbar-thin min-h-0 overflow-y-auto p-ui-lg lg:col-span-8">
            {!selectingVersion ? (
              <div className="grid gap-ui-md">
                <SectionBlock
                  title="Choose a Collection"
                  eyebrow="Step 1 / 2"
                  description="Collections organize source documents used to build immutable vector versions."
                  density="compact"
                />

                <div className="relative">
                  <Search className="pointer-events-none absolute left-ui-md top-1/2 h-icon w-icon -translate-y-1/2 text-muted-foreground" />
                  <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search collections..." className="pl-9" />
                </div>

                {collectionsLoading ? (
                  <LoadingState variant="panel" layout="list" message="Loading collections..." />
                ) : visibleCollections.length ? (
                  <div className="grid gap-ui-xs sm:grid-cols-2">
                    {visibleCollections.map((collection) => (
                      <TechnicalListItem
                        key={collection.id}
                        label={collection.name}
                        description={collection.description || 'No description provided'}
                        leading={(
                          <span className="flex h-control-sm w-control-sm items-center justify-center rounded-control border border-border bg-control text-primary-light">
                            <Database className="h-icon w-icon" />
                          </span>
                        )}
                        meta={<span className="flex items-center gap-ui-xs"><FileStack className="h-icon-sm w-icon-sm" />{collection.documents_count ?? 0} documents</span>}
                        trailing={<ArrowRight className="h-icon w-icon text-muted-foreground" />}
                        onClick={() => chooseCollection(collection)}
                      />
                    ))}
                  </div>
                ) : (
                  <EmptyStatePanel compact title="No collections found" description="Change the search or create a Collection first." />
                )}
              </div>
            ) : (
              <div className="grid gap-ui-md">
                <SectionBlock
                  title="Choose immutable version"
                  eyebrow="Step 2 / 2"
                  description="Only READY vector snapshots can be bound to the Agent."
                  density="compact"
                />

                {snapshotsLoading ? (
                  <LoadingState variant="panel" layout="list" message="Loading vector versions..." />
                ) : readySnapshots.length ? (
                  <div className="grid gap-ui-xs sm:grid-cols-2">
                    {readySnapshots.map((snapshot) => {
                      const selected = snapshot.id === snapshotId
                      return (
                        <TechnicalListItem
                          key={snapshot.id}
                          label={snapshot.version}
                          description={snapshot.description || 'Immutable vector snapshot ready for Agent runtime.'}
                          selected={selected}
                          leading={<StatusBadge status={snapshot.status} size="compact" />}
                          meta={(
                            <>
                              <span>{snapshot.document_count} documents</span>
                              <span>{snapshot.chunk_count.toLocaleString()} chunks</span>
                              <span>{snapshot.embedding_provider} · {snapshot.embedding_model}</span>
                              <span>Built {formatDate(snapshot.completed_at || snapshot.created_at)}</span>
                            </>
                          )}
                          trailing={selected ? <Check className="h-icon w-icon text-primary-light" /> : null}
                          onClick={() => setSnapshotId(snapshot.id)}
                        />
                      )
                    })}
                  </div>
                ) : (
                  <EmptyStatePanel
                    compact
                    title="No READY vector versions"
                    description="Build vectors for this Collection before binding it to the Agent."
                  />
                )}
              </div>
            )}
          </main>
        </div>

        <footer className="flex shrink-0 flex-col-reverse gap-ui-sm border-t border-border bg-surface/95 px-ui-lg py-ui-md sm:flex-row sm:items-center sm:justify-between">
          <div>{selectingVersion ? <Button type="button" variant="ghost" onClick={changeCollection}>Back to collections</Button> : null}</div>
          <div className="flex gap-ui-sm">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="button" disabled={!selectedSnapshot} onClick={() => selectedSnapshot && onSelect(selectedSnapshot)}>Apply knowledge</Button>
          </div>
        </footer>
      </div>
    </Dialog>
  )
}
