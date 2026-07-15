import { useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ChevronLeft, Code2, History, Lock, MessageSquare, PencilLine, Workflow, type LucideIcon } from 'lucide-react'

import { CreateAgentFlowModal } from '@/features/agents/components/CreateAgentFlowModal'
import { useAgents } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'
import { getNetworkExecutionSnapshot } from '@/features/network/api'
import { NetworkAgentWorkspace, type AgentNetworkBindingSummary } from '@/features/network/components/NetworkAgentWorkspace'
import { NetworkAgentCatalogDrawer } from '@/features/network/components/NetworkAgentCatalogDrawer'
import { NetworkContextInspector } from '@/features/network/components/NetworkContextInspector'
import { NetworkGraphEditor } from '@/features/network/components/NetworkGraphEditor'
import { NetworkPromotionDialog } from '@/features/network/components/NetworkPromotionDialog'
import { NetworkRemoveDialog } from '@/features/network/components/NetworkRemoveDialog'
import { NetworkDraftConflictDialog } from '@/features/network/components/NetworkDraftConflictDialog'
import { NetworkUnsavedChangesDialog } from '@/features/network/components/NetworkUnsavedChangesDialog'
import { NetworkVersionsModal } from '@/features/network/components/NetworkVersionsModal'
import {
  useActivateNetworkProduction,
  useCreateNetworkSession,
  useNetwork,
  useNetworkSessionMessages,
  useNetworkSessions,
  useNetworkVersions,
  usePromoteNetwork,
  useSaveNetworkDraft,
} from '@/features/network/hooks'
import type {
  NetworkDefinition,
  NetworkExecutionSnapshot,
  NetworkSessionResource,
  NetworkVersion,
  PromotionPreview,
  ResolvedNetworkBinding,
} from '@/features/network/types'
import { NetworkChatWorkspace } from '@/features/network/components/NetworkChatWorkspace'
import { hydrateNetworkHistory } from '@/features/network/components/networkHistory'
import type { AgentNodeId, Environment, NetworkBinding } from '@/features/network/components/networkWorkspaceTypes'
import { Badge, NetworkOperationsPanel, NetworkOperationsRail, type PanelTab } from '@/features/network/components/NetworkOperations'
import { createNetworkTraceRecord } from '@/features/network/components/networkObservabilityFactory'
import type { NetworkTraceRecord } from '@/features/network/components/networkObservabilityTypes'
import type { ActiveSessionByEnvironment, NetworkSession, NetworkSessionsByEnvironment } from '@/features/network/components/networkSessionTypes'
import { NetworkApiModal } from '@/features/network/components/NetworkApiModal'
import { UnsavedAgentSwitchDialog, type ReleaseAction } from '@/features/network/components/NetworkReleaseDialogs'
import { delegationCount, networkLabel, type NetworkExecution } from '@/features/network/components/networkChatExecution'
import { initialNetworkWorkspaceState, networkWorkspaceReducer } from '@/features/network/components/networkWorkspaceReducer'
import { applyNetworkDefinitionChange, createEmptyNetworkDefinition, createNodeForAgent, normalizeNetworkDefinition } from '@/features/network/editor/networkDefinitionMapper'
import { validateNetworkGraph } from '@/features/network/editor/networkGraphValidation'
import type { NetworkDefinitionChange, NetworkEditorSelection } from '@/features/network/editor/types'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { cn } from '@/lib/utils'

const smallButton = 'rounded-lg border border-border/80 bg-background/40 px-2.5 py-1.5 text-[10px] font-medium text-muted hover:border-primary/30 hover:text-white disabled:cursor-not-allowed disabled:opacity-45'

type SnapshotInspection = {
  kind: 'run' | 'version'
  title: string
  snapshot: NetworkExecutionSnapshot
  trace: NetworkTraceRecord | null
}

function bindingSource(
  environment: Environment,
  binding: ResolvedNetworkBinding,
): NetworkBinding['source'] {
  if (binding.binding_source === 'draft' || binding.binding_source === 'staging' || binding.binding_source === 'release') return binding.binding_source
  if (binding.snapshot_override) return 'draft'
  if (binding.snapshot_kind === 'staging') return 'staging'
  return environment === 'draft' ? 'draft' : 'release'
}

function definitionForEnvironment(
  environment: Environment,
  draft: NetworkDefinition,
  staging: NetworkVersion | null,
  production: NetworkVersion | null,
) {
  if (environment === 'draft') return draft
  const version = environment === 'staging' ? staging : production
  return version ? normalizeNetworkDefinition(version.definition) : createEmptyNetworkDefinition()
}

function versionBindings(
  version: NetworkVersion | null,
  environment: Extract<Environment, 'staging' | 'production'>,
  agents: Agent[],
): Record<AgentNodeId, NetworkBinding> {
  if (!version) return {}
  return bindingsForSnapshot({
    execution_id: `version:${version.id}`,
    network_id: '',
    network_session_id: '',
    environment,
    draft_revision: null,
    network_version_id: version.id,
    version_label: version.version,
    composition_hash: version.composition_hash,
    definition: normalizeNetworkDefinition(version.definition),
    resolved_bindings: version.resolved_bindings,
    snapshot_source: 'network_version',
    agent_contexts: [],
  }, agents)
}

function bindingsForSnapshot(
  snapshot: NetworkExecutionSnapshot,
  agents: Agent[],
): Record<AgentNodeId, NetworkBinding> {
  const agentsById = new Map(agents.map((agent) => [agent.id, agent]))
  return Object.fromEntries(snapshot.definition.nodes.flatMap((node) => {
    const agent = agentsById.get(node.agent_id)
    const resolved = snapshot.resolved_bindings[node.id]
    if (!agent || !resolved) return []
    const source = bindingSource(snapshot.environment, resolved)
    return [[node.id, {
      nodeId: node.id,
      agent,
      source,
      ref: resolved.release_id ?? resolved.draft_release_id ?? agent.id,
      version: resolved.release_version ?? (source === 'draft' ? snapshot.version_label ?? `Draft r${snapshot.draft_revision ?? 'captured'}` : 'Pinned snapshot'),
      draftVersion: snapshot.version_label ?? `Draft r${snapshot.draft_revision ?? 'captured'}`,
      dirty: false,
      snapshotOverride: resolved.snapshot_override ?? undefined,
    } satisfies NetworkBinding]]
  }))
}

