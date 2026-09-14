import { useMemo, useState } from 'react'
import { ArrowRight, Eye, FileText, History, Package } from 'lucide-react'
import { toast } from 'sonner'
import { EmptyStatePanel, TechnicalListItem } from '@woobe/ui'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { getRelease } from '@/features/agents/api'
import { useReleaseActivations, useReleases } from '@/features/agents/hooks'
import type { AgentRelease, AgentReleaseActivation } from '@/features/agents/types'
import { useAgentEditor } from '../AgentEditorContext'
import { ProductionChangesModal } from './ProductionChangesModal'
import { ReleaseLibraryModal } from './ReleaseLibraryModal'
import { ReleaseSnapshotModal } from './ReleaseSnapshotModal'
import {
  activationLabel,
  describeReleaseChanges,
  formatReleaseDate,
  newestProductionChanges,
  promotableReleases,
} from './releasePresentation'

function SessionModeBadge({ mode }: { mode?: string }) {
  return <Badge variant="outline">{mode === 'stateful' ? 'Stateful' : mode === 'stateless' ? 'Stateless' : 'Mode unknown'}</Badge>
}

function SnapshotMeta({ release }: { release: AgentRelease }) {
  return (
    <span className="flex flex-wrap items-center gap-ui-xs">
      <span>{release.provider ?? '—'}/{release.model ?? '—'} · {formatReleaseDate(release.created_at)}</span>
      <SessionModeBadge mode={release.session_mode} />
    </span>
  )
}

function activationVariant(action: AgentReleaseActivation['action']) {
  if (action === 'rollback') return 'warning' as const
  if (action === 'deploy') return 'success' as const
  return 'secondary' as const
}

