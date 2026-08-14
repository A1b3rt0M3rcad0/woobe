import { useMemo } from 'react'

import { useReleases } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'
import type { RuntimeEnvironment } from '@/features/api-keys/types'
import {
  RuntimeApiReferenceModal,
  type RuntimeEnvironmentReference,
} from '@/features/runtime-reference/RuntimeApiReferenceModal'
import {
  buildApiReferenceForSlot,
  type RuntimeSlot,
} from '../lib/api-reference-contracts'

interface ApiModalProps {
  open: boolean
  onClose: () => void
  agent: Agent
  workspaceProjectPathFn: (projId: string, ...segments: string[]) => string
  projectId: string
}

export function ApiModal({ open, onClose, agent, workspaceProjectPathFn, projectId }: ApiModalProps) {
  const { data: releases = [] } = useReleases(agent.id)

  const environments = useMemo(() => {
    return Object.fromEntries((['production', 'staging'] as RuntimeSlot[]).map((slot) => {
      const release = releases.find((item) => item.status === slot) ?? null
      const reference = buildApiReferenceForSlot({ slot, release })
      const sessionMode = agent.session_mode ?? 'stateful'
      const value: RuntimeEnvironmentReference = {
        available: reference.available,
        version: reference.release?.version ?? null,
        summary: [
          { label: 'Provider', value: reference.release?.provider ?? 'not deployed' },
          { label: 'Model', value: reference.release?.model ?? 'not deployed' },
          { label: 'Session', value: sessionMode },
        ],
        request: reference.request,
        requestWithSession: sessionMode === 'stateless' ? null : reference.request_with_session,
        response: reference.sync_response_example,
        streamEvents: reference.stream_events,
        outputContract: reference.structured_output.enabled ? reference.structured_output : null,
        warning: null,
        note: `This Runtime Key always resolves the current ${slot === 'production' ? 'Production' : 'Staging'} Agent Release. Existing Sessions keep their conversation context and follow the current environment Release on the next Run.`,
      }
      return [slot, value]
    })) as Record<RuntimeEnvironment, RuntimeEnvironmentReference>
  }, [agent.session_mode, releases])

  return (
    <RuntimeApiReferenceModal
      open={open}
      onClose={onClose}
      projectId={projectId}
      targetType="agent"
      targetId={agent.id}
      targetName={agent.name}
      manageKeysPath={workspaceProjectPathFn(projectId, 'api-keys')}
      environments={environments}
    />
  )
}
