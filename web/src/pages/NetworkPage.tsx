import { useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Activity, Bug, ChevronLeft, Code2, GitBranch, ListChecks, MessageSquare, Plus, Settings2, Workflow, type LucideIcon } from 'lucide-react'

import { useAgents } from '@/features/agents/hooks'
import type { Agent } from '@/features/agents/types'
import { NetworkAgentWorkspace, type AgentNetworkBindingSummary } from '@/features/network/components/NetworkAgentWorkspace'
import { NetworkChatWorkspace } from '@/features/network/components/NetworkChatWorkspace'
import { NetworkInspectorWorkspace, type NetworkConfigSection, type NetworkInspectorSection } from '@/features/network/components/NetworkInspectorWorkspace'
import type { AgentNodeId, ChatTarget, Environment, NetworkRun, NetworkSelection, NetworkVersionOption, NodeId } from '@/features/network/components/networkWorkspaceTypes'
import { NetworkCanvas } from '@/features/network/components/NetworkCanvas'
import { Badge, Operations, type PanelTab } from '@/features/network/components/NetworkOperations'
import { NetworkApiModal } from '@/features/network/components/NetworkApiModal'
import { NetworkInspectorShell, type InspectorContext } from '@/features/network/components/NetworkInspectorShell'
import { NetworkReleaseModal, UnsavedAgentSwitchDialog, type ReleaseAction } from '@/features/network/components/NetworkReleaseDialogs'
import { DRAFT, HISTORY, PRODUCTION, STAGING, bind, clone, fallbackAgents, runHistory, signature } from '@/features/network/components/networkPageData'
import { useWorkspace } from '@/features/workspace/WorkspaceProvider'
import { cn } from '@/lib/utils'

type CenterMode = 'canvas' | 'chat'
const smallButton = 'rounded-lg border border-border/80 bg-background/40 px-2.5 py-1.5 text-[10px] font-medium text-muted hover:border-primary/30 hover:text-white disabled:cursor-not-allowed disabled:opacity-45'

