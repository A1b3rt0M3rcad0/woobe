import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { ArrowLeft, ExternalLink, LocateFixed, Lock } from 'lucide-react'

import type { Agent } from '@/features/agents/types'
import { cn } from '@/lib/utils'

import type { NetworkDefinition } from '../types'
import type { NetworkDefinitionChange, NetworkEditorIssue, NetworkEditorSelection } from '../editor/types'
import { NetworkGraphInspector } from './NetworkGraphInspector'
import { NetworkWorkspaceBootstrap } from './NetworkWorkspaceBootstrap'
import type { Environment, NetworkBinding } from './networkWorkspaceTypes'
import type { NetworkCenterMode, NetworkInspectionScope, NetworkInspectorContext } from './networkWorkspaceReducer'

interface NetworkContextInspectorProps {
  context: NetworkInspectorContext
  centerMode: NetworkCenterMode
  inspectionScope: NetworkInspectionScope
  inspectionLabel?: string | null
  inspectionKind?: 'run' | 'version' | null
  definition: NetworkDefinition
  environment?: Environment
  agents: Agent[]
  bindings: Record<string, NetworkBinding>
  issues: NetworkEditorIssue[]
  selection: NetworkEditorSelection
  readOnly: boolean
  name: string
  description: string
  agentWorkspace: ReactNode
  onContext: (context: NetworkInspectorContext) => void
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
  inspectionKind,
  definition,
  environment = 'draft',
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
  const showAgent = context === 'agent' && agentEnabled
  const inspecting = inspectionScope.type === 'run' && Boolean(inspectionLabel)
  const canLocate = selection.type !== 'network' && centerMode !== 'canvas'
  const workspaceBootstrapping = !readOnly && definition.nodes.length === 0

  if (workspaceBootstrapping) {
    const loading = <NetworkWorkspaceBootstrap networkName={name || 'Project Network'} />
    return typeof document === 'undefined' ? loading : createPortal(loading, document.body)
  }

  return (
    <aside className="absolute inset-y-0 right-0 z-40 flex min-h-0 w-[min(94vw,32.5rem)] max-w-[94vw] shrink-0 flex-col border-l border-border bg-surface/95 shadow-2xl shadow-black/30 xl:relative xl:z-auto xl:w-inspector-workspace xl:max-w-inspector-workspace xl:bg-surface/80 xl:shadow-none">
      {inspecting ? (
        <div className="flex shrink-0 items-center gap-2 border-b border-border bg-background/35 px-3 py-2 text-[9px] text-muted">
          <Lock className="h-3 w-3 shrink-0 text-primary-light" />
          <span className="truncate">{inspectionKind === 'run' ? 'Historical Run snapshot' : 'Immutable Network snapshot'} · {inspectionLabel}</span>
          <span className="ml-auto shrink-0 text-[8px] uppercase tracking-wide text-slate-400">Read-only</span>
        </div>
      ) : null}

      <div className="relative min-h-0 flex-1 overflow-hidden">
        {agentEnabled ? (
          <div className={cn('absolute inset-0 flex min-h-0 flex-col', !showAgent && 'invisible pointer-events-none')} aria-hidden={!showAgent}>
            <header className="shrink-0 border-b border-border p-4">
              <div className="flex items-center gap-2">
                <button type="button" onClick={() => onContext('network')} className="inline-flex items-center gap-1 text-[9px] font-medium text-muted hover:text-white">
                  <ArrowLeft className="h-3.5 w-3.5" />In Network
                </button>
                <span className="ml-auto rounded border border-border bg-background/45 px-1.5 py-0.5 text-[8px] uppercase tracking-wide text-muted">Shared Agent</span>
              </div>
              <div className="mt-3 flex min-w-0 items-start gap-3">
                <div className="min-w-0 flex-1">
                  <h2 className="truncate text-sm font-semibold text-white">{selectedAgent?.name ?? selectedNode?.label}</h2>
                  <p className="mt-1 truncate text-[9px] text-muted">Prompt, model, Tools, Knowledge and output contract</p>
                  {selectedBinding ? <p className="mt-1 truncate font-mono text-[8px] text-slate-300">{selectedBinding.source} · {selectedBinding.version}</p> : null}
                </div>
                {canLocate ? (
                  <button type="button" onClick={onLocateOnCanvas} className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-border bg-background/45 px-2.5 py-2 text-[9px] font-medium text-muted hover:border-primary/30 hover:text-white">
                    <LocateFixed className="h-3.5 w-3.5" />Locate
                  </button>
                ) : null}
                <button type="button" onClick={() => onContext('network')} className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-border bg-background/45 px-2.5 py-2 text-[9px] font-medium text-primary-light hover:border-primary/30 hover:text-white">
                  <ExternalLink className="h-3.5 w-3.5" />Node settings
                </button>
              </div>
            </header>
            <div className="relative min-h-0 flex-1 overflow-hidden">{agentWorkspace}</div>
          </div>
        ) : null}

        <div className={cn('absolute inset-0', showAgent && 'invisible pointer-events-none')} aria-hidden={showAgent}>
          <NetworkGraphInspector
            embedded
            definition={definition}
            environment={environment}
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
            onSelectNetwork={selection.type !== 'network' ? () => onSelect({ type: 'network' }) : undefined}
            onLocateOnCanvas={canLocate ? onLocateOnCanvas : undefined}
          />
        </div>
      </div>
    </aside>
  )
}
