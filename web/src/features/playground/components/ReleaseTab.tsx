import { useState, useMemo } from 'react'
import {
  useReleases, usePromoteRelease, useRollbackRelease,
  useCreateRelease, useDeleteRelease,
} from '@/features/agents/hooks'
import { useUpdateAgent } from '@/features/agents/hooks'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Skeleton } from '@/components/ui/Skeleton'
import { toast } from 'sonner'
import {
  Rocket, RotateCcw, Save, FileText, Cpu, BookOpen, GitBranch,
  Circle, CheckCircle2, Archive, AlertTriangle, Loader2,
} from 'lucide-react'
import { useAgentEditor } from '../AgentEditorContext'
import { ConfirmVersionModal } from './ConfirmVersionModal'
import { ConfirmDeleteModal } from './ConfirmDeleteModal'
import type { AgentRelease, ReleaseStatus } from '@/features/agents/types'

const statusBadgeVariant: Record<ReleaseStatus, 'success' | 'warning' | 'secondary' | 'default' | 'destructive'> = {
  production: 'success',
  staging: 'warning',
  draft: 'secondary',
  archived: 'default',
  rolled_back: 'destructive',
}

const statusIcon: Record<ReleaseStatus, React.ReactNode> = {
  production: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />,
  staging: <AlertTriangle className="h-3.5 w-3.5 text-yellow-400" />,
  draft: <Circle className="h-3.5 w-3.5 text-muted" />,
  archived: <Archive className="h-3.5 w-3.5 text-muted" />,
  rolled_back: <RotateCcw className="h-3.5 w-3.5 text-red-400" />,
}

