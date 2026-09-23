import { AlertTriangle, ChevronLeft } from 'lucide-react'
import { Alert, AlertDescription, Button } from '@woobe/ui'

import type { Agent } from '@/features/agents/types'

import type { NetworkDefinition } from '../types'
import type { NetworkDefinitionChange, NetworkEditorIssue, NetworkEditorSelection } from '../editor/types'
import { NetworkEdgeInspector } from './NetworkEdgeInspector'
import { NetworkNodeInspector } from './NetworkNodeInspector'
import { NetworkOverviewInspector } from './NetworkOverviewInspector'
import type { Environment, NetworkBinding } from './networkWorkspaceTypes'

export function NetworkGraphInspector({
  definition,
  agents,
  bindings,
  liveDraftContractsByAgentId,
  issues,
  selection,
  readOnly,
  environment = 'draft',
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
  liveDraftContractsByAgentId?: Record<string, unknown>
  issues: NetworkEditorIssue[]
  selection: NetworkEditorSelection
  readOnly: boolean
  environment?: Environment
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
      agents={agents}
      liveDraftContractsByAgentId={liveDraftContractsByAgentId}
      readOnly={readOnly}
      environment={environment}
      name={name}
      description={description}
      onMetadata={onMetadata}
      onChange={onChange}
    />
  )

  const content = (
    <>
      {selection.type !== 'network' && onSelectNetwork ? (
        <div className="shrink-0 border-b border-border bg-background/20 px-ui-md py-ui-sm">
          <Button type="button" size="sm" variant="ghost" onClick={onSelectNetwork}>
            <ChevronLeft className="mr-ui-xs h-icon-sm w-icon-sm" />Network
          </Button>
        </div>
      ) : null}
      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain">
        {view}
        {errors.length ? (
          <Alert variant="destructive" className="m-ui-md">
            <AlertDescription>
              <div className="flex items-center gap-ui-sm font-mono text-system-label font-semibold">
                <AlertTriangle className="h-icon w-icon" />
                {errors.length} issue{errors.length === 1 ? '' : 's'} block this composition
              </div>
              <ul className="mt-ui-sm space-y-ui-xs font-sans text-product-caption">
                {errors.map((item, index) => <li key={`${item.code}-${item.nodeId ?? item.edgeId ?? index}`}>• {item.message}</li>)}
              </ul>
            </AlertDescription>
          </Alert>
        ) : null}
      </div>
    </>
  )

  if (embedded) return <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{content}</div>
  return <aside className="flex h-full min-h-0 w-inspector max-w-[94vw] shrink-0 flex-col border-l border-border bg-surface/85">{content}</aside>
}
