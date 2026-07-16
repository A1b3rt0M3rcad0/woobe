import { AlertTriangle, ChevronLeft } from 'lucide-react'

import type { Agent } from '@/features/agents/types'

import type { NetworkDefinition } from '../types'
import type { NetworkDefinitionChange, NetworkEditorIssue, NetworkEditorSelection } from '../editor/types'
import { NetworkEdgeInspector } from './NetworkEdgeInspector'
import { NetworkNodeInspector } from './NetworkNodeInspector'
import { NetworkOverviewInspector } from './NetworkOverviewInspector'
import type { NetworkBinding } from './networkWorkspaceTypes'

export function NetworkGraphInspector({
  definition,
  agents,
  bindings,
  issues,
  selection,
  readOnly,
  name,
  description,
  embedded = false,
  onMetadata,
  onChange,
  onOpenAgent,
  onSelectNetwork,
  onLocateOnCanvas,
}: {
  definition: NetworkDefinition
  agents: Agent[]
  bindings?: Record<string, NetworkBinding>
  issues: NetworkEditorIssue[]
  selection: NetworkEditorSelection
  readOnly: boolean
  name: string
  description: string
  embedded?: boolean
  onMetadata: (metadata: { name?: string; description?: string }) => void
  onChange: (change: NetworkDefinitionChange) => void
  onOpenAgent?: () => void
  onSelectNetwork?: () => void
  onLocateOnCanvas?: () => void
}) {
  const node = selection.type === 'node' ? definition.nodes.find((item) => item.id === selection.id) ?? null : null
  const agent = node ? agents.find((item) => item.id === node.agent_id) ?? null : null
  const binding = node ? bindings?.[node.id] ?? null : null
  const errors = issues.filter((item) => item.severity === 'error')

  const view = node ? (
    <NetworkNodeInspector
      definition={definition}
      node={node}
      agent={agent}
      binding={binding}
      readOnly={readOnly}
      onChange={onChange}
      onOpenAgent={onOpenAgent}
      onLocateOnCanvas={onLocateOnCanvas}
    />
  ) : selection.type === 'edge' ? (
    <NetworkEdgeInspector definition={definition} edgeId={selection.id} agents={agents} readOnly={readOnly} onChange={onChange} />
  ) : (
    <NetworkOverviewInspector
      definition={definition}
      readOnly={readOnly}
      name={name}
      description={description}
      onMetadata={onMetadata}
      onChange={onChange}
    />
  )

  const content = (
    <>
      {selection.type !== 'network' && onSelectNetwork ? (
        <div className="shrink-0 border-b border-border bg-background/20 px-4 py-2">
          <button type="button" onClick={onSelectNetwork} className="inline-flex items-center gap-1 text-[9px] font-medium text-muted hover:text-white">
            <ChevronLeft className="h-3.5 w-3.5" />Network
          </button>
        </div>
      ) : null}
      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain">
        {view}
        {errors.length ? (
          <section className="m-4 rounded-xl border border-red-500/25 bg-red-500/5 p-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-3.5 w-3.5 text-red-400" />
              <p className="text-[10px] font-medium text-white">{errors.length} issue{errors.length === 1 ? '' : 's'} block this composition</p>
            </div>
            <ul className="mt-2 space-y-1">
              {errors.map((item, index) => <li key={`${item.code}-${item.nodeId ?? item.edgeId ?? index}`} className="text-[9px] leading-4 text-red-200">• {item.message}</li>)}
            </ul>
          </section>
        ) : null}
      </div>
    </>
  )

  if (embedded) return <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{content}</div>
  return <aside className="flex h-full min-h-0 w-[min(94vw,390px)] shrink-0 flex-col border-l border-border bg-surface/85">{content}</aside>
}