function generateVersionName(): string {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  const hh = String(now.getHours()).padStart(2, '0')
  const mm = String(now.getMinutes()).padStart(2, '0')
  const rand = Math.random().toString(16).slice(2, 6)
  return `agent_${y}-${m}-${d}_${hh}${mm}_${rand}`
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function truncate(text: string | undefined | null, max: number): string {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '...' : text
}

function unwrapSchema(val: unknown): unknown {
  if (val && typeof val === 'object' && ('enabled' in (val as Record<string, unknown>) || 'type' in (val as Record<string, unknown>))) {
    return (val as Record<string, unknown>).schema ?? val
  }
  return val
}

interface ReleaseTabProps {
  agentId: string
  projectId: string
}

export function ReleaseTab({ agentId, projectId }: ReleaseTabProps) {
  const { data: releases, isLoading: releasesLoading } = useReleases(agentId)
  const promoteRelease = usePromoteRelease(agentId)
  const rollbackRelease = useRollbackRelease(agentId)
  const createRelease = useCreateRelease(agentId)
  const deleteRelease = useDeleteRelease(agentId)
  const updateAgent = useUpdateAgent(agentId)

  const {
    state, toSnapshot, setState,
    loadedReleaseId, loadedReleaseVersion, setLoadedRelease,
    isDirty, updateBaseline,
  } = useAgentEditor()

  const [loadingReleaseId, setLoadingReleaseId] = useState<string | null>(null)
  const [showVersionModal, setShowVersionModal] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<AgentRelease | null>(null)

  const productionRelease = useMemo(() => releases?.find(r => r.status === 'production'), [releases])

  const lastRelease = useMemo(() => {
    if (!releases || releases.length === 0) return null
    return releases.reduce((a, b) => {
      const aTime = a.created_at ? new Date(a.created_at).getTime() : 0
      const bTime = b.created_at ? new Date(b.created_at).getTime() : 0
      return aTime > bTime ? a : b
    })
  }, [releases])

  const pendingVersionName = useMemo(() => generateVersionName(), [showVersionModal])

  const handleSaveVersion = async () => {
    const versionName = pendingVersionName
    const snapshot = toSnapshot()
    try {
      await createRelease.mutateAsync({
        project_id: projectId,
        agent_id: agentId,
        version: versionName,
        ...snapshot,
      } as any)
      toast.success(`Version ${versionName} saved`)
      setShowVersionModal(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save version')
    }
  }

  const handleLoadVersionForEditing = async (release: AgentRelease) => {
    setLoadingReleaseId(release.id)
    try {
      const schema = unwrapSchema(release.output_schema)
      const newState = {
        name: release.name ?? state.name,
        description: release.description ?? state.description,
        systemPrompt: release.system_prompt ?? state.systemPrompt,
        responseFormat: {
          enabled: Boolean((release.response_format as any)?.enabled ?? (release.output_schema ? true : false)),
          type: ((release.response_format as any)?.type === 'json' ? 'json' : 'text') as 'text' | 'json',
          strict: Boolean((release.response_format as any)?.strict),
          schema: (release.response_format as any)?.schema ?? schema ?? null,
          repair_attempts: (release.response_format as any)?.repair_attempts,
        },
        outputSchema: release.output_schema ?? null,
        provider: release.provider ?? state.provider,
        model: release.model ?? state.model,
        providerCredentialId: release.provider_credential_id ?? state.providerCredentialId,
        baseUrl: release.base_url ?? state.baseUrl,
        temperature: release.temperature ?? state.temperature,
        maxOutputTokens: release.max_output_tokens ?? state.maxOutputTokens,
        sessionMode: (release.session_mode as 'stateful' | 'stateless') ?? state.sessionMode,
        status: (release.agent_status as 'active' | 'inactive') ?? state.status,
        collectionIds: (release.collection_ids as string[]) ?? state.collectionIds,
        runtimeConfig: (release.runtime_config as Record<string, unknown>) ?? state.runtimeConfig,
        fallbackProvider: release.fallback_provider ?? state.fallbackProvider,
        fallbackModel: release.fallback_model ?? state.fallbackModel,
        fallbackProviderCredentialId: release.fallback_credential_id ?? state.fallbackProviderCredentialId,
      }
      setState(newState)
      setLoadedRelease(release.id, release.version)
      toast.success(`Version ${release.version} loaded for editing`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load version')
    } finally {
      setLoadingReleaseId(null)
    }
  }

  const handleRestoreVersionAsCurrentDraft = async (release: AgentRelease) => {
    setLoadingReleaseId(release.id)
    try {
      const schema = unwrapSchema(release.output_schema)
      const newState = {
        name: release.name ?? state.name,
        description: release.description ?? state.description,
        systemPrompt: release.system_prompt ?? state.systemPrompt,
        responseFormat: {
          enabled: Boolean((release.response_format as any)?.enabled ?? (release.output_schema ? true : false)),
          type: ((release.response_format as any)?.type === 'json' ? 'json' : 'text') as 'text' | 'json',
          strict: Boolean((release.response_format as any)?.strict),
          schema: (release.response_format as any)?.schema ?? schema ?? null,
          repair_attempts: (release.response_format as any)?.repair_attempts,
        },
        outputSchema: release.output_schema ?? null,
        provider: release.provider ?? state.provider,
        model: release.model ?? state.model,
        providerCredentialId: release.provider_credential_id ?? state.providerCredentialId,
        baseUrl: release.base_url ?? state.baseUrl,
        temperature: release.temperature ?? state.temperature,
        maxOutputTokens: release.max_output_tokens ?? state.maxOutputTokens,
        sessionMode: (release.session_mode as 'stateful' | 'stateless') ?? state.sessionMode,
        status: (release.agent_status as 'active' | 'inactive') ?? state.status,
        collectionIds: (release.collection_ids as string[]) ?? state.collectionIds,
        runtimeConfig: (release.runtime_config as Record<string, unknown>) ?? state.runtimeConfig,
        fallbackProvider: release.fallback_provider ?? state.fallbackProvider,
        fallbackModel: release.fallback_model ?? state.fallbackModel,
        fallbackProviderCredentialId: release.fallback_credential_id ?? state.fallbackProviderCredentialId,
      }
      const rf = {
        enabled: newState.responseFormat.enabled,
        type: newState.responseFormat.type,
        strict: newState.responseFormat.strict,
        schema: newState.responseFormat.schema,
        repair_attempts: newState.responseFormat.repair_attempts,
      }
      const payload: Record<string, unknown> = {
        name: newState.name,
        description: newState.description,
        system_prompt: newState.systemPrompt,
        provider: newState.provider,
        model: newState.model,
        provider_credential_id: newState.providerCredentialId,
        temperature: newState.temperature,
        max_output_tokens: newState.maxOutputTokens,
        session_mode: newState.sessionMode,
        status: newState.status,
        settings: {
          response_format: rf,
          base_url: newState.baseUrl,
        },
      }
      await updateAgent.mutateAsync(payload as any)
      setState(newState)
      setLoadedRelease(null, null)
      updateBaseline()
      toast.success(`Version ${release.version} restored as Current Draft`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to restore version')
    } finally {
      setLoadingReleaseId(null)
    }
  }

  const handlePromote = async (release: AgentRelease) => {
    try {
      await promoteRelease.mutateAsync({ releaseId: release.id })
      toast.success(`Version ${release.version} deployed to production`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to deploy')
    }
  }

  const handleRollback = async (release: AgentRelease) => {
    try {
      await rollbackRelease.mutateAsync({ releaseId: release.id })
      toast.success(`Rolled back to ${release.version}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to rollback')
    }
  }

  const handleOpenDelete = (release: AgentRelease) => {
    setDeleteTarget(release)
  }

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteRelease.mutateAsync({ releaseId: deleteTarget.id })
      toast.success(`Version ${deleteTarget.version} deleted`)
      setDeleteTarget(null)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete version')
    }
  }

  const sortedReleases = useMemo(() => {
    if (!releases) return []
    return [...releases].sort((a, b) => {
      const aTime = a.created_at ? new Date(a.created_at).getTime() : 0
      const bTime = b.created_at ? new Date(b.created_at).getTime() : 0
      return bTime - aTime
    })
  }, [releases])

  const isCreating = createRelease.isPending || updateAgent.isPending

  if (releasesLoading) {
    return (
      <div className="p-4 space-y-4">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }

  return (
    <div className="p-4 space-y-4">
      {/* Loaded Version Indicator */}
      {loadedReleaseVersion && (
        <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-3 space-y-1">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 text-blue-400" />
              <span className="text-xs font-semibold text-blue-300">Loaded: {loadedReleaseVersion}</span>
            </div>
            {isDirty && (
              <Badge variant="warning" className="text-[10px]">Modified</Badge>
            )}
          </div>
          {isDirty && (
            <p className="text-[10px] text-muted">Modified from loaded version</p>
          )}
        </div>
      )}

      {/* Production Release Banner */}
      {productionRelease && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <p className="text-xs font-semibold text-emerald-300 uppercase tracking-wider">Production</p>
            </div>
            <Badge variant="success">{productionRelease.version}</Badge>
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[10px] text-muted">
            <span>Model: {productionRelease.provider}/{productionRelease.model || '—'}</span>
            <span>Deployed: {formatDate(productionRelease.promoted_at)}</span>
          </div>
        </div>
      )}

      {/* Save Version Button */}
      <Button
        size="sm"
        onClick={() => setShowVersionModal(true)}
        className="w-full"
      >
        <Save className="mr-1.5 h-4 w-4" />
        New Version
      </Button>

      {/* All Versions */}
      <div className="space-y-2">
        <p className="text-xs font-semibold text-muted uppercase tracking-wider px-1">
          Versions {releases ? `(${releases.length})` : ''}
        </p>

        {!sortedReleases || sortedReleases.length === 0 ? (
          <div className="rounded-xl border border-border bg-surface p-6 text-center">
            <Rocket className="h-8 w-8 text-muted mx-auto mb-2" />
            <p className="text-sm text-muted">No versions saved yet</p>
            <p className="text-xs text-muted mt-1">Save your first version to deploy to production.</p>
          </div>
        ) : (
          sortedReleases.map((release) => {
            const isProduction = release.status === 'production'
            const isLoaded = release.id === loadedReleaseId
            return (
              <div
                key={release.id}
                className={`rounded-xl border p-5 space-y-4 transition-colors ${
                  isProduction
                    ? 'border-emerald-500/40 bg-emerald-500/[0.04]'
                    : release.status === 'rolled_back'
                      ? 'border-red-500/20 bg-red-500/[0.02]'
                      : isLoaded
                        ? 'border-blue-500/30 bg-blue-500/[0.03]'
                        : 'border-border bg-surface'
                }`}
              >
                {/* Header */}
                <div className="grid grid-cols-[14px_1fr] gap-x-2 gap-y-2 min-w-0">
                  <div className="mt-0.5">{statusIcon[release.status]}</div>
                  <div className="flex items-center gap-2 min-w-0">
                    <h3 className="min-w-0 truncate font-semibold text-white leading-5">
                      {release.version}
                    </h3>
                    {isLoaded && (
                      <Badge variant="secondary" className="text-[10px] shrink-0">Loaded</Badge>
                    )}
                  </div>
                  <div aria-hidden="true" />
                  <div className="flex min-w-0 items-center gap-2 text-xs leading-none">
                    <Badge variant={statusBadgeVariant[release.status]} className="h-5 shrink-0 px-2 text-xs leading-none capitalize">
                      {release.status.replace('_', ' ')}
                    </Badge>
                    <span className="shrink-0 text-slate-600">·</span>
                    <span className="min-w-0 truncate whitespace-nowrap text-slate-500">
                      {formatDate(release.created_at)}
                    </span>
                  </div>
                </div>

                {/* Config Summary */}
                <div className="text-[11px] space-y-2.5">
                  {release.name && (
                    <div className="flex items-center gap-2">
                      <span className="text-muted">Name:</span>
                      <span className="truncate">{release.name}</span>
                    </div>
                  )}
                  <div className="flex items-start gap-2">
                    <FileText className="h-3 w-3 text-muted shrink-0 mt-0.5" />
                    <span className="text-muted shrink-0">Prompt:</span>
                    <span className="truncate">{truncate(release.system_prompt, 80) || '—'}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Cpu className="h-3 w-3 text-muted shrink-0" />
                    <span className="text-muted shrink-0">Model:</span>
                    <span>{release.provider}/{release.model || '—'}</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <GitBranch className="h-3 w-3 text-muted shrink-0 mt-0.5" />
                    <span className="text-muted shrink-0">Schema:</span>
                    <span className="truncate">{release.output_schema ? `JSON enabled · ${Object.keys(release.output_schema as object).length > 0 ? Object.keys((release.output_schema as Record<string, unknown>)?.properties || {}).length + ' fields' : 'schema set'}` : '—'}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <BookOpen className="h-3 w-3 text-muted shrink-0" />
                    <span className="text-muted">Knowledge:</span>
                    <span>{(release.collection_ids?.length || 0) > 0 ? `${release.collection_ids!.length} collections` : '—'}</span>
                  </div>
                  {(release.temperature != null || release.session_mode) && (
                    <div className="grid grid-cols-2 gap-x-4">
                      {release.temperature != null && (
                        <div className="flex items-center gap-2">
                          <span className="text-muted">Temp:</span>
                          <span>{release.temperature}</span>
                        </div>
                      )}
                      {release.session_mode && (
                        <div className="flex items-center gap-2">
                          <span className="text-muted">Session:</span>
                          <span>{release.session_mode}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex justify-between items-start flex-wrap gap-3 pt-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleLoadVersionForEditing(release)}
                      loading={loadingReleaseId === release.id}
                      disabled={loadingReleaseId === release.id}
                    >
                      <FileText className="mr-1 h-3 w-3" />
                      Load for editing
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleRestoreVersionAsCurrentDraft(release)}
                      loading={loadingReleaseId === release.id}
                      disabled={loadingReleaseId === release.id}
                    >
                      <Save className="mr-1 h-3 w-3" />
                      Restore as Current Draft
                    </Button>
                    {(release.status === 'draft' || release.status === 'staging') && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handlePromote(release)}
                        loading={promoteRelease.isPending}
                      >
                        <Rocket className="mr-1 h-3 w-3" />
                        Deploy
                      </Button>
                    )}
                    {release.status === 'production' && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleRollback(release)}
                        loading={rollbackRelease.isPending}
                      >
                        <RotateCcw className="mr-1 h-3 w-3" />
                        Rollback
                      </Button>
                    )}
                    {(release.status === 'archived' || release.status === 'rolled_back') && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleRollback(release)}
                        loading={rollbackRelease.isPending}
                      >
                        <RotateCcw className="mr-1 h-3 w-3" />
                        Rollback to this
                      </Button>
                    )}
                  </div>
                  {release.status !== 'production' && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-red-400 hover:text-red-300 shrink-0"
                      onClick={() => handleOpenDelete(release)}
                    >
                      <Archive className="mr-1 h-3 w-3" />
                      Delete
                    </Button>
                  )}
                </div>

                {release.release_notes && (
                  <p className="text-[10px] text-muted italic border-t border-border pt-3 mt-2">
                    {release.release_notes}
                  </p>
                )}
              </div>
            )
          })
        )}
      </div>

      <ConfirmVersionModal
        open={showVersionModal}
        onClose={() => setShowVersionModal(false)}
        onConfirm={handleSaveVersion}
        versionName={pendingVersionName}
        currentSnapshot={toSnapshot()}
        lastRelease={lastRelease}
        hasUnsavedChanges={isDirty}
        isPending={createRelease.isPending}
      />

      <ConfirmDeleteModal
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleConfirmDelete}
        versionName={deleteTarget?.version ?? ''}
        isPending={deleteRelease.isPending}
      />
    </div>
  )
}
