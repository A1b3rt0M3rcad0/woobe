import { useMemo, useState } from 'react'
import { useCreateRelease, useDeleteRelease, usePromoteRelease, useReleases } from '@/features/agents/hooks'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { toast } from 'sonner'
import { Archive, CheckCircle2, Circle, FileText, Rocket, Save, AlertTriangle } from 'lucide-react'
import { useAgentEditor } from '../AgentEditorContext'
import { ConfirmVersionModal } from './ConfirmVersionModal'
import { ConfirmDeleteModal } from './ConfirmDeleteModal'
import type { AgentRelease, ReleaseStatus } from '@/features/agents/types'

const statusVariant: Record<ReleaseStatus, 'success' | 'warning' | 'secondary' | 'default' | 'destructive'> = {
  production: 'success',
  staging: 'warning',
  draft: 'secondary',
  archived: 'default',
  rolled_back: 'destructive',
}

function formatDate(value?: string) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

function applyReleaseToSnapshot(release: AgentRelease, current: any) {
  const responseFormat = release.response_format as any
  return {
    ...current,
    name: release.name ?? current.name,
    description: release.description ?? current.description,
    systemPrompt: release.system_prompt ?? current.systemPrompt,
    provider: release.provider ?? current.provider,
    model: release.model ?? current.model,
    providerCredentialId: release.provider_credential_id ?? current.providerCredentialId,
    fallbackProvider: release.fallback_provider ?? current.fallbackProvider,
    fallbackModel: release.fallback_model ?? current.fallbackModel,
    fallbackProviderCredentialId: release.fallback_credential_id ?? current.fallbackProviderCredentialId,
    baseUrl: release.base_url ?? current.baseUrl,
    temperature: release.temperature ?? current.temperature,
    maxOutputTokens: release.max_output_tokens ?? current.maxOutputTokens,
    sessionMode: (release.session_mode as 'stateful' | 'stateless') ?? current.sessionMode,
    status: (release.agent_status as 'active' | 'inactive') ?? current.status,
    collectionIds: release.collection_ids ?? current.collectionIds,
    runtimeConfig: release.runtime_config ?? current.runtimeConfig,
    responseFormat: {
      enabled: Boolean(responseFormat?.enabled ?? release.output_schema),
      type: responseFormat?.type === 'json' ? 'json' : 'text',
      strict: Boolean(responseFormat?.strict),
      schema: responseFormat?.schema ?? release.output_schema ?? null,
      repair_attempts: responseFormat?.repair_attempts,
    },
    outputSchema: release.output_schema ?? current.outputSchema,
  }
}

