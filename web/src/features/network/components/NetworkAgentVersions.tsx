import { useMemo, useState, type ReactNode } from 'react'
import { Copy, Eye, GitBranch, History, Rocket, RotateCcw, Upload, X } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { getRelease } from '@/features/agents/api'
import { useCreateRelease, usePromoteRelease, useReleases, useRollbackRelease } from '@/features/agents/hooks'
import type { Agent, AgentRelease } from '@/features/agents/types'
import { releaseToEditorState, useAgentEditor } from '@/features/playground/AgentEditorContext'
import { cn } from '@/lib/utils'
import { AgentSnapshotDetails } from './AgentSnapshotDetails'
import type { AgentNetworkBindingSummary } from './NetworkAgentWorkspace'

interface NetworkAgentVersionsProps {
  agent: Agent
  projectId: string
  networkBinding: AgentNetworkBindingSummary
  readOnly?: boolean
  onOpenComposition: () => void
}

function formatDate(value?: string) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(date)
}

function statusTone(status: AgentRelease['status']) {
  if (status === 'production') return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
  if (status === 'staging') return 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300'
  if (status === 'rolled_back') return 'border-red-500/30 bg-red-500/10 text-red-300'
  return 'border-border bg-background/50 text-muted'
}

function SnapshotModal({ release, onClose }: { release: AgentRelease | null; onClose: () => void }) {
  if (!release) return null
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
      <div className="flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-border bg-surface shadow-2xl">
        <div className="flex shrink-0 items-start gap-3 border-b border-border p-4">
          <div className="min-w-0 flex-1">
            <p className="text-[9px] uppercase tracking-wider text-primary-light">Agent snapshot</p>
            <h2 className="mt-1 truncate text-sm font-semibold text-white">{release.name || 'Agent'} · {release.version}</h2>
            <p className="mt-1 text-[10px] text-muted">Read-only configuration preserved for this version.</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-md p-1 text-muted hover:bg-background hover:text-white"><X className="h-4 w-4" /></button>
        </div>
        <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain p-4">
          <AgentSnapshotDetails release={release} />
        </div>
      </div>
    </div>
  )
}

