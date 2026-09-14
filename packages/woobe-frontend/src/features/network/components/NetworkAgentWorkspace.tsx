import { useMemo, useState } from 'react'
import { Bot, Edit3, FileJson, GitBranch, Lock, MessageSquare, Rocket } from 'lucide-react'
import {
  Alert,
  AlertDescription,
  Badge,
  Button,
  EmptyStatePanel,
  SectionBlock,
  SegmentedControl,
  Skeleton,
  TechnicalListItem,
} from '@woobe/ui'

import { AgentBehaviorDetails } from '@/features/agents/components/AgentBehaviorDetails'
import { AgentConfigurationEditor } from '@/features/agents/components/AgentConfigurationEditor'
import { useRelease, useReleases } from '@/features/agents/hooks'
import type { Agent, AgentRelease, BehaviorSpecification } from '@/features/agents/types'
import { AgentEditorProvider, useAgentEditor } from '@/features/playground/AgentEditorContext'
import { JsonCodeBlock } from '@/components/ui/JsonCodeBlock'
import { cn } from '@/lib/utils'
import { NetworkAgentChat } from './NetworkAgentChat'
import { NetworkAgentVersions } from './NetworkAgentVersions'

type AgentWorkspaceTab = 'editor' | 'versions' | 'chat'
type SnapshotWorkspaceTab = 'snapshot' | 'versions'
type BindingSource = 'draft' | 'staging' | 'release'

export interface AgentNetworkBindingSummary {
  source: BindingSource
  version: string
  ref?: string
  snapshotOverride?: Record<string, unknown>
}

interface NetworkAgentWorkspaceProps {
  agent: Agent
  projectId: string
  networkBinding: AgentNetworkBindingSummary
  readOnly?: boolean
  onOpenComposition: () => void
  onDirtyChange?: (dirty: boolean) => void
  onRegisterSaveAction?: (action: (() => Promise<boolean>) | null) => void
}

