import { useEffect, useMemo, useRef } from 'react'
import { useQueries } from '@tanstack/react-query'
import {
  Background,
  BackgroundVariant,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import './network-flow.css'
import { AlertTriangle, Bot, Crown, Lock, Plus, X } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@woobe/ui'

import { getRelease } from '@/features/agents/api'
import type { Agent } from '@/features/agents/types'
import { createUuid } from '@/lib/uuid'
import { cn } from '@/lib/utils'
import type { NetworkDefinition } from '../types'
import { canConnectNetworkNodes } from '../editor/networkGraphValidation'
import type { NetworkAgentNodeData, NetworkDefinitionChange, NetworkEditorIssue, NetworkEditorSelection } from '../editor/types'
import { NetworkBindingBadge } from './NetworkBindingBadge'
import { NetworkCanvasChrome } from './NetworkCanvasChrome'
import type { AgentNodeId, NetworkBinding } from './networkWorkspaceTypes'

type AgentFlowNode = Node<NetworkAgentNodeData, 'network-agent'>

type BindingDisplayCandidate = {
  nodeId: string
  agentId: string
  source: 'draft' | 'staging' | 'release'
  ref: string
  version: string
  dirty: boolean
}

function draftVersionFromInspection(inspectionLabel?: string | null) {
  const match = inspectionLabel?.match(/Draft\s+r(\d+)/i)
  return match ? `r${match[1]}` : 'current'
}

function AgentNode({ data, selected }: NodeProps<AgentFlowNode>) {
  const issue = data.issues.find((item) => item.severity === 'error')
  return (
    <article className={cn(
      'w-60 rounded-container border bg-surface/95 p-ui-md text-left transition-colors',
      selected
        ? 'border-primary ring-1 ring-primary/30'
        : data.activeInRun
          ? 'border-emerald-400/65 ring-1 ring-emerald-400/25'
          : issue
            ? 'border-red-500/45'
            : data.isRoot
              ? 'border-primary/55'
              : 'border-border hover:border-primary/35',
    )}>
      {!data.isRoot ? <Handle type="target" position={Position.Left} className="!h-3 !w-3 !border-2 !border-surface !bg-slate-400" /> : null}
      <Handle type="source" position={Position.Right} className="!h-3 !w-3 !border-2 !border-surface !bg-primary" />
      <div className="flex items-start gap-ui-md">
        <div className={cn('flex h-control w-control shrink-0 items-center justify-center rounded-control border', data.isRoot ? 'border-primary/35 bg-primary/10 text-primary-light' : 'border-border bg-background/60 text-slate-300')}>
          {data.isRoot ? <Crown className="h-icon w-icon" /> : <Bot className="h-icon w-icon" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-ui-sm">
            <p className="truncate font-sans text-product-small font-semibold text-white">{data.node.label}</p>
            {issue ? <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-red-400" /> : null}
          </div>
          <p className="mt-ui-xs truncate font-mono text-system-meta text-muted-foreground">{data.agent ? `${data.agent.provider}/${data.agent.model}` : 'Agent unavailable'}</p>
          {data.node.capability_description ? <p className="mt-ui-sm line-clamp-2 font-sans text-product-caption leading-4 text-slate-400">{data.node.capability_description}</p> : null}
        </div>
      </div>
      <div className="mt-ui-md space-y-ui-sm border-t border-border/70 pt-ui-sm">
        <div className="flex items-center justify-between gap-ui-sm">
          <span className={cn('rounded-technical border px-ui-xs py-ui-hairline font-mono text-system-meta font-semibold uppercase', data.activeInRun ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300' : data.isRoot ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-border text-muted-foreground')}>
            {data.activeInRun ? 'Executed' : data.isRoot ? 'Entry point' : 'Agent'}
          </span>
          <span className={cn('h-2 w-2 shrink-0 rounded-full', data.agent?.status === 'active' ? 'bg-emerald-400' : 'bg-amber-400')} />
        </div>
        {data.binding ? (
          <NetworkBindingBadge
            source={data.binding.source}
            version={data.binding.version}
            dirty={data.binding.dirty}
            className="w-full justify-center"
            title={`${data.binding.source === 'release' ? 'Agent Release' : data.binding.source === 'staging' ? 'Agent Staging snapshot' : 'Agent Draft'}: ${data.binding.version}${data.binding.dirty ? ' · unsaved changes' : ''}`}
          />
        ) : (
          <span className="block rounded-technical border border-red-500/30 bg-red-500/10 px-ui-sm py-ui-xs text-center font-mono text-system-meta font-semibold text-red-300">Binding unavailable</span>
        )}
      </div>
    </article>
  )
}

const nodeTypes: NodeTypes = { 'network-agent': AgentNode }

export function NetworkGraphEditor({
  definition,
  agents,
  bindings = {},
  issues,
  selection,
  readOnly,
  activePath = [],
  inspectionLabel,
  onChange,
  onSelect,
  onAddAgent,
  onClearInspection,
}: {
  definition: NetworkDefinition
  agents: Agent[]
  bindings?: Record<AgentNodeId, NetworkBinding>
  issues: NetworkEditorIssue[]
  selection: NetworkEditorSelection
  readOnly: boolean
  activePath?: string[]
  inspectionLabel?: string | null
  onChange: (change: NetworkDefinitionChange) => void
  onSelect: (selection: NetworkEditorSelection) => void
  onAddAgent: () => void
  onClearInspection?: () => void
}) {
  const agentsById = useMemo(() => new Map(agents.map((agent) => [agent.id, agent])), [agents])
  const activePathSet = useMemo(() => new Set(activePath), [activePath])
  const bindingCandidates = useMemo<BindingDisplayCandidate[]>(() => definition.nodes.map((node) => {
    const resolved = bindings[node.id]
    if (resolved) {
      return {
        nodeId: node.id,
        agentId: resolved.agent.id,
        source: resolved.source,
        ref: resolved.ref,
        version: resolved.version,
        dirty: resolved.dirty,
      }
    }
    return {
      nodeId: node.id,
      agentId: node.agent_id,
      source: node.binding.source,
      ref: node.binding.release_id ?? node.agent_id,
      version: node.binding.source === 'draft' ? draftVersionFromInspection(inspectionLabel) : 'pinned snapshot',
      dirty: false,
    }
  }), [bindings, definition.nodes, inspectionLabel])
  const unresolvedBindings = useMemo(() => bindingCandidates.filter((binding) => (
    binding.source !== 'draft'
    && Boolean(binding.ref)
    && (!binding.version || binding.version === 'pinned snapshot')
  )), [bindingCandidates])
  const releaseQueries = useQueries({
    queries: unresolvedBindings.map((binding) => ({
      queryKey: ['release', binding.agentId, binding.ref],
      queryFn: () => getRelease(binding.agentId, binding.ref),
      staleTime: 60_000,
    })),
  })
  const unresolvedBindingsKey = unresolvedBindings.map((binding) => `${binding.agentId}:${binding.ref}`).join('|')
  const releaseVersionSignature = releaseQueries.map((query, index) => `${unresolvedBindings[index]?.ref ?? ''}:${query.data?.version ?? ''}`).join('|')
  const releaseVersionByRef = useMemo(() => {
    const result = new Map<string, string>()
    releaseQueries.forEach((query, index) => {
      const binding = unresolvedBindings[index]
      if (binding && query.data?.version) result.set(binding.ref, query.data.version)
    })
    return result
  }, [releaseVersionSignature, unresolvedBindingsKey])
  const bindingCandidatesKey = bindingCandidates.map((binding) => `${binding.nodeId}:${binding.source}:${binding.ref}:${binding.version}:${binding.dirty ? '1' : '0'}`).join('|')
  const displayBindings = useMemo(() => Object.fromEntries(bindingCandidates.map((binding) => {
    const fallbackVersion = binding.source === 'draft'
      ? draftVersionFromInspection(inspectionLabel)
      : releaseVersionByRef.get(binding.ref) ?? 'pinned'
    const version = !binding.version || binding.version === 'current Draft' || binding.version === 'pinned snapshot'
      ? fallbackVersion
      : binding.version
    return [binding.nodeId, {
      source: binding.source,
      version,
      dirty: binding.dirty,
      ref: binding.ref,
    }]
  })), [bindingCandidatesKey, inspectionLabel, releaseVersionSignature])
  const derivedNodes = useMemo<AgentFlowNode[]>(() => definition.nodes.map((node) => ({
    id: node.id,
    type: 'network-agent',
    position: node.position,
    selected: selection.type === 'node' && selection.id === node.id,
    draggable: !readOnly,
    connectable: !readOnly,
    data: {
      node,
      agent: agentsById.get(node.agent_id),
      binding: displayBindings[node.id],
      isRoot: definition.root_node_id === node.id,
      readOnly,
      activeInRun: activePathSet.has(node.id),
      issues: issues.filter((issue) => issue.nodeId === node.id),
    },
  })), [activePathSet, agentsById, definition.nodes, definition.root_node_id, displayBindings, issues, readOnly, selection])
  const [nodes, setNodes, onNodesChange] = useNodesState<AgentFlowNode>(derivedNodes)
  const draggingRef = useRef(false)
  const viewportTouchedRef = useRef(false)

  useEffect(() => {
    if (draggingRef.current) return
    setNodes(derivedNodes)
  }, [derivedNodes, setNodes])
  const edges = useMemo<Edge[]>(() => definition.edges.map((edge) => {
    const active = activePath.some((nodeId, index) => nodeId === edge.source_node_id && activePath[index + 1] === edge.target_node_id)
    return {
      id: edge.id,
      source: edge.source_node_id,
      target: edge.target_node_id,
      selected: selection.type === 'edge' && selection.id === edge.id,
      markerEnd: { type: MarkerType.ArrowClosed, color: active ? '#34d399' : undefined },
      animated: active,
      style: { strokeWidth: active ? 2.5 : 2, stroke: active ? '#34d399' : undefined },
    }
  }), [activePath, definition.edges, selection])
  const fitKey = useMemo(() => [
    inspectionLabel ?? 'current',
    readOnly ? 'readonly' : 'editable',
    definition.root_node_id ?? 'no-root',
    definition.nodes.map((node) => node.id).sort().join(','),
    definition.edges.map((edge) => edge.id).sort().join(','),
  ].join(':'), [definition.edges, definition.nodes, definition.root_node_id, inspectionLabel, readOnly])

  const connect = (connection: Connection) => {
    if (readOnly || !connection.source || !connection.target) return
    const reason = canConnectNetworkNodes(definition, connection.source, connection.target)
    if (reason) {
      toast.error(reason)
      return
    }
    const id = createUuid()
    onChange({ type: 'add-edge', edge: { id, source_node_id: connection.source, target_node_id: connection.target } })
    onSelect({ type: 'edge', id })
  }

  return (
    <div data-network-canvas-shell className="relative min-h-0 flex-1 overflow-hidden bg-background">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        colorMode="dark"
        className="network-flow"
        onMoveStart={(event) => {
          if (event) viewportTouchedRef.current = true
        }}
        onNodesChange={onNodesChange}
        onConnect={connect}
        onNodeClick={(_, node) => onSelect({ type: 'node', id: node.id })}
        onEdgeClick={(_, edge) => onSelect({ type: 'edge', id: edge.id })}
        onPaneClick={() => onSelect({ type: 'network' })}
        onNodeDragStart={() => {
          draggingRef.current = true
          viewportTouchedRef.current = true
        }}
        onNodeDragStop={(_, node) => {
          draggingRef.current = false
          setNodes((current) => current.map((item) => item.id === node.id ? { ...item, position: node.position } : item))
          onChange({ type: 'move-node', nodeId: node.id, position: node.position })
        }}
        isValidConnection={(connection) => !canConnectNetworkNodes(definition, connection.source, connection.target)}
        nodesDraggable={!readOnly}
        nodesConnectable={!readOnly}
        elementsSelectable
        panOnDrag={[0, 1]}
        selectionOnDrag={false}
        deleteKeyCode={null}
        minZoom={0.25}
        maxZoom={1.8}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={28} size={1.2} color="rgba(100,116,139,.52)" />
        <NetworkCanvasChrome
          nodeCount={definition.nodes.length}
          edgeCount={definition.edges.length}
          fitKey={fitKey}
          viewportTouchedRef={viewportTouchedRef}
        />
        <MiniMap
          position="bottom-right"
          pannable
          zoomable
          inversePan
          zoomStep={5}
          bgColor="#020817"
          nodeStrokeColor="#64748b"
          nodeColor={(node) => activePathSet.has(node.id) ? '#10b981' : node.id === definition.root_node_id ? '#7c3aed' : '#334155'}
          maskColor="rgba(2,8,23,.52)"
          maskStrokeColor="rgba(96,165,250,.9)"
          maskStrokeWidth={1.5}
          ariaLabel="Network overview. Drag to navigate and scroll to zoom."
        />
      </ReactFlow>

      {inspectionLabel ? (
        <div className="absolute left-1/2 top-ui-md z-10 flex -translate-x-1/2 items-center gap-ui-sm rounded-control border border-border/80 bg-surface/95 px-ui-md py-ui-sm font-mono text-system-meta text-slate-300">
          <Lock className="h-3 w-3 text-primary-light" />
          <span>Snapshot: {inspectionLabel}</span>
          {onClearInspection ? <button type="button" onClick={onClearInspection} className="rounded-technical p-ui-xs text-muted-foreground transition-colors hover:bg-background/60 hover:text-white" aria-label="Return to current composition"><X className="h-3 w-3" /></button> : null}
        </div>
      ) : null}
      {!readOnly ? (
        <Button type="button" size="sm" onClick={onAddAgent} className="absolute right-ui-md top-ui-md z-10">
          <Plus className="h-icon-sm w-icon-sm" />Add Agent
        </Button>
      ) : null}
      {!definition.nodes.length ? (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-ui-xl">
          <div className="pointer-events-auto max-w-sm rounded-container border border-border bg-surface/95 p-ui-xl text-center">
            <div className="mx-auto flex h-control-lg w-control-lg items-center justify-center rounded-control border border-primary/25 bg-primary/10 text-primary-light"><Plus className="h-icon-lg w-icon-lg" /></div>
            <h2 className="mt-ui-lg font-sans text-heading-sm font-semibold text-white">Build your Network</h2>
            <p className="mt-ui-sm font-sans text-product-caption leading-5 text-muted-foreground">Add an Agent, make it the entry point, then connect the Agents it may delegate work to.</p>
            {!readOnly ? <Button type="button" size="sm" onClick={onAddAgent} className="mt-ui-lg">Add first Agent</Button> : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}
