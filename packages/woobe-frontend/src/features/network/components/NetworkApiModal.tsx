import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'

import type { RuntimeEnvironment } from '@/features/api-keys/types'
import { getNetwork, getNetworkVersions } from '@/features/network/api'
import type { NetworkVersion } from '@/features/network/types'
import {
  RuntimeApiReferenceModal,
  type RuntimeEnvironmentReference,
} from '@/features/runtime-reference/RuntimeApiReferenceModal'
import { workspaceProjectPath } from '@/lib/constants/routes'
import type { AgentNodeId, NetworkBinding } from './networkWorkspaceTypes'

type Props = {
  open: boolean
  onClose: () => void
  projectId: string
  networkId: string
  versionIds?: { staging?: string | null; production?: string | null }
  versions?: { staging: NetworkVersion | null; production: NetworkVersion | null }
  bindings: {
    staging: Record<AgentNodeId, NetworkBinding>
    production: Record<AgentNodeId, NetworkBinding>
  }
}

function outputExample(version: NetworkVersion | null): Record<string, unknown> | null {
  const contract = version?.public_output_contract
  if (!contract?.enabled) return null
  const properties = contract.schema?.properties
  if (!properties || typeof properties !== 'object') return {}
  return Object.fromEntries(Object.entries(properties).map(([name, raw]) => {
    const schema = raw && typeof raw === 'object' ? raw as Record<string, unknown> : {}
    const type = schema.type
    if (type === 'number') return [name, 0.91]
    if (type === 'integer') return [name, 1]
    if (type === 'boolean') return [name, true]
    if (type === 'array') return [name, []]
    if (type === 'object') return [name, {}]
    return [name, `<${name}>`]
  }))
}

