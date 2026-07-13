import type { ReactNode } from 'react'
import { CheckCircle2, Search } from 'lucide-react'

import { ScrollArea } from '@/components/ui/ScrollArea'
import { cn } from '@/lib/utils'

import type { AgentNodeId, NetworkBinding, NetworkRun } from './networkWorkspaceTypes'
import { runHistory } from './networkPageData'

export type PanelTab = 'runs' | 'trace' | 'debug' | 'validation'
const surface = 'rounded-xl border border-border/75 bg-background/35'
const sourceTone = { staging: 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300', release: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300' } as const

export function Badge({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'staging' | 'production' | 'warning' | 'danger' }) {
  const styles = {
    default: 'border-border bg-background/50 text-muted',
    staging: sourceTone.staging,
    production: sourceTone.release,
    warning: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
    danger: 'border-red-500/30 bg-red-500/10 text-red-300',
  }
  return <span className={cn('rounded-md border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide', styles[tone])}>{children}</span>
}

function PanelTitle({ title, description }: { title: string; description: string }) {
  return <div className="shrink-0 border-b border-border/80 p-4"><h2 className="text-sm font-semibold text-white">{title}</h2><p className="mt-1 text-[10px] leading-4 text-muted">{description}</p></div>
}

export function Operations({ tab, run, draftBindings }: { tab: PanelTab; run: NetworkRun; draftBindings: Record<AgentNodeId, NetworkBinding> }) {
  if (tab === 'runs') {
    return (
      <div className="flex h-full min-h-0 flex-col">
        <PanelTitle title="Executions" description="Inspect Network path, composition and cost." />
        <div className="flex shrink-0 items-center gap-2 border-b border-border/70 p-3"><button className="rounded-md border border-primary/30 bg-primary/10 px-2 py-1 text-[10px] text-primary-light">All runs</button><Search className="ml-auto h-3.5 w-3.5 text-muted" /></div>
        <ScrollArea className="min-h-0 flex-1"><div className="space-y-2 p-3">{runHistory.map((item) => <div key={item.id} className={cn(surface, 'p-3')}><div className="flex items-start gap-2"><span className={cn('mt-1 h-2 w-2 rounded-full', item.status === 'success' ? 'bg-emerald-400' : 'bg-red-400')} /><div className="min-w-0 flex-1"><p className="truncate text-[11px] font-medium text-white">{item.title}</p><div className="mt-2 flex items-center gap-2"><Badge tone={item.environment === 'production' ? 'production' : 'staging'}>{item.environment}</Badge><span className="text-[9px] text-muted">{item.duration} · {item.cost}</span></div></div></div></div>)}</div></ScrollArea>
      </div>
    )
  }

  if (tab === 'trace') {
    return (
      <div className="flex h-full min-h-0 flex-col">
        <PanelTitle title="Trace path" description={`${run.title} · ${run.duration}`} />
        <ScrollArea className="min-h-0 flex-1"><div className="p-4">{run.path.map((node, index) => <div key={`${node}-${index}`} className="relative flex gap-3 pb-5"><span className="relative z-10 mt-1 h-3 w-3 rounded-full border-2 border-emerald-400 bg-emerald-500/20" />{index < run.path.length - 1 ? <span className="absolute left-[5px] top-4 h-full w-px bg-border" /> : null}<div className={cn(surface, 'flex-1 p-2.5')}><p className="text-[10px] font-medium capitalize text-white">{node}</p><p className="mt-1 text-[9px] text-muted">Exact source and version recorded</p>{run.traceId && index === 0 ? <p className="mt-2 font-mono text-[8px] text-primary-light">trace {run.traceId.slice(0, 12)}…</p> : null}</div></div>)}</div></ScrollArea>
      </div>
    )
  }

  if (tab === 'debug') {
    return (
      <div className="flex h-full min-h-0 flex-col">
        <PanelTitle title="Debug events" description="Raw Network orchestration events." />
        <ScrollArea className="min-h-0 flex-1"><div className="space-y-2 p-3 font-mono text-[9px]">{[['network.started', 'checksum=9c14f3a1'], ['node.entered', 'node=coordinator'], ['handoff.selected', 'key=billing_support'], ['network.completed', 'status=success']].map(([name, data]) => <div key={name} className={cn(surface, 'p-3')}><p className="text-primary-light">{name}</p><p className="mt-1 text-muted">{data}</p></div>)}</div></ScrollArea>
      </div>
    )
  }

  const drafts = Object.values(draftBindings).filter((item) => item.source === 'draft').length
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PanelTitle title="Validation" description="Readiness before coordinated promotion." />
      <div className="grid shrink-0 grid-cols-2 gap-2 border-b border-border p-3"><div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3"><p className="text-lg text-emerald-300">0</p><p className="text-[9px] text-muted">Blockers</p></div><div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3"><p className="text-lg text-amber-300">2</p><p className="text-[9px] text-muted">Warnings</p></div></div>
      <ScrollArea className="min-h-0 flex-1"><div className="space-y-2 p-3">{['One entry point', 'Every route reaches END', `${drafts} Draft binding${drafts === 1 ? '' : 's'} can be promoted`, 'All exact versions are available'].map((text) => <div key={text} className={cn(surface, 'flex gap-2 p-3')}><CheckCircle2 className="h-4 w-4 text-emerald-400" /><p className="text-[10px] text-white">{text}</p></div>)}</div></ScrollArea>
    </div>
  )
}
