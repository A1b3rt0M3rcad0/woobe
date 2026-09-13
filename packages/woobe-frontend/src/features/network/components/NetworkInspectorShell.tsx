import type { ReactNode } from 'react'
import { Bot, Maximize2, Minimize2, Workflow } from 'lucide-react'
import { Button, EmptyStatePanel, SegmentedControl } from '@woobe/ui'
import { cn } from '@/lib/utils'
import type { NetworkBinding } from './networkWorkspaceTypes'

export type InspectorContext = 'agent' | 'network'

export function NetworkInspectorShell({ context, selectedAgentDraft, selectedNetworkBinding, expanded, onContext, onExpand, agentWorkspace, networkWorkspace }: { context: InspectorContext; selectedAgentDraft: NetworkBinding | null; selectedNetworkBinding: NetworkBinding | null; expanded: boolean; onContext: (context: InspectorContext) => void; onExpand: () => void; agentWorkspace: ReactNode; networkWorkspace: ReactNode }) {
  return (
    <aside className={cn('absolute inset-y-0 right-0 z-workspace flex min-h-0 shrink-0 flex-col border-l border-border bg-surface/95 xl:relative xl:z-auto xl:bg-surface/75', expanded ? 'w-[min(96vw,720px)] xl:w-[720px]' : 'w-[min(94vw,520px)] xl:w-[520px]')}>
      <div className="flex shrink-0 items-center gap-ui-xs border-b border-border bg-background/20 p-ui-xs">
        <SegmentedControl
          className="min-w-0 flex-1"
          stretch
          size="compact"
          ariaLabel="Network inspector context"
          value={context}
          onValueChange={(value) => onContext(value as InspectorContext)}
          items={[
            { value: 'agent', label: 'Agent', icon: <Bot className="h-icon-sm w-icon-sm" />, disabled: !selectedAgentDraft },
            { value: 'network', label: 'Network', icon: <Workflow className="h-icon-sm w-icon-sm" /> },
          ]}
        />
        <Button type="button" variant="ghost" size="iconSm" onClick={onExpand} aria-label={expanded ? 'Collapse inspector' : 'Expand inspector'}>
          {expanded ? <Minimize2 className="h-icon w-icon" /> : <Maximize2 className="h-icon w-icon" />}
        </Button>
      </div>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {context === 'agent' ? (
          selectedAgentDraft && selectedNetworkBinding ? agentWorkspace : (
            <div className="flex h-full items-center justify-center p-ui-xl">
              <EmptyStatePanel
                compact
                icon={<Bot className="h-icon-lg w-icon-lg" />}
                title="Configure an Agent"
                description="Select an Agent node on the canvas to edit its Draft, inspect Versions and run an isolated Chat."
              />
            </div>
          )
        ) : networkWorkspace}
      </div>
    </aside>
  )
}
