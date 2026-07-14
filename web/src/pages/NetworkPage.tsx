import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ChevronLeft, Code2, Lock, MessageSquare, PencilLine, Workflow, type LucideIcon } from 'lucide-react'

import { useAgents } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'
import { NetworkAgentWorkspace, type AgentNetworkBindingSummary } from '@/features/network/components/NetworkAgentWorkspace'
import { NetworkAgentCatalogDrawer } from '@/features/network/components/NetworkAgentCatalogDrawer'
import { NetworkGraphEditor } from '@/features/network/components/NetworkGraphEditor'
import { NetworkGraphInspector } from '@/features/network/components/NetworkGraphInspector'
import { NetworkPromotionDialog } from '@/features/network/components/NetworkPromotionDialog'
import { NetworkRemoveDialog } from '@/features/network/components/NetworkRemoveDialog'
import { useCreateNetworkSession, useNetwork, useNetworkSessions, useNetworkVersions, usePromoteNetwork, useSaveNetworkDraft } from '@/features/network/hooks'
import type { NetworkDefinition, NetworkSessionResource } from '@/features/network/types'
import { NetworkChatWorkspace } from '@/features/network/components/NetworkChatWorkspace'
import { NetworkInspectorWorkspace, type NetworkConfigSection, type NetworkInspectorSection } from '@/features/network/components/NetworkInspectorWorkspace'
import type { AgentNodeId, Environment, NetworkVersionOption, NodeId } from '@/features/network/components/networkWorkspaceTypes'
import { Badge, NetworkOperationsPanel, NetworkOperationsRail, type PanelTab } from '@/features/network/components/NetworkOperations'
import { createNetworkTraceRecord } from '@/features/network/components/networkObservabilityFactory'
import { hashComposition, type NetworkTraceRecord } from '@/features/network/components/networkObservabilityTypes'
import type { ActiveSessionByEnvironment, NetworkSession, NetworkSessionsByEnvironment } from '@/features/network/components/networkSessionTypes'
import { NetworkApiModal } from '@/features/network/components/NetworkApiModal'
import { NetworkInspectorShell, type InspectorContext } from '@/features/network/components/NetworkInspectorShell'
import { NetworkReleaseModal, UnsavedAgentSwitchDialog, type ReleaseAction } from '@/features/network/components/NetworkReleaseDialogs'
import { DRAFT, HISTORY, PRODUCTION, STAGING, bind, clone, fallbackAgents } from '@/features/network/components/networkPageData'
import { currentSignature, networkLabel, type NetworkExecution } from '@/features/network/components/networkChatExecution'
import { applyNetworkDefinitionChange, createEmptyNetworkDefinition, createNodeForAgent, normalizeNetworkDefinition } from '@/features/network/editor/networkDefinitionMapper'
import { validateNetworkGraph } from '@/features/network/editor/networkGraphValidation'
import type { NetworkDefinitionChange, NetworkEditorSelection } from '@/features/network/editor/types'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { cn } from '@/lib/utils'

type CenterMode = 'canvas' | 'chat'
const smallButton = 'rounded-lg border border-border/80 bg-background/40 px-2.5 py-1.5 text-[10px] font-medium text-muted hover:border-primary/30 hover:text-white disabled:cursor-not-allowed disabled:opacity-45'

