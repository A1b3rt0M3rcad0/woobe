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
    isModifiedFromLoaded,
  } = useAgentEditor()

  const [loadingReleaseId, setLoadingReleaseId] = useState<string | null>(null)

  const productionRelease = useMemo(() => releases?.find(r => r.status === 'production'), [releases])

  const handleSaveVersion = async () => {
    try {
      const versionName = generateVersionName()
      const snapshot = toSnapshot()
      await createRelease.mutateAsync({
        project_id: projectId,
        agent_id: agentId,
        version: versionName,
        ...snapshot,
      } as any)
      toast.success(`Version ${versionName} saved`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save version')
    }
  }

  const handleLoadVersion = async (release: AgentRelease) => {
    setLoadingReleaseId(release.id)
    try {
      const newState = {
        name: release.name ?? state.name,
        description: release.description ?? state.description,
        systemPrompt: release.system_prompt ?? state.systemPrompt,
        responseFormat: {
          enabled: Boolean((release.response_format as any)?.enabled ?? (release.output_schema ? true : false)),
          type: ((release.response_format as any)?.type === 'json' ? 'json' : 'text') as 'text' | 'json',
          strict: Boolean((release.response_format as any)?.strict),
          schema: (release.response_format as any)?.schema ?? release.output_schema ?? null,
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
      }
      setState(newState)
      setLoadedRelease(release.id, release.version)
      toast.success(`Version ${release.version} loaded into editor`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load version')
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

  const handleDelete = async (release: AgentRelease) => {
    if (!window.confirm(`Delete version ${release.version}? This cannot be undone.`)) return
    try {
      await deleteRelease.mutateAsync({ releaseId: release.id })
      toast.success(`Version ${release.version} deleted`)
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
            {isModifiedFromLoaded && (
              <Badge variant="warning" className="text-[10px]">Modified</Badge>
            )}
          </div>
          {isModifiedFromLoaded && (
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
        onClick={handleSaveVersion}
        loading={isCreating}
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
                className={`rounded-xl border p-4 space-y-3 transition-colors ${
                  isProduction
                    ? 'border-emerald-500/30 bg-emerald-500/[0.03]'
                    : isLoaded
                      ? 'border-blue-500/30 bg-blue-500/[0.03]'
                      : 'border-border bg-surface'
                }`}
              >
                {/* Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {statusIcon[release.status]}
                    <span className="text-sm font-semibold">{release.version}</span>
                    <Badge variant={statusBadgeVariant[release.status]} className="text-[10px]">
                      {release.status}
                    </Badge>
                    {isLoaded && (
                      <Badge variant="secondary" className="text-[10px]">Loaded</Badge>
                    )}
                  </div>
                  <span className="text-[10px] text-muted">{formatDate(release.created_at)}</span>
                </div>

                {/* Config Summary */}
                <div className="text-[11px] space-y-1.5">
                  {release.name && (
                    <div className="flex items-center gap-1.5">
                      <span className="text-muted">Name:</span>
                      <span className="truncate">{release.name}</span>
                    </div>
                  )}
                  <div className="flex items-start gap-1.5">
                    <FileText className="h-3 w-3 text-muted shrink-0 mt-0.5" />
                    <span className="text-muted shrink-0">Prompt:</span>
                    <span className="truncate">{truncate(release.system_prompt, 80) || '—'}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Cpu className="h-3 w-3 text-muted shrink-0" />
                    <span className="text-muted shrink-0">Model:</span>
                    <span>{release.provider}/{release.model || '—'}</span>
                  </div>
                  <div className="flex items-start gap-1.5">
                    <GitBranch className="h-3 w-3 text-muted shrink-0 mt-0.5" />
                    <span className="text-muted shrink-0">Schema:</span>
                    <span className="truncate">{release.output_schema ? `JSON enabled · ${Object.keys(release.output_schema as object).length > 0 ? Object.keys((release.output_schema as Record<string, unknown>)?.properties || {}).length + ' fields' : 'schema set'}` : '—'}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <BookOpen className="h-3 w-3 text-muted shrink-0" />
                    <span className="text-muted">Knowledge:</span>
                    <span>{(release.collection_ids?.length || 0) > 0 ? `${release.collection_ids!.length} collections` : '—'}</span>
                  </div>
                  {release.temperature != null && (
                    <div className="flex items-center gap-1.5">
                      <span className="text-muted">Temp:</span>
                      <span>{release.temperature}</span>
                    </div>
                  )}
                  {release.session_mode && (
                    <div className="flex items-center gap-1.5">
                      <span className="text-muted">Session:</span>
                      <span>{release.session_mode}</span>
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 pt-1">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleLoadVersion(release)}
                    loading={loadingReleaseId === release.id}
                  >
                    Load
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
                  {release.status !== 'production' && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-red-400 hover:text-red-300 ml-auto"
                      onClick={() => handleDelete(release)}
                      loading={deleteRelease.isPending}
                    >
                      <Archive className="mr-1 h-3 w-3" />
                      Delete
                    </Button>
                  )}
                </div>

                {release.release_notes && (
                  <p className="text-[10px] text-muted italic border-t border-border pt-2 mt-1">
                    {release.release_notes}
                  </p>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
