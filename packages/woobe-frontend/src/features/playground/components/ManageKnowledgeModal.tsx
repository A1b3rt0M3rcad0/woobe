import { useEffect, useMemo, useState } from 'react'
import { BookOpen, Database, Plus, Search } from 'lucide-react'
import {
  Badge,
  Button,
  Dialog,
  DialogContextBar,
  DialogFooter,
  EmptyStatePanel,
  Input,
  MetricTile,
  SectionBlock,
  Skeleton,
  TechnicalListItem,
} from '@woobe/ui'

import { StatusBadge } from '@/components/common/StatusBadge'
import { CollectionDetailsModal } from '@/features/knowledge/components/CollectionDetailsModalV2'
import { CreateCollectionModal } from '@/features/knowledge/components/CreateCollectionModal'
import { useCollections } from '@/features/knowledge/hooks'
import type { Collection, VectorSnapshot } from '@/features/knowledge/types'

interface ActiveKnowledgeBinding {
  collectionId: string | null
  collectionName: string
  knowledgeVersion: string
  vectorVersion: string
}

interface ManageKnowledgeModalProps {
  open: boolean
  projectId: string
  activeBinding: ActiveKnowledgeBinding | null
  currentSnapshotId?: string | null
  onClose: () => void
  onUseSnapshot: (snapshot: VectorSnapshot) => boolean | Promise<boolean>
}

