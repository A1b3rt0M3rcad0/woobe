import { useMemo } from 'react'

import { useSelectedAgentEnvironment, selectionMessage } from '@/features/asac/environmentSelection'
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
  const production = useSelectedAgentEnvironment(projectId, agent.id, 'production', open)
  const staging = useSelectedAgentEnvironment(projectId, agent.id, 'staging', open)

  const environments = useMemo(() => {
    return Object.fromEntries((['production', 'staging'] as RuntimeSlot[]).map((slot) => {
      const selection = slot === 'production' ? production : staging
      const release = selection.snapshot
      const reference = buildApiReferenceForSlot({ slot, release })
      const sessionMode = release?.session_mode ?? 'unknown'
      const value: RuntimeEnvironmentReference = {
        available: selection.state === 'selected',
        selectionState: selection.state,
        observationLabel: release ? null : selectionMessage(selection, slot === 'production' ? 'Production' : 'Staging'),
        version: reference.release?.version ?? selection.snapshotId,
        summary: [
          { label: 'Provider', value: reference.release?.provider ?? 'unavailable' },
          { label: 'Model', value: reference.release?.model ?? 'unavailable' },
          { label: 'Session', value: sessionMode },
        ],
        request: reference.request,
        requestWithSession: sessionMode === 'stateless' ? null : reference.request_with_session,
        response: reference.sync_response_example,
        streamEvents: reference.stream_events,
        outputContract: reference.structured_output.enabled ? reference.structured_output : null,
        warning: release ? null : selectionMessage(selection, slot === 'production' ? 'Production' : 'Staging'),
        note: `This Runtime Key always resolves the current ${slot === 'production' ? 'Production' : 'Staging'} Agent Release. Existing Sessions keep their conversation context and follow the current environment Release on the next Run.`,
      }
      return [slot, value]
    })) as Record<RuntimeEnvironment, RuntimeEnvironmentReference>
  }, [production.state, production.snapshotId, production.snapshot, production.detailState, staging.state, staging.snapshotId, staging.snapshot, staging.detailState])

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