export default function NetworkPage() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  const navigate = useNavigate()
  const { currentProject } = useWorkspace()
  const networkQuery = useNetwork(projectId, currentProject?.name || 'Project')
  const network = networkQuery.data
  const saveNetworkDraftMutation = useSaveNetworkDraft(network?.id, projectId)
  const promoteNetworkMutation = usePromoteNetwork(network?.id, projectId)
  const createNetworkSessionMutation = useCreateNetworkSession(network?.id, projectId)
  const activateProductionMutation = useActivateNetworkProduction(network?.id, projectId)
  const networkSessionsQuery = useNetworkSessions(network?.id, projectId)
  const networkVersionsQuery = useNetworkVersions(network?.id, projectId)
  const agentsQuery = useAgents(projectId)
  const projectAgents = agentsQuery.data ?? []

  const [workspace, dispatchWorkspace] = useReducer(networkWorkspaceReducer, initialNetworkWorkspaceState)
  const { environment, centerMode, selection, inspectorContext, inspectionScope } = workspace
  const [panelTab, setPanelTab] = useState<PanelTab>('traces')
  const [showLeftPanel, setShowLeftPanel] = useState(false)
  const [pendingNode, setPendingNode] = useState<string | null>(null)
  const [showApi, setShowApi] = useState(false)
  const [versionsOpen, setVersionsOpen] = useState(false)
  const [releaseAction, setReleaseAction] = useState<ReleaseAction>(null)
  const [catalogOpen, setCatalogOpen] = useState(false)
  const [showCreateAgent, setShowCreateAgent] = useState(false)
  const [pendingEnvironment, setPendingEnvironment] = useState<Environment | null>(null)
  const [savingWorkspace, setSavingWorkspace] = useState(false)
  const [snapshotInspection, setSnapshotInspection] = useState<SnapshotInspection | null>(null)
  const [snapshotLoadingId, setSnapshotLoadingId] = useState<string | null>(null)
  const [editorDefinition, setEditorDefinition] = useState<NetworkDefinition>(() => createEmptyNetworkDefinition())
  const [editorName, setEditorName] = useState('Project Network')
  const [editorDescription, setEditorDescription] = useState('')
  const [editorRevision, setEditorRevision] = useState(0)
  const [editorDirty, setEditorDirty] = useState(false)
  const [pendingRemoval, setPendingRemoval] = useState<NetworkDefinitionChange | null>(null)
  const [draftConflict, setDraftConflict] = useState(false)
  const [dirtyAgentIds, setDirtyAgentIds] = useState<Set<string>>(() => new Set())
  const saveAgentActionRef = useRef<(() => Promise<boolean>) | null>(null)
  const hydratedRevisionRef = useRef<number | null>(null)

  const workspaceDirty = editorDirty || dirtyAgentIds.size > 0
  const dirtyAgentNames = useMemo(() => {
    const names = projectAgents.filter((agent) => dirtyAgentIds.has(agent.id)).map((agent) => agent.name)
    return names.length ? names : dirtyAgentIds.size ? ['Modified Agent'] : []
  }, [dirtyAgentIds, projectAgents])
  const editorIssues = useMemo(() => validateNetworkGraph(editorDefinition), [editorDefinition])
  const stagingVersion = useMemo(() => networkVersionsQuery.data?.find((item) => item.id === network?.staging_version_id) ?? null, [network?.staging_version_id, networkVersionsQuery.data])
  const productionVersion = useMemo(() => networkVersionsQuery.data?.find((item) => item.id === network?.production_version_id) ?? null, [network?.production_version_id, networkVersionsQuery.data])
  const visibleVersion = environment === 'staging' ? stagingVersion : environment === 'production' ? productionVersion : null
  const visibleDefinition = useMemo(() => definitionForEnvironment(environment, editorDefinition, stagingVersion, productionVersion), [editorDefinition, environment, productionVersion, stagingVersion])
  const visibleEditorIssues = useMemo(() => validateNetworkGraph(visibleDefinition), [visibleDefinition])
  const environmentReady = environment === 'draft' || Boolean(visibleVersion)
  const versionLabel = environment === 'draft' ? String(editorRevision) : visibleVersion?.version ?? 'not created'
  const currentVersionId = environment === 'draft' ? null : visibleVersion?.id ?? null

  const runtimeBindings = useMemo<Record<AgentNodeId, NetworkBinding>>(() => {
    if (environment !== 'draft') return versionBindings(visibleVersion, environment, projectAgents)
    const agentsById = new Map(projectAgents.map((agent) => [agent.id, agent]))
    return Object.fromEntries(visibleDefinition.nodes.flatMap((node) => {
      const agent = agentsById.get(node.agent_id)
      if (!agent) return []
      const source = node.binding.source
      return [[node.id, {
        nodeId: node.id,
        agent,
        source,
        ref: source === 'draft' ? agent.id : node.binding.release_id,
        version: source === 'draft' ? 'current Draft' : 'pinned snapshot',
        draftVersion: 'current Draft',
        dirty: source === 'draft' && dirtyAgentIds.has(agent.id),
      } satisfies NetworkBinding]]
    }))
  }, [dirtyAgentIds, environment, projectAgents, visibleDefinition.nodes, visibleVersion])

  const apiBindings = useMemo(() => ({
    staging: versionBindings(stagingVersion, 'staging', projectAgents),
    production: versionBindings(productionVersion, 'production', projectAgents),
  }), [productionVersion, projectAgents, stagingVersion])

  useEffect(() => {
    if (!network || hydratedRevisionRef.current === network.draft_revision) return
    if (hydratedRevisionRef.current !== null && network.draft_revision < hydratedRevisionRef.current) return
    if (editorDirty && hydratedRevisionRef.current !== null) return
    setEditorDefinition(normalizeNetworkDefinition(network.draft_definition))
    setEditorName(network.name)
    setEditorDescription(network.description)
    setEditorRevision(network.draft_revision)
    setEditorDirty(false)
    dispatchWorkspace({ type: 'select', selection: { type: 'network' }, context: 'network' })
    hydratedRevisionRef.current = network.draft_revision
  }, [editorDirty, network])

  const initialSessions = useMemo<NetworkSessionsByEnvironment>(() => ({ draft: [], staging: [], production: [] }), [])
  const [sessionsByEnvironment, setSessionsByEnvironment] = useState(() => initialSessions)
  const [activeSessionIdByEnvironment, setActiveSessionIdByEnvironment] = useState<ActiveSessionByEnvironment>(() => ({ draft: null, staging: null, production: null }))
  const [traces, setTraces] = useState<NetworkTraceRecord[]>([])
  const [selectedTraceIdBySession, setSelectedTraceIdBySession] = useState<Record<string, string | null>>({})

  useEffect(() => {
    const remoteSessions = networkSessionsQuery.data
    if (!remoteSessions) return
    const mapSession = (item: NetworkSessionResource): NetworkSession => ({
      id: item.id,
      projectId: projectId!,
      networkId: network?.id || '',
      title: item.title,
      environment: item.environment,
      networkVersion: item.network_version_id,
      draftRevision: item.environment === 'draft' ? editorRevision : null,
      compositionHash: item.network_version_id ?? `draft:${editorRevision}`,
      status: item.status,
      createdAt: item.created_at,
      lastMessageAt: item.last_message_at ?? null,
      messageCount: item.message_count ?? 0,
      traceCount: item.trace_count ?? 0,
      agentContexts: [],
    })
    const draft = remoteSessions.filter((item) => item.environment === 'draft').map(mapSession)
    const staging = remoteSessions.filter((item) => item.environment === 'staging').map(mapSession)
    const production = remoteSessions.filter((item) => item.environment === 'production').map(mapSession)
    setSessionsByEnvironment({ draft, staging, production })
    setActiveSessionIdByEnvironment((current) => ({
      draft: draft.some((item) => item.id === current.draft) ? current.draft : draft[0]?.id ?? null,
      staging: staging.some((item) => item.id === current.staging) ? current.staging : staging[0]?.id ?? null,
      production: production.some((item) => item.id === current.production) ? current.production : production[0]?.id ?? null,
    }))
  }, [editorRevision, networkSessionsQuery.data, network?.id, projectId])

  const persistDraft = async () => {
    if (!network || !projectId) throw new Error('Network is still loading')
    const errors = validateNetworkGraph(editorDefinition).filter((issue) => issue.severity === 'error')
    if (errors.length) throw new Error(errors[0].message)
    if (!editorDirty) return { ...network, draft_revision: editorRevision }
    const saved = await saveNetworkDraftMutation.mutateAsync({ expectedRevision: editorRevision, name: editorName, description: editorDescription, definition: editorDefinition })
    hydratedRevisionRef.current = saved.draft_revision
    setEditorRevision(saved.draft_revision)
    setEditorDirty(false)
    return saved
  }

  const saveWorkspaceDraft = async () => {
    if (savingWorkspace) throw new Error('Draft changes are already being saved')
    setSavingWorkspace(true)
    try {
      if (dirtyAgentIds.size > 0) {
        if (!saveAgentActionRef.current) throw new Error('Open the modified Agent and save its Draft before continuing')
        const saved = await saveAgentActionRef.current()
        if (!saved) throw new Error('Agent Draft could not be saved')
        setDirtyAgentIds(new Set())
      }
      return await persistDraft()
    } finally {
      setSavingWorkspace(false)
    }
  }

  const clearSnapshotInspection = () => {
    setSnapshotInspection(null)
    dispatchWorkspace({ type: 'clear-run-inspection' })
  }

  const changeCenter = (mode: 'canvas' | 'chat') => {
    if (mode === 'chat' && snapshotInspection) clearSnapshotInspection()
    dispatchWorkspace({ type: 'center', mode })
  }

  const applyEditorChange = (change: NetworkDefinitionChange) => {
    if (environment !== 'draft' || snapshotInspection) return
    setEditorDefinition((current) => applyNetworkDefinitionChange(current, change))
    setEditorDirty(true)
    if (change.type === 'remove-node' || change.type === 'remove-edge') dispatchWorkspace({ type: 'select', selection: { type: 'network' }, context: 'network' })
  }

  const changeEditor = (change: NetworkDefinitionChange) => {
    if (change.type === 'remove-node' || change.type === 'remove-edge') {
      setPendingRemoval(change)
      return
    }
    applyEditorChange(change)
  }

  const updateEditorMetadata = (metadata: { name?: string; description?: string }) => {
    if (environment !== 'draft' || snapshotInspection) return
    if (metadata.name !== undefined) setEditorName(metadata.name)
    if (metadata.description !== undefined) setEditorDescription(metadata.description)
    setEditorDirty(true)
  }

  const addAgentToNetwork = (agent: Agent) => {
    const node = createNodeForAgent(agent, editorDefinition.nodes.length)
    changeEditor({ type: 'add-node', node })
    dispatchWorkspace({ type: 'select', selection: { type: 'node', id: node.id }, context: 'network' })
    setCatalogOpen(false)
    toast.success(`${agent.name} added to the Network`)
  }

  const saveDraft = async () => {
    try {
      await saveWorkspaceDraft()
      toast.success('Draft changes saved')
    } catch (error) {
      if (error instanceof Error && error.message.includes('changed by another request')) setDraftConflict(true)
      toast.error(error instanceof Error ? error.message : 'Unable to save Draft changes')
    }
  }

  const reloadServerDraft = async () => {
    const result = await networkQuery.refetch()
    if (!result.data) return
    setEditorDefinition(normalizeNetworkDefinition(result.data.draft_definition))
    setEditorName(result.data.name)
    setEditorDescription(result.data.description)
    setEditorRevision(result.data.draft_revision)
    hydratedRevisionRef.current = result.data.draft_revision
    setEditorDirty(false)
    dispatchWorkspace({ type: 'select', selection: { type: 'network' }, context: 'network' })
    setDraftConflict(false)
    toast.success('Latest Network Draft loaded')
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault()
        if (environment === 'draft' && workspaceDirty && !snapshotInspection) void saveDraft()
      }
    }
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!workspaceDirty) return
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('beforeunload', onBeforeUnload)
    }
  }, [environment, snapshotInspection, workspaceDirty])

  const environmentSessions = sessionsByEnvironment[environment]
  const activeSessionId = activeSessionIdByEnvironment[environment]
  const activeSession = environmentSessions.find((session) => session.id === activeSessionId) ?? null
  const activeSessionVersion = useMemo(() => activeSession?.networkVersion ? networkVersionsQuery.data?.find((item) => item.id === activeSession.networkVersion) ?? null : null, [activeSession?.networkVersion, networkVersionsQuery.data])
  const historyBindings = useMemo<Record<AgentNodeId, NetworkBinding>>(() => environment === 'draft' ? runtimeBindings : activeSessionVersion ? versionBindings(activeSessionVersion, environment, projectAgents) : {}, [activeSessionVersion, environment, projectAgents, runtimeBindings])
  const sessionMessagesQuery = useNetworkSessionMessages(network?.id, activeSession?.id, projectId)
  const hydratedHistory = useMemo(() => activeSession && sessionMessagesQuery.data ? hydrateNetworkHistory({ messages: sessionMessagesQuery.data, environment, bindings: historyBindings, session: activeSession, versionLabel: activeSessionVersion?.version ?? versionLabel }) : { turns: [], traces: [] }, [activeSession?.id, activeSession?.networkVersion, activeSession?.agentContexts, activeSessionVersion?.version, environment, historyBindings, sessionMessagesQuery.data, versionLabel])

  useEffect(() => {
    if (!activeSession) return
    const hydratedIds = new Set(hydratedHistory.traces.map((trace) => trace.id))
    setTraces((current) => [...hydratedHistory.traces, ...current.filter((trace) => trace.networkSessionId !== activeSession.id || !hydratedIds.has(trace.id))])
  }, [activeSession?.id, hydratedHistory.traces])

  const activeTraces = activeSession ? traces.filter((trace) => trace.networkSessionId === activeSession.id && trace.environment === environment) : []
  const selectedTraceId = activeSession ? selectedTraceIdBySession[activeSession.id] ?? null : null
  const selectedTrace = selectedTraceId ? activeTraces.find((trace) => trace.id === selectedTraceId) ?? null : null
  const workspaceDefinition = snapshotInspection ? normalizeNetworkDefinition(snapshotInspection.snapshot.definition) : visibleDefinition
  const workspaceBindings = useMemo<Record<AgentNodeId, NetworkBinding>>(() => snapshotInspection ? bindingsForSnapshot(snapshotInspection.snapshot, projectAgents) : runtimeBindings, [projectAgents, runtimeBindings, snapshotInspection])
  const workspaceIssues = useMemo(() => validateNetworkGraph(workspaceDefinition), [workspaceDefinition])

  useEffect(() => {
    if (selection.type === 'node' && !workspaceDefinition.nodes.some((node) => node.id === selection.id)) dispatchWorkspace({ type: 'select', selection: { type: 'network' }, context: 'network' })
    else if (selection.type === 'edge' && !workspaceDefinition.edges.some((edge) => edge.id === selection.id)) dispatchWorkspace({ type: 'select', selection: { type: 'network' }, context: 'network' })
  }, [selection, workspaceDefinition.edges, workspaceDefinition.nodes])

  const selectedNodeId = selection.type === 'node' ? selection.id : null
  const selectedNetworkBinding = selectedNodeId ? workspaceBindings[selectedNodeId] ?? null : null
  const selectedAgent = selectedNetworkBinding?.agent ?? null

  const openReleaseAction = async (nextAction: Exclude<ReleaseAction, null>) => {
    if (nextAction !== 'stage') {
      setReleaseAction(nextAction)
      return
    }
    try {
      await saveWorkspaceDraft()
      setReleaseAction('stage')
    } catch (error) {
      if (error instanceof Error && error.message.includes('changed by another request')) setDraftConflict(true)
      toast.error(error instanceof Error ? error.message : 'Unable to prepare Network Staging')
    }
  }

  const commitEnvironmentChange = (next: Environment) => {
    clearSnapshotInspection()
    const nextDefinition = definitionForEnvironment(next, editorDefinition, stagingVersion, productionVersion)
    const nextSelection: NetworkEditorSelection = selection.type === 'node' && nextDefinition.nodes.some((node) => node.id === selection.id)
      ? selection
      : selection.type === 'edge' && nextDefinition.edges.some((edge) => edge.id === selection.id)
        ? selection
        : { type: 'network' }
    dispatchWorkspace({ type: 'environment', environment: next, selection: nextSelection })
    const nextSessionId = activeSessionIdByEnvironment[next]
    if (nextSessionId) setSelectedTraceIdBySession((current) => ({ ...current, [nextSessionId]: null }))
  }

  const changeEnvironment = (next: Environment) => {
    if (next === environment) return
    if (environment === 'draft' && workspaceDirty) {
      setPendingEnvironment(next)
      return
    }
    commitEnvironmentChange(next)
  }

  const saveAndChangeEnvironment = async () => {
    if (!pendingEnvironment) return
    const target = pendingEnvironment
    try {
      await saveWorkspaceDraft()
      setPendingEnvironment(null)
      commitEnvironmentChange(target)
      toast.success(`Draft saved. ${target} opened.`)
    } catch (error) {
      if (error instanceof Error && error.message.includes('changed by another request')) setDraftConflict(true)
      toast.error(error instanceof Error ? error.message : 'Unable to save Draft changes')
    }
  }

  const commitNodeSelection = (nodeId: string) => dispatchWorkspace({ type: 'select', selection: { type: 'node', id: nodeId }, context: 'agent' })
  const selectWorkspace = (nextSelection: NetworkEditorSelection, context?: 'agent' | 'network') => {
    const currentAgentId = selectedAgent?.id
    const changingNode = nextSelection.type !== 'node' || nextSelection.id !== selectedNodeId
    if (changingNode && currentAgentId && dirtyAgentIds.has(currentAgentId)) {
      if (nextSelection.type === 'node') setPendingNode(nextSelection.id)
      else toast.warning('Save or discard Agent Draft changes before changing context')
      return
    }
    dispatchWorkspace({ type: 'select', selection: nextSelection, context })
  }

  const selectNode = (nodeId: string) => {
    if (workspaceDefinition.nodes.some((item) => item.id === nodeId)) selectWorkspace({ type: 'node', id: nodeId }, 'agent')
  }

  const updateSelectedAgentDirty = (dirty: boolean) => {
    const agentId = selectedAgent?.id
    if (!agentId) return
    setDirtyAgentIds((current) => {
      const next = new Set(current)
      if (dirty) next.add(agentId)
      else next.delete(agentId)
      return next
    })
  }

  const discardAndSwitch = () => {
    if (!pendingNode) return
    const currentAgentId = selectedAgent?.id
    if (currentAgentId) setDirtyAgentIds((current) => {
      const next = new Set(current)
      next.delete(currentAgentId)
      return next
    })
    const target = pendingNode
    setPendingNode(null)
    commitNodeSelection(target)
  }

  const saveAndSwitch = async () => {
    if (!pendingNode || !saveAgentActionRef.current) return
    if (!(await saveAgentActionRef.current())) return
    const target = pendingNode
    setPendingNode(null)
    commitNodeSelection(target)
  }

  const stage = async (preview: PromotionPreview, approvedActionIds: string[]) => {
    if (!network || !projectId) return
    try {
      await saveWorkspaceDraft()
      await promoteNetworkMutation.mutateAsync({ environment: 'staging', expected_revision: preview.network_revision, approved_action_ids: approvedActionIds })
      setReleaseAction(null)
      dispatchWorkspace({ type: 'environment', environment: 'staging', selection: { type: 'network' } })
      toast.success('Immutable Network Staging version created')
    } catch (error) {
      if (error instanceof Error && error.message.includes('changed after the promotion preview')) setDraftConflict(true)
      toast.error(error instanceof Error ? error.message : 'Unable to stage Network')
    }
  }

  const publish = async (preview: PromotionPreview, approvedActionIds: string[]) => {
    if (!network || !projectId) return
    try {
      await promoteNetworkMutation.mutateAsync({ environment: 'production', expected_network_version_id: preview.network_version_id, approved_action_ids: approvedActionIds })
      setReleaseAction(null)
      dispatchWorkspace({ type: 'environment', environment: 'production', selection: { type: 'network' } })
      toast.success('Immutable Network Production release created')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to publish Network')
    }
  }

  const confirmRelease = (preview: PromotionPreview, approvedActionIds: string[]) => {
    if (releaseAction === 'stage') void stage(preview, approvedActionIds)
    else if (releaseAction === 'publish') void publish(preview, approvedActionIds)
  }

  const activateProduction = async (sourceVersionId: string, description: string) => {
    try {
      await activateProductionMutation.mutateAsync({
        source_version_id: sourceVersionId,
        expected_current_production_version_id: network?.production_version_id ?? null,
        change_description: description,
      })
      setVersionsOpen(false)
      clearSnapshotInspection()
      dispatchWorkspace({ type: 'environment', environment: 'production', selection: { type: 'network' } })
      toast.success('Selected Network Release activated in Production')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to activate Network Production')
      throw error
    }
  }

  const selectSession = (sessionId: string) => {
    setActiveSessionIdByEnvironment((current) => ({ ...current, [environment]: sessionId }))
    setSelectedTraceIdBySession((current) => ({ ...current, [sessionId]: null }))
    clearSnapshotInspection()
  }

  const createSession = async () => {
    if (!network || !projectId) return
    if (!environmentReady) {
      toast.info(`Create the ${environment} version before starting its Chat`)
      return
    }
    try {
      const sessionDraftRevision = environment === 'draft' ? (await saveWorkspaceDraft()).draft_revision : null
      const created = await createNetworkSessionMutation.mutateAsync(environment)
      const session: NetworkSession = {
        id: created.id,
        projectId,
        networkId: network.id,
        title: created.title,
        environment: created.environment,
        networkVersion: created.network_version_id,
        draftRevision: sessionDraftRevision,
        compositionHash: created.network_version_id ?? `draft:${sessionDraftRevision}`,
        status: created.status,
        createdAt: created.created_at,
        lastMessageAt: null,
        messageCount: 0,
        traceCount: 0,
        agentContexts: [],
      }
      setSessionsByEnvironment((current) => ({ ...current, [environment]: [session, ...current[environment]] }))
      setActiveSessionIdByEnvironment((current) => ({ ...current, [environment]: session.id }))
      clearSnapshotInspection()
      toast.success(`New ${environment} Network Session started`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to create Network Session')
    }
  }

  const selectTrace = (trace: NetworkTraceRecord) => {
    setSelectedTraceIdBySession((current) => ({ ...current, [trace.networkSessionId]: trace.id }))
  }

  const viewTraceOnCanvas = async (trace: NetworkTraceRecord) => {
    if (!projectId) return
    setSnapshotLoadingId(trace.execution.id)
    try {
      const snapshot = await getNetworkExecutionSnapshot(trace.execution.id, projectId)
      setSnapshotInspection({ kind: 'run', title: `Run · ${snapshot.version_label ?? trace.networkVersion}`, snapshot, trace })
      dispatchWorkspace({ type: 'inspect-run', runId: trace.id })
      dispatchWorkspace({ type: 'center', mode: 'canvas' })
    } catch (error) {
      toast.info(error instanceof Error ? error.message : 'Exact Network Run snapshot is unavailable')
    } finally {
      setSnapshotLoadingId(null)
    }
  }

  const viewVersionOnCanvas = (version: NetworkVersion) => {
    const snapshot: NetworkExecutionSnapshot = {
      execution_id: `version:${version.id}`,
      network_id: network?.id ?? '',
      network_session_id: '',
      environment: version.kind === 'staging' ? 'staging' : 'production',
      draft_revision: null,
      network_version_id: version.id,
      version_label: version.version,
      composition_hash: version.composition_hash,
      definition: normalizeNetworkDefinition(version.definition),
      resolved_bindings: version.resolved_bindings,
      snapshot_source: 'network_version',
      agent_contexts: [],
    }
    setSnapshotInspection({ kind: 'version', title: `Release · ${version.version}`, snapshot, trace: null })
    dispatchWorkspace({ type: 'inspect-run', runId: `version:${version.id}` })
    dispatchWorkspace({ type: 'center', mode: 'canvas' })
    setVersionsOpen(false)
  }

  const handleCompletedTrace = (trace: NetworkTraceRecord) => {
    setTraces((current) => [trace, ...current.filter((item) => item.id !== trace.id)])
    setSessionsByEnvironment((current) => ({
      ...current,
      [trace.environment]: current[trace.environment].map((session) => session.id === trace.networkSessionId ? {
        ...session,
        title: session.messageCount === 0 ? trace.title : session.title,
        lastMessageAt: trace.completedAt ?? trace.startedAt,
        messageCount: session.messageCount + 2,
        traceCount: session.traceCount + 1,
        agentContexts: trace.agentContexts,
      } : session),
    }))
    if (trace.status === 'error') {
      selectTrace(trace)
      setPanelTab('traces')
      setShowLeftPanel(true)
      toast.error('Network execution failed. Run details opened for diagnosis.')
    } else {
      toast.success('Network execution completed', { description: `${delegationCount(trace.execution.root)} hops · ${trace.durationMs}ms` })
    }
  }

  const openTraceFromChat = (execution: NetworkExecution) => {
    if (!activeSession) return
    const existing = activeTraces.find((trace) => trace.execution.id === execution.id || (execution.traceId != null && trace.traceId === execution.traceId))
    const trace = existing ?? createNetworkTraceRecord({
      execution,
      environment,
      bindings: historyBindings,
      networkSessionId: activeSession.id,
      title: 'Network Run',
      userMessage: 'Opened from the current Network Chat.',
      answer: 'Execution details from the current Network Chat.',
      agentContexts: activeSession.agentContexts,
      source: 'chat',
      networkVersion: activeSessionVersion?.version ?? networkLabel(environment, versionLabel),
    })
    if (!existing) setTraces((current) => [trace, ...current])
    selectTrace(trace)
    setPanelTab('traces')
    setShowLeftPanel(true)
  }

  const handlePanelTab = (tab: PanelTab) => {
    if (showLeftPanel && panelTab === tab) {
      setShowLeftPanel(false)
      return
    }
    setPanelTab(tab)
    setShowLeftPanel(true)
  }

  const networkBindingSummary: AgentNetworkBindingSummary | null = selectedNetworkBinding
    ? { source: selectedNetworkBinding.source, version: selectedNetworkBinding.version, ref: selectedNetworkBinding.ref, snapshotOverride: selectedNetworkBinding.snapshotOverride }
    : null
  const inspectorReadOnly = environment !== 'draft' || Boolean(snapshotInspection)
  const agentConfigReadOnly = inspectorReadOnly || selectedNetworkBinding?.source !== 'draft'
  const agentWorkspace = selectedAgent && networkBindingSummary ? (
    <NetworkAgentWorkspace
      key={`${selectedAgent.id}:${selectedNetworkBinding?.ref ?? 'draft'}:${snapshotInspection?.snapshot.execution_id ?? 'current'}`}
      agent={selectedAgent}
      projectId={projectId!}
      networkBinding={networkBindingSummary}
      readOnly={agentConfigReadOnly}
      onOpenComposition={() => dispatchWorkspace({ type: 'context', context: 'network' })}
      onDirtyChange={updateSelectedAgentDirty}
      onRegisterSaveAction={(saveAction) => { saveAgentActionRef.current = saveAction }}
    />
  ) : null
  const draftSavePending = savingWorkspace || saveNetworkDraftMutation.isPending
  const activePath = snapshotInspection?.kind === 'run' ? snapshotInspection.trace?.execution.path ?? [] : []
  const contextVersionLabel = snapshotInspection?.title ?? networkLabel(environment, versionLabel)

  const canvasContent = agentsQuery.isLoading ? (
    <div className="flex flex-1 items-center justify-center text-xs text-muted">Loading Network inventory</div>
  ) : !environmentReady && !snapshotInspection ? (
    <div className="flex min-w-0 flex-1 items-center justify-center p-6 text-center"><div className="max-w-sm rounded-2xl border border-border bg-surface/70 p-6"><p className="text-sm font-medium text-white">{environment === 'staging' ? 'Staging has not been created' : 'Production has not been published'}</p><p className="mt-2 text-[10px] leading-5 text-muted">{environment === 'staging' ? 'Return to Draft, save the composition and create an immutable Staging version.' : 'Validate the Network in Staging, then publish that exact snapshot.'}</p><button type="button" onClick={() => changeEnvironment(environment === 'staging' ? 'draft' : 'staging')} className="mt-4 rounded-lg bg-primary px-3 py-2 text-[11px] font-medium text-white">Go to {environment === 'staging' ? 'Draft' : 'Staging'}</button></div></div>
  ) : (
    <NetworkGraphEditor definition={workspaceDefinition} agents={projectAgents} issues={workspaceIssues} selection={selection} readOnly={inspectorReadOnly} activePath={activePath} inspectionLabel={snapshotInspection?.title ?? null} onClearInspection={clearSnapshotInspection} onChange={changeEditor} onSelect={selectWorkspace} onAddAgent={() => setCatalogOpen(true)} />
  )

  const chatContent = activeSession ? (
    <NetworkChatWorkspace key={activeSession.id} networkId={network?.id || ''} projectId={projectId!} networkName={`${currentProject?.name || 'Project'} Network`} environment={environment} versionLabel={versionLabel} currentVersionId={currentVersionId} bindings={runtimeBindings} sessions={environmentSessions} activeSession={activeSession} historyTurns={hydratedHistory.turns} historyLoading={sessionMessagesQuery.isLoading} onBeforeDraftRun={async () => (await saveWorkspaceDraft()).draft_revision} onSelectSession={selectSession} onNewSession={() => createSession()} onRun={handleCompletedTrace} onSelectAgent={selectNode} onOpenTrace={openTraceFromChat} />
  ) : (
    <div className="flex min-w-0 flex-1 items-center justify-center p-6 text-center"><div><p className="text-sm font-medium text-white">No {environment} Network Session selected</p><p className="mt-1 text-[10px] text-muted">The Chat will use {networkLabel(environment, versionLabel)}.</p><button type="button" onClick={createSession} className="mt-3 rounded-lg bg-primary px-3 py-2 text-[11px] font-medium text-white">Create session</button></div></div>
  )

  return (
    <div className="flex h-screen min-w-0 flex-col overflow-hidden bg-background">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-surface/80 px-3">
        <button type="button" onClick={() => navigate(`/organizations/${organizationId}/projects/${projectId}`)} className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted"><ChevronLeft className="h-4 w-4" /></button>
        <div>
          <div className="flex items-center gap-2"><h1 className="text-sm font-semibold text-white">{currentProject?.name || 'Project'} Network</h1><Badge>{networkQuery.isLoading ? 'Loading' : 'Runtime'}</Badge><button type="button" onClick={() => setVersionsOpen(true)} className={cn('rounded border px-2 py-0.5 font-mono text-[9px]', productionVersion ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300' : 'border-border bg-background/45 text-muted')}>{productionVersion ? `Production · ${productionVersion.version}` : 'No Production release'}</button></div>
          <p className="text-[10px] text-muted">One Network per Project</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <div role="tablist" aria-label="Network environment" className="flex rounded-xl border border-border bg-background/35 p-1">{(['draft', 'staging', 'production'] as Environment[]).map((item) => <button key={item} type="button" role="tab" aria-selected={item === environment} onClick={() => changeEnvironment(item)} title={item === 'draft' ? 'Editable working composition' : item === 'staging' ? 'Read-only validation snapshot' : 'Immutable released composition'} className={cn('rounded-lg px-3 py-1.5 text-[10px] capitalize', item === environment ? item === 'production' ? 'bg-emerald-500/10 text-emerald-300' : item === 'staging' ? 'bg-indigo-500/10 text-indigo-300' : 'bg-primary/10 text-primary-light' : 'text-muted hover:text-white')}>{item}</button>)}</div>
          {environment === 'draft' ? <button type="button" disabled={!workspaceDirty || draftSavePending || editorIssues.some((issue) => issue.severity === 'error') || Boolean(snapshotInspection)} onClick={() => void saveDraft()} className={smallButton}>{draftSavePending ? 'Saving…' : workspaceDirty ? 'Save Draft' : `Draft saved · r${editorRevision}`}</button> : null}
          <button type="button" onClick={() => setVersionsOpen(true)} className={smallButton}><History className="mr-1 inline h-3.5 w-3.5" />Versions</button>
          <button type="button" onClick={() => setShowApi(true)} className={smallButton}><Code2 className="mr-1 inline h-3.5 w-3.5" />API Reference</button>
          {environment === 'production' ? <button type="button" onClick={() => setVersionsOpen(true)} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white">Manage Production</button> : <button type="button" disabled={Boolean(snapshotInspection)} onClick={() => void openReleaseAction(environment === 'draft' ? 'stage' : 'publish')} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45">{environment === 'draft' ? 'Stage Network' : 'Publish Release'}</button>}
        </div>
      </header>
      <div className="relative flex h-8 shrink-0 items-center border-b border-border bg-surface/35 px-3 text-[10px] text-muted">
        <span className="inline-flex items-center gap-1.5">{snapshotInspection || environment !== 'draft' ? <Lock className="h-3 w-3 text-muted" /> : <PencilLine className="h-3 w-3 text-primary-light" />}Viewing: <b className="text-slate-300">{contextVersionLabel}</b> · {snapshotInspection ? 'Exact read-only snapshot' : environment === 'draft' ? workspaceDirty ? 'Unsaved Draft changes' : 'Draft saved' : environmentReady ? 'Read-only composition · Chat and Runs available' : 'Environment not created'}</span>
        <div className="absolute left-1/2 flex -translate-x-1/2 rounded-lg border border-border bg-background/45 p-0.5">{([['canvas', Workflow], ['chat', MessageSquare]] as Array<['canvas' | 'chat', LucideIcon]>).map(([mode, Icon]) => <button key={mode} type="button" onClick={() => changeCenter(mode)} className={cn('flex items-center gap-1 rounded-md px-2.5 py-1 capitalize', centerMode === mode ? 'bg-primary/10 text-primary-light' : 'text-muted')}><Icon className="h-3 w-3" />{mode}</button>)}</div>
        <span className="ml-auto truncate">{activeSession ? `Session: ${activeSession.title}` : 'No session selected'} · Max depth {workspaceDefinition.settings.max_depth} · Timeout {workspaceDefinition.settings.timeout_seconds}s</span>
      </div>
      <div className="relative flex min-h-0 flex-1">
        <NetworkOperationsRail activeTab={showLeftPanel ? panelTab : null} onTabChange={handlePanelTab} />
        {showLeftPanel ? <NetworkOperationsPanel activeTab={panelTab} traces={activeTraces} session={activeSession} selectedTraceId={selectedTraceId} onSelectTrace={selectTrace} onViewCanvas={(trace) => void viewTraceOnCanvas(trace)} onOpenAgent={selectNode} /> : null}
        <div className="relative flex min-w-0 flex-1 overflow-hidden">
          <div className={cn('absolute inset-0 flex min-w-0', centerMode !== 'canvas' && 'invisible pointer-events-none')} aria-hidden={centerMode !== 'canvas'}>{canvasContent}</div>
          <div className={cn('absolute inset-0 flex min-w-0', centerMode !== 'chat' && 'invisible pointer-events-none')} aria-hidden={centerMode !== 'chat'}>{chatContent}</div>
          {snapshotLoadingId ? <div className="pointer-events-none absolute inset-x-0 top-3 z-20 flex justify-center"><div className="rounded-lg border border-border bg-surface/95 px-3 py-2 text-[9px] text-muted shadow-xl">Loading exact Run snapshot…</div></div> : null}
        </div>
        <NetworkContextInspector context={inspectorContext} centerMode={centerMode} inspectionScope={inspectionScope} inspectionLabel={snapshotInspection?.title ?? null} inspectionKind={snapshotInspection?.kind ?? null} definition={workspaceDefinition} agents={projectAgents} bindings={workspaceBindings} issues={workspaceIssues} selection={selection} readOnly={inspectorReadOnly} name={snapshotInspection ? `${editorName} · ${snapshotInspection.snapshot.version_label ?? 'snapshot'}` : editorName} description={editorDescription} agentWorkspace={agentWorkspace} onContext={(context) => dispatchWorkspace({ type: 'context', context })} onLocateOnCanvas={() => changeCenter('canvas')} onSelect={selectWorkspace} onMetadata={updateEditorMetadata} onChange={changeEditor} />
        <NetworkAgentCatalogDrawer open={catalogOpen} agents={projectAgents} addedAgentIds={new Set(editorDefinition.nodes.map((node) => node.agent_id))} onClose={() => setCatalogOpen(false)} onAdd={addAgentToNetwork} onCreate={() => { setCatalogOpen(false); setShowCreateAgent(true) }} />
      </div>
      <CreateAgentFlowModal open={showCreateAgent} onClose={() => { setShowCreateAgent(false); setCatalogOpen(true) }} projectId={projectId!} onCreated={(agent) => { setShowCreateAgent(false); addAgentToNetwork(agent); void agentsQuery.refetch() }} />
      {showApi ? <NetworkApiModal open={showApi} onClose={() => setShowApi(false)} projectId={projectId!} networkId={network?.id || ''} versionIds={{ staging: network?.staging_version_id, production: network?.production_version_id }} bindings={apiBindings} /> : null}
      {releaseAction === 'stage' || releaseAction === 'publish' ? <NetworkPromotionDialog environment={releaseAction === 'stage' ? 'staging' : 'production'} networkId={network?.id || ''} projectId={projectId!} definition={releaseAction === 'stage' ? editorDefinition : visibleDefinition} agents={projectAgents} issues={releaseAction === 'stage' ? editorIssues : visibleEditorIssues} pending={draftSavePending || promoteNetworkMutation.isPending} onClose={() => setReleaseAction(null)} onConfirm={confirmRelease} /> : null}
      <NetworkVersionsModal open={versionsOpen} networkName={`${currentProject?.name || 'Project'} Network`} draftDefinition={editorDefinition} draftRevision={editorRevision} draftDirty={workspaceDirty} stagingVersion={stagingVersion} productionVersion={productionVersion} versions={networkVersionsQuery.data ?? []} agents={projectAgents} pending={activateProductionMutation.isPending || promoteNetworkMutation.isPending || draftSavePending} onClose={() => setVersionsOpen(false)} onStage={() => { setVersionsOpen(false); void openReleaseAction('stage') }} onPublish={() => { setVersionsOpen(false); setReleaseAction('publish') }} onViewVersion={viewVersionOnCanvas} onActivate={activateProduction} />
      {pendingRemoval ? <NetworkRemoveDialog title={pendingRemoval.type === 'remove-node' ? 'Remove Agent from Network?' : 'Remove delegation?'} description={pendingRemoval.type === 'remove-node' ? 'The Agent remains available in the Project. Only this Network node will be removed.' : 'The source Agent will no longer be able to delegate work through this connection.'} impact={pendingRemoval.type === 'remove-node' ? `${editorDefinition.edges.filter((edge) => edge.source_node_id === pendingRemoval.nodeId || edge.target_node_id === pendingRemoval.nodeId).length} connected delegation(s) will also be removed. The graph must remain reachable before it can be saved.` : 'The target Agent may become unreachable from the entry point.'} onClose={() => setPendingRemoval(null)} onConfirm={() => { applyEditorChange(pendingRemoval); setPendingRemoval(null) }} /> : null}
      {draftConflict ? <NetworkDraftConflictDialog onClose={() => setDraftConflict(false)} onReload={() => void reloadServerDraft()} /> : null}
      {pendingNode && selectedAgent ? <UnsavedAgentSwitchDialog agentName={selectedAgent.name} onStay={() => setPendingNode(null)} onDiscard={discardAndSwitch} onSave={() => void saveAndSwitch()} /> : null}
      {pendingEnvironment ? <NetworkUnsavedChangesDialog target={pendingEnvironment} networkDirty={editorDirty} agentNames={dirtyAgentNames} pending={savingWorkspace} onClose={() => setPendingEnvironment(null)} onConfirm={() => void saveAndChangeEnvironment()} /> : null}
    </div>
  )
}
