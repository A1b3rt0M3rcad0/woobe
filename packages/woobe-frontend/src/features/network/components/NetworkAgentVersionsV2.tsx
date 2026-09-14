import { useMemo, useState } from 'react'
import { ExternalLink, Eye, GitBranch, Package } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Badge, Button, Dialog, EmptyStatePanel, SectionBlock, TechnicalListItem } from '@woobe/ui'

import { LoadingState } from '@/components/common/LoadingState'
import { getRelease } from '@/features/agents/api'
import { useReleases } from '@/features/agents/hooks'
import type { Agent, AgentRelease } from '@/features/agents/types'
import { AgentSnapshotDetails } from './AgentSnapshotDetails'
import type { AgentNetworkBindingSummary } from './NetworkAgentWorkspace'

interface NetworkAgentVersionsProps {
  agent: Agent
  projectId: string
  networkBinding: AgentNetworkBindingSummary
  readOnly?: boolean
  onOpenComposition: () => void
}

function SnapshotModal({ release, onClose }: { release: AgentRelease | null; onClose: () => void }) {
  return (
    <Dialog
      open={Boolean(release)}
      onClose={onClose}
      title={release ? `${release.name || 'Agent'} · ${release.version}` : 'Agent snapshot'}
      className="max-w-dialog"
      scrollMode="content"
    >
      {release ? (
        <div className="space-y-ui-md">
          <p className="font-sans text-product-caption text-muted-foreground">
            Immutable Agent configuration. Viewing it does not change Agent or Network Production.
          </p>
          <AgentSnapshotDetails release={release} />
        </div>
      ) : null}
    </Dialog>
  )
}

function ReleaseRow({ release, label, onView, loading }: { release: AgentRelease; label: string; onView: () => void; loading: boolean }) {
  return (
    <TechnicalListItem
      leading={<Package className="h-icon w-icon text-primary-light" />}
      label={release.version}
      description={`${release.provider ?? '—'}/${release.model ?? '—'}`}
      meta={<Badge size="compact" variant="outline">{label}</Badge>}
      trailing={(
        <Button type="button" size="iconSm" variant="ghost" disabled={loading} onClick={onView} aria-label={`View ${release.version} snapshot`}>
          <Eye className="h-icon-sm w-icon-sm" />
        </Button>
      )}
    />
  )
}

function ReleaseEmpty({ children }: { children: string }) {
  return <EmptyStatePanel compact title={children} />
}

export function NetworkAgentVersions({ agent, projectId, networkBinding, onOpenComposition }: NetworkAgentVersionsProps) {
  const { workspaceId } = useParams<{ workspaceId?: string }>()
  const navigate = useNavigate()
  const { data: releases = [], isLoading } = useReleases(agent.id)
  const [snapshot, setSnapshot] = useState<AgentRelease | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const staging = useMemo(() => releases.find((release) => release.status === 'staging') ?? null, [releases])
  const production = useMemo(() => releases.find((release) => release.status === 'production') ?? null, [releases])
  const available = useMemo(() => releases.filter((release) => release.snapshot_kind === 'release' && release.status !== 'production'), [releases])

  const view = async (release: AgentRelease) => {
    setLoadingId(release.id)
    try {
      setSnapshot(await getRelease(agent.id, release.id))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to load Agent snapshot')
    } finally {
      setLoadingId(null)
    }
  }

  const openPlayground = () => {
    if (workspaceId) navigate(`/workspaces/${workspaceId}/projects/${projectId}/agents/${agent.id}/playground`)
    else navigate(`/projects/${projectId}/agents/${agent.id}/playground`)
  }

  if (isLoading) return <LoadingState variant="panel" layout="list" message="Loading Agent versions…" />

  return (
    <div className="scrollbar-thin h-full min-h-0 space-y-ui-md overflow-y-auto bg-background p-ui-md">
      <SectionBlock
        density="compact"
        eyebrow="Network binding"
        title={`${networkBinding.source} · ${networkBinding.version}`}
        description="This exact immutable binding belongs to the Network. Standalone Agent Production is managed only in the Agent Playground."
        actions={<GitBranch className="h-icon w-icon text-primary-light" />}
      >
        <div className="flex flex-wrap gap-ui-sm">
          <Button type="button" size="sm" variant="outline" onClick={onOpenComposition}>Role in Network</Button>
          <Button type="button" size="sm" variant="outline" onClick={openPlayground}>
            <ExternalLink className="mr-ui-xs h-icon-sm w-icon-sm" />
            Open Agent Playground
          </Button>
        </div>
      </SectionBlock>

      <SectionBlock density="compact" title="Agent Staging">
        {staging ? <ReleaseRow release={staging} label="Staging" loading={loadingId === staging.id} onView={() => void view(staging)} /> : <ReleaseEmpty>No Agent Staging snapshot.</ReleaseEmpty>}
      </SectionBlock>

      <SectionBlock density="compact" title="Available Agent Releases" actions={<Badge size="compact" variant="outline">{available.length}</Badge>}>
        {available.length ? (
          <div className="space-y-ui-sm">
            {available.map((release) => <ReleaseRow key={release.id} release={release} label="Available" loading={loadingId === release.id} onView={() => void view(release)} />)}
          </div>
        ) : <ReleaseEmpty>No available Agent Releases.</ReleaseEmpty>}
      </SectionBlock>

      <SectionBlock density="compact" title="Agent Playground Production" description="Network publish and rollback never change this standalone activation.">
        {production ? <ReleaseRow release={production} label="Standalone active" loading={loadingId === production.id} onView={() => void view(production)} /> : <ReleaseEmpty>No standalone Agent Production is active.</ReleaseEmpty>}
      </SectionBlock>

      <SnapshotModal release={snapshot} onClose={() => setSnapshot(null)} />
    </div>
  )
}
