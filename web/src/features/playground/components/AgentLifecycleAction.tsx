import { useMemo, useState } from 'react'
import { RotateCcw, Rocket, Upload } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/Button'
import { useCreateRelease, usePromoteRelease, useReleases } from '@/features/agents/hooks'
import type { AgentRelease, RuntimeEnvironment } from '@/features/agents/types'
import { useAgentEditor } from '../AgentEditorContext'
import { ReleaseLibraryModal } from './ReleaseLibraryModal'
import { ReleaseSnapshotModal } from './ReleaseSnapshotModal'
import { StageDraftSnapshotModal } from './StageDraftSnapshotModal'
import { promotableReleases, sessionModeLabel } from './releasePresentation'

export function AgentLifecycleAction({
  agentId,
  projectId,
  environment,
  disabled = false,
}: {
  agentId: string
  projectId: string
  environment: RuntimeEnvironment
  disabled?: boolean
}) {
  const { data: releases = [] } = useReleases(agentId)
  const createRelease = useCreateRelease(agentId)
  const promoteRelease = usePromoteRelease(agentId)
  const { state, toSnapshot, isDirty } = useAgentEditor()
  const [stageOpen, setStageOpen] = useState(false)
  const [publishOpen, setPublishOpen] = useState(false)
  const [releaseDescription, setReleaseDescription] = useState('')
  const [rollbackLibraryOpen, setRollbackLibraryOpen] = useState(false)
  const [rollbackTarget, setRollbackTarget] = useState<AgentRelease | null>(null)

  const staging = useMemo(
    () => releases.find((release) => release.status === 'staging') ?? null,
    [releases],
  )
  const production = useMemo(
    () => releases.find((release) => release.status === 'production') ?? null,
    [releases],
  )
  const rollbackCandidates = useMemo(
    () => promotableReleases(releases).filter((release) => release.id !== production?.id),
    [production?.id, releases],
  )
  const pending = createRelease.isPending || promoteRelease.isPending
  const sessionModeChange = Boolean(
    staging
    && production
    && staging.session_mode
    && production.session_mode
    && staging.session_mode !== production.session_mode,
  )

  const stageDraft = async () => {
    if (isDirty) {
      toast.info('Save the Agent Draft before creating Staging')
      return
    }
    try {
      const draft = await createRelease.mutateAsync({
        project_id: projectId,
        agent_id: agentId,
        version: 'draft',
        ...toSnapshot(),
      } as any)
      const staged = await promoteRelease.mutateAsync({
        releaseId: draft.id,
        targetStatus: 'staging',
        copySnapshot: true,
      })
      setStageOpen(false)
      toast.success(`${staged.version} created as current Staging`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to promote Draft to Staging')
    }
  }

  const publishRelease = async () => {
    if (!staging) return
    try {
      const result = await promoteRelease.mutateAsync({
        releaseId: staging.id,
        targetStatus: 'production',
        copySnapshot: true,
        releaseNotes: releaseDescription.trim() || undefined,
      })
      setPublishOpen(false)
      setReleaseDescription('')
      toast.success(`${result.version} published to Agent Production`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to publish Agent Release')
    }
  }

  const rollbackProduction = async () => {
    if (!rollbackTarget) return
    try {
      await promoteRelease.mutateAsync({
        releaseId: rollbackTarget.id,
        targetStatus: 'production',
        copySnapshot: false,
        restoreExistingVersion: true,
      })
      toast.success(`${rollbackTarget.version} restored to Agent Production`)
      setRollbackTarget(null)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to rollback Agent Production')
    }
  }

  const actionDisabled = disabled || pending

  return (
    <>
      {environment === 'draft' ? (
        <Button
          size="sm"
          disabled={actionDisabled || isDirty}
          onClick={() => setStageOpen(true)}
          title={isDirty ? 'Save Draft before creating immutable Staging' : 'Create immutable Staging from the saved Agent Draft'}
          className="bg-primary text-white hover:bg-primary/90"
        >
          <Upload className="mr-1 h-3.5 w-3.5" />
          Stage Agent
        </Button>
      ) : environment === 'staging' ? (
        <Button
          size="sm"
          disabled={actionDisabled || !staging}
          onClick={() => setPublishOpen(true)}
          title={staging ? 'Publish current Staging as an immutable Production Release' : 'Create Staging before publishing'}
          className="bg-primary text-white hover:bg-primary/90"
        >
          <Rocket className="mr-1 h-3.5 w-3.5" />
          Publish Release
        </Button>
      ) : (
        <Button
          size="sm"
          disabled={actionDisabled || rollbackCandidates.length === 0}
          onClick={() => setRollbackLibraryOpen(true)}
          title={rollbackCandidates.length ? 'Restore a previous immutable Release to Production' : 'No previous Agent Release is available'}
          className="bg-primary text-white hover:bg-primary/90"
        >
          <RotateCcw className="mr-1 h-3.5 w-3.5" />
          Rollback
        </Button>
      )}

      <StageDraftSnapshotModal
        open={stageOpen}
        state={state}
        snapshot={toSnapshot()}
        currentStaging={staging}
        isConfirming={pending}
        onClose={() => setStageOpen(false)}
        onConfirm={() => void stageDraft()}
      />

      <ReleaseSnapshotModal
        open={publishOpen}
        title="Publish Agent Release?"
        description={sessionModeChange
          ? `Compatibility change: Session Mode will change from ${sessionModeLabel(production?.session_mode)} to ${sessionModeLabel(staging?.session_mode)}. The immutable Staging snapshot will be published to Production.`
          : 'Create an immutable Release from current Staging and activate that exact snapshot in Agent Production.'}
        release={staging}
        confirmLabel="Publish Release"
        isConfirming={pending}
        onConfirm={() => void publishRelease()}
        onClose={() => { setPublishOpen(false); setReleaseDescription('') }}
        releaseDescription={releaseDescription}
        onReleaseDescriptionChange={setReleaseDescription}
      />

      <ReleaseLibraryModal
        open={rollbackLibraryOpen}
        agentId={agentId}
        releases={rollbackCandidates}
        title="Rollback Agent Production"
        description="Choose an immutable historical Release to restore as the active Agent Production snapshot."
        actionLabel="Rollback"
        onClose={() => setRollbackLibraryOpen(false)}
        onDeploy={(release) => setRollbackTarget(release)}
      />

      <ReleaseSnapshotModal
        open={Boolean(rollbackTarget)}
        title="Rollback Agent Production?"
        description={`Restore ${rollbackTarget?.version ?? 'this Release'} as the active standalone Agent Production snapshot. Network Releases remain pinned to their stored Agent Release IDs.`}
        release={rollbackTarget}
        confirmLabel="Rollback"
        isConfirming={pending}
        onConfirm={() => void rollbackProduction()}
        onClose={() => setRollbackTarget(null)}
      />
    </>
  )
}