export function NetworkApiModal({
  open,
  onClose,
  projectId,
  networkId,
  versionIds,
  versions,
  bindings,
}: Props) {
  const { workspaceId } = useParams<{ workspaceId?: string }>()
  const networkQuery = useQuery({
    queryKey: ['network', projectId, networkId, 'api-reference'],
    queryFn: () => getNetwork(projectId, networkId),
    enabled: Boolean(open && projectId && networkId),
  })
  const versionsQuery = useQuery({
    queryKey: ['network-versions', projectId, networkId, 'api-reference'],
    queryFn: () => getNetworkVersions(networkId, projectId),
    enabled: Boolean(open && networkId && projectId && !versions),
  })

  const resolvedVersions = useMemo(() => {
    if (versions) return versions
    const available = versionsQuery.data ?? []
    return {
      staging: available.find((item) => item.id === versionIds?.staging) ?? null,
      production: available.find((item) => item.id === versionIds?.production) ?? null,
    }
  }, [versionIds?.production, versionIds?.staging, versions, versionsQuery.data])

  const environments = useMemo(() => {
    return Object.fromEntries((['production', 'staging'] as RuntimeEnvironment[]).map((environment) => {
      const version = resolvedVersions[environment]
      const versionId = version?.id ?? versionIds?.[environment] ?? null
      const activeBindings = bindings[environment]
      const parsedOutput = outputExample(version)
      const response = {
        success: true,
        message: 'ok',
        data: {
          execution_id: '<uuid>',
          job_id: '<uuid>',
          session_id: '<uuid>',
          network_id: networkId,
          network_version_id: versionId ?? '<uuid>',
          status: 'completed',
          answer: parsedOutput ? JSON.stringify(parsedOutput) : '<network answer>',
          result: parsedOutput ?? '<network answer>',
          parsed_output: parsedOutput,
          output_parse_error: null,
          error: null,
          trace_id: '<uuid | null>',
          created_at: '<iso datetime>',
          started_at: '<iso datetime>',
          completed_at: '<iso datetime>',
        },
      }
      const streamEvents = {
        execution_started: {
          event: 'execution_started',
          data: {
            protocol_version: 1,
            sequence: 1,
            execution_id: '<uuid>',
            network_session_id: '<uuid>',
            invocation_id: '<uuid | null>',
            parent_invocation_id: null,
            node_id: '<uuid | null>',
            agent_id: '<uuid | null>',
            depth: 0,
            data: {},
            created_at: '<iso datetime>',
          },
        },
        agent_invocation_completed: {
          event: 'agent_invocation_completed',
          data: {
            protocol_version: 1,
            sequence: 2,
            execution_id: '<uuid>',
            network_session_id: '<uuid>',
            invocation_id: '<uuid>',
            parent_invocation_id: '<uuid | null>',
            node_id: '<uuid>',
            agent_id: '<uuid>',
            depth: 0,
            data: {
              trace_id: '<uuid | null>',
              provider: '<provider | null>',
              model: '<model | null>',
              output: parsedOutput ? JSON.stringify(parsedOutput) : '<agent answer>',
              parsed_output: parsedOutput,
              output_parse_error: null,
            },
            created_at: '<iso datetime>',
          },
        },
        network_result: {
          event: 'network_result',
          data: {
            protocol_version: 1,
            sequence: 3,
            execution_id: '<uuid>',
            network_session_id: '<uuid>',
            invocation_id: '<root invocation uuid>',
            data: {
              answer: response.data.answer,
              result: response.data.result,
              parsed_output: response.data.parsed_output,
              output_parse_error: null,
              result_type: parsedOutput ? 'structured' : 'text',
              trace_id: '<uuid | null>',
            },
            created_at: '<iso datetime>',
          },
        },
        execution_completed: {
          event: 'execution_completed',
          data: {
            protocol_version: 1,
            sequence: 4,
            execution_id: '<uuid>',
            network_session_id: '<uuid>',
            data: { trace_id: '<uuid | null>' },
            created_at: '<iso datetime>',
          },
        },
        heartbeat: {
          event: 'heartbeat',
          data: { protocol_version: 1, execution_id: '<uuid>' },
        },
      }
      const manifest = (version?.agent_release_manifest ?? Object.values(activeBindings).map((item) => ({
        node_id: item.nodeId,
        agent_id: item.agent.id,
        role: 'specialist' as const,
        release_version: item.version,
      }))).map((item) => ({
        id: item.node_id,
        name: activeBindings[item.node_id]?.agent.name ?? item.agent_id,
        version: item.release_version,
        role: item.role,
      }))
      const reference: RuntimeEnvironmentReference = {
        available: Boolean(versionId),
        version: version?.version ?? null,
        summary: [
          { label: 'Composition', value: version?.composition_hash?.slice(0, 12) ?? 'not deployed' },
          { label: 'Entry Agent', value: version?.entry_agent_release_version ?? 'not deployed' },
          { label: 'Session', value: version?.definition.settings.session_mode ?? 'stateful' },
        ],
        request: { message: 'Hello!' },
        requestWithSession: { message: 'Hello!', session_id: '<optional-uuid>' },
        response,
        streamEvents,
        outputContract: version?.public_output_contract ?? null,
        manifest,
        warning: null,
        note: `The Runtime Key remains bound to this Network and always resolves the active ${environment === 'production' ? 'Production' : 'Staging'} Release. A completed Run always contains a public answer or a valid structured result; empty model output fails explicitly.`,
      }
      return [environment, reference]
    })) as Record<RuntimeEnvironment, RuntimeEnvironmentReference>
  }, [bindings, networkId, resolvedVersions, versionIds?.production, versionIds?.staging])

  return (
    <RuntimeApiReferenceModal
      open={open}
      onClose={onClose}
      projectId={projectId}
      targetType="network"
      targetId={networkId}
      targetName={networkQuery.data?.name ?? 'Network'}
      manageKeysPath={workspaceProjectPath(workspaceId, projectId, 'api-keys')}
      environments={environments}
    />
  )
}
