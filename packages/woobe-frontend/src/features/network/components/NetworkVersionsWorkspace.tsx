import { ScrollArea } from '@/components/ui/ScrollArea'
import { cn } from '@/lib/utils'

import type { AgentNodeId, BindingSource, NetworkBinding } from './networkWorkspaceTypes'

const surface = 'rounded-xl border border-border/75 bg-background/35'
const smallButton = 'rounded-lg border border-border/80 bg-background/40 px-2.5 py-1.5 text-[10px] font-medium text-muted hover:border-primary/30 hover:text-white disabled:cursor-not-allowed disabled:opacity-45'

export function NetworkVersions({
  draftBindings,
  stagingBindings,
  productionBindings,
  onStage,
  onPublish,
  onRollback,
  onLoadNetwork,
}: {
  draftBindings: Record<AgentNodeId, NetworkBinding>
  stagingBindings: Record<AgentNodeId, NetworkBinding>
  productionBindings: Record<AgentNodeId, NetworkBinding>
  onStage: () => void
  onPublish: () => void
  onRollback: () => void
  onLoadNetwork: () => void
}) {
  const count = (items: Record<AgentNodeId, NetworkBinding>, type: BindingSource) => Object.values(items).filter((item) => item.source === type).length

  return (
    <ScrollArea className="min-h-0 flex-1 overscroll-contain">
      <div className="p-4">
        <div><p className="text-sm font-semibold text-white">Network lifecycle</p><p className="mt-1 text-[10px] leading-4 text-muted">Draft is mutable. Staging and Production preserve exact composition snapshots.</p></div>
        <div className="mt-4 space-y-2">
          <div className={cn(surface, 'p-3')}><div className="flex justify-between gap-3"><div><p className="text-[9px] uppercase text-muted">Draft Revision 29</p><p className="mt-1 text-[10px] text-white">{count(draftBindings, 'draft')} Draft · {count(draftBindings, 'staging')} Staging · {count(draftBindings, 'release')} Release</p></div><button onClick={onStage} className="rounded-lg bg-primary px-2.5 py-1.5 text-[9px] text-white">Stage</button></div></div>
          <div className="rounded-xl border border-indigo-500/30 bg-indigo-500/5 p-3"><div className="flex justify-between gap-3"><div><p className="text-[9px] uppercase text-indigo-300">Staging v0.12</p><p className="mt-1 text-[10px] text-white">{count(stagingBindings, 'staging')} Staging · {count(stagingBindings, 'release')} Release</p></div><button onClick={onPublish} className={smallButton}>Publish</button></div></div>
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-3"><p className="text-[9px] uppercase text-emerald-300">Production v0.10</p><p className="mt-1 text-[10px] text-white">{count(productionBindings, 'release')} immutable Agent Releases</p></div>
          <div className={cn(surface, 'p-3')}><div className="flex justify-between"><div><p className="font-mono text-[10px] text-white">Historical v0.8</p><p className="mt-1 text-[9px] text-muted">Exact composition preserved</p></div><span className="rounded-md border border-border bg-background/50 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-muted">Archived</span></div><div className="mt-3 flex gap-3"><button onClick={onLoadNetwork} className="text-[9px] text-indigo-300">Load to Draft</button><button onClick={onRollback} className="text-[9px] text-emerald-400">Rollback</button></div></div>
        </div>
      </div>
    </ScrollArea>
  )
}