function sourceLabel(source: BindingSource) {
  if (source === 'draft') return 'Draft'
  if (source === 'staging') return 'Staging'
  return 'Release'
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function stringValue(record: Record<string, unknown>, key: string): string | undefined {
  return typeof record[key] === 'string' ? record[key] as string : undefined
}

function numberValue(record: Record<string, unknown>, key: string): number | undefined {
  return typeof record[key] === 'number' ? record[key] as number : undefined
}

function capturedDraftRelease(agent: Agent, binding: AgentNetworkBindingSummary): AgentRelease | null {
  if (!binding.snapshotOverride) return null
  const snapshot = binding.snapshotOverride
  const responseFormat = recordValue(snapshot.response_format)
  const runtimeConfig = recordValue(snapshot.runtime_config)
  return {
    id: `captured-draft:${agent.id}`,
    project_id: agent.project_id,
    agent_id: agent.id,
    version: binding.version,
    status: 'archived',
    snapshot_kind: 'draft',
    name: stringValue(snapshot, 'name') ?? agent.name,
    description: stringValue(snapshot, 'description') ?? agent.description,
    behavior_spec: snapshot.behavior_spec as BehaviorSpecification | null | undefined,
    system_prompt: stringValue(snapshot, 'system_prompt'),
    response_format: Object.keys(responseFormat).length ? responseFormat : undefined,
    output_schema: recordValue(snapshot.output_schema),
    provider: stringValue(snapshot, 'provider'),
    model: stringValue(snapshot, 'model'),
    provider_credential_id: stringValue(snapshot, 'provider_credential_id'),
    provider_model_id: stringValue(snapshot, 'provider_model_id'),
    fallback_provider_model_id: stringValue(snapshot, 'fallback_provider_model_id'),
    fallback_provider: stringValue(snapshot, 'fallback_provider'),
    fallback_model: stringValue(snapshot, 'fallback_model'),
    fallback_credential_id: stringValue(snapshot, 'fallback_credential_id'),
    temperature: numberValue(snapshot, 'temperature'),
    max_output_tokens: numberValue(snapshot, 'max_output_tokens'),
    session_mode: stringValue(snapshot, 'session_mode'),
    knowledge_version_id: stringValue(snapshot, 'knowledge_version_id'),
    runtime_config: runtimeConfig,
  }
}

function agentFromRelease(agent: Agent, release: AgentRelease): Agent {
  return {
    ...agent,
    name: release.name ?? agent.name,
    description: release.description ?? agent.description,
    behavior_spec: release.behavior_spec ?? null,
    system_prompt: release.system_prompt ?? '',
    session_mode: release.session_mode ?? agent.session_mode,
    provider: release.provider ?? agent.provider,
    model: release.model ?? agent.model,
    provider_model_id: release.provider_model_id ?? agent.provider_model_id,
    fallback_provider_model_id: release.fallback_provider_model_id ?? agent.fallback_provider_model_id,
    provider_credential_id: release.provider_credential_id ?? agent.provider_credential_id,
    fallback_provider: release.fallback_provider ?? agent.fallback_provider,
    fallback_model: release.fallback_model ?? agent.fallback_model,
    fallback_credential_id: release.fallback_credential_id ?? agent.fallback_credential_id,
    temperature: release.temperature ?? agent.temperature,
    max_output_tokens: release.max_output_tokens ?? agent.max_output_tokens,
    settings: release.runtime_config ?? agent.settings,
  }
}

function SnapshotUnavailable({ message }: { message: string }) {
  return (
    <div className="flex h-full min-h-0 items-center justify-center p-ui-lg">
      <EmptyStatePanel
        icon={<Lock className="h-icon-lg w-icon-lg" />}
        title="Exact Agent snapshot unavailable"
        description={message}
      />
    </div>
  )
}

function WorkspaceHeader({
  agent,
  networkBinding,
  onOpenComposition,
  readOnly = false,
}: Pick<NetworkAgentWorkspaceProps, 'agent' | 'networkBinding' | 'onOpenComposition'> & { readOnly?: boolean }) {
  return (
    <div className="shrink-0 border-b border-border bg-background/20 px-ui-md py-ui-sm">
      <div className="flex min-w-0 items-center gap-ui-md">
        <span className="flex h-control-nav w-control-nav shrink-0 items-center justify-center rounded-control border border-primary/25 bg-primary/[0.08] text-primary-light">
          {readOnly ? <Lock className="h-icon w-icon" /> : <Bot className="h-icon w-icon" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-wrap items-center gap-ui-sm">
            <p className="min-w-0 flex-1 truncate font-mono text-system-heading font-semibold text-accent-foreground">{agent.name}</p>
            {readOnly ? <Badge variant="outline" size="compact">Read-only</Badge> : null}
          </div>
          <div className="mt-ui-xs flex min-w-0 flex-wrap items-center gap-x-ui-sm gap-y-ui-xs font-mono text-system-meta text-muted-foreground">
            <GitBranch className="h-icon-sm w-icon-sm shrink-0 text-primary-light" />
            <span className="truncate">
              {readOnly ? 'Exact' : 'Network uses'} {sourceLabel(networkBinding.source)}{' '}
              <span className="text-accent-foreground">{networkBinding.version}</span>
            </span>
            <Button type="button" variant="link" size="xs" className="ml-auto shrink-0" onClick={onOpenComposition}>
              Role in Network
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

function EditableAgentWorkspaceContent({ agent, projectId, networkBinding, onOpenComposition, onDirtyChange, onRegisterSaveAction }: NetworkAgentWorkspaceProps) {
  const [tab, setTab] = useState<AgentWorkspaceTab>('editor')
  const { loadedReleaseVersion, state } = useAgentEditor()
  const runtimeAgent = useMemo<Agent>(() => ({ ...agent, session_mode: state.sessionMode }), [agent, state.sessionMode])
  const bindingTitle = loadedReleaseVersion
    ? `Draft based on ${loadedReleaseVersion}. Editing it affects every context that uses this Agent Draft.`
    : 'Editing this shared Agent Draft may affect every context that uses it.'

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden bg-surface/75">
      <WorkspaceHeader agent={agent} networkBinding={networkBinding} onOpenComposition={onOpenComposition} />

      <div className="shrink-0 border-b border-border bg-surface/60 px-ui-sm py-ui-xs" title={bindingTitle}>
        <SegmentedControl
          items={[
            { value: 'editor', label: 'Editor', icon: <Edit3 className="h-icon-sm w-icon-sm" /> },
            { value: 'versions', label: 'Versions', icon: <Rocket className="h-icon-sm w-icon-sm" /> },
            { value: 'chat', label: 'Chat', icon: <MessageSquare className="h-icon-sm w-icon-sm" /> },
          ]}
          value={tab}
          onValueChange={(value) => setTab(value as AgentWorkspaceTab)}
          ariaLabel="Agent workspace"
          stretch
          size="compact"
        />
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden">
        <div className={cn('absolute inset-0', tab !== 'editor' && 'invisible pointer-events-none')} aria-hidden={tab !== 'editor'}>
          <AgentConfigurationEditor
            agent={agent}
            projectId={projectId}
            agentId={agent.id}
            onDirtyChange={onDirtyChange}
            onRegisterSaveAction={onRegisterSaveAction}
          />
        </div>
        <div className={cn('absolute inset-0', tab !== 'versions' && 'invisible pointer-events-none')} aria-hidden={tab !== 'versions'}>
          <NetworkAgentVersions agent={agent} projectId={projectId} networkBinding={networkBinding} onOpenComposition={onOpenComposition} />
        </div>
        <div className={cn('absolute inset-0', tab !== 'chat' && 'invisible pointer-events-none')} aria-hidden={tab !== 'chat'}>
          <NetworkAgentChat agent={runtimeAgent} projectId={projectId} onChatCompleted={() => undefined} />
        </div>
      </div>
    </div>
  )
}

function SnapshotField({ label, value, mono = false }: { label: string; value: string | number | null | undefined; mono?: boolean }) {
  const display = value == null || value === '' ? 'Not configured' : String(value)
  return (
    <TechnicalListItem
      label={label}
      description={display}
      className={mono ? '[&>span:nth-child(2)>span:nth-child(2)]:font-mono' : undefined}
      title={display}
    />
  )
}

function ReadOnlyAgentSnapshotContent({ agent, release, projectId, networkBinding, onOpenComposition }: NetworkAgentWorkspaceProps & { release: AgentRelease }) {
  const [tab, setTab] = useState<SnapshotWorkspaceTab>('snapshot')
  const showVersions = networkBinding.source !== 'draft'

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden bg-surface/75">
      <WorkspaceHeader agent={agent} networkBinding={{ ...networkBinding, version: release.version }} onOpenComposition={onOpenComposition} readOnly />

      {showVersions ? (
        <div className="shrink-0 border-b border-border bg-surface/60 px-ui-sm py-ui-xs">
          <SegmentedControl
            items={[
              { value: 'snapshot', label: 'Snapshot', icon: <FileJson className="h-icon-sm w-icon-sm" /> },
              { value: 'versions', label: 'Versions', icon: <Rocket className="h-icon-sm w-icon-sm" /> },
            ]}
            value={tab}
            onValueChange={(value) => setTab(value as SnapshotWorkspaceTab)}
            ariaLabel="Snapshot workspace"
            stretch
            size="compact"
          />
        </div>
      ) : null}

      <div className="min-h-0 flex-1 overflow-hidden">
        {tab === 'snapshot' || !showVersions ? (
          <div className="scrollbar-thin h-full overflow-y-auto p-ui-md">
            <div className="grid gap-ui-md">
              <Alert variant="info">
                <AlertDescription>
                  This is the exact Agent configuration captured by the Network. The isolated Chat is unavailable because it would execute the current Agent runtime rather than this snapshot.
                </AlertDescription>
              </Alert>

              <SectionBlock title="Captured configuration" description="Immutable values bound to this Network execution." density="compact">
                <div className="grid gap-ui-xs sm:grid-cols-2">
                  <SnapshotField label="Version" value={release.version} mono />
                  <SnapshotField label="Snapshot" value={networkBinding.source} />
                  <SnapshotField label="Session mode" value={release.session_mode} />
                  <SnapshotField label="Provider" value={release.provider} />
                  <SnapshotField label="Model" value={release.model} mono />
                  <SnapshotField label="Temperature" value={release.temperature} />
                  <SnapshotField label="Max output tokens" value={release.max_output_tokens} />
                  <SnapshotField label="Knowledge version" value={release.knowledge_version_id} mono />
                  <SnapshotField label="Provider model" value={release.provider_model_id} mono />
                </div>
              </SectionBlock>

              <SectionBlock title="Behavior" density="compact">
                <AgentBehaviorDetails behavior={release.behavior_spec} legacyPrompt={release.system_prompt} />
              </SectionBlock>

              <SectionBlock title="Output contract" density="compact">
                <JsonCodeBlock value={release.response_format ?? release.output_schema} actions={['copy', 'format', 'expand']} />
              </SectionBlock>

              <SectionBlock title="Runtime configuration" density="compact">
                <JsonCodeBlock value={release.runtime_config} actions={['copy', 'format', 'expand']} />
              </SectionBlock>
            </div>
          </div>
        ) : (
          <NetworkAgentVersions
            agent={agent}
            projectId={projectId}
            networkBinding={{ ...networkBinding, version: release.version, ref: release.id }}
            readOnly
            onOpenComposition={onOpenComposition}
          />
        )}
      </div>
    </div>
  )
}

export function NetworkAgentWorkspace(props: NetworkAgentWorkspaceProps) {
  const stableInspection = Boolean(props.readOnly && props.networkBinding.source !== 'draft')
  const exactReleaseQuery = useRelease(stableInspection ? props.agent.id : undefined, stableInspection ? props.networkBinding.ref : undefined)
  const releaseListQuery = useReleases(stableInspection && !props.networkBinding.ref ? props.agent.id : undefined)

  if (props.readOnly && props.networkBinding.source === 'draft') {
    const release = capturedDraftRelease(props.agent, props.networkBinding)
    if (!release) {
      return <SnapshotUnavailable message="The execution is immutable, but its captured Agent Draft payload is unavailable. The mutable current Agent is intentionally not substituted." />
    }
    const snapshotAgent = agentFromRelease(props.agent, release)
    return (
      <AgentEditorProvider key={`${props.agent.id}:${props.networkBinding.version}`} agent={snapshotAgent} projectId={props.projectId}>
        <ReadOnlyAgentSnapshotContent {...props} agent={snapshotAgent} release={release} readOnly />
      </AgentEditorProvider>
    )
  }

  if (stableInspection) {
    if (exactReleaseQuery.isLoading || releaseListQuery.isLoading) {
      return (
        <div className="flex h-full items-center justify-center p-ui-lg" aria-label="Loading exact Agent snapshot">
          <div className="grid w-full max-w-dialog-compact gap-ui-sm">
            <Skeleton className="h-control-row w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        </div>
      )
    }

    const release = exactReleaseQuery.data ?? releaseListQuery.data?.find((item) => item.version === props.networkBinding.version)
    if (!release) {
      return <SnapshotUnavailable message={`The Network references Agent snapshot ${props.networkBinding.version}, but it could not be loaded. The current Agent is intentionally not substituted.`} />
    }
    const snapshotAgent = agentFromRelease(props.agent, release)
    return (
      <AgentEditorProvider key={`${props.agent.id}:${release.id}`} agent={snapshotAgent} projectId={props.projectId}>
        <ReadOnlyAgentSnapshotContent
          {...props}
          agent={snapshotAgent}
          release={release}
          networkBinding={{ ...props.networkBinding, version: release.version, ref: release.id }}
          readOnly
        />
      </AgentEditorProvider>
    )
  }

  return (
    <AgentEditorProvider key={props.agent.id} agent={props.agent} projectId={props.projectId}>
      <EditableAgentWorkspaceContent {...props} />
    </AgentEditorProvider>
  )
}