export default function NetworkPage() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  const navigate = useNavigate()
  const { currentProject } = useWorkspace()
  const networkQuery = useNetwork(projectId, currentProject?.name || 'Project')
  const network = networkQuery.data
  const saveNetworkDraftMutation = useSaveNetworkDraft(network?.id, projectId)
  const promoteNetworkMutation = usePromoteNetwork(network?.id, projectId)
  const createNetworkSessionMutation = useCreateNetworkSession(network?.id, projectId)
  const networkSessionsQuery = useNetworkSessions(network?.id, projectId)
  const networkVersionsQuery = useNetworkVersions(network?.id, projectId)
  const agentsQuery = useAgents(projectId)
  const agents = useMemo<[Agent, Agent, Agent]>(() => {
    const source = agentsQuery.data?.length ? agentsQuery.data : fallbackAgents
    return [source[0] ?? fallbackAgents[0], source[1] ?? fallbackAgents[1], source[2] ?? fallbackAgents[2]]
  }, [agentsQuery.data])

  const [environment, setEnvironment] = useState<Environment>('draft')
  const [centerMode, setCenterMode] = useState<CenterMode>('canvas')
  const [panelTab, setPanelTab] = useState<PanelTab>('traces')
  const [showLeftPanel, setShowLeftPanel] = useState(true)
  const [selectedNode, setSelectedNode] = useState<NodeId>('coordinator')
  const [pendingNode, setPendingNode] = useState<NodeId | null>(null)
  const [compositionNode, setCompositionNode] = useState<AgentNodeId>('coordinator')
  const [inspectorContext, setInspectorContext] = useState<InspectorContext>('agent')
  const [networkSection, setNetworkSection] = useState<NetworkInspectorSection>('configuration')
  const [networkConfigSection, setNetworkConfigSection] = useState<NetworkConfigSection>('composition')
  const [expanded, setExpanded] = useState(false)
  const [showApi, setShowApi] = useState(false)
  const [releaseAction, setReleaseAction] = useState<ReleaseAction>(null)
  const [catalogOpen, setCatalogOpen] = useState(false)
  const [editorSelection, setEditorSelection] = useState<NetworkEditorSelection>({ type: 'network' })
  const [editorDefinition, setEditorDefinition] = useState<NetworkDefinition>(() => createEmptyNetworkDefinition())
  const [editorName, setEditorName] = useState('Project Network')
  const [editorDescription, setEditorDescription] = useState('')
  const [editorRevision, setEditorRevision] = useState(0)
  const [editorDirty, setEditorDirty] = useState(false)
  const [pendingRemoval, setPendingRemoval] = useState<NetworkDefinitionChange | null>(null)
  const [draftState, setDraftState] = useState(() => clone(DRAFT))
  const [stagingState, setStagingState] = useState(() => clone(STAGING))
  const [productionState, setProductionState] = useState(() => clone(PRODUCTION))
  const [dirtyAgentIds, setDirtyAgentIds] = useState<Set<string>>(() => new Set())
  const saveAgentActionRef = useRef<(() => Promise<boolean>) | null>(null)
  const hydratedRevisionRef = useRef<number | null>(null)

  const draftBindings = useMemo(() => bind(agents, draftState), [agents, draftState])
  const stagingBindings = useMemo(() => bind(agents, stagingState), [agents, stagingState])
  const productionBindings = useMemo(() => bind(agents, productionState), [agents, productionState])
  const visibleBindings = environment === 'draft' ? draftBindings : environment === 'staging' ? stagingBindings : productionBindings
  const editorIssues = useMemo(() => validateNetworkGraph(editorDefinition), [editorDefinition])
  const visibleDefinition = useMemo(() => {
    if (environment === 'draft') return editorDefinition
    const versionId = environment === 'staging' ? network?.staging_version_id : network?.production_version_id
    const version = networkVersionsQuery.data?.find((item) => item.id === versionId)
    return version ? normalizeNetworkDefinition(version.definition) : editorDefinition
  }, [editorDefinition, environment, network?.production_version_id, network?.staging_version_id, networkVersionsQuery.data])
  const visibleEditorIssues = useMemo(() => validateNetworkGraph(visibleDefinition), [visibleDefinition])
  const projectAgents = agentsQuery.data ?? []

  useEffect(() => {
    if (!network || hydratedRevisionRef.current === network.draft_revision) return
    if (editorDirty && hydratedRevisionRef.current !== null) return
    setEditorDefinition(normalizeNetworkDefinition(network.draft_definition))
    setEditorName(network.name)
    setEditorDescription(network.description)
    setEditorRevision(network.draft_revision)
    setEditorDirty(false)
    setEditorSelection({ type: 'network' })
    hydratedRevisionRef.current = network.draft_revision
  }, [editorDirty, network])

  const initialSessions = useMemo<NetworkSessionsByEnvironment>(() => ({
    draft: [],
    staging: [],
    production: [],
  }), [])
  const [sessionsByEnvironment, setSessionsByEnvironment] = useState(() => initialSessions)
  const [activeSessionIdByEnvironment, setActiveSessionIdByEnvironment] = useState<ActiveSessionByEnvironment>(() => ({
    draft: initialSessions.draft[0]?.id ?? null,
    staging: initialSessions.staging[0]?.id ?? null,
    production: initialSessions.production[0]?.id ?? null,
  }))
  const [traces, setTraces] = useState<NetworkTraceRecord[]>([])
  const [selectedTraceIdBySession, setSelectedTraceIdBySession] = useState<Record<string, string | null>>({})
  const [pinned, setPinned] = useState(false)

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
      compositionHash: hashComposition(currentSignature(
        item.environment,
        item.environment === 'staging' ? stagingBindings : productionBindings,
      )),
      status: item.status,
      createdAt: item.created_at,
      lastMessageAt: item.last_message_at ?? null,
      messageCount: 0,
      traceCount: 0,
      agentContexts: [],
    })
    const staging = remoteSessions.filter((item) => item.environment === 'staging').map(mapSession)
    const production = remoteSessions.filter((item) => item.environment === 'production').map(mapSession)
    setSessionsByEnvironment((current) => ({ ...current, staging, production }))
    setActiveSessionIdByEnvironment((current) => ({
      ...current,
      staging: staging.some((item) => item.id === current.staging) ? current.staging : staging[0]?.id ?? null,
      production: production.some((item) => item.id === current.production) ? current.production : production[0]?.id ?? null,
    }))
  }, [networkSessionsQuery.data, network?.id, projectId, stagingBindings, productionBindings])

  const persistDraft = async () => {
    if (!network || !projectId) throw new Error('Network is still loading')
    const errors = validateNetworkGraph(editorDefinition).filter((issue) => issue.severity === 'error')
    if (errors.length) throw new Error(errors[0].message)
    const saved = await saveNetworkDraftMutation.mutateAsync({
      expectedRevision: editorRevision,
      name: editorName,
      description: editorDescription,
      definition: editorDefinition,
    })
    hydratedRevisionRef.current = saved.draft_revision
    setEditorRevision(saved.draft_revision)
    setEditorDirty(false)
    return saved
  }

  const applyEditorChange = (change: NetworkDefinitionChange) => {
    if (environment !== 'draft') return
    setEditorDefinition((current) => applyNetworkDefinitionChange(current, change))
    setEditorDirty(true)
    if (change.type === 'remove-node' || change.type === 'remove-edge') setEditorSelection({ type: 'network' })
  }

  const changeEditor = (change: NetworkDefinitionChange) => {
    if (change.type === 'remove-node' || change.type === 'remove-edge') {
      setPendingRemoval(change)
      return
    }
    applyEditorChange(change)
  }

  const updateEditorMetadata = (metadata: { name?: string; description?: string }) => {
    if (environment !== 'draft') return
    if (metadata.name !== undefined) setEditorName(metadata.name)
    if (metadata.description !== undefined) setEditorDescription(metadata.description)
    setEditorDirty(true)
  }

  const addAgentToNetwork = (agent: Agent) => {
    const node = createNodeForAgent(agent, editorDefinition.nodes.length)
    changeEditor({ type: 'add-node', node })
    setEditorSelection({ type: 'node', id: node.id })
    setCatalogOpen(false)
    toast.success(`${agent.name} added to the Network`)
  }

  const saveDraft = async () => {
    try {
      await persistDraft()
      toast.success('Network Draft saved')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to save Network Draft')
    }
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault()
        if (environment === 'draft' && editorDirty) void saveDraft()
      }
    }
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!editorDirty) return
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('beforeunload', onBeforeUnload)
    }
  }, [editorDirty, environment, editorDefinition, editorDescription, editorName, editorRevision])

  const environmentSessions = sessionsByEnvironment[environment]
  const activeSessionId = activeSessionIdByEnvironment[environment]
  const activeSession = environmentSessions.find((session) => session.id === activeSessionId) ?? null
  const activeTraces = activeSession ? traces.filter((trace) => trace.networkSessionId === activeSession.id && trace.environment === environment) : []
  const selectedTraceId = activeSession ? selectedTraceIdBySession[activeSession.id] ?? null : null
  const selectedAgentNode = selectedNode === 'entry' || selectedNode === 'end' ? null : selectedNode
  const selectedAgentDraft = selectedAgentNode ? draftBindings[selectedAgentNode] : null
  const selectedNetworkBinding = selectedAgentNode ? visibleBindings[selectedAgentNode] : null
  const action = environment === 'draft' ? 'stage' : environment === 'staging' ? 'publish' : 'rollback'

  const changeEnvironment = (next: Environment) => {
    if (next === environment) return
    if (environment === 'draft' && (dirtyAgentIds.size > 0 || editorDirty)) {
      toast.warning('Save the Network and Agent Draft changes before switching environments')
      return
    }
    setEnvironment(next)
    setPinned(false)
    const nextSessionId = activeSessionIdByEnvironment[next]
    if (nextSessionId) setSelectedTraceIdBySession((current) => ({ ...current, [nextSessionId]: null }))
  }

  const commitNodeSelection = (node: NodeId) => {
    setSelectedNode(node)
    if (node === 'entry' || node === 'end') {
      setInspectorContext('network')
      setNetworkSection('configuration')
      setNetworkConfigSection(node === 'entry' ? 'general' : 'routing')
      return
    }
    setCompositionNode(node)
    setInspectorContext('agent')
  }

  const selectNode = (node: NodeId) => {
    const currentAgentId = selectedAgentDraft?.agent.id
    if (node !== selectedNode && currentAgentId && dirtyAgentIds.has(currentAgentId)) { setPendingNode(node); return }
    commitNodeSelection(node)
  }

  const updateSelectedAgentDirty = (dirty: boolean) => {
    const agentId = selectedAgentDraft?.agent.id
    if (!agentId) return
    setDirtyAgentIds((current) => { const next = new Set(current); if (dirty) next.add(agentId); else next.delete(agentId); return next })
  }

  const discardAndSwitch = () => {
    if (!pendingNode) return
    const currentAgentId = selectedAgentDraft?.agent.id
    if (currentAgentId) setDirtyAgentIds((current) => { const next = new Set(current); next.delete(currentAgentId); return next })
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

  const useVersion = (node: AgentNodeId, option: NetworkVersionOption) => {
    if (environment !== 'draft') return
    setDraftState((current) => ({ ...current, [node]: { ...current[node], source: option.source, ref: option.ref, version: option.version } }))
    toast.success(`${option.version} selected for this Network node`)
  }

  const stage = async () => {
    if (!network || !projectId) return
    try {
      await persistDraft()
      await promoteNetworkMutation.mutateAsync('staging')
      setEnvironment('staging')
      setPinned(false)
      toast.success('Immutable Network Staging version created')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to stage Network')
    }
  }

  const publish = async () => {
    if (!network || !projectId) return
    try {
      await persistDraft()
      await promoteNetworkMutation.mutateAsync('production')
      setEnvironment('production')
      setPinned(false)
      toast.success('Immutable Network Production release created')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to publish Network')
    }
  }

  const confirmRelease = () => {
    if (releaseAction === 'stage') void stage()
    else if (releaseAction === 'publish') void publish()
    else { setProductionState(clone(HISTORY)); toast.success('Historical Network Release reactivated') }
    setReleaseAction(null)
  }

  const selectSession = (sessionId: string) => {
    setActiveSessionIdByEnvironment((current) => ({ ...current, [environment]: sessionId }))
    setSelectedTraceIdBySession((current) => ({ ...current, [sessionId]: null }))
    setPinned(false)
  }

  const createSession = async () => {
    if (environment === 'draft') {
      toast.info('Stage the Network before starting a runtime session')
      return
    }
    if (!network || !projectId) return
    try {
      const created = await createNetworkSessionMutation.mutateAsync(environment)
      const session: NetworkSession = {
        id: created.id,
        projectId,
        networkId: network.id,
        title: created.title,
        environment: created.environment,
        networkVersion: created.network_version_id,
        compositionHash: hashComposition(currentSignature(
          created.environment,
          created.environment === 'staging' ? stagingBindings : productionBindings,
        )),
        status: created.status,
        createdAt: created.created_at,
        lastMessageAt: null,
        messageCount: 0,
        traceCount: 0,
        agentContexts: [],
      }
      setSessionsByEnvironment((current) => ({
        ...current,
        [environment]: [session, ...current[environment]],
      }))
      setActiveSessionIdByEnvironment((current) => ({ ...current, [environment]: session.id }))
      toast.success(`New ${environment} Network Session started`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to create Network Session')
    }
  }

  const selectTrace = (trace: NetworkTraceRecord) => {
    setSelectedTraceIdBySession((current) => ({ ...current, [trace.networkSessionId]: trace.id }))
  }
  const viewTraceOnCanvas = (trace: NetworkTraceRecord) => { selectTrace(trace); setCenterMode('canvas') }
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
      toast.error('Network execution failed. Trace opened for diagnosis.')
    } else {
      toast.success('Network execution completed', { description: `${trace.execution.path.length} hops · ${trace.durationMs}ms` })
    }
  }
  const openTraceFromChat = (execution: NetworkExecution) => {
    if (!activeSession) return
    const existing = activeTraces.find((trace) => trace.execution.id === execution.id || trace.traceId === execution.traceId)
    const trace = existing ?? createNetworkTraceRecord({ execution, environment, bindings: visibleBindings, networkSessionId: activeSession.id, title: 'Network execution', userMessage: 'Opened from the current Network Chat.', answer: 'Execution details from the current Network Chat.', agentContexts: activeSession.agentContexts, source: 'chat' })
    if (!existing) setTraces((current) => [trace, ...current])
    selectTrace(trace)
    setPanelTab('traces')
    setShowLeftPanel(true)
  }
  const handlePanelTab = (tab: PanelTab) => { if (showLeftPanel && panelTab === tab) { setShowLeftPanel(false); return }; setPanelTab(tab); setShowLeftPanel(true) }

  const networkBindingSummary: AgentNetworkBindingSummary | null = selectedNetworkBinding ? { source: selectedNetworkBinding.source, version: selectedNetworkBinding.version } : null
  const agentWorkspace = selectedAgentDraft && networkBindingSummary ? <NetworkAgentWorkspace key={selectedAgentDraft.agent.id} agent={selectedAgentDraft.agent} projectId={projectId!} networkBinding={networkBindingSummary} readOnly={environment !== 'draft'} onOpenComposition={() => { setCompositionNode(selectedAgentDraft.nodeId); setInspectorContext('network'); setNetworkSection('configuration'); setNetworkConfigSection('composition') }} onDirtyChange={updateSelectedAgentDirty} onRegisterSaveAction={(saveAction) => { saveAgentActionRef.current = saveAction }} /> : null
  const networkWorkspace = <NetworkInspectorWorkspace section={networkSection} configSection={networkConfigSection} environment={environment} bindings={visibleBindings} draftBindings={draftBindings} stagingBindings={stagingBindings} productionBindings={productionBindings} compositionNode={compositionNode} onSection={setNetworkSection} onConfigSection={setNetworkConfigSection} onCompositionNode={(node) => { setCompositionNode(node); setSelectedNode(node) }} onUse={useVersion} onStage={() => setReleaseAction('stage')} onPublish={() => setReleaseAction('publish')} onRollback={() => setReleaseAction('rollback')} onLoadNetwork={() => { setDraftState(clone(HISTORY)); setEnvironment('draft'); setInspectorContext('network'); setNetworkSection('configuration'); setNetworkConfigSection('composition'); toast.success('Historical Network Release loaded into Draft') }} />

  return (
    <div className="flex h-screen min-w-0 flex-col overflow-hidden bg-background">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-surface/80 px-3">
        <button type="button" onClick={() => navigate(`/organizations/${organizationId}/projects/${projectId}`)} className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted"><ChevronLeft className="h-4 w-4" /></button>
        <div><div className="flex items-center gap-2"><h1 className="text-sm font-semibold text-white">{currentProject?.name || 'Project'} Network</h1><Badge>{networkQuery.isLoading ? 'Loading' : 'Runtime'}</Badge></div><p className="text-[10px] text-muted">One Network per Project</p></div>
        <div className="ml-auto flex items-center gap-2">
          <div role="tablist" aria-label="Network environment" className="flex rounded-xl border border-border bg-background/35 p-1">{(['draft', 'staging', 'production'] as Environment[]).map((item) => <button key={item} type="button" role="tab" aria-selected={item === environment} onClick={() => changeEnvironment(item)} title={item === 'draft' ? 'Editable working composition' : item === 'staging' ? 'Read-only validation snapshot' : 'Immutable released composition'} className={cn('rounded-lg px-3 py-1.5 text-[10px] capitalize', item === environment ? item === 'production' ? 'bg-emerald-500/10 text-emerald-300' : item === 'staging' ? 'bg-indigo-500/10 text-indigo-300' : 'bg-primary/10 text-primary-light' : 'text-muted hover:text-white')}>{item}</button>)}</div>
          {environment === 'draft' ? <button type="button" disabled={!editorDirty || saveNetworkDraftMutation.isPending || editorIssues.some((issue) => issue.severity === 'error')} onClick={() => void saveDraft()} className={smallButton}>{saveNetworkDraftMutation.isPending ? 'Saving…' : editorDirty ? 'Save Draft' : 'Draft saved'}</button> : null}
          <button type="button" onClick={() => setCenterMode('chat')} className={smallButton}><MessageSquare className="mr-1 inline h-3.5 w-3.5" />Network Chat</button>
          <button type="button" onClick={() => setShowApi(true)} className={smallButton}><Code2 className="mr-1 inline h-3.5 w-3.5" />API Reference</button>
          <button type="button" onClick={() => setReleaseAction(action)} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white">{environment === 'draft' ? 'Stage Network' : environment === 'staging' ? 'Publish Release' : 'Rollback'}</button>
        </div>
      </header>
      <div className="relative flex h-8 shrink-0 items-center border-b border-border bg-surface/35 px-3 text-[10px] text-muted">
        <span className="inline-flex items-center gap-1.5">{environment === 'draft' ? <PencilLine className="h-3 w-3 text-primary-light" /> : <Lock className="h-3 w-3 text-muted" />}Viewing: <b className="text-slate-300">{networkLabel(environment)}</b> · {environment === 'draft' ? editorDirty ? 'Unsaved composition changes' : 'Draft saved' : 'Read-only composition · Chat and Traces available'}</span>
        <div className="absolute left-1/2 flex -translate-x-1/2 rounded-lg border border-border bg-background/45 p-0.5">{([['canvas', Workflow], ['chat', MessageSquare]] as Array<[CenterMode, LucideIcon]>).map(([mode, Icon]) => <button key={mode} type="button" onClick={() => setCenterMode(mode)} className={cn('flex items-center gap-1 rounded-md px-2.5 py-1 capitalize', centerMode === mode ? 'bg-primary/10 text-primary-light' : 'text-muted')}><Icon className="h-3 w-3" />{mode}</button>)}</div>
        <span className="ml-auto truncate">{activeSession ? `Session: ${activeSession.title}` : 'No session selected'} · Max depth {visibleDefinition.settings.max_depth} · Timeout {visibleDefinition.settings.timeout_seconds}s</span>
      </div>
      <div className="relative flex min-h-0 flex-1">
        <NetworkOperationsRail activeTab={showLeftPanel ? panelTab : null} onTabChange={handlePanelTab} />
        {showLeftPanel ? <NetworkOperationsPanel activeTab={panelTab} traces={activeTraces} session={activeSession} selectedTraceId={selectedTraceId} onSelectTrace={selectTrace} onViewCanvas={viewTraceOnCanvas} onOpenAgent={selectNode} /> : null}
        {agentsQuery.isLoading ? <div className="flex flex-1 items-center justify-center text-xs text-muted">Loading Network inventory</div> : centerMode === 'canvas' ? <NetworkGraphEditor definition={visibleDefinition} agents={projectAgents} issues={visibleEditorIssues} selection={editorSelection} readOnly={environment !== 'draft'} onChange={changeEditor} onSelect={setEditorSelection} onAddAgent={() => setCatalogOpen(true)} /> : activeSession ? <NetworkChatWorkspace key={activeSession.id} networkId={network?.id || ''} projectId={projectId!} networkName={`${currentProject?.name || 'Project'} Network`} environment={environment} bindings={visibleBindings} sessions={environmentSessions} activeSession={activeSession} pinned={pinned} onSelectSession={selectSession} onNewSession={() => createSession()} onPin={() => { setPinned(true); toast.info('Session kept on its previous composition') }} onRun={handleCompletedTrace} onSelectAgent={selectNode} onOpenTrace={openTraceFromChat} /> : <div className="flex min-w-0 flex-1 items-center justify-center p-6 text-center"><div><p className="text-sm font-medium text-white">No Network Session selected</p><button type="button" onClick={createSession} className="mt-3 rounded-lg bg-primary px-3 py-2 text-[11px] font-medium text-white">Create session</button></div></div>}
        {centerMode === 'canvas' ? <NetworkGraphInspector definition={visibleDefinition} agents={projectAgents} issues={visibleEditorIssues} selection={editorSelection} readOnly={environment !== 'draft'} name={editorName} description={editorDescription} onMetadata={updateEditorMetadata} onChange={changeEditor} /> : <NetworkInspectorShell context={inspectorContext} selectedAgentDraft={selectedAgentDraft} selectedNetworkBinding={selectedNetworkBinding} expanded={expanded} onContext={setInspectorContext} onExpand={() => setExpanded((value) => !value)} agentWorkspace={agentWorkspace} networkWorkspace={networkWorkspace} />}
        <NetworkAgentCatalogDrawer open={catalogOpen} agents={projectAgents} addedAgentIds={new Set(editorDefinition.nodes.map((node) => node.agent_id))} onClose={() => setCatalogOpen(false)} onAdd={addAgentToNetwork} />
      </div>
      {showApi ? <NetworkApiModal open={showApi} onClose={() => setShowApi(false)} projectId={projectId!} networkId={network?.id || ''} versionIds={{ staging: network?.staging_version_id, production: network?.production_version_id }} bindings={{ staging: stagingBindings, production: productionBindings }} /> : null}
      {releaseAction === 'stage' || releaseAction === 'publish' ? <NetworkPromotionDialog environment={releaseAction === 'stage' ? 'staging' : 'production'} definition={editorDefinition} agents={projectAgents} issues={editorIssues} pending={saveNetworkDraftMutation.isPending || promoteNetworkMutation.isPending} onClose={() => setReleaseAction(null)} onConfirm={confirmRelease} /> : null}
      {releaseAction === 'rollback' ? <NetworkReleaseModal action="rollback" draftBindings={draftBindings} stagingBindings={stagingBindings} onClose={() => setReleaseAction(null)} onConfirm={confirmRelease} /> : null}
      {pendingRemoval ? <NetworkRemoveDialog title={pendingRemoval.type === 'remove-node' ? 'Remove Agent from Network?' : 'Remove delegation?'} description={pendingRemoval.type === 'remove-node' ? 'The Agent remains available in the Project. Only this Network node will be removed.' : 'The source Agent will no longer be able to delegate work through this connection.'} impact={pendingRemoval.type === 'remove-node' ? `${editorDefinition.edges.filter((edge) => edge.source_node_id === pendingRemoval.nodeId || edge.target_node_id === pendingRemoval.nodeId).length} connected delegation(s) will also be removed. The graph must remain reachable before it can be saved.` : 'The target Agent may become unreachable from the entry point.'} onClose={() => setPendingRemoval(null)} onConfirm={() => { applyEditorChange(pendingRemoval); setPendingRemoval(null) }} /> : null}
      {pendingNode && selectedAgentDraft ? <UnsavedAgentSwitchDialog agentName={selectedAgentDraft.agent.name} onStay={() => setPendingNode(null)} onDiscard={discardAndSwitch} onSave={() => void saveAndSwitch()} /> : null}
    </div>
  )
}
