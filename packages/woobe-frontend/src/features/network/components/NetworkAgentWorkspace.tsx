import { AgentBehaviorDetails } from '@/features/agents/components/AgentBehaviorDetails'
import { useMemo, useState } from 'react'
import { Bot, Edit3, FileJson, GitBranch, Lock, MessageSquare, Rocket } from 'lucide-react'

import { useRelease, useReleases } from '@/features/agents/hooks'
import type { Agent, AgentRelease, BehaviorSpecification } from '@/features/agents/types'
import { AgentEditorProvider, useAgentEditor } from '@/features/playground/AgentEditorContext'
import { cn } from '@/lib/utils'
import { NetworkAgentChat } from './NetworkAgentChat'
import { AgentConfigurationEditor } from '@/features/agents/components/AgentConfigurationEditor'
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
    <div className="flex h-full min-h-0 items-center justify-center p-6 text-center">
      <div className="max-w-sm rounded-2xl border border-amber-500/25 bg-amber-500/5 p-5">
        <p className="text-[11px] font-medium text-white">Exact Agent snapshot unavailable</p>
        <p className="mt-2 text-[9px] leading-5 text-muted">{message}</p>
      </div>
    </div>
  )
}

function EditableAgentWorkspaceContent({ agent, projectId, networkBinding, onOpenComposition, onDirtyChange, onRegisterSaveAction }: NetworkAgentWorkspaceProps) {
  const [tab, setTab] = useState<AgentWorkspaceTab>('editor')
  const { loadedReleaseVersion, state } = useAgentEditor()
  const runtimeAgent = useMemo<Agent>(() => ({ ...agent, session_mode: state.sessionMode }), [agent, state.sessionMode])
  const bindingTitle = loadedReleaseVersion ? `Draft based on ${loadedReleaseVersion}. Editing it affects every context that uses this Agent Draft.` : 'Editing this shared Agent Draft may affect every context that uses it.'

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden bg-surface/75">
      <div className="shrink-0 border-b border-border/80 bg-background/20 px-3 py-2.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary-light"><Bot className="h-3.5 w-3.5" /></div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[11px] font-semibold text-white">{agent.name}</p>
            <div className="mt-1 flex min-w-0 items-center gap-1.5 text-[8px] text-muted" title={bindingTitle}>
              <GitBranch className="h-3 w-3 shrink-0 text-primary-light" />
              <span className="truncate">Network uses <span className="text-white">{sourceLabel(networkBinding.source)}</span> <span className="font-mono text-slate-300">{networkBinding.version}</span></span>
              <button type="button" onClick={onOpenComposition} className="ml-auto shrink-0 font-medium text-primary-light hover:text-white">Role in Network</button>
            </div>
          </div>
        </div>
      </div>
      <div className="flex shrink-0 gap-1 border-b border-border/80 bg-surface/60 p-1.5">{([['editor', 'Editor', Edit3], ['versions', 'Versions', Rocket], ['chat', 'Chat', MessageSquare]] as Array<[AgentWorkspaceTab, string, typeof Edit3]>).map(([id, label, Icon]) => <button key={id} type="button" onClick={() => setTab(id)} className={cn('flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-2 py-1.5 text-[10px] font-medium', tab === id ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/70 hover:text-white')}><Icon className="h-3.5 w-3.5" />{label}</button>)}</div>
      <div className="relative min-h-0 flex-1 overflow-hidden">
        <div className={cn('absolute inset-0', tab !== 'editor' && 'invisible pointer-events-none')} aria-hidden={tab !== 'editor'}><AgentConfigurationEditor agent={agent} projectId={projectId} agentId={agent.id} onDirtyChange={onDirtyChange} onRegisterSaveAction={onRegisterSaveAction} /></div>
        <div className={cn('absolute inset-0', tab !== 'versions' && 'invisible pointer-events-none')} aria-hidden={tab !== 'versions'}><NetworkAgentVersions agent={agent} projectId={projectId} networkBinding={networkBinding} onOpenComposition={onOpenComposition} /></div>
        <div className={cn('absolute inset-0', tab !== 'chat' && 'invisible pointer-events-none')} aria-hidden={tab !== 'chat'}><NetworkAgentChat agent={runtimeAgent} projectId={projectId} onChatCompleted={() => undefined} /></div>
      </div>
    </div>
  )
}

function SnapshotField({ label, value, mono = false }: { label: string; value: string | number | null | undefined; mono?: boolean }) {
  return <div className="rounded-lg border border-border/75 bg-background/35 p-3"><p className="text-[8px] font-semibold uppercase tracking-wide text-muted">{label}</p><p className={cn('mt-1 break-words text-[10px] text-slate-200', mono && 'font-mono')}>{value == null || value === '' ? 'Not configured' : String(value)}</p></div>
}

function JsonSnapshot({ label, value }: { label: string; value: unknown }) {
  return <section><p className="mb-1.5 text-[9px] font-semibold uppercase tracking-wide text-muted">{label}</p><pre className="max-h-72 overflow-auto rounded-xl border border-border/75 bg-background/45 p-3 text-[9px] leading-5 text-slate-300">{JSON.stringify(value ?? null, null, 2)}</pre></section>
}

function ReadOnlyAgentSnapshotContent({ agent, release, projectId, networkBinding, onOpenComposition }: NetworkAgentWorkspaceProps & { release: AgentRelease }) {
  const [tab, setTab] = useState<SnapshotWorkspaceTab>('snapshot')
  const showVersions = networkBinding.source !== 'draft'
  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden bg-surface/75">
      <div className="shrink-0 border-b border-border/80 bg-background/20 px-3 py-2.5"><div className="flex items-center gap-2.5"><div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary-light"><Lock className="h-3.5 w-3.5" /></div><div className="min-w-0 flex-1"><div className="flex min-w-0 items-center gap-2"><p className="truncate text-[11px] font-semibold text-white">{agent.name}</p><span className="rounded border border-border bg-background/50 px-1.5 py-0.5 text-[8px] font-semibold uppercase text-muted">Read-only</span></div><div className="mt-1 flex min-w-0 items-center gap-1.5 text-[8px] text-muted"><GitBranch className="h-3 w-3 shrink-0 text-primary-light" /><span className="truncate">Exact {sourceLabel(networkBinding.source)} snapshot <span className="font-mono text-slate-300">{release.version}</span></span><button type="button" onClick={onOpenComposition} className="ml-auto shrink-0 font-medium text-primary-light hover:text-white">Role in Network</button></div></div></div></div>
      {showVersions ? <div className="flex shrink-0 gap-1 border-b border-border/80 bg-surface/60 p-1.5">{([['snapshot', 'Snapshot', FileJson], ['versions', 'Versions', Rocket]] as Array<[SnapshotWorkspaceTab, string, typeof FileJson]>).map(([id, label, Icon]) => <button key={id} type="button" onClick={() => setTab(id)} className={cn('flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-2 py-1.5 text-[10px] font-medium', tab === id ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/70 hover:text-white')}><Icon className="h-3.5 w-3.5" />{label}</button>)}</div> : null}
      <div className="min-h-0 flex-1 overflow-hidden">{tab === 'snapshot' || !showVersions ? <div className="scrollbar-thin h-full overflow-y-auto p-4"><div className="mb-4 rounded-xl border border-border bg-background/35 p-3 text-[9px] leading-4 text-muted">This is the exact Agent configuration captured by the Network. The isolated Chat is unavailable because it would execute the current Agent runtime rather than this snapshot.</div><div className="grid grid-cols-2 gap-2"><SnapshotField label="Version" value={release.version} mono /><SnapshotField label="Snapshot" value={networkBinding.source} /><SnapshotField label="Session mode" value={release.session_mode} /><SnapshotField label="Provider" value={release.provider} /><SnapshotField label="Model" value={release.model} mono /><SnapshotField label="Temperature" value={release.temperature} /><SnapshotField label="Max output tokens" value={release.max_output_tokens} /><SnapshotField label="Knowledge version" value={release.knowledge_version_id} mono /><SnapshotField label="Provider model" value={release.provider_model_id} mono /></div><div className="mt-4"><AgentBehaviorDetails behavior={release.behavior_spec} legacyPrompt={release.system_prompt} /></div><div className="mt-4 space-y-4"><JsonSnapshot label="Output contract" value={release.response_format ?? release.output_schema} /><JsonSnapshot label="Runtime configuration" value={release.runtime_config} /></div></div> : <NetworkAgentVersions agent={agent} projectId={projectId} networkBinding={{ ...networkBinding, version: release.version, ref: release.id }} readOnly onOpenComposition={onOpenComposition} />}</div>
    </div>
  )
}

export function NetworkAgentWorkspace(props: NetworkAgentWorkspaceProps) {
  const stableInspection = Boolean(props.readOnly && props.networkBinding.source !== 'draft')
  const exactReleaseQuery = useRelease(stableInspection ? props.agent.id : undefined, stableInspection ? props.networkBinding.ref : undefined)
  const releaseListQuery = useReleases(stableInspection && !props.networkBinding.ref ? props.agent.id : undefined)

  if (props.readOnly && props.networkBinding.source === 'draft') {
    const release = capturedDraftRelease(props.agent, props.networkBinding)
    if (!release) return <SnapshotUnavailable message="The execution is immutable, but its captured Agent Draft payload is unavailable. The mutable current Agent is intentionally not substituted." />
    const snapshotAgent = agentFromRelease(props.agent, release)
    return <AgentEditorProvider key={`${props.agent.id}:${props.networkBinding.version}`} agent={snapshotAgent} projectId={props.projectId}><ReadOnlyAgentSnapshotContent {...props} agent={snapshotAgent} release={release} readOnly /></AgentEditorProvider>
  }

  if (stableInspection) {
    if (exactReleaseQuery.isLoading || releaseListQuery.isLoading) return <div className="flex h-full items-center justify-center text-[10px] text-muted">Loading exact Agent snapshot…</div>
    const release = exactReleaseQuery.data ?? releaseListQuery.data?.find((item) => item.version === props.networkBinding.version)
    if (!release) return <SnapshotUnavailable message={`The Network references Agent snapshot ${props.networkBinding.version}, but it could not be loaded. The current Agent is intentionally not substituted.`} />
    const snapshotAgent = agentFromRelease(props.agent, release)
    return <AgentEditorProvider key={`${props.agent.id}:${release.id}`} agent={snapshotAgent} projectId={props.projectId}><ReadOnlyAgentSnapshotContent {...props} agent={snapshotAgent} release={release} networkBinding={{ ...props.networkBinding, version: release.version, ref: release.id }} readOnly /></AgentEditorProvider>
  }

  return <AgentEditorProvider key={props.agent.id} agent={props.agent} projectId={props.projectId}><EditableAgentWorkspaceContent {...props} /></AgentEditorProvider>
}
