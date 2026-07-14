import { useMemo } from 'react'
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { AlertTriangle, Bot, Crown, Plus, Workflow } from 'lucide-react'
import { toast } from 'sonner'

import type { Agent } from '@/features/agents/types'
import { cn } from '@/lib/utils'
import type { NetworkDefinition } from '../types'
import { canConnectNetworkNodes } from '../editor/networkGraphValidation'
import type { NetworkAgentNodeData, NetworkDefinitionChange, NetworkEditorIssue, NetworkEditorSelection } from '../editor/types'

type AgentFlowNode = Node<NetworkAgentNodeData, 'network-agent'>

function AgentNode({ data, selected }: NodeProps<AgentFlowNode>) {
  const issue = data.issues.find((item) => item.severity === 'error')
  return (
    <article className={cn(
      'w-60 rounded-2xl border bg-surface/95 p-3.5 text-left shadow-xl shadow-black/20 transition',
      selected ? 'border-primary ring-4 ring-primary/10' : issue ? 'border-red-500/45' : data.isRoot ? 'border-primary/55' : 'border-border hover:border-primary/35',
    )}>
      {!data.isRoot ? <Handle type="target" position={Position.Left} className="!h-3 !w-3 !border-2 !border-surface !bg-slate-400" /> : null}
      <Handle type="source" position={Position.Right} className="!h-3 !w-3 !border-2 !border-surface !bg-primary" />
      <div className="flex items-start gap-3">
        <div className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border', data.isRoot ? 'border-primary/35 bg-primary/10 text-primary-light' : 'border-border bg-background/60 text-slate-300')}>
          {data.isRoot ? <Crown className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-xs font-semibold text-white">{data.node.label}</p>
            {issue ? <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-red-400" /> : null}
          </div>
          <p className="mt-1 truncate text-[9px] text-muted">{data.agent ? `${data.agent.provider}/${data.agent.model}` : 'Agent unavailable'}</p>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between border-t border-border/70 pt-2">
        <span className={cn('rounded-md border px-1.5 py-0.5 text-[8px] font-semibold uppercase', data.isRoot ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-border text-muted')}>
          {data.isRoot ? 'Entry point' : 'Agent'}
        </span>
        <span className={cn('h-2 w-2 rounded-full', data.agent?.status === 'active' ? 'bg-emerald-400' : 'bg-amber-400')} />
      </div>
    </article>
  )
}

const nodeTypes: NodeTypes = { 'network-agent': AgentNode }

export function NetworkGraphEditor({
  definition,
  agents,
  issues,
  selection,
  readOnly,
  onChange,
  onSelect,
  onAddAgent,
}: {
  definition: NetworkDefinition
  agents: Agent[]
  issues: NetworkEditorIssue[]
  selection: NetworkEditorSelection
  readOnly: boolean
  onChange: (change: NetworkDefinitionChange) => void
  onSelect: (selection: NetworkEditorSelection) => void
  onAddAgent: () => void
}) {
  const agentsById = useMemo(() => new Map(agents.map((agent) => [agent.id, agent])), [agents])
  const nodes = useMemo<AgentFlowNode[]>(() => definition.nodes.map((node) => ({
    id: node.id,
    type: 'network-agent',
    position: node.position,
    selected: selection.type === 'node' && selection.id === node.id,
    draggable: !readOnly,
    connectable: !readOnly,
    data: {
      node,
      agent: agentsById.get(node.agent_id),
      isRoot: definition.root_node_id === node.id,
      readOnly,
      issues: issues.filter((issue) => issue.nodeId === node.id),
    },
  })), [agentsById, definition.nodes, definition.root_node_id, issues, readOnly, selection])
  const edges = useMemo<Edge[]>(() => definition.edges.map((edge) => ({
    id: edge.id,
    source: edge.source_node_id,
    target: edge.target_node_id,
    selected: selection.type === 'edge' && selection.id === edge.id,
    markerEnd: { type: MarkerType.ArrowClosed },
    style: { strokeWidth: 2 },
  })), [definition.edges, selection])

  const connect = (connection: Connection) => {
    if (readOnly || !connection.source || !connection.target) return
    const reason = canConnectNetworkNodes(definition, connection.source, connection.target)
    if (reason) {
      toast.error(reason)
      return
    }
    const id = crypto.randomUUID()
    onChange({ type: 'add-edge', edge: { id, source_node_id: connection.source, target_node_id: connection.target } })
    onSelect({ type: 'edge', id })
  }

  return (
    <div className="relative min-h-0 flex-1 overflow-hidden bg-background">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onConnect={connect}
        onNodeClick={(_, node) => onSelect({ type: 'node', id: node.id })}
        onEdgeClick={(_, edge) => onSelect({ type: 'edge', id: edge.id })}
        onPaneClick={() => onSelect({ type: 'network' })}
        onNodeDragStop={(_, node) => onChange({ type: 'move-node', nodeId: node.id, position: node.position })}
        isValidConnection={(connection) => !canConnectNetworkNodes(definition, connection.source, connection.target)}
        nodesDraggable={!readOnly}
        nodesConnectable={!readOnly}
        elementsSelectable
        deleteKeyCode={null}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        minZoom={0.25}
        maxZoom={1.8}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={22} size={1} color="rgba(100,116,139,.22)" />
        <Controls position="bottom-left" showInteractive={false} />
        <MiniMap position="bottom-right" pannable zoomable nodeColor={(node) => node.id === definition.root_node_id ? '#7c3aed' : '#334155'} maskColor="rgba(2,6,23,.78)" />
      </ReactFlow>

      <div className="pointer-events-none absolute left-4 top-4 z-10 flex items-center gap-2 rounded-xl border border-border bg-surface/90 px-3 py-2 text-[10px] text-muted shadow-lg">
        <Workflow className="h-3.5 w-3.5 text-primary-light" />
        <span><b className="text-white">{definition.nodes.length}</b> Agents · <b className="text-white">{definition.edges.length}</b> delegations</span>
      </div>
      {!readOnly ? (
        <button type="button" onClick={onAddAgent} className="absolute right-4 top-4 z-10 flex items-center gap-2 rounded-xl bg-primary px-3 py-2 text-[10px] font-semibold text-white shadow-lg shadow-primary/20">
          <Plus className="h-3.5 w-3.5" />Add Agent
        </button>
      ) : null}
      {!definition.nodes.length ? (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-8">
          <div className="pointer-events-auto max-w-sm rounded-2xl border border-border bg-surface/95 p-7 text-center shadow-2xl">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-primary/25 bg-primary/10 text-primary-light"><Workflow className="h-5 w-5" /></div>
            <h2 className="mt-4 text-sm font-semibold text-white">Build your Network</h2>
            <p className="mt-2 text-[10px] leading-5 text-muted">Add an Agent, make it the entry point, then connect the Agents it may delegate work to.</p>
            {!readOnly ? <button type="button" onClick={onAddAgent} className="mt-5 rounded-xl bg-primary px-4 py-2.5 text-[10px] font-semibold text-white">Add first Agent</button> : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}

