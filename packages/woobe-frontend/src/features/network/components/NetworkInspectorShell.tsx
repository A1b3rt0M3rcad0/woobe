import type { ReactNode } from 'react'
import { Bot, Maximize2, Minimize2, Workflow } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { NetworkBinding } from './networkWorkspaceTypes'

export type InspectorContext = 'agent' | 'network'

export function NetworkInspectorShell({ context, selectedAgentDraft, selectedNetworkBinding, expanded, onContext, onExpand, agentWorkspace, networkWorkspace }: { context: InspectorContext; selectedAgentDraft: NetworkBinding | null; selectedNetworkBinding: NetworkBinding | null; expanded: boolean; onContext: (context: InspectorContext) => void; onExpand: () => void; agentWorkspace: ReactNode; networkWorkspace: ReactNode }) {
  return (
    <aside className={cn('absolute inset-y-0 right-0 z-40 flex min-h-0 shrink-0 flex-col border-l border-border bg-surface/95 shadow-2xl shadow-black/30 xl:relative xl:z-auto xl:bg-surface/75 xl:shadow-none', expanded ? 'w-[min(96vw,720px)] xl:w-[720px]' : 'w-[min(94vw,520px)] xl:w-[520px]')}>
      <div className="flex shrink-0 items-center gap-1 border-b border-border bg-background/20 p-1.5"><button disabled={!selectedAgentDraft} onClick={() => onContext('agent')} className={cn('flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-[11px] font-medium', context === 'agent' ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/70 hover:text-white', !selectedAgentDraft && 'cursor-not-allowed opacity-40')}><Bot className="h-3.5 w-3.5" />Agent</button><button onClick={() => onContext('network')} className={cn('flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-[11px] font-medium', context === 'network' ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/70 hover:text-white')}><Workflow className="h-3.5 w-3.5" />Network</button><button onClick={onExpand} className="rounded-lg border border-border/80 bg-background/35 p-2 text-muted hover:text-white">{expanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}</button></div>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{context === 'agent' ? (selectedAgentDraft && selectedNetworkBinding ? agentWorkspace : <div className="flex h-full items-center justify-center p-6 text-center"><div><Bot className="mx-auto h-7 w-7 text-muted" /><p className="mt-3 text-xs font-medium text-white">Configure an Agent</p><p className="mt-1 max-w-xs text-[10px] leading-4 text-muted">Select an Agent node on the canvas to edit its Draft, inspect Versions and run an isolated Chat.</p></div></div>) : networkWorkspace}</div>
    </aside>
  )
}