export default function NetworkPage() {
  const { organizationId, projectId } = useParams<{ organizationId: string; projectId: string }>()
  const navigate = useNavigate()
  const { currentProject } = useWorkspace()
  const agentsQuery = useAgents(projectId)
  const agents = useMemo<[Agent, Agent, Agent]>(() => {
    const source = agentsQuery.data?.length ? agentsQuery.data : fallbackAgents
    return [source[0] ?? fallbackAgents[0], source[1] ?? fallbackAgents[1], source[2] ?? fallbackAgents[2]]
  }, [agentsQuery.data])

  const [environment, setEnvironment] = useState<Environment>('draft')
  const [centerMode, setCenterMode] = useState<CenterMode>('canvas')
  const [chatTarget, setChatTarget] = useState<ChatTarget>('draft')
  const [panelTab, setPanelTab] = useState<PanelTab>('runs')
  const [selectedNode, setSelectedNode] = useState<NodeId>('coordinator')
  const [pendingNode, setPendingNode] = useState<NodeId | null>(null)
  const [compositionNode, setCompositionNode] = useState<AgentNodeId>('coordinator')
  const [inspectorContext, setInspectorContext] = useState<InspectorContext>('agent')
  const [networkSection, setNetworkSection] = useState<NetworkInspectorSection>('configuration')
  const [networkConfigSection, setNetworkConfigSection] = useState<NetworkConfigSection>('composition')
  const [expanded, setExpanded] = useState(false)
  const [showApi, setShowApi] = useState(false)
  const [releaseAction, setReleaseAction] = useState<ReleaseAction>(null)
  const [draftState, setDraftState] = useState(() => clone(DRAFT))
  const [stagingState, setStagingState] = useState(() => clone(STAGING))
  const [productionState, setProductionState] = useState(() => clone(PRODUCTION))
  const [dirtyAgentIds, setDirtyAgentIds] = useState<Set<string>>(() => new Set())
  const saveAgentActionRef = useRef<(() => Promise<boolean>) | null>(null)

  const draftBindings = useMemo(() => bind(agents, draftState), [agents, draftState])
  const stagingBindings = useMemo(() => bind(agents, stagingState), [agents, stagingState])
  const productionBindings = useMemo(() => bind(agents, productionState), [agents, productionState])
  const historyBindings = useMemo(() => bind(agents, HISTORY), [agents])
  const visibleBindings = environment === 'draft' ? draftBindings : environment === 'staging' ? stagingBindings : productionBindings
  const chatBindings = chatTarget === 'draft' ? draftBindings : chatTarget === 'staging' ? stagingBindings : chatTarget === 'production' ? productionBindings : historyBindings
  const [run, setRun] = useState<NetworkRun>(runHistory[0])
  const [sessionSignature, setSessionSignature] = useState(() => signature('draft', bind(fallbackAgents, DRAFT)))
  const [pinned, setPinned] = useState(false)
  const selectedAgentNode = selectedNode === 'entry' || selectedNode === 'end' ? null : selectedNode
  const selectedAgentDraft = selectedAgentNode ? draftBindings[selectedAgentNode] : null
  const selectedNetworkBinding = selectedAgentNode ? visibleBindings[selectedAgentNode] : null
  const action = environment === 'draft' ? 'stage' : environment === 'staging' ? 'publish' : 'rollback'

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
    if (node !== selectedNode && currentAgentId && dirtyAgentIds.has(currentAgentId)) {
      setPendingNode(node)
      return
    }
    commitNodeSelection(node)
  }

  const updateSelectedAgentDirty = (dirty: boolean) => {
    const agentId = selectedAgentDraft?.agent.id
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
    const currentAgentId = selectedAgentDraft?.agent.id
    if (currentAgentId) setDirtyAgentIds((current) => { const next = new Set(current); next.delete(currentAgentId); return next })
    const target = pendingNode
    setPendingNode(null)
    commitNodeSelection(target)
  }

  const saveAndSwitch = async () => {
    if (!pendingNode || !saveAgentActionRef.current) return
    if (!await saveAgentActionRef.current()) return
    const target = pendingNode
    setPendingNode(null)
    commitNodeSelection(target)
  }

  const useVersion = (node: AgentNodeId, option: NetworkVersionOption) => {
    if (environment !== 'draft') return
    setDraftState((current) => ({ ...current, [node]: { ...current[node], source: option.source, ref: option.ref, version: option.version } }))
    toast.success(`${option.version} selected for this Network node`)
  }

  const stage = () => {
    const next = Object.fromEntries((Object.entries(draftState) as Array<[AgentNodeId, NetworkSelection]>).map(([node, item]) => [node, item.source === 'draft' ? { ...item, source: 'staging' as const, ref: `staging-${node}-new`, version: node === 'coordinator' ? 'v0.5.20260713.03' : node === 'billing' ? 'v0.4.20260713.02' : 'v0.3.20260713.01', dirty: false } : { ...item, dirty: false }])) as Record<AgentNodeId, NetworkSelection>
    setStagingState(next)
    setEnvironment('staging')
    setChatTarget('staging')
    toast.success('Network and required Agent Drafts promoted to Staging')
  }

  const publish = () => {
    const next = Object.fromEntries((Object.entries(stagingState) as Array<[AgentNodeId, NetworkSelection]>).map(([node, item]) => [node, item.source === 'release' ? { ...item } : { ...item, source: 'release' as const, ref: `release-${node}-new`, version: node === 'coordinator' ? 'v0.6.20260713.00' : node === 'billing' ? 'v0.5.20260713.00' : 'v0.4.20260713.00' }])) as Record<AgentNodeId, NetworkSelection>
    setProductionState(next)
    setEnvironment('production')
    setChatTarget('production')
    toast.success('Immutable Network Release created')
  }

  const confirmRelease = () => {
    if (releaseAction === 'stage') stage()
    else if (releaseAction === 'publish') publish()
    else {
      setProductionState(clone(HISTORY))
      toast.success('Historical Network Release reactivated')
    }
    setReleaseAction(null)
  }

  const networkBindingSummary: AgentNetworkBindingSummary | null = selectedNetworkBinding ? { source: selectedNetworkBinding.source, version: selectedNetworkBinding.version } : null
  const agentWorkspace = selectedAgentDraft && networkBindingSummary ? <NetworkAgentWorkspace key={selectedAgentDraft.agent.id} agent={selectedAgentDraft.agent} projectId={projectId!} networkBinding={networkBindingSummary} onOpenComposition={() => { setCompositionNode(selectedAgentDraft.nodeId); setInspectorContext('network'); setNetworkSection('configuration'); setNetworkConfigSection('composition') }} onDirtyChange={updateSelectedAgentDirty} onRegisterSaveAction={(saveAction) => { saveAgentActionRef.current = saveAction }} /> : null
  const networkWorkspace = <NetworkInspectorWorkspace section={networkSection} configSection={networkConfigSection} environment={environment} bindings={visibleBindings} draftBindings={draftBindings} stagingBindings={stagingBindings} productionBindings={productionBindings} compositionNode={compositionNode} onSection={setNetworkSection} onConfigSection={setNetworkConfigSection} onCompositionNode={(node) => { setCompositionNode(node); setSelectedNode(node) }} onUse={useVersion} onStage={() => setReleaseAction('stage')} onPublish={() => setReleaseAction('publish')} onRollback={() => setReleaseAction('rollback')} onLoadNetwork={() => { setDraftState(clone(HISTORY)); setEnvironment('draft'); setInspectorContext('network'); setNetworkSection('configuration'); setNetworkConfigSection('composition'); toast.success('Historical Network Release loaded into Draft') }} />

  return (
    <div className="flex h-screen min-w-[1180px] flex-col overflow-hidden bg-background">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-surface/80 px-3"><button onClick={() => navigate(`/organizations/${organizationId}/projects/${projectId}`)} className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted"><ChevronLeft className="h-4 w-4" /></button><div><div className="flex items-center gap-2"><h1 className="text-sm font-semibold text-white">{currentProject?.name || 'Project'} Network</h1><Badge>Prototype</Badge></div><p className="text-[9px] text-muted">One Network per Project</p></div><div className="ml-auto flex items-center gap-2"><div className="flex rounded-xl border border-border bg-background/35 p-1">{(['draft', 'staging', 'production'] as Environment[]).map((item) => <button key={item} onClick={() => setEnvironment(item)} className={cn('rounded-lg px-3 py-1.5 text-[10px] capitalize', item === environment ? item === 'production' ? 'bg-emerald-500/10 text-emerald-300' : item === 'staging' ? 'bg-indigo-500/10 text-indigo-300' : 'bg-primary/10 text-primary-light' : 'text-muted')}>{item}</button>)}</div><button onClick={() => { setCenterMode('chat'); setChatTarget(environment); setPinned(false) }} className={smallButton}><MessageSquare className="mr-1 inline h-3.5 w-3.5" />Network Chat</button><button onClick={() => setShowApi(true)} className={smallButton}><Code2 className="mr-1 inline h-3.5 w-3.5" />API Reference</button><button onClick={() => setReleaseAction(action)} className="rounded-lg bg-primary px-3 py-2 text-[10px] font-semibold text-white">{environment === 'draft' ? 'Stage Network' : environment === 'staging' ? 'Publish Release' : 'Rollback'}</button></div></header>
      <div className="relative flex h-8 shrink-0 items-center border-b border-border bg-surface/35 px-3 text-[9px] text-muted"><span>Viewing: <b className="text-slate-300">{environment === 'draft' ? 'Working Draft Revision 29' : environment === 'staging' ? 'Network Staging v0.12' : 'Network Release v0.10'}</b> · {environment === 'draft' ? 'Network configuration enabled' : 'exact read-only composition'}</span><div className="absolute left-1/2 flex -translate-x-1/2 rounded-lg border border-border bg-background/45 p-0.5">{([['canvas', Workflow], ['chat', MessageSquare]] as Array<[CenterMode, LucideIcon]>).map(([mode, Icon]) => <button key={mode} onClick={() => setCenterMode(mode)} className={cn('flex items-center gap-1 rounded-md px-2.5 py-1 capitalize', centerMode === mode ? 'bg-primary/10 text-primary-light' : 'text-muted')}><Icon className="h-3 w-3" />{mode}</button>)}</div><span className="ml-auto">Max hops 8 · Timeout 90s</span></div>
      <div className="relative flex min-h-0 flex-1"><nav className="flex w-14 shrink-0 flex-col items-center gap-2 border-r border-border bg-surface/75 p-2">{([['runs', Activity], ['trace', GitBranch], ['debug', Bug], ['validation', ListChecks]] as Array<[PanelTab, LucideIcon]>).map(([tab, Icon]) => <button key={tab} onClick={() => setPanelTab(tab)} className={cn('flex h-10 w-10 items-center justify-center rounded-xl border', panelTab === tab ? 'border-primary/35 bg-primary/10 text-primary-light' : 'border-transparent text-muted')}><Icon className="h-4 w-4" /></button>)}<button className="mt-auto flex h-10 w-10 items-center justify-center rounded-xl border border-border text-muted"><Plus className="h-4 w-4" /></button><button className="flex h-10 w-10 items-center justify-center text-muted"><Settings2 className="h-4 w-4" /></button></nav><aside className="hidden w-[330px] shrink-0 border-r border-border bg-surface/65 2xl:block"><Operations tab={panelTab} run={run} draftBindings={draftBindings} /></aside>{agentsQuery.isLoading ? <div className="flex flex-1 items-center justify-center text-xs text-muted">Loading Network inventory</div> : centerMode === 'canvas' ? <NetworkCanvas bindings={visibleBindings} run={run} selectedNode={selectedNode} environment={environment} dirtyAgentIds={dirtyAgentIds} onSelect={selectNode} /> : <NetworkChatWorkspace networkName={`${currentProject?.name || 'Project'} Network`} target={chatTarget} bindings={chatBindings} sessionSignature={sessionSignature} pinned={pinned} onTarget={(target) => { setChatTarget(target); setPinned(false) }} onNewSession={(next) => { setSessionSignature(next); setPinned(false); toast.success('New Network session started') }} onPin={() => { setPinned(true); toast.info('Session kept on previous composition') }} onRun={(next) => { setRun(next); setPanelTab('trace') }} onSelectAgent={(node) => selectNode(node)} onOpenTrace={(execution) => { setRun({ id: execution.id, title: 'Network execution', environment: execution.environment, status: execution.status, duration: `${(execution.durationMs / 1000).toFixed(2)}s`, cost: `$${execution.costUsd.toFixed(3)}`, path: execution.path, traceId: execution.traceId }); setPanelTab('trace') }} />}<NetworkInspectorShell context={inspectorContext} selectedAgentDraft={selectedAgentDraft} selectedNetworkBinding={selectedNetworkBinding} expanded={expanded} onContext={setInspectorContext} onExpand={() => setExpanded((value) => !value)} agentWorkspace={agentWorkspace} networkWorkspace={networkWorkspace} /></div>
      {showApi ? <NetworkApiModal open={showApi} onClose={() => setShowApi(false)} bindings={{ staging: stagingBindings, production: productionBindings }} /> : null}
      {releaseAction ? <NetworkReleaseModal action={releaseAction} draftBindings={draftBindings} stagingBindings={stagingBindings} onClose={() => setReleaseAction(null)} onConfirm={confirmRelease} /> : null}
      {pendingNode && selectedAgentDraft ? <UnsavedAgentSwitchDialog agentName={selectedAgentDraft.agent.name} onStay={() => setPendingNode(null)} onDiscard={discardAndSwitch} onSave={() => void saveAndSwitch()} /> : null}
    </div>
  )
}
