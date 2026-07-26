import { useMemo } from 'react'
import { RotateCcw, Rocket, Upload } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { useReleases } from '@/features/agents/hooks'
import type { RuntimeEnvironment } from '@/features/agents/types'
import { useAgentEditor } from '../AgentEditorContext'
import type { AgentManagerMode, AgentManagerSection } from './AgentManagerModal'
import { promotableReleases } from './releasePresentation'

export function AgentLifecycleAction({
  agentId,
  environment,
  disabled = false,
  onManageAgent,
}: {
  agentId: string
  environment: RuntimeEnvironment
  disabled?: boolean
  onManageAgent: (section: AgentManagerSection, mode: AgentManagerMode) => void
}) {
  const { data: releases = [] } = useReleases(agentId)
  const { isDirty } = useAgentEditor()

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

  if (environment === 'draft') {
    return (
      <Button
        size="sm"
        disabled={disabled || isDirty}
        onClick={() => onManageAgent('draft', 'stage')}
        title={isDirty ? 'Save Draft before creating immutable Staging' : 'Review the saved Draft and create immutable Staging'}
        className="bg-primary text-white hover:bg-primary/90"
      >
        <Upload className="mr-1 h-3.5 w-3.5" />
        Stage Agent
      </Button>
    )
  }

  if (environment === 'staging') {
    return (
      <Button
        size="sm"
        disabled={disabled || !staging}
        onClick={() => onManageAgent('staging', 'publish')}
        title={staging ? 'Review current Staging and publish an immutable Release' : 'Create Staging before publishing'}
        className="bg-primary text-white hover:bg-primary/90"
      >
        <Rocket className="mr-1 h-3.5 w-3.5" />
        Publish Release
      </Button>
    )
  }

  return (
    <Button
      size="sm"
      disabled={disabled || rollbackCandidates.length === 0}
      onClick={() => onManageAgent('releases', 'rollback')}
      title={rollbackCandidates.length ? 'Choose a historical immutable Release to rollback to' : 'No previous Agent Release is available'}
      className="bg-primary text-white hover:bg-primary/90"
    >
      <RotateCcw className="mr-1 h-3.5 w-3.5" />
      Rollback
    </Button>
  )
}
