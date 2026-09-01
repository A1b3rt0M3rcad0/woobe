import { GitBranch, Settings2, SlidersHorizontal, Workflow, type LucideIcon } from 'lucide-react'

import { ScrollArea } from '@/components/ui/ScrollArea'
import { cn } from '@/lib/utils'

import type { AgentNodeId, Environment, NetworkBinding, NetworkVersionOption } from './networkWorkspaceTypes'
import { CompositionSettings } from './NetworkCompositionSettings'

export type NetworkConfigSection = 'general' | 'composition' | 'routing' | 'runtime'

const surface = 'rounded-xl border border-border/75 bg-background/35'

function SecondaryTabs<T extends string>({
  value,
  items,
  onChange,
}: {
  value: T
  items: Array<{ id: T; label: string; icon: LucideIcon }>
  onChange: (value: T) => void
}) {
  return (
    <div className="flex shrink-0 gap-1 border-b border-border/80 bg-surface/60 p-1.5">
      {items.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          className={cn(
            'flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-2 py-2 text-[10px] font-medium',
            value === id
              ? 'border-primary/30 bg-primary/10 text-primary-light'
              : 'border-transparent text-muted hover:border-border/70 hover:text-white',
          )}
        >
          <Icon className="h-3.5 w-3.5" />
          {label}
        </button>
      ))}
    </div>
  )
}

function GeneralSettings({ readOnly }: { readOnly: boolean }) {
  return (
    <div className="space-y-4">
      <label className="block text-[10px] text-muted">
        Network name
        <input disabled={readOnly} defaultValue="Customer Support Network" className="mt-1.5 w-full rounded-xl border border-border bg-background/50 px-3 py-2.5 text-xs text-white outline-none focus:border-primary/40 disabled:opacity-50" />
      </label>
      <label className="block text-[10px] text-muted">
        Description
        <textarea disabled={readOnly} defaultValue="Routes customer requests to billing or technical support specialists." className="mt-1.5 min-h-28 w-full resize-none rounded-xl border border-border bg-background/50 px-3 py-2.5 text-xs leading-5 text-white outline-none focus:border-primary/40 disabled:opacity-50" />
      </label>
      <div className={cn(surface, 'p-3')}>
        <p className="text-[9px] uppercase tracking-wide text-muted">Entry point</p>
        <p className="mt-1 text-[10px] text-white">Coordinator</p>
      </div>
    </div>
  )
}

function RoutingSettings() {
  return (
    <div className="space-y-4">
      <div className={cn(surface, 'p-3')}><p className="text-[10px] font-medium text-white">Coordinator → Billing Specialist</p><p className="mt-1 text-[9px] text-muted">Condition: billing, invoice, refund or subscription intent.</p></div>
      <div className={cn(surface, 'p-3')}><p className="text-[10px] font-medium text-white">Coordinator → Technical Support</p><p className="mt-1 text-[9px] text-muted">Condition: API, incident, password or technical error intent.</p></div>
    </div>
  )
}

function RuntimeSettings({ readOnly }: { readOnly: boolean }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        <button disabled={readOnly} className="rounded-xl border border-primary/35 bg-primary/10 p-3 text-left disabled:opacity-50"><p className="text-[10px] font-medium text-white">Stateful</p><p className="mt-1 text-[9px] text-muted">Persistent Network sessions</p></button>
        <button disabled={readOnly} className="rounded-xl border border-border bg-background/35 p-3 text-left disabled:opacity-50"><p className="text-[10px] font-medium text-white">Stateless</p><p className="mt-1 text-[9px] text-muted">Independent requests</p></button>
      </div>
      <label className="block text-[10px] text-muted">Maximum hops<input disabled={readOnly} defaultValue="8" className="mt-1.5 w-full rounded-xl border border-border bg-background/50 px-3 py-2.5 text-xs text-white disabled:opacity-50" /></label>
    </div>
  )
}

export function NetworkConfiguration({
  section,
  environment,
  bindings,
  compositionNode,
  onSection,
  onCompositionNode,
  onUse,
}: {
  section: NetworkConfigSection
  environment: Environment
  bindings: Record<AgentNodeId, NetworkBinding>
  compositionNode: AgentNodeId
  onSection: (section: NetworkConfigSection) => void
  onCompositionNode: (node: AgentNodeId) => void
  onUse: (node: AgentNodeId, option: NetworkVersionOption) => void
}) {
  const readOnly = environment !== 'draft'
  const sections: Array<{ id: NetworkConfigSection; label: string; icon: LucideIcon }> = [
    { id: 'general', label: 'General', icon: SlidersHorizontal },
    { id: 'composition', label: 'Composition', icon: GitBranch },
    { id: 'routing', label: 'Routing', icon: Workflow },
    { id: 'runtime', label: 'Runtime', icon: Settings2 },
  ]

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="scrollbar-thin flex shrink-0 gap-1 overflow-x-auto border-b border-border p-1.5">
        {sections.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => onSection(id)}
            className={cn(
              'flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-2 text-[10px] font-medium',
              section === id ? 'border-primary/30 bg-primary/10 text-primary-light' : 'border-transparent text-muted hover:border-border/70 hover:text-white',
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      <ScrollArea className="min-h-0 flex-1 overscroll-contain">
        <div className="p-4">
          {readOnly ? <div className="mb-4 rounded-xl border border-border bg-background/35 p-3 text-[10px] text-muted">Viewing an exact read-only {environment} snapshot. Switch to Draft to change Network configuration or composition.</div> : null}
          {section === 'general' ? <GeneralSettings readOnly={readOnly} /> : null}
          {section === 'composition' ? <CompositionSettings bindings={bindings} compositionNode={compositionNode} readOnly={readOnly} onCompositionNode={onCompositionNode} onUse={onUse} /> : null}
          {section === 'routing' ? <RoutingSettings /> : null}
          {section === 'runtime' ? <RuntimeSettings readOnly={readOnly} /> : null}
        </div>
      </ScrollArea>
    </div>
  )
}
