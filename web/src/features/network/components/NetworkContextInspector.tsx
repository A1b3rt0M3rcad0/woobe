import type { ReactNode } from 'react'
import { Bot, LocateFixed, Workflow } from 'lucide-react'

import type { Agent } from '@/features/agents/types'
import { cn } from '@/lib/utils'

import type { NetworkDefinition } from '../types'
import type { NetworkDefinitionChange, NetworkEditorIssue, NetworkEditorSelection } from '../editor/types'
import { NetworkGraphInspector } from './NetworkGraphInspector'
import type { NetworkBinding } from './networkWorkspaceTypes'
import type { NetworkCenterMode, NetworkInspectionScope, NetworkInspectorContext } from './networkWorkspaceReducer'

interface NetworkContextInspectorProps {
  context: NetworkInspectorContext
  centerMode: NetworkCenterMode
  inspectionScope: NetworkInspectionScope
  inspectionLabel?: string | null
  definition: NetworkDefinition
  agents: Agent[]
  bindings: Record<string, NetworkBinding>
  issues: NetworkEditorIssue[]
  selection: NetworkEditorSelection
  readOnly: boolean
  expanded?: boolean
  name: string
  description: string
  agentWorkspace: ReactNode
  onContext: (context: NetworkInspectorContext) => void
  onExpand?: () => void
  onLocateOnCanvas: () => void
  onSelect: (selection: NetworkEditorSelection) => void
  onMetadata: (metadata: { name?: string; description?: string }) => void
  onChange: (change: NetworkDefinitionChange) => void
}

export function NetworkContextInspector({
  context,
  centerMode,
  inspectionScope,
  inspectionLabel,
  definition,
  agents,
  bindings,
  issues,
  selection,
  readOnly,
  name,
  description,
  agentWorkspace,
  onContext,
  onLocateOnCanvas,
  onSelect,
  onMetadata,
  onChange,
}: NetworkContextInspectorProps) {
  const selectedNode = selection.type === 'node'
    ? definition.nodes.find((node) => node.id === selection.id) ?? null
    : null
  const selectedAgent = selectedNode
    ? agents.find((agent) => agent.id === selectedNode.agent_id) ?? null
    : null
  const selectedBinding = selectedNode ? bindings[selectedNode.id] ?? null : null
  const agentEnabled = Boolean(selectedNode && selectedAgent && selectedBinding)

  return (
    <aside className="absolute inset-y-0 right-0 z-40 flex min-h-0 w-[min(94vw,520px)] shrink-0 flex-col border-l border-border bg-surface/95 shadow-2xl shadow-black/30 xl:relative xl:z-auto xl:w-[520px] xl:bg-surface/80 xl:shadow-none">
      <div className="flex shrink-0 items-center gap-1 border-b border-border bg-background/20 p-1.5">
        <button
          type="button"
          disabled={!agentEnabled}
          onClick={() => onContext('agent')}
          className={cn(
            'flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-[11px] font-medium',
            context === 'agent'
              ? 'border-primary/30 bg-primary/10 text-primary-light'
              : 'border-transparent text-muted hover:border-border/70 hover:text-white',
            !agentEnabled && 'cursor-not-allowed opacity-40',
          )}
        >
          <Bot className="h-3.5 w-3.5" />Agent
        </button>
        <button
          type="button"
          onClick={() => onContext('network')}
          className={cn(
            'flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-[11px] font-medium',
            context === 'network'
              ? 'border-primary/30 bg-primary/10 text-primary-light'
              : 'border-transparent text-muted hover:border-border/70 hover:text-white',
          )}
        >
          <Workflow className="h-3.5 w-3.5" />Network
        </button>
      </div>

      <div className="shrink-0 border-b border-border/80 bg-surface/70 px-3 py-2.5">
        <div className="flex items-center gap-2">
          <select
            value={selectedNode?.id ?? ''}
            onChange={(event) => onSelect(event.target.value ? { type: 'node', id: event.target.value } : { type: 'network' })}
            className="min-w-0 flex-1 rounded-lg border border-border bg-background/50 px-2.5 py-2 text-[10px] text-white outline-none focus:border-primary/40"
            aria-label="Selected Network Agent"
          >
            <option value="">Network context</option>
            {definition.nodes.map((node) => {
              const agent = agents.find((item) => item.id === node.agent_id)
              return <option key={node.id} value={node.id}>{node.label} · {agent?.name ?? 'Agent unavailable'}</option>
            })}
          </select>
          {selectedNode && centerMode !== 'canvas' ? (
            <button type="button" onClick={onLocateOnCanvas} className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-border bg-background/45 px-2.5 py-2 text-[9px] font-medium text-muted hover:border-primary/30 hover:text-white">
              <LocateFixed className="h-3.5 w-3.5" />Locate
            </button>
          ) : null}
        </div>
        <div className="mt-2 flex min-w-0 items-center gap-2 text-[9px] text-muted">
          <span className="truncate">{selectedNode ? `${selectedNode.label} · ${selectedAgent?.name ?? 'Agent unavailable'}` : name}</span>
          {selectedBinding ? <span className="ml-auto shrink-0 rounded border border-border bg-background/50 px-1.5 py-0.5 font-mono text-[8px] text-slate-300">{selectedBinding.source} · {selectedBinding.version}</span> : null}
        </div>
        {inspectionScope.type === 'run' ? (
          <div className="mt-2 rounded-lg border border-amber-500/25 bg-amber-500/5 px-2.5 py-2 text-[9px] leading-4 text-amber-100">
            Inspecting Network Run {inspectionLabel ?? inspectionScope.runId}. Configuration is read-only and resolved from the execution snapshot when available.
          </div>
        ) : null}
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {context === 'agent' && agentEnabled ? agentWorkspace : (
          <NetworkGraphInspector
            embedded
            definition={definition}
            agents={agents}
            bindings={bindings}
            issues={issues}
            selection={selection}
            readOnly={readOnly}
            name={name}
            description={description}
            onMetadata={onMetadata}
            onChange={onChange}
            onOpenAgent={agentEnabled ? () => onContext('agent') : undefined}
          />
        )}
      </div>
    </aside>
  )
}