export function ReleaseTab({ agentId, projectId: _projectId }: { agentId: string; projectId: string }) {
  const { data: releases = [], isLoading } = useReleases(agentId)
  const { data: activations = [], isLoading: activationsLoading } = useReleaseActivations(agentId)
  const { state } = useAgentEditor()
  const [snapshot, setSnapshot] = useState<AgentRelease | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [releaseLibraryOpen, setReleaseLibraryOpen] = useState(false)
  const [productionChangesOpen, setProductionChangesOpen] = useState(false)
  const [initialProductionChange, setInitialProductionChange] = useState<AgentReleaseActivation | null>(null)

  const staging = useMemo(() => releases.find((item) => item.status === 'staging') ?? null, [releases])
  const production = useMemo(() => releases.find((item) => item.status === 'production') ?? null, [releases])
  const availableReleases = useMemo(() => promotableReleases(releases), [releases])
  const latestProductionChanges = useMemo(() => newestProductionChanges(activations), [activations])
  const visibleAvailableReleases = availableReleases.slice(0, 3)
  const visibleProductionChanges = latestProductionChanges.slice(0, 3)
  const releasesById = useMemo(() => new Map(releases.map((release) => [release.id, release])), [releases])

  const viewSnapshot = async (release: AgentRelease) => {
    setLoadingId(release.id)
    try {
      setSnapshot(await getRelease(agentId, release.id))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to load Agent Release')
    } finally {
      setLoadingId(null)
    }
  }

  const openProductionChange = (activation?: AgentReleaseActivation) => {
    setInitialProductionChange(activation ?? null)
    setProductionChangesOpen(true)
  }

  if (isLoading) {
    return <div className="space-y-ui-md p-ui-lg"><Skeleton className="h-5 w-32" /><Skeleton className="h-16 w-full" /><Skeleton className="h-20 w-full" /></div>
  }

  return (
    <div className="p-ui-md">
      <div className="pb-ui-md">
        <h2 className="font-mono text-system-heading font-semibold text-slate-50">Version history</h2>
        <p className="mt-ui-xs font-sans text-product-caption text-muted-foreground">Inspect mutable Draft state, immutable environments, Releases and Production changes.</p>
      </div>

      <section aria-label="Environment versions" className="space-y-ui-sm border-t border-border/80 pt-ui-md">
        <TechnicalListItem
          leading={<FileText className="h-3.5 w-3.5 text-primary-light" />}
          label="Current Draft"
          description={`${state.provider || '—'}/${state.model || '—'}`}
          meta={<SessionModeBadge mode={state.sessionMode} />}
          trailing={<Badge variant="outline">Mutable</Badge>}
        />

        {staging ? (
          <TechnicalListItem
            onClick={() => void viewSnapshot(staging)}
            leading={<span className="h-1.5 w-1.5 rounded-full bg-primary-light" />}
            label={<span className="flex items-center gap-ui-sm"><span>Staging</span><span className="text-muted-foreground">{staging.version}</span></span>}
            description="Immutable validation snapshot."
            meta={<SnapshotMeta release={staging} />}
            trailing={<Eye className={loadingId === staging.id ? 'h-3.5 w-3.5 animate-pulse text-primary-light' : 'h-3.5 w-3.5 text-muted-foreground'} />}
          />
        ) : <EmptyStatePanel compact title="No Staging snapshot" description="Stage the current Draft to create an immutable validation snapshot." />}

        {production ? (
          <TechnicalListItem
            onClick={() => void viewSnapshot(production)}
            leading={<span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />}
            label={<span className="flex items-center gap-ui-sm"><span>Production</span><span className="text-muted-foreground">{production.version}</span></span>}
            description="Active standalone Agent Production release."
            meta={<SnapshotMeta release={production} />}
            trailing={<Eye className={loadingId === production.id ? 'h-3.5 w-3.5 animate-pulse text-primary-light' : 'h-3.5 w-3.5 text-muted-foreground'} />}
          />
        ) : <EmptyStatePanel compact title="No Production release" description="Publish an immutable Release to activate standalone Production." />}
      </section>

      <section aria-label="Agent Releases" className="mt-ui-lg border-t border-border/80 pt-ui-lg">
        <div className="mb-ui-sm flex items-center justify-between gap-ui-md">
          <div className="flex items-center gap-ui-sm">
            <Package className="h-3.5 w-3.5 text-primary-light" />
            <h3 className="font-mono text-system-meta font-semibold uppercase tracking-[0.08em] text-muted-foreground">Releases</h3>
            <span className="font-mono text-system-meta text-muted-foreground">{availableReleases.length}</span>
          </div>
          {availableReleases.length ? <Button size="sm" variant="ghost" onClick={() => setReleaseLibraryOpen(true)}>View all</Button> : null}
        </div>
        {visibleAvailableReleases.length ? (
          <div className="space-y-ui-sm">
            {visibleAvailableReleases.map((release) => (
              <TechnicalListItem
                key={release.id}
                onClick={() => void viewSnapshot(release)}
                leading={<Package className="h-3.5 w-3.5 text-primary-light" />}
                label={release.version}
                description={release.release_notes || 'Immutable Agent Release'}
                meta={<SnapshotMeta release={release} />}
                trailing={<Eye className={loadingId === release.id ? 'h-3.5 w-3.5 animate-pulse text-primary-light' : 'h-3.5 w-3.5 text-muted-foreground'} />}
              />
            ))}
          </div>
        ) : <EmptyStatePanel compact title="No immutable Releases" description="Publish Staging to create the first Agent Release." />}
      </section>

      <section aria-label="Production history" className="mt-ui-lg border-t border-border/80 pt-ui-lg">
        <div className="mb-ui-sm flex items-center justify-between gap-ui-md">
          <div className="flex items-center gap-ui-sm">
            <History className="h-3.5 w-3.5 text-muted-foreground" />
            <h3 className="font-mono text-system-meta font-semibold uppercase tracking-[0.08em] text-muted-foreground">Production history</h3>
            <span className="font-mono text-system-meta text-muted-foreground">{latestProductionChanges.length}</span>
          </div>
          {latestProductionChanges.length ? <Button size="sm" variant="ghost" onClick={() => openProductionChange()}>View all</Button> : null}
        </div>
        {activationsLoading ? <Skeleton className="h-16 w-full" /> : visibleProductionChanges.length ? (
          <div className="space-y-ui-sm">
            {visibleProductionChanges.map((activation) => {
              const release = releasesById.get(activation.release_id) ?? null
              const previous = activation.previous_release_id ? releasesById.get(activation.previous_release_id) ?? null : null
              const summary = describeReleaseChanges(previous, release)[0]
              return (
                <TechnicalListItem
                  key={activation.id}
                  onClick={() => openProductionChange(activation)}
                  leading={<History className="h-3.5 w-3.5 text-muted-foreground" />}
                  label={<span className="flex items-center gap-ui-xs"><Badge variant={activationVariant(activation.action)}>{activationLabel(activation.action)}</Badge><span>{previous?.version ?? 'No Production'}</span><ArrowRight className="h-3 w-3 text-muted-foreground" /><span>{release?.version ?? activation.release_id.slice(0, 8)}</span></span>}
                  description={summary}
                  meta={formatReleaseDate(activation.created_at)}
                />
              )
            })}
          </div>
        ) : <EmptyStatePanel compact title="No Production changes" description="Deployment and rollback activity will appear here." />}
      </section>

      <ReleaseSnapshotModal open={Boolean(snapshot)} title="Agent Release details" description="Operational configuration stored for this immutable version." release={snapshot} onClose={() => setSnapshot(null)} />
      <ReleaseLibraryModal open={releaseLibraryOpen} agentId={agentId} releases={availableReleases} readOnly onClose={() => setReleaseLibraryOpen(false)} onDeploy={() => undefined} />
      <ProductionChangesModal open={productionChangesOpen} agentId={agentId} activations={latestProductionChanges} releases={releases} initialActivation={initialProductionChange} onClose={() => { setProductionChangesOpen(false); setInitialProductionChange(null) }} />
    </div>
  )
}