export function ManageKnowledgeModal({
  open,
  projectId,
  activeBinding,
  currentSnapshotId,
  onClose,
  onUseSnapshot,
}: ManageKnowledgeModalProps) {
  const { data: collections = [], isLoading, refetch } = useCollections(projectId)
  const [query, setQuery] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [selectedCollection, setSelectedCollection] = useState<Collection | null>(null)

  useEffect(() => {
    if (!open) return
    setQuery('')
    setCreateOpen(false)
    setSelectedCollection(null)
  }, [open])

  const normalizedQuery = query.trim().toLowerCase()
  const visibleCollections = useMemo(() => {
    if (!normalizedQuery) return collections
    return collections.filter((collection) => (
      `${collection.name} ${collection.description || ''}`.toLowerCase().includes(normalizedQuery)
    ))
  }, [collections, normalizedQuery])

  const totalDocuments = useMemo(
    () => collections.reduce((sum, collection) => sum + (collection.documents_count ?? 0), 0),
    [collections],
  )
  const boundCollection = activeBinding?.collectionId
    ? collections.find((collection) => collection.id === activeBinding.collectionId) ?? null
    : null

  const handleCreated = (collection: Collection) => {
    setCreateOpen(false)
    setSelectedCollection(collection)
    void refetch()
  }

  const handleUseSnapshot = async (snapshot: VectorSnapshot) => {
    await onUseSnapshot(snapshot)
  }

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        title="Manage Knowledge"
        variant="workspace"
        height="workspace"
      >
        <div className="flex h-full min-h-0 flex-col">
          <DialogContextBar>
            <div className="grid gap-ui-md lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
              <TechnicalListItem
                label={activeBinding ? activeBinding.collectionName : 'No knowledge selected'}
                description={activeBinding
                  ? `Knowledge ${activeBinding.knowledgeVersion} · Vector ${activeBinding.vectorVersion}`
                  : 'Select an immutable READY vector snapshot to bind Knowledge to this Agent Draft.'}
                density="compact"
                leading={(
                  <span className="flex h-control-nav w-control-nav items-center justify-center rounded-control border border-primary/25 bg-primary/[0.08] text-primary-light">
                    <BookOpen className="h-icon w-icon" />
                  </span>
                )}
                meta={(
                  <>
                    <Badge variant={activeBinding ? 'success' : 'outline'} size="compact">
                      {activeBinding ? 'Current Agent binding' : 'Unbound'}
                    </Badge>
                    {currentSnapshotId ? <Badge variant="outline" size="compact">Snapshot bound</Badge> : null}
                  </>
                )}
              />

              <div className="grid grid-cols-2 gap-ui-xs sm:grid-cols-3">
                <MetricTile label="Collections" value={String(collections.length)} />
                <MetricTile label="Documents" value={String(totalDocuments)} />
                <MetricTile label="Binding" value={activeBinding ? 'Immutable' : 'None'} />
              </div>
            </div>
          </DialogContextBar>

          <main className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain p-ui-lg">
            <div className="mx-auto grid max-w-dialog-content gap-ui-md">
              <SectionBlock
                title="Knowledge sources"
                eyebrow="Collections"
                description="Collections organize source documents. Each Collection can produce immutable vector snapshots that Agents bind through Knowledge versions."
                density="compact"
                actions={(
                  <Button type="button" size="sm" onClick={() => setCreateOpen(true)}>
                    <Plus className="h-icon-sm w-icon-sm" />New collection
                  </Button>
                )}
              />

              <div className="relative">
                <Search className="pointer-events-none absolute left-ui-md top-1/2 h-icon w-icon -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search collections..."
                  className="pl-9"
                />
              </div>

              {isLoading ? (
                <div className="grid gap-ui-xs sm:grid-cols-2">
                  <Skeleton className="h-control-row w-full" />
                  <Skeleton className="h-control-row w-full" />
                  <Skeleton className="h-control-row w-full" />
                  <Skeleton className="h-control-row w-full" />
                </div>
              ) : visibleCollections.length === 0 ? (
                <EmptyStatePanel
                  icon={<Database className="h-icon-lg w-icon-lg" />}
                  title={normalizedQuery ? 'No Collections found' : 'No Collections yet'}
                  description={normalizedQuery ? 'Adjust the search term.' : 'Create the first Collection for this Project.'}
                  action={!normalizedQuery ? (
                    <Button type="button" size="sm" onClick={() => setCreateOpen(true)}>
                      <Plus className="h-icon-sm w-icon-sm" />New collection
                    </Button>
                  ) : undefined}
                />
              ) : (
                <div className="grid gap-ui-xs sm:grid-cols-2">
                  {visibleCollections.map((collection) => {
                    const isBound = activeBinding?.collectionId === collection.id
                    return (
                      <TechnicalListItem
                        key={collection.id}
                        label={collection.name}
                        description={collection.description || 'No description provided'}
                        density="compact"
                        selected={isBound}
                        leading={(
                          <span className="flex h-control-sm w-control-sm items-center justify-center rounded-control border border-border bg-control text-primary-light">
                            <Database className="h-icon w-icon" />
                          </span>
                        )}
                        meta={(
                          <>
                            <Badge variant="outline" size="compact">{collection.documents_count ?? 0} documents</Badge>
                            {collection.status ? <StatusBadge status={collection.status} size="compact" /> : null}
                            {isBound ? <Badge variant="success" size="compact">In use</Badge> : null}
                          </>
                        )}
                        onClick={() => setSelectedCollection(collection)}
                      />
                    )
                  })}
                </div>
              )}

              <SectionBlock
                title="How Agent Knowledge works"
                description="The Agent never points directly at mutable Collection contents in a release."
                density="compact"
              >
                <div className="grid gap-ui-xs sm:grid-cols-3">
                  <TechnicalListItem label="1 · Collection" description="Groups source documents inside the Project." />
                  <TechnicalListItem label="2 · Vector snapshot" description="Freezes documents, chunking and embedding output into an immutable build." />
                  <TechnicalListItem label="3 · Agent binding" description="The Agent Draft references that immutable version; Releases preserve the same binding." />
                </div>
              </SectionBlock>
            </div>
          </main>

          <DialogFooter
            meta={(
              <p className="font-sans text-product-caption text-muted-foreground">
                {boundCollection
                  ? `${boundCollection.name} is currently bound to this Agent Draft.`
                  : activeBinding
                    ? `${activeBinding.collectionName} is currently bound to this Agent Draft.`
                    : 'No Knowledge snapshot is currently bound to this Agent Draft.'}
              </p>
            )}
            actions={(
              <>
                <Button type="button" variant="outline" onClick={onClose}>Close</Button>
                <Button type="button" onClick={() => setCreateOpen(true)}>
                  <Plus className="h-icon-sm w-icon-sm" />New collection
                </Button>
              </>
            )}
          />
        </div>
      </Dialog>

      <CreateCollectionModal
        open={createOpen}
        projectId={projectId}
        onClose={() => setCreateOpen(false)}
        onCreated={handleCreated}
      />

      <CollectionDetailsModal
        open={Boolean(selectedCollection)}
        onClose={() => setSelectedCollection(null)}
        collection={selectedCollection}
        projectId={projectId}
        onUseSnapshot={(snapshot) => { void handleUseSnapshot(snapshot) }}
      />
    </>
  )
}