function VersionCard({ release, actions }: { release: AgentRelease; actions: ReactNode }) {
  return (
    <article className="rounded-lg border border-border/80 bg-background/35 p-2.5">
      <div className="flex items-start gap-2.5">
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-2">
            <p className="truncate font-mono text-[10px] font-medium text-white">{release.version}</p>
            <span className={cn('shrink-0 rounded border px-1.5 py-0.5 text-[8px] font-semibold uppercase', statusTone(release.status))}>{release.status}</span>
          </div>
          <p className="mt-1 truncate text-[9px] text-muted">{release.provider || '—'}/{release.model || '—'} · {formatDate(release.created_at)}</p>
          {release.release_notes && <p className="mt-1 line-clamp-2 text-[9px] leading-4 text-slate-300">{release.release_notes}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-1">{actions}</div>
      </div>
    </article>
  )
}

export function NetworkAgentVersions({ agent, projectId, networkBinding, readOnly = false, onOpenComposition }: NetworkAgentVersionsProps) {
  const { data: releases = [], isLoading } = useReleases(agent.id)
  const createRelease = useCreateRelease(agent.id)
  const promoteRelease = usePromoteRelease(agent.id)
  const rollbackRelease = useRollbackRelease(agent.id)
  const { state, setState, toSnapshot, setLoadedRelease } = useAgentEditor()
  const [snapshot, setSnapshot] = useState<AgentRelease | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [releaseNotes, setReleaseNotes] = useState('')

  const staging = useMemo(() => releases.find((release) => release.status === 'staging') || null, [releases])
  const production = useMemo(() => releases.find((release) => release.status === 'production') || null, [releases])
  const history = useMemo(() => releases.filter((release) => release.status === 'archived' || release.status === 'rolled_back').sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()), [releases])

  const viewRelease = async (release: AgentRelease) => {
    setLoadingId(release.id)
    try {
      setSnapshot(await getRelease(agent.id, release.id))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to load snapshot')
    } finally {
      setLoadingId(null)
    }
  }

  const stageDraft = async () => {
    if (readOnly) return
    try {
      const draft = await createRelease.mutateAsync({ project_id: projectId, agent_id: agent.id, version: 'draft', ...toSnapshot() } as any)
      await promoteRelease.mutateAsync({ releaseId: draft.id, targetStatus: 'staging', copySnapshot: true })
      toast.success('Agent Draft promoted to Staging')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to stage Agent Draft')
    }
  }

  const publishStaging = async () => {
    if (readOnly || !staging) return
    if (typeof window !== 'undefined' && !window.confirm(`Publish ${staging.version} to Production?`)) return
    try {
      await promoteRelease.mutateAsync({ releaseId: staging.id, targetStatus: 'production', copySnapshot: true, releaseNotes: releaseNotes.trim() || undefined })
      setReleaseNotes('')
      toast.success('Agent Release published')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to publish Agent Release')
    }
  }

  const loadIntoDraft = async (release: AgentRelease) => {
    if (readOnly) return
    if (typeof window !== 'undefined' && !window.confirm(`Load ${release.version} into the Agent Draft? Unsaved Draft changes will be replaced.`)) return
    setLoadingId(release.id)
    try {
      const details = await getRelease(agent.id, release.id)
      setState(releaseToEditorState(details, state))
      setLoadedRelease(details.id, details.version)
      toast.success(`${details.version} loaded into the Agent Draft`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to load Agent Release')
    } finally {
      setLoadingId(null)
    }
  }

  const rollback = async (release: AgentRelease) => {
    if (readOnly) return
    if (typeof window !== 'undefined' && !window.confirm(`Rollback Agent Production to ${release.version}?`)) return
    try {
      await rollbackRelease.mutateAsync({ releaseId: release.id })
      toast.success(`Agent Production rolled back to ${release.version}`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to rollback Agent Production')
    }
  }

  if (isLoading) return <div className="flex h-full items-center justify-center text-[10px] text-muted">Loading Agent versions…</div>

  const viewAction = (release: AgentRelease) => <button type="button" disabled={loadingId === release.id} onClick={() => void viewRelease(release)} className="rounded-md border border-border/80 p-1.5 text-muted hover:text-white" title="View exact snapshot"><Eye className="h-3 w-3" /></button>

  return (
    <div className="scrollbar-thin h-full min-h-0 overflow-y-auto overscroll-contain bg-background p-3">
      <div className="sticky top-0 z-10 mb-3 flex items-center gap-2 rounded-lg border border-primary/20 bg-surface/95 px-2.5 py-2 shadow-sm">
        <GitBranch className="h-3.5 w-3.5 shrink-0 text-primary-light" />
        <p className="min-w-0 flex-1 truncate text-[9px] text-white">Network uses <span className="font-medium capitalize">{networkBinding.source}</span> <span className="font-mono text-slate-300">{networkBinding.version}</span></p>
        <button type="button" onClick={onOpenComposition} className="shrink-0 text-[9px] font-medium text-primary-light hover:text-white">Role in Network</button>
      </div>

      {readOnly ? <div className="mb-3 rounded-lg border border-border bg-background/35 px-3 py-2 text-[9px] leading-4 text-muted">Inspection mode. Agent promotion, rollback and Draft replacement actions are disabled here.</div> : null}

      <div className="space-y-3">
        {!readOnly ? <section className="rounded-lg border border-border/80 bg-background/35 p-3">
          <div className="flex items-start gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface"><Upload className="h-3.5 w-3.5 text-primary-light" /></div>
            <div className="min-w-0 flex-1"><p className="text-[11px] font-medium text-white">Current Draft</p><p className="mt-0.5 text-[9px] text-muted">Mutable configuration · {state.provider || '—'}/{state.model || '—'}</p></div>
            <Button size="sm" className="h-7 px-2 text-[9px]" onClick={() => void stageDraft()} loading={createRelease.isPending || promoteRelease.isPending}>Stage</Button>
          </div>
        </section> : null}

        <section>
          <p className="mb-1.5 text-[9px] font-semibold uppercase tracking-wider text-muted">Staging</p>
          {staging ? (
            <div className="rounded-lg border border-indigo-500/25 bg-indigo-500/[0.045] p-2.5">
              <div className="flex items-start gap-2.5">
                <div className="min-w-0 flex-1"><p className="font-mono text-[10px] font-medium text-white">{staging.version}</p><p className="mt-1 text-[9px] text-muted">Exact validation snapshot · {formatDate(staging.created_at)}</p></div>
                {viewAction(staging)}
              </div>
              {!readOnly ? <div className="mt-2 flex gap-2"><input value={releaseNotes} onChange={(event) => setReleaseNotes(event.target.value)} placeholder="Release description" className="h-8 min-w-0 flex-1 rounded-md border border-border bg-background/60 px-2 text-[9px] text-white placeholder:text-muted outline-none focus:border-primary/40" /><Button size="sm" className="h-8 px-2 text-[9px]" onClick={() => void publishStaging()} loading={promoteRelease.isPending}><Rocket className="mr-1 h-3 w-3" />Publish</Button></div> : null}
            </div>
          ) : <div className="rounded-lg border border-dashed border-border p-3 text-[9px] text-muted">No Staging snapshot.</div>}
        </section>

        <section>
          <p className="mb-1.5 text-[9px] font-semibold uppercase tracking-wider text-muted">Production</p>
          {production ? <VersionCard release={production} actions={<>{viewAction(production)}{!readOnly ? <button type="button" disabled={loadingId === production.id} onClick={() => void loadIntoDraft(production)} className="rounded-md border border-border/80 p-1.5 text-muted hover:text-white" title="Copy to Draft"><Copy className="h-3 w-3" /></button> : null}</>} /> : <div className="rounded-lg border border-dashed border-border p-3 text-[9px] text-muted">No Production Release is active.</div>}
        </section>

        <section>
          <div className="mb-1.5 flex items-center gap-1.5"><History className="h-3 w-3 text-muted" /><p className="text-[9px] font-semibold uppercase tracking-wider text-muted">History</p></div>
          {history.length === 0 ? <div className="rounded-lg border border-dashed border-border p-3 text-[9px] text-muted">No historical Releases yet.</div> : <div className="space-y-1.5">{history.map((release) => <VersionCard key={release.id} release={release} actions={<>{viewAction(release)}{!readOnly ? <><button type="button" disabled={loadingId === release.id} onClick={() => void loadIntoDraft(release)} className="rounded-md border border-border/80 p-1.5 text-muted hover:text-white" title="Load into Draft"><Copy className="h-3 w-3" /></button><button type="button" onClick={() => void rollback(release)} className="rounded-md border border-emerald-500/25 p-1.5 text-emerald-400 hover:bg-emerald-500/10" title="Rollback"><RotateCcw className="h-3 w-3" /></button></> : null}</>} />)}</div>}
        </section>
      </div>

      <SnapshotModal release={snapshot} onClose={() => setSnapshot(null)} />
    </div>
  )
}