export function ReleaseTab({ agentId, projectId }: { agentId: string; projectId: string }) {
  const { data: releases, isLoading } = useReleases(agentId)
  const createRelease = useCreateRelease(agentId)
  const promoteRelease = usePromoteRelease(agentId)
  const deleteRelease = useDeleteRelease(agentId)
  const { state, setState, toSnapshot, setLoadedRelease, updateBaseline } = useAgentEditor()
  const [showVersionModal, setShowVersionModal] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<AgentRelease | null>(null)

  const draft = useMemo(() => releases?.find((item) => item.status === 'draft'), [releases])
  const staging = useMemo(() => releases?.find((item) => item.status === 'staging'), [releases])
  const production = useMemo(() => releases?.find((item) => item.status === 'production'), [releases])
  const sorted = useMemo(() => [...(releases ?? [])].sort((a, b) => new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime()), [releases])
  const lastRelease = sorted[0] ?? null

  async function saveDraft() {
    const snapshot = toSnapshot()
    const saved = await createRelease.mutateAsync({ project_id: projectId, agent_id: agentId, version: 'auto', change_kind: 'change', ...snapshot } as any)
    toast.success(`Draft ${saved.version} saved`)
    setShowVersionModal(false)
    return saved
  }

  async function promoteDraftToStaging() {
    try {
      const source = draft ?? await saveDraft()
      await promoteRelease.mutateAsync({ releaseId: source.id, targetStatus: 'staging', copySnapshot: true, changeKind: 'change' })
      toast.success('Draft promoted to staging')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to promote draft to staging')
    }
  }

  async function loadToStaging(release: AgentRelease) {
    try {
      await promoteRelease.mutateAsync({ releaseId: release.id, targetStatus: 'staging', copySnapshot: true, changeKind: 'change' })
      toast.success(`${release.version} loaded to staging`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to load to staging')
    }
  }

  async function deployProduction(release?: AgentRelease) {
    const source = release ?? staging
    if (!source) return toast.error('No staging release available')
    try {
      await promoteRelease.mutateAsync({ releaseId: source.id, targetStatus: 'production', copySnapshot: true, changeKind: 'change' })
      toast.success(`${source.version} deployed to production`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to deploy production')
    }
  }

  async function loadToDraft(release: AgentRelease) {
    try {
      await promoteRelease.mutateAsync({ releaseId: release.id, targetStatus: 'draft', copySnapshot: true, changeKind: 'change' })
      setState(applyReleaseToSnapshot(release, state))
      setLoadedRelease(null, null)
      updateBaseline()
      toast.success(`${release.version} loaded to draft`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to load to draft')
    }
  }

  async function loadForEditing(release: AgentRelease) {
    setState(applyReleaseToSnapshot(release, state))
    setLoadedRelease(release.id, release.version)
    toast.success(`${release.version} loaded for editing`)
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    await deleteRelease.mutateAsync({ releaseId: deleteTarget.id })
    toast.success(`${deleteTarget.version} deleted`)
    setDeleteTarget(null)
  }

  if (isLoading) return <div className="p-4 space-y-4"><Skeleton className="h-5 w-48" /><Skeleton className="h-32 w-full" /></div>

  return <div className="p-4 space-y-4">
    <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-4 space-y-3">
      <div className="flex items-center justify-between"><p className="text-xs font-semibold text-blue-300 uppercase">Draft</p><Badge variant="secondary">{draft?.version ?? 'Current Draft'}</Badge></div>
      <Button size="sm" onClick={() => setShowVersionModal(true)} className="w-full"><Save className="mr-1.5 h-4 w-4" />Save Draft</Button>
      <Button size="sm" variant="outline" onClick={promoteDraftToStaging} loading={promoteRelease.isPending || createRelease.isPending} className="w-full"><AlertTriangle className="mr-1.5 h-4 w-4" />Promote Draft to Staging</Button>
    </div>

    <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-4 space-y-3">
      <div className="flex items-center justify-between"><p className="text-xs font-semibold text-yellow-300 uppercase">Staging</p><Badge variant="warning">{staging?.version ?? 'No staging'}</Badge></div>
      <p className="text-[10px] text-muted">Consume this with API payload: execution_context=staging.</p>
      <Button size="sm" variant="outline" onClick={() => deployProduction()} disabled={!staging} loading={promoteRelease.isPending} className="w-full"><Rocket className="mr-1.5 h-4 w-4" />Deploy Staging to Production</Button>
    </div>

    {production && <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4 space-y-2"><div className="flex items-center justify-between"><p className="text-xs font-semibold text-emerald-300 uppercase">Production</p><Badge variant="success">{production.version}</Badge></div><p className="text-[10px] text-muted">Consume this with API payload: execution_context=production.</p></div>}

    <div className="space-y-2"><p className="text-xs font-semibold text-muted uppercase px-1">Versions {releases ? `(${releases.length})` : ''}</p>{sorted.map((release) => <div key={release.id} className="rounded-xl border border-border bg-surface p-4 space-y-3">
      <div className="flex items-start justify-between gap-2"><div className="flex items-center gap-2 min-w-0">{release.status === 'production' ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : release.status === 'staging' ? <AlertTriangle className="h-3.5 w-3.5 text-yellow-400" /> : <Circle className="h-3.5 w-3.5 text-blue-400" />}<div className="min-w-0"><p className="truncate font-semibold text-white">{release.version}</p><p className="text-[10px] text-muted">{formatDate(release.created_at)}</p></div></div><Badge variant={statusVariant[release.status]} className="capitalize">{release.status.replace('_', ' ')}</Badge></div>
      <div className="text-[11px] text-muted space-y-1"><p><FileText className="inline h-3 w-3 mr-1" />{release.name ?? 'Unnamed'}</p><p>Model: {release.provider}/{release.model ?? '—'}</p></div>
      <div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => loadForEditing(release)}>Load for editing</Button><Button size="sm" variant="outline" onClick={() => loadToDraft(release)}>Load to Draft</Button>{release.status !== 'staging' && <Button size="sm" variant="outline" onClick={() => loadToStaging(release)}>Load to Staging</Button>}{release.status !== 'production' && <Button size="sm" variant="outline" onClick={() => deployProduction(release)}>Deploy Production</Button>}{release.status !== 'production' && <Button size="sm" variant="ghost" className="text-red-400" onClick={() => setDeleteTarget(release)}><Archive className="mr-1 h-3 w-3" />Delete</Button>}</div>
    </div>)}</div>

    <ConfirmVersionModal open={showVersionModal} onClose={() => setShowVersionModal(false)} onConfirm={saveDraft} versionName="system-generated" currentSnapshot={toSnapshot()} lastRelease={lastRelease} hasUnsavedChanges={false} isPending={createRelease.isPending} />
    <ConfirmDeleteModal open={deleteTarget !== null} onClose={() => setDeleteTarget(null)} onConfirm={confirmDelete} versionName={deleteTarget?.version ?? ''} isPending={deleteRelease.isPending} />
  </div>
}
