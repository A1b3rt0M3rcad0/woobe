import { useMemo, useState } from 'react'
import { ExternalLink, Eye, GitBranch, Package } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

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
  if (!release) return null
  return <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/75 p-4"><div className="flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-border bg-surface"><header className="flex items-start gap-3 border-b border-border p-4"><div className="min-w-0 flex-1"><p className="text-[9px] uppercase tracking-wider text-primary-light">Agent snapshot</p><h2 className="mt-1 truncate text-sm font-semibold text-white">{release.name || 'Agent'} · {release.version}</h2><p className="mt-1 text-[9px] text-muted">Immutable configuration. Viewing it does not change Agent or Network Production.</p></div><button type="button" onClick={onClose} className="rounded-lg border border-border px-2 py-1 text-[9px] text-muted hover:text-white">Close</button></header><div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-4"><AgentSnapshotDetails release={release} /></div></div></div>
}

function ReleaseRow({ release, label, onView, loading }: { release: AgentRelease; label: string; onView: () => void; loading: boolean }) {
  return <article className="rounded-xl border border-border bg-background/35 p-3"><div className="flex items-start gap-3"><Package className="mt-0.5 h-4 w-4 text-primary-light" /><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><p className="truncate font-mono text-[10px] text-white">{release.version}</p><span className="rounded border border-border px-1.5 py-0.5 text-[8px] text-muted">{label}</span></div><p className="mt-1 truncate text-[9px] text-muted">{release.provider ?? '—'}/{release.model ?? '—'}</p></div><button type="button" disabled={loading} onClick={onView} className="rounded-lg border border-border p-2 text-muted hover:text-white disabled:opacity-45"><Eye className="h-3.5 w-3.5" /></button></div></article>
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
    try { setSnapshot(await getRelease(agent.id, release.id)) }
    catch (error) { toast.error(error instanceof Error ? error.message : 'Failed to load Agent snapshot') }
    finally { setLoadingId(null) }
  }

  const openPlayground = () => {
    if (workspaceId) navigate(`/workspaces/${workspaceId}/projects/${projectId}/agents/${agent.id}/playground`)
    else navigate(`/projects/${projectId}/agents/${agent.id}/playground`)
  }

  if (isLoading) return <div className="flex h-full items-center justify-center text-[10px] text-muted">Loading Agent versions…</div>

  return <div className="scrollbar-thin h-full min-h-0 space-y-4 overflow-y-auto bg-background p-3"><section className="rounded-xl border border-primary/25 bg-primary/[0.04] p-3"><div className="flex items-start gap-3"><GitBranch className="mt-0.5 h-4 w-4 text-primary-light" /><div className="min-w-0 flex-1"><p className="text-[9px] font-semibold uppercase tracking-wide text-muted">Used by this Network node</p><p className="mt-1 truncate text-[10px] text-white"><span className="capitalize">{networkBinding.source}</span> · <span className="font-mono">{networkBinding.version}</span></p><p className="mt-2 text-[9px] leading-4 text-muted">This exact binding belongs to the Network. Standalone Agent Production is managed only in the Agent Playground.</p></div></div><div className="mt-3 flex gap-2"><button type="button" onClick={onOpenComposition} className="rounded-lg border border-border px-2.5 py-2 text-[9px] text-primary-light hover:text-white">Role in Network</button><button type="button" onClick={openPlayground} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-2 text-[9px] text-primary-light hover:text-white"><ExternalLink className="h-3.5 w-3.5" />Open Agent Playground</button></div></section>

    <section><p className="mb-2 text-[9px] font-semibold uppercase tracking-wide text-muted">Agent Staging</p>{staging ? <ReleaseRow release={staging} label="Staging" loading={loadingId === staging.id} onView={() => void view(staging)} /> : <p className="rounded-xl border border-dashed border-border p-3 text-[9px] text-muted">No Agent Staging snapshot.</p>}</section>

    <section><div className="mb-2 flex items-center gap-2"><p className="text-[9px] font-semibold uppercase tracking-wide text-muted">Available Agent Releases</p><span className="rounded border border-border px-1.5 py-0.5 text-[8px] text-muted">{available.length}</span></div><div className="space-y-2">{available.length ? available.map((release) => <ReleaseRow key={release.id} release={release} label="Available" loading={loadingId === release.id} onView={() => void view(release)} />) : <p className="rounded-xl border border-dashed border-border p-3 text-[9px] text-muted">No available Agent Releases.</p>}</div></section>

    <section><p className="mb-2 text-[9px] font-semibold uppercase tracking-wide text-muted">Agent Playground Production</p>{production ? <ReleaseRow release={production} label="Standalone active" loading={loadingId === production.id} onView={() => void view(production)} /> : <p className="rounded-xl border border-dashed border-border p-3 text-[9px] text-muted">No standalone Agent Production is active.</p>}<p className="mt-2 text-[8px] leading-4 text-muted">Network publish and rollback never change this activation.</p></section>

    <SnapshotModal release={snapshot} onClose={() => setSnapshot(null)} />
  </div>
}
